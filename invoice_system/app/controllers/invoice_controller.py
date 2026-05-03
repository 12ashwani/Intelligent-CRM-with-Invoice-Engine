from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from app.db_compat import DictCursor
from datetime import date
from flask import jsonify
from app import mysql
from app.repositories.customer_repo import CustomerRepo
from app.services.invoice_service import InvoiceService
from app.utils.gst import resolve_state_and_code, validate_address_pincode, validate_place_of_supply_format
from app.utils.pdf_generator import build_invoice_context, generate_invoice_pdf, select_invoice_template

invoice_bp = Blueprint("invoice", __name__)
service = InvoiceService()
customer_repo = CustomerRepo()
# ========================================
# Invoice routes and logic
# ========================================
def get_cursor(cursor_class=None):
    """ Helper to get a MySQL cursor, optionally as a DictCursor. Returns a tuple of (cursor, is_dict). """
    try:
        if cursor_class:
            return mysql.connection.cursor(cursor_class), True
        return mysql.connection.cursor(), False
    except TypeError:
        return mysql.connection.cursor(), False

# =================================
# Helper functions
# ================================
def fetchall_dict(cur):
    """ Helper to convert cursor results to list of dicts."""
    columns = [col[0] for col in cur.description] if cur.description else []
    return [dict(zip(columns, row)) for row in cur.fetchall()]

# ================================
# Invoice UI routes
# ================================

def fetchone_dict(cur):
    """ Helper to convert a single cursor result to a dict."""
    row = cur.fetchone()
    if row is None:
        return None
    columns = [col[0] for col in cur.description]
    return dict(zip(columns, row))


def get_company_settings():
    cur, use_dict = get_cursor(DictCursor)
    cur.execute("SELECT * FROM company_settings LIMIT 1")
    return cur.fetchone() if use_dict else fetchone_dict(cur)


def get_table_columns(table_name):
    cur = mysql.connection.cursor()
    cur.execute(f"SHOW COLUMNS FROM {table_name}")
    return {row[0] for row in cur.fetchall()}

# ================================
# Invoice UI routes
# ================================
@invoice_bp.route("/ui")
def invoice_ui():
    cur = mysql.connection.cursor(DictCursor)
    cur.execute(
        """
        SELECT
            i.*,
            DATE_FORMAT(i.date, '%%Y-%%m-%%d') AS invoice_date_iso,
            DATE_FORMAT(i.due_date, '%%Y-%%m-%%d') AS due_date_iso,
            c.name AS customer_name,
            c.gstin AS customer_gstin,
            COALESCE(SUM(CASE WHEN ip.status = 'paid' THEN ip.amount ELSE 0 END), 0) AS amount_paid
        FROM invoices i
        LEFT JOIN customers c ON c.id = i.customer_id
        LEFT JOIN invoice_payments ip ON ip.invoice_id = i.id
        GROUP BY i.id
        ORDER BY i.id DESC
        """
    )
    invoices = cur.fetchall()

    company = get_company_settings()

    return render_template(
        "invoices/list.html",
        invoices=invoices,
        company=company,
        now_date=date.today().isoformat()

    )
# ================================
# API route to fetch customer details by ID (used for dynamic form population in invoice creation)
# ================================

@invoice_bp.route("/api/customer/<int:customer_id>")
def get_customer_api(customer_id):
    cur = mysql.connection.cursor(DictCursor)
    cur.execute("SELECT * FROM customers WHERE id = %s", (customer_id,))
    customer = cur.fetchone()
    if not customer:
        return jsonify({})
    payload = dict(customer)
    payload["contact"] = payload.get("contact") or payload.get("phone") or ""
    payload["state_code"] = payload.get("state_code") or ""
    return jsonify(payload)


