"""Database adapter for mysql-connector-python compatibility with flask-mysqldb interface"""
import mysql.connector
from mysql.connector import Error
from flask import g

class MySQLConnection:
    """Wrapper to mimic flask-mysqldb cursor interface"""
    
    def __init__(self, app=None):
        self.app = app
        self._connection = None
    
    def init_app(self, app):
        self.app = app
        self.app.teardown_appcontext(self._close_connection)
    
    def _close_connection(self, exception=None):
        if hasattr(g, 'mysql_connection'):
            try:
                g.mysql_connection.close()
            except:
                pass
            delattr(g, 'mysql_connection')
    
    def _get_connection(self):
        if not hasattr(g, 'mysql_connection'):
            try:
                g.mysql_connection = mysql.connector.connect(
                    host=self.app.config.get('MYSQL_HOST', 'localhost'),
                    user=self.app.config.get('MYSQL_USER', 'root'),
                    password=self.app.config.get('MYSQL_PASSWORD', ''),
                    database=self.app.config.get('MYSQL_DB', ''),
                    autocommit=False
                )
            except Error as e:
                raise Exception(f"Error connecting to MySQL: {e}")
        return g.mysql_connection
    
    @property
    def connection(self):
        """Return the connection object with custom cursor method"""
        conn = self._get_connection()
        
        # Add custom cursor method if not already present
        if not hasattr(conn, '_custom_cursor'):
            original_cursor = conn.cursor
            
            def custom_cursor(cursor_class=None):
                """Create a cursor, optionally as a dictionary cursor"""
                if cursor_class is not None and hasattr(cursor_class, '__name__') and cursor_class.__name__ == 'DictCursor':
                    return original_cursor(dictionary=True)
                elif cursor_class is None:
                    return original_cursor()
                else:
                    return original_cursor()
            
            conn.cursor = custom_cursor
            conn._custom_cursor = True
        
        return conn


# Create instance for import
mysql_db = MySQLConnection()
