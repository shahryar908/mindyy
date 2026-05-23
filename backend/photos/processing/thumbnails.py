import io

from PIL import Image, ImageOps
import pillow_heif

pillow_heif.register_heif_opener()


def make_thumbnail(image_bytes: bytes, max_side: int = 400) -> tuple[bytes, str]:
    img = Image.open(io.BytesIO(image_bytes))
    # Respect EXIF orientation so thumbnails aren't sideways.
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=85, method=4)
    return buf.getvalue(), "image/webp"
