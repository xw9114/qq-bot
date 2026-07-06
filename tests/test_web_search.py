import asyncio
import unittest
from unittest.mock import patch

import httpx

import nonebot


nonebot.init()

import plugins.web_search as web_search  # noqa: E402


class FakeResponse:
    def __init__(self, text: str, headers: dict[str, str] | None = None) -> None:
        self.text = text
        self.headers = headers or {"content-type": "text/html"}

    def raise_for_status(self) -> None:
        return None


class FakeWebClient:
    def __init__(self, search_html: str = "") -> None:
        self.search_html = search_html
        self.cancelled_urls: list[str] = []

    async def get(self, url: str) -> FakeResponse:
        if "duckduckgo.com" in url:
            return FakeResponse(self.search_html)
        if url.endswith("/slow"):
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                self.cancelled_urls.append(url)
                raise
        if url.endswith("/fail"):
            raise httpx.ConnectError("page unavailable")
        return FakeResponse(f"<html><body><p>Body {url}</p></body></html>")


class DuckDuckGoUrlTest(unittest.TestCase):
    def test_decodes_redirect_url(self):
        self.assertEqual(
            web_search.clean_duckduckgo_url(
                "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa%3Fx%3D1"
            ),
            "https://example.com/a?x=1",
        )

    def test_build_search_url_percent_encodes_chinese(self):
        self.assertEqual(
            web_search.build_duckduckgo_search_url("Python 教程"),
            "https://html.duckduckgo.com/html/?q=Python%20%E6%95%99%E7%A8%8B",
        )

    def test_fresh_query_adds_official_latest_terms(self):
        self.assertEqual(
            web_search.build_effective_search_query("王者荣耀最新英雄"),
            "王者荣耀最新英雄 官方 最新",
        )

    def test_fresh_query_keeps_existing_official_term(self):
        self.assertEqual(
            web_search.build_effective_search_query("王者荣耀官方最新英雄"),
            "王者荣耀官方最新英雄",
        )


class DuckDuckGoParserTest(unittest.TestCase):
    def test_parses_title_url_and_snippet(self):
        html = """
        <div class="result">
          <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fone">
            Example &amp; One
          </a>
          <a class="result__snippet" href="/l/?uddg=https%3A%2F%2Fexample.com%2Fone">
            First <b>snippet</b> text.
          </a>
        </div>
        """

        self.assertEqual(
            web_search.parse_duckduckgo_results(html, limit=3),
            [
                web_search.WebSearchResult(
                    title="Example & One",
                    url="https://example.com/one",
                    snippet="First snippet text.",
                )
            ],
        )

    def test_respects_limit(self):
        html = """
        <a class="result__a" href="https://example.com/one">One</a>
        <a class="result__snippet">First</a>
        <a class="result__a" href="https://example.com/two">Two</a>
        <a class="result__snippet">Second</a>
        """

        self.assertEqual(
            web_search.parse_duckduckgo_results(html, limit=1),
            [
                web_search.WebSearchResult(
                    title="One",
                    url="https://example.com/one",
                    snippet="First",
                )
            ],
        )


class WebPageExtractTest(unittest.TestCase):
    def test_extracts_readable_text_and_skips_script_style(self):
        html = """
        <html>
          <head><style>.hidden{display:none}</style><script>var stale='old'</script></head>
          <body>
            <h1>最新公告</h1>
            <p>新英雄今天上线。</p>
          </body>
        </html>
        """

        self.assertEqual(
            web_search.extract_readable_text(html),
            "最新公告 新英雄今天上线。",
        )

    def test_prioritizes_official_results_for_fresh_queries(self):
        results = [
            web_search.WebSearchResult(
                title="玩家整理",
                url="https://example.com/a",
                snippet="民间列表",
            ),
            web_search.WebSearchResult(
                title="官方公告",
                url="https://example.com/b",
                snippet="最新发布",
            ),
        ]

        self.assertEqual(
            web_search.prioritize_results("最新英雄", results),
            [results[1], results[0]],
        )


