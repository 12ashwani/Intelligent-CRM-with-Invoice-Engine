from app.db_compat import DictCursor

from app import mysql


class InvoiceRepo:
    def _get_columns(self, table_name):
        cur = mysql.connection.cursor()
        try:
            cur.execute(f"SHOW COLUMNS FROM {table_name}")
            return {row[0] for row in cur.fetchall()}
        finally:
            cur.close()

    def save(self, invoice, items):
        cur = mysql.connection.cursor()
        invoice_columns = self._get_columns("invoices")
        invoice_payload = {
            "invoice_number": invoice["invoice_number"],
            "invoice_type": invoice["invoice_type"],
            "customer_id": invoice["customer_id"],
            "lead_id": invoice.get("lead_id"),
            "subtotal": invoice["subtotal"],
            "tax_amount": invoice["tax"],
            "cgst": invoice["cgst"],
            "sgst": invoice["sgst"],
            "igst": invoice["igst"],
            "total": invoice["total"],
            "po_number": invoice.get("po_number", ""),
            "place_of_supply": invoice.get("place_of_supply", ""),
            "payment_terms": invoice.get("payment_terms", "Net 30 days"),
            "due_date": invoice.get("due_date", None),
            "total_in_words": invoice.get("total_in_words", ""),
            "created_at": invoice.get("invoice_date"),
        }
        ordered_invoice_columns = [column for column in invoice_payload if column in invoice_columns]
        invoice_sql = f"""
            INSERT INTO invoices ({", ".join(ordered_invoice_columns)})
            VALUES ({", ".join(["%s"] * len(ordered_invoice_columns))})
        """
        cur.execute(invoice_sql, tuple(invoice_payload[column] for column in ordered_invoice_columns))

        invoice_id = cur.lastrowid
        item_columns = self._get_columns("invoice_items")

        for item in items:
            item_payload = {
                "invoice_id": invoice_id,
                "name": item["name"],
                "qty": item["qty"],
                "price": item["price"],
                "hsn": item.get("hsn", "998314"),
                "tax_rate": item.get("tax_rate", 18),
            }
            ordered_item_columns = [column for column in item_payload if column in item_columns]
            item_sql = f"""
                INSERT INTO invoice_items ({", ".join(ordered_item_columns)})
                VALUES ({", ".join(["%s"] * len(ordered_item_columns))})
            """
            cur.execute(item_sql, tuple(item_payload[column] for column in ordered_item_columns))

        mysql.connection.commit()
        return {"invoice_id": invoice_id, "invoice_number": invoice["invoice_number"]}

    def get_all(self):
        cur = mysql.connection.cursor(DictCursor)
        cur.execute("SELECT * FROM invoices")
        return cur.fetchall()

    def get_full_invoice(self, invoice_id):
        cur = mysql.connection.cursor(DictCursor)
        cur.execute("SELECT * FROM invoices WHERE id=%s", (invoice_id,))
        invoice = cur.fetchone()
        if not invoice:
            return None

        cur.execute("SELECT * FROM customers WHERE id=%s", (invoice["customer_id"],))
        customer = cur.fetchone()

        cur.execute("SELECT * FROM invoice_items WHERE invoice_id=%s", (invoice_id,))
        items = cur.fetchall()

        return invoice, customer, items

    def delete(self, invoice_id):
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM invoice_items WHERE invoice_id=%s", (invoice_id,))
        cur.execute("DELETE FROM invoices WHERE id=%s", (invoice_id,))
        mysql.connection.commit()
        cur.close()

    def get_dashboard_stats(self):
        cur = mysql.connection.cursor()
        cur.execute("SELECT SUM(total) FROM invoices")
        total_revenue = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM invoices")
        total_invoices = cur.fetchone()[0]

        cur.execute("SELECT SUM(amount) FROM invoice_payments WHERE status='paid'")
        paid = cur.fetchone()[0] or 0
        pending = total_revenue - paid

        cur.execute("SELECT COUNT(*) FROM invoices WHERE LOWER(COALESCE(status, '')) = 'paid'")
        paid_invoices = cur.fetchone()[0] or 0

        cur.execute(
            """
            SELECT COUNT(*)
            FROM invoices
            WHERE COALESCE(LOWER(status), 'draft') NOT IN ('paid', 'draft')
              AND COALESCE(due_date, date) IS NOT NULL
              AND COALESCE(due_date, date) < CURDATE()
            """
        )
        overdue = cur.fetchone()[0] or 0

        return {
            "total_revenue": float(total_revenue),
            "total_invoices": total_invoices,
            "paid": float(paid),
            "pending": float(pending),
            "paid_invoices": paid_invoices,
            "overdue": overdue,
        }

    def get_monthly_sales(self):
        cur = mysql.connection.cursor()
        cur.execute(
            """
            SELECT MONTH(created_at), SUM(total)
            FROM invoices
            GROUP BY MONTH(created_at)
            ORDER BY MONTH(created_at)
            """
        )
        return cur.fetchall()

    def get_invoice_types(self):
        cur = mysql.connection.cursor()
        cur.execute(
            """
            SELECT invoice_type, COUNT(*)
            FROM invoices
            GROUP BY invoice_type
            """
        )
        return cur.fetchall()

    def get_recent_invoices(self, limit=10):
        cur = mysql.connection.cursor(DictCursor)
        cur.execute(
            """
            SELECT
                i.invoice_number,
                COALESCE(c.name, CONCAT('Customer #', i.customer_id)) AS customer_name,
                i.invoice_type,
                DATE_FORMAT(COALESCE(i.date, i.created_at), '%%Y-%%m-%%d') AS invoice_date,
                i.total,
                LOWER(COALESCE(i.status, 'draft')) AS status
            FROM invoices i
            LEFT JOIN customers c ON c.id = i.customer_id
            ORDER BY i.id DESC
            LIMIT %s
            """,
            (limit,),
        )
        return cur.fetchall()
