import unittest

from skills.base import format_skill_catalog, load_skill
from main.prompts.base import load_agent_instructions
from main.agents.skill_picker import LoadSkillInput, _load_skill


class SkillLoadingTests(unittest.IsolatedAsyncioTestCase):
    def test_catalog_lists_skill_description(self):
        catalog = format_skill_catalog()

        self.assertIn(
            "- web-search: Search the web, investigate topics",
            catalog,
        )

    def test_load_skill_returns_full_document(self):
        content = load_skill("web-search")

        self.assertIn("# Web Search", content)
        self.assertIn("## Workflow", content)

    def test_agent_prompt_includes_catalog_and_on_demand_guidance(self):
        instructions = load_agent_instructions()

        self.assertIn("- web-search:", instructions)
        self.assertIn("load_skill", instructions)
        normalized_instructions = " ".join(instructions.split())
        self.assertIn(
            "do not load a skill for every request",
            normalized_instructions,
        )

    def test_unknown_skill_raises(self):
        with self.assertRaisesRegex(ValueError, "Unknown skill"):
            load_skill("missing-skill")

    async def test_load_skill_tool_returns_instructions(self):
        result = await _load_skill(LoadSkillInput(name="web-search"))

        self.assertEqual(result["name"], "web-search")
        self.assertIn("# Web Search", result["instructions"])


if __name__ == "__main__":
    unittest.main()
