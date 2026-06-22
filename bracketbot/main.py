"""
BracketBot — AI Tournament Setup Agent
Entry point for local development and Cloud Run deployment.

Run locally:
    python main.py

Deploy to Cloud Run:
    See deploy/cloudbuild.yaml
"""

import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from agent.bracketbot import BracketBotAgent

# Load environment variables from .env file (local dev only)
load_dotenv()

app = Flask(__name__)
CORS(app)

# Rate limiting — protect against abuse
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per hour", "20 per minute"],
    storage_uri="memory://",
)

# Initialize the BracketBot agent
agent = BracketBotAgent()


@app.route("/", methods=["GET"])
def index():
    """Serve the BracketBot web UI."""
    return render_template_string(open("agent/templates/index.html").read())


@app.route("/chat", methods=["POST"])
@limiter.limit("20 per minute")
def chat():
    """
    Handle a chat message from the organizer.

    Expects JSON: { "message": "...", "session_id": "..." }
    Returns JSON: { "response": "...", "bracket": null | { ... } }
    """
    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"error": "Missing message field"}), 400

    user_message = data.get("message", "").strip()
    session_id = data.get("session_id", "default")

    # Input validation — reject empty or oversized inputs
    if not user_message:
        return jsonify({"error": "Message cannot be empty"}), 400
    if len(user_message) > 2000:
        return jsonify({"error": "Message too long (max 2000 characters)"}), 400

    response = agent.chat(user_message, session_id)
    return jsonify(response)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for Cloud Run."""
    return jsonify({"status": "ok", "agent": "BracketBot"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("ENVIRONMENT", "development") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
