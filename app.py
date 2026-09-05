import os
import requests

from flask import Flask, request, jsonify, render_template, session
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "change-me"
)

WATSONX_URL = (
    os.getenv("WATSONX_URL")
    or "https://au-syd.ml.cloud.ibm.com"
).rstrip("/")



WATSONX_MODEL = os.getenv(
    "WATSONX_MODEL",
    "ibm/granite-guardian-3-8b"
)

API_KEY = os.getenv(
    "ORCHESTRATE_API_KEY"
)

INSTANCE_URL = (
    os.getenv("ORCHESTRATE_URL")
    or ""
).rstrip("/")

AGENT_ID = os.getenv(
    "ORCHESTRATE_AGENT_ID"
)


# ============================================================
# ORCHESTRATE CHAT COMPLETIONS URL
# ============================================================

if INSTANCE_URL and AGENT_ID:

    CHAT_URL = (
        f"{INSTANCE_URL}/v1/orchestrate/"
        f"{AGENT_ID}/chat/completions"
    )

else:

    CHAT_URL = ""


# ============================================================
# GET IBM IAM ACCESS TOKEN
# ============================================================

def get_iam_token() -> str:
    """
    Generate IBM Cloud IAM access token
    using the API key stored in .env.
    """

    if not API_KEY:

        raise RuntimeError(
            "ORCHESTRATE_API_KEY is missing from .env"
        )

    response = requests.post(

        "https://iam.cloud.ibm.com/identity/token",

        headers={
            "Content-Type":
                "application/x-www-form-urlencoded"
        },

        data={
            "grant_type":
                "urn:ibm:params:oauth:grant-type:apikey",

            "apikey":
                API_KEY
        },

        timeout=15
    )

    response.raise_for_status()

    token = response.json().get(
        "access_token"
    )

    if not token:

        raise RuntimeError(
            "IBM IAM response did not contain "
            "an access token."
        )

    return token


# ============================================================
# EXTRACT RESPONSE TEXT
# ============================================================

def extract_reply_text(result: dict) -> str:
    """
    Extract assistant response from different
    possible IBM Orchestrate response formats.
    """

    choices = result.get(
        "choices"
    ) or []

    if not choices:
        return ""

    choice = choices[0]


    # --------------------------------------------------------
    # FORMAT A
    # choices[0].message.content
    # --------------------------------------------------------

    message = choice.get(
        "message"
    ) or {}

    content = message.get(
        "content"
    )


    # --------------------------------------------------------
    # FORMAT B
    # message.content is a list
    # --------------------------------------------------------

    if isinstance(content, list):

        texts = []

        for part in content:

            if isinstance(part, dict):

                text = (
                    part.get("text")
                    or part.get("content")
                    or ""
                )

                if text:
                    texts.append(
                        str(text)
                    )

            elif isinstance(part, str):

                texts.append(part)

        return " ".join(
            texts
        ).strip()


    # --------------------------------------------------------
    # FORMAT C
    # message.content is a string
    # --------------------------------------------------------

    if isinstance(content, str):

        return content.strip()


    # --------------------------------------------------------
    # FORMAT D
    # choices[0].text
    # --------------------------------------------------------

    text = choice.get(
        "text"
    )

    if isinstance(text, str):

        return text.strip()


    # --------------------------------------------------------
    # FORMAT E
    # choices[0].delta.content
    # --------------------------------------------------------

    delta = choice.get(
        "delta"
    ) or {}

    delta_content = delta.get(
        "content"
    )

    if isinstance(
        delta_content,
        str
    ):

        return delta_content.strip()


    return ""


# ============================================================
# CHECK REQUIRED CONFIGURATION
# ============================================================

def get_missing_config():

    required = {

        "ORCHESTRATE_API_KEY":
            API_KEY,

        "ORCHESTRATE_URL":
            INSTANCE_URL,

        "ORCHESTRATE_AGENT_ID":
            AGENT_ID
    }

    missing = []

    for name, value in required.items():

        if not value:

            missing.append(name)

    return missing


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def index():

    return render_template(

        "index.html",

        agent_name=
            "Digital Financial Literacy Agent"
    )


# ============================================================
# CHAT API
# ============================================================

