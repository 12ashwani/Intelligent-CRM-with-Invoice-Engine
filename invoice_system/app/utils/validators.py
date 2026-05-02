import re

from app.utils.gst import GSTIN_RE, contains_pincode, resolve_state_and_code, split_place_of_supply


def _clean(value):
    return str(value or "").strip()


def validate_invoice_payload(data, company, customer):
    errors = []

    company_gstin = _clean(company.get("gstin"))
    if not company_gstin:
        errors.append("Supplier GSTIN is required in company settings.")
    elif not GSTIN_RE.match(company_gstin.upper()):
        errors.append("Supplier GSTIN must be a valid 15-character GSTIN.")

    company_address = _clean(company.get("address"))
    if not company_address or not contains_pincode(company_address):
        errors.append("Supplier address must include a 6-digit PIN code.")
    company_state, company_state_code = resolve_state_and_code(company.get("state"), company.get("state_code"), company.get("gstin"))
    if not company_state or not company_state_code:
        errors.append("Supplier state name and state code are required.")

    customer_name = _clean(customer.get("name"))
    if not customer_name:
        errors.append("Customer name is required.")

    customer_address = _clean(customer.get("address"))
    if not customer_address or not contains_pincode(customer_address):
        errors.append("Customer address must include a 6-digit PIN code.")

    customer_gstin = _clean(customer.get("gstin"))
    if customer_gstin and not GSTIN_RE.match(customer_gstin.upper()):
        errors.append("Customer GSTIN must be a valid 15-character GSTIN when provided.")
    customer_state, customer_state_code = resolve_state_and_code(customer.get("state"), customer.get("state_code"), customer.get("gstin"))
    if not customer_state or not customer_state_code:
        errors.append("Customer state name and state code are required.")

    place_of_supply = _clean(data.get("place_of_supply"))
    pos_state, pos_code = split_place_of_supply(place_of_supply)
    if not place_of_supply or not pos_state or not pos_code:
        errors.append("Place of supply is required in the format 'State Name (Code)'.")

    due_date = _clean(data.get("due_date"))
    if not due_date:
        errors.append("Due date is required.")

    payment_terms = _clean(data.get("payment_terms"))
    if not payment_terms:
        errors.append("Payment terms are required.")

    items = data.get("items") or []
    if not items:
        errors.append("At least one invoice item is required.")

    for index, item in enumerate(items, start=1):
        description = _clean(item.get("name"))
        sac = _clean(item.get("hsn"))
        qty = item.get("qty")
        price = item.get("price")

        if not description:
            errors.append(f"Item {index}: description is required.")
        if not sac:
            errors.append(f"Item {index}: SAC code is required.")
        elif not re.fullmatch(r"[0-9A-Za-z]{4,8}", sac):
            errors.append(f"Item {index}: SAC code must be 4 to 8 alphanumeric characters.")
        if qty is None or qty <= 0:
            errors.append(f"Item {index}: quantity must be greater than zero.")
        if price is None or price < 0:
            errors.append(f"Item {index}: rate must be zero or greater.")

    return errors
