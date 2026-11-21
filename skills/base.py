import re
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent

SKILL_DICT = {
    "web-search": SKILLS_DIR / "web_search" / "WEB_SEARCH.md",
    "media-download": SKILLS_DIR / "media_download" / "MEDIA_DOWNLOAD.md",
}

_FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n(.*?)\n---(?:\s*\n|\Z)", re.DOTALL)


def _read_skill_metadata(name: str) -> tuple[str, str]:
    path = SKILL_DICT.get(name)

    if path is None:
        raise ValueError(f"Unknown skill: {name}")

    if not path.is_file():
        raise FileNotFoundError(
            f"Skill documentation not found: {path}"
        )

    content = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_PATTERN.match(content)
    if match is None:
        raise ValueError(f"Skill metadata is missing: {path}")

    metadata = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() in {"name", "description"}:
            metadata[key.strip()] = value.strip().strip("\"'")

    skill_name = metadata.get("name")
    description = metadata.get("description")
    if not skill_name or not description:
        raise ValueError(f"Skill name or description is missing: {path}")
    if skill_name != name:
        raise ValueError(
            f"Skill name mismatch for {path}: expected {name}, found {skill_name}"
        )

    return description, content


def format_skill_catalog() -> str:
    entries = []
    for name in SKILL_DICT:
        description, _ = _read_skill_metadata(name)
        entries.append(f"- {name}: {description}")
    return "\n".join(entries)


def load_skill(name: str) -> str:
    _, content = _read_skill_metadata(name)
    return content