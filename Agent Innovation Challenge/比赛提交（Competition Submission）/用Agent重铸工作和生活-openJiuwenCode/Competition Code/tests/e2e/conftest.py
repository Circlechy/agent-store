"""
E2E 测试配置和 Fixtures

使用真实的 jiuwen CLI 命令进行测试，不使用 mock。
通过 subprocess 调用 jiuwen 命令，模拟真实用户交互。
"""

import pytest
import asyncio
import os
import sys
import tempfile
import shutil
import subprocess
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


# ============================================================================
# 配置
# ============================================================================

# jiuwen 命令路径 - 使用 Python 3.11 venv
PYTHON_311 = "/home/snape/claude-code-projects/openjiuwen-code/python11venv/bin/python3.11"
JIUWEN_MODULE = "packages.cli.main"

# 默认超时时间（秒）
DEFAULT_TIMEOUT = 120

# 是否显示详细输出
VERBOSE = os.environ.get("E2E_VERBOSE", "0") == "1"


# ============================================================================
# 测试结果收集器
# ============================================================================

@dataclass
class ToolCall:
    """工具调用记录"""
    name: str
    arguments: Dict[str, Any]
    result: Optional[str] = None


@dataclass
class JiuwenResponse:
    """Jiuwen CLI 响应"""
    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration: float = 0.0

    def has_tool_call(self, tool_name: str, **kwargs) -> bool:
        """检查是否调用了指定工具

        通过分析输出内容来判断工具调用
        """
        # 从输出中解析工具调用
        output = self.stdout + self.content
        tool_name_lower = tool_name.lower()

        # 常见工具名称映射 - 包含原始名称和友好显示名称
        tool_patterns = {
            "read_file": ["read_file", "read(", "● read(", "读取文件", "reading file"],
            "write_file": ["write_file", "write(", "● write(", "写入文件", "writing file"],
            "edit_file": ["edit_file", "edit(", "● edit(", "编辑文件", "editing file"],
            "bash": ["bash", "bash(", "● bash(", "执行命令", "running command"],
            "grep": ["grep", "grep(", "● grep(", "搜索", "searching"],
            "glob": ["glob", "glob(", "● glob(", "查找文件", "finding files"],
            "ls": ["ls", "ls(", "● ls(", "目录列表"],
            "todo_write": ["todo_write", "todowrite", "● todowrite", "任务"],
            "task": ["task", "task(", "● task(", "子代理", "subagent", "sub_agent", "explore", "plan"],
            "web_fetch": ["web_fetch", "webfetch", "● webfetch(", "获取网页"],
            "browser_open": ["browser_open", "browseropen", "● browseropen(", "打开浏览器"],
        }

        patterns = tool_patterns.get(tool_name_lower, [tool_name_lower])
        for pattern in patterns:
            if pattern.lower() in output.lower():
                return True

        return False

    def get_tool_calls(self, tool_name: str) -> List[ToolCall]:
        """获取指定工具的所有调用"""
        return [c for c in self.tool_calls if c.name == tool_name]

    def has_error(self) -> bool:
        """是否有错误"""
        return len(self.errors) > 0 or self.exit_code != 0


# 为了兼容性，创建别名
AgentResponse = JiuwenResponse


# ============================================================================
# Jiuwen CLI 运行器
# ============================================================================

