"""openjiuwen Agent 核心类"""

import os
from typing import Optional, Dict, Any
from openjiuwen.agent.react_agent.react_agent import ReActAgent
from openjiuwen.agent.config.react_config import ReActAgentConfig
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo, BaseModelClient

from .tools import get_tools
from .prompts import SYSTEM_PROMPT
from config.settings import get_settings

# 根据 test.py，设置 SSL 验证（如果需要）
# os.environ["LLM_SSL_VERIFY"] = "false"  # 如果需要禁用 SSL 验证，取消注释


class OpenJiuwenAgent:
    """openjiuwen 自动化 Agent 类"""
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: float = 0.0,
        max_iterations: Optional[int] = None,
        verbose: Optional[bool] = None,
    ):
        """初始化 Agent。
        
        Args:
            model_name: 模型名称（如果为 None，使用配置中的模型）
            temperature: 模型温度参数
            max_iterations: 最大迭代次数（如果为 None，使用配置中的值）
            verbose: 是否显示详细日志（如果为 None，使用配置中的值）
        """
        self.settings = get_settings()
        self.model_name = model_name or self.settings.llm_model
        self.temperature = temperature
        self.max_iterations = max_iterations or self.settings.max_iterations
        print(f"Agent 最大迭代次数设置为: {self.max_iterations}")
        self.verbose = verbose if verbose is not None else self.settings.verbose
        
        # 创建模型配置
        self.model_config = self._create_model_config()
        
        # 获取工具
        self.tools = get_tools()
        
        # 创建 Agent
        self.agent = self._create_agent()
    
    def _create_model_config(self) -> ModelConfig:
        """创建模型配置。
        
        Returns:
            ModelConfig 实例
        """
        provider = self.settings.llm_provider.lower()
        
        # 确保 api_base 和 model_provider 有值
        # 根据 test.py 的成功配置，DashScope 使用 compatible-mode 端点
        if not self.settings.api_base:
            if provider == "openai":
                self.settings.api_base = "https://api.openai.com/v1"
            elif provider == "dashscope":
                # 使用 compatible-mode 端点（与 test.py 一致）
                self.settings.api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        
        if not self.settings.model_provider:
            # 根据 test.py，使用 "OpenAI"（首字母大写）
            if provider == "dashscope":
                self.settings.model_provider = "OpenAI"
            else:
                self.settings.model_provider = provider.capitalize()
        
        # 确定 API Key
        if provider == "openai":
            if not self.settings.openai_api_key:
                raise ValueError(
                    "未配置 OPENAI_API_KEY。请在 .env 文件中设置 OPENAI_API_KEY，"
                    "或使用其他 LLM 提供商。"
                )
            api_key = self.settings.openai_api_key
        elif provider == "dashscope":
            if not self.settings.dashscope_api_key:
                raise ValueError(
                    "未配置 DASHSCOPE_API_KEY。请在 .env 文件中设置 DASHSCOPE_API_KEY。"
                )
            api_key = self.settings.dashscope_api_key
            # 如果没有指定模型，使用默认的 qwen-turbo
            if self.model_name == "gpt-4":
                self.model_name = "qwen-turbo"
        else:
            raise ValueError(
                f"不支持的 LLM 提供商: {provider}。"
                "请在 .env 文件中设置 LLM_PROVIDER 为 'openai' 或 'dashscope'。"
            )
        
        # 确保 api_base 已设置（再次检查，防止遗漏）
        if not self.settings.api_base:
            if provider == "openai":
                self.settings.api_base = "https://api.openai.com/v1"
            elif provider == "dashscope":
                # 使用 compatible-mode 端点（与 test.py 一致）
                self.settings.api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        
        # 创建 BaseModelInfo
        # 根据 test.py 的成功配置，调整参数
        model_info = BaseModelInfo(
            api_key=api_key,
            api_base=self.settings.api_base,
            model=self.model_name,
            temperature=self.temperature,
            timeout=60,  # 设置超时时间，避免连接失败
            top_p=0.95,  # 根据 test.py 使用 0.95
            streaming=False,  # 非流式输出
        )
        
        # 创建 ModelConfig
        # 根据 test.py 的成功配置，使用 "OpenAI"（首字母大写）作为 model_provider
        model_provider = self.settings.model_provider
        if provider == "dashscope":
            # 根据 test.py，DashScope 使用 "OpenAI" 作为 provider（首字母大写）
            model_provider = "OpenAI"
        elif provider == "openai":
            model_provider = "OpenAI"
        
        return ModelConfig(
            model_provider=model_provider,
            model_info=model_info
        )
    
    def _create_agent(self) -> ReActAgent:
        """创建 ReAct Agent。
        
        Returns:
            ReActAgent 实例
        """
        # 创建 Agent 配置
        agent_config_data = {
            "id": "file_operation_agent",
            "version": "1.0.0",
            "description": "文件操作自动化 Agent",
            "model": self.model_config,
            "system_prompt": SYSTEM_PROMPT,
        }
        
        agent_config = ReActAgentConfig(data=agent_config_data)
        
        # 手动设置 model 字段（因为通过 data 传入可能无法正确解析）
        if hasattr(agent_config, 'model'):
            agent_config.model = self.model_config
        
        # 设置 constrain.max_iteration（从 .env 中的 MAX_ITERATIONS 读取）
        if hasattr(agent_config, 'constrain') and hasattr(agent_config.constrain, 'max_iteration'):
            agent_config.constrain.max_iteration = self.max_iterations
            print(f"已设置 Agent constrain.max_iteration = {self.max_iterations}")
        
        # 创建 Agent
        agent = ReActAgent(agent_config)
        
        # 通过 runtime 添加 model（作为备用）
        # add_model 需要 model_id 和 BaseModelClient
        if hasattr(agent, '_runtime') and hasattr(agent._runtime, 'add_model'):
            # 从 model_config 创建 BaseModelClient
            # 确保使用与 model_config 相同的配置
            model_client = BaseModelClient(
                api_key=self.model_config.model_info.api_key,
                api_base=self.model_config.model_info.api_base,
                timeout=self.model_config.model_info.timeout if hasattr(self.model_config.model_info, 'timeout') else 60
            )
            agent._runtime.add_model("default_model", model_client)
        
        # 添加工具
        agent.add_tools(self.tools)
        
        return agent
    
    def run(self, query: str) -> str:
        """执行 Agent 任务。
        
        Args:
            query: 用户查询
            
        Returns:
            Agent 的响应
        """
        import asyncio
        try:
            # openjiuwen 的 invoke 是异步的，需要使用 asyncio.run
            # 注意：输入必须包含 'query' 字段
            inputs = {"query": query}
            
            # 确保 model_config 有效
            if self.model_config is None:
                return "执行错误: 模型配置未初始化"
            
            # 检查 agent 配置
            if self.agent is None:
                return "执行错误: Agent 未初始化"
            
            # 检查 agent 的配置
            try:
                agent_config = self.agent.config()
                if agent_config and hasattr(agent_config, 'model'):
                    model = agent_config.model
                    if model is None:
                        return "执行错误: Agent 配置中的 model 为 None"
                    if hasattr(model, 'model_provider') and model.model_provider is None:
                        return "执行错误: model_provider 为 None"
            except Exception as config_error:
                # 如果无法检查配置，继续执行
                pass
            
            result = asyncio.run(self.agent.invoke(inputs))
            
            # 提取响应 - openjiuwen 返回格式可能多样，需要全面检查
            if isinstance(result, dict):
                # 深度搜索响应内容
                def extract_response(obj, depth=0):
                    """递归提取响应内容"""
                    if depth > 3:  # 防止过深递归
                        return None
                    
                    if isinstance(obj, str):
                        return obj if len(obj) > 0 else None
                    
                    if isinstance(obj, dict):
                        # 优先检查常见字段
                        for key in ["responseContent", "content", "response", "output", "result", "message", "text"]:
                            if key in obj:
                                value = obj[key]
                                if isinstance(value, str) and len(value) > 0:
                                    return value
                                if isinstance(value, dict):
                                    extracted = extract_response(value, depth + 1)
                                    if extracted:
                                        return extracted
                        
                        # 递归检查所有值
                        for value in obj.values():
                            extracted = extract_response(value, depth + 1)
                            if extracted:
                                return extracted
                    
                    if isinstance(obj, list) and len(obj) > 0:
                        # 检查列表中的第一个元素
                        extracted = extract_response(obj[0], depth + 1)
                        if extracted:
                            return extracted
                    
                    return None
                
                # 尝试提取响应
                response = extract_response(result)
                if response:
                    return response
                
                # 如果提取失败，返回整个结果的字符串表示（用于调试）
                import json
                try:
                    return json.dumps(result, indent=2, ensure_ascii=False)
                except:
                    return str(result)
            
            # 如果不是字典，直接返回字符串
            return str(result) if result else "未收到响应"
        except Exception as e:
            # 提供更详细的错误信息
            error_msg = str(e)
            error_detail = f"执行错误: {error_msg}"
            
            # 如果是 API 调用错误，提供更详细的诊断信息
            if "API" in error_msg or "api" in error_msg.lower():
                error_detail += "\n\n可能的解决方案："
                error_detail += "\n1. 检查 .env 文件中的 DASHSCOPE_API_KEY 是否正确"
                error_detail += "\n2. 确认 API_BASE 设置为: https://dashscope.aliyuncs.com/api/v1"
                error_detail += f"\n3. 当前配置 - API_BASE: {self.settings.api_base}"
                error_detail += f"\n4. 当前配置 - MODEL_PROVIDER: {self.settings.model_provider}"
                error_detail += f"\n5. 当前配置 - LLM_MODEL: {self.model_name}"
                error_detail += f"\n6. 当前配置 - API Key 长度: {len(self.model_config.model_info.api_key) if self.model_config and self.model_config.model_info else 'N/A'}"
            
            return error_detail
    
    def stream(self, query: str):
        """流式执行 Agent 任务（生成器）。

        Args:
            query: 用户查询

        Yields:
            Agent 的响应片段（包含工具执行跟踪信息和最终回答）
        """
        import asyncio

        def parse_output_schema_string(chunk_str: str):
            """解析 OutputSchema 字符串，提取有效内容

            Returns:
                dict: {'type': str, 'content': str} 或 None
            """
            try:
                import re

                # 查找 type
                type_match = re.search(r"type='([^']+)'", chunk_str)
                if not type_match:
                    return None
                chunk_type = type_match.group(1)

                # 处理 tracer_agent 类型的 chunk（工具执行跟踪）
                if chunk_type == 'tracer_agent':
                    # 从 metaData.class_name 提取工具名称
                    # 格式: metaData={'class_name': 'read_file', 'type': 'tool'}
                    # 尝试单引号和双引号格式
                    tool_name_match = re.search(r"metaData=\{'class_name':\s*'([^']+)'", chunk_str)
                    if not tool_name_match:
                        tool_name_match = re.search(r"metaData=\{'class_name':\s*\"([^\"]+)\"", chunk_str)
                    if not tool_name_match:
                        # 尝试从顶层 name 字段提取
                        tool_name_match = re.search(r"name='([^']+)'", chunk_str)
                    tool_name = tool_name_match.group(1) if tool_name_match else 'unknown'

                    # 检查是否有 outputs（工具执行结果）
                    has_outputs = "outputs={" in chunk_str or "'outputs':" in chunk_str

                    # 构造返回信息
                    if has_outputs:
                        return {
                            'type': 'tool_completed',
                            'content': f"✓ Tool '{tool_name}' executed successfully",
                            'tool_name': tool_name,
                            'status': 'completed'
                        }
                    else:
                        return {
                            'type': 'tool_start',
                            'content': f"⚡ Executing tool: {tool_name}",
                            'tool_name': tool_name,
                            'status': 'executing'
                        }

                # 处理 answer 类型的 chunk（最终回答）
                elif chunk_type == 'answer':
                    # 查找 payload 中的 output
                    output_match = re.search(r"payload=\{[^}]*'output':\s*\{[^}]*'output':\s*'(.*?)'[^}]*\}", chunk_str, re.DOTALL)
                    if output_match:
                        return {
                            'type': 'answer',
                            'content': output_match.group(1)
                        }

                    # 备用方法：直接解析字典
                    payload_match = re.search(r"payload=(\{[^}]+\})", chunk_str, re.DOTALL)
                    if payload_match:
                        import ast
                        try:
                            payload_dict = ast.literal_eval(payload_match.group(1))
                            if isinstance(payload_dict, dict) and 'output' in payload_dict:
                                output = payload_dict['output']
                                if isinstance(output, dict) and 'output' in output:
                                    return {'type': 'answer', 'content': output['output']}
                                elif isinstance(output, str):
                                    return {'type': 'answer', 'content': output}
                        except:
                            pass

                return None
            except Exception:
                return None

        async def _async_stream():
            try:
                inputs = {"query": query}
                # 使用 ReActAgent 的 stream 方法
                async for chunk in self.agent.stream(inputs):
                    # 提取响应内容
                    if isinstance(chunk, dict):
                        # 如果是字典，直接处理
                        if "output" in chunk:
                            yield {'type': 'answer', 'content': chunk["output"]}
                        elif "content" in chunk:
                            yield {'type': 'answer', 'content': chunk["content"]}
                        elif "payload" in chunk and isinstance(chunk["payload"], dict):
                            if "output" in chunk["payload"]:
                                payload_output = chunk["payload"]["output"]
                                if isinstance(payload_output, dict):
                                    if "output" in payload_output:
                                        yield {'type': 'answer', 'content': payload_output["output"]}
                                    else:
                                        yield {'type': 'answer', 'content': payload_output}
                                else:
                                    yield {'type': 'answer', 'content': payload_output}
                            elif "content" in chunk["payload"]:
                                yield {'type': 'answer', 'content': chunk["payload"]["content"]}
                        else:
                            yield str(chunk)
                    elif hasattr(chunk, '__class__') and hasattr(chunk, 'type'):
                        # 处理 TraceSchema 和 OutputSchema 对象
                        chunk_type = getattr(chunk, 'type', None)

                        # 处理 tracer_agent 类型（工具执行跟踪）
                        if chunk_type == 'tracer_agent':
                            # 获取 payload
                            payload = getattr(chunk, 'payload', None)
                            if isinstance(payload, dict):
                                # 从 metaData 获取工具名称
                                meta_data = payload.get('metaData', {})
                                tool_name = meta_data.get('class_name', payload.get('name', 'unknown'))

                                # 检查是否有 outputs（工具执行结果）
                                outputs = payload.get('outputs')
                                has_outputs = outputs is not None

                                # 获取 inputs（工具输入参数）
                                inputs = payload.get('inputs', {})

                                # 构造返回信息
                                if has_outputs:
                                    # 提取 outputs 中的实际输出内容
                                    tool_output = outputs.get('outputs', str(outputs))
                                    yield {
                                        'type': 'tool_completed',
                                        'content': f"✓ Tool '{tool_name}' executed successfully",
                                        'tool_name': tool_name,
                                        'status': 'completed',
                                        'outputs': tool_output
                                    }
                                else:
                                    yield {
                                        'type': 'tool_start',
                                        'content': f"⚡ Executing tool: {tool_name}",
                                        'tool_name': tool_name,
                                        'status': 'executing',
                                        'inputs': inputs
                                    }

                        # 处理 answer 类型（最终回答）
                        elif chunk_type == 'answer':
                            payload = getattr(chunk, 'payload', None)
                            if isinstance(payload, dict):
                                # 尝试从 payload.output.output 获取内容
                                if 'output' in payload:
                                    output = payload['output']
                                    if isinstance(output, dict) and 'output' in output:
                                        yield {'type': 'answer', 'content': output['output']}
                                    elif isinstance(output, str):
                                        yield {'type': 'answer', 'content': output}
                                elif 'content' in payload:
                                    yield {'type': 'answer', 'content': payload['content']}
                    else:
                        # 处理字符串形式的 chunk（OutputSchema 的字符串表示）
                        chunk_str = str(chunk)
                        parsed = parse_output_schema_string(chunk_str)
                        if parsed:
                            yield parsed
            except Exception as e:
                yield {'type': 'error', 'content': f"执行错误: {str(e)}"}

        # 转换异步生成器为同步生成器
        async_gen = _async_stream()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            while True:
                try:
                    # 获取下一个异步生成器产生的值
                    yield loop.run_until_complete(async_gen.__anext__())
                except StopAsyncIteration:
                    break
        finally:
            loop.close()
