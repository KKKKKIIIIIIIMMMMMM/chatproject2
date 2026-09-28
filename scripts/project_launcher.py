"""Start/stop this Windows project's local UI and LINE bot.

Only the configured Neo4j container is started; it is never deleted. Runtime
logs/state stay in ignored .runtime/. Credentials remain in memory and .env.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
RUNTIME = ROOT / ".runtime"
STATE = RUNTIME / "launcher-state.json"
CONTAINER = "hybrid-rag-neo4j"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TUNNEL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.I)


def env_file() -> dict[str, str]:
    path = ROOT / ".env"
    if not path.is_file():
        raise RuntimeError("Missing .env. Copy .env.example and fill in your private LINE credentials.")
    values = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def http_json(url: str, *, method: str = "GET", token: str | None = None,
              payload: dict | None = None, timeout: int = 6) -> dict:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
    return json.loads(raw) if raw else {}


def healthy(url: str, *, identify: bool = False) -> bool:
    try:
        response = http_json(url, timeout=3)
        return bool(response.get("ok")) and (
            not identify or response.get("service") == "fitness-rag-line"
        )
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return False


def alive(pid: int, started: float) -> bool:
    try:
        import psutil  # Already present in this project's Windows environment.
        process = psutil.Process(pid)
        return process.is_running() and abs(process.create_time() - started) < 2
    except (ImportError, OSError, ValueError):
        return False
    except Exception:  # psutil.NoSuchProcess, AccessDenied, ZombieProcess
        return False


def read_state() -> dict:
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    RUNTIME.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def launch(name: str, argv: list[str], env: dict[str, str], state: dict) -> None:
    import psutil
    RUNTIME.mkdir(exist_ok=True)
    record = state.get(name, {})
    if alive(record.get("pid", -1), record.get("started", -1)):
        return
    stdout_path = RUNTIME / f"{name}.out.log"
    stderr_path = RUNTIME / f"{name}.err.log"
    with stdout_path.open("a", encoding="utf-8") as stdout, stderr_path.open("a", encoding="utf-8") as stderr:
        proc = subprocess.Popen(
            argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
            stdout=stdout, stderr=stderr, creationflags=CREATE_NO_WINDOW,
        )
    state[name] = {"pid": proc.pid, "started": psutil.Process(proc.pid).create_time()}
    save_state(state)
    print(f"Started {name} (PID {proc.pid}).")


def wait_until(label: str, predicate, seconds: int, *, state: dict, process_name: str | None = None) -> None:
    print(f"Waiting for {label}...", flush=True)
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            print(f"{label}: ready")
            return
        if process_name:
            record = state.get(process_name, {})
            if record and not alive(record.get("pid", -1), record.get("started", -1)):
                raise RuntimeError(f"{label} exited. See .runtime/{process_name}.err.log")
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for {label}. See .runtime/ logs.")


def docker_ready() -> bool:
    try:
        result = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                                capture_output=True, timeout=8, creationflags=CREATE_NO_WINDOW)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def ensure_docker(state: dict) -> None:
    if not shutil.which("docker"):
        raise RuntimeError("Docker CLI not found. Install/open Docker Desktop first.")
    if not docker_ready():
        desktop = Path(r"C:\Program Files\Docker\Docker\Docker Desktop.exe")
        if not desktop.is_file():
            raise RuntimeError("Docker Desktop is not running and its executable was not found.")
        subprocess.Popen([str(desktop)], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=CREATE_NO_WINDOW)
        wait_until("Docker Desktop", docker_ready, 150, state=state)
    inspect = subprocess.run(["docker", "inspect", "--format", "{{.State.Running}}", CONTAINER],
                             capture_output=True, text=True, timeout=15, creationflags=CREATE_NO_WINDOW)
    if inspect.returncode != 0:
        raise RuntimeError(f"Docker container {CONTAINER} was not found. Create it before using this launcher.")
    if inspect.stdout.strip() != "true":
        start = subprocess.run(["docker", "start", CONTAINER], capture_output=True,
                               timeout=45, creationflags=CREATE_NO_WINDOW)
        if start.returncode != 0:
            raise RuntimeError(f"Could not start Docker container {CONTAINER}.")
    wait_until("Neo4j", lambda: _text_available("http://127.0.0.1:7474/"), 60, state=state)


def neo4j_environment(base: dict[str, str]) -> dict[str, str]:
    from scripts.run_with_neo4j import docker_environment
    previous = os.environ.copy()
    try:
        os.environ.clear()
        os.environ.update(base)
        return docker_environment()
    finally:
        os.environ.clear()
        os.environ.update(previous)


def ensure_ollama(base: dict[str, str], state: dict) -> None:
    url = "http://127.0.0.1:11434/api/tags"
    try:
        tags = http_json(url, timeout=3)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        ollama = shutil.which("ollama")
        if not ollama:
            raise RuntimeError("Ollama not found. Install Ollama before running this project.")
        launch("ollama", [ollama, "serve"], base, state)
        wait_until("Ollama", lambda: _json_available(url), 60, state=state, process_name="ollama")
        tags = http_json(url)
    model = base.get("OLLAMA_MODEL", "qwen2.5:3b")
    installed = {item.get("name") for item in tags.get("models", [])}
    if model not in installed:
        raise RuntimeError(f"Ollama model {model} is not installed. Run: ollama pull {model}")
    print(f"Ollama model: {model}")


def _json_available(url: str) -> bool:
    try:
        return isinstance(http_json(url, timeout=3).get("models"), list)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return False


def ensure_webhook(base: dict[str, str], state: dict) -> int:
    port = int(base.get("LINE_PORT", "8000"))
    health = f"http://127.0.0.1:{port}/healthz"
    if healthy(health, identify=True):
        print("LINE webhook: already running")
        return port
    if _port_in_use(port):
        raise RuntimeError(f"Port {port} is occupied by a different or outdated service. Stop it and rerun.")
    env = neo4j_environment(base)
    launch("line_webhook", [sys.executable, "-u", "scripts/line_webhook.py"], env, state)
    wait_until("LINE webhook", lambda: healthy(health, identify=True), 150,
               state=state, process_name="line_webhook")
    return port


def _port_in_use(port: int) -> bool:
    import socket
    with socket.socket() as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def ensure_ui(base: dict[str, str], state: dict) -> None:
    health = "http://127.0.0.1:8501/_stcore/health"
    if _port_in_use(8501):
        record = state.get("streamlit", {})
        if alive(record.get("pid", -1), record.get("started", -1)) and _text_available(health):
            print("Streamlit UI: already running")
        else:
            print("Port 8501 is already in use; leaving the existing UI/process untouched.")
        return
    env = neo4j_environment(base)
    launch("streamlit", [sys.executable, "-m", "streamlit", "run", "app.py",
                         "--server.address", "127.0.0.1", "--server.port", "8501",
                         "--server.headless", "true"], env, state)
    wait_until("Streamlit UI", lambda: _text_available(health), 60,
               state=state, process_name="streamlit")


def _text_available(url: str) -> bool:
    try:
        with urlopen(url, timeout=3) as response:
            return response.status == 200
    except (HTTPError, URLError, TimeoutError, OSError):
        return False


def line_endpoint(token: str) -> dict:
    return http_json("https://api.line.me/v2/bot/channel/webhook/endpoint", token=token)


def tunnel_from_log() -> str | None:
    for suffix in ("err", "out"):
        path = RUNTIME / f"cloudflared.{suffix}.log"
        if path.is_file():
            matches = TUNNEL_RE.findall(path.read_text(encoding="utf-8", errors="replace"))
            if matches:
                return matches[-1]
    return None


def stop_owned_tunnel(state: dict) -> None:
    """Retire only a stale tunnel started by this launcher, never another process."""
    record = state.get("cloudflared", {})
    if alive(record.get("pid", -1), record.get("started", -1)):
        import psutil
        try:
            process = psutil.Process(record["pid"])
            process.terminate()
            try:
                process.wait(timeout=10)
            except psutil.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        except psutil.NoSuchProcess:
            pass
    state.pop("cloudflared", None)
    save_state(state)


def ensure_tunnel(port: int, base: dict[str, str], state: dict) -> str:
    token = base["LINE_CHANNEL_ACCESS_TOKEN"]
    current = line_endpoint(token).get("endpoint", "")
    if current.endswith("/webhook"):
        remote_health = current[:-len("/webhook")] + "/healthz"
        if healthy(remote_health, identify=True):
            print("HTTPS tunnel: existing LINE endpoint is healthy")
            return current
    cloudflared = shutil.which("cloudflared")
    if not cloudflared:
        raise RuntimeError("cloudflared not found. Install Cloudflare Tunnel or configure a public HTTPS endpoint.")
    record = state.get("cloudflared", {})
    active = alive(record.get("pid", -1), record.get("started", -1))
    owned_url = tunnel_from_log() if active else None
    if owned_url and healthy(owned_url + "/healthz", identify=True):
        endpoint = owned_url + "/webhook"
    else:
        if active:
            print("Old Quick Tunnel is unhealthy; restarting only this project's tunnel.")
            stop_owned_tunnel(state)
        for suffix in ("err", "out"):
            (RUNTIME / f"cloudflared.{suffix}.log").write_text("", encoding="utf-8")
        launch("cloudflared", [cloudflared, "tunnel", "--url", f"http://127.0.0.1:{port}"], base, state)
        deadline = time.monotonic() + 75
        endpoint = None
        while time.monotonic() < deadline:
            record = state.get("cloudflared", {})
            if not alive(record.get("pid", -1), record.get("started", -1)):
                raise RuntimeError("Cloudflare tunnel exited. See .runtime/cloudflared.err.log")
            url = tunnel_from_log()
            if url and healthy(url + "/healthz", identify=True):
                endpoint = url + "/webhook"
                break
            time.sleep(2)
        if not endpoint:
            raise RuntimeError("Could not obtain a working Quick Tunnel URL. See .runtime/cloudflared.err.log")
    test = http_json("https://api.line.me/v2/bot/channel/webhook/test", method="POST",
                     token=token, payload={"endpoint": endpoint}, timeout=15)
    if not test.get("success"):
        raise RuntimeError("LINE webhook test did not succeed; the existing LINE endpoint was left unchanged.")
    http_json("https://api.line.me/v2/bot/channel/webhook/endpoint", method="PUT",
              token=token, payload={"endpoint": endpoint}, timeout=15)
    print("LINE endpoint updated after a successful webhook test.")
    return endpoint


def start() -> int:
    if os.name != "nt":
        raise RuntimeError("This one-click launcher is for Windows only.")
    try:
        import psutil  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("This launcher needs the already-used psutil package (pip install psutil).") from exc
    private = env_file()
    if not private.get("LINE_CHANNEL_SECRET") or not private.get("LINE_CHANNEL_ACCESS_TOKEN"):
        raise RuntimeError("Fill LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN in private .env first.")
    base = os.environ.copy()
    base.update(private)  # .env wins over stale variables from earlier lab sessions.
    RUNTIME.mkdir(exist_ok=True)
    state = read_state()
    ensure_docker(state)
    ensure_ollama(base, state)
    port = ensure_webhook(base, state)
    ensure_ui(base, state)
    endpoint = ensure_tunnel(port, base, state)
    print("\nProject ready:")
    print("  Web UI: http://127.0.0.1:8501")
    print(f"  LINE webhook: {endpoint}")
    print("  Neo4j Browser: http://127.0.0.1:7474")
    print("  Test by sending a message to your LINE Official Account.")
    print("  Quick Tunnel URL changes when restarted; rerun START_PROJECT.cmd to reconnect.")
    return 0


def stop() -> int:
    state = read_state()
    if not state:
        print("No processes recorded by this launcher. Existing user services were not touched.")
        return 0
    for name in ("cloudflared", "line_webhook", "streamlit", "ollama"):
        record = state.get(name, {})
        pid, started = record.get("pid", -1), record.get("started", -1)
        if alive(pid, started):
            result = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                                    capture_output=True, creationflags=CREATE_NO_WINDOW)
            print(f"{name}: {'stopped' if result.returncode == 0 else 'could not stop'}")
            if result.returncode != 0:
                continue
        state.pop(name, None)
    save_state(state)
    print("Docker Desktop and Neo4j container were left running. LINE still points to the old tunnel until restart.")
    return 0


def main() -> int:
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in {"start", "stop"}:
            print("Usage: python scripts/project_launcher.py [start|stop]")
            return 2
        return start() if sys.argv[1] == "start" else stop()
    except (RuntimeError, OSError, ValueError, HTTPError, URLError, subprocess.SubprocessError) as exc:
        if isinstance(exc, HTTPError):
            message = f"External API returned HTTP {exc.code}"
        else:
            message = str(exc)
        print(f"ERROR: {message}", file=sys.stderr)
        print("Check the non-secret logs in .runtime/ and rerun START_PROJECT.cmd.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
