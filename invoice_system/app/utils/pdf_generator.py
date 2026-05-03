import os
import tempfile
from decimal import Decimal
from urllib.parse import urlparse, unquote

HTML = None
WEASYPRINT_AVAILABLE = False

try:
    import pdfkit
    PDFKIT_AVAILABLE = True
except ImportError:
    PDFKIT_AVAILABLE = False

try:
    from xhtml2pdf import pisa
    XHTML2PDF_AVAILABLE = True
except (ImportError, OSError):
    XHTML2PDF_AVAILABLE = False

from flask import current_app, render_template, url_for

from app.utils.gst import format_invoice_date, format_state_with_code, resolve_state_and_code, split_place_of_supply
from app.utils.number_to_words import number_to_words_indian


def _load_weasyprint():
    """Lazy import WeasyPrint to avoid startup warnings when native libs are missing."""
    global HTML, WEASYPRINT_AVAILABLE

    if HTML is not None:
        return True

    try:
        from weasyprint import HTML as weasyprint_html

        HTML = weasyprint_html
        WEASYPRINT_AVAILABLE = True
    except (ImportError, OSError):
        WEASYPRINT_AVAILABLE = False

    return WEASYPRINT_AVAILABLE


def _pdfkit_configuration():
    if not PDFKIT_AVAILABLE:
        return None
    try:
        return pdfkit.configuration()
    except OSError:
        return None


