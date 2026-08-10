from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from queue import Queue
from threading import Event, RLock, Thread
from typing import Literal
from uuid import uuid4

from koeclone.errors import ErrorCode, KoecloneError

logger = logging.getLogger(__name__)

JobStatus = Literal["queued", "running", "succeeded", "failed"]
JobHandler = Callable[[str], None]
StateListener = Callable[["JobState"], None]


@dataclass(frozen=True)
class JobState:
    job_id: str
    status: JobStatus
    error_code: ErrorCode | None = None
    error_id: str | None = None


class JobQueue:
    def __init__(
        self,
        handler: JobHandler,
        *,
        listener: StateListener | None = None,
    ) -> None:
        self._handler = handler
        self._listener = listener
        self._queue: Queue[object] = Queue()
        self._states: dict[str, JobState] = {}
        self._completed: dict[str, Event] = {}
        self._lock = RLock()
        self._thread: Thread | None = None
        self._accepting = True
        self._shutdown_started = False
        self._sentinel = object()

    def start(self) -> None:
        with self._lock:
            self._start_worker_locked()

    def submit(self, job_id: str) -> JobState:
        with self._lock:
            if not self._accepting:
                raise RuntimeError("Job queue is shut down")
            if job_id in self._states:
                raise ValueError("Duplicate job id")
            state = JobState(job_id=job_id, status="queued")
            self._states[job_id] = state
            self._completed[job_id] = Event()
            self._queue.put(job_id)
            self._notify(state)
        return state

    def state(self, job_id: str) -> JobState | None:
        with self._lock:
            return self._states.get(job_id)

    def wait_for(self, job_id: str, timeout: float = 5.0) -> JobState:
        with self._lock:
            event = self._completed.get(job_id)
        if event is None:
            raise KeyError(job_id)
        if not event.wait(timeout):
            raise TimeoutError(job_id)
        state = self.state(job_id)
        if state is None:
            raise KeyError(job_id)
        return state

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            self._accepting = False
            self._start_worker_locked()
            if not self._shutdown_started:
                self._shutdown_started = True
                self._queue.put(self._sentinel)
            thread = self._thread
        if wait:
            self._queue.join()
            if thread is not None:
                thread.join()

    def _start_worker_locked(self) -> None:
        if self._thread is not None:
            return
        self._thread = Thread(target=self._worker, daemon=True, name="koeclone-worker")
        self._thread.start()

    def _worker(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is self._sentinel:
                    return
                job_id = str(item)
                self._transition(job_id, "running")
                try:
                    self._handler(job_id)
                except KoecloneError as error:
                    error_id = uuid4().hex
                    logger.warning(
                        "Job failed job_id=%s error_id=%s code=%s",
                        job_id,
                        error_id,
                        error.code.value,
                    )
                    self._transition(
                        job_id,
                        "failed",
                        error_code=error.code,
                        error_id=error_id,
                    )
                except Exception as error:  # noqa: BLE001 - isolate every job failure
                    error_id = uuid4().hex
                    logger.error(
                        "Job failed job_id=%s error_id=%s exception_type=%s",
                        job_id,
                        error_id,
                        type(error).__name__,
                    )
                    self._transition(
                        job_id,
                        "failed",
                        error_code=ErrorCode.ERR_INTERNAL,
                        error_id=error_id,
                    )
                else:
                    self._transition(job_id, "succeeded")
            finally:
                self._queue.task_done()

    def _transition(
        self,
        job_id: str,
        status: JobStatus,
        *,
        error_code: ErrorCode | None = None,
        error_id: str | None = None,
    ) -> JobState:
        state = JobState(job_id, status, error_code, error_id)
        with self._lock:
            self._states[job_id] = state
            if status in {"succeeded", "failed"}:
                self._completed[job_id].set()
        self._notify(state)
        return state

    def _notify(self, state: JobState) -> None:
        if self._listener is None:
            return
        try:
            self._listener(state)
        except Exception as error:  # noqa: BLE001 - listener must not stop worker
            logger.error(
                "Job state listener failed job_id=%s status=%s exception_type=%s",
                state.job_id,
                state.status,
                type(error).__name__,
            )
