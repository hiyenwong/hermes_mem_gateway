from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable


class BackgroundTasks:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="layered-memory")
        self._pending: list[Future[Any]] = []
        self.errors: list[BaseException] = []

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future[Any]:
        future = self._executor.submit(fn, *args, **kwargs)
        future.add_done_callback(self._record_error)
        self._pending.append(future)
        return future

    def drain(self, *, timeout: float) -> None:
        for future in list(self._pending):
            future.result(timeout=timeout)
        self._pending.clear()

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)

    def _record_error(self, future: Future[Any]) -> None:
        try:
            error = future.exception()
        except BaseException as exc:
            self.errors.append(exc)
            return
        if error is not None:
            self.errors.append(error)
