from decimal import Decimal, ROUND_HALF_UP

from MySQLdb.cursors import DictCursor

from app import mysql
from app.repositories.customer_repo import CustomerRepo
from app.repositories.invoice_repo import InvoiceRepo
from app.services.number_generator import generate_invoice_number
from app.services.tax_service import TaxService
from app.utils.gst import resolve_state_and_code, split_place_of_supply
from app.utils.number_to_words import number_to_words_indian
from app.utils.validators import validate_invoice_payload


class InvoiceService:
    def __init__(self):
        self.repo = InvoiceRepo()
        self.tax = TaxService()
        self.customer_repo = CustomerRepo()

    def _get_company_settings(self):
        cur = mysql.connection.cursor(DictCursor)
        cur.execute("SELECT * FROM company_settings LIMIT 1")
        return cur.fetchone()

    def create_invoice(self, data):
        items = data["items"]
        invoice_type = data["invoice_type"]
        customer_id = data["customer_id"]

        customer = self.customer_repo.get_by_id(customer_id)
        if not customer:
            raise ValueError("Selected customer was not found.")

        company = self._get_company_settings()
        if not company:
            raise ValueError("Company settings are required before creating an invoice.")

        validation_errors = validate_invoice_payload(data, company, customer)
        if validation_errors:
            raise ValueError(" ".join(validation_errors))

        seller_state_name, seller_state_code = resolve_state_and_code(
            company.get("state"),
            company.get("state_code"),
            company.get("gstin"),
        )
        customer_state_name, customer_state_code = resolve_state_and_code(
            customer.get("state"),
            customer.get("state_code"),
            customer.get("gstin"),
        )
        place_of_supply_name, place_of_supply_code = split_place_of_supply(data.get("place_of_supply"))

        subtotal = sum(Decimal(str(item["qty"])) * Decimal(str(item["price"])) for item in items)
        subtotal = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        tax_data = self.tax.calculate_tax(
            subtotal,
            seller_state_name or seller_state_code,
            place_of_supply_name or place_of_supply_code or customer_state_name or customer_state_code,
        )
        total = (subtotal + tax_data["total_tax"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        invoice_number = generate_invoice_number(invoice_type)
        total_in_words = number_to_words_indian(float(total))

        invoice_data = {
            "invoice_number": invoice_number,
            "invoice_type": invoice_type,
            "customer_id": customer_id,
            "lead_id": data.get("lead_id"),
            "subtotal": subtotal,
            "cgst": tax_data["cgst"],
            "sgst": tax_data["sgst"],
            "igst": tax_data["igst"],
            "cgst_rate": tax_data["cgst_rate"],
            "sgst_rate": tax_data["sgst_rate"],
            "igst_rate": tax_data["igst_rate"],
            "tax": tax_data["total_tax"],
            "total": total,
            "po_number": data.get("po_number", ""),
            "place_of_supply": f"{place_of_supply_name} ({place_of_supply_code})",
            "payment_terms": data.get("payment_terms", "Net 30 days"),
            "due_date": data.get("due_date", None),
            "total_in_words": total_in_words,
            "invoice_date": data.get("invoice_date"),
        }

        default_hsn = data.get("hsn_code", "998314")
        for item in items:
            if "hsn" not in item or not item["hsn"]:
                item["hsn"] = default_hsn
            item["tax_rate"] = 18

        return self.repo.save(invoice_data, items)

    def get_invoice_details(self, invoice_id):
        return self.repo.get_full_invoice(invoice_id)

    def get_dashboard_data(self):
        stats = self.repo.get_dashboard_stats()
        monthly = self.repo.get_monthly_sales()
        types = self.repo.get_invoice_types()
        recent = self.repo.get_recent_invoices(limit=10)
        recent_invoices = [
            {
                "number": row.get("invoice_number"),
                "customer": row.get("customer_name"),
                "type": row.get("invoice_type"),
                "date": row.get("invoice_date"),
                "amount": f"₹ {float(row.get('total') or 0):,.2f}",
                "status": row.get("status") or "draft",
            }
            for row in recent
        ]
        return {"stats": stats, "monthly": monthly, "types": types, "recent_invoices": recent_invoices}
