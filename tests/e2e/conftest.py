"""End-to-end fixtures: 起 run_demo.py 后台、给 TestClient 全局用。"""
import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEMO_CMD = ["python", str(ROOT / "run_demo.py")]


@pytest.fixture(scope="session")
def demo_server():
    """Start run_demo.py on port 8000 once per session."""
    env = os.environ.copy()
    env.setdefault("AGNES_API_KEY", "demo-not-real-key")  # demo 数据库依然 seed
    proc = subprocess.Popen(
        DEMO_CMD,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )
    base = "http://localhost:8000"
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            import urllib.request
            urllib.request.urlopen(base + "/api/v1/health", timeout=2)
            break
        except Exception:
            time.sleep(0.5)
    else:
        proc.send_signal(signal.SIGTERM)
        raise RuntimeError("run_demo.py did not start within 30s")
    yield base
    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)