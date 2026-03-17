from __future__ import annotations

import subprocess
import sys
import threading
import webbrowser
import socket
import os
from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"
FRONTEND_SRC = FRONTEND_DIR / "src"
PACKAGE_JSON = FRONTEND_DIR / "package.json"
PACKAGE_LOCK = FRONTEND_DIR / "package-lock.json"
NODE_MODULES = FRONTEND_DIR / "node_modules"
SYNC_SCRIPT = ROOT / "scripts" / "sync_converted_bundle.py"
CONVERTED_MENTORS = ROOT / "data_raw" / "converted" / "mentors.csv"
CONVERTED_SCENARIO = ROOT / "data_raw" / "converted" / "scenario.json"


def run_command(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def needs_frontend_build() -> bool:
    index_path = FRONTEND_DIST / "index.html"
    if not index_path.exists():
        return True
    dist_mtime = index_path.stat().st_mtime
    watched = [PACKAGE_JSON, PACKAGE_LOCK]
    watched.extend(path for path in FRONTEND_SRC.rglob("*") if path.is_file())
    return any(path.exists() and path.stat().st_mtime > dist_mtime for path in watched)


def sync_converted_bundle_if_needed() -> None:
    if not (CONVERTED_MENTORS.exists() and CONVERTED_SCENARIO.exists() and SYNC_SCRIPT.exists()):
        return
    if CONVERTED_MENTORS.stat().st_mtime > CONVERTED_SCENARIO.stat().st_mtime:
        run_command([sys.executable, str(SYNC_SCRIPT)], cwd=ROOT)


def ensure_frontend_ready() -> None:
    if not PACKAGE_JSON.exists():
        return
    if not NODE_MODULES.exists():
        run_command(["npm", "install"], cwd=FRONTEND_DIR)
    if needs_frontend_build():
        run_command(["npm", "run", "build"], cwd=FRONTEND_DIR)


def open_browser_later(url: str) -> None:
    def _open() -> None:
        webbrowser.open(url)

    threading.Timer(1.0, _open).start()


def find_available_port(preferred: int = 8000, attempts: int = 20) -> int:
    for port in range(preferred, preferred + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"Could not find a free port in range {preferred}-{preferred + attempts - 1}.")


def terminate_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def main_dev() -> None:
    sync_converted_bundle_if_needed()
    if not PACKAGE_JSON.exists():
        raise FileNotFoundError(f"Missing frontend package manifest: {PACKAGE_JSON}")
    if not NODE_MODULES.exists():
        run_command(["npm", "install"], cwd=FRONTEND_DIR)

    api_port = find_available_port(8000)
    frontend_port = find_available_port(5173)
    env = os.environ.copy()
    env["VITE_API_BASE_URL"] = f"http://127.0.0.1:{api_port}"

    backend_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
        ],
        cwd=ROOT,
    )
    frontend_process = None
    try:
        frontend_process = subprocess.Popen(
            [
                "npm",
                "run",
                "dev",
                "--",
                "--host",
                "127.0.0.1",
                "--port",
                str(frontend_port),
            ],
            cwd=FRONTEND_DIR,
            env=env,
        )
        url = f"http://127.0.0.1:{frontend_port}"
        print(
            f"Starting Mentor Group Optimizer dev mode at {url} "
            f"(API: http://127.0.0.1:{api_port})"
        )
        open_browser_later(url)
        frontend_process.wait()
    except KeyboardInterrupt:
        pass
    finally:
        terminate_process(frontend_process)
        terminate_process(backend_process)


def main() -> None:
    sync_converted_bundle_if_needed()
    ensure_frontend_ready()
    port = find_available_port()
    url = f"http://127.0.0.1:{port}"
    print(f"Starting Mentor Group Optimizer at {url}")
    open_browser_later(url)
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=port, reload=False)


if __name__ == "__main__":
    main()
