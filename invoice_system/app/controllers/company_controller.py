import os
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request
from app.db_compat import DictCursor
from werkzeug.utils import secure_filename

from app import mysql
from app.utils.gst import resolve_state_and_code

company_bp = Blueprint("company", __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "static", "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_company_columns():
    cur = mysql.connection.cursor()
    try:
        cur.execute("SHOW COLUMNS FROM company_settings")
        return {row[0] for row in cur.fetchall()}
    finally:
        cur.close()


def get_company_settings_record():
    cur = mysql.connection.cursor(DictCursor)
    cur.execute("SELECT * FROM company_settings LIMIT 1")
    return cur.fetchone()


def _company_value(company, *keys, default=""):
    if not company:
        return default
    for key in keys:
        value = company.get(key)
        if value not in (None, ""):
            return value
    return default
# ==============================
# Company Settings Route
# ==============================

@company_bp.route("/company", methods=["GET", "POST"])
def company_settings():
    """View and update company settings. Handles logo upload and GSTIN-based state resolution.
    HERE WE CHECK IF THE REQUEST METHOD IS POST, THEN WE EXTRACT THE FORM DATA, HANDLE FILE UPLOADS, AND UPDATE OR INSERT INTO THE DATABASE AS NEEDED. WE ALSO RESOLVE THE STATE NAME AND CODE BASED ON THE GSTIN OR PROVIDED VALUES. IF THERE ARE ANY ERRORS DURING DATABASE OPERATIONS, WE ROLLBACK AND FLASH AN ERROR MESSAGE."""
    cur = mysql.connection.cursor()

    if request.method == "POST":
        name = request.form["name"]
        gstin = request.form["gstin"]
        address = request.form["address"]
        email = request.form.get("email", "")
        phone = request.form.get("phone", "")
        state_name, state_code = resolve_state_and_code(request.form.get("state"), request.form.get("state_code"), gstin)
        bank_account = request.form.get("bank_account", "")
        bank_name = request.form.get("bank_name", "")
        ifsc_code = request.form.get("ifsc_code", "")
        columns = get_company_columns()

        file = request.files.get("logo")
        filename = None

        if file and file.filename and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            name_part, ext = os.path.splitext(original_filename)
            filename = f"{name_part}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
            file.save(os.path.join(UPLOAD_FOLDER, filename))

        existing = get_company_settings_record()

        try:
            payload = {
                "name": name,
                "gstin": gstin,
                "address": address,
                "email": email,
                "phone": phone,
                "logo_path": filename,
                "bank_account": bank_account,
                "bank_name": bank_name,
                "ifsc_code": ifsc_code,
                "bank_ifsc": ifsc_code,
                "state": state_name,
                "state_code": state_code,
            }
            if existing:
                assignments = []
                values = []
                for column, value in payload.items():
                    if column in columns:
                        assignments.append(f"{column}=%s")
                        values.append(value if column != "logo_path" or value else existing.get("logo_path"))
                values.append(existing["id"])
                cur.execute(f"UPDATE company_settings SET {', '.join(assignments)} WHERE id=%s", tuple(values))
            else:
                insert_columns = [column for column in payload if column in columns]
                insert_values = [payload[column] for column in insert_columns]
                cur.execute(
                    f"INSERT INTO company_settings ({', '.join(insert_columns)}) VALUES ({', '.join(['%s'] * len(insert_columns))})",
                    tuple(insert_values),
                )
        except Exception as e:
            if "Unknown column" in str(e):
                try:
                    if existing:
                        cur.execute(
                            """
                            UPDATE company_settings
                            SET name=%s, gstin=%s, address=%s, logo_path=%s
                            WHERE id=%s
                            """,
                            (name, gstin, address, filename if filename else existing.get("logo_path"), existing["id"]),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO company_settings (name, gstin, address, logo_path)
                            VALUES (%s,%s,%s,%s)
                            """,
                            (name, gstin, address, filename),
                        )

                    flash(
                        "Settings saved, but bank details columns were not found in the database. Please run the migrations.",
                        "warning",
                    )
                except Exception as inner_error:
                    mysql.connection.rollback()
                    flash(f"Error saving company settings: {inner_error}", "danger")
                    return redirect("/company")
            else:
                mysql.connection.rollback()
                flash(f"Error saving company settings: {e}", "danger")
                return redirect("/company")

        mysql.connection.commit()
        flash("Company settings saved successfully.", "success")
        return redirect("/company")

    raw_company = get_company_settings_record()
    company = {
        "name": _company_value(raw_company, "name"),
        "gstin": _company_value(raw_company, "gstin"),
        "address": _company_value(raw_company, "address"),
        "logo_path": _company_value(raw_company, "logo_path"),
        "email": _company_value(raw_company, "email"),
        "phone": _company_value(raw_company, "phone"),
        "state": _company_value(raw_company, "state"),
        "state_code": _company_value(raw_company, "state_code"),
        "bank_name": _company_value(raw_company, "bank_name"),
        "bank_account": _company_value(raw_company, "bank_account"),
        "ifsc_code": _company_value(raw_company, "ifsc_code", "bank_ifsc"),
    } if raw_company else None

    return render_template("company/settings.html", company=company)
