import unittest
from types import SimpleNamespace

import nonebot


nonebot.init()

import plugins.voice_chat as voice_chat  # noqa: E402


SAMPLE_RAW = [
    {
        "type": "推荐",
        "characters": [
            {
                "character_id": "lucy-voice-a",
                "character_name": "小新",
                "preview_url": "https://example.com/a.mp3",
            },
            {
                "character_id": "lucy-voice-b",
                "character_name": "妲己",
                "preview_url": "https://example.com/b.mp3",
            },
        ],
    },
    {
        "type": "古风",
        "characters": [
            {
                "character_id": "lucy-voice-c",
                "character_name": "书生",
                "preview_url": "https://example.com/c.mp3",
            },
        ],
    },
]


class NormalizeAiCharacterGroupsTest(unittest.TestCase):
    def test_normalizes_valid_payload(self):
        groups = voice_chat.normalize_ai_character_groups(SAMPLE_RAW)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["type"], "推荐")
        self.assertEqual(
            groups[0]["characters"][0],
            {"id": "lucy-voice-a", "name": "小新"},
        )

    def test_tolerates_malformed_payload(self):
        self.assertEqual(voice_chat.normalize_ai_character_groups(None), [])
        self.assertEqual(voice_chat.normalize_ai_character_groups("oops"), [])
        self.assertEqual(
            voice_chat.normalize_ai_character_groups(
                [{"type": "推荐"}, {"characters": [{}, "bad"]}, 42]
            ),
            [],
        )

    def test_skips_characters_missing_fields(self):
        groups = voice_chat.normalize_ai_character_groups(
            [
                {
                    "type": "推荐",
                    "characters": [
                        {"character_id": "id-only"},
                        {"character_id": "ok", "character_name": "正常"},
                    ],
                }
            ]
        )
        self.assertEqual(groups[0]["characters"], [{"id": "ok", "name": "正常"}])


class ResolveAiCharacterTest(unittest.TestCase):
    def setUp(self):
        self.groups = voice_chat.normalize_ai_character_groups(SAMPLE_RAW)

    def test_matches_by_name(self):
        self.assertEqual(
            voice_chat.resolve_ai_character(self.groups, "妲己"), "lucy-voice-b"
        )

    def test_matches_by_id(self):
        self.assertEqual(
            voice_chat.resolve_ai_character(self.groups, "lucy-voice-c"),
            "lucy-voice-c",
        )

    def test_returns_none_for_unknown_or_empty(self):
        self.assertIsNone(voice_chat.resolve_ai_character(self.groups, "不存在"))
        self.assertIsNone(voice_chat.resolve_ai_character(self.groups, "  "))


class ResolveEdgeVoiceTest(unittest.TestCase):
    def test_matches_short_name(self):
        self.assertEqual(
            voice_chat.resolve_edge_voice("晓晓"), "zh-CN-XiaoxiaoNeural"
        )

    def test_passes_through_full_voice_id(self):
        self.assertEqual(
            voice_chat.resolve_edge_voice("zh-CN-YunxiNeural"), "zh-CN-YunxiNeural"
        )

    def test_rejects_unknown_query(self):
        self.assertIsNone(voice_chat.resolve_edge_voice("妲己"))
        self.assertIsNone(voice_chat.resolve_edge_voice("en-US-JennyNeural"))


class VoiceSessionKeyTest(unittest.TestCase):
    def test_group_event_keys_by_group(self):
        event = SimpleNamespace(group_id=123, user_id=456)
        self.assertEqual(voice_chat.voice_session_key(event), ("group", 123))

    def test_private_event_keys_by_user(self):
        event = SimpleNamespace(user_id=456)
        self.assertEqual(voice_chat.voice_session_key(event), ("private", 456))


class FormatVoiceRolesTest(unittest.TestCase):
    def test_group_listing_contains_ai_and_edge_sections(self):
        groups = voice_chat.normalize_ai_character_groups(SAMPLE_RAW)
        text = voice_chat.format_voice_roles(groups, in_group=True)
        self.assertIn("QQ AI 声聊", text)
        self.assertIn("推荐：小新、妲己", text)
        self.assertIn("在线合成", text)

    def test_private_listing_hides_ai_section(self):
        text = voice_chat.format_voice_roles([], in_group=False)
        self.assertNotIn("QQ AI 声聊", text)
        self.assertIn("在线合成", text)


if __name__ == "__main__":
    unittest.main()
