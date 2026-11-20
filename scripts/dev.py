"""Start both local development servers. Run: python3 scripts/dev.py --web"""

import argparse
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--web", action="store_true", help="Open the web preview instead of the Expo device launcher"
    )
    parser.add_argument(
        "--postgres",
        action="store_true",
        help="Start the project PostgreSQL service and apply migrations before launching",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not shutil.which("uv") or not shutil.which("node"):
        parser.error("Install uv and Node.js 24 first; see README.md.")
    if not (root / "mobile/node_modules").exists() or not (root / "backend/.venv").exists():
        parser.error(
            "Install dependencies first: (cd backend && uv sync --locked), then (cd mobile && npm ci)."
        )
    version = int(
        subprocess.check_output(["node", "-p", "process.versions.node.split('.')[0]"], text=True).strip()
    )
    command = (
        ["node"] if version in (22, 24) or version >= 26 else ["npx", "--yes", "--package=node@24", "node"]
    )
    command += [str(root / "mobile/node_modules/expo/bin/cli"), "start", "--port", "8081"]
    if args.web:
        command.append("--web")
    server_env = os.environ.copy()
    mobile_env = os.environ.copy()
    mobile_env.setdefault("APP_VARIANT", "development")
    mobile_env.setdefault("EXPO_PUBLIC_APP_VARIANT", mobile_env["APP_VARIANT"])
    if args.postgres:
        if not shutil.which("docker"):
            parser.error("Docker is required for --postgres.")
        subprocess.run(["docker", "compose", "up", "-d", "--wait", "db"], cwd=root, check=True)
        if "DATABASE_URL" not in server_env:
            from urllib.parse import quote

            password = quote(server_env.get("POSTGRES_PASSWORD", "local-development"), safe="")
            port = server_env.get("POSTGRES_PORT", "55433")
            server_env["DATABASE_URL"] = (
                f"postgresql+psycopg://quantlens:{password}@localhost:{port}/quantlens"
            )
        subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"], cwd=root / "backend", env=server_env, check=True
        )
    processes = []
    try:
        processes.append(
            subprocess.Popen(
                ["uv", "run", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
                cwd=root / "backend",
                env=server_env,
                start_new_session=True,
            )
        )
        processes.append(
            subprocess.Popen(command, cwd=root / "mobile", env=mobile_env, start_new_session=True)
        )
        print(
            "\nQuantLens: http://localhost:8081 | API docs: http://localhost:8000/docs\nCtrl+C stops both servers.\n",
            flush=True,
        )
        while all(p.poll() is None for p in processes):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)


if __name__ == "__main__":
    main()
