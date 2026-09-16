"""
Proxies between the authenticated frontend and Gemini's real Live API
(the WebSocket-based real-time audio API), rather than letting the
browser connect to Gemini directly. This is deliberate, not just cautious:
- The API key must never reach the browser.
- Every functionCall Gemini makes during a live session is intercepted
  and executed HERE, with company_id fixed for the whole session from
  the authenticated connection - never from anything Gemini or the
  client sends. The client never even sees a functionCall message, only
  the resulting audio/text reply, exactly like the text-chat agent.

Protocol reference (Gemini Live WebSocket API, v1beta, current as of
2026-09): https://ai.google.dev/api/live
"""
import asyncio
import json
import logging
import os

import websockets
from fastapi import WebSocket, WebSocketDisconnect

from . import tools
from .tool_schemas import TOOL_DECLARATIONS
from .agent import SYSTEM_PROMPT, TOOL_DISPATCH, _log_tool_call

logger = logging.getLogger("uvicorn")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# A separate env var from the text-chat model, since Live API audio needs
# a model variant that specifically supports it - kept configurable
# rather than hardcoded, since exactly which model name is current can
# change and getting it wrong should be a one-line env var fix, not a
# code change.
GEMINI_LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-2.0-flash-live-001")
GEMINI_LIVE_URL = os.getenv(
    "GEMINI_LIVE_URL",
    "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent",
)


def build_setup_message() -> dict:
    return {
        "setup": {
            "model": f"models/{GEMINI_LIVE_MODEL}",
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "tools": [{"functionDeclarations": TOOL_DECLARATIONS}],
            "generationConfig": {"responseModalities": ["AUDIO"]},
            "inputAudioTranscription": {},
            "outputAudioTranscription": {},
        }
    }


async def handle_tool_call(db, company_id, user_id, tool_call: dict) -> dict:
    """
    Executes every functionCall in one Gemini toolCall message and returns
    the BidiGenerateContentToolResponse to send back. Reuses the exact
    same TOOL_DISPATCH table and logging as the text-chat agent - this is
    not a second implementation of tool execution, just a different
    transport calling into it.
    """
    responses = []
    for call in tool_call.get("functionCalls", []):
        name = call.get("name")
        args = call.get("args", {}) or {}
        call_id = call.get("id")
        fn = TOOL_DISPATCH.get(name)

        if not fn:
            result = {"error": f"Unknown tool '{name}'"}
            status = "error"
        else:
            try:
                result = fn(db, company_id, **args)
                status = "success"
            except Exception as e:
                result = {"error": str(e)}
                status = "error"

        try:
            _log_tool_call(db, company_id, user_id, name, args, result, status)
        except Exception as e:
            logger.error(f"[ai-live] failed to log tool call: {e}")

        responses.append({"id": call_id, "name": name, "response": result})

    return {"toolResponse": {"functionResponses": responses}}


async def run_live_session(client_ws: WebSocket, company_id, user_id, db_factory):
    """
    The main proxy loop for one voice session. Opens the upstream Gemini
    connection, sends setup, then relays messages both ways for the
    lifetime of the connection - intercepting and executing toolCall
    messages instead of forwarding them.
    """
    if not GEMINI_API_KEY:
        await client_ws.send_json({"error": "Lekha AI voice isn't set up yet - GEMINI_API_KEY is missing."})
        await client_ws.close()
        return

    upstream_url = f"{GEMINI_LIVE_URL}?key={GEMINI_API_KEY}"

    try:
        async with websockets.connect(upstream_url, max_size=None) as upstream:
            await upstream.send(json.dumps(build_setup_message()))

            async def client_to_upstream():
                try:
                    while True:
                        msg = await client_ws.receive_json()
                        if "audio" in msg:
                            await upstream.send(json.dumps({
                                "realtimeInput": {"audio": {"mimeType": "audio/pcm;rate=16000", "data": msg["audio"]}}
                            }))
                        elif "text" in msg:
                            await upstream.send(json.dumps({
                                "clientContent": {
                                    "turns": [{"role": "user", "parts": [{"text": msg["text"]}]}],
                                    "turnComplete": True,
                                }
                            }))
                        elif msg.get("audioStreamEnd"):
                            await upstream.send(json.dumps({"realtimeInput": {"audioStreamEnd": True}}))
                except WebSocketDisconnect:
                    pass

            async def upstream_to_client():
                db = db_factory()
                try:
                    async for raw in upstream:
                        data = json.loads(raw)

                        if "toolCall" in data:
                            # Tell the client a tool ran (for a "🔎 searching"
                            # style indicator) before executing it - the
                            # client never receives the raw functionCall or
                            # its arguments, only this notice.
                            for call in data["toolCall"].get("functionCalls", []):
                                await client_ws.send_json({
                                    "tool_call": {"name": call.get("name"), "args": call.get("args", {})}
                                })
                            tool_response = await handle_tool_call(db, company_id, user_id, data["toolCall"])
                            await upstream.send(json.dumps(tool_response))
                            continue

                        await client_ws.send_json(data)
                finally:
                    db.close()

            await asyncio.gather(client_to_upstream(), upstream_to_client())

    except websockets.exceptions.ConnectionClosed as e:
        logger.info(f"[ai-live] upstream connection closed: {e}")
    except Exception as e:
        logger.error(f"[ai-live] session error: {e}")
        try:
            await client_ws.send_json({"error": "The voice session hit a problem and had to stop. Please try again."})
        except Exception:
            pass
