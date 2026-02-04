#!/usr/bin/env python3
"""
GitHub Repository Downloader MCP Tool - Windows Optimized
保留了代理设置，修复了路径逻辑，保留了调试日志
"""

import asyncio
import os
import shutil
import sys
import datetime
from typing import Dict, List, Optional
from mcp.server import FastMCP

# ================= 配置区域 =================
# 请确保这个端口和你的代理软件一致
PROXY_URL = "http://127.0.0.1:7890"
TIMEOUT_SECONDS = 300
DEBUG_LOG_FILE = "git_tool_debug.log"

mcp = FastMCP("github-downloader")


# ================= 调试辅助 =================
def log_debug(message: str):
    """双写日志：既输出到控制台（给Agent看），也写入文件（给你看）"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}\n"
    sys.stderr.write(line)
    try:
        with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


# ================= 核心工具类 =================
class GitHubURLExtractor:
    @staticmethod
    def extract_github_urls(text: str) -> List[str]:
        import re
        # 增强正则，不仅匹配 https，也匹配 github.com/user/repo 这种格式
        patterns = [
            r"https?://github\.com/[\w\-\.]+/[\w\-\.]+(?:\.git)?",
            r"github\.com/[\w\-\.]+/[\w\-\.]+"
        ]
        urls = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple): match = match[0]
                # 补全 https
                if not match.startswith("http"):
                    match = "https://" + match
                url = match.rstrip(".git").rstrip("/")
                urls.append(url)
        return list(set(urls))

    @staticmethod
    def infer_repo_name(url: str) -> str:
        url = url.rstrip(".git").rstrip("/")
        return url.split("/")[-1]


async def run_git_clone_process(repo_url: str, target_path: str) -> Dict[str, any]:
    """底层 Git 调用，包含强制代理和抗干扰配置"""
    log_debug(f"⚡ Starting clone: {repo_url} -> {target_path}")

    # 1. 确保目标父目录存在
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    # 2. 如果目标已存在，尝试清理（防止 git 报错）
    if os.path.exists(target_path):
        if os.listdir(target_path):
            log_debug(f"Target exists and not empty, attempting cleanup: {target_path}")
            # 使用 Windows 专用清理命令
            proc = await asyncio.create_subprocess_shell(
                f'rmdir /s /q "{target_path}"',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.wait()
            await asyncio.sleep(1)  # 给 Windows 文件系统一点喘息时间

    # 3. 查找 Git
    git_cmd = shutil.which("git")
    if not git_cmd:
        # 常见路径回退
        candidates = [
            r"C:\Program Files\Git\cmd\git.exe",
            r"D:\Program Files\Git\cmd\git.exe"
        ]
        for c in candidates:
            if os.path.exists(c):
                git_cmd = c
                break

    if not git_cmd:
        return {"success": False, "msg": "❌ Git not found. Please install Git for Windows."}

    # 4. 构造命令 (关键：保留了你的代理配置)
    cmd_args = [
        git_cmd, "clone",
        "--depth=1",
        "--progress",
        "-c", f"http.proxy={PROXY_URL}",
        "-c", f"https.proxy={PROXY_URL}",
        "-c", "http.sslVerify=false",  # 关闭 SSL 验证
        "-c", "core.longpaths=true",  # 防止路径过长错误
        repo_url,
        target_path
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # 增加超时控制
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            proc.kill()
            return {"success": False, "msg": "❌ Git clone timed out. Check network proxy."}

        stderr_str = stderr.decode('utf-8', errors='replace')

        if proc.returncode == 0:
            log_debug(f"✅ Clone success: {target_path}")
            return {"success": True, "msg": f"Successfully cloned into {target_path}"}
        else:
            log_debug(f"❌ Clone failed: {stderr_str}")
            return {"success": False, "msg": f"Git Error: {stderr_str}"}

    except Exception as e:
        log_debug(f"❌ System Error: {e}")
        return {"success": False, "msg": f"System Error: {str(e)}"}


# ================= MCP 工具暴露 =================

@mcp.tool()
async def download_github_repo(instruction: str) -> str:
    """
    Download a GitHub repository based on natural language instruction.
    Extracts URL automatically.
    Default path: ./deepcode_lab/papers/1/code_base/<repo_name>
    """
    log_debug(f"📥 Received tool call: download_github_repo('{instruction}')")

    extractor = GitHubURLExtractor()
    urls = extractor.extract_github_urls(instruction)

    if not urls:
        return "❌ No GitHub URLs found in the instruction. Please provide a valid URL."

    results = []
    # 动态获取当前工作目录，防止路径错误
    cwd = os.getcwd()
    # 这里我们保留之前的逻辑，但使其更稳健
    base_dir = os.path.join(cwd, "deepcode_lab", "papers", "1", "code_base")

    for url in urls:
        repo_name = extractor.infer_repo_name(url)
        target_path = os.path.join(base_dir, repo_name)

        res = await run_git_clone_process(url, target_path)
        results.append(f"{url}: {res['msg']}")

    return "\n".join(results)


@mcp.tool()
async def git_clone(repo_url: str, target_path: Optional[str] = None) -> str:
    """
    Directly clone a GitHub repository to a specific path.
    If target_path is not provided, uses default workspace.
    """
    log_debug(f"📥 Received tool call: git_clone(url='{repo_url}', target='{target_path}')")

    if target_path:
        # Agent 指定了路径，直接用
        final_path = target_path
    else:
        # Agent 没指定，使用默认结构
        extractor = GitHubURLExtractor()
        repo_name = extractor.infer_repo_name(repo_url)
        final_path = os.path.join(os.getcwd(), "deepcode_lab", "papers", "1", "code_base", repo_name)

    res = await run_git_clone_process(repo_url, final_path)
    return res['msg']


if __name__ == "__main__":
    # 启动时写入分割线，方便查看
    with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{'=' * 50}\n🚀 New Session Started: {datetime.datetime.now()}\n{'=' * 50}\n")
    mcp.run()

