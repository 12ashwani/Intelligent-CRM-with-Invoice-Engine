"""
Database-backed CRM tools used by the AI assistant.
"""

import os
import re
from contextvars import ContextVar
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, cast,Tuple

from ai_agent.db.mysql import get_connection


_USER_CONTEXT: ContextVar[Dict[str, Any]] = ContextVar("crm_user_context", default={})


SERVICE_DOCUMENT_REQUIREMENTS = {
    
    "gst registration": [
        "PAN card copy of the business or proprietor",
        "Aadhaar card of the proprietor or partners",
        "Proof of business address",
        "Bank account statement or cancelled cheque",
        "Business constitution document",
        "Photograph of the proprietor or partners",
        "Digital signature if required",
    ],
    "Plastic EPR Registration": [
        "Company PAN card copy",
        "GST registration certificate",
        "MSME/Udyam registration if available",
        "Bank account details",
        "Authorization letter from authorized signatory",
        "List of plastic products manufactured or handled",
        "Plastic production/import data",
        "Plastic waste collection or recycling agreements",
    ],
    "Plastic EPR Return": [
        "Company PAN card copy",
        "GST registration certificate",
        "EPR registration application form",
        "Plastic production/import data",
        "Plastic waste collection agreements",
        "Annual action plan for plastic waste management",
    ],
    "Battery EPR Registration": [
        "Company PAN card copy",
        "GST registration certificate",
        "MSME/Udyam registration if available",
        "IEC code if applicable",
        "List of battery types and quantities handled",
        "Annual production/import data",
        "Battery waste collection mechanism details",
        "Recycling partner agreements",
    ],
    "Battery EPR Return": [
        "Company PAN card copy",
        "GST registration certificate",
        "IEC code if applicable",
        "Battery type and quantity details",
        "Recycling partner agreements",
        "Battery waste collection plan",
    ],
    "e-waste registration": [
        "Company PAN card copy",
        "GST registration certificate",
        "CIN certificate for companies",
        "IEC code for importers",
        "E-waste generation or collection data",
        "Agreements with authorized recyclers",
        "Annual e-waste return filings if available",
    ],
    "e-waste Return": [
        "Company PAN card copy",
        "GST registration certificate",
        "CIN certificate for companies",
        "IEC code for importers",
        "E-waste generation or collection data",
        "Agreements with authorized recyclers",
        "Annual e-waste return filings if available",],
    "msme": [
        "Company PAN card copy",
        "Aadhaar card of proprietor/partner/director",
        "GST registration certificate",
        "Bank account details",
        "Address proof of business",
        "Investment and turnover declaration",
    ],
    "iso": [
        "Company PAN card copy",
        "GST registration certificate",
        "Certificate of incorporation",
        "Company letterhead with logo",
        "Organization chart",
        "Process flow chart",
        "Quality manual and procedures if available",
    ],
    "fssai": [
        "Company PAN card copy",
        "GST registration certificate",
        "Proof of premises",
        "List of food products handled",
        "Food safety management system plan",
        "Water testing report if applicable",
        "Partnership deed/MOA for companies",
    ],
    "iec": [
        "Company PAN card copy",
        "GST registration certificate",
        "Certificate of incorporation",
        "Digital signature certificate",
        "Bank account certificate",
        "Cancelled cheque of current account",
        "Address proof of registered office",
    ],
    "bis": [
        "Company PAN card copy",
        "GST registration certificate",
        "CIN certificate for companies",
        "Product testing report from BIS-approved lab",
        "Factory layout and machinery details",
        "Quality control plan",
        "Product sample for testing",
    ],
    "isi": [
        "Company PAN card copy",
        "GST registration certificate",
        "Factory address proof",
        "Product specification sheet",
        "Test reports from BIS-approved lab",
        "Manufacturing process flowchart",
        "Quality control staff details",
    ],
    "cdsco": [
        "Company PAN card copy",
        "GST registration certificate",
        "Drug manufacturing license if applicable",
        "Product list with composition",
        "Plant master file",
        "Medical device registration certificate if applicable",
    ],
    "lmpc": [
        "Company PAN card copy",
        "GST registration certificate",
        "IEC code for importers",
        "Product list with legal metrology details",
        "Packaging sample images",
        "Pre-packaged commodity declaration",
    ],
    "bee": [
        "Company PAN card copy",
        "GST registration certificate",
        "Product technical specifications",
        "Lab test report for energy efficiency",
        "Brand registration certificate if applicable",
        "Production volume data",
    ],
    "wpc": [
        "Company PAN card copy",
        "GST registration certificate",
        "IEC code for importers",
        "Equipment technical specification sheet",
        "Frequency band details",
        "RF test reports",
        "Product user manual",
    ],
    "tec": [
        "Company PAN card copy",
        "GST registration certificate",
        "CIN certificate for companies",
        "IEC code for importers",
        "Product technical specifications",
        "Test reports from TEC-approved lab",
        "Safety test reports",
    ],
}


