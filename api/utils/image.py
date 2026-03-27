# api/utils/image.py
import base64
import io
from typing import Tuple
from PIL import Image
import logging
from config import settings

logger = logging.getLogger(__name__)

MAGIC_BYTES = {
    b'\x89PNG\r\n\x1a\n': 'png',
    b'\xff\xd8\xff': 'jpg',
    b'GIF87a': 'gif',
    b'GIF89a': 'gif',
    b'RIFF': 'webp',
}

def decode_base64_image(data: str) -> Tuple[bytes, str]:
    """Decode Base64 image and validate format"""
    try:
        if ',' in data:
            data = data.split(',', 1)[1]

        image_bytes = base64.b64decode(data)

        if len(image_bytes) > settings.max_image_size_bytes:
            raise ValueError(f"Image size {len(image_bytes)} exceeds maximum {settings.max_image_size_bytes}")

        image_format = detect_format(image_bytes)

        if image_format not in settings.supported_formats:
            raise ValueError(f"Unsupported format: {image_format}. Supported: {settings.supported_formats}")

        return image_bytes, image_format

    except base64.binascii.Error as e:
        raise ValueError(f"Invalid Base64 encoding: {e}")
    except Exception as e:
        raise ValueError(f"Failed to decode image: {e}")

def detect_format(image_bytes: bytes) -> str:
    """Detect image format by magic bytes"""
    for magic, fmt in MAGIC_BYTES.items():
        if image_bytes.startswith(magic):
            if fmt == 'webp':
                if b'WEBP' in image_bytes[:12]:
                    return 'webp'
                continue
            return fmt

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            return img.format.lower()
    except:
        return 'unknown'

def validate_image_dimensions(image_bytes: bytes, max_size: Tuple[int, int] = (4096, 4096)) -> bool:
    """Validate image dimensions"""
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            width, height = img.size
            max_width, max_height = max_size

            if width > max_width or height > max_height:
                raise ValueError(f"Image dimensions {width}x{height} exceed maximum {max_width}x{max_height}")

            return True

    except Exception as e:
        raise ValueError(f"Failed to validate dimensions: {e}")

def save_image_to_shared_volume(image_bytes: bytes, task_id: str, filename: str) -> str:
    """Save image to shared volume"""
    import os

    task_dir = f"/data/inputs/{task_id}"
    os.makedirs(task_dir, exist_ok=True)

    filepath = os.path.join(task_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(image_bytes)

    logger.info(f"Saved image to {filepath}")
    return filepath
