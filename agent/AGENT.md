# TicketPilot — AI Customer Support Dispatcher

## What it does

TicketPilot reads an incoming customer support ticket and automatically classifies it,
determines its urgency, and routes it to the correct team — all before the LLM takes a single
action. Strands Decider 2B makes the routing decision in one fast call, returning calibrated
probabilities for both team assignment and urgency level. The agent then uses only the tools
appropriate for that team, drafts a first-response email, and escalates if needed.

## Who it is for

Customer support managers and agents at SaaS companies who deal with high volumes of inbound
tickets spanning billing disputes, security incidents, technical bugs, account issues, and
general questions. TicketPilot gives every ticket a consistent, explainable triage in under
five seconds.

## The decision handed to Strands Decider 2B

Pattern: **#tool-selection**

Before any tool is called, the decider reads the raw ticket text and answers two questions:

1. **team** (choice): which support team should handle this?
   - `billing` — payment issues, charges, refunds, invoices
   - `security` — hacked accounts, suspicious logins, unauthorized changes
   - `technical` — bugs, API errors, integration failures, performance issues
   - `account` — login problems, profile changes, password resets, access requests
   - `general` — questions, how-tos, feature inquiries, onboarding

2. **urgency** (score): how urgent is this ticket?
   - `low` — informational, no business impact
   - `medium` — annoying but not blocking
   - `high` — blocking work or involving money
   - `critical` — security incident, data at risk, or production down

The decider's output determines which tools the Strands Agent may call. This is tool selection:
the decision shapes what the agent can do, not just what it says.

## Tools

- `classify_and_route(team, priority)` — records the routing decision, returns SLA target
- `lookup_customer(ticket_id)` — retrieves mock customer record and history
- `draft_response(team, issue_summary)` — drafts a professional first-response email
- `escalate(reason, team)` — flags for immediate human review, returns escalation ID

## Features

1. Single-call classification of team and urgency via Strands Decider 2B
2. Tool selection: only the right team's tools are available to the agent
3. Confidence-aware routing: below 0.60 confidence routes to general with a human-review flag
4. Automatic escalation for security incidents and critical-urgency tickets
5. First-response email drafted by Amazon Bedrock, tailored to the routed team

## Data

Synthetic: 10 mock customer records and 20 sample tickets in `agent/data/`. Deterministic for
tests and the demo; no real PII.

## Demo highlight

Submit the ticket: *"I can't access my account and someone changed my email address without my
permission."* It reads like an account reset, but the decider scores it as `security` with
`critical` urgency. The demo panel shows the probability breakdown live — the agent escalates
and drafts a security-team response instead of a routine account reply.
