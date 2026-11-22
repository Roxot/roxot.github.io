#!/usr/bin/env python3
"""Regenerate the sampling-path favicon family using only Python's standard library.

Run from any directory: python3 /path/to/site/static/scripts/gen_favicon.py
The SVG and raster exports share the geometry below. Raster edges use deterministic
supersampling; no font, random seed, image library, or external renderer is required.
"""

from math import ceil, floor, hypot, sqrt
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"
INK = (41, 78, 64, 255)          # #294e40
IVORY = (247, 244, 233, 255)     # #f7f4e9
GOLD = (216, 181, 109, 255)      # #d8b56d
STROKE = 4.0
SOURCE = (14, 32)
FORK = (23, 32)
# Draw the selected upper branch last so the shared stem also shows its selection.
BRANCHES = (
    ((35, 32), (38, 32), (50, 32), IVORY, 3.8),
    ((35, 32), (34, 48), (50, 48), IVORY, 3.8),
    ((35, 32), (34, 16), (50, 16), GOLD, 4.6),
)


def hex_color(color):
    return "#" + "".join(f"{channel:02x}" for channel in color[:3])


def svg(monochrome=False):
    lines = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">']
    if not monochrome:
        lines.append(f'  <rect width="64" height="64" rx="12" fill="{hex_color(INK)}"/>')
    for control_a, control_b, end, color, radius in BRANCHES:
        fill = "#000000" if monochrome else hex_color(color)
        path = (f"M{SOURCE[0]} {SOURCE[1]}H{FORK[0]}"
                f"C{control_a[0]} {control_a[1]} {control_b[0]} {control_b[1]} {end[0]} {end[1]}")
        lines.append(f'  <path d="{path}" fill="none" stroke="{fill}" stroke-width="{STROKE:g}" stroke-linecap="round"/>')
        lines.append(f'  <circle cx="{end[0]}" cy="{end[1]}" r="{radius:g}" fill="{fill}"/>')
    fill = "#000000" if monochrome else hex_color(IVORY)
    lines.append(f'  <circle cx="{SOURCE[0]}" cy="{SOURCE[1]}" r="4" fill="{fill}"/>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


class Raster:
    """A tiny opaque-shape rasterizer with transparent canvas and antialiased export."""

    def __init__(self, size):
        self.size = size
        self.samples = 4 if size <= 192 else 2
        self.width = size * self.samples
        self.scale = self.width / 64
        self.pixels = bytearray(self.width * self.width * 4)

    def span(self, y, left, right, color):
        start = max(0, ceil(left - 0.5))
        stop = min(self.width, ceil(right - 0.5))
        if 0 <= y < self.width and stop > start:
            offset = (y * self.width + start) * 4
            self.pixels[offset:offset + (stop - start) * 4] = bytes(color) * (stop - start)

    def rounded_tile(self, radius, color):
        radius *= self.scale
        for y in range(self.width):
            center_y = y + 0.5
            distance = max(radius - center_y, center_y - (self.width - radius), 0)
            inset = radius - sqrt(max(0, radius * radius - distance * distance))
            self.span(y, inset, self.width - inset, color)

    def circle(self, x, y, radius, color):
        x, y, radius = x * self.scale, y * self.scale, radius * self.scale
        for row in range(max(0, floor(y - radius)), min(self.width, ceil(y + radius))):
            delta = row + 0.5 - y
            if abs(delta) < radius:
                half = sqrt(radius * radius - delta * delta)
                self.span(row, x - half, x + half, color)

    def polygon(self, points, color):
        points = [(x * self.scale, y * self.scale) for x, y in points]
        edges = list(zip(points, points[1:] + points[:1]))
        for row in range(max(0, floor(min(y for _, y in points))),
                         min(self.width, ceil(max(y for _, y in points)))):
            y = row + 0.5
            intersections = []
            for (x1, y1), (x2, y2) in edges:
                if min(y1, y2) <= y < max(y1, y2):
                    intersections.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
            intersections.sort()
            for left, right in zip(intersections[::2], intersections[1::2]):
                self.span(row, left, right, color)

    def branch(self, control_a, control_b, end, color):
        # Offset the sampled cubic along its exact tangent to form its stroke.
        top = [(SOURCE[0], SOURCE[1] + STROKE / 2)]
        bottom = [(SOURCE[0], SOURCE[1] - STROKE / 2)]
        for step in range(129):
            t = step / 128
            u = 1 - t
            x, y = [u**3 * FORK[k] + 3 * u*u*t * control_a[k]
                    + 3 * u*t*t * control_b[k] + t**3 * end[k] for k in (0, 1)]
            dx, dy = [3 * u*u * (control_a[k] - FORK[k])
                      + 6 * u*t * (control_b[k] - control_a[k])
                      + 3 * t*t * (end[k] - control_b[k]) for k in (0, 1)]
            length = hypot(dx, dy)
            nx, ny = -dy / length * STROKE / 2, dx / length * STROKE / 2
            top.append((x + nx, y + ny))
            bottom.append((x - nx, y - ny))
        self.polygon(top + list(reversed(bottom)), color)
        self.circle(*SOURCE, STROKE / 2, color)
        self.circle(*end, STROKE / 2, color)

    def png(self):
        raw = bytearray()
        samples, width, pixels = self.samples, self.width, self.pixels
        for y in range(self.size):
            raw.append(0)  # PNG filter: none.
            for x in range(self.size):
                red = green = blue = alpha = 0
                for sy in range(samples):
                    offset = ((y * samples + sy) * width + x * samples) * 4
                    for sx in range(samples):
                        index = offset + sx * 4
                        red += pixels[index]
                        green += pixels[index + 1]
                        blue += pixels[index + 2]
                        alpha += pixels[index + 3]
                # All painted samples are opaque. Unpremultiply edge pixels so
                # rounded corners remain clean against light and dark browser UI.
                if alpha:
                    raw.extend((round(red * 255 / alpha), round(green * 255 / alpha),
                                round(blue * 255 / alpha), round(alpha / (samples * samples))))
                else:
                    raw.extend((0, 0, 0, 0))

        def chunk(kind, data):
            return (struct.pack(">I", len(data)) + kind + data
                    + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

        header = struct.pack(">IIBBBBB", self.size, self.size, 8, 6, 0, 0, 0)
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def raster_png(size):
    image = Raster(size)
    image.rounded_tile(12, INK)
    for control_a, control_b, end, color, radius in BRANCHES:
        image.branch(control_a, control_b, end, color)
        image.circle(*end, radius, color)
    image.circle(*SOURCE, 4, IVORY)
    return image.png()


def icon(images):
    """Pack PNG-backed 16, 32 and 48px images in a standard multi-resolution ICO."""
    offset = 6 + len(images) * 16
    directory = bytearray(struct.pack("<HHH", 0, 1, len(images)))
    payload = bytearray()
    for size, png in images:
        directory.extend(struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(png), offset))
        payload.extend(png)
        offset += len(png)
    return bytes(directory + payload)


def main():
    (STATIC / "favicon.svg").write_text(svg(), encoding="utf-8")
    (STATIC / "safari-pinned-tab.svg").write_text(svg(monochrome=True), encoding="utf-8")
    exports = {
        16: STATIC / "favicon-16x16.png",
        32: STATIC / "favicon-32x32.png",
        150: STATIC / "mstile-150x150.png",
        180: STATIC / "apple-touch-icon.png",
        192: STATIC / "android-chrome-192x192.png",
        512: STATIC / "android-chrome-512x512.png",
        1024: ROOT / "favicon-1024.png",
    }
    images = {}
    for size, path in exports.items():
        images[size] = raster_png(size)
        path.write_bytes(images[size])
    (STATIC / "favicon.ico").write_bytes(icon([(16, images[16]), (32, images[32]), (48, raster_png(48))]))
    print("Regenerated SVG, Safari mask, 7 PNG sizes, and 16/32/48px ICO.")


if __name__ == "__main__":
    main()
