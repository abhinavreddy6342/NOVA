from __future__ import annotations

import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict


# ---------------------------------------------------------------------------
# NOVA DOCKER SANDBOX CONFIGURATION
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).resolve().parents[3]
SANDBOX_ROOT = (
    BACKEND_ROOT / "app" / "sandbox"
).resolve()

SANDBOX_INPUT = (
    SANDBOX_ROOT / "input"
).resolve()

SANDBOX_OUTPUT = (
    SANDBOX_ROOT / "output"
).resolve()

SANDBOX_TEMP = (
    SANDBOX_ROOT / "temp"
).resolve()

DOCKER_IMAGE = "python:3.13-slim"

DEFAULT_TIMEOUT = 10
MAX_TIMEOUT = 30

MAX_CODE_SIZE = 100_000

MAX_OUTPUT_SIZE = 100_000

MEMORY_LIMIT = "256m"
CPU_LIMIT = "1.0"


# ---------------------------------------------------------------------------
# SANDBOX INITIALIZATION
# ---------------------------------------------------------------------------

def _ensure_sandbox_directories() -> None:
    """
    Ensure NOVA sandbox directories exist.
    """

    SANDBOX_INPUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    SANDBOX_OUTPUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    SANDBOX_TEMP.mkdir(
        parents=True,
        exist_ok=True,
    )


# ---------------------------------------------------------------------------
# CODE VALIDATION
# ---------------------------------------------------------------------------

def _validate_python_code(
    code: str,
) -> str:
    """
    Validate basic Python execution input.

    Docker isolation is the primary security boundary.
    """

    if code is None:
        raise ValueError(
            "Code is required."
        )

    code = str(code)

    if not code.strip():
        raise ValueError(
            "Code cannot be empty."
        )

    code_size = len(
        code.encode("utf-8")
    )

    if code_size > MAX_CODE_SIZE:
        raise ValueError(
            "Code exceeds the maximum allowed size."
        )

    return code


def _normalize_timeout(
    timeout: int | float | None,
) -> int:
    """
    Normalize requested execution timeout.
    """

    if timeout is None:
        return DEFAULT_TIMEOUT

    try:
        timeout_value = int(
            timeout
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "timeout must be an integer."
        ) from exc

    if timeout_value < 1:
        timeout_value = 1

    return min(
        timeout_value,
        MAX_TIMEOUT,
    )


# ---------------------------------------------------------------------------
# TEMPORARY SOURCE FILE
# ---------------------------------------------------------------------------

def _create_source_file(
    code: str,
) -> Path:
    """
    Create a temporary Python source file inside
    the NOVA sandbox temp directory.
    """

    _ensure_sandbox_directories()

    filename = (
        f"nova_exec_{uuid.uuid4().hex}.py"
    )

    source_path = (
        SANDBOX_TEMP / filename
    ).resolve()

    source_path.write_text(
        code,
        encoding="utf-8",
    )

    return source_path


# ---------------------------------------------------------------------------
# OUTPUT SANITIZATION
# ---------------------------------------------------------------------------

def _truncate_output(
    value: str,
) -> str:
    """
    Prevent excessively large tool responses.
    """

    if len(value) <= MAX_OUTPUT_SIZE:
        return value

    return (
        value[:MAX_OUTPUT_SIZE]
        + "\n\n[NOVA: output truncated]"
    )


# ---------------------------------------------------------------------------
# DOCKER EXECUTION
# ---------------------------------------------------------------------------

def execute_python_in_sandbox(
    code: str,
    timeout: int | float | None = None,
) -> Dict[str, Any]:
    """
    Execute Python code inside an isolated Docker container.

    Security properties:
    - network disabled
    - read-only container filesystem
    - temporary NOVA workspace mounted
    - no host root filesystem access
    - memory limit
    - CPU limit
    - timeout
    - automatic container removal
    """

    code = _validate_python_code(
        code
    )

    execution_timeout = _normalize_timeout(
        timeout
    )

    source_path = _create_source_file(
        code
    )

    container_name = (
        f"nova-sandbox-{uuid.uuid4().hex[:12]}"
    )

    try:
        command = [
            "docker",
            "run",

            "--rm",

            "--name",
            container_name,

            # No network access.
            "--network",
            "none",

            # Read-only container filesystem.
            "--read-only",

            # Resource limits.
            "--memory",
            MEMORY_LIMIT,

            "--cpus",
            CPU_LIMIT,

            # Temporary filesystem for /tmp.
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",

            # Mount only the sandbox directories NOVA needs.
            "-v",
            f"{SANDBOX_INPUT}:/nova/input:ro",

            "-v",
            f"{SANDBOX_OUTPUT}:/nova/output:rw",

            "-v",
            f"{SANDBOX_TEMP}:/nova/temp:rw",

            # Mount the generated source file read-only.
            "-v",
            f"{source_path}:/nova/code.py:ro",

            DOCKER_IMAGE,

            "python",
            "/nova/code.py",
        ]

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=execution_timeout,
            check=False,
        )

        stdout = _truncate_output(
            completed.stdout or ""
        )

        stderr = _truncate_output(
            completed.stderr or ""
        )

        return {
            "success": (
                completed.returncode == 0
            ),
            "language": "python",
            "return_code": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "timeout_seconds": execution_timeout,
            "network": "disabled",
            "filesystem": "read-only",
            "workspace": "NOVA sandbox",
            "container_removed": True,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "language": "python",
            "return_code": None,
            "stdout": "",
            "stderr": (
                "Execution timed out after "
                f"{execution_timeout} seconds."
            ),
            "timeout_seconds": execution_timeout,
            "network": "disabled",
            "filesystem": "read-only",
            "workspace": "NOVA sandbox",
            "container_removed": True,
            "timeout": True,
        }

    except FileNotFoundError as exc:
        raise RuntimeError(
            "Docker executable was not found."
        ) from exc

    finally:
        try:
            if source_path.exists():
                source_path.unlink()
        except OSError:
            pass