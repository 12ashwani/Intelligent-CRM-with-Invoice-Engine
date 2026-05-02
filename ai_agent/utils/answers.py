"""
ai_agent.utils.answers
Professional response formatting layer for CRM AI Assistant.

Responsibilities:
- Convert raw tool/database output into readable responses
- Standardize payload structure
- Centralize reusable templates
- Maintain strong typing
"""

from __future__ import annotations
from typing import Any, cast

from typing import Any, Callable, Dict, List, Optional, TypedDict


# =====================================================
# Type Aliases
# =====================================================

CRMRow = Dict[str, Any]
CRMRows = List[CRMRow]


class AnswerPayloadRequired(TypedDict):
    message: str


class AnswerPayload(AnswerPayloadRequired, total=False):
    data: Any
    count: int
    total: int
    total_due: float
    total_amount: float
    type: str


# =====================================================
# Helpers
# =====================================================

def safe_str(value: Any, default: str = "N/A") -> str:
    """Return string-safe value."""
    if value is None or value == "":
        return default
    return str(value)


def safe_float(value: Any) -> float:
    """Convert value safely to float."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0




def make_payload(
    message: str,
    data: Any = None,
    payload_type: str = "response",
    **extra: Any,
) -> AnswerPayload:
    """Build standardized response payload."""

    payload = {
        "message": message,
        "data": data,
        "type": payload_type,
        **extra,
    }

    return cast(AnswerPayload, payload)


# =====================================================
# Repository
# =====================================================

class AnswerRepository:
    """Centralized formatter for all CRM responses."""

    # -------------------------------------------------
    # Lead Lists
    # -------------------------------------------------
    @staticmethod
    def format_lead_list(leads: CRMRows) -> AnswerPayload:
        if not leads:
            return make_payload(
                "No leads found in the database.",
                data=[],
                payload_type="lead_list",
                count=0,
            )

        lines = [f"Found {len(leads)} Leads", ""]

        for index, lead in enumerate(leads[:10], start=1):
            lines.extend(
                [
                    f"{index}. {safe_str(lead.get('company_name'), 'Unknown')}",
                    f"   Contact: {safe_str(lead.get('auth_person_name'))}",
                    f"   Mobile: {safe_str(lead.get('auth_person_number'))}",
                    f"   Email: {safe_str(lead.get('email'))}",
                    f"   Service: {safe_str(lead.get('service'))}",
                    f"   Status: {safe_str(lead.get('status'))}",
                    f"   Date: {safe_str(lead.get('date') or lead.get('created_at'))}",
                    "",
                ]
            )

        if len(leads) > 10:
            lines.append(f"And {len(leads) - 10} more leads...")

        return make_payload(
            "\n".join(lines),
            data=leads,
            payload_type="lead_list",
            count=len(leads),
        )

    # -------------------------------------------------
    # Pending Payments
    # -------------------------------------------------
    @staticmethod
    def format_pending_payments(payments: CRMRows) -> AnswerPayload:
        if not payments:
            return make_payload(
                "No pending payments found. All payments are up to date.",
                data=[],
                payload_type="pending_payments",
                count=0,
            )

        total_due = 0.0
        lines = ["Pending Payments", ""]

        for index, row in enumerate(payments[:10], start=1):
            govt = safe_float(row.get("govt_amount"))
            prof = safe_float(row.get("professional_amount"))
            due = govt + prof
            total_due += due

            lines.extend(
                [
                    f"{index}. {safe_str(row.get('company_name'), 'Unknown')}",
                    f"   Total Due: Rs. {due:,.2f}",
                    f"   Govt Amount: Rs. {govt:,.2f}",
                    f"   Professional Amount: Rs. {prof:,.2f}",
                    f"   Govt Status: {safe_str(row.get('govt_payment_status'), 'Pending')}",
                    f"   Professional Status: {safe_str(row.get('professional_payment_status'), 'Pending')}",
                    "",
                ]
            )

        lines.append(f"Total Outstanding: Rs. {total_due:,.2f}")

        return make_payload(
            "\n".join(lines),
            data=payments,
            payload_type="pending_payments",
            count=len(payments),
            total_due=total_due,
        )

    # -------------------------------------------------
    # Status Report
    # -------------------------------------------------
    @staticmethod
    def format_status_report(report: CRMRow) -> AnswerPayload:
        rows = report.get("by_status", [])

        if not rows:
            return make_payload(
                "No status report data available.",
                data=report,
                payload_type="status_report",
            )

        total = int(report.get("total", 0) or 0)

        lines = ["Lead Status Report", ""]

        for row in rows:
            count = int(row.get("total", 0) or 0)
            pct = (count / total * 100) if total else 0
            lines.append(
                f"{safe_str(row.get('status'), 'Unknown')}: "
                f"{count} leads ({pct:.1f}%)"
            )

        lines.extend(["", f"Total Leads: {total}"])

        return make_payload(
            "\n".join(lines),
            data=report,
            payload_type="status_report",
            total=total,
        )

    # -------------------------------------------------
    # Lead Details
    # -------------------------------------------------
    @staticmethod
    def format_lead_details(leads: CRMRows) -> AnswerPayload:
        if not leads:
            return make_payload(
                "No lead details found.",
                data=None,
                payload_type="lead_details",
            )

        lead = leads[0]

        lines = [
            f"Lead Details: {safe_str(lead.get('company_name'), 'Unknown')}",
            "",
            f"Contact Person: {safe_str(lead.get('auth_person_name'))}",
            f"Mobile: {safe_str(lead.get('auth_person_number'))}",
            f"Email: {safe_str(lead.get('email'))}",
            f"Service: {safe_str(lead.get('service'))}",
            f"Status: {safe_str(lead.get('status'))}",
            f"Marketing: {safe_str(lead.get('marketing_executive_name'))}",
            f"Operations: {safe_str(lead.get('operation_executive_name'))}",
            f"Accounts: {safe_str(lead.get('account_executive_name'))}",
        ]

        return make_payload(
            "\n".join(lines),
            data=lead,
            payload_type="lead_details",
        )

    # -------------------------------------------------
    # Customer Search
    # -------------------------------------------------
    @staticmethod
    def format_customer_search(customers: CRMRows) -> AnswerPayload:
        return AnswerRepository.format_lead_list(customers)

    # -------------------------------------------------
    # Payment History
    # -------------------------------------------------
    @staticmethod
    def format_payment_history(history: CRMRows) -> AnswerPayload:
        if not history:
            return make_payload(
                "No payment history found.",
                data=[],
                payload_type="payment_history",
                count=0,
            )

        total = 0.0
        lines = ["Payment History", ""]

        for index, row in enumerate(history[:10], start=1):
            amount = safe_float(row.get("total_amount"))
            total += amount

            lines.extend(
                [
                    f"{index}. {safe_str(row.get('company_name'), 'Unknown')}",
                    f"   Amount: Rs. {amount:,.2f}",
                    f"   Date: {safe_str(row.get('payment_date'))}",
                    "",
                ]
            )

        lines.append(f"Total Amount: Rs. {total:,.2f}")

        return make_payload(
            "\n".join(lines),
            data=history,
            payload_type="payment_history",
            count=len(history),
            total_amount=total,
        )

    # -------------------------------------------------
    # Service Documents
    # -------------------------------------------------
    @staticmethod
    def format_service_documents(documents: CRMRow) -> AnswerPayload:
        if not documents:
            return make_payload(
                "No document requirements found.",
                data=[],
                payload_type="service_documents",
            )

        if "message" in documents:
            msg = documents["message"]
            if isinstance(msg, list):
                text = msg[0] if msg else "No document details found."
            else:
                text = safe_str(msg)

            return make_payload(
                text,
                data=None,
                payload_type="service_documents",
            )

        lines = ["Required Documents", ""]

        for service, docs in documents.items():
            lines.append(service.upper())

            if isinstance(docs, list):
                for index, item in enumerate(docs, start=1):
                    lines.append(f"{index}. {item}")

            lines.append("")

        return make_payload(
            "\n".join(lines),
            data=documents,
            payload_type="service_documents",
        )

    # -------------------------------------------------
    # Static Messages
    # -------------------------------------------------
    @staticmethod
    def welcome_message() -> AnswerPayload:
        return make_payload(
            (
                "Welcome to CRM AI Assistant!\n\n"
                "Try:\n"
                "- all leads\n"
                "- today leads\n"
                "- pending payments\n"
                "- status report\n"
                "- lead details ABC Pvt Ltd"
            ),
            payload_type="welcome",
        )

    @staticmethod
    def help_message() -> AnswerPayload:
        return make_payload(
            (
                "Available Commands:\n"
                "- all leads\n"
                "- today leads\n"
                "- pending payments\n"
                "- status report\n"
                "- lead details [company]\n"
                "- search customer [name]\n"
                "- payment history [company]"
            ),
            payload_type="help",
        )

    @staticmethod
    def conversation_message() -> AnswerPayload:
        return make_payload(
            "I help users retrieve CRM data quickly and accurately.",
            payload_type="conversation",
        )

    @staticmethod
    def fallback_response(query: str) -> AnswerPayload:
        return make_payload(
            f"No CRM result found for '{query}'. Type help.",
            payload_type="fallback",
        )

    @staticmethod
    def error_response(
        error_type: str,
        details: Optional[str] = None,
    ) -> AnswerPayload:

        errors = {
            "no_data": "No matching data found.",
            "unauthorized": "Access denied.",
            "database_error": f"Database error: {details}" if details else "Database error.",
        }

        return make_payload(
            errors.get(error_type, "An error occurred."),
            payload_type="error",
        )


# =====================================================
# Public Resolver
# =====================================================

def get_answer(answer_type: str, data: Any = None, **kwargs: Any) -> AnswerPayload:
    """Public dispatcher."""

    repo = AnswerRepository()

    answer_map: Dict[str, Callable[..., AnswerPayload]] = {
        "lead_list": repo.format_lead_list,
        "pending_payments": repo.format_pending_payments,
        "status_report": repo.format_status_report,
        "lead_details": repo.format_lead_details,
        "customer_search": repo.format_customer_search,
        "payment_history": repo.format_payment_history,
        "service_documents": repo.format_service_documents,
        "welcome": repo.welcome_message,
        "help": repo.help_message,
        "conversation": repo.conversation_message,
        "fallback": lambda: repo.fallback_response(kwargs.get("query", "")),
        "error": lambda: repo.error_response(
            kwargs.get("error_type", ""),
            kwargs.get("details"),
        ),
    }

    handler = answer_map.get(answer_type)

    if not handler:
        return repo.fallback_response("unknown")

    if data is not None:
        return handler(data)

    return handler()