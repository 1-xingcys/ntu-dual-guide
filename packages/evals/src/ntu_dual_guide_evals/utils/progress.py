from __future__ import annotations

import sys
import time


class EvalProgress:
    def __init__(self, total: int, *, enabled: bool = True, width: int = 24) -> None:
        self.total = max(total, 0)
        self.enabled = enabled and self.total > 0
        self.width = width
        self.started_at = time.monotonic()
        self._last_message_length = 0

    def start_case(self, completed: int, case_id: str) -> None:
        self._render(completed, case_id, state="running")

    def finish_case(self, completed: int, case_id: str, *, state: str = "done") -> None:
        self._render(completed, case_id, state=state)

    def close(self) -> None:
        if not self.enabled:
            return
        sys.stderr.write("\n")
        sys.stderr.flush()

    def _render(self, completed: int, case_id: str, *, state: str) -> None:
        if not self.enabled:
            return
        completed = min(max(completed, 0), self.total)
        ratio = completed / self.total if self.total else 0.0
        filled = int(self.width * ratio)
        bar = "#{0}{1}".format("#" * filled, "-" * (self.width - filled))
        elapsed = time.monotonic() - self.started_at
        message = (
            "\r[{bar}] {completed}/{total} {percent:>5.1f}% "
            "{state:<7} case={case_id} elapsed={elapsed:.1f}s"
        ).format(
            bar=bar,
            completed=completed,
            total=self.total,
            percent=ratio * 100,
            state=state,
            case_id=case_id,
            elapsed=elapsed,
        )
        padding = max(self._last_message_length - len(message), 0)
        sys.stderr.write(message + (" " * padding))
        sys.stderr.flush()
        self._last_message_length = len(message)

