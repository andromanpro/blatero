"""Local, metadata-free image previews and explicit rectangular redactions."""
from __future__ import annotations

import base64
import hashlib
import io
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

MAX_IMAGES = 8
MAX_RAW = 10 * 1024 * 1024
MAX_PNG = 3 * 1024 * 1024
PROVIDERS = frozenset({"openrouter", "openai", "anthropic", "compatible", "codex"})


def normalize(raw: bytes, masks: list | None = None) -> bytes:
    masks = [] if masks is None else masks
    if len(raw) > MAX_RAW or not isinstance(masks, list) or len(masks) > 40:
        raise ValueError("слишком большое изображение или слишком много областей скрытия")
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.width * source.height > 20_000_000 or getattr(source, "n_frames", 1) != 1:
                raise ValueError("изображение слишком большое или многостраничное; разделите его")
            source.load()
            oriented = ImageOps.exif_transpose(source).convert("RGBA")
            background = Image.new("RGB", oriented.size, "white")
            background.paste(oriented, mask=oriented.getchannel("A"))
            background.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            draw = ImageDraw.Draw(background)
            for rectangle in masks:
                if (not isinstance(rectangle, list) or len(rectangle) != 4
                        or any(type(n) not in (int, float) or not math.isfinite(n) or not 0 <= n <= 1
                               for n in rectangle)):
                    raise ValueError("неверная область скрытия")
                x, y, w, h = rectangle
                if w <= 0 or h <= 0 or x + w > 1.00001 or y + h > 1.00001:
                    raise ValueError("область скрытия выходит за изображение")
                # Outward rounding ensures edge pixels are not left visible.
                draw.rectangle((math.floor(x * background.width), math.floor(y * background.height),
                                math.ceil((x + w) * background.width), math.ceil((y + h) * background.height)), fill="black")
            out = io.BytesIO()
            # New image object: no original EXIF, text chunks, ICC or attachments.
            background.save(out, format="PNG")
            png = out.getvalue()
            if len(png) > MAX_PNG:
                raise ValueError("изображение после подготовки слишком велико; уменьшите его")
            return png
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("изображение повреждено или слишком велико") from exc


def prepare(root: Path, candidates: list[str], selection: list | None = None) -> list[dict]:
    import workspace_context
    selection = selection or []
    if (not isinstance(selection, list) or len(selection) > MAX_IMAGES
            or any(not isinstance(x, dict) or not isinstance(x.get("path"), str) for x in selection)):
        raise ValueError("неверный выбор изображений")
    options = {x["path"]: x.get("masks", []) for x in selection}
    if len(options) != len(selection) or set(options) - set(candidates):
        raise ValueError("выбранное изображение отсутствует в проверяемой папке")
    rows = []
    for relative in candidates[:MAX_IMAGES]:
        path = root / relative
        try:
            resolved = path.resolve(strict=True)
            if (root not in resolved.parents or any(workspace_context._is_link(p)
                    for p in (path, *path.parents) if p != root and root in p.parents)):
                raise ValueError("ссылка на изображение за пределами папки запрещена")
            with resolved.open("rb") as stream:
                raw = stream.read(MAX_RAW + 1)
            png = normalize(raw, options.get(relative, []))
            rows.append({"path": relative, "selected": relative in options,
                         "masks": options.get(relative, []), "sha256": hashlib.sha256(raw).hexdigest(),
                         "data_url": "data:image/png;base64," + base64.b64encode(png).decode("ascii")})
        except (OSError, ValueError) as exc:
            if relative in options:
                raise ValueError("выбранное изображение не удалось подготовить: " + relative) from exc
            rows.append({"path": relative, "error": str(exc) if isinstance(exc, ValueError) else "нет доступа"})
    if set(options) - {x["path"] for x in rows}:
        raise ValueError("слишком много изображений; выберите папку меньшего размера")
    return rows


def selected_png(rows: list[dict]) -> tuple[bytes, ...]:
    return tuple(base64.b64decode(row["data_url"].split(",", 1)[1], validate=True)
                 for row in rows if row.get("selected"))
