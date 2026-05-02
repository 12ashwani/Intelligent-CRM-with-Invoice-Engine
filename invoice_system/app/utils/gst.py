from __future__ import annotations

import re
from datetime import date, datetime

STATE_CODE_MAP = {
    "andaman and nicobar islands": "35",
    "andhra pradesh": "37",
    "arunachal pradesh": "12",
    "assam": "18",
    "bihar": "10",
    "chandigarh": "04",
    "chhattisgarh": "22",
    "dadra and nagar haveli and daman and diu": "26",
    "daman and diu": "25",
    "dadra and nagar haveli": "26",
    "delhi": "07",
    "goa": "30",
    "gujarat": "24",
    "haryana": "06",
    "himachal pradesh": "02",
    "jammu and kashmir": "01",
    "jharkhand": "20",
    "karnataka": "29",
    "kerala": "32",
    "ladakh": "38",
    "lakshadweep": "31",
    "madhya pradesh": "23",
    "maharashtra": "27",
    "manipur": "14",
    "meghalaya": "17",
    "mizoram": "15",
    "nagaland": "13",
    "odisha": "21",
    "orissa": "21",
    "puducherry": "34",
    "pondicherry": "34",
    "punjab": "03",
    "rajasthan": "08",
    "sikkim": "11",
    "tamil nadu": "33",
    "telangana": "36",
    "tripura": "16",
    "uttar pradesh": "09",
    "uttarakhand": "05",
    "west bengal": "19",
    "other territory": "97",
    "other country": "96",
}

CODE_STATE_MAP = {value: key.title() for key, value in STATE_CODE_MAP.items()}
PINCODE_RE = re.compile(r"\b\d{6}\b")
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z0-9]{13}$")


def normalize_state_name(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def extract_state_code_from_gstin(gstin: str | None) -> str:
    gstin_value = (gstin or "").strip().upper()
    if GSTIN_RE.match(gstin_value):
        return gstin_value[:2]
    return ""


def state_code_for_name(state_name: str | None) -> str:
    return STATE_CODE_MAP.get(normalize_state_name(state_name).lower(), "")


def state_name_for_code(state_code: str | None) -> str:
    code = str(state_code or "").strip()
    return CODE_STATE_MAP.get(code.zfill(2), "") if code else ""


def resolve_state_and_code(state_name: str | None = None, state_code: str | None = None, gstin: str | None = None):
    resolved_name = normalize_state_name(state_name)
    resolved_code = str(state_code or "").strip()

    if not resolved_code:
        resolved_code = extract_state_code_from_gstin(gstin)
    if not resolved_code and resolved_name:
        resolved_code = state_code_for_name(resolved_name)
    if not resolved_name and resolved_code:
        resolved_name = state_name_for_code(resolved_code)
    if resolved_code:
        resolved_code = resolved_code.zfill(2)
    return resolved_name, resolved_code


def split_place_of_supply(place_of_supply: str | None):
    value = normalize_state_name(place_of_supply)
    if not value:
        return "", ""

    match = re.search(r"\((\d{2})\)", value)
    if match:
        return resolve_state_and_code(value[: match.start()].strip(" ,-"), match.group(1))
    return resolve_state_and_code(value)


def validate_address_pincode(address: str | None) -> bool:
    """Validate that address contains a 6-digit PIN code"""
    if not address:
        return False
    return bool(PINCODE_RE.search(address))


def validate_place_of_supply_format(place_of_supply: str | None) -> bool:
    """Validate that place of supply is in format 'State Name (Code)'"""
    if not place_of_supply:
        return False
    value = normalize_state_name(place_of_supply)
    match = re.search(r"^(.+)\s*\((\d{2})\)$", value)
    if not match:
        return False
    state_name = match.group(1).strip()
    state_code = match.group(2)
    # Verify the state code matches the state name
    expected_code = state_code_for_name(state_name)
    return expected_code == state_code


def extract_gstin_details(gstin: str | None) -> dict:
    """Extract state details from GSTIN for auto-fill functionality"""
    gstin_value = (gstin or "").strip().upper()
    if not GSTIN_RE.match(gstin_value):
        return {}

    state_code = gstin_value[:2]
    state_name = state_name_for_code(state_code)

    return {
        "state_code": state_code,
        "state_name": state_name,
        "place_of_supply": f"{state_name} ({state_code})" if state_name else "",
        "gstin_valid": True
    }


def format_state_with_code(state_name: str | None, state_code: str | None) -> str:
    name, code = resolve_state_and_code(state_name, state_code)
    if name and code:
        return f"{name} ({code})"
    return name or code


def contains_pincode(address: str | None) -> bool:
    return bool(PINCODE_RE.search(address or ""))


def format_invoice_date(value) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d-%m-%Y")
    if isinstance(value, date):
        return value.strftime("%d-%m-%Y")

    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%d-%m-%Y")
        except ValueError:
            continue
    return text
