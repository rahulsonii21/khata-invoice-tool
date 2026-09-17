"""
The Lekha AI agent loop. Gemini decides which tool (if any) is needed;
this module executes it against the real database and feeds the result
back to Gemini, looping until it produces a final answer. Gemini never
sees the database directly and never receives or chooses company_id -
that's fixed for the whole conversation, derived from the authenticated
session before this loop ever starts.
"""
import json
import os

import httpx

from . import tools
from .tool_schemas import TOOL_DECLARATIONS
from .. import models

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

MAX_TOOL_ROUNDS = 5  # a safety cap - a genuine multi-step request needs a
                      # handful of calls, but this stops a confused loop
                      # from running forever

SYSTEM_PROMPT = """You are Lekha AI, a business assistant for a wholesale agri-inputs business in India. You help the owner check balances, stock, do calculations, and now also create parties and invoices, by talking naturally in English, Hindi, or Hinglish - respond in whichever the user used.

Rules:
1. Never invent business data - a balance, a stock number, an overdue amount. Always use a tool to look it up.
2. Never do arithmetic yourself - always call the calculate tool, even for something that looks simple.
3. If a tool result says a name is ambiguous (multiple matches), ask the user which one they meant - do not guess.
4. If a tool finds nothing, say so plainly rather than making something up.
5. Be concise. Answer the question directly, in a sentence or two, not a report.
6. For anything that creates or changes data (a new party, a new invoice, a stock transfer): ALWAYS call the propose_* tool first, show the user its exact summary, and wait for an explicit yes/haan/confirm before ever calling the matching confirm_* tool. Never call a confirm_* tool without that explicit go-ahead having just happened in this conversation. If propose_* comes back with a duplicate_warning, ambiguous result, or error instead of requires_confirmation, relay that to the user and ask what they want - do not proceed to confirm.
7. When calling a confirm_* tool, use the exact same arguments the matching propose_* call returned (especially IDs like party_id, item_id, location IDs) - do not re-derive them.
8. For payment reminders: use draft_payment_reminder. This only drafts a message - it never sends anything, since there's no way for you to actually send a WhatsApp message. Tell the user the message is ready for them to send, don't say you've sent it.
9. Nothing else is possible yet. If asked, say so plainly and that it's coming in a future update.
"""

TOOL_DISPATCH = {
    "search_party": tools.search_party,
    "get_party_balance": tools.get_party_balance,
    "get_business_summary": tools.get_business_summary,
    "list_sales_invoices": tools.list_sales_invoices,
    "list_purchase_invoices": tools.list_purchase_invoices,
    "get_stock": tools.get_stock,
    "get_low_stock_items": tools.get_low_stock_items,
    "calculate": tools.calculate,
    "propose_create_party": tools.propose_create_party,
    "confirm_create_party": tools.confirm_create_party,
    "propose_create_invoice": tools.propose_create_invoice,
    "confirm_create_invoice": tools.confirm_create_invoice,
    "draft_payment_reminder": tools.draft_payment_reminder,
    "propose_stock_transfer": tools.propose_stock_transfer,
    "confirm_stock_transfer": tools.confirm_stock_transfer,
}


def _log_tool_call(db, company_id, user_id, tool_name, args, result, status):
    db.add(models.AIToolCallLog(
        company_id=company_id,
        user_id=user_id,
        tool_name=tool_name,
        arguments_json=json.dumps(args, default=str),
        result_json=json.dumps(result, default=str)[:5000],  # cap - this is a log, not a data store
        status=status,
    ))
    db.commit()


def run_agent(db, company_id, user_id, history: list) -> dict:
    """
    history: list of {"role": "user"|"model", "text": str} - the whole
    conversation so far, including the newest user message. Returns
    {"reply": str, "tool_calls": [{"name": str, "args": dict}, ...]}
    so the frontend can show what the agent actually did, not just the
    final sentence.
    """
    if not GEMINI_API_KEY:
        return {"reply": "Lekha AI isn't set up yet - GEMINI_API_KEY is missing.", "tool_calls": []}

    contents = [{"role": h["role"], "parts": [{"text": h["text"]}]} for h in history]
    tool_calls_made = []

    for _ in range(MAX_TOOL_ROUNDS):
        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "tools": [{"functionDeclarations": TOOL_DECLARATIONS}],
            "generationConfig": {"temperature": 0.2},
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload)

        if resp.status_code != 200:
            return {"reply": f"Something went wrong talking to the AI ({resp.status_code}). Please try again.", "tool_calls": tool_calls_made}

        data = resp.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError):
            return {"reply": "I didn't get a usable response - please try again.", "tool_calls": tool_calls_made}

        function_call_part = next((p for p in parts if "functionCall" in p), None)

        if not function_call_part:
            # A plain text answer - the agent is done.
            text = "".join(p.get("text", "") for p in parts).strip()
            return {"reply": text or "I'm not sure how to answer that.", "tool_calls": tool_calls_made}

        call = function_call_part["functionCall"]
        tool_name = call["name"]
        args = call.get("args", {})
        fn = TOOL_DISPATCH.get(tool_name)

        if not fn:
            result = {"error": f"Unknown tool '{tool_name}'"}
            status = "error"
        else:
            try:
                result = fn(db, company_id, **args)
                status = "success"
            except Exception as e:
                result = {"error": str(e)}
                status = "error"

        _log_tool_call(db, company_id, user_id, tool_name, args, result, status)
        tool_calls_made.append({"name": tool_name, "args": args, "result": result})

        # Feed the model's own function-call turn back in, then the result,
        # exactly as Gemini's function-calling protocol expects - it needs
        # to see that it asked for this before it sees the answer.
        contents.append({"role": "model", "parts": [{"functionCall": call}]})
        contents.append({"role": "user", "parts": [{"functionResponse": {"name": tool_name, "response": result}}]})

    return {"reply": "That took more steps than expected - could you rephrase or break it into smaller questions?", "tool_calls": tool_calls_made}
