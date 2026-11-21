from pydantic import BaseModel

from ..tools.tools_registry import create_tool
from skills.base import load_skill


class LoadSkillInput(BaseModel):
    name: str


async def _load_skill(args: LoadSkillInput) -> dict[str, str]:
    return {
        "name": args.name,
        "instructions": load_skill(args.name),
    }


load_skill_tool = create_tool(
    name="load_skill",
    description=(
        "Load the full instructions for one relevant skill from the skill "
        "catalog in the system instructions. Use only when the task benefits "
        "from that skill; you do not need to load a skill for every request."
    ),
    schema=LoadSkillInput,
    handler=_load_skill,
)
