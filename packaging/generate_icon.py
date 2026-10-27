"""
packaging/generate_icon.py - Generates an original multi-resolution Windows .ico icon.

Aesthetic:
- Retro-futuristic timeline clock companion.
- Warm amber/orange bezel with subtle radiant glow.
- Ivory clock face with precise hour indices and hands pointing to 10:10.
- Central cyan/gold quantum core symbolizing AI co-pilot intelligence.
- Multi-resolution ICO: 16x16, 32x32, 48x48, 64x64, 128x128, 256x256.
- 100% original artwork (no copyrighted assets).
"""

import math
from PIL import Image, ImageDraw


def create_clock_icon(size: int = 256) -> Image.Image:
    # High-res master canvas with transparency
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center = size / 2.0
    radius = size * 0.44

    # Outer soft glow ring
    glow_color = (245, 158, 11, 40)
    for g in range(int(size * 0.04), 0, -2):
        r_glow = radius + g
        draw.ellipse(
            [center - r_glow, center - r_glow, center + r_glow, center + r_glow],
            outline=glow_color,
            width=2,
        )

    # Outer metallic bezel (warm amber/bronze)
    bezel_outer = radius
    bezel_inner = radius * 0.86
    draw.ellipse(
        [center - bezel_outer, center - bezel_outer, center + bezel_outer, center + bezel_outer],
        fill=(217, 119, 6, 255),  # Deep amber
        outline=(180, 83, 9, 255),
        width=int(size * 0.015),
    )

    # Dial face (warm ivory/cream with slight radial illumination)
    draw.ellipse(
        [center - bezel_inner, center - bezel_inner, center + bezel_inner, center + bezel_inner],
        fill=(254, 243, 199, 255),  # Light warm cream
        outline=(245, 158, 11, 255),
        width=int(size * 0.01),
    )

    # 12 Hour tick marks
    tick_length_major = radius * 0.12
    tick_length_minor = radius * 0.06
    for i in range(12):
        angle_rad = math.radians(i * 30 - 90)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        is_cardinal = (i % 3 == 0)
        t_len = tick_length_major if is_cardinal else tick_length_minor
        w = max(2, int(size * (0.02 if is_cardinal else 0.012)))

        p_outer = (center + (bezel_inner - size * 0.02) * cos_a, center + (bezel_inner - size * 0.02) * sin_a)
        p_inner = (center + (bezel_inner - size * 0.02 - t_len) * cos_a, center + (bezel_inner - size * 0.02 - t_len) * sin_a)

        tick_col = (146, 64, 14, 255) if is_cardinal else (180, 83, 9, 200)
        draw.line([p_inner, p_outer], fill=tick_col, width=w)

    # Clock Hands (pointing to 10:10 for classic aesthetic)
    # Hour hand: points towards 10 o'clock (-60 deg)
    hour_angle = math.radians(300 - 90)
    hour_len = radius * 0.48
    hour_w = max(3, int(size * 0.035))
    h_end = (center + hour_len * math.cos(hour_angle), center + hour_len * math.sin(hour_angle))
    draw.line([(center, center), h_end], fill=(120, 53, 15, 255), width=hour_w)

    # Minute hand: points towards 2 o'clock (+60 deg)
    min_angle = math.radians(60 - 90)
    min_len = radius * 0.68
    min_w = max(2, int(size * 0.024))
    m_end = (center + min_len * math.cos(min_angle), center + min_len * math.sin(min_angle))
    draw.line([(center, center), m_end], fill=(180, 83, 9, 255), width=min_w)

    # Center Hub / Quantum Core (AI intelligence node)
    core_r = radius * 0.14
    draw.ellipse(
        [center - core_r, center - core_r, center + core_r, center + core_r],
        fill=(14, 165, 233, 255),  # Cyan intelligence glow
        outline=(3, 105, 161, 255),
        width=int(size * 0.015),
    )
    center_pin_r = radius * 0.06
    draw.ellipse(
        [center - center_pin_r, center - center_pin_r, center + center_pin_r, center + center_pin_r],
        fill=(255, 255, 255, 255),
    )

    return img


def main():
    master_icon = create_clock_icon(size=256)
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon_images = [master_icon.resize(s, Image.Resampling.LANCZOS) for s in sizes]

    ico_path = "packaging/MissMinutes.ico"
    png_path = "packaging/MissMinutes.png"

    master_icon.save(png_path, format="PNG")
    icon_images[0].save(
        ico_path,
        format="ICO",
        sizes=sizes,
        append_images=icon_images[1:],
    )
    print(f"[OK] Generated Windows icon: {ico_path} and master PNG: {png_path}")


if __name__ == "__main__":
    main()
