"""
沙箱执行环境

提供隔离的执行环境用于测试代码
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger

from app.config.settings import get_settings


class Sandbox:
    """沙箱执行环境"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        初始化沙箱
        
        Args:
            base_dir: 沙箱基础目录（可选，默认使用临时目录）
        """
        settings = get_settings()
        if base_dir is None:
            project_root = Path(__file__).parent.parent.parent.parent
            base_dir = project_root / "sandboxes"
        
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self._sandboxes: Dict[str, Path] = {}  # conversation_id -> sandbox_path
    
    def create_sandbox(self, conversation_id: str, persistent: bool = False) -> Path:
        """
        创建沙箱环境
        
        Args:
            conversation_id: 会话 ID
            persistent: 是否持久化（持久化沙箱支持多轮对话）
        
        Returns:
            沙箱目录路径
        """
        if persistent:
            # 持久化沙箱：基于 conversation_id 创建固定目录
            sandbox_path = self.base_dir / conversation_id
            sandbox_path.mkdir(exist_ok=True)
        else:
            # 临时沙箱：创建临时目录
            sandbox_path = Path(tempfile.mkdtemp(prefix="sandbox_", dir=self.base_dir))
        
        self._sandboxes[conversation_id] = sandbox_path
        logger.debug(f"创建沙箱: {conversation_id} -> {sandbox_path}")
        return sandbox_path
    
    def get_sandbox(self, conversation_id: str) -> Optional[Path]:
        """获取沙箱路径"""
        return self._sandboxes.get(conversation_id)
    
    def copy_files(self, conversation_id: str, files: Dict[str, str]):
        """
        复制文件到沙箱
        
        Args:
            conversation_id: 会话 ID
            files: 文件字典 {相对路径: 内容}
        """
        sandbox_path = self.get_sandbox(conversation_id)
        if not sandbox_path:
            sandbox_path = self.create_sandbox(conversation_id, persistent=True)
        
        # 检测是否需要 setup_path.py
        needs_setup_path = False
        if 'setup_path.py' not in files:
            # 检查复制的文件中是否包含 import setup_path
            for content in files.values():
                if 'import setup_path' in content or 'from setup_path' in content:
                    needs_setup_path = True
                    logger.debug("检测到需要 setup_path.py")
                    break
        
        # 复制文件
        for rel_path, content in files.items():
            file_path = sandbox_path / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        
        # 如果需要，自动生成 setup_path.py
        if needs_setup_path:
            setup_path_content = generate_setup_path_code()
            setup_path_file = sandbox_path / "setup_path.py"
            with open(setup_path_file, "w", encoding="utf-8") as f:
                f.write(setup_path_content)
            logger.info(f"✅ 已自动生成 setup_path.py: {setup_path_file}")
        
        logger.debug(f"复制 {len(files)} 个文件到沙箱: {conversation_id}")
    
    def execute(
        self,
        conversation_id: str,
        command: str,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        在沙箱中执行命令
        
        Args:
            conversation_id: 会话 ID
            command: 要执行的命令
            timeout: 超时时间（秒）
        
        Returns:
            执行结果 {success, output, error, execution_time}
        """
        sandbox_path = self.get_sandbox(conversation_id)
        if not sandbox_path:
            return {
                "success": False,
                "output": "",
                "error": f"沙箱不存在: {conversation_id}",
                "execution_time": 0.0
            }
        
        settings = get_settings()
        if timeout is None:
            timeout = settings.agent.test_timeout
        
        try:
            import time
            import locale
            start_time = time.time()
            
            # 检测系统编码（Windows 通常是 GBK，Linux/Mac 通常是 UTF-8）
            system_encoding = locale.getpreferredencoding()
            logger.debug(f"检测到系统编码: {system_encoding}")
            
            # 优先使用的编码列表（UTF-8 优先，然后是系统编码）
            encodings_to_try = ["utf-8", system_encoding]
            if system_encoding.lower() not in ["utf-8", "utf8"]:
                # 如果系统编码不是 UTF-8，添加常用编码
                encodings_to_try.extend(["gbk", "gb2312", "cp936"])
            
            # 先尝试以字节模式执行，然后手动解码
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(sandbox_path),
                capture_output=True,
                text=False,  # 先获取字节数据
                timeout=timeout
            )
            
            execution_time = time.time() - start_time
            
            stdout_decoded = self._decode_with_fallback(result.stdout, encodings_to_try, system_encoding)
            stderr_decoded = self._decode_with_fallback(result.stderr, encodings_to_try, system_encoding) if result.stderr else None
            
            return {
                "success": result.returncode == 0,
                "output": stdout_decoded,
                "error": stderr_decoded if result.returncode != 0 else None,
                "execution_time": execution_time
            }
        
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": f"执行超时（>{timeout}秒）",
                "execution_time": timeout
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "execution_time": 0.0
            }
    
    def cleanup(self, conversation_id: str, force: bool = False):
        """
        清理沙箱
        
        Args:
            conversation_id: 会话 ID
            force: 是否强制清理（即使标记为持久化）
        """
        sandbox_path = self._sandboxes.get(conversation_id)
        if not sandbox_path:
            return
        
        # 如果是临时沙箱或强制清理，删除目录
        if force or not (self.base_dir / conversation_id).exists():
            if sandbox_path.exists():
                shutil.rmtree(sandbox_path)
                logger.debug(f"清理沙箱: {conversation_id}")
        
        del self._sandboxes[conversation_id]
    
    @staticmethod
    def _decode_with_fallback(data: bytes, encodings_to_try: list, system_encoding: str) -> str:
        """尝试多种编码方式解码数据"""
        if not data:
            return ""
        
        # 尝试各种编码
        for encoding in encodings_to_try:
            try:
                decoded = data.decode(encoding)
                # 检查是否包含替换字符（表示解码可能有问题）
                if "\ufffd" not in decoded:
                    return decoded
            except (UnicodeDecodeError, LookupError):
                continue
        
        # 所有编码都失败，使用 replace 模式回退
        fallback_encodings = ["utf-8", system_encoding, "latin1"]
        for encoding in fallback_encodings:
            try:
                return data.decode(encoding, errors="replace")
            except (UnicodeDecodeError, LookupError):
                continue
        
        # 理论上不会到这里，但为了安全返回空字符串
        return ""