def _row_get(row, key, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (IndexError, KeyError, TypeError):
        return default


def _to_decimal(value):
    if value in (None, ""):
        return Decimal("0.00")
    return Decimal(str(value))


def _display_value(value, default="-"):
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _format_money(value):
    return f"{_to_decimal(value):.2f}"


def _format_quantity(value):
    quantity = _to_decimal(value)
    if quantity == quantity.to_integral():
        return str(int(quantity))
    return format(quantity.normalize(), "f")


def _resolve_image_path(image_path):
    if not image_path:
        return ""
    if image_path.startswith(("http://", "https://", "file://")):
        return image_path

    app_root = current_app.root_path
    candidates = []

    if os.path.isabs(image_path):
        candidates.append(image_path)
    else:
        candidates.extend(
            [
                os.path.join(app_root, image_path.lstrip("/")),
                os.path.join(app_root, "static", image_path.lstrip("/")),
                os.path.join(app_root, "static", "uploads", image_path),
            ]
        )

    for candidate in candidates:
        absolute_path = os.path.abspath(candidate)
        if os.path.exists(absolute_path):
            return f"file:///{absolute_path.replace(os.sep, '/')}"
    return image_path


def _xhtml2pdf_link_callback(uri, _rel):
    if not uri:
        return uri

    if uri.startswith("file:///"):
        parsed = urlparse(uri)
        resolved = unquote(parsed.path or "")
        if os.name == "nt" and resolved.startswith("/"):
            resolved = resolved[1:]
        return resolved

    if uri.startswith(("http://", "https://")):
        return uri

    if uri.startswith("/static/"):
        static_path = os.path.join(current_app.root_path, "static", uri[len("/static/"):].lstrip("/"))
        return os.path.abspath(static_path)

    return uri


def select_invoice_template(invoice_type):
    invoice_kind = str(invoice_type or "").strip().upper()
    if invoice_kind == "TAX":
        return "invoices/tax.html"
    if invoice_kind == "PI":
        return "invoices/pi.html"
    return "invoices/invoice.html"


def _normalize_invoice(invoice):
    data = {
        "id": _row_get(invoice, "id", _row_get(invoice, 0)),
        "invoice_number": _display_value(_row_get(invoice, "invoice_number", _row_get(invoice, 1, "")), "invoice"),
        "invoice_type": _display_value(_row_get(invoice, "invoice_type", _row_get(invoice, 2, "PI")), "PI").upper(),
        "customer_id": _row_get(invoice, "customer_id", _row_get(invoice, 3)),
        "subtotal": _to_decimal(_row_get(invoice, "subtotal", _row_get(invoice, 4, 0))),
        "tax_amount": _to_decimal(_row_get(invoice, "tax_amount", _row_get(invoice, 5, 0))),
        "total": _to_decimal(_row_get(invoice, "total", _row_get(invoice, 6, 0))),
        "cgst": _to_decimal(_row_get(invoice, "cgst", _row_get(invoice, 7, 0))),
        "sgst": _to_decimal(_row_get(invoice, "sgst", _row_get(invoice, 8, 0))),
        "igst": _to_decimal(_row_get(invoice, "igst", _row_get(invoice, 9, 0))),
        "status": _display_value(_row_get(invoice, "status", _row_get(invoice, 10, "unpaid")), "unpaid"),
        "lead_id": _row_get(invoice, "lead_id", _row_get(invoice, 11)),
        "created_at": _row_get(invoice, "created_at", _row_get(invoice, 12, "")),
        "po_number": _display_value(_row_get(invoice, "po_number", _row_get(invoice, 13, ""))),
        "place_of_supply": _display_value(_row_get(invoice, "place_of_supply", _row_get(invoice, 14, ""))),
        "payment_terms": _display_value(_row_get(invoice, "payment_terms", _row_get(invoice, 15, "Net 30 days")), "Net 30 days"),
        "due_date": _row_get(invoice, "due_date", _row_get(invoice, 16, "")),
        "total_in_words": _display_value(_row_get(invoice, "total_in_words", _row_get(invoice, 17, ""))),
        "reference_no_date": _display_value(_row_get(invoice, "reference_no_date", "")),
        "other_references": _display_value(_row_get(invoice, "other_references", "")),
        "remarks": _display_value(_row_get(invoice, "remarks", "")),
    }

    pos_name, pos_code = split_place_of_supply(data["place_of_supply"])
    data["created_at_display"] = _display_value(format_invoice_date(data["created_at"]))
    data["due_date_display"] = _display_value(format_invoice_date(data["due_date"]))
    data["place_of_supply_name"] = pos_name
    data["place_of_supply_code"] = pos_code
    data["place_of_supply_display"] = _display_value(format_state_with_code(pos_name, pos_code))
    data["tax_total"] = (data["cgst"] + data["sgst"] + data["igst"]).quantize(Decimal("0.01"))
    data["is_intra_state"] = data["cgst"] > 0 or data["sgst"] > 0
    data["cgst_rate_percent"] = "9" if data["cgst"] > 0 else "0"
    data["sgst_rate_percent"] = "9" if data["sgst"] > 0 else "0"
    data["igst_rate_percent"] = "18" if data["igst"] > 0 else "0"
    if data["total_in_words"] in ("", "-"):
        data["total_in_words"] = number_to_words_indian(float(data["total"]))
    data["tax_in_words"] = number_to_words_indian(float(data["tax_total"])) if data["tax_total"] > 0 else "-"
    return data


def _normalize_customer(customer):
    if isinstance(customer, dict):
        data = {
            "name": _display_value(customer.get("name")),
            "email": _display_value(customer.get("email")),
            "gstin": (customer.get("gstin") or "").strip(),
            "state": customer.get("state", ""),
            "state_code": customer.get("state_code", ""),
            "address": _display_value(customer.get("address")),
            "contact": _display_value(customer.get("contact") or customer.get("phone", "")),
        }
    else:
        data = {
            "name": _display_value(_row_get(customer, 1, "")),
            "email": _display_value(_row_get(customer, 2, "")),
            "gstin": (_row_get(customer, 3, "") or "").strip(),
            "state": _row_get(customer, 4, ""),
            "address": _display_value(_row_get(customer, 5, "")),
            "contact": _display_value(_row_get(customer, 6, _row_get(customer, 5, ""))),
            "state_code": _row_get(customer, 7, ""),
        }
    data["state"], data["state_code"] = resolve_state_and_code(data.get("state"), data.get("state_code"), data["gstin"])
    data["state_display"] = _display_value(format_state_with_code(data["state"], data["state_code"]))
    data["gstin_display"] = data["gstin"] or "Unregistered"
    return data


def _normalize_company(company):
    if isinstance(company, dict):
        data = {
            "name": _display_value(company.get("name")),
            "gstin": (company.get("gstin") or "").strip(),
            "address": _display_value(company.get("address")),
            "logo_path": company.get("logo_path", ""),
            "email": _display_value(company.get("email")),
            "phone": _display_value(company.get("phone")),
            "bank_name": _display_value(company.get("bank_name")),
            "bank_account": _display_value(company.get("bank_account")),
            "ifsc_code": _display_value(company.get("ifsc_code") or company.get("bank_ifsc")),
            "state": company.get("state", ""),
            "state_code": company.get("state_code", ""),
            "upi_id": _display_value(company.get("upi_id")),
        }
    else:
        data = {
            "name": _display_value(_row_get(company, 1, "")),
            "gstin": (_row_get(company, 2, "") or "").strip(),
            "address": _display_value(_row_get(company, 3, "")),
            "logo_path": _row_get(company, 4, ""),
            "email": _display_value(_row_get(company, 5, "")),
            "phone": _display_value(_row_get(company, 6, "")),
            "bank_name": _display_value(_row_get(company, 8, "")),
            "bank_account": _display_value(_row_get(company, 9, "")),
            "ifsc_code": _display_value(_row_get(company, 10, "")),
            "state": _row_get(company, 11, ""),
            "state_code": _row_get(company, 12, ""),
            "upi_id": _display_value(_row_get(company, 13, "")),
        }
    data["state"], data["state_code"] = resolve_state_and_code(data.get("state"), data.get("state_code"), data["gstin"])
    data["state_display"] = _display_value(format_state_with_code(data["state"], data["state_code"]))
    data["account_number"] = data.get("bank_account", "-")
    data["ifsc"] = data.get("ifsc_code", "-")
    data["gstin_display"] = data["gstin"] or "Unregistered"
    return data


def _normalize_items(items):
    normalized = []
    for item in items or []:
        qty = _to_decimal(_row_get(item, "qty", _row_get(item, 3, 0)))
        price = _to_decimal(_row_get(item, "price", _row_get(item, 4, 0)))
        normalized.append(
            {
                "name": _display_value(_row_get(item, "name", _row_get(item, 2, ""))),
                "qty": qty,
                "qty_display": _format_quantity(qty),
                "price": price,
                "line_total": (qty * price).quantize(Decimal("0.01")),
                "hsn": _display_value(_row_get(item, "hsn", _row_get(item, 5, "998314")), "998314"),
                "tax_rate": _to_decimal(_row_get(item, "tax_rate", _row_get(item, 6, 18))),
                "unit_label": _display_value(_row_get(item, "unit_label", _row_get(item, "per", "Nos")), "Nos"),
            }
        )
    return normalized


def _build_tax_rows(invoice_data, items_data):
    if not items_data:
        return []

    # Aggregate one row per GST rate.
    taxable_by_rate = {}
    for item in items_data:
        rate = _to_decimal(item.get("tax_rate", 18))
        taxable = _to_decimal(item.get("line_total", 0))
        entry = taxable_by_rate.setdefault(
            rate,
            {"taxable_value": Decimal("0.00"), "hsn_values": set()},
        )
        entry["taxable_value"] += taxable
        if item.get("hsn") and item["hsn"] != "-":
            entry["hsn_values"].add(item["hsn"])

    rows = []
    for rate in sorted(taxable_by_rate.keys()):
        taxable_value = taxable_by_rate[rate]["taxable_value"].quantize(Decimal("0.01"))
        hsn_values = sorted(taxable_by_rate[rate]["hsn_values"])
        hsn = ", ".join(hsn_values) if hsn_values else (items_data[0]["hsn"] if items_data else "998314")

        if invoice_data["is_intra_state"]:
            cgst_rate = (rate / Decimal("2")).quantize(Decimal("0.01"))
            sgst_rate = (rate / Decimal("2")).quantize(Decimal("0.01"))
            igst_rate = Decimal("0.00")
            cgst_amount = (taxable_value * (cgst_rate / Decimal("100"))).quantize(Decimal("0.01"))
            sgst_amount = (taxable_value * (sgst_rate / Decimal("100"))).quantize(Decimal("0.01"))
            igst_amount = Decimal("0.00")
        else:
            cgst_rate = Decimal("0.00")
            sgst_rate = Decimal("0.00")
            igst_rate = rate.quantize(Decimal("0.01"))
            cgst_amount = Decimal("0.00")
            sgst_amount = Decimal("0.00")
            igst_amount = (taxable_value * (igst_rate / Decimal("100"))).quantize(Decimal("0.01"))

        rows.append(
            {
                "hsn": hsn,
                "rate": rate.quantize(Decimal("0.01")),
                "taxable_value": taxable_value,
                "cgst_rate": cgst_rate,
                "sgst_rate": sgst_rate,
                "igst_rate": igst_rate,
                "cgst_amount": cgst_amount,
                "sgst_amount": sgst_amount,
                "igst_amount": igst_amount,
                "amount": (cgst_amount + sgst_amount + igst_amount).quantize(Decimal("0.01")),
            }
        )
    return rows


def build_invoice_context(invoice, customer, items, company, pdf_mode=False):
    invoice_data = _normalize_invoice(invoice)
    company_data = _normalize_company(company)
    customer_data = _normalize_customer(customer)
    items_data = _normalize_items(items)
    tax_rows = _build_tax_rows(invoice_data, items_data)

    if company_data.get("logo_path") and company_data["logo_path"] != "-":
        company_data["logo_src"] = (
            _resolve_image_path(company_data["logo_path"])
            if pdf_mode
            else url_for("static", filename=f"uploads/{company_data['logo_path']}")
        )
    else:
        company_data["logo_src"] = ""

    document_title = "PROFORMA INVOICE" if invoice_data["invoice_type"] == "PI" else "TAX INVOICE"
    return {
        "invoice": invoice_data,
        "customer": customer_data,
        "items": items_data,
        "company": company_data,
        "tax_rows": tax_rows,
        "document_title": document_title,
        "declaration_text": "We declare that this invoice shows the actual price of the services described and that all particulars are true and correct.",
        "pdf_mode": pdf_mode,
        "format_money": _format_money,
        "format_quantity": _format_quantity,
    }


def generate_invoice_pdf(invoice, customer, items, company):
    context = build_invoice_context(invoice, customer, items, company, pdf_mode=True)
    invoice_number = context["invoice"]["invoice_number"] or "invoice"
    safe_invoice_number = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(invoice_number))
    file_path = os.path.join(tempfile.gettempdir(), f"{safe_invoice_number}.pdf")
    template = select_invoice_template(context["invoice"]["invoice_type"])
    html = render_template(template, **context)

    if _load_weasyprint():
        HTML(string=html, base_url=current_app.root_path).write_pdf(file_path)
        return file_path

    if PDFKIT_AVAILABLE:
        config = _pdfkit_configuration()
        if config:
            options = {
                "enable-local-file-access": None,
                "page-size": "A4",
                "margin-top": "8mm",
                "margin-bottom": "8mm",
                "margin-left": "8mm",
                "margin-right": "8mm",
                "dpi": 300,
                "encoding": "UTF-8",
                "print-media-type": None,
                "disable-smart-shrinking": None,
                "quiet": None,
            }
            pdfkit.from_string(html, file_path, configuration=config, options=options)
            return file_path

    if XHTML2PDF_AVAILABLE:
        with open(file_path, "wb") as pdf_file:
            pisa_status = pisa.CreatePDF(html, dest=pdf_file, link_callback=_xhtml2pdf_link_callback)
        if not pisa_status.err:
            return file_path

    raise RuntimeError(
        "No HTML-compatible PDF engine is available. "
        "Install WeasyPrint for the best print fidelity, or install wkhtmltopdf/pdfkit or xhtml2pdf."
    )
