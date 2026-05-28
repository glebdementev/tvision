import base64
import struct


def encode_b64_png(png_bytes: bytes) -> str:
    return base64.b64encode(png_bytes).decode("ascii")


def data_url_png(png_bytes: bytes) -> str:
    return f"data:image/png;base64,{encode_b64_png(png_bytes)}"


def png_size(png_bytes: bytes) -> tuple[int, int] | None:
    if len(png_bytes) < 24 or png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", png_bytes[16:24])
    return int(w), int(h)
