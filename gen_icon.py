"""Generate the application icon (assets/icon.ico) using PIL."""

import os
from PIL import Image, ImageDraw, ImageFont


def create_icon(size: int = 256) -> Image.Image:
    """Create a 256x256 icon: dark blue rounded square with white '译' character."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Dark blue rounded rectangle background
    margin = size // 16
    radius = size // 6
    bg_color = (30, 80, 160, 255)
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=radius,
        fill=bg_color,
    )

    # White "译" character in the center
    font_size = int(size * 0.55)
    # Try common CJK fonts on Windows
    font = None
    for font_name in [
        "C:/Windows/Fonts/msyh.ttc",      # Microsoft YaHei
        "C:/Windows/Fonts/msyhbd.ttc",     # Microsoft YaHei Bold
        "C:/Windows/Fonts/simhei.ttf",     # SimHei
        "C:/Windows/Fonts/simsun.ttc",     # SimSun
    ]:
        if os.path.exists(font_name):
            try:
                font = ImageFont.truetype(font_name, font_size)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()

    # Center the text
    text = "译"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2 - bbox[0]
    y = (size - text_h) // 2 - bbox[1]
    draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)

    return img


def main():
    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    os.makedirs(assets_dir, exist_ok=True)

    icon = create_icon(256)

    # Save as .ico (multi-size)
    ico_path = os.path.join(assets_dir, "icon.ico")
    icon.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Icon saved to: {ico_path}")

    # Also save a .png for reference
    png_path = os.path.join(assets_dir, "icon.png")
    icon.save(png_path, format="PNG")
    print(f"PNG saved to: {png_path}")


if __name__ == "__main__":
    main()
