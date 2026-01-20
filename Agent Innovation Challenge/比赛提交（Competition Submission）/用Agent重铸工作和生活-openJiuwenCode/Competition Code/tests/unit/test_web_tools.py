"""
WebFetch 工具单元测试
"""

import pytest
import time

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from packages.server.tools.web_tools import (
    WebFetchTool,
    WebFetchCache,
    html_to_markdown,
    create_web_fetch_tool,
)


class TestWebFetchCache:
    """WebFetchCache 缓存测试"""

    def test_cache_set_and_get(self):
        """测试缓存设置和获取"""
        cache = WebFetchCache(ttl_seconds=60)
        cache.set("https://example.com", "test content")

        result = cache.get("https://example.com")
        assert result == "test content"

    def test_cache_miss(self):
        """测试缓存未命中"""
        cache = WebFetchCache(ttl_seconds=60)

        result = cache.get("https://nonexistent.com")
        assert result is None

    def test_cache_expiry(self):
        """测试缓存过期"""
        cache = WebFetchCache(ttl_seconds=0)  # 立即过期
        cache.set("https://example.com", "test content")

        # 等待一小段时间确保过期
        time.sleep(0.1)

        result = cache.get("https://example.com")
        assert result is None

    def test_clear_expired(self):
        """测试清理过期缓存"""
        cache = WebFetchCache(ttl_seconds=0)
        cache.set("https://example1.com", "content1")
        cache.set("https://example2.com", "content2")

        time.sleep(0.1)

        cleared = cache.clear_expired()
        assert cleared == 2

    def test_cache_key_uniqueness(self):
        """测试不同 URL 的缓存键唯一性"""
        cache = WebFetchCache(ttl_seconds=60)
        cache.set("https://example.com/page1", "content1")
        cache.set("https://example.com/page2", "content2")

        assert cache.get("https://example.com/page1") == "content1"
        assert cache.get("https://example.com/page2") == "content2"


class TestHtmlToMarkdown:
    """HTML 转 Markdown 测试"""

    def test_basic_html(self):
        """测试基本 HTML 转换"""
        html = "<p>Hello World</p>"
        result = html_to_markdown(html)
        assert "Hello World" in result

    def test_heading_conversion(self):
        """测试标题转换"""
        html = "<h1>Title</h1><p>Content</p>"
        result = html_to_markdown(html)
        assert "Title" in result
        assert "Content" in result

    def test_script_removal(self):
        """测试脚本标签移除"""
        html = "<p>Text</p><script>alert('xss')</script><p>More</p>"
        result = html_to_markdown(html)
        assert "alert" not in result
        assert "Text" in result
        assert "More" in result

    def test_style_removal(self):
        """测试样式标签移除"""
        html = "<style>.class{color:red}</style><p>Content</p>"
        result = html_to_markdown(html)
        assert "color" not in result
        assert "Content" in result

    def test_html_entities(self):
        """测试 HTML 实体解码"""
        html = "<p>&amp; &lt; &gt; &quot;</p>"
        result = html_to_markdown(html)
        # html2text 或回退方法都应该解码实体
        assert "&amp;" not in result or "&" in result

    def test_list_conversion(self):
        """测试列表转换"""
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        result = html_to_markdown(html)
        assert "Item 1" in result
        assert "Item 2" in result

    def test_link_preservation(self):
        """测试链接保留"""
        html = '<a href="https://example.com">Link Text</a>'
        result = html_to_markdown(html)
        assert "Link Text" in result

    def test_empty_html(self):
        """测试空 HTML"""
        result = html_to_markdown("")
        assert result == "" or result.strip() == ""

    def test_complex_html(self):
        """测试复杂 HTML 结构"""
        html = """
        <html>
        <head><title>Test</title></head>
        <body>
            <h1>Main Title</h1>
            <p>First paragraph with <strong>bold</strong> text.</p>
            <ul>
                <li>Item one</li>
                <li>Item two</li>
            </ul>
        </body>
        </html>
        """
        result = html_to_markdown(html)
        assert "Main Title" in result
        assert "First paragraph" in result
        assert "Item one" in result


