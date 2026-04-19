"""
Security-focused tests: SSRF, path traversal, canvas validation,
watermark behaviour, health/metrics endpoints.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from kartochka.models.generation import Generation
from kartochka.models.user import User
from kartochka.services.image_service import generate_image, is_safe_url

# ---------------------------------------------------------------------------
# SSRF protection — is_safe_url
# ---------------------------------------------------------------------------


class TestIsSafeUrl:
    def test_public_https_url_allowed(self):
        assert is_safe_url("https://example.com/image.jpg") is True

    def test_public_http_url_allowed(self):
        assert is_safe_url("http://cdn.example.com/photo.png") is True

    def test_localhost_blocked(self):
        assert is_safe_url("http://localhost/secret") is False

    def test_127_blocked(self):
        assert is_safe_url("http://127.0.0.1/admin") is False

    def test_private_class_a_blocked(self):
        assert is_safe_url("http://10.0.0.1/data") is False

    def test_private_class_b_blocked(self):
        assert is_safe_url("http://172.16.0.1/data") is False

    def test_private_class_c_blocked(self):
        assert is_safe_url("http://192.168.1.1/data") is False

    def test_link_local_blocked(self):
        assert is_safe_url("http://169.254.169.254/latest/meta-data/") is False

    def test_metadata_google_blocked(self):
        assert (
            is_safe_url("http://metadata.google.internal/computeMetadata/v1/") is False
        )

    def test_dotlocal_blocked(self):
        assert is_safe_url("http://myservice.local/api") is False

    def test_dotinternal_blocked(self):
        assert is_safe_url("http://db.internal/query") is False

    def test_empty_url_blocked(self):
        assert is_safe_url("") is False

    def test_malformed_url_blocked(self):
        assert is_safe_url("not-a-url") is False


# ---------------------------------------------------------------------------
# SSRF in fetch_image — HTTP URLs to private IPs must not be fetched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_image_blocks_private_ip():
    """fetch_image must return None for SSRF-unsafe URLs without making HTTP requests."""
    from kartochka.services.image_service import fetch_image

    with patch("kartochka.services.image_service.httpx.AsyncClient") as mock_client_cls:
        result = await fetch_image("http://192.168.1.100/secret.png")

    assert result is None
    mock_client_cls.assert_not_called()


# ---------------------------------------------------------------------------
# Watermark — only on preview, not on final generation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_watermark_absent_on_final_generation(tmp_path: Path):
    canvas_json = json.dumps(
        {
            "layers": [
                {
                    "type": "rectangle",
                    "id": "bg",
                    "x": 0,
                    "y": 0,
                    "width": 200,
                    "height": 200,
                    "zIndex": 0,
                    "fill": "#FFFFFF",
                    "border_radius": 0,
                    "opacity": 1.0,
                }
            ]
        }
    )
    output_path = tmp_path / "final.png"
    await generate_image(
        canvas_json=canvas_json,
        input_data={},
        output_format="png",
        canvas_width=200,
        canvas_height=200,
        output_width=None,
        output_height=None,
        user_plan="free",
        output_path=output_path,
        is_preview=False,
    )
    assert output_path.exists()
    img = Image.open(output_path).convert("RGBA")
    # The canvas should be pure white — no semi-transparent grey pixels
    # that a watermark text would introduce in the bottom-right corner
    pixels = list(img.getdata())
    non_white = [p for p in pixels if p[:3] != (255, 255, 255)]
    assert len(non_white) == 0, "Final image for free plan must not contain watermark"


@pytest.mark.asyncio
async def test_watermark_present_on_preview(tmp_path: Path):
    canvas_json = json.dumps(
        {
            "layers": [
                {
                    "type": "rectangle",
                    "id": "bg",
                    "x": 0,
                    "y": 0,
                    "width": 200,
                    "height": 200,
                    "zIndex": 0,
                    "fill": "#FFFFFF",
                    "border_radius": 0,
                    "opacity": 1.0,
                }
            ]
        }
    )
    output_path = tmp_path / "preview.png"
    await generate_image(
        canvas_json=canvas_json,
        input_data={},
        output_format="png",
        canvas_width=200,
        canvas_height=200,
        output_width=None,
        output_height=None,
        user_plan="free",
        output_path=output_path,
        is_preview=True,
    )
    assert output_path.exists()
    img = Image.open(output_path).convert("RGBA")
    pixels = list(img.getdata())
    non_white = [p for p in pixels if p[:3] != (255, 255, 255)]
    assert len(non_white) > 0, "Preview for free plan must contain watermark pixels"


# ---------------------------------------------------------------------------
# Canvas size validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_canvas_size_validation_too_large(
    async_client: AsyncClient, auth_headers: dict
):
    resp = await async_client.post(
        "/api/templates/",
        json={
            "name": "Huge Canvas",
            "canvas_width": 9999,
            "canvas_height": 9999,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_canvas_size_validation_too_small(
    async_client: AsyncClient, auth_headers: dict
):
    resp = await async_client.post(
        "/api/templates/",
        json={
            "name": "Tiny Canvas",
            "canvas_width": 10,
            "canvas_height": 10,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_canvas_size_validation_valid(
    async_client: AsyncClient, auth_headers: dict
):
    resp = await async_client.post(
        "/api/templates/",
        json={
            "name": "Valid Canvas",
            "canvas_width": 1000,
            "canvas_height": 1000,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Path traversal — download endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_path_traversal_blocked(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
    test_user: User,
):
    """A generation whose file_path points outside storage root must return 403."""
    gen_uid = str(uuid.uuid4())
    gen = Generation(
        uid=gen_uid,
        user_id=test_user.id,
        template_id=1,
        input_data="{}",
        status="completed",
        output_format="png",
        file_path="/etc/passwd",  # malicious path
    )
    test_db.add(gen)
    await test_db.commit()

    resp = await async_client.get(
        f"/api/generations/{gen_uid}/download",
        headers=auth_headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_returns_ok(async_client: AsyncClient):
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"


# ---------------------------------------------------------------------------
# Metrics endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metrics_returns_prometheus_format(async_client: AsyncClient):
    resp = await async_client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    content = resp.text
    # Our custom metrics must be present
    assert "kartochka_generations_total" in content
    assert "kartochka_active_users_30d" in content


# ---------------------------------------------------------------------------
# MAU — last_active_at updated on authenticated request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_last_active_at_updated_on_request(
    async_client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    test_db: AsyncSession,
):
    """Authenticated request must update last_active_at."""
    from datetime import datetime

    assert test_user.last_active_at is None

    await async_client.get("/api/auth/me", headers=auth_headers)

    await test_db.refresh(test_user)
    assert test_user.last_active_at is not None
    delta = datetime.now(UTC) - test_user.last_active_at.replace(tzinfo=UTC)
    assert delta.total_seconds() < 10


@pytest.mark.asyncio
async def test_mau_counted_in_metrics(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
    test_user: User,
):
    """After an authenticated request the MAU gauge must be >= 1."""
    # Make one request so last_active_at is set
    await async_client.get("/api/auth/me", headers=auth_headers)

    resp = await async_client.get("/metrics")
    assert resp.status_code == 200
    # Find the MAU gauge line
    mau_line = next(
        (
            line
            for line in resp.text.splitlines()
            if line.startswith("kartochka_active_users_30d ")
        ),
        None,
    )
    assert mau_line is not None
    value = float(mau_line.split()[-1])
    assert value >= 1
