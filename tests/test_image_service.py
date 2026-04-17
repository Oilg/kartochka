import io
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    return tmp_path / "output.png"


def make_simple_canvas(layers: list) -> str:
    return json.dumps({"layers": layers})


@pytest.mark.asyncio
async def test_generate_image_text_layer(tmp_output: Path) -> None:
    from kartochka.services.image_service import generate_image

    canvas = make_simple_canvas(
        [
            {
                "type": "rectangle",
                "id": "bg",
                "x": 0,
                "y": 0,
                "width": 200,
                "height": 100,
                "zIndex": 0,
                "fill": "#FFFFFF",
                "border_radius": 0,
                "opacity": 1.0,
            },
            {
                "type": "text",
                "id": "t",
                "x": 5,
                "y": 5,
                "width": 190,
                "height": 40,
                "zIndex": 1,
                "text": "Hello World",
                "font_family": "Roboto",
                "font_size": 14,
                "font_bold": False,
                "font_italic": False,
                "color": "#000000",
                "align": "left",
                "max_lines": 2,
                "line_height": 1.2,
            },
        ]
    )
    result = await generate_image(
        canvas_json=canvas,
        input_data={},
        output_format="png",
        canvas_width=200,
        canvas_height=100,
        output_width=None,
        output_height=None,
        user_plan="pro",
        output_path=tmp_output,
    )
    assert result.exists()
    assert result.stat().st_size > 0


@pytest.mark.asyncio
async def test_variable_substitution(tmp_output: Path) -> None:
    from kartochka.services.image_service import generate_image

    canvas = make_simple_canvas(
        [
            {
                "type": "text",
                "id": "t",
                "x": 0,
                "y": 0,
                "width": 200,
                "height": 50,
                "zIndex": 0,
                "text": "{{title}}",
                "font_family": "Roboto",
                "font_size": 12,
                "font_bold": False,
                "font_italic": False,
                "color": "#000000",
                "align": "left",
                "max_lines": 1,
                "line_height": 1.0,
            },
        ]
    )
    result = await generate_image(
        canvas_json=canvas,
        input_data={"title": "Мой Товар"},
        output_format="png",
        canvas_width=200,
        canvas_height=100,
        output_width=None,
        output_height=None,
        user_plan="pro",
        output_path=tmp_output,
    )
    assert result.exists()


@pytest.mark.asyncio
async def test_image_layer_with_mock(tmp_output: Path) -> None:
    from kartochka.services.image_service import generate_image

    # Create a fake image response
    fake_img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
    fake_bytes = io.BytesIO()
    fake_img.save(fake_bytes, "PNG")
    fake_bytes.seek(0)

    mock_response = AsyncMock()
    mock_response.content = fake_bytes.read()
    mock_response.raise_for_status = AsyncMock()

    canvas = make_simple_canvas(
        [
            {
                "type": "image",
                "id": "img",
                "x": 0,
                "y": 0,
                "width": 200,
                "height": 100,
                "zIndex": 0,
                "src": "https://example.com/image.png",
                "fit": "cover",
                "border_radius": 0,
            },
        ]
    )

    with patch(
        "kartochka.services.image_service.httpx.AsyncClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await generate_image(
            canvas_json=canvas,
            input_data={},
            output_format="png",
            canvas_width=200,
            canvas_height=100,
            output_width=None,
            output_height=None,
            user_plan="pro",
            output_path=tmp_output,
        )
    assert result.exists()


@pytest.mark.asyncio
async def test_text_wrapping(tmp_output: Path) -> None:
    from kartochka.services.image_service import load_font, wrap_text

    font = load_font("Roboto", 14)
    long_text = "Это очень длинный текст который должен перенестись на следующую строку автоматически"
    lines = wrap_text(long_text, font, max_width=100)
    assert len(lines) > 1


@pytest.mark.asyncio
async def test_text_max_lines(tmp_output: Path) -> None:
    from kartochka.services.image_service import generate_image

    canvas = make_simple_canvas(
        [
            {
                "type": "text",
                "id": "t",
                "x": 0,
                "y": 0,
                "width": 50,
                "height": 60,
                "zIndex": 0,
                "text": "Слово1 Слово2 Слово3 Слово4 Слово5 Слово6 Слово7",
                "font_family": "Roboto",
                "font_size": 14,
                "font_bold": False,
                "font_italic": False,
                "color": "#000000",
                "align": "left",
                "max_lines": 2,
                "line_height": 1.2,
            },
        ]
    )
    result = await generate_image(
        canvas_json=canvas,
        input_data={},
        output_format="png",
        canvas_width=200,
        canvas_height=100,
        output_width=None,
        output_height=None,
        user_plan="pro",
        output_path=tmp_output,
    )
    assert result.exists()


