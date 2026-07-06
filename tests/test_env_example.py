import unittest
from pathlib import Path


class EnvExampleTest(unittest.TestCase):
    def test_web_search_page_enrich_timeout_is_active_config(self):
        env_example = Path(__file__).resolve().parents[1] / ".env.example"
        lines = env_example.read_text(encoding="utf-8").splitlines()
        matches = [
            index
            for index, line in enumerate(lines)
            if "WEB_SEARCH_PAGE_ENRICH_TIMEOUT" in line
        ]

        self.assertEqual(len(matches), 1)
        config_index = matches[0]
        self.assertEqual(lines[config_index], "WEB_SEARCH_PAGE_ENRICH_TIMEOUT=3")
        self.assertFalse(lines[config_index].lstrip().startswith("#"))
        self.assertNotIn("WEB_SEARCH_PAGE_ENRICH_TIMEOUT", lines[config_index - 1])


if __name__ == "__main__":
    unittest.main()
