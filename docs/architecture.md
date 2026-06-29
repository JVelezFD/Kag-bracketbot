# BracketBot — Architecture

## Overview

BracketBot is a multi-agent system built with Google ADK and Gemini 1.5 Flash.
The manager agent orchestrates four specialized subagents to guide an organizer
through setting up a complete tournament via natural language conversation.

## Agent Architecture

```
Organizer (Web UI)
        │
        ▼
  Manager Agent  ←── Gemini 1.5 Flash via Google ADK
  (bracketbot.py)
        │
        ├── Conversation Subagent (conversation.py)
        │       └── Tracks setup state, determines next question,
        │           sanitizes input, extracts field values directly
        │           from natural language (no API call needed)
        │
        ├── Format Advisor Subagent (tools/format_tool.py)
        │       └── Recommends bracket type based on player count
        │
        ├── Bracket Engine Subagent (bracket_engine.py)
        │       └── Generates bracket on organizer confirmation
        │           Standard 1v8 seeding for all formats
        │           Supports: Single Elim, Double Elim, Round Robin, Pool Play
        │
        └── Bracket Progression Subagent (progression.py)
                └── Accepts winner inputs in natural language
                    Advances winners bracket and losers bracket
                    Handles Grand Final, undo (5 states back),
                    Round Robin standings, champion declaration
```

## Data Flow

1. Organizer sends natural language message via web UI
2. Flask (main.py) receives the POST /chat request
3. Input is sanitized and validated with Bleach
4. Manager Agent checks conversation state
5. If setup is incomplete → direct pattern matching extracts field values,
   Gemini generates the warm conversational response
6. If player count is known → Format Advisor recommends bracket type
7. If Double Elimination selected with non-power-of-2 count →
   BracketBot flags the issue and asks organizer to adjust
8. If organizer has names → drag-and-drop seed order widget appears in chat
9. If all fields collected → Summary presented for confirmation
10. On confirmation → Bracket Engine generates full bracket structure
11. Bracket returned to web UI for visual rendering
12. Organizer enters results → Progression Subagent advances bracket

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | Google ADK |
| LLM | Gemini 1.5 Flash |
| Language | Python 3.11+ |
| Web server | Flask |
| Deployment | Google Cloud Run |
| Secret management | Google Secret Manager |
| Rate limiting | Flask-Limiter |
| Input security | Bleach |
| PDF export | jsPDF (client-side) |

## Security

- All user input sanitized with `bleach` before touching any logic
- Prompt injection protection via character filtering in conversation.py
- API key stored in Google Secret Manager — never in code or GitHub
- Rate limiting: 200 req/hour, 30 req/minute per IP via Flask-Limiter
- No user authentication required — stateless sessions via session ID

## Session Memory

Each conversation maintains state via a session ID. The Manager Agent
tracks all collected tournament fields in memory for the duration of the session,
allowing the organizer to provide information incrementally in any order.
The Progression Subagent maintains an undo stack of up to 5 previous bracket
states so organizers can reverse incorrect results.

## Bracket Format Support

| Format | Player Counts | Notes |
|--------|--------------|-------|
| Single Elimination | Any | Byes given to top seeds for non-power-of-2 counts |
| Double Elimination | 4, 8, 16, 32 | Power-of-2 only — BracketBot flags other counts |
| Round Robin | Any | Auto-calculates standings, detects ties |
| Pool Play | 33+ | Pools of 4-6, top 2 advance to playoff bracket |
