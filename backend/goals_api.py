"""Customer-stated goals ("keep €8,000 available for my renovation").

  POST   /me/goals/parse   -> {proposal} (deterministic parse, optional Gemini; nothing is stored)
  POST   /me/goals         -> stored goal (the customer confirmed the proposal)
  GET    /me/goals         -> the caller's goals
  DELETE /me/goals/{id}    -> remove one of the caller's goals

The customer id comes only from the token. Goals change what the idle-cash rule
counts as idle; the typed sentence itself is never stored or logged.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field

import auth
import config
from engine.intent import parse_goal
from engine.models import Goal, GoalPurpose

router = APIRouter()

GOAL_ID = r"^g_[a-f0-9]{12}$"


class ParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=300)
    lang: Literal["nl", "en", "fr"] = "nl"


class GoalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: GoalPurpose
    amount: float = Field(gt=0, le=1_000_000)
    keep_accessible: bool = Field(default=True, strict=True)


def _api() -> Any:
    import api  # late import: api.py includes this router
    return api


def _log(customer_id: str, decision: str, goal: Goal) -> None:
    reason = f"{goal.purpose} €{goal.amount:,.0f}" + (", keep available" if goal.keep_accessible else "")
    _api().store.log_decisions([{
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "customer_id": customer_id,
        "moment_type": None, "source": "customer", "stakes": None, "decision": decision, "reason": reason,
        "score": None, "channel": None, "delivery": None}])


@router.post("/me/goals/parse")
def parse(body: ParseRequest, customer_id: str = Depends(auth.current_customer_id)) -> dict[str, Any]:
    _api()._customer(customer_id)
    return {"proposal": parse_goal(body.text, body.lang)}


@router.post("/me/goals", status_code=status.HTTP_201_CREATED, response_model=Goal)
def create(body: GoalCreate, customer_id: str = Depends(auth.current_customer_id)) -> Goal:
    api = _api()
    api._customer(customer_id)
    goal = Goal(id="g_" + secrets.token_hex(6), purpose=body.purpose, amount=body.amount,
                keep_accessible=body.keep_accessible, created=config.today())
    try:
        api.store.add_goal(customer_id, goal)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    _log(customer_id, "goal_set", goal)
    return goal


@router.get("/me/goals")
def list_goals(customer_id: str = Depends(auth.current_customer_id)) -> dict[str, Any]:
    api = _api()
    api._customer(customer_id)
    return {"goals": [g.model_dump(mode="json") for g in api.store.list_goals(customer_id)]}


@router.delete("/me/goals/{goal_id}")
def delete(goal_id: str = Path(pattern=GOAL_ID), customer_id: str = Depends(auth.current_customer_id)) -> dict[str, Any]:
    api = _api()
    api._customer(customer_id)
    goal = api.store.delete_goal(customer_id, goal_id)
    if goal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such goal")
    _log(customer_id, "goal_deleted", goal)
    return {"ok": True, "id": goal_id}