@invoice_bp.route("/api/lead/<int:lead_id>")
def get_lead_api(lead_id):
    customer_columns = get_table_columns("customers")
    has_state_code = "state_code" in customer_columns
    state_code_select = "c.state_code" if has_state_code else "'' AS state_code"
    cur = mysql.connection.cursor(DictCursor)
    cur.execute(
        f"""
        SELECT
            l.id,
            l.company_name,
            l.email,
            l.auth_person_name,
            l.auth_person_number,
            l.auth_person_email,
            l.service,
            l.status,
            c.id AS customer_id,
            c.gstin,
            c.address,
            c.state,
            {state_code_select},
            COALESCE(c.contact, c.phone, '') AS customer_contact
        FROM leads l
        LEFT JOIN customers c
            ON c.name = l.company_name
           AND (
                (c.email IS NOT NULL AND c.email <> '' AND (c.email = l.auth_person_email OR c.email = l.email))
                OR (c.email IS NULL OR c.email = '')
           )
        WHERE l.id = %s
        ORDER BY c.id DESC
        LIMIT 1
        """,
        (lead_id,),
    )
    lead = cur.fetchone()
    if not lead:
        return jsonify({})
    return jsonify(
        {
            "id": lead.get("id"),
            "company_name": lead.get("company_name") or "",
            "email": lead.get("auth_person_email") or lead.get("email") or "",
            "contact_person": lead.get("auth_person_name") or "",
            "contact": lead.get("auth_person_number") or lead.get("customer_contact") or "",
            "service": lead.get("service") or "",
            "status": lead.get("status") or "",
            "gstin": lead.get("gstin") or "",
            "address": lead.get("address") or "",
            "state": lead.get("state") or "",
            "state_code": lead.get("state_code") or "",
            "customer_id": lead.get("customer_id"),
        }
    )
