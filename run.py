import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CRM_DIR = BASE_DIR / "crm"
AI_DIR = BASE_DIR / "ai_agent"
INVOICE_DIR = BASE_DIR / "invoice_system"


def validate_paths() -> None:
    missing = [str(folder) for folder in (CRM_DIR, AI_DIR, INVOICE_DIR) if not folder.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required folders: {', '.join(missing)}")


def stop_process(process: subprocess.Popen | None) -> None:
    if not process or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def run_all() -> None:
    print("Starting CRM, Invoice System, and AI Agent...")
    validate_paths()

    crm_process = None
    invoice_process = None

    try:
        crm_process = subprocess.Popen([sys.executable, "app.py"], cwd=str(CRM_DIR))
        print("CRM started in background on http://localhost:5000")

        invoice_process = subprocess.Popen([sys.executable, "run.py"], cwd=str(INVOICE_DIR))
        print("Invoice System started in background on http://localhost:5001")

        print("Starting AI Agent...")
        subprocess.run([sys.executable, "-m", "ai_agent.main"], cwd=str(BASE_DIR))

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        stop_process(crm_process)
        stop_process(invoice_process)
        print("CRM and Invoice System servers stopped.")


if __name__ == "__main__":
    try:
        run_all()
    except KeyboardInterrupt:
        print("\nApplication terminated by user.")
    except Exception as error:
        print(f"\nAn error occurred: {error}")