def generate_setup_path_code() -> str:
    """
    生成 setup_path.py 文件内容（公共函数）
    
    Returns:
        setup_path.py 的代码内容
    """
    return '''"""
路径设置模块 - 将 openjiuwen 目录添加到 Python 路径
必须在导入 openjiuwen 相关模块之前执行
查找 agent-core/openjiuwen/ 目录
"""
import sys
import os
import warnings
from pathlib import Path

current_file = Path(__file__).resolve()
openjiuwen_path = None

# 方法1: 从当前文件向上查找 agent-core/openjiuwen 目录
for parent in current_file.parents[:10]:
    potential_agent_core = parent / 'agent-core'
    potential_openjiuwen = potential_agent_core / 'openjiuwen'
    if potential_openjiuwen.exists() and potential_openjiuwen.is_dir():
        openjiuwen_path = potential_openjiuwen
        break

# 方法2: 如果没找到，尝试直接查找 openjiuwen 目录（无论父目录名称）
if openjiuwen_path is None:
    for parent in current_file.parents[:10]:
        potential_openjiuwen = parent / 'openjiuwen'
        if potential_openjiuwen.exists() and potential_openjiuwen.is_dir():
            openjiuwen_path = potential_openjiuwen
            break

# 方法3: 如果没找到，尝试从环境变量获取
if openjiuwen_path is None:
    # 支持 AGENT_CORE_PATH 环境变量
    agent_core_env = os.getenv('AGENT_CORE_PATH')
    if agent_core_env:
        potential_agent_core = Path(agent_core_env)
        if potential_agent_core.exists() and potential_agent_core.is_dir():
            potential_openjiuwen = potential_agent_core / 'openjiuwen'
            if potential_openjiuwen.exists() and potential_openjiuwen.is_dir():
                openjiuwen_path = potential_openjiuwen

# 如果找到了，添加到路径
if openjiuwen_path:
    openjiuwen_str = str(openjiuwen_path.resolve())
    if openjiuwen_str not in sys.path:
        sys.path.insert(0, openjiuwen_str)
else:
    # 如果还是没找到，检查是否已经通过 PYTHONPATH 或其他方式添加到路径中
    # 检查 sys.path 中是否已经包含 openjiuwen
    openjiuwen_already_in_path = False
    for path_item in sys.path:
        try:
            path_obj = Path(path_item)
            if path_obj.exists():
                # 检查是否是 openjiuwen 目录本身
                if path_obj.name == 'openjiuwen' and path_obj.is_dir():
                    openjiuwen_already_in_path = True
                    break
                # 检查父目录中是否有 openjiuwen
                for parent in path_obj.parents[:3]:
                    if parent.name == 'openjiuwen' and parent.is_dir():
                        openjiuwen_already_in_path = True
                        break
                if openjiuwen_already_in_path:
                    break
        except Exception:
            # 忽略路径解析错误
            pass
    
    # 如果路径中没找到，尝试检测是否已作为包安装（可以通过 import 导入）
    if not openjiuwen_already_in_path:
        try:
            # 尝试导入 openjiuwen，如果能导入说明已经安装为包
            import importlib.util
            spec = importlib.util.find_spec("openjiuwen")
            if spec is not None and spec.origin is not None:
                openjiuwen_already_in_path = True
        except Exception:
            # 导入失败，继续检查
            pass
    
    # 只有在确实找不到且路径中也没有且无法导入时才发出警告
    if not openjiuwen_already_in_path:
        warnings.warn(
            "无法找到 openjiuwen 目录。请确保以下目录之一存在："
            "agent-core/openjiuwen/，"
            "或设置环境变量 AGENT_CORE_PATH 指向 agent-core 目录。"
            "如果 openjiuwen 已作为包安装，可以忽略此警告。",
            UserWarning
        )
'''