@app.route(
    "/chat",
    methods=["POST"]
)
def chat():

    # --------------------------------------------------------
    # READ JSON REQUEST
    # --------------------------------------------------------

    try:

        data = request.get_json(
            force=True
        )

    except Exception:

        return jsonify({

            "error":
                "Invalid JSON request."

        }), 400


    # --------------------------------------------------------
    # GET USER MESSAGE
    # --------------------------------------------------------

    user_message = (

        data.get("message")
        or ""

    ).strip()


    # --------------------------------------------------------
    # EMPTY MESSAGE CHECK
    # --------------------------------------------------------

    if not user_message:

        return jsonify({

            "error":
                "Empty message."

        }), 400


    # --------------------------------------------------------
    # CHECK ENVIRONMENT VARIABLES
    # --------------------------------------------------------

    missing = get_missing_config()

    if missing:

        app.logger.error(

            "Missing environment variables: %s",

            ", ".join(missing)

        )

        return jsonify({

            "error":
                "Server configuration error. "
                "Check your .env file."

        }), 500


    # --------------------------------------------------------
    # CALL IBM ORCHESTRATE
    # --------------------------------------------------------

    try:

        # Get IBM IAM token
        token = get_iam_token()


        # ----------------------------------------------------
        # REQUEST HEADERS
        # ----------------------------------------------------

        headers = {

            "Authorization":
                f"Bearer {token}",

            "Content-Type":
                "application/json"
        }


        # ----------------------------------------------------
        # REQUEST PAYLOAD
        # ----------------------------------------------------

        payload = {

            "messages": [

                {
                    "role": "user",

                    "content":
                        user_message
                }

            ],

            "additional_parameters":
                {},

            "context":
                {},

            "stream":
                False
        }


        # ----------------------------------------------------
        # CONTINUE EXISTING CONVERSATION
        # ----------------------------------------------------

        thread_id = session.get(

            "orchestrate_thread_id"
        )

        if thread_id:

            payload[
                "thread_id"
            ] = thread_id


        # ----------------------------------------------------
        # SEND REQUEST
        # ----------------------------------------------------

        response = requests.post(

            CHAT_URL,

            headers=headers,

            json=payload,

            timeout=60
        )


        # ----------------------------------------------------
        # HANDLE 404
        # ----------------------------------------------------

        if response.status_code == 404:

            app.logger.error(

                "Orchestrate agent returned 404. "
                "Check ORCHESTRATE_URL and "
                "ORCHESTRATE_AGENT_ID."
            )

            return jsonify({

                "error":
                    "Agent not found (404). "
                    "Check ORCHESTRATE_URL and "
                    "ORCHESTRATE_AGENT_ID."

            }), 502


        # ----------------------------------------------------
        # HANDLE OTHER HTTP ERRORS
        # ----------------------------------------------------

        response.raise_for_status()


        # ----------------------------------------------------
        # READ RESPONSE
        # ----------------------------------------------------

        result = response.json()


        # ----------------------------------------------------
        # SAVE THREAD ID
        # ----------------------------------------------------

        new_thread_id = result.get(
            "thread_id"
        )

        if new_thread_id:

            session[
                "orchestrate_thread_id"
            ] = new_thread_id


        # ----------------------------------------------------
        # EXTRACT RESPONSE
        # ----------------------------------------------------

        reply = extract_reply_text(
            result
        )


        if not reply:

            reply = (
                "(No response text returned.)"
            )


        # ----------------------------------------------------
        # RETURN RESPONSE TO FRONTEND
        # ----------------------------------------------------

        return jsonify({

            "reply":
                reply

        })


    # ========================================================
    # HTTP ERROR
    # ========================================================

    except requests.HTTPError as exc:

        status = (

            exc.response.status_code

            if exc.response is not None

            else "unknown"

        )

        app.logger.error(

            "Orchestrate HTTP error: %s",

            status

        )

        return jsonify({

            "error":
                f"API error {status}."

        }), 502


    # ========================================================
    # NETWORK ERROR
    # ========================================================

    except requests.RequestException as exc:

        app.logger.error(

            "Network error while contacting "
            "Orchestrate: %s",

            exc

        )

        return jsonify({

            "error":
                "Could not connect to "
                "the Orchestrate service."

        }), 502


    # ========================================================
    # GENERAL ERROR
    # ========================================================

    except Exception as exc:

        app.logger.exception(

            "Unexpected error: %s",

            exc

        )

        return jsonify({

            "error":
                "Request failed. "
                "Check the server terminal."

        }), 502


# ============================================================
# RESET CHAT
# ============================================================

@app.route(
    "/reset",
    methods=["POST"]
)
def reset():

    session.pop(

        "orchestrate_thread_id",

        None
    )

    return jsonify({

        "status":
            "ok"

    })


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "FinanceGuru - Digital Financial Literacy Agent"
    )

    print(
        "=" * 60
    )

    print(
        f"Watsonx URL   : {WATSONX_URL}"
    )

    print(
        f"Watsonx Model : {WATSONX_MODEL}"
    )

    print(
        f"Orchestrate URL : "
        f"{INSTANCE_URL or '[not configured]'}"
    )

    print(
        f"Agent ID      : "
        f"{AGENT_ID or '[not configured]'}"
    )

    print(
        "=" * 60
    )


    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True
    )