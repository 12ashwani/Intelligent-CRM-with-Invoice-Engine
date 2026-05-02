"""
ai_agent.agent.executor
Professional execution layer for CRM AI Agent.

Responsibilities:
- Receive action from planner
- Execute mapped tool function
- Apply role context
- Format responses via answers.py
- Return standardized payload
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ai_agent.tools.crm_tools import (
    get_all_leads,
    get_lead_by_company,
    get_payment_history,
    get_pending_payments,
    get_service_documents,
    get_status_report,
    get_today_leads,
    search_customer,
    is_role_scoped,
    set_user_context,
    reset_user_context,
)

from ai_agent.utils.answers import get_answer


# =====================================================
# Type Aliases
# =====================================================

ToolResult = Any
ToolFunction = Callable[..., ToolResult]


# =====================================================
# Action Maps
# =====================================================

TOOL_ACTION_MAP: Dict[str, ToolFunction] = {
    "today_leads": get_today_leads,
    "all_leads": get_all_leads,
    "pending_payment": get_pending_payments,
    "status_report": get_status_report,
    "lead_details": get_lead_by_company,
    "customer_search": search_customer,
    "payment_history": get_payment_history,
    "service_documents": get_service_documents,
}

ANSWER_TYPE_MAP: Dict[str, str] = {
    "today_leads": "lead_list",
    "all_leads": "lead_list",
    "pending_payment": "pending_payments",
    "status_report": "status_report",
    "lead_details": "lead_details",
    "customer_search": "customer_search",
    "payment_history": "payment_history",
    "service_documents": "service_documents",
}

PARAM_ACTIONS = {
    "lead_details",
    "customer_search",
    "payment_history",
    "service_documents",
}


# =====================================================
# Helpers
# =====================================================

def _help_response(user_text: str) -> Dict[str, Any]:
    """Handle conversational / help requests."""
    user_lower = user_text.lower().strip()

    if user_lower in {"help", "commands", "examples", "sample questions"}:
        return {
            "source": "crm_help",
            "response": get_answer("help")["message"],
        }

    if user_lower in {"hi", "hello", "hey", "start"}:
        return {
            "source": "crm_help",
            "response": get_answer("welcome")["message"],
        }

    if any(
        phrase in user_lower
        for phrase in [
            "what can you do",
            "how can you help",
            "what do you do",
            "who are you",
            "about you",
            "how to use",
            "what should i ask",
            "why use this bot",
            "explain",
        ]
    ):
        return {
            "source": "crm_help",
            "response": get_answer("conversation")["message"],
        }

    return {
        "source": "crm_help",
        "response": get_answer("fallback", query=user_text)["message"],
    }


def _no_data_response(action: str) -> Dict[str, Any]:
    """Standard no-data response."""
    msg = get_answer("error", error_type="no_data")["message"]

    if is_role_scoped() and action in {
        "all_leads",
        "today_leads",
        "status_report",
        "lead_details",
        "customer_search",
    }:
        msg = "No matching data found in your assigned leads."

    return {
        "source": "crm_tool",
        "response": msg,
        "data": [],
        "count": 0,
    }


def _unauthorized_response() -> Dict[str, Any]:
    return {
        "source": "crm_error",
        "response": get_answer(
            "error",
            error_type="unauthorized"
        )["message"],
    }


def _error_response(exc: Exception) -> Dict[str, Any]:
    return {
        "source": "crm_error",
        "response": get_answer(
            "error",
            error_type="database_error",
            details=str(exc),
        )["message"],
        "error": str(exc),
    }


# =====================================================
# Main Executor
# =====================================================

def execute(
    action: str,
    user_text: str,
    role: str = "",
    employee_id: str = "",
) -> Dict[str, Any]:
    """
    Execute action selected by planner.

    Args:
        action: planner-selected action
        user_text: original user query
        role: employee role
        employee_id: logged-in employee id

    Returns:
        Standard response payload
    """

    token: Optional[Any] = None

    if role or employee_id:
        token = set_user_context(
            role=role,
            employee_id=employee_id,
        )

    try:
        # ---------------------------------------------
        # Help / Chat responses
        # ---------------------------------------------
        if action == "llm_response":
            return _help_response(user_text)

        # ---------------------------------------------
        # Unsupported action
        # ---------------------------------------------
        if action not in TOOL_ACTION_MAP:
            return {
                "source": "crm_error",
                "response": "Action not supported.",
            }

        # ---------------------------------------------
        # Execute tool
        # ---------------------------------------------
        tool_func = TOOL_ACTION_MAP[action]

        if action in PARAM_ACTIONS:
            result = tool_func(user_text)
        else:
            result = tool_func()

        # ---------------------------------------------
        # Empty results
        # ---------------------------------------------
        if not result or (
            isinstance(result, list) and len(result) == 0
        ):
            return _no_data_response(action)

        # ---------------------------------------------
        # Access denied
        # ---------------------------------------------
        if isinstance(result, dict) and "message" in result:
            msg = str(result["message"]).lower()

            if "denied" in msg:
                return _unauthorized_response()

            return {
                "source": "crm_tool",
                "response": result["message"],
                "data": result,
            }

        # ---------------------------------------------
        # Format final answer
        # ---------------------------------------------
        answer_type = ANSWER_TYPE_MAP.get(action)

        if answer_type:
            formatted = get_answer(answer_type, result)

            return {
                "source": "crm_tool",
                "response": formatted["message"],
                "data": result,
                "count": len(result) if isinstance(result, list) else 1,
            }

        # ---------------------------------------------
        # Fallback raw response
        # ---------------------------------------------
        return {
            "source": "crm_tool",
            "response": str(result),
            "data": result,
        }

    except Exception as exc:
        return _error_response(exc)

    finally:
        if token is not None:
            reset_user_context(token)