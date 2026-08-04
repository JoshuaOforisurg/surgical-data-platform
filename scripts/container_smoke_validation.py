from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
STOCK_ROOT = REPO_ROOT / "platform" / "modules" / "operational" / "stock_inventory"
SURGEON_ROOT = REPO_ROOT / "platform" / "modules" / "operational" / "surgeon_preference"


@dataclass(frozen=True)
class SmokeResult:
    name: str
    status: str
    message: str
    command: str | None = None

    @property
    def failed(self) -> bool:
        return self.status == "failed"


@dataclass(frozen=True)
class SmokeSummary:
    status: str
    run_id: str
    check_count: int
    failure_count: int
    checks: list[dict[str, str | None]]


def command_label(command: Iterable[str]) -> str:
    return " ".join(command)


def run_command(
    name: str,
    command: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    timeout_seconds: int = 600,
    show_output: bool = False,
) -> SmokeResult:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    label = command_label(command)
    print(f"RUN {name}: {label}", flush=True)
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=run_env,
            capture_output=not show_output,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return SmokeResult(name, "failed", f"Command not found: {command[0]}", label)
    except subprocess.TimeoutExpired:
        return SmokeResult(name, "failed", f"Timed out after {timeout_seconds}s.", label)

    if completed.returncode == 0:
        message = "Command completed successfully."
        if not show_output:
            output = "\n".join(part.strip() for part in [completed.stdout, completed.stderr] if part.strip())
            message = output[-1200:] if output else message
        return SmokeResult(name, "passed", message, label)

    output = ""
    if not show_output:
        output = "\n".join(part.strip() for part in [completed.stdout, completed.stderr] if part.strip())
    message = output[-2000:] if output else f"Command exited with {completed.returncode}."
    return SmokeResult(name, "failed", message, label)


