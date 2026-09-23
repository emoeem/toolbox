from __future__ import annotations

from threading import Event


class CancelledError(RuntimeError):
    """Raised when a processor cooperatively stops after cancellation."""


class CancelToken:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise CancelledError("任务已取消")

    @property
    def event(self) -> Event:
        return self._event
