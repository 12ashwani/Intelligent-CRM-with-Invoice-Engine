import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request, session

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from shared_sso import verify_sso_payload
from ai_agent.agent.agent import run_agent
from ai_agent.tools.crm_tools import set_user_context, reset_user_context


app = Flask(__name__)
app.secret_key = os.getenv("AI_AGENT_SECRET", "ai-agent-secret")


def _grant_sso_access() -> bool:
    username = request.args.get("user", "").strip()
    role = request.args.get("role", "").strip().lower()
    employee_id = request.args.get("employee_id", "").strip()
    issued_at = request.args.get("ts", "").strip()
    signature = request.args.get("sig", "").strip()
    ttl_raw = request.args.get("ttl", "3600").strip()

    if not all([username, role, issued_at, signature]):
        return False
    try:
        ts = int(issued_at)
        ttl = int(ttl_raw)
    except ValueError:
        return False

    if not verify_sso_payload(username, role, employee_id, ts, signature, ttl):
        return False

    session["ai_user"] = username
    session["ai_role"] = role
    session["ai_employee_id"] = employee_id
    return True


@app.before_request
def _auth_gate():
    if _grant_sso_access():
        return None
    if request.path in {"/health", "/"}:
        return None
    if not session.get("ai_role"):
        return jsonify({"error": "unauthorized"}), 401
    return None


@app.get("/")
def index():
    return jsonify({"service": "ai_agent", "status": "ok"})


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/query")
def query():
    payload = request.get_json(silent=True) or {}
    prompt = (payload.get("query") or "").strip()
    if not prompt:
        return jsonify({"error": "query is required"}), 400

    role = session.get("ai_role", "")
    employee_id = session.get("ai_employee_id", "")
    username = session.get("ai_user", "")
    token = set_user_context(role=role, employee_id=employee_id, user_id=username)
    try:
        result = run_agent(prompt)
        return jsonify({"ok": True, "response": result.get("response")})
    finally:
        reset_user_context(token)


if __name__ == "__main__":
    app.run(host=os.getenv("AI_HOST", "127.0.0.1"), port=int(os.getenv("AI_PORT", "5002")), debug=False)