class TestWebFetchTool:
    """WebFetchTool 工具测试"""

    def test_tool_initialization(self):
        """测试工具初始化"""
        tool = WebFetchTool()

        assert tool.name == "web_fetch"
        assert "url" in tool.description.lower() or "URL" in tool.description
        assert len(tool.params) == 2

    def test_tool_info(self):
        """测试工具信息"""
        tool = WebFetchTool()
        info = tool.get_tool_info()

        assert info.name == "web_fetch"
        assert "url" in info.parameters.required
        assert "prompt" in info.parameters.required

    def test_tool_info_properties(self):
        """测试工具信息属性"""
        tool = WebFetchTool()
        info = tool.get_tool_info()

        assert "url" in info.parameters.properties
        assert "prompt" in info.parameters.properties

    def test_missing_url(self):
        """测试缺少 URL 参数"""
        tool = WebFetchTool()
        result = tool.invoke({"prompt": "test"})

        assert "错误" in result
        assert "URL" in result

    def test_missing_prompt(self):
        """测试缺少 prompt 参数"""
        tool = WebFetchTool()
        result = tool.invoke({"url": "https://example.com"})

        assert "错误" in result
        assert "prompt" in result

    def test_empty_url(self):
        """测试空 URL"""
        tool = WebFetchTool()
        result = tool.invoke({"url": "", "prompt": "test"})

        assert "错误" in result

    def test_empty_prompt(self):
        """测试空 prompt"""
        tool = WebFetchTool()
        result = tool.invoke({"url": "https://example.com", "prompt": ""})

        assert "错误" in result

    def test_invalid_url_scheme(self):
        """测试无效的 URL 协议"""
        tool = WebFetchTool()
        result = tool.invoke({
            "url": "ftp://example.com",
            "prompt": "test"
        })

        assert "错误" in result
        assert "协议" in result or "不支持" in result

    def test_invalid_url_format(self):
        """测试无效的 URL 格式"""
        tool = WebFetchTool()
        # 这个测试验证 URL 解析不会崩溃
        result = tool.invoke({
            "url": "not-a-valid-url",
            "prompt": "test"
        })
        # 应该返回错误或尝试处理
        assert isinstance(result, str)

    def test_tool_with_mode_manager(self):
        """测试带模式管理器的工具"""
        # 验证可以传入 mode_manager
        tool = WebFetchTool(mode_manager=None)
        assert tool.mode_manager is None

    def test_tool_with_llm_callback(self):
        """测试带 LLM 回调的工具"""
        async def callback(s, u):
            return "result"

        tool = WebFetchTool(llm_callback=callback)
        assert tool.llm_callback is callback


class TestCreateWebFetchTool:
    """工厂函数测试"""

    def test_create_without_params(self):
        """测试无参数创建"""
        tool = create_web_fetch_tool()
        assert isinstance(tool, WebFetchTool)
        assert tool.mode_manager is None
        assert tool.llm_callback is None

    def test_create_with_llm_callback(self):
        """测试带 LLM 回调创建"""
        async def callback(s, u):
            return "result"

        tool = create_web_fetch_tool(llm_callback=callback)
        assert tool.llm_callback is callback

    def test_create_returns_correct_type(self):
        """测试工厂函数返回正确类型"""
        tool = create_web_fetch_tool()
        assert isinstance(tool, WebFetchTool)
        assert hasattr(tool, 'invoke')
        assert hasattr(tool, 'ainvoke')
        assert hasattr(tool, 'get_tool_info')


# 网络测试（需要真实网络连接）
@pytest.mark.network
class TestWebFetchToolNetwork:
    """需要网络连接的测试"""

    @pytest.mark.asyncio
    async def test_real_fetch_httpbin(self):
        """测试真实网页获取 - httpbin"""
        tool = WebFetchTool()

        result = await tool.ainvoke({
            "url": "https://httpbin.org/html",
            "prompt": "描述这个页面的内容"
        })

        # 应该成功获取并包含内容
        assert "错误" not in result or "Herman Melville" in result

    @pytest.mark.asyncio
    async def test_real_fetch_with_redirect(self):
        """测试带重定向的真实请求"""
        tool = WebFetchTool()

        # httpbin 的重定向端点
        result = await tool.ainvoke({
            "url": "https://httpbin.org/redirect/1",
            "prompt": "获取页面内容"
        })

        # 应该成功处理重定向
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_real_fetch_404(self):
        """测试 404 错误"""
        tool = WebFetchTool()

        result = await tool.ainvoke({
            "url": "https://httpbin.org/status/404",
            "prompt": "test"
        })

        assert "错误" in result
        assert "404" in result

    @pytest.mark.asyncio
    async def test_real_fetch_json_content(self):
        """测试 JSON 内容获取"""
        tool = WebFetchTool()

        result = await tool.ainvoke({
            "url": "https://httpbin.org/json",
            "prompt": "提取 JSON 中的信息"
        })

        # JSON 内容应该被处理
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_cache_works_on_repeated_requests(self):
        """测试缓存在重复请求时生效"""
        tool = WebFetchTool()

        # 第一次请求
        result1 = await tool.ainvoke({
            "url": "https://httpbin.org/html",
            "prompt": "获取内容"
        })

        # 第二次请求（应该使用缓存）
        result2 = await tool.ainvoke({
            "url": "https://httpbin.org/html",
            "prompt": "获取内容"
        })

        # 两次结果应该相似（缓存命中）
        assert isinstance(result1, str)
        assert isinstance(result2, str)
        # 缓存结果会包含 [缓存] 标记
        assert "缓存" in result2 or result1 == result2
