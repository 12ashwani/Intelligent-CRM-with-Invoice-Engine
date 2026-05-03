from decimal import Decimal, ROUND_HALF_UP


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
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM company_settings LIMIT 1")
        row = cur.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cur.description]
        return dict(zip(columns, row))
        
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

        # Helper to convert any value to str or None
        def to_str_or_none(val):
            if val is None:
                return None
            # Convert Decimal, int, float, etc. to string
            return str(val)

        seller_state_name, seller_state_code = resolve_state_and_code(
            to_str_or_none(company.get("state")),
            to_str_or_none(company.get("state_code")),
            to_str_or_none(company.get("gstin")),
        )
        customer_state_name, customer_state_code = resolve_state_and_code(
            to_str_or_none(customer.get("state")),
            to_str_or_none(customer.get("state_code")),
            to_str_or_none(customer.get("gstin")),
        )
        place_of_supply_name, place_of_supply_code = split_place_of_supply(data.get("place_of_supply"))

        subtotal = Decimal("0.00")
        for item in items:
            qty = Decimal(str(item["qty"]))
            price = Decimal(str(item["price"]))
            discount = Decimal(str(item.get("discount", 0)))
            line_total = qty * price
            if discount > 0:
                line_total = line_total * (Decimal("1.00") - (discount / Decimal("100")))
            subtotal += line_total
        subtotal = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        seller_state = seller_state_name or seller_state_code
        buyer_state = place_of_supply_name or place_of_supply_code or customer_state_name or customer_state_code
        is_intra_state = self.tax.is_intra_state(seller_state, buyer_state)

        total_cgst = Decimal("0.00")
        total_sgst = Decimal("0.00")
        total_igst = Decimal("0.00")

        for item in items:
            qty = Decimal(str(item["qty"]))
            price = Decimal(str(item["price"]))
            discount = Decimal(str(item.get("discount", 0)))
            rate_percent = Decimal(str(item.get("tax_rate", 18)))
            line_total = qty * price
            if discount > 0:
                line_total = line_total * (Decimal("1.00") - (discount / Decimal("100")))
            line_total = line_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            line_tax = self.tax.calculate_tax_for_amount(line_total, rate_percent, is_intra_state)
            total_cgst += line_tax["cgst"]
            total_sgst += line_tax["sgst"]
            total_igst += line_tax["igst"]

        total_cgst = total_cgst.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_sgst = total_sgst.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_igst = total_igst.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_tax = (total_cgst + total_sgst + total_igst).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = (subtotal + total_tax).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        invoice_number = generate_invoice_number(invoice_type)
        total_in_words = number_to_words_indian(float(total))

        invoice_data = {
            "invoice_number": invoice_number,
            "invoice_type": invoice_type,
            "customer_id": customer_id,
            "lead_id": data.get("lead_id"),
            "subtotal": subtotal,
            "cgst": total_cgst,
            "sgst": total_sgst,
            "igst": total_igst,
            "cgst_rate": Decimal("0.09") if is_intra_state else Decimal("0.00"),
            "sgst_rate": Decimal("0.09") if is_intra_state else Decimal("0.00"),
            "igst_rate": Decimal("0.18") if not is_intra_state else Decimal("0.00"),
            "tax": total_tax,
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
            if "tax_rate" not in item or item["tax_rate"] in (None, ""):
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
                "amount": f"INR {float(row.get('total') or 0):,.2f}",
                "status": row.get("status") or "draft",
            }
            for row in recent
        ]
        return {"stats": stats, "monthly": monthly, "types": types, "recent_invoices": recent_invoices}
