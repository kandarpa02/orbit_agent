from pathlib import Path

from skills.base import format_skill_catalog

INSTRUCTIONS_DIR = Path("main/prompts")

def load_agent_instructions() -> str:
    files = [
        "SOUL.md",
        "AGENT.md",
        "TOOLS.md",
    ]

    sections = []

    for filename in files:
        path = INSTRUCTIONS_DIR / filename

        if path.exists():
            content = path.read_text(encoding="utf-8")
            sections.append(
                f"# {filename}\n\n{content}"
            )

    sections.append(
        "# Available Skills\n\n"
        "Load a skill only when its description is relevant to the user's task. "
        "The full instructions are available through the `load_skill` tool.\n\n"
        + format_skill_catalog()
    )

    return "\n\n".join(sections)