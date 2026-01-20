# -*- coding: utf-8 -*-
"""
Prompt 加载器

从文件系统加载 prompt 模板
"""

import os
from pathlib import Path
from typing import Optional, Tuple
from openjiuwen.core.common.logging import logger


class PromptLoader:
    """Prompt 加载器 - 从文件加载 prompt 模板"""
    
    def __init__(self, prompts_dir: Optional[Path] = None):
        """
        初始化 Prompt 加载器
        
        Args:
            prompts_dir: prompt 文件目录，如果为 None 则使用默认目录
        """
        if prompts_dir is None:
            # 默认使用当前文件所在目录
            current_file = Path(__file__).resolve()
            prompts_dir = current_file.parent
        
        self.prompts_dir = Path(prompts_dir)
        if not self.prompts_dir.exists():
            logger.warning(f"Prompt 目录不存在: {self.prompts_dir}")
    
    def load(self, relative_path: str) -> str:
        """
        加载 prompt 文件
        
        Args:
            relative_path: 相对于 prompts_dir 的文件路径（如 "content_analyzer/normal_system.txt"）
        
        Returns:
            prompt 内容字符串
        
        Raises:
            FileNotFoundError: 如果文件不存在
        """
        file_path = self.prompts_dir / relative_path
        
        if not file_path.exists():
            error_msg = f"Prompt 文件不存在: {file_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content.strip()
        except Exception as e:
            logger.error(f"读取 prompt 文件失败: {file_path}, 错误: {e}")
            raise
    
    def load_or_default(self, relative_path: str, default: str) -> str:
        """
        加载 prompt 文件，如果不存在则返回默认值
        
        Args:
            relative_path: 相对于 prompts_dir 的文件路径
            default: 默认 prompt 内容
        
        Returns:
            prompt 内容字符串
        """
        try:
            return self.load(relative_path)
        except FileNotFoundError:
            logger.warning(f"使用默认 prompt: {relative_path}")
            return default
    
    def load_combined(self, relative_path: str) -> Tuple[str, str]:
        """
        加载合并的 prompt 文件（包含 system 和 user prompt）
        
        文件格式：
        === SYSTEM ===
        system prompt content
        
        === USER ===
        user prompt content
        
        Args:
            relative_path: 相对于 prompts_dir 的文件路径（如 "content_analyzer/normal.txt"）
        
        Returns:
            (system_prompt, user_prompt) 元组
        
        Raises:
            FileNotFoundError: 如果文件不存在
            ValueError: 如果文件格式不正确
        """
        content = self.load(relative_path)
        
        # 按分隔符分割
        parts = content.split("=== SYSTEM ===")
        if len(parts) < 2:
            raise ValueError(f"Prompt 文件格式错误，缺少 SYSTEM 部分: {relative_path}")
        
        system_user = parts[1].split("=== USER ===")
        if len(system_user) < 2:
            raise ValueError(f"Prompt 文件格式错误，缺少 USER 部分: {relative_path}")
        
        system_prompt = system_user[0].strip()
        user_prompt = system_user[1].strip()
        
        return system_prompt, user_prompt


# 全局实例
_default_loader = PromptLoader()


def load_prompt(relative_path: str) -> str:
    """
    便捷函数：加载 prompt
    
    Args:
        relative_path: 相对于 prompts 目录的文件路径
    
    Returns:
        prompt 内容字符串
    """
    return _default_loader.load(relative_path)


def load_prompt_or_default(relative_path: str, default: str) -> str:
    """
    便捷函数：加载 prompt，如果不存在则返回默认值
    
    Args:
        relative_path: 相对于 prompts 目录的文件路径
        default: 默认 prompt 内容
    
    Returns:
        prompt 内容字符串
    """
    return _default_loader.load_or_default(relative_path, default)


def load_combined_prompt(relative_path: str) -> Tuple[str, str]:
    """
    便捷函数：加载合并的 prompt（包含 system 和 user）
    
    Args:
        relative_path: 相对于 prompts 目录的文件路径（如 "content_analyzer/normal.txt"）
    
    Returns:
        (system_prompt, user_prompt) 元组
    """
    return _default_loader.load_combined(relative_path)
