# -*- coding: utf-8 -*-
"""
内容分析组件

使用LLMComponent分析提取的文本内容，提取结构化信息
支持自动截屏模式（is_auto_screenshot），使用不同的prompt
"""

from typing import Dict, Any, Optional
from openjiuwen.core.component.base import ComponentExecutable, WorkflowComponent
from openjiuwen.core.component.llm_comp import LLMComponent, LLMCompConfig
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.common.logging import logger
import os
import sys
from pathlib import Path

# 导入 prompt 加载器
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent.parent
sys.path.insert(0, str(_backend_dir))
from backend.prompts.prompt_loader import load_combined_prompt


class ContentAnalyzerComponent(ComponentExecutable, WorkflowComponent):
    """内容分析组件 - 使用LLMComponent分析提取的文本内容"""
    
    def __init__(self, model_config: Optional[ModelConfig] = None):
        """
        初始化内容分析组件
        
        Args:
            model_config: LLM模型配置，如果为None则使用默认配置
        """
        self.model_config = model_config or self._create_default_model_config()
        
        # 保存模型配置，用于创建LLMComponent
        self._model_config = model_config or self._create_default_model_config()
    
    def _create_default_model_config(self) -> ModelConfig:
        """创建默认模型配置"""
        api_key = os.getenv("API_KEY", "")
        api_base = os.getenv("API_BASE", "https://api.modelarts-maas.com/openai/v1")
        model = os.getenv("MODEL_NAME", "deepseek-v3.2-exp")
        
        return ModelConfig(
            model_provider="openai",
            model_info=BaseModelInfo(
                model=model,
                api_base=api_base,
                api_key=api_key,
                temperature=0.7,
                top_p=0.9,
                timeout=120,
            ),
        )
    
    def _create_llm_config(self, is_auto_screenshot: bool = False) -> LLMCompConfig:
        """
        创建LLM组件配置
        
        Args:
            is_auto_screenshot: 是否是自动截屏模式
        """
        if is_auto_screenshot:
            # 自动截屏模式的prompt（从文件加载）
            system_prompt, user_prompt = load_combined_prompt("content_analyzer/auto_screenshot.txt")
        else:
            # 普通模式的prompt（从文件加载）
            system_prompt, user_prompt = load_combined_prompt("content_analyzer/normal.txt")
        
        return LLMCompConfig(
            model=self.model_config,
            template_content=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json"},
            output_config={
                "content_type": {
                    "type": "string",
                    "description": "内容类型：own_work(自己写的工作内容)、learning_material(学习材料)、mixed(混合类型)",
                    "required": True,
                    "enum": ["own_work", "learning_material", "mixed"]
                },
                "tasks": {
                    "type": "array",
                    "description": "主要任务/项目列表",
                    "required": True,
                    "items": {"type": "string"}
                },
                "work_content": {
                    "type": "string",
                    "description": "完成的工作内容详细描述（如果是学习材料，描述学习的内容和收获）",
                    "required": True
                },
                "achievements": {
                    "type": "array",
                    "description": "取得的成果列表，每个成果是一个对象，只包含title和description两个字段，不要包含impact字段",
                    "required": False,
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "成果标题"},
                            "description": {"type": "string", "description": "成果描述，不要包含'影响:xxx'这样的内容"}
                        },
                        "required": ["title", "description"]
                    }
                },
                "issues": {
                    "type": "array",
                    "description": "遇到的问题列表",
                    "required": False,
                    "items": {"type": "string"}
                },
                "next_steps": {
                    "type": "array",
                    "description": "下一步计划列表",
                    "required": False,
                    "items": {"type": "string"}
                }
            },
        )
    
    async def invoke(self, inputs: Dict[str, Any], runtime: Runtime, context: Context) -> Dict[str, Any]:
        """
        分析工作内容
        
        Args:
            inputs: 输入数据，包含：
                - text: 要分析的文本内容（来自提取器组件）
                - is_auto_screenshot: 是否是自动截屏（来自metadata）
            runtime: 运行时上下文
            context: 上下文引擎
            
        Returns:
            分析结果字典
        """
        text = inputs.get("text", "")
        if not text or not text.strip():
            logger.warning("内容分析组件：输入文本为空")
            return {
                "content_type": "own_work",
                "tasks": [],
                "work_content": "",
                "achievements": [],
                "issues": [],
                "next_steps": [],
                "metadata": {
                    "analyzed": False,
                    "error": "输入文本为空"
                }
            }
        
        # 从metadata中获取is_auto_screenshot参数
        metadata = inputs.get("metadata", {})
        is_auto_screenshot = metadata.get("is_auto_screenshot", False)
        
        # LLM API输入长度限制（根据错误信息：Range of input length should be [1, 6000]）
        MAX_INPUT_LENGTH = 5500  # 留一些余量，避免prompt模板增加长度后超限
        original_text_length = len(text)
        truncated = False
        
        # 检查并截断文本
        if original_text_length > MAX_INPUT_LENGTH:
            logger.warning(
                f"内容分析组件：文本长度({original_text_length})超过限制({MAX_INPUT_LENGTH})，"
                f"将截取前{MAX_INPUT_LENGTH}个字符"
            )
            # 尝试在段落边界截断，如果找不到则直接截断
            truncated_text = text[:MAX_INPUT_LENGTH]
            # 尝试找到最后一个换行符，使截断更自然
            last_newline = truncated_text.rfind('\n')
            if last_newline > MAX_INPUT_LENGTH * 0.8:  # 如果最后换行符在80%之后，使用它
                text = truncated_text[:last_newline] + "\n\n[注：内容已截断，仅分析前部分]"
            else:
                text = truncated_text + "\n\n[注：内容已截断，仅分析前部分]"
            truncated = True
            logger.info(f"内容分析组件：文本已截断，实际分析长度={len(text)}")
        
        # 根据is_auto_screenshot选择配置
        if is_auto_screenshot:
            logger.info("内容分析组件：使用自动截屏模式分析")
            config = self._create_llm_config(is_auto_screenshot=True)
        else:
            logger.info("内容分析组件：使用普通模式分析")
            config = self._create_llm_config(is_auto_screenshot=False)
        
        # 准备输入数据
        llm_inputs = {
            "input_content": text
        }
        
        try:
            # 创建LLMComponent实例使用正确的配置
            llm_component = LLMComponent(config)
            
            # 调用LLM组件的executable进行分析
            result = await llm_component.executable.invoke(
                llm_inputs,
                runtime.base(),
                context
            )
            
            # 解析结果
            if isinstance(result, dict):
                analysis_result = result
            else:
                # 如果结果是字符串，尝试解析JSON
                import json
                try:
                    analysis_result = json.loads(result) if isinstance(result, str) else {}
                except json.JSONDecodeError:
                    logger.warning(f"无法解析LLM返回的JSON: {result[:200]}")
                    analysis_result = {}
            
            # 确保content_type存在（兼容旧版本）
            if "content_type" not in analysis_result:
                # 如果没有content_type，尝试从内容推断
                content_type = "own_work"  # 默认值
                
                # 学习类动词关键词（优先判断）
                learning_verbs = ["学习了", "阅读了", "研究了", "了解了", "查看了", "看了", "学习了", "阅读", "研究", "了解"]
                # 工作类动词关键词
                work_verbs = ["完成了", "编写了", "开发了", "实现了", "修复了", "创建了", "制作了", "编写", "开发", "实现"]
                # 学习相关内容关键词
                learning_content = ["论文", "教程", "文档", "资料", "技术文档", "学习笔记"]
                
                # 优先检查用户输入文本部分（如果有标签）
                user_input_section = ""
                if "[用户输入文本]" in text:
                    parts = text.split("[用户输入文本]")
                    if len(parts) > 1:
                        user_input_section = parts[1].split("\n\n")[0] if "\n\n" in parts[1] else parts[1][:200]
                
                # 检查学习类动词（优先）
                has_learning_verb = any(verb in text for verb in learning_verbs) or \
                                   (user_input_section and any(verb in user_input_section for verb in learning_verbs))
                # 检查工作类动词
                has_work_verb = any(verb in text for verb in work_verbs) or \
                               (user_input_section and any(verb in user_input_section for verb in work_verbs))
                # 检查学习相关内容
                has_learning_content = any(keyword in text for keyword in learning_content)
                
                # 判断逻辑：学习类动词优先级最高
                if has_learning_verb and has_work_verb:
                    content_type = "mixed"
                elif has_learning_verb:
                    content_type = "learning_material"  # 即使有文档内容，用户说"学习了"就是学习材料
                elif has_learning_content and not has_work_verb:
                    content_type = "learning_material"  # 只有学习内容，没有工作动词
                elif has_work_verb:
                    content_type = "own_work"
                # 如果都没有，保持默认值 own_work
                
                analysis_result["content_type"] = content_type
                logger.info(
                    f"内容分析组件：推断内容类型为 {content_type} "
                    f"(has_learning_verb={has_learning_verb}, has_work_verb={has_work_verb}, "
                    f"has_learning_content={has_learning_content})"
                )
            
            logger.info(
                f"内容分析组件：分析完成，内容类型={analysis_result.get('content_type', 'unknown')}, "
                f"提取了 {len(analysis_result.get('tasks', []))} 个任务"
            )
            
            return {
                **analysis_result,
                "metadata": {
                    "analyzed": True,
                    "is_auto_screenshot": is_auto_screenshot,
                    "text_length": len(text),
                    "original_text_length": original_text_length,
                    "truncated": truncated,
                    "content_type": analysis_result.get("content_type", "own_work")
                }
            }
        except Exception as e:
            logger.error(f"内容分析组件：分析失败: {e}", exc_info=True)
            # 即使分析失败，也保存原始文本内容，避免完全丢失信息
            # 保存更多内容（前2000字符），确保重要信息不丢失
            # 如果文本很长，至少保存前2000字符，并添加截断标记
            if text and len(text) > 2000:
                fallback_content = text[:2000] + "\n\n[注：内容已截断，仅保存前2000字符]"
            elif text:
                fallback_content = text
            else:
                fallback_content = "截图内容分析失败，但已保存截图"
            return {
                "content_type": "own_work",
                "tasks": [],
                "work_content": fallback_content,
                "achievements": [],
                "issues": [],
                "next_steps": [],
                "metadata": {
                    "analyzed": False,
                    "error": str(e),
                    "is_auto_screenshot": is_auto_screenshot,
                    "original_text_length": original_text_length,
                    "truncated": truncated,
                    "fallback_content": True  # 标记这是备用内容
                }
            }
