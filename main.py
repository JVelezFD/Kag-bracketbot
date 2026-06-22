"""
BracketBot — Flask entry point.
Serves the web UI and handles all API routes.
Run locally with: python main.py
"""

import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from agent.bracketbot import BracketBotAgent
from agent.prompts import GREETING

load_dotenv()

app = Flask(__name__)
CORS(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per hour", "30 per minute"],
    storage_uri="memory://",
)

agent = BracketBotAgent()


@app.route("/", methods=["GET"])
def index():
    """Serve the BracketBot web UI."""
    return render_template_string(
        open("agent/templates/index.html", encoding="utf-8").read()
    )


@app.route("/chat", methods=["POST"])
@limiter.limit("30 per minute")
def chat():
    """
    Main chat endpoint.
    Body: { "message": str, "session_id": str }
    Returns: { "response": str, "bracket": dict|null, "state": str,
               "show_seed_widget": bool, "names": list }
    """
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    session_id = data.get("session_id", "default")

    # Boot greeting — do not pass to agent
    if message == "__init__":
        return jsonify({"response": GREETING, "bracket": None, "state": "setup"})

    # Block internal reserved messages
    if message.startswith("__"):
        return jsonify({"error": "Invalid message"}), 400

    if not message:
        return jsonify({"error": "Message cannot be empty"}), 400
    if len(message) > 2000:
        return jsonify({"error": "Message too long — max 2000 characters"}), 400

    result = agent.chat(message, session_id)
    return jsonify(result)


@app.route("/confirm_seeds", methods=["POST"])
@limiter.limit("20 per minute")
def confirm_seeds():
    """
    Receive the confirmed seed order from the drag-and-drop widget.
    Body: { "session_id": str, "names": list }
    Returns: { "response": str, "bracket": dict|null }
    """
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "default")
    names = data.get("names", [])

    if not names:
        return jsonify({"error": "No names provided"}), 400

    result = agent.confirm_seed_order(names, session_id)
    return jsonify(result)


@app.route("/new", methods=["POST"])
@limiter.limit("10 per minute")
def new_tournament():
    """Reset the session for a new tournament."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "default")
    result = agent.new_tournament(session_id)
    return jsonify(result)


@app.route("/health", methods=["GET"])
def health():
    """Health check for Cloud Run."""
    return jsonify({"status": "ok", "service": "bracketbot"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("ENVIRONMENT", "development") == "development"
    print(f"BracketBot running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)