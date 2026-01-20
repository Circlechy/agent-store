"""配置管理模块.

统一管理服务化配置和资源类配置。
- 服务化配置：从 service.yaml 加载
- 资源类配置：从 .env 文件加载（API keys、敏感信息等）
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore


class Config:
    """配置管理类."""

    def __init__(
        self,
        service_config_path: Optional[str] = None,
        env_file_path: Optional[str] = None,
    ):
        """初始化配置管理器.

        Args:
            service_config_path: service.yaml 文件路径（默认为项目根目录下的 service.yaml）
            env_file_path: .env 文件路径（默认为项目根目录下的 .env）
        """
        # 确定配置文件路径
        if service_config_path is None:
            # 从当前文件向上查找项目根目录
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent
            service_config_path = project_root / "service.yaml"
        else:
            service_config_path = Path(service_config_path)

        if env_file_path is None:
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent
            env_file_path = project_root / ".env"
        else:
            env_file_path = Path(env_file_path)

        self.service_config_path = service_config_path
        self.env_file_path = env_file_path

        # 加载配置
        self.service_config: Dict[str, Any] = {}
        self.env_config: Dict[str, Any] = {}

        self._load_service_config()
        self._load_env_config()

    def _load_service_config(self) -> None:
        """加载服务化配置（service.yaml）."""
        if not self.service_config_path.exists():
            # 如果文件不存在，使用默认配置
            self.service_config = self._get_default_service_config()
            return

        if yaml is None:
            print("警告: PyYAML 未安装，使用默认配置")
            self.service_config = self._get_default_service_config()
            return

        try:
            with open(self.service_config_path, "r", encoding="utf-8") as f:
                self.service_config = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"加载 service.yaml 失败: {e}，使用默认配置")
            self.service_config = self._get_default_service_config()

    def _load_env_config(self) -> None:
        """加载环境变量配置（.env）."""
        # 加载 .env 文件
        if self.env_file_path.exists() and load_dotenv:
            try:
                load_dotenv(self.env_file_path)
            except Exception as e:
                print(f"加载 .env 文件失败: {e}")

        # 从环境变量读取配置
        self.env_config = {
            # API Keys
            "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
            # API URLs
            "openai_api_base": os.getenv("OPENAI_API_BASE", ""),
            "image_api_base": os.getenv("IMAGE_API_BASE", ""),
            "tts_api_base": os.getenv("TTS_API_BASE", ""),
            "asr_api_base": os.getenv("ASR_API_BASE", ""),
            # Model Names
            "llm_model_type": os.getenv("LLM_MODEL_TYPE", ""),
            "llm_model_name": os.getenv("LLM_MODEL_NAME", ""),
            "image_model_name": os.getenv("IMAGE_MODEL_NAME", ""),
            "tts_model_name": os.getenv("TTS_MODEL_NAME", ""),
            "asr_model_name": os.getenv("ASR_MODEL_NAME", ""),
            # SSL config
            "llm_ssl_verify": os.getenv("LLM_SSL_VERIFY", ""),
            "llm_ssl_cert": os.getenv("LLM_SSL_CERT", ""),
        }

    def _get_default_service_config(self) -> Dict[str, Any]:
        """获取默认服务配置."""
        return {
            "agent": {
                "model": None,  # LLM 模型名称
                "default_age": 6,
                "intent_recognition_enabled": True,
            },
            "commander": {},
            "artist": {
                "enable_content_generation": True,
            },
            "mentor": {
                "enable_socratic_teaching": True,
                "enable_character_teaching": True,
                "max_follow_up_questions": 5,
            },
        }

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值.

        Args:
            key: 配置键（支持点号分隔的路径，如 "agent.model"）
            default: 默认值

        Returns:
            配置值
        """
        # 支持点号分隔的路径
        keys = key.split(".")
        value = self.service_config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def get_env(self, key: str, default: Any = None) -> Any:
        """获取环境变量配置值.

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值
        """
        return self.env_config.get(key, default)

    def get_agent_config(self) -> Dict[str, Any]:
        """获取 Agent 配置."""
        return self.get("agent", {})

    def get_commander_config(self) -> Dict[str, Any]:
        """获取 Commander 配置."""
        return self.get("commander", {})

    def get_artist_config(self) -> Dict[str, Any]:
        """获取 Artist 配置."""
        return self.get("artist", {})

    def get_mentor_config(self) -> Dict[str, Any]:
        """获取 Mentor 配置."""
        return self.get("mentor", {})


# 全局配置实例
_global_config: Optional[Config] = None


def load_config(
    service_config_path: Optional[str] = None,
    env_file_path: Optional[str] = None,
) -> Config:
    """加载配置（全局单例）.

    Args:
        service_config_path: service.yaml 文件路径
        env_file_path: .env 文件路径

    Returns:
        配置实例
    """
    global _global_config
    if _global_config is None:
        _global_config = Config(service_config_path, env_file_path)
    return _global_config


def get_config() -> Config:
    """获取全局配置实例.

    Returns:
        配置实例
    """
    global _global_config
    if _global_config is None:
        _global_config = Config()
    return _global_config


def reset_config() -> None:
    """重置全局配置实例（用于测试）."""
    global _global_config
    _global_config = None
