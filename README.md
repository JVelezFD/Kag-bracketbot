# <img src="docs/paw.svg" width="36" height="36" valign="middle"/> BracketBot — AI Tournament Setup Agent

> Set up any tournament in minutes — just describe your event.

[![Try BracketBot Live](https://img.shields.io/badge/Try%20BracketBot-Live%20Demo-FF4FA3?style=for-the-badge&logo=google-cloud&logoColor=white)](https://bracketbot-98857171777.us-central1.run.app)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Google ADK](https://img.shields.io/badge/Google-ADK-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://google.github.io/adk-docs/)
[![Gemini](https://img.shields.io/badge/Gemini-1.5%20Flash-A6FF3B?style=for-the-badge&logo=google&logoColor=black)](https://ai.google.dev/)
[![Cloud Run](https://img.shields.io/badge/Cloud%20Run-Deployed-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white)](https://cloud.google.com/run)

**Built for the Kaggle 5-Day AI Agents Capstone — Track: Agents for Business**

---

![BracketBot Demo](docs/bracketbot_demo.gif)
_← Drop your demo GIF here after recording. Replace this line and the img tag above with your actual GIF._

---

## The Problem

Volunteer tournament coordinators — gym owners, community center staff, rec league organizers — spend more time managing logistics than playing. Paper brackets get lost. Spreadsheets break. Group chats become chaos.

BracketBot fixes this with a five-minute conversation.

---

## What BracketBot Does

- Guides organizers through setup **one question at a time** — never overwhelming
- Recommends the right bracket format based on player count
- Collects team or player names with **drag and drop seed ordering**
- Supports **Single Elimination, Double Elimination, Round Robin, and Pool Play** (32+ players)
- Uses standard tournament seeding — Seed 1 vs Seed 8, Seed 2 vs Seed 7
- Generates a complete visual bracket on organizer confirmation
- Handles **winner entry** and advances the bracket automatically
- Downloads a **branded PDF bracket** ready to print and hand to a scorekeeper

---

## Live Demo

**🔗 Try it now:** [https://bracketbot-98857171777.us-central1.run.app](https://bracketbot-98857171777.us-central1.run.app)

No login required. No installation. Just open and start talking.

---

## Example Conversation

```
BracketBot: Hey there! 👋 I'm BracketBot — I'll get your tournament set up
            in just a few quick questions. What's the name of your event?

Organizer:  Spring Showdown

BracketBot: Got it! What sport or activity is this tournament for?

Organizer:  Volleyball

BracketBot: How many teams will be competing?

Organizer:  8 teams

BracketBot: Will this be an individual player tournament or a team tournament?

Organizer:  team

BracketBot: What bracket format would you like? For 8 teams I'd recommend
            Single Elimination or Double Elimination.

Organizer:  Double Elimination

BracketBot: Do you have the team names ready? Reply yes to enter them,
            or no to auto-assign numbers.

Organizer:  yes

BracketBot: Go ahead and list all 8 teams — comma or line separated:

Organizer:  Thunderbolts, Spike Kings, Net Ninjas, Sand Sharks,
            Block Party, Ace Squad, Dig Deep, Rally Cats

BracketBot: [Drag and drop seed order widget appears — organizer reorders teams]
            Got it! 8 teams locked in. What's the match format —
            Best of 1, Best of 3, or Best of 5?

Organizer:  Best of 3

BracketBot: Here's your tournament setup — does everything look right?

            Spring Showdown
            Sport: Volleyball | Teams: 8 | Type: team
            Format: Double Elimination | Seeding: manual | Best of 3

            Reply yes to generate your bracket.

Organizer:  yes

BracketBot: Your bracket is ready! Here's Spring Showdown 🏆
            [Full bracket renders on the right panel]
            [Download Bracket PDF button available]
```

---

## Architecture

```
Organizer (Web UI — Flask + vanilla JS)
        │
        ▼
  Manager Agent  ←── Gemini 1.5 Flash via Google ADK
  (bracketbot.py)
        │
        ├── Conversation Subagent   — question flow, state tracking, input sanitization
        │
        ├── Format Advisor Subagent — bracket type recommendation by player count
        │
        ├── Bracket Engine Subagent — bracket generation with standard 1v8 seeding
        │   └── Single Elim / Double Elim / Round Robin / Pool Play (32+ players)
        │
        └── Bracket Progression Subagent — winner entry, bracket advancement,
                                           losers bracket handling (Double Elim)
```

See [docs/architecture.md](docs/architecture.md) for the full data flow diagram.

---

## Tech Stack

| Component         | Technology                      |
| ----------------- | ------------------------------- |
| Agent framework   | Google ADK                      |
| LLM               | Gemini 1.5 Flash                |
| Language          | Python 3.11+                    |
| Web framework     | Flask                           |
| Deployment        | Google Cloud Run                |
| Secret management | Google Secret Manager           |
| IDE               | Antigravity IDE v2.0.4          |
| Security          | Bleach, Flask-Limiter, env vars |

---

## Capstone Concepts Demonstrated

| Concept                 | How                                                                          |
| ----------------------- | ---------------------------------------------------------------------------- |
| ✅ Multi-agent system   | Manager + 4 subagents via Google ADK                                         |
| ✅ Gemini API           | Gemini 1.5 Flash for conversation + field extraction                         |
| ✅ Antigravity IDE      | Built and tested in Antigravity IDE v2.0.4                                   |
| ✅ Cloud Run deployment | Live public URL, scales to zero                                              |
| ✅ Security             | Input validation, rate limiting, Secret Manager, prompt injection protection |
| ✅ Agent skill          | PDF bracket export skill                                                     |

---

## Prerequisites

- Python 3.11+
- A [Google AI Studio](https://aistudio.google.com/) account with a Gemini API key
- Git

---

## Setup — Run Locally

**1. Clone the repo**

```bash
git clone https://github.com/JVelezFD/Kag-bracketbot.git
cd Kag-bracketbot
```

**2. Create and activate a virtual environment**

```bash
python -m venv venv
source venv/Scripts/activate   # Windows (Git Bash)
source venv/bin/activate        # Mac / Linux
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Add your Gemini API key**

```bash
cp .env.example .env
```

Open `.env` and add your key:

```
GEMINI_API_KEY=your_key_here
```

**5. Run locally**

```bash
python main.py
```

Open your browser to `http://localhost:8080`

---

## Deploy to Cloud Run

**Prerequisites:**

- Google Cloud project with billing enabled
- `gcloud` CLI installed and authenticated

**1. Enable required APIs**

```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

**2. Store your API key securely**

```bash
printf '%s' 'YOUR_GEMINI_API_KEY' | gcloud secrets create gemini-api-key --data-file=-
```

**3. Grant Cloud Run access to the secret**

```bash
gcloud secrets add-iam-policy-binding gemini-api-key \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

**4. Deploy**

```bash
gcloud run deploy bracketbot \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-secrets=GEMINI_API_KEY=gemini-api-key:latest \
  --memory 512Mi \
  --port 8080
```

Your public URL will appear at the end of the deploy output.

---

## Running Tests

```bash
pytest tests/
```

---

## Project Structure

```
Kag-Bracketbot/
├── README.md                        # This file
├── .env.example                     # Environment variable template
├── .gitignore
├── requirements.txt
├── main.py                          # Flask app + Cloud Run entry point
├── Dockerfile                       # Container for Cloud Run
├── agent/
│   ├── bracketbot.py                # Manager agent — orchestrates subagents
│   ├── conversation.py              # Conversation state + input sanitization
│   ├── bracket_engine.py            # Bracket generation — all 4 formats
│   ├── progression.py               # Winner entry + bracket advancement
│   ├── prompts.py                   # System prompts and message templates
│   └── templates/
│       └── index.html               # Web UI — chat + bracket renderer + PDF export
├── tools/
│   ├── bracket_tool.py              # ADK tool: bracket generation
│   ├── seeding_tool.py              # ADK tool: participant seeding
│   └── format_tool.py               # ADK tool: format recommendations
├── tests/
│   ├── test_bracket.py              # Bracket engine unit tests
│   └── test_conversation.py         # Conversation logic unit tests
├── docs/
│   ├── architecture.md              # Architecture diagram + data flow
│   └── bracketbot_demo.gif          # Demo GIF (add after recording)
└── deploy/
    └── cloudbuild.yaml              # Cloud Build configuration
```

---

## Security

- All user input sanitized with `bleach` before touching any logic
- API key stored in Google Secret Manager — never in code or GitHub
- Rate limiting: 30 requests/minute, 200/hour per IP via Flask-Limiter
- Prompt injection protection via character filtering in `conversation.py`
- `.env` excluded from git via `.gitignore`

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

_Built by [JVelezFD]() for the Kaggle 5-Day AI Agents Capstone, 2026._
_Powered by Google ADK, Gemini 1.5 Flash, and Google Cloud Run._
