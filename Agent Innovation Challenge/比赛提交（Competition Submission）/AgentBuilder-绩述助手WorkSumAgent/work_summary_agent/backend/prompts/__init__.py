# -*- coding: utf-8 -*-
"""
Prompts 模块

存放所有 prompt 模板文件，便于修改和维护
"""

from .prompt_loader import PromptLoader, load_prompt, load_combined_prompt

__all__ = ['PromptLoader', 'load_prompt', 'load_combined_prompt']
