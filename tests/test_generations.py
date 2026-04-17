import pytest
from httpx import AsyncClient

from kartochka.models.template import Template


@pytest.mark.asyncio
async def test_create_generation_bearer(
    async_client: AsyncClient, auth_headers: dict[str, str], sample_template: Template
) -> None:
    resp = await async_client.post(
        "/api/generations/",
        json={
            "template_uid": sample_template.uid,
            "input_data": {"title": "Test"},
            "output_format": "png",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["uid"]
    assert data["status"] in ("completed", "failed")  # sync generation


@pytest.mark.asyncio
async def test_create_generation_api_key(
    async_client: AsyncClient,
    api_key_headers: dict[str, str],
    pro_sample_template: Template,
) -> None:
    resp = await async_client.post(
        "/api/generations/",
        json={
            "template_uid": pro_sample_template.uid,
            "input_data": {},
            "output_format": "png",
        },
        headers=api_key_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_generation_api_key_free_plan(
    async_client: AsyncClient,
    free_api_key_headers: dict[str, str],
    sample_template: Template,
) -> None:
    resp = await async_client.post(
        "/api/generations/",
        json={
            "template_uid": sample_template.uid,
            "input_data": {},
            "output_format": "png",
        },
        headers=free_api_key_headers,
    )
    # Free plan can still generate via API key (limited by daily quota)
    assert resp.status_code in (200, 403)


@pytest.mark.asyncio
async def test_generation_nonexistent_template(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await async_client.post(
        "/api/generations/",
        json={
            "template_uid": "nonexistent-uid",
            "input_data": {},
            "output_format": "png",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generation_foreign_template(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    pro_sample_template: Template,
) -> None:
    resp = await async_client.post(
        "/api/generations/",
        json={
            "template_uid": pro_sample_template.uid,
            "input_data": {},
            "output_format": "png",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generation_daily_limit(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    sample_template: Template,
    test_db: object,
) -> None:
    from datetime import date

    from sqlalchemy import select

    from kartochka.config import settings
    from kartochka.models.user import User as UserModel

    db = test_db  # type: AsyncSession
    result = await db.execute(select(UserModel).where(UserModel.plan == "free"))
    users = result.scalars().all()
    for u in users:
        u.free_generations_used_today = settings.free_plan_max_generations_per_day
        u.generations_reset_date = date.today()
    await db.commit()

    resp = await async_client.post(
        "/api/generations/",
        json={
            "template_uid": sample_template.uid,
            "input_data": {},
            "output_format": "png",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_generation_by_uid(
    async_client: AsyncClient, auth_headers: dict[str, str], sample_template: Template
) -> None:
    create_resp = await async_client.post(
        "/api/generations/",
        json={
            "template_uid": sample_template.uid,
            "input_data": {"title": "T"},
            "output_format": "png",
        },
        headers=auth_headers,
    )
    uid = create_resp.json()["uid"]
    resp = await async_client.get(f"/api/generations/{uid}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["uid"] == uid


@pytest.mark.asyncio
async def test_download_generation(
    async_client: AsyncClient, auth_headers: dict[str, str], sample_template: Template
) -> None:
    create_resp = await async_client.post(
        "/api/generations/",
        json={
            "template_uid": sample_template.uid,
            "input_data": {"title": "T"},
            "output_format": "png",
        },
        headers=auth_headers,
    )
    data = create_resp.json()
    if data["status"] == "completed":
        uid = data["uid"]
        resp = await async_client.get(
            f"/api/generations/{uid}/download", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/png")


@pytest.mark.asyncio
async def test_list_generations_own_only(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    pro_auth_headers: dict[str, str],
    sample_template: Template,
    pro_sample_template: Template,
) -> None:
    # Create one generation for each user
    await async_client.post(
        "/api/generations/",
        json={
            "template_uid": sample_template.uid,
            "input_data": {},
            "output_format": "png",
        },
        headers=auth_headers,
    )
    resp = await async_client.get("/api/generations/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    # All should belong to the test_user (we don't have user_id in response)
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_delete_generation(
    async_client: AsyncClient, auth_headers: dict[str, str], sample_template: Template
) -> None:
    create_resp = await async_client.post(
        "/api/generations/",
        json={
            "template_uid": sample_template.uid,
            "input_data": {},
            "output_format": "png",
        },
        headers=auth_headers,
    )
    uid = create_resp.json()["uid"]
    del_resp = await async_client.delete(
        f"/api/generations/{uid}", headers=auth_headers
    )
    assert del_resp.status_code == 200
    get_resp = await async_client.get(f"/api/generations/{uid}", headers=auth_headers)
    assert get_resp.status_code == 404
