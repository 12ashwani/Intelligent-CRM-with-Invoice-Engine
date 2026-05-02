import subprocess
import sys
from pathlib import Path

# =====================================================
# Base Paths
# =====================================================

BASE_DIR = Path(__file__).resolve().parent

CRM_DIR = BASE_DIR / "crm"
AI_DIR = BASE_DIR / "ai_agent"
INVOICE_DIR = BASE_DIR / "invoice_system"


# =====================================================
# Validate Required Folders
# =====================================================

def validate_paths() -> None:
    for folder in [CRM_DIR, AI_DIR, INVOICE_DIR]:
        if not folder.exists():
            raise FileNotFoundError(f"Missing folder: {folder}")


# =====================================================
# Main Launcher
# =====================================================

def run_both() -> None:
    print("Starting CRM, Invoice System, and AI Agent...\n")

    print("CRM Path:", CRM_DIR)
    print("AI Path:", AI_DIR)
    print("Invoice Path:", INVOICE_DIR)
    print()

    validate_paths()

    crm = None
    invoice = None

    try:
        # ---------------------------------------------
        # Start CRM
        # ---------------------------------------------
        crm = subprocess.Popen(
            [sys.executable, "app.py"],
            cwd=str(CRM_DIR)
        )
        print("CRM started on http://localhost:5000")

        # ---------------------------------------------
        # Start Invoice
        # ---------------------------------------------
        invoice = subprocess.Popen(
            [sys.executable, "run.py"],
            cwd=str(INVOICE_DIR)
        )
        print("Invoice System started on http://localhost:5001")

        # ---------------------------------------------
        # Start AI Agent (IMPORTANT FIX)
        # Run as module from project root
        # ---------------------------------------------
        print("Starting AI Agent...\n")

        subprocess.run(
            [sys.executable, "-m", "ai_agent.main"],
            cwd=str(BASE_DIR)
        )

    except KeyboardInterrupt:
        print("\nInterrupted by user.")

    finally:
        print("\nStopping background services...")

        if crm and crm.poll() is None:
            crm.terminate()

        if invoice and invoice.poll() is None:
            invoice.terminate()

        print("CRM and Invoice System servers stopped.")


# =====================================================
# Entry Point
# =====================================================

if __name__ == "__main__":
    run_both()