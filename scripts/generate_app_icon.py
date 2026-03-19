from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
ICONSET_DIR = ASSETS_DIR / "TRULS.iconset"
PNG_PATH = ASSETS_DIR / "truls-icon-1024.png"
ICNS_PATH = ASSETS_DIR / "TRULS.icns"


def draw_gradient_background(draw: ImageDraw.ImageDraw, size: int) -> None:
    top = (19, 34, 46)
    bottom = (53, 78, 96)
    for y in range(size):
        blend = y / max(1, size - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * blend) for i in range(3))
        draw.line([(0, y), (size, y)], fill=color, width=1)


def draw_grid(base: Image.Image) -> None:
    draw = ImageDraw.Draw(base)
    line = (90, 123, 145, 42)
    for x in range(80, 1024, 96):
        draw.line([(x, 0), (x, 1024)], fill=line, width=2)
    for y in range(80, 1024, 96):
        draw.line([(0, y), (1024, y)], fill=line, width=2)


def generate_icon() -> Image.Image:
    size = 1024
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)

    draw_gradient_background(draw, size)
    draw_grid(base)

    # Outer plate
    draw.rounded_rectangle(
        [(56, 56), (968, 968)],
        radius=220,
        fill=(28, 45, 57, 255),
        outline=(107, 147, 171, 255),
        width=10,
    )

    # Glow behind robot
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse([(210, 180), (814, 784)], fill=(33, 194, 213, 75))
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    base.alpha_composite(glow)

    draw = ImageDraw.Draw(base)

    # Antenna
    draw.rounded_rectangle([(500, 165), (524, 285)], radius=12, fill=(199, 213, 224, 255))
    draw.ellipse([(470, 120), (554, 204)], fill=(42, 223, 227, 255), outline=(195, 252, 255, 255), width=6)

    # Head shadow
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle([(238, 254), (786, 764)], radius=138, fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    base.alpha_composite(shadow, (0, 16))

    draw = ImageDraw.Draw(base)

    # Head shell
    draw.rounded_rectangle(
        [(248, 244), (776, 756)],
        radius=132,
        fill=(220, 229, 237, 255),
        outline=(116, 136, 154, 255),
        width=12,
    )

    # Side bolts
    for x in (276, 748):
        for y in (360, 456, 552):
            draw.ellipse([(x - 16, y - 16), (x + 16, y + 16)], fill=(126, 142, 157, 255))
            draw.line([(x - 8, y), (x + 8, y)], fill=(227, 236, 243, 255), width=4)

    # Visor glasses
    visor_box = [(312, 352), (712, 506)]
    draw.rounded_rectangle(
        visor_box,
        radius=54,
        fill=(25, 48, 66, 255),
        outline=(77, 231, 243, 255),
        width=10,
    )
    draw.rounded_rectangle([(498, 352), (526, 506)], radius=12, fill=(186, 198, 209, 255))

    visor_highlight = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    visor_draw = ImageDraw.Draw(visor_highlight)
    visor_draw.rounded_rectangle([(328, 368), (696, 426)], radius=28, fill=(124, 250, 255, 72))
    visor_highlight = visor_highlight.filter(ImageFilter.GaussianBlur(8))
    base.alpha_composite(visor_highlight)

    draw = ImageDraw.Draw(base)

    # Mouth plate
    draw.rounded_rectangle(
        [(372, 566), (652, 676)],
        radius=36,
        fill=(190, 203, 214, 255),
        outline=(121, 138, 154, 255),
        width=8,
    )

    for x in range(404, 624, 40):
        draw.rounded_rectangle([(x, 594), (x + 18, 646)], radius=8, fill=(82, 105, 120, 255))

    # Jaw and chin
    draw.rounded_rectangle([(420, 690), (604, 732)], radius=20, fill=(104, 124, 140, 255))

    # Corner screws
    for x, y in ((150, 150), (874, 150), (150, 874), (874, 874)):
        draw.ellipse([(x - 18, y - 18), (x + 18, y + 18)], fill=(103, 124, 142, 255))

    return base


def export_iconset(image: Image.Image) -> None:
    if ICONSET_DIR.exists():
        for file in ICONSET_DIR.iterdir():
            file.unlink()
    ICONSET_DIR.mkdir(parents=True, exist_ok=True)

    sizes = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }

    for filename, size in sizes.items():
        resized = image.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(ICONSET_DIR / filename)


def build_icns() -> None:
    subprocess.run(
        ["iconutil", "-c", "icns", str(ICONSET_DIR), "-o", str(ICNS_PATH)],
        check=True,
        cwd=ROOT,
    )


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    image = generate_icon()
    image.save(PNG_PATH)
    export_iconset(image)
    build_icns()
    print(f"Wrote {PNG_PATH}")
    print(f"Wrote {ICNS_PATH}")


if __name__ == "__main__":
    main()
