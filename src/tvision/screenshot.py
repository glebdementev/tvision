import base64


def encode_b64_png(png_bytes: bytes) -> str:
    return base64.b64encode(png_bytes).decode("ascii")


def data_url_png(png_bytes: bytes) -> str:
    return f"data:image/png;base64,{encode_b64_png(png_bytes)}"
