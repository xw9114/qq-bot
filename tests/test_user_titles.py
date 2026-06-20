import asyncio
import sqlite3
import unittest
from pathlib import Path

import nonebot
from nonebot.adapters.onebot.v11 import Message, MessageSegment


nonebot.init()

from plugins.user_titles import (  # noqa: E402
    UserTitleStore,
    get_mentioned_titles_prompt,
    normalize_title,
    parse_target_and_title,
    parse_target_id,
    title_store,
)


class InMemoryUserTitleStore(UserTitleStore):
    def __init__(self):
        super().__init__(Path(":memory:"))
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row

    def _connect(self) -> sqlite3.Connection:
        return self.connection


class UserTitleStoreTest(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryUserTitleStore()

    def tearDown(self):
        self.store.connection.close()

    def test_title_lifecycle(self):
        async def run_test():
            self.assertIsNone(await self.store.get_title(10001))

            await self.store.set_title(10001, "物理课代表", 90001)
            self.assertEqual(await self.store.get_title(10001), "物理课代表")

            await self.store.set_title(10001, "废物", 90001)
            self.assertEqual(await self.store.get_title(10001), "废物")
            self.assertEqual(
                await self.store.find_titles_in_text("废物是谁"),
                [(10001, "废物")],
            )

            self.assertTrue(await self.store.delete_title(10001))
            self.assertIsNone(await self.store.get_title(10001))
            self.assertFalse(await self.store.delete_title(10001))

        asyncio.run(run_test())


class UserTitleParsingTest(unittest.TestCase):
    def test_parse_qq_number_and_title(self):
        message = Message("10001 物理课代表")
        self.assertEqual(parse_target_and_title(message), (10001, "物理课代表"))

    def test_parse_at_and_title(self):
        message = Message(
            [MessageSegment.at(10001), MessageSegment.text(" 废物")]
        )
        self.assertEqual(parse_target_and_title(message), (10001, "废物"))

    def test_parse_default_user(self):
        self.assertEqual(parse_target_id(Message(), 10001), 10001)

    def test_normalize_title(self):
        self.assertEqual(normalize_title("  物理   课代表  "), "物理 课代表")
        with self.assertRaises(ValueError):
            normalize_title("")
        with self.assertRaises(ValueError):
            normalize_title("称" * 31)

    def test_mentioned_titles_prompt(self):
        original_store = title_store
        store = InMemoryUserTitleStore()

        async def run_test():
            import plugins.user_titles as user_titles

            user_titles.title_store = store
            try:
                await store.set_title(10001, "废物", 90001)
                prompt = await get_mentioned_titles_prompt("废物是谁")
                self.assertIn("废物", prompt)
                self.assertIn("10001", prompt)
            finally:
                user_titles.title_store = original_store
                store.connection.close()

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
