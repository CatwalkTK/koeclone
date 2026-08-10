from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from koeclone.config import AppConfig
from koeclone.domain.pronunciation import PronunciationOverride
from koeclone.engines.base import SpeechEngine
from koeclone.engines.chatterbox import ChatterboxEngine
from koeclone.engines.fake import FakeEngine
from koeclone.errors import ErrorCode, KoecloneError
from koeclone.storage.db import Database
from koeclone.storage.files import create_data_directories
from koeclone.worker.pipeline import SynthesisPipeline, SynthesisRequest
from koeclone.worker.queue import JobQueue

MAX_REQUEST_BYTES = 52_428_800
_ROUTER_MODULES = ("consent", "voices", "syntheses")
logger = logging.getLogger(__name__)


class _RequestTooLargeError(Exception):
    pass


class RequestSizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = Headers(scope=scope).get("content-length")
        if declared is not None:
            try:
                length = int(declared)
            except ValueError:
                await _error_response(ErrorCode.ERR_BAD_REQUEST)(scope, receive, send)
                return
            if length > MAX_REQUEST_BYTES:
                await _error_response(ErrorCode.ERR_REQUEST_TOO_LARGE)(
                    scope, receive, send
                )
                return
        received = 0
        started = False

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_REQUEST_BYTES:
                    raise _RequestTooLargeError
            return message

        async def watching_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, watching_send)
        except _RequestTooLargeError:
            if started:
                raise
            await _error_response(ErrorCode.ERR_REQUEST_TOO_LARGE)(scope, receive, send)


_STATUS = {
    ErrorCode.ERR_BAD_REQUEST: 400,
    ErrorCode.ERR_ROUTE_NOT_FOUND: 404,
    ErrorCode.ERR_REQUEST_TOO_LARGE: 413,
    ErrorCode.ERR_DRAFT_NOT_FOUND: 404,
    ErrorCode.ERR_PROFILE_NOT_FOUND: 404,
    ErrorCode.ERR_JOB_NOT_FOUND: 404,
    ErrorCode.ERR_AUDIO_NOT_READY: 409,
    ErrorCode.ERR_AI_DISCLOSURE_REQUIRED: 403,
    ErrorCode.ERR_NO_CONSENT: 403,
    ErrorCode.ERR_PROFILE_ALREADY_EXISTS: 409,
}
_MESSAGES = {
    ErrorCode.ERR_BAD_REQUEST: "リクエストの形式が正しくありません。",
    ErrorCode.ERR_ROUTE_NOT_FOUND: "指定されたAPIは見つかりません。",
    ErrorCode.ERR_REQUEST_TOO_LARGE: "送信データが大きすぎます。",
    ErrorCode.ERR_INTERNAL: "内部エラーが発生しました。",
}


def create_app(
    config: AppConfig,
    *,
    engine: SpeechEngine,
    docs_enabled: bool = False,
    web_dir: Path | None = None,
) -> FastAPI:
    app = FastAPI(
        openapi_url="/openapi.json" if docs_enabled else None,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
    )
    paths = create_data_directories(config.data_dir)
    database = Database(paths.root / "koeclone.sqlite3")
    pipeline = SynthesisPipeline(engine, database, paths, config)

    def handle_job(job_id: str) -> None:
        job = database.get_synthesis_job(job_id)
        if job is None:
            raise KoecloneError(ErrorCode.ERR_JOB_NOT_FOUND)
        raw_overrides = json.loads(job.pronunciation_overrides)
        overrides = tuple(PronunciationOverride(**item) for item in raw_overrides)
        pipeline.run(
            SynthesisRequest(job.id, job.voice_id, job.text, overrides, job.language)
        )

    queue = JobQueue(handle_job)
    queue.start()
    app.state.config = config
    app.state.paths = paths
    app.state.database = database
    app.state.engine = engine
    app.state.pipeline = pipeline
    app.state.queue = queue
    app.state.drafts = {}

    app.add_middleware(RequestSizeLimitMiddleware)

    @app.exception_handler(KoecloneError)
    async def handle_koeclone_error(_: Request, error: KoecloneError) -> JSONResponse:
        return _error_response(error.code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, __: RequestValidationError
    ) -> JSONResponse:
        return _error_response(ErrorCode.ERR_BAD_REQUEST)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        _: Request, error: StarletteHTTPException
    ) -> JSONResponse:
        if error.status_code in {404, 405}:
            return _error_response(
                ErrorCode.ERR_ROUTE_NOT_FOUND,
                status=error.status_code,
            )
        return _error_response(ErrorCode.ERR_INTERNAL)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, __: Exception) -> JSONResponse:
        return _error_response(ErrorCode.ERR_INTERNAL)

    @app.get("/api/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "app_version": config.app_version,
            "engine": engine.engine_name,
            "model_loaded": _model_loaded(engine),
        }

    for name in _ROUTER_MODULES:
        module_name = f"koeclone.api.{name}"
        if importlib.util.find_spec(module_name) is None:
            continue
        module = importlib.import_module(module_name)
        app.include_router(module.router, prefix="/api")

    directory = web_dir or Path(__file__).parents[1] / "web"
    app.mount("/", StaticFiles(directory=directory, html=True), name="web")
    return app


def create_default_app() -> FastAPI:
    config = AppConfig.from_env()
    engine: SpeechEngine
    if config.engine == "fake":
        engine = FakeEngine()
    else:
        engine = ChatterboxEngine.from_config(config)
    docs_enabled = os.environ.get("KOECLONE_DOCS") == "1"
    return create_app(config, engine=engine, docs_enabled=docs_enabled)


def _model_loaded(engine: SpeechEngine) -> bool:
    if hasattr(engine, "load_count"):
        return bool(engine.load_count)
    return getattr(engine, "_model", None) is not None


def _error_response(code: ErrorCode, *, status: int | None = None) -> JSONResponse:
    error_id = str(uuid4()) if code is ErrorCode.ERR_INTERNAL else None
    if error_id is not None:
        logger.error("API internal error error_id=%s code=%s", error_id, code.value)
    response_status = status or _STATUS.get(
        code, 500 if code is ErrorCode.ERR_INTERNAL else 422
    )
    return JSONResponse(
        status_code=response_status,
        content={
            "error": {
                "code": code.value,
                "message": _MESSAGES.get(code, "入力内容を確認してください。"),
                "error_id": error_id,
            }
        },
    )
