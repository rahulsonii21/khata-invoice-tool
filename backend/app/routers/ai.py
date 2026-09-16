from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import schemas, auth
from ..database import get_db
from ..ai.agent import run_agent

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
