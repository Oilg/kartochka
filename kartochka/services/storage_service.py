from pathlib import Path

import aiofiles

from kartochka.config import settings
from kartochka.utils.helpers import generate_uid


async def save_upload(data: bytes, extension: str) -> tuple[str, str]:
    """Save uploaded file, return (filename, url)"""
    uid = generate_uid()
    filename = f"{uid}.{extension}"
    folder = Path(settings.storage_path) / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    filepath = folder / filename

    async with aiofiles.open(filepath, "wb") as f:
        await f.write(data)

    url = f"{settings.base_url}/storage/uploads/{filename}"
    return filename, url


async def get_image_dimensions(data: bytes) -> tuple[int, int]:
    import io

    from PIL import Image

    img = Image.open(io.BytesIO(data))
    return img.width, img.height


def get_storage_url(subfolder: str, filename: str) -> str:
    return f"{settings.base_url}/storage/{subfolder}/{filename}"