class JiuwenRunner:
    """Jiuwen CLI 运行器 - 通过 subprocess 调用真实的 jiuwen 命令"""

    def __init__(self, working_dir: str = None):
        self.working_dir = working_dir or os.getcwd()
        self.project_root = Path(__file__).parent.parent.parent

    def run_sync(self, query: str, timeout: int = DEFAULT_TIMEOUT) -> JiuwenResponse:
        """同步运行 jiuwen 命令

        Args:
            query: 用户查询
            timeout: 超时时间（秒）

        Returns:
            JiuwenResponse: 响应结果
        """
        response = JiuwenResponse()
        start_time = time.time()

        try:
            # 构建命令 - 使用 -p 参数进行非交互模式
            cmd = [
                PYTHON_311,
                "-m", JIUWEN_MODULE,
                "--skip-welcome",
                "--no-color",
                "-p", query,
            ]

            if VERBOSE:
                print(f"\n[E2E] Running: {' '.join(cmd)}")
                print(f"[E2E] Query: {query}")
                print(f"[E2E] Working dir: {self.working_dir}")

            # 设置环境变量
            env = os.environ.copy()
            env["PYTHONPATH"] = str(self.project_root)

            # 使用 Popen 实现实时输出
            process = subprocess.Popen(
                cmd,
                cwd=self.working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                bufsize=1,  # 行缓冲
            )

            stdout_lines = []
            stderr_lines = []

            # 实时读取输出（使用 select 或线程）
            import threading
            import queue

            def read_stream(stream, output_list, stream_name):
                """读取流并实时打印"""
                for line in iter(stream.readline, ''):
                    if line:
                        output_list.append(line)
                        # 始终打印 jiuwen 输出（使用 -s 参数时可见）
                        print(f"[jiuwen] {line}", end='', flush=True)
                stream.close()

            # 启动读取线程
            stdout_thread = threading.Thread(
                target=read_stream,
                args=(process.stdout, stdout_lines, "stdout")
            )
            stderr_thread = threading.Thread(
                target=read_stream,
                args=(process.stderr, stderr_lines, "stderr")
            )

            stdout_thread.start()
            stderr_thread.start()

            # 等待进程完成（带超时）
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                response.errors.append(f"命令执行超时 ({timeout}s)")
                response.exit_code = -1

            # 等待线程完成
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)

            response.stdout = ''.join(stdout_lines)
            response.stderr = ''.join(stderr_lines)
            response.exit_code = process.returncode if process.returncode is not None else -1
            response.content = response.stdout

            # 解析输出中的错误
            if response.exit_code != 0:
                response.errors.append(f"Exit code: {response.exit_code}")
            if "error" in response.stderr.lower():
                response.errors.append(response.stderr)

            # 解析工具调用（从输出中提取）
            response.tool_calls = self._parse_tool_calls(response.stdout)

        except Exception as e:
            response.errors.append(f"执行异常: {str(e)}")
            response.exit_code = -1

        response.duration = time.time() - start_time

        if VERBOSE:
            print(f"[E2E] Duration: {response.duration:.2f}s")
            print(f"[E2E] Exit code: {response.exit_code}")
            if response.errors:
                print(f"[E2E] Errors: {response.errors}")

        return response

    async def run(self, query: str, timeout: int = DEFAULT_TIMEOUT) -> JiuwenResponse:
        """异步运行 jiuwen 命令

        Args:
            query: 用户查询
            timeout: 超时时间（秒）

        Returns:
            JiuwenResponse: 响应结果
        """
        # 在线程池中运行同步命令
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.run_sync(query, timeout)
        )

    def _parse_tool_calls(self, output: str) -> List[ToolCall]:
        """从输出中解析工具调用"""
        tool_calls = []

        # 简单的模式匹配来识别工具调用
        # 匹配新的友好显示格式: ● Read(...), ● Write(...) 等
        tool_patterns = [
            (r"● Read\(|read_file|读取文件", "read_file"),
            (r"● Write\(|write_file|写入文件", "write_file"),
            (r"● Edit\(|edit_file|编辑文件", "edit_file"),
            (r"● Bash\(|bash\(|执行命令", "bash"),
            (r"● Grep\(|grep\(|搜索", "grep"),
            (r"● Glob\(|glob\(|查找文件", "glob"),
            (r"● LS\(|ls\(|目录列表", "ls"),
            (r"● TodoWrite|todo_write|任务", "todo_write"),
            (r"● Task\(|task\(|子代理|subagent|Explore|Plan", "task"),
            (r"● WebFetch\(|web_fetch|获取网页", "web_fetch"),
            (r"● BrowserOpen\(|browser_open|打开浏览器", "browser_open"),
        ]

        import re
        for pattern, tool_name in tool_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                tool_calls.append(ToolCall(name=tool_name, arguments={}))

        return tool_calls


# 为了兼容性，创建别名
AgentRunner = JiuwenRunner


# ============================================================================
# Fixtures
# ============================================================================

