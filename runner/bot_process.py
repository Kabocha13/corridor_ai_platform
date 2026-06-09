from __future__ import annotations

import json
import select
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class BotReply:
    action: dict[str, Any] | None
    thinking_time_ms: float
    error: str | None = None
    raw_output: str = ""


class BotProcess:
    """Runs a Python bot behind a small process boundary.

    The class owns process execution so it can later be replaced by a Docker
    implementation without changing the match runner.
    """

    def __init__(self, script_path: str | Path, timeout_seconds: float = 1.0):
        self.script_path = str(script_path)
        self.timeout_seconds = timeout_seconds
        self._process: subprocess.Popen[str] | None = None

    @property
    def name(self) -> str:
        return Path(self.script_path).stem

    def request_action(self, state_json: dict[str, Any]) -> BotReply:
        import time

        started = time.perf_counter()
        try:
            process = self._ensure_process()
            assert process.stdin is not None
            assert process.stdout is not None
            process.stdin.write(json.dumps(state_json) + "\n")
            process.stdin.flush()
            ready, _, _ = select.select([process.stdout], [], [], self.timeout_seconds)
            if not ready:
                self.close()
                return BotReply(None, self._elapsed_ms(started), "timeout", "")
            stdout = process.stdout.readline().strip()
        except BrokenPipeError as exc:
            self.close()
            return BotReply(None, self._elapsed_ms(started), f"crash: {exc}", "")
        except Exception as exc:  # pragma: no cover - defensive process boundary
            self.close()
            return BotReply(None, self._elapsed_ms(started), f"crash: {exc}", "")

        elapsed = self._elapsed_ms(started)
        if not stdout:
            stderr = self._read_stderr()
            self.close()
            return BotReply(None, elapsed, f"empty output; stderr={stderr}", stdout)
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError as exc:
            return BotReply(None, elapsed, f"invalid json: {exc}; stderr={self._read_stderr()}", stdout)
        if not isinstance(parsed, dict):
            return BotReply(None, elapsed, "action output was not an object", stdout)
        return BotReply(parsed, elapsed, None, stdout)

    def close(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None

    def _ensure_process(self) -> subprocess.Popen[str]:
        if self._process and self._process.poll() is None:
            return self._process
        self._process = subprocess.Popen(
            [sys.executable, self.script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        return self._process

    def _read_stderr(self) -> str:
        if not self._process or not self._process.stderr:
            return ""
        ready, _, _ = select.select([self._process.stderr], [], [], 0)
        if not ready:
            return ""
        return self._process.stderr.readline().strip()

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        import time

        return (time.perf_counter() - started) * 1000.0
