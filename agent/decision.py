"""REUSABLE DECISION PATTERN: support ticket router  (#tool-selection)

What it does
    Before the support agent calls any tool, Strands Decider 2B reads the raw ticket text and
    answers two questions in a single call:
    - which support team should handle this ticket? (billing / security / technical / account /
      general)
    - how urgent is it? (low / medium / high / critical)

    The decider's output narrows the tool list that the Strands Agent may call. This is the
    tool-selection pattern: the decision shapes what the agent *can do*, not just what it says.
    A billing ticket gets billing tools; a security incident gets escalation tools. The agent
    cannot accidentally call the wrong team's workflow.

Typed questions and options
    `team` (choice): five teams, each described by the kinds of tickets they handle.
    `urgency` (score): four ordered levels, lowest first.

    See QUESTIONS below.

Wiring
    `TicketRouter` wraps `ToolSelector` from `decider_kit.patterns.tool_selection`. Before the
    Strands Agent is built, call `router.select(ticket_text)` to get the team and urgency, then
    use `router.tools_for_decision(team, urgency, confidence)` to get the narrowed tool list.

    In agent.py:
        router = TicketRouter(Decider())
        team, urgency, confidence, decisions = router.route(ticket_text)
        tools = router.tools_for_decision(team, urgency, confidence)
        agent = Agent(model=..., tools=tools, ...)

How to reuse it
    Copy this file, replace the five team options in QUESTIONS["team"]["criteria"] with your
    own categories (e.g. product lines, intent types, priority queues), update URGENCY_LEVELS
    if your rubric differs, and change the tool mapping in TicketRouter.tools_for_decision.
    The pattern needs no retraining: option descriptions carry the signal.

Confidence handling
    >= 0.80  route as decided
    0.60–0.79  route as decided, note "moderate confidence — review recommended"
    < 0.60   route to general, flag for human review regardless of label
"""

from __future__ import annotations

from typing import Any

from decider_kit import Decider
from decider_kit.patterns.tool_selection import ToolSelector

PATTERN_TAG = "#tool-selection"

URGENCY_LEVELS = ["low", "medium", "high", "critical"]

QUESTIONS: dict[str, dict[str, Any]] = {
    "team": Decider.choice(
        "Which support team should handle this ticket?",
        {
            "billing": "payment issues, charges, refunds, invoices, subscription cancellations, or disputed transactions",
            "security": "hacked accounts, unauthorized access, suspicious logins, password changed without consent, or data breach concerns",
            "technical": "software bugs, API errors, integration failures, performance issues, crashes, or broken features",
            "account": "login problems, forgotten passwords, account lockouts, profile changes, username or email updates, or access requests that are not security incidents",
            "general": "general questions, how-to requests, feature inquiries, pricing questions, onboarding help, or anything that does not fit the other categories",
        },
    ),
    "urgency": Decider.score(
        "How urgent is this support ticket?",
        URGENCY_LEVELS,
    ),
}

# Confidence threshold: below this the decider is unsure → fall back to general + human review
CONFIDENCE_THRESHOLD = 0.60
REVIEW_THRESHOLD = 0.80


class TicketRouter:
    """Routes a ticket to the right team and tool set using Strands Decider 2B.

    Usage:
        router = TicketRouter(Decider())
        team, urgency, confidence, decisions = router.route(ticket_text)
        tools = router.tools_for_decision(team, urgency, confidence)
    """

    def __init__(self, decider: Decider):
        self.decider = decider
        self.log: list[dict[str, Any]] = []

    def route(self, ticket_text: str) -> tuple[str, str, float, list[dict[str, Any]]]:
        """Call the decider and return (team, urgency, team_confidence, decision_records)."""
        answers = self.decider.ask(ticket_text, QUESTIONS)

        team_ans = answers["team"]
        urgency_ans = answers["urgency"]

        team = team_ans.label or "general"
        urgency = urgency_ans.label or "low"
        confidence = team_ans.confidence

        # Low confidence: route to general and flag for human review
        if confidence < CONFIDENCE_THRESHOLD:
            team = "general"
            flag = "low-confidence: routed to general for human review"
        elif confidence < REVIEW_THRESHOLD:
            flag = "moderate confidence: review recommended"
        else:
            flag = "high confidence"

        record: dict[str, Any] = {
            "pattern": PATTERN_TAG,
            "team": team,
            "urgency": urgency,
            "team_confidence": round(confidence, 3),
            "urgency_confidence": round(urgency_ans.confidence, 3),
            "flag": flag,
            "team_probabilities": {k: round(v, 3) for k, v in team_ans.probabilities.items()},
            "urgency_probabilities": {k: round(v, 3) for k, v in urgency_ans.probabilities.items()},
            "verdict": team,
            "decider_ms": round(self.decider.last_latency_ms or 0),
            "probabilities": {k: round(v, 3) for k, v in team_ans.probabilities.items()},
        }
        self.log.append(record)
        return team, urgency, confidence, [record]

    def tools_for_decision(self, team: str, urgency: str, confidence: float) -> list[Any]:
        """Return the narrowed tool list for this team and urgency combination."""
        from .tools import (
            classify_and_route,
            draft_response,
            escalate,
            lookup_customer,
        )

        # classify_and_route is always available
        always = [classify_and_route, draft_response]

        # Security incidents or critical urgency: escalate immediately
        if team == "security" or urgency == "critical":
            return [*always, lookup_customer, escalate]

        # Billing and account: need customer context
        if team in ("billing", "account"):
            return [*always, lookup_customer]

        # Technical and general: just draft a response
        return always
