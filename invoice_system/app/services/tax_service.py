from decimal import Decimal, ROUND_HALF_UP

from app.utils.gst import resolve_state_and_code


class TaxService:
    GST_RATE = Decimal("0.18")
    HALF_GST_RATE = Decimal("0.09")

    def is_intra_state(self, seller_state, customer_state):
        _, seller_code = resolve_state_and_code(seller_state)
        _, customer_code = resolve_state_and_code(customer_state)
        return bool(seller_code and customer_code and seller_code == customer_code)

    def calculate_tax_for_amount(self, amount, rate_percent, is_intra_state):
        taxable_value = Decimal(str(amount or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        rate = Decimal(str(rate_percent or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) / Decimal("100")

        if is_intra_state:
            half_rate = (rate / Decimal("2")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            cgst = (taxable_value * half_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            sgst = (taxable_value * half_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            igst = Decimal("0.00")
            cgst_rate = half_rate
            sgst_rate = half_rate
            igst_rate = Decimal("0.00")
        else:
            cgst = Decimal("0.00")
            sgst = Decimal("0.00")
            igst = (taxable_value * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            cgst_rate = Decimal("0.00")
            sgst_rate = Decimal("0.00")
            igst_rate = rate

        return {
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "cgst_rate": cgst_rate,
            "sgst_rate": sgst_rate,
            "igst_rate": igst_rate,
            "total_tax": (cgst + sgst + igst).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "taxable_value": taxable_value,
            "is_intra_state": is_intra_state,
        }

    def calculate_tax(self, amount, seller_state, customer_state):
        taxable_value = Decimal(str(amount or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        is_intra_state = self.is_intra_state(seller_state, customer_state)

        if is_intra_state:
            cgst = (taxable_value * self.HALF_GST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            sgst = (taxable_value * self.HALF_GST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            igst = Decimal("0.00")
            cgst_rate = self.HALF_GST_RATE
            sgst_rate = self.HALF_GST_RATE
            igst_rate = Decimal("0.00")
        else:
            cgst = Decimal("0.00")
            sgst = Decimal("0.00")
            igst = (taxable_value * self.GST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            cgst_rate = Decimal("0.00")
            sgst_rate = Decimal("0.00")
            igst_rate = self.GST_RATE

        return {
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "cgst_rate": cgst_rate,
            "sgst_rate": sgst_rate,
            "igst_rate": igst_rate,
            "total_tax": (cgst + sgst + igst).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "taxable_value": taxable_value,
            "is_intra_state": is_intra_state,
        }
