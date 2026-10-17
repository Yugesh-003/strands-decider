"""TicketPilot tools: classify, look up customers, draft responses, and escalate.

Each tool has a clear one-line docstring — the model reads it and the tool-selection pattern
uses the first line as the option description.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from strands import tool

# ---------------------------------------------------------------------------
# Mock data — loaded once at import time
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent / "data"


def _load_customers() -> dict[str, dict]:
    path = _DATA_DIR / "customers.json"
    if not path.exists():
        return {}
    records = json.loads(path.read_text())
    return {r["customer_id"]: r for r in records}


def _load_tickets() -> dict[str, dict]:
    path = _DATA_DIR / "tickets.json"
    if not path.exists():
        return {}
    records = json.loads(path.read_text())
    return {r["ticket_id"]: r for r in records}


CUSTOMERS = _load_customers()
TICKETS = _load_tickets()

# SLA targets by urgency
SLA_MAP = {
    "critical": "1 hour",
    "high": "4 hours",
    "medium": "1 business day",
    "low": "3 business days",
}

ESCALATION_LOG: list[dict] = []


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
def classify_and_route(team: str, priority: str) -> dict:
    """Record the routing decision for this ticket and return the assigned team and SLA target."""
    sla = SLA_MAP.get(priority.lower(), "3 business days")
    return {
        "routed_to": team,
        "priority": priority,
        "sla_target": sla,
        "message": f"Ticket routed to the {team} team. SLA: {sla}.",
    }


@tool
def lookup_customer(ticket_id: str) -> dict:
    """Retrieve the customer record and ticket history for a given ticket ID."""
    ticket = TICKETS.get(ticket_id.strip().upper())
    if not ticket:
        # Try partial match
        upper = ticket_id.strip().upper()
        ticket = next((t for tid, t in TICKETS.items() if upper in tid), None)
    if not ticket:
        return {"error": f"No ticket found with ID '{ticket_id}'. Available IDs: {list(TICKETS.keys())[:5]}"}

    customer = CUSTOMERS.get(ticket["customer_id"])
    if not customer:
        return {"ticket": ticket, "customer": None}

    return {
        "ticket_id": ticket["ticket_id"],
        "subject": ticket["subject"],
        "customer_id": customer["customer_id"],
        "customer_name": customer["name"],
        "email": customer["email"],
        "account_status": customer["account_status"],
        "plan": customer["plan"],
        "recent_tickets": customer["recent_tickets"],
    }


@tool
def draft_response(team: str, issue_summary: str) -> dict:
    """Draft a professional first-response email for the customer, tailored to the routed team."""
    # The LLM (Bedrock/ugmdu) generates the actual email via the Strands Agent.
    # This tool provides structured context; the agent writes the email as its reply.
    tone_map = {
        "billing": "empathetic and assuring, acknowledging the financial concern",
        "security": "urgent and reassuring, prioritising account safety",
        "technical": "clear and methodical, showing technical competence",
        "account": "helpful and patient, guiding through account recovery",
        "general": "friendly and informative",
    }
    tone = tone_map.get(team.lower(), "professional and helpful")
    return {
        "team": team,
        "issue_summary": issue_summary,
        "tone": tone,
        "instruction": (
            f"Write a short, professional first-response email to the customer. "
            f"Tone: {tone}. Acknowledge their issue, confirm it has been routed to the {team} team, "
            f"state the SLA, and offer next steps. Keep it under 120 words."
        ),
    }


@tool
def escalate(reason: str, team: str) -> dict:
    """Escalate this ticket for immediate human review and return an escalation ID."""
    escalation_id = f"ESC-{uuid.uuid4().hex[:6].upper()}"
    record = {
        "escalation_id": escalation_id,
        "team": team,
        "reason": reason,
        "status": "escalated",
        "assigned_to": f"{team.capitalize()} Team — Senior Agent",
        "estimated_response": "Within 1 hour",
    }
    ESCALATION_LOG.append(record)
    return record


TOOLS = [classify_and_route, lookup_customer, draft_response, escalate]
