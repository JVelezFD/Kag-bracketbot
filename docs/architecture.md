# BracketBot — Architecture

## Overview

BracketBot is a multi-agent system built with Google ADK and Gemini 3.5 Flash.
The manager agent orchestrates four specialized subagents to guide an organizer
through setting up a complete tournament via natural language conversation.

## Agent Architecture

```
Organizer (Web UI)
        │
        ▼
  Manager Agent  ←── Gemini 3.5 Flash via ADK
  (bracketbot.py)
        │
        ├── Conversation Subagent (conversation.py)
        │       └── Tracks setup state, determines next question,
        │           sanitizes input, extracts player count
        │
        ├── Format Advisor Subagent (tools/format_tool.py)
        │       └── Recommends bracket type based on player count
        │
        ├── Bracket Engine Subagent (bracket_engine.py)
        │       └── Generates bracket on organizer confirmation
        │           Supports: Single Elim, Double Elim, Round Robin, Pool Play
        │
        └── Bracket Progression Subagent
                └── Accepts winner inputs, advances bracket,
                    handles losers bracket in Double Elimination
```

## Data Flow

1. Organizer sends natural language message via web UI
2. Flask (main.py) receives the POST /chat request
3. Input is sanitized and validated
4. Manager Agent checks conversation state
5. If setup is incomplete → Conversation Subagent determines next question
6. If player count is known → Format Advisor recommends bracket type
7. If all fields collected → Summary presented for confirmation
8. On confirmation → Bracket Engine generates full bracket structure
9. Bracket returned to web UI for visual rendering

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | Google ADK |
| LLM | Gemini 3.5 Flash |
| Language | Python 3.11+ |
| Web server | Flask |
| Deployment | Google Cloud Run |
| Rate limiting | Flask-Limiter |
| Input security | Bleach |

## Security

- All user input sanitized with `bleach` before touching the model
- API key loaded from environment variable — never in code
- Rate limiting: 100 req/hour, 20 req/minute per IP
- Prompt injection protection via character filtering
- No user authentication required — stateless sessions via session ID

## Session Memory

Each conversation maintains state via a session ID. The manager agent
tracks all collected tournament fields in memory for the duration of the session,
allowing the organizer to provide information incrementally.
