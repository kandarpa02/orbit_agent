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
        self.assertIn("- media-download: Download user-authorized audio or video", catalog)

    def test_load_skill_returns_full_document(self):
        content = load_skill("web-search")

        self.assertIn("# Web Search", content)
        self.assertIn("## Workflow", content)

    def test_media_download_skill_covers_ffmpeg_merging(self):
        content = load_skill("media-download")

        self.assertIn("imageio_ffmpeg.get_ffmpeg_exe()", content)
        self.assertIn("bestvideo+bestaudio/best", content)
        self.assertIn('"noplaylist": True', content)
        self.assertIn('"outtmpl": "%(id)s.%(ext)s"', content)
        self.assertIn('"noprogress": True', content)

    def test_agent_prompt_includes_catalog_and_on_demand_guidance(self):
        instructions = load_agent_instructions()

        self.assertIn("- web-search:", instructions)
        self.assertIn("load_skill", instructions)
        self.assertIn("run_python_task", instructions)
        normalized_instructions = " ".join(instructions.split())
        self.assertIn("python_tasks/download.jpg", normalized_instructions)
        self.assertIn("do not make duplicate filesystem or shell checks", normalized_instructions)
        self.assertIn(
            "Never fall back to `execute_command` to delete files",
            normalized_instructions,
        )
        self.assertIn(
            'Resolve "it" to the single file or directory ORBIT most recently created',
            normalized_instructions,
        )
        self.assertIn(
            "Never retry directory deletion through `execute_command`",
            normalized_instructions,
        )
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