# ================================
# Invoice creation UI
# ================================
@invoice_bp.route("/create-ui", methods=["GET", "POST"])
def create_invoice_ui():
    """ UI for creating a new invoice. On GET, shows form with customers and CRM leads. On POST, validates input and creates invoice."""
    company = get_company_settings()
    company_state_name = ""
    if not company:
        flash("Company settings are missing. You can fill form, but invoice creation needs company setup.", "warning")
    else:
        company_state_name, _ = resolve_state_and_code(
            company.get("state"),
            company.get("state_code"),
            company.get("gstin"),
        )

    cur, use_dict = get_cursor(DictCursor)
    cur.execute("SELECT * FROM customers")
    customers = cur.fetchall() if use_dict else fetchall_dict(cur)
    cur.execute(
        """
        SELECT
            id,
            company_name,
            email,
            auth_person_name,
            auth_person_number,
            auth_person_email,
            service,
            status
        FROM leads
        ORDER BY id DESC
        """
    )
    crm_leads = cur.fetchall() if use_dict else fetchall_dict(cur)
    selected_lead_id = request.args.get("lead_id", type=int)
    selected_lead = next((lead for lead in crm_leads if lead["id"] == selected_lead_id), None)

    if request.method == "POST":
        names = request.form.getlist("name[]")
        qtys = request.form.getlist("qty[]")
        prices = request.form.getlist("price[]")
        sacs = request.form.getlist("sac[]")
        discounts = request.form.getlist("discount[]")
        tax_rates = request.form.getlist("tax_rate[]")

        items = []
        for i in range(len(names)):
            item_name = (names[i] or "").strip()
            qty_raw = (qtys[i] or "").strip()
            price_raw = (prices[i] or "").strip()
            sac_raw = (sacs[i] or "").strip() if i < len(sacs) else ""
            discount_raw = (discounts[i] or "").strip() if i < len(discounts) else "0"
            tax_rate_raw = (tax_rates[i] or "").strip() if i < len(tax_rates) else "18"

            if not item_name and not qty_raw and not price_raw and not sac_raw:
                continue

            if not item_name or not qty_raw or not price_raw or not sac_raw:
                flash("Each invoice item must include a description, SAC, quantity, and rate.", "warning")
                return render_template(
                    "invoices/create.html",
                    customers=customers,
                    crm_leads=crm_leads,
                    selected_lead=selected_lead,
                    company_state=company_state_name,
                )

            try:
                qty = int(qty_raw)
                price = float(price_raw)
                discount = float(discount_raw or 0)
                tax_rate = float(tax_rate_raw or 0)
            except ValueError:
                flash("Please enter valid numeric values for quantity, price, discount, and GST rate.", "warning")
                return render_template(
                    "invoices/create.html",
                    customers=customers,
                    crm_leads=crm_leads,
                    selected_lead=selected_lead,
                    company_state=company_state_name,
                )

            if discount < 0 or discount > 100:
                flash("Discount must be between 0 and 100.", "warning")
                return render_template(
                    "invoices/create.html",
                    customers=customers,
                    crm_leads=crm_leads,
                    selected_lead=selected_lead,
                    company_state=company_state_name,
                )

            if tax_rate < 0 or tax_rate > 100:
                flash("GST rate must be between 0 and 100.", "warning")
                return render_template(
                    "invoices/create.html",
                    customers=customers,
                    crm_leads=crm_leads,
                    selected_lead=selected_lead,
                    company_state=company_state_name,
                )

            items.append({
                "name": item_name,
                "qty": qty,
                "price": price,
                "hsn": sac_raw,
                "discount": discount,
                "tax_rate": tax_rate,
            })

        if not items:
            flash("Add at least one invoice item.", "warning")
            return render_template(
                "invoices/create.html",
                customers=customers,
                crm_leads=crm_leads,
                selected_lead=selected_lead,
                company_state=company_state_name,
            )

        customer_id = request.form.get("customer_id", type=int)

        if not customer_id:
            customer_name = (request.form.get("customer_name") or "").strip()
            customer_email = (request.form.get("customer_email") or "").strip()
            customer_contact = (request.form.get("customer_contact") or "").strip()
            customer_gstin = (request.form.get("customer_gstin") or "").strip()
            customer_address = (request.form.get("customer_address") or "").strip()
            customer_state = (request.form.get("customer_state") or "").strip()
            customer_state_name, customer_state_code = resolve_state_and_code(
                customer_state,
                request.form.get("customer_state_code"),
                customer_gstin,
            )

            # Validate customer address contains PIN code
            if not validate_address_pincode(customer_address):
                flash("Customer address must include a valid 6-digit PIN code.", "warning")
                return render_template(
                    "invoices/create.html",
                    customers=customers,
                    crm_leads=crm_leads,
                    selected_lead=selected_lead,
                    company_state=company_state_name,
                )

            if not customer_name:
                flash("Customer name is required.", "warning")
                return render_template(
                    "invoices/create.html",
                    customers=customers,
                    crm_leads=crm_leads,
                    selected_lead=selected_lead,
                    company_state=company_state_name,
                )

            if not customer_state:
                flash("Customer state is required.", "warning")
                return render_template(
                    "invoices/create.html",
                    customers=customers,
                    crm_leads=crm_leads,
                    selected_lead=selected_lead,
                    company_state=company_state_name,
                )

            existing_customer = customer_repo.find_by_name_email(customer_name, customer_email or None)
            if existing_customer:
                customer_id = existing_customer["id"]
            else:
                customer_id = customer_repo.create_and_return_id(
                    {
                        "name": customer_name,
                        "email": customer_email,
                        "gstin": customer_gstin,
                        "address": customer_address,
                        "contact": customer_contact,
                        "state": customer_state_name,
                        "state_code": customer_state_code,
                    }
                )

        invoice_type = (request.form.get("invoice_type") or "").strip().upper()
        if invoice_type not in ("PI", "TAX"):
            flash("Please select a valid invoice type.", "warning")
            return render_template(
                "invoices/create.html",
                customers=customers,
                crm_leads=crm_leads,
                selected_lead=selected_lead,
                company_state=company_state_name,
            )

        data = {
            "customer_id": customer_id,
            "lead_id": request.form.get("crm_lead_id", type=int),
            "invoice_type": invoice_type,
            "items": items,
            "po_number": request.form.get("po_number", "").strip(),
            "place_of_supply": request.form.get("place_of_supply", "").strip(),
            "payment_terms": request.form.get("payment_terms", "").strip(),
            "due_date": request.form.get("due_date", "").strip(),
            "invoice_date": request.form.get("invoice_date", "").strip(),
            "hsn_code": request.form.get("hsn_code", "").strip(),
        }

        # Validate place of supply format
        if not validate_place_of_supply_format(data["place_of_supply"]):
            flash("Place of supply must be in format 'State Name (Code)', e.g., 'Maharashtra (27)'.", "warning")
            return render_template(
                "invoices/create.html",
                customers=customers,
                crm_leads=crm_leads,
                selected_lead=selected_lead,
                company_state=company_state_name,
            )

        try:
            service.create_invoice(data)
        except ValueError as ex:
            flash(str(ex), "danger")
            return render_template(
                "invoices/create.html",
                customers=customers,
                crm_leads=crm_leads,
                selected_lead=selected_lead,
                company_state=company_state_name,
            )
        except Exception as ex:
            flash("Unable to create invoice. " + str(ex), "danger")
            return render_template(
                "invoices/create.html",
                customers=customers,
                crm_leads=crm_leads,
                selected_lead=selected_lead,
                company_state=company_state_name,
            )

        return redirect(url_for("invoice.invoice_ui"))

    return render_template(
        "invoices/create.html",
        customers=customers,
        crm_leads=crm_leads,
        selected_lead=selected_lead,
        company_state=company_state_name,
    )

