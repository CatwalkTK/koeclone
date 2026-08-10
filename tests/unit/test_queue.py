from threading import Event, Lock

import pytest

from koeclone.errors import ErrorCode, KoecloneError
from koeclone.worker.queue import JobQueue, JobState


def test_submit_before_start_is_queued() -> None:
    queue = JobQueue(lambda _: None)

    submitted = queue.submit("job-1")

    assert submitted.status == "queued"
    assert queue.state("job-1") == submitted
    queue.start()
    assert queue.wait_for("job-1").status == "succeeded"
    queue.shutdown()


def test_state_is_running_while_handler_executes() -> None:
    entered = Event()
    release = Event()

    def handler(_: str) -> None:
        entered.set()
        assert release.wait(1)

    queue = JobQueue(handler)
    queue.submit("job-1")
    queue.start()
    assert entered.wait(1)

    assert queue.state("job-1").status == "running"  # type: ignore[union-attr]
    release.set()
    assert queue.wait_for("job-1").status == "succeeded"
    queue.shutdown()


def test_success_has_no_error_information() -> None:
    queue = JobQueue(lambda _: None)
    queue.submit("job-1")
    queue.start()

    state = queue.wait_for("job-1")

    assert state.status == "succeeded"
    assert state.error_code is None
    assert state.error_id is None
    queue.shutdown()


def test_maps_koeclone_error_code(caplog: pytest.LogCaptureFixture) -> None:
    def handler(_: str) -> None:
        raise KoecloneError(ErrorCode.ERR_WATERMARK_NOT_DETECTED)

    queue = JobQueue(handler)
    queue.submit("job-1")
    queue.start()

    state = queue.wait_for("job-1")

    assert state.status == "failed"
    assert state.error_code is ErrorCode.ERR_WATERMARK_NOT_DETECTED
    assert state.error_id
    assert state.error_id in caplog.text
    assert ErrorCode.ERR_WATERMARK_NOT_DETECTED.value in caplog.text
    queue.shutdown()


def test_maps_unexpected_error_to_internal_without_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_message = "sensitive full input"

    def handler(_: str) -> None:
        raise RuntimeError(secret_message)

    queue = JobQueue(handler)
    queue.submit("job-1")
    queue.start()

    state = queue.wait_for("job-1")

    assert state.status == "failed"
    assert state.error_code is ErrorCode.ERR_INTERNAL
    assert state.error_id in caplog.text
    assert secret_message not in repr(state)
    assert secret_message not in caplog.text
    queue.shutdown()


def test_failure_error_ids_are_unique() -> None:
    def handler(_: str) -> None:
        raise RuntimeError

    queue = JobQueue(handler)
    queue.submit("one")
    queue.submit("two")
    queue.start()

    first = queue.wait_for("one")
    second = queue.wait_for("two")

    assert first.error_id
    assert second.error_id
    assert first.error_id != second.error_id
    queue.shutdown()


def test_jobs_execute_serially() -> None:
    counter_lock = Lock()
    active = 0
    maximum_active = 0

    def handler(_: str) -> None:
        nonlocal active, maximum_active
        with counter_lock:
            active += 1
            maximum_active = max(maximum_active, active)
        with counter_lock:
            active -= 1

    queue = JobQueue(handler)
    queue.submit("one")
    queue.submit("two")
    queue.start()
    queue.wait_for("one")
    queue.wait_for("two")

    assert maximum_active == 1
    queue.shutdown()


def test_jobs_execute_in_submission_order() -> None:
    calls: list[str] = []
    queue = JobQueue(calls.append)
    for job_id in ("one", "two", "three"):
        queue.submit(job_id)
    queue.start()
    for job_id in ("one", "two", "three"):
        queue.wait_for(job_id)

    assert calls == ["one", "two", "three"]
    queue.shutdown()


def test_failure_does_not_stop_next_job() -> None:
    def handler(job_id: str) -> None:
        if job_id == "bad":
            raise RuntimeError

    queue = JobQueue(handler)
    queue.submit("bad")
    queue.submit("good")
    queue.start()

    assert queue.wait_for("bad").status == "failed"
    assert queue.wait_for("good").status == "succeeded"
    queue.shutdown()


def test_rejects_duplicate_job_id() -> None:
    queue = JobQueue(lambda _: None)
    queue.submit("job-1")

    with pytest.raises(ValueError):
        queue.submit("job-1")

    queue.start()
    queue.wait_for("job-1")
    queue.shutdown()


def test_wait_for_times_out_without_polling() -> None:
    release = Event()

    def handler(_: str) -> None:
        assert release.wait(1)

    queue = JobQueue(handler)
    queue.submit("job-1")
    queue.start()

    with pytest.raises(TimeoutError):
        queue.wait_for("job-1", timeout=0.01)

    release.set()
    queue.wait_for("job-1")
    queue.shutdown()


def test_rejects_submit_after_shutdown() -> None:
    queue = JobQueue(lambda _: None)
    queue.start()
    queue.shutdown()

    with pytest.raises(RuntimeError):
        queue.submit("job-1")


def test_listener_receives_each_transition() -> None:
    statuses: list[str] = []
    queue = JobQueue(lambda _: None, listener=lambda state: statuses.append(state.status))
    queue.submit("job-1")
    queue.start()
    queue.wait_for("job-1")
    queue.shutdown()

    assert statuses == ["queued", "running", "succeeded"]


def test_listener_receives_queued_first_when_worker_already_started() -> None:
    handler_entered = Event()
    statuses: list[str] = []

    def handler(_: str) -> None:
        handler_entered.set()

    def listener(state: JobState) -> None:
        status = state.status
        if status == "queued":
            handler_entered.wait(0.05)
        statuses.append(status)

    queue = JobQueue(handler, listener=listener)
    queue.start()
    queue.submit("job-1")
    queue.wait_for("job-1")
    queue.shutdown()

    assert statuses == ["queued", "running", "succeeded"]


def test_listener_failure_does_not_stop_worker() -> None:
    def listener(_: object) -> None:
        raise RuntimeError("listener failure")

    queue = JobQueue(lambda _: None, listener=listener)
    queue.submit("job-1")
    queue.start()

    assert queue.wait_for("job-1").status == "succeeded"
    queue.shutdown()
