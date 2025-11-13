"""Tests for FastAPI app lifecycle helpers."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import main


def test_configure_sqlalchemy_logging_sets_expected_levels():
    logger_names = [
        "sqlalchemy",
        "sqlalchemy.engine",
        "sqlalchemy.engine.Engine",
        "sqlalchemy.pool",
        "sqlalchemy.pool.impl.AsyncAdaptedQueuePool",
    ]
    original = []
    for name in logger_names:
        logger = logging.getLogger(name)
        original.append((logger, logger.level, logger.propagate))

    try:
        main._configure_sqlalchemy_logging(database_echo=False)
        for logger, _, _ in original:
            assert logger.level == logging.WARNING
            assert logger.propagate is False

        main._configure_sqlalchemy_logging(database_echo=True)
        for logger, _, _ in original:
            assert logger.level == logging.INFO
            assert logger.propagate is True
    finally:
        for logger, level, propagate in original:
            logger.setLevel(level)
            logger.propagate = propagate


def test_request_id_middleware_respects_existing_header(monkeypatch):
    app = FastAPI()
    main._install_request_id_middleware(app)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/ping", headers={main.REQUEST_ID_HEADER: "external-id"})
    assert response.headers[main.REQUEST_ID_HEADER] == "external-id"

    monkeypatch.setattr(main, "uuid4", lambda: "generated-id")
    response = client.get("/ping")
    assert response.headers[main.REQUEST_ID_HEADER] == "generated-id"


@pytest.mark.asyncio
async def test_lifespan_configures_telemetry_and_disposes_engine(monkeypatch):
    fake_settings = SimpleNamespace(
        otel_service_name="svc",
        otel_service_version="1.0.0",
        otel_exporter_otlp_endpoint="http://otel",
        otel_exporter_otlp_headers=None,
        otel_enabled=True,
    )
    configure_calls = {}

    def fake_configure(**kwargs):
        configure_calls.update(kwargs)

    httpx_calls = {}

    def fake_instrument_httpx(*, enabled: bool):
        httpx_calls["enabled"] = enabled

    fake_engine = SimpleNamespace(dispose=AsyncMock())

    monkeypatch.setattr(main, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(main, "configure_opentelemetry", fake_configure)
    monkeypatch.setattr(main, "instrument_httpx", fake_instrument_httpx)
    monkeypatch.setattr(main, "engine", fake_engine)

    async with main.lifespan(FastAPI()):
        assert configure_calls["service_name"] == "svc"
        assert configure_calls["enabled"] is True
        assert httpx_calls["enabled"] is True

    fake_engine.dispose.assert_awaited_once()


def test_create_app_passes_otel_flag_to_fastapi(monkeypatch):
    fake_settings = SimpleNamespace(
        database_echo=False,
        cors_allow_origins=["http://localhost"],
        cors_allow_origin_regex=None,
        otel_enabled=False,
    )
    fastapi_call = {}

    def fake_instrument_fastapi(app: FastAPI, *, enabled: bool):
        fastapi_call["enabled"] = enabled

    monkeypatch.setattr(main, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(main, "instrument_fastapi", fake_instrument_fastapi)
    monkeypatch.setattr(main, "_configure_sqlalchemy_logging", lambda _: None)

    created_app = main.create_app()

    assert isinstance(created_app, FastAPI)
    assert fastapi_call["enabled"] is False
