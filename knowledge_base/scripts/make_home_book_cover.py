#!/usr/bin/env python3
from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "site" / "assets"
BASE_PATH = ASSETS_DIR / "home-classical-crayon-archive-athena.png"
SOURCE_PATH = Path("/Users/youngkit/Downloads/金色桂冠下的静谧书卷.png")
OUTPUT_PATH = ASSETS_DIR / "home-classical-crayon-archive-book.png"


def is_white_background(pixel: tuple[int, int, int]) -> bool:
    r, g, b = pixel
    return r > 238 and g > 238 and b > 238 and max(pixel) - min(pixel) < 24


def edge_connected_background(image: Image.Image) -> Image.Image:
    width, height = image.size
    pixels = image.load()
    background = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def visit(x: int, y: int) -> None:
        index = y * width + x
        if background[index] or not is_white_background(pixels[x, y]):
            return
        background[index] = 1
        queue.append((x, y))

    for x in range(width):
        visit(x, 0)
        visit(x, height - 1)
    for y in range(height):
        visit(0, y)
        visit(width - 1, y)

    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < width and 0 <= ny < height:
                visit(nx, ny)

    mask = Image.new("L", image.size, 255)
    mask_pixels = mask.load()
    for y in range(height):
        row = y * width
        for x in range(width):
            if background[row + x]:
                mask_pixels[x, y] = 0
    return mask.filter(ImageFilter.GaussianBlur(1.4))


def bbox_from_mask(mask: Image.Image, threshold: int = 8) -> tuple[int, int, int, int]:
    bbox = mask.point(lambda value: 255 if value > threshold else 0).getbbox()
    if bbox is None:
        raise RuntimeError("Could not find a foreground figure in the source image.")
    left, top, right, bottom = bbox
    return max(0, left - 2), max(0, top - 2), min(mask.width, right + 2), min(mask.height, bottom + 2)


def soft_rectangle(size: tuple[int, int], feather: int) -> Image.Image:
    width, height = size
    mask = Image.new("L", size, 0)
    pixels = mask.load()
    for y in range(height):
        for x in range(width):
            edge = min(x, y, width - 1 - x, height - 1 - y)
            pixels[x, y] = 255 if edge >= feather else int(255 * edge / feather)
    return mask.filter(ImageFilter.GaussianBlur(8))


def erase_old_figure(base: Image.Image) -> Image.Image:
    result = base.copy()
    cover_width, cover_height = result.size
    erase_box = (870, 66, 1536, 927)
    left, top, right, bottom = erase_box

    clean_strip = base.crop((792, 0, 1010, cover_height))
    paper = clean_strip.resize((right - left, bottom - top), Image.Resampling.BICUBIC)
    paper = ImageEnhance.Contrast(paper).enhance(0.94)
    result.paste(paper, erase_box, soft_rectangle(paper.size, 58))
    return result


def cut_out_figure(source: Image.Image) -> Image.Image:
    source = source.convert("RGB")
    alpha = edge_connected_background(source)
    crop_box = bbox_from_mask(alpha)
    figure = source.crop(crop_box).convert("RGBA")
    figure.putalpha(alpha.crop(crop_box))
    return figure


def main() -> None:
    base = Image.open(BASE_PATH).convert("RGB")
    source = Image.open(SOURCE_PATH).convert("RGB")

    canvas = erase_old_figure(base).convert("RGBA")
    figure = cut_out_figure(source)

    target_height = 860
    scale = target_height / figure.height
    target_width = round(figure.width * scale)
    figure = figure.resize((target_width, target_height), Image.Resampling.LANCZOS)

    x = 922
    y = 52
    canvas.alpha_composite(figure, (x, y))
    canvas.convert("RGB").save(OUTPUT_PATH, quality=96)
    print(f"Wrote {OUTPUT_PATH} ({canvas.width} x {canvas.height})")


if __name__ == "__main__":
    main()
