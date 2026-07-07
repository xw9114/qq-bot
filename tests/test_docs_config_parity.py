import ast
import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
README = PROJECT_ROOT / "README.md"
CLAUDE_CHAT = PROJECT_ROOT / "plugins" / "claude_chat.py"
MUSIC_CHAT = PROJECT_ROOT / "plugins" / "music_chat.py"
WEB_SEARCH = PROJECT_ROOT / "plugins" / "web_search.py"


SOURCE_CONFIG_CONSTANTS = (
    (WEB_SEARCH, "WEB_SEARCH_MAX_RESULTS"),
    (WEB_SEARCH, "WEB_SEARCH_FETCH_PAGES"),
    (WEB_SEARCH, "WEB_SEARCH_PAGE_ENRICH_TIMEOUT"),
    (WEB_SEARCH, "WEB_SEARCH_PAGE_MAX_CHARS"),
    (WEB_SEARCH, "WEB_SEARCH_COMMAND_COOLDOWN"),
    (WEB_SEARCH, "WEB_SEARCH_REPLY_MAX_CHARS"),
    (CLAUDE_CHAT, "CHAT_IDLE_NUDGE_SECONDS"),
    (CLAUDE_CHAT, "CHAT_IDLE_NUDGE_MESSAGE"),
    (MUSIC_CHAT, "MUSIC_SELECTION_TIMEOUT"),
)

PINNED_EMPTY_DEFAULTS = {
    "CHAT_IDLE_NUDGE_GROUP_IDS": "",
}

RECENT_USER_VISIBLE_CONFIGS = (
    "WEB_SEARCH_MAX_RESULTS",
    "WEB_SEARCH_FETCH_PAGES",
    "WEB_SEARCH_PAGE_ENRICH_TIMEOUT",
    "WEB_SEARCH_PAGE_MAX_CHARS",
    "WEB_SEARCH_COMMAND_COOLDOWN",
    "WEB_SEARCH_REPLY_MAX_CHARS",
    "CHAT_IDLE_NUDGE_SECONDS",
    "CHAT_IDLE_NUDGE_GROUP_IDS",
    "CHAT_IDLE_NUDGE_MESSAGE",
    "MUSIC_SELECTION_TIMEOUT",
)

README_DEFAULT_OVERRIDES = {
    "CHAT_IDLE_NUDGE_GROUP_IDS": "空",
    "CHAT_IDLE_NUDGE_MESSAGE": "内置短句",
}

README_ROW_FRAGMENTS = {
    "WEB_SEARCH_MAX_RESULTS": ("/联网", "搜索结果数量"),
    "WEB_SEARCH_FETCH_PAGES": ("联网搜索", "正文摘录"),
    "WEB_SEARCH_PAGE_ENRICH_TIMEOUT": ("正文抓取", "超时", "降级回答"),
    "WEB_SEARCH_PAGE_MAX_CHARS": ("页面正文摘录", "最大字符数"),
    "WEB_SEARCH_COMMAND_COOLDOWN": ("/联网", "冷却秒数"),
    "WEB_SEARCH_REPLY_MAX_CHARS": ("联网回答", "最大字符数"),
    "CHAT_IDLE_NUDGE_SECONDS": ("群白名单", "设为 `0` 可关闭"),
    "CHAT_IDLE_NUDGE_GROUP_IDS": ("群号白名单", "留空不触发"),
    "CHAT_IDLE_NUDGE_MESSAGE": ("空闲提醒文案", "多条用 `|` 分隔"),
    "MUSIC_SELECTION_TIMEOUT": ("/点歌", "候选", "回复序号", "超时后需重新点歌"),
}

README_CONFIG_ROW = re.compile(
    r"^\|\s*`(?P<key>[A-Z0-9_]+)`\s*"
    r"\|\s*(?P<required>.*?)\s*"
    r"\|\s*(?P<default>.*?)\s*"
    r"\|\s*(?P<description>.*)\|\s*$"
)


def _read_env_example():
    values = {}
    comments = {}
    pending_comments = []

    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            pending_comments = []
            continue
        if stripped.startswith("#"):
            pending_comments.append(stripped.lstrip("#").strip())
            continue
        if "=" not in stripped:
            pending_comments = []
            continue

        key, value = stripped.split("=", 1)
        values[key] = value
        comments[key] = "\n".join(pending_comments)
        pending_comments = []

    return values, comments


def _read_readme_config_rows():
    rows = {}
    for line in README.read_text(encoding="utf-8").splitlines():
        match = README_CONFIG_ROW.match(line)
        if match:
            rows[match.group("key")] = {
                "default": match.group("default").strip(),
                "description": match.group("description").strip(),
                "line": line,
            }
    return rows