class WebSearchEnrichTest(unittest.IsolatedAsyncioTestCase):
    async def test_search_web_returns_results_when_one_page_times_out(self):
        search_html = """
        <a class="result__a" href="https://example.com/fast">Fast</a>
        <a class="result__snippet">Fast snippet</a>
        <a class="result__a" href="https://example.com/slow">Slow</a>
        <a class="result__snippet">Slow snippet</a>
        """
        http_client = FakeWebClient(search_html)

        started_at = asyncio.get_running_loop().time()
        with patch.object(web_search, "WEB_SEARCH_PAGE_ENRICH_TIMEOUT", 0.01):
            results = await web_search.search_web(http_client, "test", limit=2)
        elapsed = asyncio.get_running_loop().time() - started_at

        self.assertLess(elapsed, 0.5)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].page_excerpt, "Body https://example.com/fast")
        self.assertEqual(results[1].title, "Slow")
        self.assertEqual(results[1].snippet, "Slow snippet")
        self.assertEqual(results[1].page_excerpt, "")
        self.assertEqual(http_client.cancelled_urls, ["https://example.com/slow"])

    async def test_enrich_keeps_results_when_one_page_fails(self):
        results = [
            web_search.WebSearchResult(
                title="OK",
                url="https://example.com/ok",
                snippet="ok snippet",
            ),
            web_search.WebSearchResult(
                title="Fail",
                url="https://example.com/fail",
                snippet="fail snippet",
            ),
        ]

        enriched = await web_search.enrich_search_results(
            FakeWebClient(),
            results,
            fetch_pages=2,
            fetch_timeout=1.0,
        )

        self.assertEqual(len(enriched), 2)
        self.assertEqual(enriched[0].page_excerpt, "Body https://example.com/ok")
        self.assertEqual(enriched[1], results[1])


class WebSearchCommandParseTest(unittest.TestCase):
    def test_parses_quick_web_search(self):
        self.assertEqual(
            web_search.parse_quick_web_search("联网 Python 最新版本"),
            "Python 最新版本",
        )
        self.assertEqual(
            web_search.parse_quick_web_search("联网搜索 张雪峰"),
            "张雪峰",
        )
        self.assertEqual(
            web_search.parse_quick_web_search("联网搜索张雪峰"),
            "张雪峰",
        )
        self.assertEqual(
            web_search.parse_quick_web_search("联网查一下 今天新闻"),
            "今天新闻",
        )
        self.assertEqual(
            web_search.parse_quick_web_search("查一下 北京天气"),
            "北京天气",
        )

    def test_slash_command_is_left_to_command_handler(self):
        self.assertIsNone(web_search.parse_quick_web_search("/联网 Python"))

    def test_combined_prefix_without_query_is_not_treated_as_query(self):
        self.assertIsNone(web_search.parse_quick_web_search("联网搜索"))
        self.assertIsNone(web_search.QUICK_WEB_SEARCH_PATTERN.fullmatch("联网搜索"))
        self.assertIsNone(web_search.parse_quick_web_search("联网查一下"))
        self.assertIsNone(web_search.QUICK_WEB_SEARCH_PATTERN.fullmatch("联网查一下"))


class WebAnswerPromptTest(unittest.TestCase):
    def test_answer_prompt_requires_grounding_in_results(self):
        messages = web_search.build_web_answer_messages(
            "Python 最新版本",
            [
                web_search.WebSearchResult(
                    title="Python Releases",
                    url="https://www.python.org/downloads/",
                    snippet="The latest Python release is listed here.",
                    page_excerpt="Python 3.14.0 is the newest major release.",
                )
            ],
            current_date="2026-07-03",
        )

        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("只能使用给定搜索结果", messages[0]["content"])
        self.assertIn("今天日期是 2026-07-03", messages[0]["content"])
        self.assertIn("资料不足", messages[0]["content"])
        self.assertIn("Python Releases", messages[1]["content"])
        self.assertIn("https://www.python.org/downloads/", messages[1]["content"])
        self.assertIn("Python 3.14.0 is the newest major release.", messages[1]["content"])

    def test_trim_reply_adds_ellipsis(self):
        self.assertEqual(web_search.trim_reply("abcdef", max_chars=4), "abc…")


if __name__ == "__main__":
    unittest.main()
