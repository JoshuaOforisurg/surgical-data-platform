from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
PLATFORM_ROOT = REPO_ROOT / "platform"
STOCK_ROOT = PLATFORM_ROOT / "modules" / "operational" / "stock_inventory"
SURGEON_ROOT = PLATFORM_ROOT / "modules" / "operational" / "surgeon_preference"
SHARED_ROOT = PLATFORM_ROOT / "shared"
EMIT_PROGRESS = False

EXCLUDED_SOURCE_PARTS = {
    ".git",
    ".idea",
    ".pytest_cache",
    "__pycache__",
    ".venv",
    "venv",
    "data",
    "data_lake",
    "logs",
    "output",
    "tmp",
}


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    severity: str
    message: str
    command: str | None = None

    @property
    def failed(self) -> bool:
        return self.status == "failed" and self.severity == "error"


@dataclass(frozen=True)
class PreflightResult:
    status: str
    check_count: int
    failure_count: int
    skipped_count: int
    checks: list[dict[str, str | None]]


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _check_name_path(path: Path) -> str:
    return _relative(path).lstrip(".")


def _python_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for root in paths:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if EXCLUDED_SOURCE_PARTS.intersection(path.relative_to(root).parts):
                continue
            files.append(path)
    return sorted(files)


def check_required_files() -> list[CheckResult]:
    required_files = [
        REPO_ROOT / ".github" / "workflows" / "platform-readiness.yml",
        REPO_ROOT / "docs" / "cloud-deployment-readiness.md",
        STOCK_ROOT / "docker-compose.yml",
        STOCK_ROOT / "Dockerfile",
        STOCK_ROOT / "Dockerfile.job",
        STOCK_ROOT / "orchestration" / "cloud_readiness.py",
        SURGEON_ROOT / "docker-compose.yml",
        SURGEON_ROOT / "Dockerfile",
        SURGEON_ROOT / "Dockerfile.job",
    ]
    results: list[CheckResult] = []
    for path in required_files:
        exists = path.is_file()
        results.append(
            CheckResult(
                name=f"required_file.{_check_name_path(path)}",
                status="passed" if exists else "failed",
                severity="error",
                message=f"{_relative(path)} exists." if exists else f"{_relative(path)} is missing.",
            )
        )
    return results


def check_python_syntax() -> CheckResult:
    files = _python_files([STOCK_ROOT, SURGEON_ROOT, SHARED_ROOT])
    failures: list[str] = []
    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")
        except SyntaxError as exc:
            failures.append(f"{_relative(path)}:{exc.lineno}: {exc.msg}")
        except UnicodeDecodeError as exc:
            failures.append(f"{_relative(path)}: could not read as UTF-8: {exc}")

    if failures:
        return CheckResult(
            name="python.syntax",
            status="failed",
            severity="error",
            message="Python syntax check failed: " + "; ".join(failures[:5]),
        )
    return CheckResult(
        name="python.syntax",
        status="passed",
        severity="error",
        message=f"Compiled {len(files)} Python source files without syntax errors.",
    )


def run_command(
    name: str,
    command: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    timeout_seconds: int,
    severity: str = "error",
) -> CheckResult:
    command_label = " ".join(command)
    if EMIT_PROGRESS:
        print(f"RUN {name}: {command_label}", flush=True)
    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=run_env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return CheckResult(
            name=name,
            status="failed",
            severity=severity,
            message=f"Command not found: {command[0]}",
            command=command_label,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name=name,
            status="failed",
            severity=severity,
            message=f"Timed out after {timeout_seconds}s.",
            command=command_label,
        )

    output = "\n".join(part.strip() for part in [completed.stdout, completed.stderr] if part.strip())
    if completed.returncode == 0:
        return CheckResult(
            name=name,
            status="passed",
            severity=severity,
            message=output or "Command completed successfully.",
            command=command_label,
        )
    if completed.returncode == 124:
        return CheckResult(
            name=name,
            status="failed",
            severity=severity,
            message=output or "Command hit its timeout wrapper before completing.",
            command=command_label,
        )
    return CheckResult(
        name=name,
        status="failed",
        severity=severity,
        message=output or f"Command exited with {completed.returncode}.",
        command=command_label,
    )


def timeout_wrapped_command(command: list[str], timeout_seconds: int) -> list[str]:
    timeout_tool = shutil.which("gtimeout") or shutil.which("timeout")
    if not timeout_tool:
        return command
    return [timeout_tool, str(timeout_seconds), *command]


