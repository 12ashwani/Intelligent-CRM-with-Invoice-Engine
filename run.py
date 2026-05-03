import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent


@dataclass
class ServiceSpec:
    name: str
    cwd: Path
    command: List[str]
    port: int
    health_url: str
    env: Dict[str, str] = field(default_factory=dict)
    process: Optional[subprocess.Popen] = None
    restarts: int = 0
    last_start: float = 0.0
    stop_requested: bool = False


def _stream_output(name: str, pipe):
    for line in iter(pipe.readline, ""):
        print(f"[{name}] {line.rstrip()}")


def _is_healthy(url: str, timeout: float = 2.0) -> bool:
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except Exception:
        return False


def _start_service(spec: ServiceSpec):
    env = os.environ.copy()
    env.update(spec.env)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    spec.last_start = time.time()
    spec.process = subprocess.Popen(
        spec.command,
        cwd=str(spec.cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    t = threading.Thread(target=_stream_output, args=(spec.name, spec.process.stdout), daemon=True)
    t.start()
    print(f"[supervisor] started {spec.name} pid={spec.process.pid} port={spec.port}")


def _stop_service(spec: ServiceSpec):
    if not spec.process or spec.process.poll() is not None:
        return
    spec.stop_requested = True
    spec.process.terminate()
    try:
        spec.process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        spec.process.kill()


def build_services() -> List[ServiceSpec]:
    python = sys.executable
    return [
        ServiceSpec(
            name="crm",
            cwd=BASE_DIR / "crm",
            command=[python, "app.py"],
            port=5000,
            health_url="http://127.0.0.1:5000/test-app",
            env={"APP_PORT": "5000", "FLASK_DEBUG": "false"},
        ),
        ServiceSpec(
            name="invoice",
            cwd=BASE_DIR / "invoice_system",
            command=[python, "run.py"],
            port=5001,
            health_url="http://127.0.0.1:5001/",
            env={"APP_PORT": "5001"},
        ),
        ServiceSpec(
            name="ai_agent",
            cwd=BASE_DIR,
            command=[python, "-m", "ai_agent.server"],
            port=5002,
            health_url="http://127.0.0.1:5002/health",
            env={"AI_PORT": "5002"},
        ),
    ]


def validate_layout(services: List[ServiceSpec]):
    missing = [str(spec.cwd) for spec in services if not spec.cwd.exists()]
    if missing:
        raise FileNotFoundError(f"Missing service directories: {', '.join(missing)}")


def main():
    services = build_services()
    validate_layout(services)
    running = True

    def shutdown_handler(_sig, _frm):
        nonlocal running
        running = False
        print("[supervisor] shutdown signal received")

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    for spec in services:
        _start_service(spec)

    try:
        while running:
            for spec in services:
                proc = spec.process
                if not proc:
                    continue
                if proc.poll() is not None and not spec.stop_requested:
                    spec.restarts += 1
                    backoff = min(2 * spec.restarts, 20)
                    print(f"[supervisor] {spec.name} exited code={proc.returncode}; restarting in {backoff}s")
                    time.sleep(backoff)
                    spec.stop_requested = False
                    _start_service(spec)
                    continue

                if not _is_healthy(spec.health_url):
                    # do not restart too quickly after fresh start
                    if time.time() - spec.last_start > 10:
                        print(f"[supervisor] unhealthy: {spec.name}; restarting")
                        _stop_service(spec)
                        spec.stop_requested = False
                        spec.restarts += 1
                        _start_service(spec)
            time.sleep(3)
    finally:
        for spec in services:
            _stop_service(spec)
        print("[supervisor] all services stopped")


if __name__ == "__main__":
    main()
