def truncate_text(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def format_for_platform(text: str, platform: str) -> str:
    limits = {
        "x": 280,
        "tiktok": 2200,
        "instagram": 2200,
    }
    max_len = limits.get(platform, 5000)
    return truncate_text(text, max_len)
