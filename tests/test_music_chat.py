import unittest

import nonebot


nonebot.init()

import plugins.music_chat as music_chat  # noqa: E402


class ParseSongIdTest(unittest.TestCase):
    def test_bare_digits(self):
        self.assertEqual(music_chat.parse_song_id("3339230677"), 3339230677)

    def test_song_page_link(self):
        self.assertEqual(
            music_chat.parse_song_id("https://music.163.com/song?id=3339230677"),
            3339230677,
        )

    def test_hash_link(self):
        self.assertEqual(
            music_chat.parse_song_id("https://music.163.com/#/song?id=3339230677"),
            3339230677,
        )

    def test_share_text_with_extra_content(self):
        text = "分享周杰伦的单曲《晴天》http://y.music.163.com/m/song?id=3339230677&app_version=8 (@网易云音乐)"
        self.assertEqual(music_chat.parse_song_id(text), 3339230677)

    def test_song_name_without_id_returns_none(self):
        self.assertIsNone(music_chat.parse_song_id("晴天 周杰伦"))

    def test_empty_text_returns_none(self):
        self.assertIsNone(music_chat.parse_song_id("   "))


class BuildDirectDownloadUrlTest(unittest.TestCase):
    def test_builds_expected_url(self):
        self.assertEqual(
            music_chat.build_direct_download_url(123),
            "https://music.163.com/song/media/outer/url?id=123.mp3",
        )


class ParseSearchResultTest(unittest.TestCase):
    def test_parses_song_with_artists(self):
        payload = {
            "result": {
                "songs": [
                    {
                        "id": 3339230677,
                        "name": "晴天",
                        "artists": [{"name": "周杰伦"}, {"name": "A-LNK"}],
                    }
                ]
            }
        }
        self.assertEqual(
            music_chat.parse_search_result(payload),
            (3339230677, "晴天 - 周杰伦/A-LNK"),
        )

    def test_parses_song_without_artists(self):
        payload = {"result": {"songs": [{"id": 1, "name": "无名"}]}}
        self.assertEqual(music_chat.parse_search_result(payload), (1, "无名"))

    def test_missing_songs_returns_none(self):
        self.assertIsNone(music_chat.parse_search_result({"result": {}}))
        self.assertIsNone(music_chat.parse_search_result({"result": {"songs": []}}))

    def test_malformed_payload_returns_none(self):
        self.assertIsNone(music_chat.parse_search_result(None))
        self.assertIsNone(music_chat.parse_search_result("oops"))
        self.assertIsNone(
            music_chat.parse_search_result({"result": {"songs": [{"name": "缺id"}]}})
        )
        self.assertIsNone(
            music_chat.parse_search_result({"result": {"songs": [{"id": 1}]}})
        )


class ParseSongUrlResultTest(unittest.TestCase):
    def test_parses_valid_url(self):
        payload = {"data": [{"id": 1, "url": "https://example.com/a.mp3"}]}
        self.assertEqual(
            music_chat.parse_song_url_result(payload), "https://example.com/a.mp3"
        )

    def test_null_url_returns_none_for_vip_only_tracks(self):
        payload = {"data": [{"id": 1, "url": None}]}
        self.assertIsNone(music_chat.parse_song_url_result(payload))

    def test_malformed_payload_returns_none(self):
        self.assertIsNone(music_chat.parse_song_url_result(None))
        self.assertIsNone(music_chat.parse_song_url_result({"data": []}))
        self.assertIsNone(music_chat.parse_song_url_result({"data": ["oops"]}))
        self.assertIsNone(music_chat.parse_song_url_result({"data": [{"url": "  "}]}))


class ValidateAudioResponseTest(unittest.TestCase):
    def test_valid_audio(self):
        self.assertTrue(
            music_chat.validate_audio_response("audio/mpeg", 200 * 1024, 15 * 1024 * 1024)
        )

    def test_rejects_non_audio_content_type(self):
        self.assertFalse(
            music_chat.validate_audio_response("text/html", 200 * 1024, 15 * 1024 * 1024)
        )

    def test_rejects_missing_content_type(self):
        self.assertFalse(
            music_chat.validate_audio_response(None, 200 * 1024, 15 * 1024 * 1024)
        )

    def test_rejects_placeholder_sized_audio(self):
        self.assertFalse(
            music_chat.validate_audio_response("audio/mpeg", 1024, 15 * 1024 * 1024)
        )

    def test_rejects_oversized_audio(self):
        self.assertFalse(
            music_chat.validate_audio_response(
                "audio/mpeg", 20 * 1024 * 1024, 15 * 1024 * 1024
            )
        )


if __name__ == "__main__":
    unittest.main()
