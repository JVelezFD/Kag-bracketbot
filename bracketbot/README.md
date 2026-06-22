# 🏆 BracketBot — AI Tournament Setup Agent

BracketBot is a conversational AI agent that helps recreational sports organizers set up complete tournaments through natural language. No software to learn — just describe your event and BracketBot handles the rest.

**Built for the [Kaggle 5-Day AI Agents Capstone](https://www.kaggle.com/) — Track: Agents for Business**

---

## The Problem

Volunteer tournament coordinators — gym owners, community center staff, rec league organizers — spend more time managing logistics than enjoying the event. Paper brackets get lost. Spreadsheets break. Group chats become chaos.

BracketBot fixes this with a five-minute conversation.

---

## What BracketBot Does

- Guides organizers through setup one question at a time
- Recommends the right bracket format based on player count
- Supports Single Elimination, Double Elimination, Round Robin, and Pool Play (32+ players)
- Accepts manual player names or random seeding
- Generates a complete, ready-to-use bracket on confirmation
- Remembers context across the conversation (session memory)

---

## Architecture

```
Organizer (Web UI)
        │
        ▼
  Manager Agent  ←── Gemini 3.5 Flash via Google ADK
        │
        ├── Conversation Subagent   — question flow, state tracking, input sanitization
        ├── Format Advisor Subagent — bracket type recommendation
        ├── Bracket Engine Subagent — bracket generation
        └── Bracket Progression     — winner entry, bracket advancement
```

See [docs/architecture.md](docs/architecture.md) for the full diagram and data flow.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent framework | Google ADK |
| LLM | Gemini 3.5 Flash |
| Language | Python 3.11+ |
| Web framework | Flask |
| Deployment | Google Cloud Run |
| IDE | Antigravity IDE v2.0.4 |

---

## Prerequisites

- Python 3.11+
- A [Google AI Studio](https://aistudio.google.com/) account with a Gemini API key
- Git

---

## Setup — Run Locally

### 1. Clone the repo

```bash
git clone https://github.com/JVelezFD/Kag-bracketbot.git
cd Kag-bracketbot
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate      # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your API key

```bash
cp .env.example .env
```

Open `.env` and add your Gemini API key:

```
GEMINI_API_KEY=your_key_here
```

### 5. Run locally

```bash
python main.py
```

Open your browser to `http://localhost:8080`

---

## Deploy to Cloud Run

### Prerequisites
- Google Cloud project with Cloud Run and Cloud Build enabled
- `gcloud` CLI installed and authenticated

### Deploy

```bash
gcloud builds submit --config deploy/cloudbuild.yaml
```

Set your API key as a Cloud Run secret:

```bash
gcloud run services update bracketbot \
  --set-secrets=GEMINI_API_KEY=gemini-api-key:latest \
  --region us-central1
```

---

## Example Conversation

```
BracketBot: Hey there! I'm BracketBot. What's the name of your event or tournament?

Organizer:  Summer Slam Basketball

BracketBot: Love it! How many teams will be competing in Summer Slam Basketball?

Organizer:  16 teams

BracketBot: Got it — 16 teams. Would you like Single Elimination or Double Elimination?
            (Double Elimination means every team has to lose twice before they're out.)

Organizer:  Double Elimination

BracketBot: How would you like to seed the bracket — random draw, or enter team names manually?

Organizer:  Random is fine

BracketBot: Last one — what's the match format? Best of 1, Best of 3, or Best of 5?

Organizer:  Best of 3

BracketBot: Here's your setup — does everything look right?

            Summer Slam Basketball
            Sport: Basketball | Teams: 16
            Format: Double Elimination | Seeding: Random | Best of 3

            Reply yes to generate your bracket.

Organizer:  Yes

BracketBot: Your bracket is ready! [bracket diagram displayed]
```

---

## Project Structure

```
bracketbot/
├── README.md               # This file
├── .env.example            # Environment variable template
├── .gitignore
├── requirements.txt
├── main.py                 # Flask app + Cloud Run entry point
├── Dockerfile              # Container definition for Cloud Run
├── agent/
│   ├── bracketbot.py       # Manager agent — orchestrates subagents
│   ├── conversation.py     # Conversation state tracking + input sanitization
│   ├── bracket_engine.py   # Bracket generation for all formats
│   └── prompts.py          # System prompts and templates
├── tools/
│   ├── bracket_tool.py     # ADK tool: bracket generation
│   ├── seeding_tool.py     # ADK tool: participant seeding
│   └── format_tool.py      # ADK tool: format recommendations
├── tests/
│   ├── test_bracket.py     # Bracket engine tests
│   └── test_conversation.py # Conversation logic tests
├── docs/
│   └── architecture.md     # Architecture diagram and data flow
└── deploy/
    └── cloudbuild.yaml     # Cloud Build + Cloud Run deployment config
```

---

## Running Tests

```bash
pytest tests/
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built by [Fierce Den](https://fierreden.com) for the Kaggle 5-Day AI Agents Capstone, 2026.*
