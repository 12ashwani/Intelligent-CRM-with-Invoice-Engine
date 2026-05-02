import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env", override=True)

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
    MYSQL_DB = os.getenv("MYSQL_DB", "invoice_db")
    APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT = int(os.getenv("APP_PORT", "5001"))
    CRM_URL = os.getenv("CRM_URL", "http://localhost:5000")
    ACCESS_TTL_SECONDS = int(os.getenv("INVOICE_ACCESS_TTL_SECONDS", "3600"))
    INVOICE_ACCESS_SECRET = os.getenv("INVOICE_ACCESS_SECRET", "invoice-access-secret")
