from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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


class ResolveRequest(BaseModel):
    query: str


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/resolve")
def resolve(request: ResolveRequest) -> dict:
    agent = ValuationAgent()
    resolution = agent.resolve(request.query)
    return serialize_resolution(resolution)


def serialize_resolution(resolution: Resolution) -> dict:
    return {
        "query": resolution.query,
        "asset_type": resolution.asset_type.value,
        "primary": serialize_candidate(resolution.primary) if resolution.primary else None,
        "candidates": [serialize_candidate(candidate) for candidate in resolution.candidates],
        "explanation": resolution.explanation,
        "needs_clarification": resolution.needs_clarification,
        "clarification_question": resolution.clarification_question,
    }


def serialize_candidate(candidate: AssetCandidate) -> dict:
    return {
        "asset_type": candidate.asset_type.value,
        "symbol": candidate.symbol,
        "name": candidate.name,
        "score": candidate.score,
        "reason": candidate.reason,
        "display_name": candidate.display_name,
    }
