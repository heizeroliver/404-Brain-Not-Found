"""In-memory state for the demo: customers, feedback, deliveries, decision log.

Everything except the decision log lives in memory on purpose: a restart resets
the demo. The decision log is append-only (memory + JSONL file, git-ignored).
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from engine.models import Consents, Customer, Goal

log = logging.getLogger("foresight.store")

MAX_GOALS = 10

FeedbackAction = str  # validated by the API model (not_now | not_relevant | never | helpful)

SUPPRESS_DAYS = {"not_now": 14, "not_relevant": 90, "never": 10 ** 6}


class Store:
    def __init__(self, customers_path: Path, decision_log_path: Path | None) -> None:
        self._lock = threading.Lock()
        self.customers: dict[str, Customer] = {}
        self.feedback: list[dict[str, Any]] = []
        self.deliveries: list[dict[str, Any]] = []
        self.decision_log: list[dict[str, Any]] = []
        self.goals: dict[str, list[Goal]] = {}
        self.decision_log_path = decision_log_path
        self.load_customers(customers_path)

    # -------------------------------------------------------------- customers
    def load_customers(self, path: Path) -> None:
        if not path.exists():
            log.warning("No customer dataset at %s. Run `python data/generate.py`.", path)
            return
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.customers = {c["id"]: Customer.model_validate(c) for c in raw["customers"]}
        log.info("Loaded %d customers", len(self.customers))

    def get_customer(self, customer_id: str) -> Customer | None:
        return self.customers.get(customer_id)

    def set_consents(self, customer_id: str, consents: Consents) -> Consents:
        with self._lock:
            customer = self.customers[customer_id]
            customer.consents = consents
            return customer.consents

    # --------------------------------------------------------------- feedback
    def add_feedback(self, customer_id: str, moment_type: str, action: FeedbackAction,
                     when: datetime | None = None) -> dict[str, Any]:
        entry = {
            "customer_id": customer_id,
            "moment_type": moment_type,
            "action": action,
            "ts": (when or datetime.now(timezone.utc)).isoformat(),
        }
        with self._lock:
            self.feedback.append(entry)
        return entry

    def feedback_count(self, customer_id: str) -> int:
        return sum(1 for fb in self.feedback if fb["customer_id"] == customer_id)

    def is_suppressed(self, customer_id: str, moment_type: str, today: date) -> str | None:
        """Return the feedback action that suppresses this moment today, if any."""
        for fb in reversed(self.feedback):
            if fb["customer_id"] != customer_id or fb["moment_type"] != moment_type:
                continue
            days = SUPPRESS_DAYS.get(fb["action"])
            if days is None:
                continue
            since = datetime.fromisoformat(fb["ts"]).date()
            if (today - since).days <= days:
                return fb["action"]
        return None

    def affinity(self, customer_id: str, moment_type: str) -> float:
        score = 1.0
        for fb in self.feedback:
            if fb["customer_id"] != customer_id or fb["moment_type"] != moment_type:
                continue
            if fb["action"] == "helpful":
                score *= 1.25
            elif fb["action"] == "not_relevant":
                score *= 0.5
        return max(0.25, min(2.0, score))

    def opt_out_count(self) -> int:
        return sum(1 for fb in self.feedback if fb["action"] == "never")

    # ------------------------------------------------------------------ goals
    def add_goal(self, customer_id: str, goal: Goal) -> Goal:
        with self._lock:
            goals = self.goals.setdefault(customer_id, [])
            if len(goals) >= MAX_GOALS:
                raise ValueError(f"At most {MAX_GOALS} goals per customer")
            goals.append(goal)
            return goal

    def list_goals(self, customer_id: str) -> list[Goal]:
        return list(self.goals.get(customer_id, []))

    def delete_goal(self, customer_id: str, goal_id: str) -> Goal | None:
        with self._lock:
            goals = self.goals.get(customer_id, [])
            for i, g in enumerate(goals):
                if g.id == goal_id:
                    return goals.pop(i)
        return None

    def goals_count(self) -> int:
        return sum(len(g) for g in self.goals.values())

    def with_goals(self, customer: Customer) -> Customer:
        """A copy of the customer with their stated goals attached, for the rules to read."""
        return customer.model_copy(update={"goals": self.list_goals(customer.id)})

    # ------------------------------------------------------------- deliveries
    def record_delivery(self, customer_id: str, moment_type: str, today: date) -> None:
        with self._lock:
            self.deliveries.append({"customer_id": customer_id, "moment_type": moment_type,
                                    "date": today.isoformat()})

    def recent_deliveries(self, customer_id: str, today: date, days: int = 7) -> list[str]:
        cutoff = today - timedelta(days=days)
        return [d["moment_type"] for d in self.deliveries
                if d["customer_id"] == customer_id and date.fromisoformat(d["date"]) >= cutoff]

    # ----------------------------------------------------------- decision log
    def log_decisions(self, entries: list[dict[str, Any]]) -> None:
        if not entries:
            return
        with self._lock:
            self.decision_log.extend(entries)
            if self.decision_log_path is not None:
                try:
                    self.decision_log_path.parent.mkdir(parents=True, exist_ok=True)
                    with self.decision_log_path.open("a", encoding="utf-8") as fh:
                        for entry in entries:
                            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
                except OSError as exc:  # never break a request over the audit file
                    log.error("Could not append to decision log: %s", exc)

    def decision_log_tail(self, n: int = 30) -> list[dict[str, Any]]:
        return list(self.decision_log[-n:])
