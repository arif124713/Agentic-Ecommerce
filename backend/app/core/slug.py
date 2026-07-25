import re
import secrets
import unicodedata


def slugify(*parts: str) -> str:
    text = "-".join(p for p in parts if p).lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def unique_suffix() -> str:
    return secrets.token_hex(3)