def _top_level_assignments(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assignments = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        assignments[node.targets[0].id] = node.value
    return assignments


def _literal_eval(node, assignments):
    if isinstance(node, ast.Name):
        return _literal_eval(assignments[node.id], assignments)
    return ast.literal_eval(node)


def _source_config_defaults():
    defaults = {}
    for path, constant_name in SOURCE_CONFIG_CONSTANTS:
        assignments = _top_level_assignments(path)
        call = assignments[constant_name]
        source_key = ast.literal_eval(call.args[0]).upper()
        default = _literal_eval(call.args[1], assignments)
        defaults[source_key] = default

    defaults.update(PINNED_EMPTY_DEFAULTS)
    return defaults


def _source_string_constant(path, constant_name):
    assignments = _top_level_assignments(path)
    return _literal_eval(assignments[constant_name], assignments)


def _plain_default(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _clean_readme_default(value):
    value = value.strip()
    if value.startswith("`") and value.endswith("`"):
        return value[1:-1]
    return value


class DocsConfigParityTest(unittest.TestCase):
    def test_env_example_defaults_match_source_for_recent_user_visible_config(self):
        env_values, _ = _read_env_example()
        source_defaults = _source_config_defaults()

        for key in RECENT_USER_VISIBLE_CONFIGS:
            with self.subTest(key=key):
                self.assertIn(key, env_values)
                self.assertEqual(env_values[key], _plain_default(source_defaults[key]))

    def test_readme_config_table_matches_env_example_for_recent_user_visible_config(self):
        env_values, _ = _read_env_example()
        readme_rows = _read_readme_config_rows()

        for key in RECENT_USER_VISIBLE_CONFIGS:
            with self.subTest(key=key):
                self.assertIn(key, readme_rows)
                expected_default = README_DEFAULT_OVERRIDES.get(key, env_values[key])
                self.assertEqual(
                    _clean_readme_default(readme_rows[key]["default"]),
                    expected_default,
                )
                for fragment in README_ROW_FRAGMENTS[key]:
                    self.assertIn(fragment, readme_rows[key]["line"])

    def test_help_and_readme_keep_command_user_visible_contracts(self):
        help_message = _source_string_constant(CLAUDE_CHAT, "HELP_MESSAGE")
        readme = README.read_text(encoding="utf-8")
        music_timeout = _plain_default(
            _source_config_defaults()["MUSIC_SELECTION_TIMEOUT"]
        )

        self.assertIn("/联网 [问题]  搜索网页后基于结果回答", help_message)
        self.assertIn("`/联网 关键词`", readme)
        self.assertIn("普通聊天不会自动联网", readme)
        self.assertIn("慢页面超时后保留搜索摘要继续回答", readme)

        self.assertIn("/点歌 [歌名]   返回 3-5 首候选，回复序号确认", help_message)
        self.assertIn("/点歌 [ID/链接]  直接点网易云歌曲", help_message)
        self.assertIn(
            f"候选默认 {music_timeout} 秒超时，超时后需重新点歌",
            help_message,
        )
        self.assertIn("候选列表（通常 3-5 首，最多 5 首）", readme)
        self.assertIn("回复 `1`、`2` 等序号", readme)
        self.assertIn("这次点歌候选已超时，请重新点歌", readme)

    def test_idle_nudge_env_and_readme_explain_activation_and_shutdown(self):
        _, env_comments = _read_env_example()
        readme = README.read_text(encoding="utf-8")

        for key in (
            "CHAT_IDLE_NUDGE_SECONDS",
            "CHAT_IDLE_NUDGE_GROUP_IDS",
            "CHAT_IDLE_NUDGE_MESSAGE",
        ):
            with self.subTest(key=key):
                self.assertIn(key, env_comments)
                self.assertIn(key, readme)

        self.assertIn("群白名单空闲提醒只会在", readme)
        self.assertIn("未加入白名单的群和私聊不会触发", readme)
        self.assertIn(
            "设为 `CHAT_IDLE_NUDGE_SECONDS=0` 或清空 `CHAT_IDLE_NUDGE_GROUP_IDS` 即可关闭",
            readme,
        )
        self.assertIn("多条用 `|` 分隔", readme)

        self.assertIn("设为 0 关闭", env_comments["CHAT_IDLE_NUDGE_SECONDS"])
        self.assertIn("群号白名单", env_comments["CHAT_IDLE_NUDGE_GROUP_IDS"])
        self.assertIn("留空不触发", env_comments["CHAT_IDLE_NUDGE_GROUP_IDS"])
        self.assertIn("多条用 | 分隔", env_comments["CHAT_IDLE_NUDGE_MESSAGE"])


if __name__ == "__main__":
    unittest.main()
