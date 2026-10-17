"""TicketPilot — AI Customer Support Dispatcher.

Strands Decider 2B classifies the ticket team and urgency in one call before the LLM acts.
The decider's output narrows the tools available to the Strands Agent (tool-selection pattern):
billing tickets get billing tools, security incidents get escalation tools, and so on.

    from agent.agent import HackathonAgent
    out = HackathonAgent().chat("I was charged twice this month and need a refund.")
    out["reply"], out["decisions"]
"""

from __future__ import annotations

import time
from typing import Any

from strands import Agent

from decider_kit import Decider
from decider_kit.llm import agent_model, default_model_id, image_blocks, strip_thinking

from .decision import QUESTIONS, TicketRouter
from .tools import TOOLS

NAME = "TicketPilot — AI Customer Support Dispatcher"

SYSTEM_PROMPT = """You are TicketPilot, an AI customer support dispatcher.

Your job:
1. Call classify_and_route with the team and priority decided by the routing system.
2. If the tools available include lookup_customer, call it with the ticket ID from the message
   (look for patterns like T001, T002, etc.; if none is given, use "T001" as a placeholder).
3. Call draft_response with the team and a brief summary of the customer's issue.
4. If escalate is available, call it with a clear reason and the team name.

After all tool calls, write a clear, structured reply to the customer that includes:
- A summary of their issue
- Which team is handling it and the SLA
- The escalation ID (if escalated)
- The drafted first-response email

Be professional, empathetic, and concise."""


class HackathonAgent:
    """TicketPilot: Strands Decider 2B routes the ticket, Strands Agent handles the rest."""

    def __init__(self, decider: Decider | None = None, model_id: str | None = None, eager: bool | None = None):
        import os

        self.decider = decider or Decider()
        self.eager = eager if eager is not None else os.environ.get("DEMO_EAGER") == "1"
        self.model_id = model_id or default_model_id()
        self.router = TicketRouter(self.decider)

    def chat(self, message: str, session_id: str = "default", images: list[Any] | None = None) -> dict[str, Any]:
        """Route the ticket, narrow the tools, run the Strands Agent, return the reply."""
        t0 = time.perf_counter()

        # ── Step 1: Strands Decider 2B makes the routing decision ──────────────
        before_log = len(self.router.log)
        team, urgency, confidence, _ = self.router.route(message)
        decision_records = self.router.log[before_log:]

        # ── Step 2: narrow the tool set based on the decision ──────────────────
        narrowed_tools = self.router.tools_for_decision(team, urgency, confidence)

        # ── Step 3: build a fresh Strands Agent with only the narrowed tools ───
        agent = Agent(
            model=agent_model(self.model_id),
            system_prompt=SYSTEM_PROMPT,
            tools=narrowed_tools,
            callback_handler=None,
        )

        # ── Step 4: run the agent ──────────────────────────────────────────────
        content = [*image_blocks(images), {"text": message}] if images else message
        result = agent(content, invocation_state={"images": list(images or [])})
        reply = strip_thinking(str(result))

        # ── Step 5: package the response ──────────────────────────────────────
        # Format decisions for the demo panel: include probabilities and verdict
        formatted_decisions = []
        for rec in decision_records:
            formatted_decisions.append({
                "pattern": rec.get("pattern"),
                "team": rec.get("team"),
                "urgency": rec.get("urgency"),
                "verdict": rec.get("verdict"),
                "team_confidence": rec.get("team_confidence"),
                "urgency_confidence": rec.get("urgency_confidence"),
                "flag": rec.get("flag"),
                "probabilities": rec.get("team_probabilities", rec.get("probabilities", {})),
                "urgency_probabilities": rec.get("urgency_probabilities", {}),
                "decider_ms": rec.get("decider_ms"),
            })

        return {
            "reply": reply,
            "decisions": formatted_decisions,
            "model_id": self.model_id,
            "latency_ms": round((time.perf_counter() - t0) * 1000),
            "agent": NAME,
            "eager": self.eager,
        }


if __name__ == "__main__":
    import json
    import sys

    a = HackathonAgent()
    tickets = sys.argv[1:] or [
        "I was charged twice this month. My invoice shows two identical charges. Please refund.",
        "Someone hacked my account and changed my email. I need immediate help.",
        "The API is returning 500 errors on the /v2/reports endpoint. This is breaking production.",
    ]
    for t in tickets:
        print(json.dumps(a.chat(t), indent=2))