# ================================
# Additional invoice-related routes (e.g. dashboard, PDF download)
# ================================
@invoice_bp.route("/dashboard")
def dashboard():
    """ Example dashboard route that aggregates data for display."""
    data = service.get_dashboard_data()
    return render_template("dashboard.html", data=data)
# ================================
# Additional invoice-related routes (e.g. dashboard, PDF download)
# ================================
@invoice_bp.route("/<int:invoice_id>/view")
def view_invoice(invoice_id):
    """ Route to view an invoice in HTML format in the browser."""
    details = service.get_invoice_details(invoice_id)
    if not details:
        flash("Invoice not found.", "danger")
        return redirect(url_for("invoice.invoice_ui"))

    invoice, customer, items = details

    # Get company details
    if not mysql.connection:
        flash("Database connection not available.", "danger")
        return redirect(url_for("invoice.invoice_ui"))

    company = get_company_settings()
    if not company:
        flash("Please complete company setup before viewing invoices.", "warning")
        return redirect(url_for("company.company_settings"))

    context = build_invoice_context(invoice, customer, items, company, pdf_mode=False)
    template_name = select_invoice_template(context["invoice"]["invoice_type"])
    return render_template(template_name, **context)

@invoice_bp.route("/<int:invoice_id>/pdf")
def download_invoice(invoice_id):
    """ Route to download the PDF version of an invoice. Fetches invoice details and company info, generates PDF, and sends it as a file download."""
    details = service.get_invoice_details(invoice_id)
    if not details:
        flash("Invoice not found.", "danger")
        return redirect(url_for("invoice.invoice_ui"))

    invoice, customer, items = details

    # Get company details
    if not mysql.connection:
        flash("Database connection not available.", "danger")
        return redirect(url_for("invoice.invoice_ui"))

    company = get_company_settings()
    if not company:
        flash("Please complete company setup before downloading invoices.", "warning")
        return redirect(url_for("company.company_settings"))

    try:
        file_path = generate_invoice_pdf(invoice, customer, items, company)
    except Exception as ex:
        flash(f"Unable to generate invoice PDF: {ex}", "danger")
        return redirect(url_for("invoice.invoice_ui"))

    invoice_number = invoice["invoice_number"] if isinstance(invoice, dict) else invoice[1]
    return send_file(file_path, as_attachment=True, download_name=f"{invoice_number}.pdf")

@invoice_bp.route("/<int:invoice_id>/delete", methods=["POST"])
def delete_invoice(invoice_id):
    """ Route to delete an invoice and its associated items."""
    try:
        from app.repositories.invoice_repo import InvoiceRepo
        invoice_repo = InvoiceRepo()
        invoice_repo.delete(invoice_id)
        flash("Invoice deleted successfully.", "success")
    except Exception as ex:
        flash(f"Unable to delete invoice: {ex}", "danger")
    
    return redirect(url_for("invoice.invoice_ui"))
