import time
import os
import sys
from pathlib import Path

from flask import Flask, abort, redirect, request, session, url_for, render_template, flash
from app.config import Config
from app.db import mysql_db as mysql

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
from shared_sso import verify_sso_payload

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    mysql.init_app(app)

    protected_prefixes = ("/invoices", "/customers", "/payments", "/company")

    def _grant_accounts_access():
        username = request.args.get("user", "").strip()
        role = request.args.get("role", "").strip().lower()
        employee_id = request.args.get("employee_id", "").strip()
        issued_at_raw = request.args.get("ts", "").strip()
        signature = request.args.get("sig", "").strip()
        ttl_raw = request.args.get("ttl", "").strip() or str(app.config["ACCESS_TTL_SECONDS"])

        if not all([username, role, issued_at_raw, signature]):
            return False

        try:
            issued_at = int(issued_at_raw)
            ttl_seconds = int(ttl_raw)
        except ValueError:
            return False

        allowed_roles = {"admin", "manager", "accounts"}
        if role not in allowed_roles:
            return False

        if not verify_sso_payload(username, role, employee_id, issued_at, signature, ttl_seconds):
            return False

        session["invoice_access_role"] = role
        session["invoice_access_user"] = username
        session["invoice_access_employee_id"] = employee_id
        session["invoice_access_at"] = issued_at
        return True

    @app.before_request
    def enforce_accounts_access():
        if _grant_accounts_access():
            return None

        if request.endpoint == "static":
            return None

        # Development mode: automatically grant access to allow testing
        if app.config.get("ENV") == "development" or os.getenv("INVOICE_DEV_MODE", "false").lower() == "true":
            if not session.get("invoice_access_role"):
                session["invoice_access_role"] = "accounts"
                session["invoice_access_user"] = "dev-user"
                session["invoice_access_at"] = int(time.time())
            return None

        if request.path == "/":
            if session.get("invoice_access_role") == "accounts":
                return redirect(url_for("invoice.invoice_ui"))
            return abort(403)

        if request.path.startswith(protected_prefixes):
            if session.get("invoice_access_role") != "accounts":
                return abort(403)

            if not request.path.startswith("/company"):
                try:
                    cur = mysql.connection.cursor()
                    cur.execute("SELECT id FROM company_settings LIMIT 1")
                    company_exists = cur.fetchone() is not None
                except Exception:
                    company_exists = True

                if not company_exists:
                    flash("Complete company setup before using invoice management.", "warning")
                    return redirect(url_for("company.company_settings"))

    from app.controllers.invoice_controller import invoice_bp
    from app.controllers.customer_controller import customer_bp
    from app.controllers.payment_controller import payment_bp
    from app.controllers.company_controller import company_bp

    @app.context_processor
    def inject_crm_url():
        return {"CRM_URL": app.config.get("CRM_URL", "http://localhost:5000")}

    @app.route("/")
    def index():
        """Main dashboard for invoice system"""
        if not session.get("invoice_access_role"):
            session["invoice_access_role"] = "accounts"
            session["invoice_access_user"] = "dev-user"
        portal_data = {"stats": {}, "recent_invoices": []}
        try:
            from app.services.invoice_service import InvoiceService

            portal_data = InvoiceService().get_dashboard_data()
        except Exception:
            # Keep home page available even if analytics query fails.
            portal_data = {"stats": {}, "recent_invoices": []}
        return render_template("invoice_portal.html", portal=portal_data)

    app.register_blueprint(invoice_bp, url_prefix="/invoices")
    app.register_blueprint(customer_bp, url_prefix="/customers")
    app.register_blueprint(payment_bp, url_prefix="/payments")
    app.register_blueprint(company_bp)

    return app
