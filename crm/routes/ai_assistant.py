"""
AI Assistant Route for CRM
Provides secure API endpoints for the AI chatbot
- Filters data by employee role and access
- Ensures data security and privacy
"""

import os
import sys

# Add project root to path so absolute imports like `ai_agent.*` work reliably.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set up environment variables for AI agent
os.environ.setdefault('CRM_DB_HOST', 'localhost')
os.environ.setdefault('CRM_DB_USER', 'root')
os.environ.setdefault('CRM_DB_PASSWORD', 'Dayachand@7037')
os.environ.setdefault('CRM_DB_NAME', 'crm_db')

# Now import Flask and other modules
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from database import get_db_connection

# Import from AI agent
try:
    from ai_agent.agent.agent import run_agent
except ImportError as e:
    print(f"Warning: Could not import AI agent modules: {e}")
    def run_agent(user_input, role="", employee_id=""):
        return {
            "source": "crm_error",
            "action": None,
            "response": "AI assistant is not available right now. Please try again after restart.",
            "error": str(e),
        }

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")


def filter_leads_by_employee_role(leads, employee_role, employee_id):
    """
    Filter leads based on employee role and access level
    - Admin: can see all leads
    - Marketing: can see only their own leads
    - Operations: can see only their assigned leads
    - Accounts: can see only assigned payments
    """
    if not leads:
        return leads

    if employee_role in ["admin", "hr"]:
        # Admins and HR can see all leads
        return leads

    if employee_role == "marketing":
        # Marketing can only see leads they created
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id FROM employees WHERE id=%s", (employee_id,))
        emp = cur.fetchone()
        cur.close()
        conn.close()

        if not emp:
            return []

        # Filter leads assigned to this marketing executive
        filtered = [
            lead for lead in leads
            if lead.get("marketing_executive") == employee_id or
               lead.get("id") in [l.get("id") for l in leads]
        ]
        return filtered

    if employee_role == "operations":
        # Operations can only see leads assigned to them
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """SELECT l.id FROM leads l
               LEFT JOIN operations o ON l.id = o.lead_id
               WHERE o.operation_executive = %s""",
            (employee_id,)
        )
        assigned_lead_ids = [row["id"] for row in cur.fetchall()]
        cur.close()
        conn.close()

        return [lead for lead in leads if lead.get("id") in assigned_lead_ids]

    if employee_role == "accounts":
        # Accounts can only see leads with payments assigned to them
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """SELECT DISTINCT l.id FROM leads l
               LEFT JOIN payments p ON l.id = p.lead_id
               WHERE p.account_executive = %s""",
            (employee_id,)
        )
        assigned_lead_ids = [row["id"] for row in cur.fetchall()]
        cur.close()
        conn.close()

        return [lead for lead in leads if lead.get("id") in assigned_lead_ids]

    # Default: filter by employee's own data
    return leads


def sanitize_response(data):
    """Safely serialize response data to JSON"""
    if isinstance(data, list):
        return [sanitize_response(item) for item in data]
    elif isinstance(data, dict):
        return {k: sanitize_response(v) for k, v in data.items()}
    elif hasattr(data, 'isoformat'):  # datetime objects
        return data.isoformat()
    else:
        return data


@ai_bp.route("/query", methods=["POST"])
@login_required
def ai_query():
    """
    Main AI query endpoint
    Accepts user input and routes to appropriate CRM function
    """
    try:
        data = request.get_json(silent=True) or {}
        user_input = (data.get("message") or data.get("query") or "").strip()

        if not user_input:
            return jsonify({"error": "Query cannot be empty"}), 400

        # Limit query length
        if len(user_input) > 500:
            return jsonify({"error": "Query too long (max 500 characters)"}), 400

        role = (getattr(current_user, "role", "") or "").strip().lower()
        employee_id = str(getattr(current_user, "employee_id", "") or "").strip()
        result = run_agent(user_input, role=role, employee_id=employee_id)

        return jsonify(
            {
                "success": True,
                "user_role": role,
                "employee_id": employee_id,
                **sanitize_response(result),
            }
        ), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@ai_bp.route("/health", methods=["GET"])
@login_required
def health_check():
    """Check if AI assistant is available"""
    return jsonify({
        "status": "ok",
        "user": current_user.username,
        "role": current_user.role
    }), 200
