import os
from typing import Dict, Any

import yaml


class Config:
    """
    配置管理类，用于读取和管理配置文件
    """

    def __init__(self, config_path: str = ""):
        """
        初始化配置管理类
        
        Args:
            config_path: 配置文件路径，默认为项目根目录下的configs/config.yaml
        """
        if not config_path:
            # 默认配置文件路径
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "configs",
                "config.yaml"
            )
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            配置字典
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config or {}
        except FileNotFoundError:
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"配置文件格式错误: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项，支持点分隔符
        
        Args:
            key: 配置项键名，支持点分隔符，如 "model.provider"
            default: 默认值
        
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def reload(self) -> None:
        """
        重新加载配置文件
        """
        self.config = self._load_config()


# 创建全局配置实例
deepsearch_config = Config()
