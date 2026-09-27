"""Run a project command with the existing local Neo4j Docker credentials.

The password stays in process memory. It is never printed or written to .env.
Usage: python scripts/run_with_neo4j.py -- python -m streamlit run app.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONTAINER = "hybrid-rag-neo4j"


def docker_environment() -> dict[str, str]:
    completed = subprocess.run(
        ["docker", "inspect", CONTAINER],
        check=True, capture_output=True, text=True, timeout=15,
    )
    inspection = json.loads(completed.stdout)[0]
    entries = [value for value in inspection["Config"]["Env"] if value.startswith("NEO4J_AUTH=")]
    if len(entries) != 1 or "/" not in entries[0][len("NEO4J_AUTH="):]:
        raise RuntimeError("Neo4j Docker auth configuration is unavailable")
    user, password = entries[0][len("NEO4J_AUTH="):].split("/", 1)
    if not user or not password or password == "none":
        raise RuntimeError("Neo4j Docker auth configuration is invalid")
    environment = os.environ.copy()
    environment.update({
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": user,
        "NEO4J_PASSWORD": password,
        "NEO4J_PROJECT_ID": "fitness_rag_final_2026",
    })
    return environment


def main() -> int:
    command = sys.argv[1:]
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        command = [sys.executable, "-m", "streamlit", "run", "app.py"]
    elif command[0].lower() in ("python", "python.exe"):
        command[0] = sys.executable
    try:
        environment = docker_environment()
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError, RuntimeError) as exc:
        print(f"Cannot obtain Neo4j Docker configuration: {type(exc).__name__}", file=sys.stderr)
        return 2
    print("Using the isolated fitness graph on Neo4j localhost:7687", flush=True)
    return subprocess.call(command, cwd=ROOT, env=environment)


if __name__ == "__main__":
    raise SystemExit(main())
