import asyncio
import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from kartochka.database import Base, get_db
from kartochka.models.catalog_batch import CatalogBatch  # noqa: F401
from kartochka.models.catalog_item import CatalogItem  # noqa: F401
from kartochka.models.marketplace_credential import MarketplaceCredential  # noqa: F401
from kartochka.models.subscription import Subscription  # noqa: F401
from kartochka.models.template import Template
from kartochka.models.user import User
from kartochka.services.auth_service import create_access_token, hash_password

TEST_DB_URL = "sqlite+aiosqlite:///./test_kartochka.db"

test_engine = create_async_engine(
    TEST_DB_URL, echo=False, connect_args={"check_same_thread": False}
)
test_session_maker = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def test_db(setup_db: None) -> AsyncSession:
    async with test_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def async_client(test_db: AsyncSession) -> AsyncClient:
    from kartochka.main import app

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(test_db: AsyncSession) -> User:
    user = User(
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("testpassword123"),
        full_name="Test User",
        api_key=str(uuid.uuid4()),
        plan="free",
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def pro_user(test_db: AsyncSession) -> User:
    user = User(
        email=f"pro_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("testpassword123"),
        full_name="Pro User",
        api_key=str(uuid.uuid4()),
        plan="pro",
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict[str, str]:
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def pro_auth_headers(pro_user: User) -> dict[str, str]:
    token = create_access_token(pro_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def api_key_headers(pro_user: User) -> dict[str, str]:
    return {"X-API-Key": pro_user.api_key}


@pytest_asyncio.fixture
async def free_api_key_headers(test_user: User) -> dict[str, str]:
    return {"X-API-Key": test_user.api_key}


@pytest_asyncio.fixture
async def sample_template(test_db: AsyncSession, test_user: User) -> Template:
    t = Template(
        uid=str(uuid.uuid4()),
        user_id=test_user.id,
        name="Test Template",
        marketplace="universal",
        canvas_json=json.dumps(
            {
                "layers": [
                    {
                        "type": "rectangle",
                        "id": "bg",
                        "x": 0,
                        "y": 0,
                        "width": 100,
                        "height": 100,
                        "zIndex": 0,
                        "fill": "#FFFFFF",
                        "border_radius": 0,
                        "opacity": 1.0,
                    },
                    {
                        "type": "text",
                        "id": "title",
                        "x": 5,
                        "y": 5,
                        "width": 90,
                        "height": 30,
                        "zIndex": 1,
                        "text": "{{title}}",
                        "font_family": "Roboto",
                        "font_size": 12,
                        "font_bold": False,
                        "font_italic": False,
                        "color": "#000000",
                        "align": "left",
                        "max_lines": 2,
                        "line_height": 1.2,
                    },
                ]
            }
        ),
        variables=json.dumps(
            [{"name": "title", "label": "Заголовок", "default": "Тест"}]
        ),
        canvas_width=100,
        canvas_height=100,
    )
    test_db.add(t)
    await test_db.commit()
    await test_db.refresh(t)
    return t


@pytest_asyncio.fixture
async def pro_sample_template(test_db: AsyncSession, pro_user: User) -> Template:
    t = Template(
        uid=str(uuid.uuid4()),
        user_id=pro_user.id,
        name="Pro Template",
        marketplace="wb",
        canvas_json=json.dumps(
            {
                "layers": [
                    {
                        "type": "rectangle",
                        "id": "bg",
                        "x": 0,
                        "y": 0,
                        "width": 100,
                        "height": 100,
                        "zIndex": 0,
                        "fill": "#FFFFFF",
                        "border_radius": 0,
                        "opacity": 1.0,
                    },
                ]
            }
        ),
        variables=json.dumps([]),
        canvas_width=100,
        canvas_height=100,
    )
    test_db.add(t)
    await test_db.commit()
    await test_db.refresh(t)
    return t