def wait_for_http(name: str, url: str, timeout_seconds: int) -> SmokeResult:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                body = response.read().decode("utf-8").strip()
            return SmokeResult(name, "passed", body or "Endpoint responded.", f"GET {url}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
            time.sleep(2)
    return SmokeResult(name, "failed", f"Endpoint did not become healthy: {last_error}", f"GET {url}")


def add_result(results: list[SmokeResult], result: SmokeResult) -> None:
    marker = "PASS" if result.status == "passed" else "FAIL"
    print(f"{marker} {result.name}: {result.message.splitlines()[-1] if result.message else result.status}", flush=True)
    results.append(result)
    if result.failed:
        raise SystemExit(1)


def run_stock_smoke(run_id: str, stock_ui_port: int, timeout_seconds: int) -> list[SmokeResult]:
    results: list[SmokeResult] = []
    env = {
        "STOCK_PIPELINE_RUN_ID": run_id,
        "STOCK_STREAMLIT_PORT": str(stock_ui_port),
    }
    add_result(
        results,
        run_command(
            "stock.clean_one_shot_containers",
            ["docker", "compose", "rm", "--stop", "--force", "stock_pipeline", "stock_quality", "stock_publish"],
            STOCK_ROOT,
            env=env,
            timeout_seconds=60,
        ),
    )
    add_result(
        results,
        run_command("stock.minio_up", ["docker", "compose", "up", "-d", "stock-minio"], STOCK_ROOT, env=env),
    )
    add_result(
        results,
        run_command(
            "stock.pipeline",
            ["docker", "compose", "run", "--rm", "--build", "stock_pipeline"],
            STOCK_ROOT,
            env=env,
            timeout_seconds=timeout_seconds,
            show_output=True,
        ),
    )
    add_result(
        results,
        run_command(
            "stock.quality",
            ["docker", "compose", "run", "--rm", "--no-deps", "stock_quality"],
            STOCK_ROOT,
            env=env,
            timeout_seconds=timeout_seconds,
            show_output=True,
        ),
    )
    add_result(
        results,
        run_command(
            "stock.publish",
            ["docker", "compose", "run", "--rm", "--no-deps", "stock_publish"],
            STOCK_ROOT,
            env=env,
            timeout_seconds=timeout_seconds,
            show_output=True,
        ),
    )
    add_result(
        results,
        run_command(
            "stock.streamlit_up",
            ["docker", "compose", "up", "-d", "--build", "--no-deps", "stock_streamlit"],
            STOCK_ROOT,
            env=env,
            timeout_seconds=timeout_seconds,
        ),
    )
    add_result(results, wait_for_http("stock.streamlit_health", f"http://localhost:{stock_ui_port}/_stcore/health", 90))
    snapshot_code = (
        "import json; "
        "from config.settings import load_settings; "
        "from storage.object_store import S3ObjectStoreClient; "
        "from streamlit_services.gold_dashboard_service import dashboard_snapshot_from_object_store, list_object_gold_manifests; "
        "settings = load_settings(); "
        "store = S3ObjectStoreClient(settings.object_store); "
        "manifests = list_object_gold_manifests(store, settings.object_store.root_prefix); "
        "assert manifests, 'no object-store gold manifests found'; "
        "snapshot = dashboard_snapshot_from_object_store(store, manifests[0].manifest_path, settings.object_store.root_prefix); "
        "data = snapshot.to_dict(); "
        "print(json.dumps({'run_id': data['run_id'], 'case_count': data['case_count'], "
        "'shortage_line_count': data['shortage_line_count'], "
        "'reorder_position_count': data['reorder_position_count']}, sort_keys=True))"
    )
    add_result(
        results,
        run_command(
            "stock.dashboard_object_store_snapshot",
            ["docker", "compose", "exec", "-T", "stock_streamlit", "python", "-c", snapshot_code],
            STOCK_ROOT,
            env=env,
            timeout_seconds=120,
        ),
    )
    return results


def run_surgeon_smoke(surgeon_ui_port: int, timeout_seconds: int) -> list[SmokeResult]:
    results: list[SmokeResult] = []
    if not (SURGEON_ROOT / ".env").is_file():
        result = SmokeResult(
            "surgeon.env",
            "failed",
            "Missing platform/modules/operational/surgeon_preference/.env. Copy .env.example and fill local values.",
        )
        print(f"FAIL {result.name}: {result.message}", flush=True)
        return [result]

    add_result(
        results,
        run_command("surgeon.services_up", ["docker", "compose", "up", "-d", "minio", "postgres"], SURGEON_ROOT),
    )
    add_result(
        results,
        run_command(
            "surgeon.clean_one_shot_containers",
            ["docker", "compose", "rm", "--stop", "--force", "surgeon_pipeline"],
            SURGEON_ROOT,
            timeout_seconds=60,
        ),
    )
    add_result(
        results,
        run_command(
            "surgeon.pipeline",
            ["docker", "compose", "run", "--rm", "--build", "surgeon_pipeline"],
            SURGEON_ROOT,
            timeout_seconds=timeout_seconds,
            show_output=True,
        ),
    )
    run_command(
        "surgeon.remove_previous_smoke_ui",
        ["docker", "rm", "-f", "surgeon_streamlit_ui_smoke"],
        SURGEON_ROOT,
        timeout_seconds=30,
    )
    add_result(
        results,
        run_command(
            "surgeon.streamlit_up",
            [
                "docker",
                "compose",
                "run",
                "-d",
                "--name",
                "surgeon_streamlit_ui_smoke",
                "--no-deps",
                "-p",
                f"{surgeon_ui_port}:8501",
                "streamlit_app",
            ],
            SURGEON_ROOT,
            timeout_seconds=timeout_seconds,
        ),
    )
    add_result(
        results,
        wait_for_http("surgeon.streamlit_health", f"http://localhost:{surgeon_ui_port}/_stcore/health", 90),
    )
    return results


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run live Docker container smoke checks for the platform.")
    parser.add_argument("--skip-stock", action="store_true", help="Skip stock inventory container smoke.")
    parser.add_argument("--skip-surgeon", action="store_true", help="Skip surgeon preference container smoke.")
    parser.add_argument("--stock-ui-port", type=int, default=8502, help="Host port for stock Streamlit.")
    parser.add_argument("--surgeon-ui-port", type=int, default=8503, help="Host port for temporary surgeon Streamlit smoke UI.")
    parser.add_argument("--run-id", default="", help="Run id for the stock pipeline smoke.")
    parser.add_argument("--timeout-seconds", type=int, default=600, help="Timeout for long-running Docker commands.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary after the checks.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not shutil.which("docker"):
        print("Docker CLI is not installed or not on PATH.", file=sys.stderr)
        raise SystemExit(1)

    run_id = args.run_id or f"smoke_container_{time.strftime('%Y%m%d_%H%M%S')}"
    results: list[SmokeResult] = []

    try:
        if not args.skip_stock:
            results.extend(run_stock_smoke(run_id, args.stock_ui_port, args.timeout_seconds))
        if not args.skip_surgeon:
            results.extend(run_surgeon_smoke(args.surgeon_ui_port, args.timeout_seconds))
    except SystemExit:
        pass

    failures = [result for result in results if result.failed]
    summary = SmokeSummary(
        status="passed" if not failures else "failed",
        run_id=run_id,
        check_count=len(results),
        failure_count=len(failures),
        checks=[asdict(result) for result in results],
    )
    if args.json:
        print(json.dumps(asdict(summary), indent=2))
    else:
        print(f"Container smoke validation: {summary.status}")
        print(f"Run id: {summary.run_id}")
        print(f"Checks: {summary.check_count}, failures: {summary.failure_count}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
