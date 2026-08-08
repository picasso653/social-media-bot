from io import BytesIO

from PIL import Image


def resize_image(image_data: bytes, width: int, height: int) -> bytes:
    image = Image.open(BytesIO(image_data))
    image = image.resize((width, height), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, format="JPEG", quality=85)
    return output.getvalue()


def get_platform_image_requirements(platform: str) -> dict:
    requirements = {
        "x": {"width": 1600, "height": 900, "max_size_mb": 5},
        "tiktok": {"width": 1080, "height": 1920, "max_size_mb": 20},
        "instagram": {"width": 1080, "height": 1080, "max_size_mb": 8},
    }
    return requirements.get(platform, {"width": 1200, "height": 1200, "max_size_mb": 10})
