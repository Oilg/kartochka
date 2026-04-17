import re
import uuid


def generate_uid() -> str:
    return str(uuid.uuid4())


def substitute_variables(text: str, variables: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return variables.get(key, "")

    return re.sub(r"\{\{(\w+)\}\}", replace, text)


def check_magic_bytes(data: bytes, content_type: str) -> bool:
    if data[:4] == b"\x89PNG":
        return True
    if data[:3] == b"\xff\xd8\xff":
        return True
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return True
    return False