LEAD_SELECT = """
    SELECT
        l.id,
        l.date,
        l.company_name,
        l.email,
        l.auth_person_name,
        l.auth_person_number,
        l.auth_person_email,
        l.service,
        l.status,
        l.created_at,
        m.name AS marketing_executive_name,
        op.name AS operation_executive_name,
        acc.name AS account_executive_name,
        o.file_status,
        o.filing_date,
        p.govt_payment_status,
        p.professional_payment_status,
        
        p.total_amount,
        p.govt_amount,
        p.professional_amount,
        
        p.payment_date,
        p.remarks AS account_remark
    FROM leads l
    LEFT JOIN employees m ON l.marketing_executive = m.id
    LEFT JOIN operations o ON l.id = o.lead_id
    LEFT JOIN employees op ON o.operation_executive = op.id
    LEFT JOIN payments p ON l.id = p.lead_id
    LEFT JOIN employees acc ON p.account_executive = acc.id
"""


def set_user_context(role: str = "", employee_id: Any = "", user_id: Any = ""):
    """Set request-local CRM user context for role-aware tools."""
    return _USER_CONTEXT.set(
        {
            "role": (role or "").strip().lower(),
            "employee_id": str(employee_id or "").strip(),
            "user_id": str(user_id or "").strip(),
        }
    )


def reset_user_context(token) -> None:
    _USER_CONTEXT.reset(token)


def _get_user_context() -> Tuple[str, str, str]:
    context = _USER_CONTEXT.get()
    role = context.get("role") or os.environ.get("CRM_ACTIVE_ROLE", "")
    employee_id = context.get("employee_id") or os.environ.get("CRM_ACTIVE_EMPLOYEE_ID", "")
    user_id = context.get("user_id") or os.environ.get("CRM_ACTIVE_USER_ID", "")
    return role.strip().lower(), str(employee_id).strip(), str(user_id).strip()


def _scope_sql() -> Tuple[str, List[Any]]:
    role, employee_id, _ = _get_user_context()
    if not role or role in {"admin", "hr"}:
        return "", []
    if not employee_id:
        return "1 = 0", []
    if role == "marketing":
        return "l.marketing_executive = %s", [employee_id]
    if role in {"operations", "operation"}:
        return "o.operation_executive = %s", [employee_id]
    if role in {"accounts", "account"}:
        return "p.account_executive = %s", [employee_id]
    return """(
        l.marketing_executive = %s
        OR o.operation_executive = %s
        OR p.account_executive = %s
    )""", [employee_id, employee_id, employee_id]


def is_role_scoped() -> bool:
    role, employee_id, _ = _get_user_context()
    return bool(employee_id and role and role not in {"admin", "hr"})


def _json_safe_row(row: Dict[str, Any]) -> Dict[str, Any]:
    safe = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date)):
            safe[key] = value.isoformat()
        elif isinstance(value, Decimal):
            safe[key] = float(value)
        else:
            safe[key] = value
    return safe



