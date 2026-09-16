from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from .. import schemas, auth
from ..database import get_db, SessionLocal
from ..ai.agent import run_agent
from ..ai.live_proxy import run_live_session

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/chat", response_model=schemas.AIChatResponse)
def chat(payload: schemas.AIChatRequest, request: Request, db: Session = Depends(get_db)):
    """
    company_id and user_id are derived from the authenticated session
    here, in the endpoint - never taken from the request body, and never
    passed to Gemini for it to choose. This is the one place tenant
    identity enters the whole AI pipeline.
    """
    company_id = auth.get_current_company_id(request)
    user_id = auth.get_current_username(request)

    history = [{"role": m.role, "text": m.text} for m in payload.history]
    result = run_agent(db, company_id, user_id, history)

    return schemas.AIChatResponse(reply=result["reply"], tool_calls=result["tool_calls"])


@router.websocket("/live/ws")
async def live_voice(websocket: WebSocket, token: str = ""):
    """
    Voice entry point - a browser WebSocket can't send custom headers on
    connect, so the auth token travels as a query parameter here instead
    of the Authorization header the rest of the app uses. Everything past
    this point (deriving company_id, executing tools, logging) works
    exactly like the text-chat endpoint.
    """
    if auth.is_auth_required():
        payload = auth.decode_token(token)
        if payload is None:
            await websocket.close(code=4401)
            return
        company_id = payload.get("company_id")
        user_id = payload.get("username")
    else:
        company_id = None
        user_id = None

    await websocket.accept()
    try:
        await run_live_session(websocket, company_id, user_id, SessionLocal)
    except WebSocketDisconnect:
        pass
