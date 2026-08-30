import os
import requests
from flask import Flask, request, jsonify, render_template, session
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-me")

API_KEY      = os.getenv("ORCHESTRATE_API_KEY")
INSTANCE_URL = (os.getenv("ORCHESTRATE_URL") or "").rstrip("/")
AGENT_ID     = os.getenv("ORCHESTRATE_AGENT_ID")

# Confirmed endpoint from IBM's developer docs:
# POST {INSTANCE_URL}/v1/orchestrate/{agent_id}/chat/completions
CHAT_URL = f"{INSTANCE_URL}/v1/orchestrate/{AGENT_ID}/chat/completions"


def get_iam_token() -> str:
    resp = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=f"grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey={API_KEY}",
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def extract_reply_text(result: dict) -> str:
    """
    Handle multiple possible response shapes robustly, since the
    documented schema for 'choices' is loosely specified.
    """
    choices = result.get("choices") or []
    if not choices:
        return ""

    choice = choices[0]

    # Shape A: choices[0].message.content as a plain string
    message = choice.get("message") or {}
    content = message.get("content")

    # Shape B: choices[0].message.content as a list of parts
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict):
                texts.append(part.get("text") or part.get("content") or "")
            elif isinstance(part, str):
                texts.append(part)
        return " ".join(t for t in texts if t).strip()

    if isinstance(content, str):
        return content.strip()

    # Shape C: choices[0].text (flat)
    if isinstance(choice.get("text"), str):
        return choice["text"].strip()

    # Shape D: choices[0].delta.content (streaming-style, just in case)
    delta = choice.get("delta") or {}
    if isinstance(delta.get("content"), str):
        return delta["content"].strip()

    return ""


@app.route("/")
def index():
    return render_template("index.html", agent_name="Digital Financial Literacy Agent")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    user_message = (data.get("message") or "").strip()

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    if not API_KEY or not INSTANCE_URL or not AGENT_ID:
        app.logger.error("Missing env vars: ORCHESTRATE_API_KEY / ORCHESTRATE_URL / ORCHESTRATE_AGENT_ID")
        return jsonify({"error": "Server configuration error — check .env"}), 500

    try:
        token = get_iam_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload: dict = {
            "messages": [
                {"role": "user", "content": user_message}
            ],
            "additional_parameters": {},
            "context": {},
            "stream": False,
        }

        thread_id = session.get("orchestrate_thread_id")
        if thread_id:
            payload["thread_id"] = thread_id

        resp = requests.post(CHAT_URL, headers=headers, json=payload, timeout=60)

        if resp.status_code == 404:
            app.logger.error(
                "404 from Orchestrate — verify ORCHESTRATE_AGENT_ID (%s) and ORCHESTRATE_URL (%s). Attempted: %s",
                AGENT_ID, INSTANCE_URL, CHAT_URL,
            )
            return jsonify({"error": "Agent not found (404). Verify ORCHESTRATE_AGENT_ID and ORCHESTRATE_URL."}), 502

        resp.raise_for_status()
        result = resp.json()

        # TEMP DEBUG — remove once working reliably
        app.logger.error("RAW ORCHESTRATE RESPONSE: %s", result)

        new_thread_id = result.get("thread_id")
        if new_thread_id:
            session["orchestrate_thread_id"] = new_thread_id

        reply = extract_reply_text(result)
        return jsonify({"reply": reply or "(No response text returned.)"})

    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        body   = exc.response.text        if exc.response is not None else ""
        app.logger.error("Orchestrate HTTP error %s: %s", status, body)
        return jsonify({"error": f"API error {status}"}), 502
    except Exception as exc:
        app.logger.error("Unexpected error: %s", exc)
        return jsonify({"error": "Request failed — see server logs."}), 502


@app.route("/reset", methods=["POST"])
def reset():
    session.pop("orchestrate_thread_id", None)
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)