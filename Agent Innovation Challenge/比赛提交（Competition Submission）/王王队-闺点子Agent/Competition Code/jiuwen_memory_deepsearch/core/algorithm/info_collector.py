import json
import logging
import uuid
from copy import deepcopy
from json import JSONDecodeError
from typing import Optional, List

from jiuwen_memory_deepsearch.core.algorithm.query_rewrite import query_rewrite
from jiuwen_memory_deepsearch.core.search_context import Step
from jiuwen_memory_deepsearch.prompts.prompts_utils import apply_system_prompt
from jiuwen_memory_deepsearch.tools.meta_engine.meta_engine_search import (
    MetaEngineSearchWrapper,
    MetaEngineSearchTool,
)
from jiuwen_memory_deepsearch.utils.config import deepsearch_config
from jiuwen_memory_deepsearch.utils.llm_utils import llm_astream, runtime_var, get_current_time

logger = logging.getLogger(__name__)


class InfoCollector:
    def __init__(self, current_inputs: dict):
        """
        初始化信息收集器

        Args:
            current_inputs: 当前调用上下文中的输入字段，主要用于记录原始用户 query
        """
        config = deepsearch_config.get("info_collector", {})
        self.max_react_recursion_limit = config.get(
            "max_react_recursion_limit", 10)
        self.max_search_results = config.get("max_search_results", 5)
        self.tools = []
        self.tools_dict = {}
        self.meta_engine_search_result = []
        self.original_user_query = current_inputs.get("query", "")
        self.language = current_inputs.get("language", "zh-CN")
        self.agent_input = {}
        self.original_agent_input = {}
        self._web_record_keys = set()
        self.current_step = None  # 保存当前处理的 step

    async def init_tools(self, search_way):
        """
        初始化工具列表

        使用 MetaEngine 搜索工具进行本地记忆/历史数据搜索
        """
        logger.info(f"[InfoCollector] init_tools, search_way: {search_way}")
        # 注册 MetaEngine 搜索引擎
        if not MetaEngineSearchWrapper.is_registered("default"):
            MetaEngineSearchWrapper.register(
                engine_name="meta_engine",
                max_search_results=self.max_search_results
            )

        # 注册xiaohongshu搜索引擎
        if not MetaEngineSearchWrapper.is_registered("xiaohongshu"):
            # 替换为第二个搜索引擎URL
            xiaohongshu_url = deepsearch_config.get("xiaohongshu_engine.api_url")  # 替换为实际的URL
            MetaEngineSearchWrapper.register(
                engine_name="xiaohongshu",
                search_url=xiaohongshu_url,
                max_search_results=self.max_search_results
            )

        # 创建 MetaEngine 搜索工具（默认引擎）
        meta_engine_tool = MetaEngineSearchTool(
            name="meta_engine_search_tool",
            description="Use MetaEngine to search user's local memory/history data. Input should be a search query string.",
            max_search_results=self.max_search_results,
            engine_name="meta_engine"
        )

        # 创建第二个搜索工具（使用新的搜索引擎）
        xiaohongshu_search_tool = MetaEngineSearchTool(
            name="xiaohongshu_search_tool",
            description="Use XiaohongshuEngine to search external data. Input should be a search query string.",
            max_search_results=self.max_search_results,
            engine_name="xiaohongshu"
        )

        if search_way == "memory":
            self.tools = [
                meta_engine_tool
            ]
        else:
            self.tools = [
                meta_engine_tool,
                xiaohongshu_search_tool
            ]

        logger.info(
            f"[COLLECTOR DEEPSEARCH LOAD TOOLS] {len(self.tools)} tools loaded: {[t.name for t in self.tools]}")
        self.tools_dict = {tool.name: tool for tool in self.tools}

    def _agent_input_build(self, step: Step) -> dict:
        """构建agent输入"""
        agent_input = {
            "messages": [
                {
                    "role": "user",
                    "content": f"Now deal with the step:\n[Step Title]: {step.title}\n[Problem]: {step.description}\n\n"
                }
            ],
            "language": self.language
        }
        self.original_agent_input = deepcopy(agent_input)
        return agent_input

    async def get_info(self, step: Step) -> dict:
        """
        执行深度搜索的主流程

        Args:
            step: 需要执行的步骤
        Returns:
            None, 结果会保存在 step.step_result 以及内部 agent_input 中
        """
        self.agent_input = self._agent_input_build(step)

        # 保存当前 step 信息，用于流式输出
        self.current_step = step

        # 执行ReAct循环进行信息收集
        await self._execute_react_loop(step)

        # 生成并设置最终结果
        await self._generate_findings(step)

    async def _execute_react_loop(self, step: Step) -> None:
        """执行ReAct循环进行信息收集"""
        for i in range(self.max_react_recursion_limit):
            # 1. 获取LLM响应
            response = await self._get_llm_response(step, self.agent_input, i)
            title = step.title if step else ""
            description = step.description if step else ""
            logger.info(
                f"工具选择阶段 response: {i} {title} {description} {json.dumps(response, ensure_ascii=False, indent=2)}")
            if response is None or not response.get("tool_calls"):
                break

            # 2. 处理工具调用
            await self._process_tool_calls(response, i)

    async def _get_llm_response(self, step: Step, agent_input: dict, index: int) -> Optional[dict]:
        """
        获取LLM响应

        Args:
            step: 当前执行的步骤
            agent_input: agent输入数据
            index: 当前循环索引

        Returns:
            LLM响应字典，包含content和tool_calls
        """
        # 构造工具列表（转换为LLM可识别的格式）
        tools = [tool.get_tool_info()
                 for tool in self.tools] if self.tools else None

        # 应用系统提示词
        tool_prompt = apply_system_prompt('tool_select', agent_input)

        try:
            # 准备额外的元数据，包含 step 信息
            extra_metadata = {
                "step_title": step.title if step else "",
                "step_description": step.description if step else "",
                "react_index": index
            }

            response = await llm_astream(
                tool_prompt,
                tools=tools,
                need_stream_out=True,
                agent_name="tool_select",
                extra_metadata=extra_metadata
            )
            return response
        except Exception as e:
            logger.error(f"Error when get info for step {step.title}: {e}")
            return {
                "content": "Error when get search records.",
                "tool_calls": []
            }

    async def _process_tool_calls(self, response: dict, index: int = None) -> None:
        """
        处理工具调用

        Args:
            response: LLM响应字典
            index: 当前 ReAct 循环索引
        """
        # 将助手响应添加到消息列表
        self.agent_input["messages"].append({
            "role": "assistant",
            "tool_calls": response.get("tool_calls", []),
            "tool_call_id": response.get("tool_call_id", "")
        })

        tool_calls = response.get("tool_calls", [])

        for tool_call in tool_calls:
            try:
                await self._handle_single_tool_call(tool_call, index)
            except Exception as e:
                logger.error(
                    f"Error when handle single tool call {tool_call}: {e}")

    def _create_expanded_tool_call(self, tool_id: str, tool_name: str, query: str, index: int) -> dict:
        """
        构造扩展工具调用，用于重写后的 query

        Args:
            tool_id: 原始 tool_call 的 id
            tool_name: 工具名称
            query: 替换后的查询关键词
            index: query 在 expanded list 中的位置
        """
        return {
            "id": f"{tool_id}_{tool_name}_{index}",
            "name": tool_name,
            "args": {"query": query},
            'query': query
        }

    async def _expand_tool_calls(self, tool_call: dict, index: int = None) -> dict:
        # 准备元数据，包含当前 step 信息
        extra_metadata = {
            "step_title": self.current_step.title if self.current_step else "",
            "step_description": self.current_step.description if self.current_step else "",
            "react_index": index
        }
        query_list = await query_rewrite(tool_call.get("query", ""), extra_metadata=extra_metadata)
        expanded_tool_calls = []
        for idx, query in enumerate(query_list):
            expanded_call = self._create_expanded_tool_call(
                tool_call.get("id", ""), tool_call.get("name", ""), query, idx)
            expanded_tool_calls.append(expanded_call)
        return expanded_tool_calls

    async def _handle_single_tool_call(self, tool_call: dict, index: int = None) -> None:
        """
        处理单个工具调用

        Args:
            tool_call: 工具调用信息
            index: 当前 ReAct 循环索引
        """
        tool_name = tool_call.get("name") or tool_call.get(
            "function", {}).get("name")

        if not tool_name:
            logger.warning("Tool call missing name, skipping")
            return

        logger.info(f"Handling tool call: {tool_name}")

        # 准备工具调用参数
        processed_tool_call = self._prepare_tool_call(tool_call)
        if not processed_tool_call:
            return
        # 执行工具调用
        expanded_tool_calls = await self._expand_tool_calls(processed_tool_call, index)
        search_results = await self._execute_expanded_tools(expanded_tool_calls, index)
        filtered_results = await self._filter_search_results_by_answerability(processed_tool_call.get("query", ""),
                                                                              search_results,
                                                                              index)
        # 创建工具消息
        self._create_tool_message(filtered_results, processed_tool_call)

    def _prepare_tool_call(self, tool_call: dict) -> Optional[dict]:
        """
        准备工具调用参数，仅支持 OpenAI 格式

        OpenAI 格式示例：
        {
            "id": "...",
            "function": {
                "name": "...",
                "arguments": "{\"query\": \"...\"}"
            }
        }
        """
        function_payload = tool_call.get("function")
        if not function_payload:
            logger.warning("Tool call missing function payload, skipping")
            return None

        tool_name = function_payload.get("name", "")
        if not tool_name:
            logger.warning("Tool call missing function name, skipping")
            return None

        arguments_value = function_payload.get("arguments", "{}")
        try:
            tool_call_args = json.loads(arguments_value) if isinstance(
                arguments_value, str) else arguments_value
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse tool arguments: {e}, arguments: {arguments_value}")
            tool_call_args = {}

        if isinstance(tool_call_args.get("kwargs"), dict):
            tool_call_args = tool_call_args["kwargs"]

        return {
            "id": tool_call.get("id", ""),
            "name": tool_name,
            "query": tool_call_args.get("query", ""),
            "args": tool_call_args
        }

    async def _execute_expanded_tools(self, expanded_tool_calls: List[dict], index: int = None) -> List[dict]:
        """
        执行工具调用

        Args:
            expanded_tool_calls: 工具调用列表
            index: 当前 ReAct 循环索引

        Returns:
            工具执行结果列表
        """
        all_results = []
        runtime = runtime_var.get()

        # 发送搜索开始事件
        if runtime:
            stream_id = str(uuid.uuid4())
            await runtime.write_custom_stream({
                "message_id": stream_id,
                "agent": "search",
                "content": "",
                "message_type": "message_chunk",
                "event": "start",
                "created_time": get_current_time(),
                "step_title": self.current_step.title if self.current_step else "",
                "react_index": index
            })

        for tool_call in expanded_tool_calls:
            logger.info(f"Start ReAct Tool call: {tool_call}")

            tool_name = tool_call.get("name")
            if tool_name not in self.tools_dict:
                logger.warning(f"ReAct Tool '{tool_name}' not found, skipping")
                continue

            try:
                # 调用工具
                result = await self.tools_dict[tool_name].ainvoke(tool_call["args"])
                tool_content = json.dumps(result, ensure_ascii=False, indent=4)
                logger.info(f"React Tool content: {tool_content}")

            except Exception as e:
                logger.error(f"ReAct Tool '{tool_name}' execute error: {e}")
                continue

            # 处理工具结果
            processed_results = await self._process_tool_result(tool_name, tool_content)
            all_results.extend(processed_results)

        # 发送搜索结束事件
        if runtime:
            await runtime.write_custom_stream({
                "message_id": stream_id,
                "agent": "search",
                "content": f"已获取 {len(all_results)} 条搜索结果",
                "message_type": "message_chunk",
                "event": "end",
                "created_time": get_current_time(),
                "step_title": self.current_step.title if self.current_step else "",
                "react_index": index
            })

        return all_results

    async def _process_tool_result(self, tool_name: str, tool_content: str) -> List[dict]:
        """
        处理工具返回结果

        Args:
            tool_name: 工具名称
            tool_content: 工具返回的内容（JSON字符串）

        Returns:
            处理后的搜索结果列表
        """
        search_content = []

        # 解析tool content
        try:
            content = json.loads(tool_content)
        except json.JSONDecodeError as e:
            logger.error(
                f"Json decode error for tool {tool_name}: {e}, content: {tool_content}")
            content = []
        except Exception as e:
            logger.error(
                f"Unexpected error decoding tool content for {tool_name}: {e}, content: {tool_content}")
            content = []

        # 根据工具名称执行不同的处理逻辑
        if tool_name == "meta_engine_search_tool":
            # MetaEngine 搜索结果处理 - 本地记忆/历史数据搜索
            search_content = content if isinstance(content, list) else []
            self.meta_engine_search_result.extend(search_content)

        else:
            # 其他工具的通用处理
            if isinstance(content, dict):
                search_content = [content]
            elif isinstance(content, list):
                search_content = content
            else:
                search_content = []

        logger.info(
            f"React Tool result: {json.dumps(search_content, ensure_ascii=False, indent=2)}")
        return search_content

    def _create_tool_message(self, results: List[dict], tool_call: dict) -> None:
        """
        创建工具消息并添加到消息列表

        Args:
            results: 工具执行结果
            tool_call: 工具调用信息
        """
        try:
            content = json.dumps(results, ensure_ascii=False)
        except Exception as e:
            content = str(results)
            logger.error(
                f"json dumps failed, using str(result) as fallback: {e}")

        tool_message = {
            "role": "tool",
            "content": content,
            "name": tool_call["name"],
            "tool_call_id": tool_call["id"]
        }
        self.agent_input["messages"].append(tool_message)
        self._extend_web_page_records(results)

    def _extend_web_page_records(self, records: List[dict]) -> None:
        """将 web_page_search_record 去重后追加进 agent_input 中"""
        existing = self.agent_input.setdefault("web_page_search_record", [])
        for item in records:
            key = (
                item.get("group_id")
            )
            if key in self._web_record_keys:
                continue
            self._web_record_keys.add(key)
            existing.append(item)

    async def _generate_findings(self, step: Step) -> None:
        """
        生成最终的总结

        Args:
            step: 当前步骤
        """
        summarize_findings_input = self.original_agent_input
        summarize_findings_input["web_page_search_record"] = self.agent_input["web_page_search_record"]
        sum_messages = apply_system_prompt("summarize_findings", summarize_findings_input)

        try:
            logger.info(
                f'[lxw_test] summarize_findings input: {json.dumps(sum_messages, ensure_ascii=False, indent=2)}')

            # 准备额外的元数据，包含 step 信息
            extra_metadata = {
                "step_title": step.title if step else "",
                "step_description": step.description if step else "",
                "react_index": None  # 显式设为 None，因为它不属于任何一个 ReAct 轮次
            }

            findings_response = await llm_astream(
                sum_messages,
                need_stream_out=True,
                agent_name="summarize_findings",
                extra_metadata=extra_metadata
            )
            logger.info(
                f'[lxw_test] summarize_findings response: {json.dumps(findings_response, ensure_ascii=False, indent=2)}')
        except Exception as e:
            logger.error(f"Error generating findings: {e}")
            findings_response = {
                "content": "Error: Failed to generate findings summary.",
                "tool_calls": []
            }

        # 添加响应到消息列表
        self.agent_input["messages"].append({
            "role": "assistant",
            "content": findings_response.get("content", ""),
        })

        # 提取并设置步骤结果
        step.step_result = self._extract_final_result(self.agent_input["messages"])

    def _extract_final_result(self, messages: List[dict]) -> str:
        """
        从消息中提取最终结果

        Args:
            messages: 消息列表

        Returns:
            最终结果字符串
        """
        if not messages:
            error_msg = "Error: No messages found in the agent result."
            logger.error(error_msg)
            return error_msg

        last_message = messages[-1]
        if isinstance(last_message, dict) and last_message.get("role") == "assistant":
            return last_message.get("content", "")
        else:
            error_msg = f"Error: Unexpected message type: {type(last_message)}. Expected assistant message."
            logger.error(error_msg)
            return error_msg

    async def _filter_search_results_by_answerability(
            self,
            query: str,
            result_list: List[dict],
            index: int = None
    ) -> List[dict]:
        """
        根据可回答性过滤搜索结果

        Args:
            query: 查询字符串
            result_list: 搜索结果列表
            index: 当前 ReAct 循环索引

        Returns:
            过滤后的结果列表
        """
        if not query.strip():
            return result_list
        if not result_list:
            return []
        llm_response_content = ""
        try:
            # 快速预过滤（去重）
            prefiltered = self._fast_prefilter(result_list)

            index_title_map = {}
            # 构建结果字符串
            results_str = '[\n'
            for i, doc in enumerate(prefiltered):
                index_title_map[i] = doc.get("group_id", "")
                results_str += json.dumps(doc, ensure_ascii=False) + ',\n'
            results_str += "]"

            # 应用提示词模板
            llm_input = {
                "messages": [],
                "query": query,
                "original_query": self.original_user_query,
                "results_str": results_str
            }
            prompt = apply_system_prompt("answerability", llm_input)

            # 调用LLM
            extra_metadata = {
                "step_title": self.current_step.title if self.current_step else "",
                "step_description": self.current_step.description if self.current_step else "",
                "react_index": index
            }
            llm_response = await llm_astream(
                prompt,
                need_stream_out=True,
                agent_name="answerability",
                extra_metadata=extra_metadata
            )
            llm_response_content = llm_response.get("content", "")

            # 解析响应
            results = json.loads(llm_response_content).get("results", [])
            logger.info(f"answerability LLM invoke response: {results}")

            if not results:
                return result_list

            # 过滤结果
            filtered_results = []
            for doc in results:
                index = doc.get("index")
                relevant = doc.get("relevant")

                if index is None or relevant is None:
                    logger.warning("Missing field in LLM response, skipping")
                    continue

                if relevant and 0 < index <= len(prefiltered):
                    filtered_results.append(prefiltered[index - 1])

            return filtered_results if filtered_results else result_list

        except JSONDecodeError as e:
            logger.error(
                f"Error parsing LLM answerability response: {e}, content = {llm_response_content}")
            return result_list
        except Exception as e:
            logger.error(
                f"Error when filtering search results by answerability: {e}")
            return result_list

    def _fast_prefilter(self, search_list: List[dict]) -> List[dict]:
        """
        快速预过滤：根据 group_id 去重，避免同一来源重复

        Args:
            search_list: 搜索结果列表

        Returns:
            去重后的结果列表
        """
        seen_group_ids = set()
        result_list = []

        for search_result in search_list:
            group_id = search_result.get("group_id", "")
            # 去重
            if group_id and group_id not in seen_group_ids:
                seen_group_ids.add(group_id)
                result_list.append(search_result)

        return result_list
