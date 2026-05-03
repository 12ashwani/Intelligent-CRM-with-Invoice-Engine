from app.db_compat import DictCursor

from app import mysql

class CustomerRepo:
    def _get_customer_columns(self):
        cur = mysql.connection.cursor()
        try:
            cur.execute("SHOW COLUMNS FROM customers")
            return {row[0] for row in cur.fetchall()}
        finally:
            cur.close()

    def _build_customer_insert(self, data):
        available_columns = self._get_customer_columns()
        requested_values = {
            "name": data.get("name", ""),
            "email": data.get("email", ""),
            "gstin": data.get("gstin", ""),
            "state": data.get("state", ""),
            "state_code": data.get("state_code", ""),
            "address": data.get("address", ""),
        }

        contact_value = data.get("contact", "")
        if "contact" in available_columns:
            requested_values["contact"] = contact_value
        elif "phone" in available_columns:
            requested_values["phone"] = contact_value

        columns = [column for column in requested_values if column in available_columns]
        placeholders = ", ".join(["%s"] * len(columns))
        values = tuple(requested_values[column] for column in columns)
        sql = f"INSERT INTO customers ({', '.join(columns)}) VALUES ({placeholders})"
        return sql, values

    def create(self, data):
        cur = mysql.connection.cursor()
        sql, values = self._build_customer_insert(data)
        cur.execute(sql, values)
        mysql.connection.commit()
        return {"message": "Customer created"}

    def get_all(self):
        cur = mysql.connection.cursor(DictCursor)
        cur.execute("SELECT * FROM customers")
        return cur.fetchall()

    def get_by_id(self, customer_id):
        cur = mysql.connection.cursor(DictCursor)
        cur.execute("SELECT * FROM customers WHERE id=%s", (customer_id,))
        return cur.fetchone()

    def delete(self, customer_id):
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM customers WHERE id = %s", (customer_id,))
        mysql.connection.commit()
        cur.close()

    def find_by_name_email(self, name, email=None):
        cur = mysql.connection.cursor(DictCursor)
        if email:
            cur.execute(
                "SELECT * FROM customers WHERE name=%s AND email=%s LIMIT 1",
                (name, email),
            )
        else:
            cur.execute(
                "SELECT * FROM customers WHERE name=%s LIMIT 1",
                (name,),
            )
        return cur.fetchone()

    def create_and_return_id(self, data):
        cur = mysql.connection.cursor()
        sql, values = self._build_customer_insert(data)
        cur.execute(sql, values)
        mysql.connection.commit()
        return cur.lastrowid