@pytest.mark.asyncio
async def test_output_size(tmp_output: Path) -> None:
    from kartochka.services.image_service import generate_image

    canvas = make_simple_canvas(
        [
            {
                "type": "rectangle",
                "id": "bg",
                "x": 0,
                "y": 0,
                "width": 200,
                "height": 200,
                "zIndex": 0,
                "fill": "#FF0000",
                "border_radius": 0,
                "opacity": 1.0,
            },
        ]
    )
    result = await generate_image(
        canvas_json=canvas,
        input_data={},
        output_format="png",
        canvas_width=200,
        canvas_height=200,
        output_width=100,
        output_height=100,
        user_plan="pro",
        output_path=tmp_output,
    )
    img = Image.open(result)
    assert img.size == (100, 100)


@pytest.mark.asyncio
async def test_watermark_free_plan(tmp_output: Path) -> None:
    from kartochka.services.image_service import generate_image

    canvas = make_simple_canvas(
        [
            {
                "type": "rectangle",
                "id": "bg",
                "x": 0,
                "y": 0,
                "width": 300,
                "height": 200,
                "zIndex": 0,
                "fill": "#FFFFFF",
                "border_radius": 0,
                "opacity": 1.0,
            },
        ]
    )
    result = await generate_image(
        canvas_json=canvas,
        input_data={},
        output_format="png",
        canvas_width=300,
        canvas_height=200,
        output_width=None,
        output_height=None,
        user_plan="free",
        output_path=tmp_output,
    )
    assert result.exists()
    img = Image.open(result)
    assert img.size == (300, 200)


@pytest.mark.asyncio
async def test_no_watermark_pro_plan(tmp_path: Path) -> None:
    from kartochka.services.image_service import generate_image

    output_free = tmp_path / "free.png"
    output_pro = tmp_path / "pro.png"
    canvas = make_simple_canvas(
        [
            {
                "type": "rectangle",
                "id": "bg",
                "x": 0,
                "y": 0,
                "width": 300,
                "height": 200,
                "zIndex": 0,
                "fill": "#FFFFFF",
                "border_radius": 0,
                "opacity": 1.0,
            },
        ]
    )
    await generate_image(
        canvas_json=canvas,
        input_data={},
        output_format="png",
        canvas_width=300,
        canvas_height=200,
        output_width=None,
        output_height=None,
        user_plan="free",
        output_path=output_free,
    )
    await generate_image(
        canvas_json=canvas,
        input_data={},
        output_format="png",
        canvas_width=300,
        canvas_height=200,
        output_width=None,
        output_height=None,
        user_plan="pro",
        output_path=output_pro,
    )
    assert output_free.exists()
    assert output_pro.exists()


@pytest.mark.asyncio
async def test_generate_jpg(tmp_path: Path) -> None:
    from kartochka.services.image_service import generate_image

    output = tmp_path / "out.jpg"
    canvas = make_simple_canvas(
        [
            {
                "type": "rectangle",
                "id": "bg",
                "x": 0,
                "y": 0,
                "width": 100,
                "height": 100,
                "zIndex": 0,
                "fill": "#0000FF",
                "border_radius": 0,
                "opacity": 1.0,
            },
        ]
    )
    result = await generate_image(
        canvas_json=canvas,
        input_data={},
        output_format="jpg",
        canvas_width=100,
        canvas_height=100,
        output_width=None,
        output_height=None,
        user_plan="pro",
        output_path=output,
    )
    assert result.exists()
    img = Image.open(result)
    assert img.format == "JPEG"


@pytest.mark.asyncio
async def test_generate_webp(tmp_path: Path) -> None:
    from kartochka.services.image_service import generate_image

    output = tmp_path / "out.webp"
    canvas = make_simple_canvas(
        [
            {
                "type": "rectangle",
                "id": "bg",
                "x": 0,
                "y": 0,
                "width": 100,
                "height": 100,
                "zIndex": 0,
                "fill": "#00FF00",
                "border_radius": 0,
                "opacity": 1.0,
            },
        ]
    )
    result = await generate_image(
        canvas_json=canvas,
        input_data={},
        output_format="webp",
        canvas_width=100,
        canvas_height=100,
        output_width=None,
        output_height=None,
        user_plan="pro",
        output_path=output,
    )
    assert result.exists()
    img = Image.open(result)
    assert img.format == "WEBP"


@pytest.mark.asyncio
async def test_invalid_image_url_doesnt_crash(tmp_output: Path) -> None:
    from kartochka.services.image_service import generate_image

    canvas = make_simple_canvas(
        [
            {
                "type": "image",
                "id": "img",
                "x": 0,
                "y": 0,
                "width": 100,
                "height": 100,
                "zIndex": 0,
                "src": "https://invalid-url-that-does-not-exist.example.com/img.png",
                "fit": "cover",
                "border_radius": 0,
            },
        ]
    )
    # Should not raise, just produce an image without the layer
    result = await generate_image(
        canvas_json=canvas,
        input_data={},
        output_format="png",
        canvas_width=100,
        canvas_height=100,
        output_width=None,
        output_height=None,
        user_plan="pro",
        output_path=tmp_output,
    )
    assert result.exists()