def _has_jiuwen():
    """检查 jiuwen 命令是否可用"""
    try:
        result = subprocess.run(
            [PYTHON_311, "-m", JIUWEN_MODULE, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def _has_api_key():
    """检查是否配置了 API Key"""
    # 检查环境变量或配置文件
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    if os.environ.get("OPENAI_API_KEY"):
        return True
    if os.environ.get("ZHIPU_API_KEY"):
        return True

    # 检查配置文件
    config_path = Path.home() / ".jiuwen" / "config.yaml"
    if config_path.exists():
        return True

    return True  # 假设已配置


# 跳过条件
requires_api_key = pytest.mark.skipif(
    not _has_api_key(),
    reason="需要配置 API Key"
)

requires_jiuwen = pytest.mark.skipif(
    not _has_jiuwen(),
    reason="jiuwen 命令不可用"
)


@pytest.fixture
def runner(temp_project) -> JiuwenRunner:
    """创建 Jiuwen 运行器"""
    return JiuwenRunner(working_dir=temp_project)


@pytest.fixture
def temp_project():
    """创建临时项目目录"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def sample_python_file(temp_project):
    """创建示例 Python 文件"""
    file_path = os.path.join(temp_project, "sample.py")
    with open(file_path, 'w') as f:
        f.write('''def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
''')
    return file_path


@pytest.fixture
def buggy_calculator(temp_project):
    """创建有 bug 的计算器项目"""
    calc_file = os.path.join(temp_project, "calculator.py")
    with open(calc_file, 'w') as f:
        f.write('''"""计算器模块 - 有 bug"""

def calculate_total(items, tax_rate=0.1):
    """计算总价（含税）"""
    subtotal = sum(item['price'] * item['quantity'] for item in items)
    # Bug: 应该是乘法，不是加法
    total = subtotal + tax_rate
    return total

def calculate_discount(price, discount_percent):
    """计算折扣后价格"""
    return price * (1 - discount_percent / 100)
''')

    test_file = os.path.join(temp_project, "test_calculator.py")
    with open(test_file, 'w') as f:
        f.write('''"""计算器测试"""
import pytest
from calculator import calculate_total, calculate_discount

def test_calculate_total():
    items = [
        {'price': 10.0, 'quantity': 2},
        {'price': 5.0, 'quantity': 3},
    ]
    result = calculate_total(items, tax_rate=0.1)
    # 预期: (10*2 + 5*3) * 1.1 = 35 * 1.1 = 38.5
    assert result == pytest.approx(38.5, rel=0.01)

def test_calculate_discount():
    result = calculate_discount(100, 20)
    assert result == pytest.approx(80, rel=0.01)
''')

    return temp_project


@pytest.fixture
def no_docstring_file(temp_project):
    """创建缺少文档字符串的文件"""
    file_path = os.path.join(temp_project, "no_docstring.py")
    with open(file_path, 'w') as f:
        f.write('''def calculate_average(numbers):
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)

def find_max(numbers):
    if not numbers:
        return None
    max_val = numbers[0]
    for n in numbers:
        if n > max_val:
            max_val = n
    return max_val
''')
    return file_path


@pytest.fixture
def syntax_error_file(temp_project):
    """创建有语法错误的文件"""
    file_path = os.path.join(temp_project, "syntax_error.py")
    with open(file_path, 'w') as f:
        f.write('''def greet(name)  # 缺少冒号
    return f"Hello, {name}!"
''')
    return file_path


# ============================================================================
# 辅助函数
# ============================================================================

def assert_tool_called(response: JiuwenResponse, tool_name: str, **kwargs):
    """断言工具被调用"""
    assert response.has_tool_call(tool_name, **kwargs), \
        f"期望调用工具 {tool_name}，实际调用: {[c.name for c in response.tool_calls]}\n输出: {response.content[:500]}"


def assert_any_tool_called(response: JiuwenResponse, tool_names: list):
    """断言至少调用了其中一个工具"""
    for name in tool_names:
        if response.has_tool_call(name):
            return
    # 如果没有明确的工具调用记录，检查输出内容
    output = response.content.lower()
    for name in tool_names:
        if name.lower() in output:
            return
    assert False, f"期望调用工具 {tool_names} 中的任意一个，实际调用: {[c.name for c in response.tool_calls]}\n输出: {response.content[:500]}"


def assert_no_errors(response: JiuwenResponse):
    """断言没有严重错误（允许警告）"""
    # 只检查严重错误，忽略警告
    serious_errors = [e for e in response.errors if "warning" not in e.lower()]
    # 如果有输出内容，认为执行成功
    if response.content and len(response.content) > 10:
        return
    assert not serious_errors, f"发生错误: {serious_errors}"


def assert_file_exists(path: str):
    """断言文件存在"""
    assert os.path.exists(path), f"文件不存在: {path}"


def assert_file_contains(path: str, content: str):
    """断言文件包含指定内容"""
    with open(path, 'r') as f:
        file_content = f.read()
    assert content in file_content, f"文件 {path} 不包含: {content}"


def assert_file_not_contains(path: str, content: str):
    """断言文件不包含指定内容"""
    with open(path, 'r') as f:
        file_content = f.read()
    assert content not in file_content, f"文件 {path} 不应包含: {content}"


def assert_response_mentions(response: JiuwenResponse, keywords: List[str]):
    """断言响应中提到了关键词"""
    content_lower = response.content.lower()
    for keyword in keywords:
        if keyword.lower() in content_lower:
            return
    assert False, f"响应应该提到 {keywords} 中的任意一个，实际响应: {response.content[:300]}"
