from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageDraw, ImageFont

from kartochka.config import settings
from kartochka.utils.helpers import substitute_variables

# Font cache
_font_cache: dict[str, ImageFont.FreeTypeFont] = {}


def load_font(
    family: str, size: int, bold: bool = False, italic: bool = False
) -> ImageFont.FreeTypeFont:
    style = "Bold" if bold else "Regular"
    if italic:
        style += "Italic"
    cache_key = f"{family}-{style}-{size}"

    if cache_key in _font_cache:
        return _font_cache[cache_key]

    fonts_path = Path(settings.fonts_path)
    # Try different filename patterns
    candidates = [
        fonts_path / f"{family}-{style}.ttf",
        fonts_path / f"{family}{style}.ttf",
        fonts_path / f"{family.lower()}-{style.lower()}.ttf",
        fonts_path / f"{family}-Regular.ttf",
        fonts_path / f"{family}.ttf",
    ]

    font: ImageFont.FreeTypeFont | None = None
    for candidate in candidates:
        if candidate.exists():
            try:
                loaded = ImageFont.truetype(str(candidate), size)
                font = loaded
                break
            except Exception:
                continue

    if font is None:
        # Use default font - wrap in FreeTypeFont-compatible wrapper
        default = ImageFont.load_default()
        # ImageFont.load_default() returns ImageFont.ImageFont, not FreeTypeFont
        # We store it but cast - in practice it works for our usage
        _font_cache[cache_key] = default  # type: ignore[assignment]
        return default  # type: ignore[return-value]

    _font_cache[cache_key] = font
    return font


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current_line = ""

    for word in words:
        test_line = (current_line + " " + word).strip() if current_line else word
        try:
            bbox = font.getbbox(test_line)
            width = bbox[2] - bbox[0]
        except AttributeError:
            # Fallback for default font
            width = len(test_line) * 6
        if width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines if lines else [""]


def draw_rounded_rectangle(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    radius: int,
    fill: str,
    opacity: float = 1.0,
) -> None:
    if opacity < 1.0:
        # Parse hex and add alpha
        hex_color = fill.lstrip("#")
        r_val = int(hex_color[0:2], 16)
        g_val = int(hex_color[2:4], 16)
        b_val = int(hex_color[4:6], 16)
        a_val = int(opacity * 255)
        rgba_color: tuple[int, int, int, int] = (r_val, g_val, b_val, a_val)
        if radius > 0:
            draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=rgba_color)
        else:
            draw.rectangle([x, y, x + w, y + h], fill=rgba_color)
    else:
        if radius > 0:
            draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill)
        else:
            draw.rectangle([x, y, x + w, y + h], fill=fill)


def apply_image_fit(
    img: Image.Image, target_w: int, target_h: int, fit: str
) -> Image.Image:
    src_w, src_h = img.size

    if fit == "fill":
        return img.resize((target_w, target_h), Image.LANCZOS)
    elif fit == "contain":
        ratio = min(target_w / src_w, target_h / src_h)
        new_w = int(src_w * ratio)
        new_h = int(src_h * ratio)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        result = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        offset_x = (target_w - new_w) // 2
        offset_y = (target_h - new_h) // 2
        result.paste(resized, (offset_x, offset_y))
        return result
    else:  # cover (default)
        ratio = max(target_w / src_w, target_h / src_h)
        new_w = int(src_w * ratio)
        new_h = int(src_h * ratio)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        offset_x = (new_w - target_w) // 2
        offset_y = (new_h - target_h) // 2
        return resized.crop(
            (offset_x, offset_y, offset_x + target_w, offset_y + target_h)
        )


async def fetch_image(src: str) -> Image.Image | None:
    try:
        if src.startswith("data:"):
            # base64 encoded
            _, data = src.split(",", 1)
            img_bytes = base64.b64decode(data)
            return Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        elif src.startswith("http://") or src.startswith("https://"):
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(src)
                response.raise_for_status()
                return Image.open(io.BytesIO(response.content)).convert("RGBA")
        else:
            # Local file
            path = Path(settings.storage_path) / "uploads" / src
            if path.exists():
                return Image.open(path).convert("RGBA")
        return None
    except Exception:
        return None


def apply_border_radius_mask(img: Image.Image, radius: int) -> Image.Image:
    if radius <= 0:
        return img
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, img.width, img.height], radius=radius, fill=255)
    result = img.copy()
    result.putalpha(mask)
    return result


