# TicketPilot — Requirements

## Overview
An AI customer support dispatcher that classifies incoming support tickets, determines urgency,
and routes them to the correct team using Strands Decider 2B for the routing decision and
Amazon Bedrock for generating responses.

## Users
Customer support managers and agents who receive a high volume of inbound tickets and need
fast, consistent triage without reading every ticket manually.

## Functional Requirements

### FR-1: Ticket intake
The agent accepts a free-text support ticket (submitted as a chat message) and processes it
end-to-end: classify → route → respond.

### FR-2: Strands Decider 2B routing decision (#tool-selection)
The decider reads the ticket text and answers two questions in a single call:
- **team** (choice): billing | security | technical | account | general
- **urgency** (score): low | medium | high | critical

The decider's output determines which tool the agent calls next (tool selection pattern).

### FR-3: Tool selection based on decider output
| team        | urgency        | action                                  |
|-------------|----------------|-----------------------------------------|
| security    | high/critical  | `escalate` + `draft_response`           |
| any         | critical       | `escalate` + `draft_response`           |
| billing     | any            | `lookup_customer` + `draft_response`    |
| account     | any            | `lookup_customer` + `draft_response`    |
| technical   | any            | `draft_response`                        |
| general     | any            | `draft_response`                        |

### FR-4: Customer lookup
`lookup_customer(ticket_id)` returns mock customer name, account status, and ticket history
from synthetic data in `agent/data/customers.json`.

### FR-5: Response drafting
`draft_response(team, issue_summary)` uses the Strands Agent (Bedrock/ugmdu LLM) to write a
professional first-response email appropriate for the routed team.

### FR-6: Escalation
`escalate(reason, team)` flags the ticket for immediate human review and returns an escalation
ID and estimated response time.

### FR-7: Routing confirmation
`classify_and_route(team, priority)` records the routing decision and returns the assigned team,
SLA target, and a confirmation message.

### FR-8: Demo transparency
The agent reply always includes: original ticket summary, routed team, urgency level, decider
confidence, next action taken, and (if drafted) the response email.

## Non-functional Requirements
- The decider call must happen before any tool is called (tool-selection pattern)
- Low confidence (< 0.60 on team choice): route to general and flag for human review
- All data is synthetic; no real PII
- Compatible with the kit's demo UI (agent/demo_script.yaml turns)

## Out of scope
- Real ticket system integration (Zendesk, Jira, etc.)
- Multi-turn conversations within a single ticket
- AgentCore Memory or Gateway (not needed for this pattern)
