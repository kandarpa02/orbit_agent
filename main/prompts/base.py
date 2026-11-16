from pathlib import Path

INSTRUCTIONS_DIR = Path("main/prompts")

def load_agent_instructions() -> str:
    files = [
        "SOUL.md",
        "AGENTS.md",
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

    return "\n\n".join(sections)