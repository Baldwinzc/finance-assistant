from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from valuation_agent.agent import ValuationAgent
from valuation_agent.models import AssetCandidate, Resolution


app = FastAPI(title="Finance Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ResolveRequest(BaseModel):
    query: str
    history: list[ConversationMessage] = Field(default_factory=list)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/resolve")
def resolve(request: ResolveRequest) -> dict:
    agent = ValuationAgent()
    history = [message.dict() for message in request.history[-10:]]
    resolution = agent.resolve(request.query, history=history)
    return serialize_resolution(resolution)


def serialize_resolution(resolution: Resolution) -> dict:
    payload = {
        "query": resolution.query,
        "asset_type": resolution.asset_type.value,
        "primary": serialize_candidate(resolution.primary) if resolution.primary else None,
        "candidates": [serialize_candidate(candidate) for candidate in resolution.candidates],
        "explanation": resolution.explanation,
        "needs_clarification": resolution.needs_clarification,
        "clarification_question": resolution.clarification_question,
    }
    if resolution.debug.get("error_code"):
        payload["error_code"] = resolution.debug["error_code"]
        payload["error_detail"] = resolution.debug.get("error_detail", resolution.explanation)
    return payload


def serialize_candidate(candidate: AssetCandidate) -> dict:
    return {
        "asset_type": candidate.asset_type.value,
        "symbol": candidate.symbol,
        "name": candidate.name,
        "score": candidate.score,
        "reason": candidate.reason,
        "display_name": candidate.display_name,
    }
