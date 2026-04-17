import pytest
from httpx import AsyncClient

from kartochka.models.template import Template

TEMPLATE_DATA = {
    "name": "My Template",
    "marketplace": "wb",
    "canvas_json": '{"layers": []}',
    "variables": "[]",
    "canvas_width": 900,
    "canvas_height": 1200,
}


@pytest.mark.asyncio
async def test_create_template_success(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await async_client.post(
        "/api/templates/", json=TEMPLATE_DATA, headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "uid" in data
    assert data["name"] == "My Template"


@pytest.mark.asyncio
async def test_create_template_unauthorized(async_client: AsyncClient) -> None:
    resp = await async_client.post("/api/templates/", json=TEMPLATE_DATA)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_templates_own_only(
    async_client: AsyncClient, auth_headers: dict[str, str], sample_template: Template
) -> None:
    resp = await async_client.get("/api/templates/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    uids = [t["uid"] for t in data]
    assert sample_template.uid in uids


@pytest.mark.asyncio
async def test_get_template_by_uid(
    async_client: AsyncClient, auth_headers: dict[str, str], sample_template: Template
) -> None:
    resp = await async_client.get(
        f"/api/templates/{sample_template.uid}", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["uid"] == sample_template.uid


@pytest.mark.asyncio
async def test_get_foreign_template(
    async_client: AsyncClient,
    pro_auth_headers: dict[str, str],
    sample_template: Template,
) -> None:
    resp = await async_client.get(
        f"/api/templates/{sample_template.uid}", headers=pro_auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_template(
    async_client: AsyncClient, auth_headers: dict[str, str], sample_template: Template
) -> None:
    resp = await async_client.put(
        f"/api/templates/{sample_template.uid}",
        json={"name": "Updated Name"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_foreign_template(
    async_client: AsyncClient,
    pro_auth_headers: dict[str, str],
    sample_template: Template,
) -> None:
    resp = await async_client.put(
        f"/api/templates/{sample_template.uid}",
        json={"name": "Hacked"},
        headers=pro_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_template(
    async_client: AsyncClient, auth_headers: dict[str, str], test_db: object
) -> None:
    create_resp = await async_client.post(
        "/api/templates/", json=TEMPLATE_DATA, headers=auth_headers
    )
    uid = create_resp.json()["uid"]
    del_resp = await async_client.delete(f"/api/templates/{uid}", headers=auth_headers)
    assert del_resp.status_code == 200
    get_resp = await async_client.get(f"/api/templates/{uid}", headers=auth_headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_foreign_template(
    async_client: AsyncClient,
    pro_auth_headers: dict[str, str],
    sample_template: Template,
) -> None:
    resp = await async_client.delete(
        f"/api/templates/{sample_template.uid}", headers=pro_auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_template_limit_free_plan(
    async_client: AsyncClient, auth_headers: dict[str, str], test_db: object
) -> None:
    from kartochka.config import settings

    # Create templates up to the limit
    for i in range(settings.free_plan_max_templates):
        await async_client.post(
            "/api/templates/",
            json={**TEMPLATE_DATA, "name": f"T{i}"},
            headers=auth_headers,
        )
    # One more should fail
    resp = await async_client.post(
        "/api/templates/",
        json={**TEMPLATE_DATA, "name": "Over limit"},
        headers=auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_filter_by_marketplace(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await async_client.post(
        "/api/templates/",
        json={**TEMPLATE_DATA, "name": "WB", "marketplace": "wb"},
        headers=auth_headers,
    )
    await async_client.post(
        "/api/templates/",
        json={**TEMPLATE_DATA, "name": "OZ", "marketplace": "ozon"},
        headers=auth_headers,
    )
    resp = await async_client.get(
        "/api/templates/?marketplace=ozon", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    for t in data:
        assert t["marketplace"] == "ozon"
