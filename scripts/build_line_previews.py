"""Make faithful, upright LINE card previews without changing manual images.

Most photos extracted from the manual are rotated clockwise on the page.
Wide images usually contain two stages of one exercise; keep both stages in
the preview. The three exceptions below are already upright in the source.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "images"
DESTINATION = ROOT / "data" / "line_previews"
SIZE = (960, 720)
ALREADY_UPRIGHT = {
    "04_rower.jpg",
    "37_dumbbell_bench_press.jpg",
    "38_dumbbell_flies.jpg",
}
UPRIGHT_PAIR = {"37_dumbbell_bench_press.jpg", "38_dumbbell_flies.jpg"}


def background(image: Image.Image) -> Image.Image:
    filled = ImageOps.fit(image, SIZE, method=Image.Resampling.LANCZOS)
    return ImageEnhance.Brightness(filled.filter(ImageFilter.GaussianBlur(24))).enhance(0.52)


def paste_contained(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int]) -> None:
    x, y, width, height = box
    fitted = ImageOps.contain(image, (width, height), method=Image.Resampling.LANCZOS)
    canvas.paste(fitted, (x + (width - fitted.width) // 2,
                          y + (height - fitted.height) // 2))


def preview(source: Image.Image, filename: str) -> Image.Image:
    original = source.convert("RGB")
    if filename in UPRIGHT_PAIR:
        # A single full-size stage is clearer on a small card; the original
        # two-stage manual image remains available at /images/<filename>.
        first = original.crop((0, 0, original.width // 2, original.height))
        canvas = background(first)
        paste_contained(canvas, first, (16, 16, 928, 688))
        return canvas
    if filename in ALREADY_UPRIGHT:
        canvas = background(original)
        paste_contained(canvas, original, (16, 16, 928, 688))
        return canvas
    if original.width / original.height >= 1.8:
        # Each half is a sideways portrait of a different movement stage.
        midpoint = original.width // 2
        frames = [original.crop((0, 0, midpoint, original.height)),
                  original.crop((midpoint, 0, original.width, original.height))]
        upright = [frame.transpose(Image.Transpose.ROTATE_270) for frame in frames]
        canvas = background(upright[0])
        paste_contained(canvas, upright[0], (12, 12, 462, 696))
        paste_contained(canvas, upright[1], (486, 12, 462, 696))
        return canvas
    upright = original.transpose(Image.Transpose.ROTATE_270)
    canvas = background(upright)
    paste_contained(canvas, upright, (16, 12, 928, 696))
    return canvas


def main() -> None:
    sources = sorted(SOURCE.glob("*.jpg"))
    if len(sources) != 40:
        raise RuntimeError(f"Expected 40 manual images, found {len(sources)}")
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for path in sources:
        with Image.open(path) as image:
            card = preview(image, path.name)
        card.save(DESTINATION / path.name, format="JPEG", quality=86, optimize=True)
    print(f"Created {len(sources)} faithful previews in {DESTINATION}")


if __name__ == "__main__":
    main()
