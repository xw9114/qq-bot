import asyncio
import tempfile
import unittest
from pathlib import Path

from plugins.chat_memory import (
    LongTermMemoryStore,
    build_long_term_memory_prompt,
    format_messages_for_memory,
    normalize_memory_summary,
    trim_history_for_memory,
)


class ChatMemoryHelperTest(unittest.TestCase):
    def test_normalizes_memory_summary(self):
        self.assertEqual(
            normalize_memory_summary("  用户准备考试  \n\n 喜欢简短回答 "),
            "用户准备考试\n喜欢简短回答",
        )

    def test_builds_prompt_only_when_summary_exists(self):
        self.assertEqual(build_long_term_memory_prompt(""), "")

        prompt = build_long_term_memory_prompt("用户最近要考试")

        self.assertIn("当前会话的长期记忆摘要", prompt)
        self.assertIn("用户最近要考试", prompt)
        self.assertIn("不要把摘要里的信息归因给其他人", prompt)

    def test_trims_history_and_returns_overflow_messages(self):
        history = [
            {"role": "user", "content": f"用户消息 {index}"}
            for index in range(5)
        ]

        kept, trimmed = trim_history_for_memory(history, 3)

        self.assertEqual([message["content"] for message in kept], [
            "用户消息 2",
            "用户消息 3",
            "用户消息 4",
        ])
        self.assertEqual([message["content"] for message in trimmed], [
            "用户消息 0",
            "用户消息 1",
        ])

    def test_formats_messages_for_memory(self):
        text = format_messages_for_memory(
            [
                {"role": "user", "content": "我要考试了"},
                {"role": "assistant", "content": "那先别熬夜"},
            ]
        )

        self.assertEqual(text, "用户: 我要考试了\n机器人: 那先别熬夜")


class LongTermMemoryStoreTest(unittest.TestCase):
    def test_persists_summary_by_session_key(self):
        async def run_test():
            with tempfile.TemporaryDirectory() as temp_dir:
                store = LongTermMemoryStore(
                    Path(temp_dir) / "memory.db",
                    use_wal=False,
                )
                group_session = ("group", 12345, 10000)
                private_session = ("private", 12345, None)

                await store.upsert_summary(group_session, "用户在 A 群准备考试")
                await store.upsert_summary(private_session, "用户私聊喜欢短回复")

                self.assertEqual(
                    await store.get_summary(group_session),
                    "用户在 A 群准备考试",
                )
                self.assertEqual(
                    await store.get_summary(private_session),
                    "用户私聊喜欢短回复",
                )

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
