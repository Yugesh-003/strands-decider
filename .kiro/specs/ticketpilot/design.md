# TicketPilot — Design

## Architecture

```
User message (ticket text)
        │
        ▼
  HackathonAgent.chat()
        │
        ├─► Strands Decider 2B  ◄─── TOOL-SELECTION PATTERN
        │     state: ticket text
        │     Q1: team  (choice: billing|security|technical|account|general)
        │     Q2: urgency (score: low|medium|high|critical)
        │     → team label + confidence, urgency label
        │
        ├─► ToolSelector.select(request, all_tools)
        │     narrows tool list based on decider output
        │     low confidence (<0.60) → general + flag
        │
        ▼
  Strands Agent (Bedrock / ugmdu LLM)
     with narrowed tool set
        │
        ├─► classify_and_route(team, priority)   always called
        ├─► lookup_customer(ticket_id)            billing / account
        ├─► draft_response(team, issue_summary)  always called
        └─► escalate(reason, team)               security-high/critical or any-critical
        │
        ▼
  reply dict: reply, decisions, model_id, latency_ms
```

## Decision pattern: #tool-selection

File: `agent/decision.py`
Pattern: `decider_kit.patterns.tool_selection.ToolSelector`

The ToolSelector runs before the Strands Agent is invoked. It:
1. Calls `Decider.ask(ticket_text, {team: choice, urgency: score})`
2. Returns a filtered list of tools appropriate for that team+urgency
3. Records the decision in the `decisions` list for the demo panel

The Strands Agent then runs with only the narrowed tools, so it cannot call the wrong team's
workflow by accident. This is the meaningful use of the decider: it is not a post-hoc label,
it shapes what the agent can do.

## Files

| File | Purpose |
|------|---------|
| `agent/AGENT.md` | Use case description |
| `agent/decision.py` | PATTERN_TAG, QUESTIONS, TicketRouter (ToolSelector subclass) |
| `agent/tools.py` | classify_and_route, lookup_customer, draft_response, escalate |
| `agent/agent.py` | HackathonAgent: decider → tool selection → Strands Agent |
| `agent/eval_cases.jsonl` | 30 labelled cases (tune + test splits) |
| `agent/demo_script.yaml` | 6 demo turns covering all teams and urgency levels |
| `agent/features.yaml` | no AgentCore features |
| `agent/data/customers.json` | mock customer records |
| `agent/data/tickets.json` | 20 sample tickets for the demo |

## Data

Synthetic data only. `agent/data/customers.json` has 10 mock customers with:
- customer_id, name, email, account_status (active/suspended/locked)
- recent_tickets: list of prior ticket summaries

`agent/data/tickets.json` has 20 sample tickets:
- ticket_id, customer_id, subject, body, expected_team, expected_urgency

## Confidence handling

| team.confidence | action |
|----------------|--------|
| ≥ 0.80 | route as decided |
| 0.60–0.79 | route as decided, add note "moderate confidence — review recommended" |
| < 0.60 | route to general, flag for human review regardless of label |

## Eval cases

30 cases in eval_cases.jsonl:
- 18 tune split, 12 test split
- Coverage: all 5 teams × all 4 urgency levels, plus near-misses
  (billing-sounding text that is actually security, account reset vs hacked account, etc.)
- state: the ticket body text as sent to the decider
- expected: {team: label, urgency: label}
