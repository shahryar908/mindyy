import io
from datetime import datetime, timezone
from typing import Optional

from PIL import ExifTags, Image
import pillow_heif

pillow_heif.register_heif_opener()


_TAGS = {v: k for k, v in ExifTags.TAGS.items()}
_GPS_TAGS = {v: k for k, v in ExifTags.GPSTAGS.items()}


def extract_exif(image_bytes: bytes) -> dict:
    out = {
        "taken_at": None,
        "location": None,
        "width": None,
        "height": None,
        "camera_make": None,
        "camera_model": None,
    }
    try:
        img = Image.open(io.BytesIO(image_bytes))
        out["width"], out["height"] = img.size
        exif = img.getexif()
        if not exif:
            return out

        for key in ("DateTimeOriginal", "DateTime"):
            tag_id = _TAGS.get(key)
            if tag_id and tag_id in exif:
                try:
                    dt = datetime.strptime(exif[tag_id], "%Y:%m:%d %H:%M:%S")
                    out["taken_at"] = dt.replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    pass

        make_id = _TAGS.get("Make")
        model_id = _TAGS.get("Model")
        if make_id and make_id in exif:
            out["camera_make"] = str(exif[make_id]).strip()
        if model_id and model_id in exif:
            out["camera_model"] = str(exif[model_id]).strip()

        gps_id = _TAGS.get("GPSInfo")
        if gps_id and gps_id in exif:
            try:
                gps = exif.get_ifd(gps_id)
                lat = _to_decimal(
                    gps.get(_GPS_TAGS.get("GPSLatitude")),
                    gps.get(_GPS_TAGS.get("GPSLatitudeRef")),
                )
                lng = _to_decimal(
                    gps.get(_GPS_TAGS.get("GPSLongitude")),
                    gps.get(_GPS_TAGS.get("GPSLongitudeRef")),
                )
                if lat is not None and lng is not None:
                    out["location"] = f"{lat:.6f},{lng:.6f}"
            except Exception:
                pass
    except Exception:
        # Malformed EXIF must never break the pipeline.
        pass
    return out


def _to_decimal(value, ref) -> Optional[float]:
    if not value:
        return None
    try:
        d, m, s = [float(x) for x in value]
    except (TypeError, ValueError):
        return None
    dec = d + (m / 60.0) + (s / 3600.0)
    if ref in ("S", "W", b"S", b"W"):
        dec = -dec
    return dec
