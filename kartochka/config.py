from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Карточка"
    app_env: str = "development"
    secret_key: str = "dev-secret-key"
    access_token_expire_minutes: int = 1440
    base_url: str = "http://localhost:8000"
    database_url: str = (
        "postgresql+asyncpg://kartochka:kartochka_dev_password@localhost:5432/kartochka"
    )
    test_database_url: str = "sqlite+aiosqlite:///./test.db"
    storage_path: str = "./storage"
    fonts_path: str = "./fonts"
    free_plan_max_templates: int = 3
    free_plan_max_generations_per_day: int = 10
    redis_url: str = "redis://localhost:6379/0"
    encryption_key: str = ""
    telegram_bot_token: str = ""
    max_batch_size: int = 500
    batch_chunk_size: int = 10
    publish_chunk_size: int = 20
    publish_chunk_delay: int = 3
    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""
    pro_plan_price_rub: int = 1490

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