def check_compose_files(timeout_seconds: int, skip_docker: bool) -> list[CheckResult]:
    if skip_docker:
        return [
            CheckResult(
                name="docker.compose_config",
                status="skipped",
                severity="warning",
                message="Docker Compose checks skipped by --skip-docker.",
            )
        ]
    if not shutil.which("docker"):
        return [
            CheckResult(
                name="docker.compose_config",
                status="failed",
                severity="error",
                message="Docker CLI is not installed or not on PATH.",
            )
        ]

    surgeon_env = {
        "DB_USER": "surgeon_preference_user",
        "DB_PASSWORD": "local-preflight-password",
        "DB_NAME": "surgeon_preference",
        "HOST_POSTGRES_PORT": "5433",
        "MINIO_ROOT_USER": "surgeon_preference_minio",
        "MINIO_ROOT_PASSWORD": "local-preflight-password",
    }
    compose_timeout = min(timeout_seconds, 45)
    compose_command = timeout_wrapped_command(["docker", "compose", "config", "--quiet"], compose_timeout)
    return [
        run_command(
            "docker.stock_compose_config",
            compose_command,
            STOCK_ROOT,
            timeout_seconds=compose_timeout + 5,
        ),
        run_command(
            "docker.surgeon_compose_config",
            compose_command,
            SURGEON_ROOT,
            env=surgeon_env,
            timeout_seconds=compose_timeout + 5,
        ),
    ]


def check_stock_cloud_like_preflight(timeout_seconds: int) -> CheckResult:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        handle.write("[]\n")
        preference_gold_path = handle.name

    env = {
        "MINIO_ENDPOINT": "https://s3.eu-west-2.amazonaws.com",
        "MINIO_ROOT_USER": "cloud-access-key",
        "MINIO_ROOT_PASSWORD": "cloud-secret-key",
        "MINIO_BUCKET": "surgical-platform-prod",
        "MINIO_ROOT_PREFIX": "stock_inventory/prod",
        "STOCK_PIPELINE_SOURCE_DIR": "/mnt/source",
        "SURGEON_PREFERENCE_GOLD_PATH": preference_gold_path,
        "STOCK_DASHBOARD_STORAGE_MODE": "object_store",
    }
    try:
        return run_command(
            "stock.cloud_like_preflight",
            [sys.executable, "-S", "-m", "orchestration.cloud_readiness", "--require-cross-pipeline"],
            STOCK_ROOT,
            env=env,
            timeout_seconds=timeout_seconds,
        )
    finally:
        Path(preference_gold_path).unlink(missing_ok=True)


def check_tests(timeout_seconds: int, include_tests: bool) -> list[CheckResult]:
    if not include_tests:
        return [
            CheckResult(
                name="tests.module_suites",
                status="skipped",
                severity="warning",
                message="Module tests skipped. Pass --include-tests to run them.",
            )
        ]

    pytest_env = {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    results = [
        run_command(
            "tests.stock_inventory",
            [sys.executable, "-m", "pytest", "-q", "tests"],
            STOCK_ROOT,
            env=pytest_env,
            timeout_seconds=timeout_seconds,
        )
    ]
    surgeon_tests = [
        "tests/test_access_control.py",
        "tests/test_auth_links.py",
        "tests/test_draft_review_service.py",
        "tests/test_publishing_service.py",
        "tests/test_user_registry_service.py",
        "tests/test_catalog_workflow.py",
    ]
    for test_file in surgeon_tests:
        results.append(
            run_command(
                f"tests.surgeon_preference.{Path(test_file).stem}",
                [sys.executable, "-m", "pytest", "-q", test_file],
                SURGEON_ROOT,
                env=pytest_env,
                timeout_seconds=timeout_seconds,
            )
        )
    return results


def run_preflight(timeout_seconds: int, include_tests: bool, skip_docker: bool) -> PreflightResult:
    checks: list[CheckResult] = []
    checks.extend(check_required_files())
    checks.append(check_python_syntax())
    checks.extend(check_compose_files(timeout_seconds, skip_docker))
    checks.append(check_stock_cloud_like_preflight(timeout_seconds))
    checks.extend(check_tests(timeout_seconds, include_tests))

    failures = [check for check in checks if check.failed]
    skipped = [check for check in checks if check.status == "skipped"]
    return PreflightResult(
        status="passed" if not failures else "failed",
        check_count=len(checks),
        failure_count=len(failures),
        skipped_count=len(skipped),
        checks=[asdict(check) for check in checks],
    )


def print_text_result(result: PreflightResult) -> None:
    print(f"Cloud deployment preflight: {result.status}")
    print(f"Checks: {result.check_count}, failures: {result.failure_count}, skipped: {result.skipped_count}")
    for check in result.checks:
        marker = {"passed": "PASS", "failed": "FAIL", "skipped": "SKIP"}[str(check["status"])]
        print(f"{marker} {check['name']}: {check['message']}")
        if check.get("command"):
            print(f"  command: {check['command']}")


def main(argv: Iterable[str] | None = None) -> None:
    global EMIT_PROGRESS

    parser = argparse.ArgumentParser(description="Run platform cloud deployment readiness checks.")
    parser.add_argument("--include-tests", action="store_true", help="Run focused module pytest suites.")
    parser.add_argument("--skip-docker", action="store_true", help="Skip Docker Compose config validation.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--timeout-seconds", type=int, default=120, help="Timeout for command checks.")
    args = parser.parse_args(list(argv) if argv is not None else None)
    EMIT_PROGRESS = not args.json

    result = run_preflight(
        timeout_seconds=args.timeout_seconds,
        include_tests=args.include_tests,
        skip_docker=args.skip_docker,
    )
    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print_text_result(result)
    if result.failure_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