async def generate_image(
    canvas_json: str,
    input_data: dict[str, str],
    output_format: str,
    canvas_width: int,
    canvas_height: int,
    output_width: int | None,
    output_height: int | None,
    user_plan: str,
    output_path: Path,
) -> Path:
    try:
        data: dict[str, Any] = json.loads(canvas_json)
    except json.JSONDecodeError:
        data = {}

    layers: list[dict[str, Any]] = data.get("layers", [])
    layers_sorted = sorted(layers, key=lambda la: la.get("zIndex", 0))

    canvas = Image.new("RGBA", (canvas_width, canvas_height), (255, 255, 255, 255))

    for layer in layers_sorted:
        layer_type = layer.get("type", "")
        lx = int(layer.get("x", 0))
        ly = int(layer.get("y", 0))
        lw = int(layer.get("width", 100))
        lh = int(layer.get("height", 100))

        layer_img = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer_img)

        if layer_type == "rectangle":
            fill = layer.get("fill", "#FFFFFF")
            opacity = float(layer.get("opacity", 1.0))
            border_radius = int(layer.get("border_radius", 0))
            draw_rounded_rectangle(draw, lx, ly, lw, lh, border_radius, fill, opacity)

        elif layer_type == "image":
            src = layer.get("src", "")
            src = substitute_variables(src, input_data)
            fit = layer.get("fit", "cover")
            border_radius = int(layer.get("border_radius", 0))

            if src:
                img = await fetch_image(src)
                if img:
                    fitted = apply_image_fit(img, lw, lh, fit)
                    if border_radius > 0:
                        fitted = apply_border_radius_mask(fitted, border_radius)
                    layer_img.paste(fitted, (lx, ly), fitted)

        elif layer_type == "text":
            raw_text = layer.get("text", "")
            text = substitute_variables(raw_text, input_data)
            font_family = layer.get("font_family", "Roboto")
            font_size = int(layer.get("font_size", 16))
            font_bold = bool(layer.get("font_bold", False))
            font_italic = bool(layer.get("font_italic", False))
            color = layer.get("color", "#000000")
            align = layer.get("align", "left")
            max_lines = layer.get("max_lines")
            line_height = float(layer.get("line_height", 1.2))

            font = load_font(font_family, font_size, font_bold, font_italic)
            lines = wrap_text(text, font, lw)

            if max_lines and len(lines) > max_lines:
                lines = lines[:max_lines]
                if lines:
                    last = lines[-1]
                    # Truncate with ellipsis
                    while last:
                        test = last + "\u2026"
                        try:
                            bbox = font.getbbox(test)
                            t_w = bbox[2] - bbox[0]
                        except AttributeError:
                            t_w = len(test) * 6
                        if t_w <= lw:
                            lines[-1] = test
                            break
                        last = last[:-1]

            line_h = int(font_size * line_height)

            for i, line in enumerate(lines):
                y_pos = ly + i * line_h
                if y_pos + line_h > ly + lh:
                    break

                try:
                    bbox = font.getbbox(line)
                    text_w = bbox[2] - bbox[0]
                except AttributeError:
                    text_w = len(line) * 6

                if align == "center":
                    x_pos = lx + (lw - text_w) // 2
                elif align == "right":
                    x_pos = lx + lw - text_w
                else:
                    x_pos = lx

                draw.text((x_pos, y_pos), line, font=font, fill=color)

        elif layer_type == "badge":
            badge_type = layer.get("badge_type", "discount")
            value = layer.get("value", "")
            value = substitute_variables(str(value), input_data)
            bg_color = layer.get("bg_color", "#FF4757")
            text_color = layer.get("text_color", "#FFFFFF")
            border_radius = int(layer.get("border_radius", 8))

            draw_rounded_rectangle(draw, lx, ly, lw, lh, border_radius, bg_color)

            display_value = value
            if badge_type == "discount" and value and "%" not in value:
                display_value = value + "%"

            font_size = min(lh - 8, 24)
            font = load_font("Roboto", font_size, bold=True)

            try:
                bbox = font.getbbox(display_value)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
            except AttributeError:
                text_w = len(display_value) * 6
                text_h = font_size

            tx = lx + (lw - text_w) // 2
            ty = ly + (lh - text_h) // 2

            draw.text((tx, ty), display_value, font=font, fill=text_color)

            if badge_type == "old_price":
                # Strikethrough
                mid_y = ty + text_h // 2
                draw.line([(tx, mid_y), (tx + text_w, mid_y)], fill=text_color, width=2)

        canvas = Image.alpha_composite(canvas, layer_img)

    # Watermark for free plan
    if user_plan == "free":
        wm_draw = ImageDraw.Draw(canvas)
        wm_font = load_font("Roboto", 16)
        wm_text = "kartochka.ru"
        try:
            wm_bbox = wm_font.getbbox(wm_text)
            wm_w = wm_bbox[2] - wm_bbox[0]
        except AttributeError:
            wm_w = len(wm_text) * 6
        wm_x = canvas_width - wm_w - 12
        wm_y = canvas_height - 28
        wm_draw.text((wm_x, wm_y), wm_text, font=wm_font, fill=(170, 170, 170, 153))

    # Resize if needed
    if output_width or output_height:
        new_w = output_width or canvas_width
        new_h = output_height or canvas_height
        canvas = canvas.resize((new_w, new_h), Image.LANCZOS)

    # Save in requested format
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_format.lower() in ("jpg", "jpeg"):
        rgb_canvas = canvas.convert("RGB")
        rgb_canvas.save(output_path, "JPEG", quality=95)
    elif output_format.lower() == "webp":
        canvas.save(output_path, "WEBP", quality=90, lossless=False)
    else:  # PNG
        canvas.save(output_path, "PNG")

    return output_path
