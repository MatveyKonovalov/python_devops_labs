from __future__ import annotations

import json
import os
import sys

INHERITED_VALUE: int = 314_159


def run_probe() -> dict[str, object]:
    """Проверить fork и вернуть единый JSON-совместимый результат."""
    if not hasattr(os, "fork"):
        return {
            "status": "unsupported",
            "reason": "os.fork недоступен на этой платформе",
        }

    read_fd, write_fd = os.pipe()

    pid = os.fork()
    if pid == 0:
        # Дочерний процесс
        os.close(read_fd)
        try:
            payload = {
                "child_pid": os.getpid(),
                "child_parent_pid": os.getppid(),
                "inherited_value": INHERITED_VALUE,
            }
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            with os.fdopen(write_fd, "wb") as handle:
                handle.write(data)
        finally:
            os._exit(0)

    # Родительский процесс
    os.close(write_fd)
    try:
        with os.fdopen(read_fd, "rb") as handle:
            raw = handle.read()
        child_payload = json.loads(raw.decode("utf-8"))
    finally:
        _, exit_code = os.waitpid(pid, 0)

    if exit_code != 0:
        return {
            "status": "failed",
            "reason": f"дочерний процесс завершился с кодом {exit_code}",
        }

    return {
        "status": "supported",
        "parent_pid": os.getpid(),
        "child_pid": child_payload["child_pid"],
        "child_parent_pid": child_payload["child_parent_pid"],
        "inherited_value": child_payload["inherited_value"],
        "inherited_value_matches": child_payload["inherited_value"] == INHERITED_VALUE,
        "child_parent_pid_matches_parent_pid": child_payload["child_parent_pid"] == os.getpid(),
    }


def main() -> int:
    result = run_probe()
    line = json.dumps(result, ensure_ascii=False)
    sys.stdout.buffer.write(line.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())