def _fetch_all(query: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(query, tuple(params or []))

        rows = cur.fetchall()

        return [
            _json_safe_row(cast(Dict[str, Any], row))
            for row in rows
        ]

    finally:
        cur.close()
        conn.close()


def _with_scope(conditions: Optional[List[str]] = None, params: Optional[List[Any]] = None):
    conditions = list(conditions or [])
    params = list(params or [])
    scope_condition, scope_params = _scope_sql()
    if scope_condition:
        conditions.append(scope_condition)
        params.extend(scope_params)
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    return where, params


def _clean_search_text(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(
        r"\b(show|get|find|search|lead|leads|detail|details|customer|payment|history|invoice|company|for|by|of|please)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", text).strip()


def get_today_leads():
    where, params = _with_scope(["DATE(COALESCE(l.date, l.created_at)) = CURDATE()"])
    return _fetch_all(f"{LEAD_SELECT}{where} ORDER BY l.created_at DESC", params)


def get_all_leads():
    where, params = _with_scope()
    return _fetch_all(f"{LEAD_SELECT}{where} ORDER BY l.created_at DESC LIMIT 100", params)


def get_leads_by_status(status: str):
    where, params = _with_scope(["LOWER(l.status) = LOWER(%s)"], [status])
    return _fetch_all(f"{LEAD_SELECT}{where} ORDER BY l.created_at DESC", params)


def get_lead_by_company(company_name: str):
    query_text = _clean_search_text(company_name)
    if not query_text or query_text.lower() in {"lead", "leads", "detail", "details"}:
        return {"message": "Please type a company name after lead details. Example: lead details ABC Pvt Ltd"}
    where, params = _with_scope(["l.company_name LIKE %s"], [f"%{query_text}%"])
    return _fetch_all(f"{LEAD_SELECT}{where} ORDER BY l.created_at DESC LIMIT 20", params)


def search_customer(query: str):
    query_text = _clean_search_text(query)
    if not query_text or query_text.lower() in {"customer", "client"}:
        return {"message": "Please type a company, customer name, email, or mobile number after search customer."}
    like = f"%{query_text}%"
    where, params = _with_scope(
        [
            """(
                l.company_name LIKE %s
                OR l.email LIKE %s
                OR l.auth_person_name LIKE %s
                OR l.auth_person_email LIKE %s
                OR l.auth_person_number LIKE %s
            )"""
        ],
        [like, like, like, like, like],
    )
    return _fetch_all(f"{LEAD_SELECT}{where} ORDER BY l.created_at DESC LIMIT 20", params)


def get_status_report():
    where, params = _with_scope()
    rows = _fetch_all(
        f"""
        SELECT COALESCE(l.status, 'Unknown') AS status, COUNT(*) AS total
        FROM leads l
        LEFT JOIN operations o ON l.id = o.lead_id
        LEFT JOIN payments p ON l.id = p.lead_id
        {where}
        GROUP BY COALESCE(l.status, 'Unknown')
        ORDER BY total DESC, status ASC
        """,
        params,
    )
    return {"total": sum(row["total"] for row in rows), "by_status": rows}


def get_payment_history(query: str):
    role, _, _ = _get_user_context()
    if role and role not in {"admin", "accounts", "account"}:
        return {"message": "Payment history is available only to admin and accounts users."}

    query_text = _clean_search_text(query)
    if not query_text or query_text.lower() in {"payment", "history"}:
        return {"message": "Please type a company name after payment history."}
    like = f"%{query_text}%"
    where, params = _with_scope(["(l.company_name LIKE %s OR l.email LIKE %s)"], [like, like])
    return _fetch_all(
        f"""
        {LEAD_SELECT}
        {where}
        ORDER BY COALESCE(p.payment_date, p.updated_at, p.created_at) DESC
        LIMIT 20
        """,
        params,
    )


def get_pending_payments():
    conditions = [
        """(
            LOWER(COALESCE(p.govt_payment_status, 'pending')) IN ('pending', 'failed')
            OR LOWER(COALESCE(p.professional_payment_status, 'pending')) IN ('pending', 'failed')
        )"""
    ]
    where, params = _with_scope(conditions)
    return _fetch_all(f"{LEAD_SELECT}{where} ORDER BY l.created_at DESC LIMIT 50", params)


def get_service_documents(service_text: str) -> Dict[str, List[str]]:
    text = (service_text or "").strip().lower()
    text = re.sub(r"\b(regitration|rgistration|registeration)\b", "registration", text)
    text = re.sub(r"\bewaste\b", "e-waste", text)
    if not text:
        return SERVICE_DOCUMENT_REQUIREMENTS

    wants_return = "return" in text
    normalized_text = text.replace("-", " ")

    service_variants = [
        ("plastic", "Plastic EPR Return" if wants_return else "Plastic EPR Registration"),
        ("battery", "Battery EPR Return" if wants_return else "Battery EPR Registration"),
        ("e waste", "e-waste Return" if wants_return else "e-waste registration"),
        ("e-waste", "e-waste Return" if wants_return else "e-waste registration"),
    ]
    for marker, service_key in service_variants:
        if marker in normalized_text and service_key in SERVICE_DOCUMENT_REQUIREMENTS:
            return {service_key: SERVICE_DOCUMENT_REQUIREMENTS[service_key]}

    for service, docs in SERVICE_DOCUMENT_REQUIREMENTS.items():
        if service.lower() in text:
            return {service: docs}

    stop_words = {
        "what", "which", "document", "documents", "required", "needed",
        "list", "for", "registration", "docs", "need",
    }
    keywords = {
        word
        for word in re.findall(r"[a-z0-9]+", text)
        if len(word) > 2 and word not in stop_words
    }
    matches = {
        service: docs
        for service, docs in SERVICE_DOCUMENT_REQUIREMENTS.items()
        if keywords and any(word in service.lower() for word in keywords)
    }
    return matches or {"message": ["No document checklist found for this service."]}
