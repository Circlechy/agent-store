import json
import logging
import dotenv

from openjiuwen.core.graph.executable import Input, Output
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.utils.llm.messages import HumanMessage, SystemMessage, AIMessage

from carEmu.car_state import get_car_state
from nodes.base_node import BaseNode
from nodes.multi_agent_graph import build_multi_agent_sub_graph
from nodes.utils.utils import trim_internal_messages, trim_tool_trace
from tools.carTools.get_all_state import _get_all_state

dotenv.load_dotenv(dotenv_path=".env")
logger = logging.getLogger(__name__)


class MultiAgent(BaseNode):
    """智能规划多任务Agent - 真正的AI Agent
    
    用户只需要用自然语言描述需求，Agent会：
    1. 理解用户意图，规划多任务Plan
    2. 根据Plan，使用router定向到对应的子Agent节点
    3. 子Agent节点根据Plan中的Task，调用工具完成任务
    4. 子Agent节点完成任务后，返回结果给MultiAgent节点
    5. 全部任务完成后，返回最终结果给用户
    """
    def __init__(self):
        super().__init__()

    async def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        query = runtime.get_global_state("query") or ""
        user_id = runtime.get_global_state("user_id") or "default_user"
        history_messages = runtime.get_global_state("messages") or []
        enable_long_term_memory = runtime.get_global_state("enable_long_term_memory")
        speaker_info = runtime.get_global_state("speaker_info")

        if speaker_info:
            # 过滤掉 avatar_base64 字段（太长，不适合打印/传递）
            speaker_info_filtered = {k: v for k, v in speaker_info.items() if k != "avatar_base64"}
            if "profile" in speaker_info_filtered and isinstance(speaker_info_filtered["profile"], dict):
                speaker_info_filtered["profile"] = {
                    k: v for k, v in speaker_info_filtered["profile"].items() if k != "avatar_base64"
                }
            speaker_info = speaker_info_filtered
            logger.info(f"当前说话者: {speaker_info.get('name', '未知')} ({speaker_info.get('seat', '未知')})")
        else:
            logger.info("未获取到 speaker_info，将使用默认处理")

        current_location = self._get_current_location_str()
        runtime.update_global_state({"current_location": current_location})

        current_car_state = _get_all_state()
        runtime.update_global_state({"current_car_state": current_car_state})

        long_term_memory = ""
        if enable_long_term_memory is True:
            try:
                from memory.memory_manager import get_memory_manager
                memory_manager = await get_memory_manager()
                logger.info(f"开始检索长期记忆 (user_id: {user_id}, query: {query[:50]}...)")
                long_term_memory = await memory_manager.get_relevant_memories(user_id, query, top_k=20)
                if long_term_memory:
                    logger.info(f"检索到相关长期记忆:\n{long_term_memory[:200]}...")
                else:
                    logger.info("长期记忆为空（可能是首次对话或没有相关历史记录）")
            except Exception as e:
                logger.warning(f"长期记忆检索失败: {e}", exc_info=True)
        else:
            logger.debug(f"长期记忆未启用 (enable_long_term_memory={enable_long_term_memory})")

        runtime.update_global_state({"long_term_memory": long_term_memory})

        user_message = query
        if speaker_info:
            speaker_name = speaker_info.get("name", "")
            speaker_seat = speaker_info.get("seat", "")
            user_message = f"[{speaker_seat}乘客 {speaker_name} 说]: {query}"

        # 构建本轮输入的对话上下文
        messages = []
        context_message = self._build_context_message(
            speaker_info=speaker_info,
            current_location=current_location,
            long_term_memory=long_term_memory,
            current_car_state=current_car_state,
        )
        if context_message:
            messages.append(context_message)
        if history_messages:
            messages.extend(history_messages)
        messages.append(HumanMessage(content=user_message).model_dump(exclude_none=True))

        # 更新对话历史（不包含系统上下文，避免重复堆叠）
        runtime.update_global_state({"messages": messages})

        sub_inputs = {"inputs": {
            "query": query,
            "messages": messages
        }}
        sub_graph_context = await self._run_sub_graph(sub_inputs, runtime) or {}
        result = runtime.get_global_state("sub_context.result") or sub_graph_context.get("result") or ""
        internal_messages = trim_internal_messages(runtime.get_global_state("sub_context.internal_messages") or [])
        tool_trace = trim_tool_trace(runtime.get_global_state("sub_context.tool_trace") or [])
        logger.info(f"{result}")
        runtime.update_global_state({"result": result})
        messages_for_ui = list(internal_messages)
        if result:
            messages_for_ui.append(AIMessage(content=result).model_dump(exclude_none=True))
        runtime.update_global_state({"messages": messages_for_ui})
        runtime.update_global_state({"tool_trace": tool_trace})

        # 智能保存到长期记忆（只记住有价值的对话）
        if enable_long_term_memory is True:
            should_remember = self._should_remember(query, result)
            logger.debug(
                f"判断是否保存记忆: should_remember={should_remember}, query={query[:50]}..."
            )
            if should_remember:
                try:
                    from memory.memory_manager import get_memory_manager
                    memory_manager = await get_memory_manager()
                    await memory_manager.add_conversation(
                        user_id=user_id,
                        messages=[
                            {"role": "user", "content": query},
                            {"role": "assistant", "content": result},
                        ],
                    )
                    logger.info(f"✓ 已保存到长期记忆 (user_id: {user_id})")
                except Exception as e:
                    logger.warning(f"保存长期记忆失败: {e}", exc_info=True)
            else:
                logger.debug("跳过记忆保存（不满足记忆条件）")
        else:
            logger.debug(f"长期记忆未启用，跳过保存 (enable_long_term_memory={enable_long_term_memory})")
        return inputs


    async def _run_sub_graph(self, inputs: dict, runtime: Runtime) -> Context:
        multi_agent_sub_graph = build_multi_agent_sub_graph()
        await multi_agent_sub_graph.sub_invoke(
            inputs=inputs.get("inputs", {}),
            runtime=runtime.base(),
        )
        return runtime.get_global_state("sub_context")

    @staticmethod
    def _should_remember(query: str, result: str) -> bool:
        """
        智能判断这轮对话是否值得记忆

        值得记忆的内容：
        - 用户偏好（喜欢什么、常去哪里、习惯等）
        - 用户明确要求记住的信息
        - 重要个人信息（名字、生日等）
        - 重要习惯和行为模式

        不值得记忆的内容：
        - 一次性查询（天气、时间、导航等）
        - 简单问候
        - 工具执行结果
        """
        import re

        query_lower = query.lower()

        # 值得记忆的关键词模式
        remember_patterns = [
            r"记住|记下|记一下|别忘",  # 明确要求记忆
            r"我喜欢|我爱|我偏好|我习惯",  # 用户偏好
            r"我一般|我通常|我常常|我经常",  # 习惯
            r"我叫|我是|我的名字",  # 个人信息
            r"我的.*是|我.*叫",  # 个人属性
            r"以后.*帮我|下次.*记得",  # 未来指令
        ]

        # 不值得记忆的关键词模式
        skip_patterns = [
            r"^(你好|hi|hello|嗨|在吗|在不在)",  # 简单问候
            r"^(谢谢|感谢|好的|嗯|ok|行)",  # 简单回应
            r"^(天气|温度|气温|下雨|晴天).*[?？]$",  # 天气查询
            r"^(几点|时间|现在|今天).*[?？]$",  # 时间查询
            r"^(导航|路线|怎么走|怎么去)(?!.*记)",  # 纯导航请求（不包含"记"）
            r"^(查|搜|找|帮我看).*新闻",  # 一次性新闻查询
        ]

        # 先检查是否匹配跳过模式
        for pattern in skip_patterns:
            if re.search(pattern, query_lower):
                logger.debug(f"跳过记忆（匹配跳过模式）: {query[:30]}...")
                return False

        # 检查是否匹配记忆模式
        for pattern in remember_patterns:
            if re.search(pattern, query_lower):
                logger.info(f"值得记忆（匹配记忆模式）: {query[:30]}...")
                return True

        # 对于其他情况，检查内容长度和复杂度
        if len(query) > 20 and any(
            kw in query for kw in ["我", "喜欢", "习惯", "一般", "通常", "经常", "偏好", "爱"]
        ):
            logger.info(f"值得记忆（包含个人信息）: {query[:30]}...")
            return True

        # 检查 result 中是否包含确认记忆的内容（如"记住"、"我会记住"等）
        if result and len(result) > 10:
            result_lower = result.lower()
            if any(kw in result_lower for kw in ["记住", "我会", "已记录", "已保存", "下次"]):
                logger.info(f"值得记忆（助手确认会记住）: {query[:30]}...")
                return True

        logger.debug(f"跳过记忆（默认）: {query[:30]}...")
        return False

    @staticmethod
    def _get_current_location_str() -> str:
        """从车机状态中获取当前位置描述"""
        try:
            state = get_car_state(reload=True)
            vehicle = state.vehicle
            name = vehicle.current_location_name or "未知"
            coords = vehicle.current_location_coords or ""
            city = vehicle.current_location_city or ""
            parts = [name]
            if coords:
                parts.append(coords)
            if city:
                parts.append(city)
            return "当前位置：" + " | ".join(parts)
        except Exception:
            return "当前位置：未知"

    @staticmethod
    def _build_context_message(
        speaker_info: dict = None,
        current_location: str = "",
        long_term_memory: str = "",
        current_car_state: dict | None = None,
    ) -> dict | None:
        """构建包含说话者/位置/长期记忆的系统上下文消息"""
        context_lines = []
        if speaker_info:
            context_lines.append(
                f"对话者：{speaker_info.get('name', '未知')} ({speaker_info.get('seat', '未知')})"
            )
        if current_location:
            context_lines.append(current_location)
        if long_term_memory:
            context_lines.append("长期记忆摘要：")
            context_lines.append(long_term_memory)
        if current_car_state:
            context_lines.append("当前车机状态：")
            context_lines.append(json.dumps(current_car_state, ensure_ascii=False))

        if not context_lines:
            return None

        content = "以下为对话上下文信息（供参考）：\n" + "\n".join(context_lines)
        return SystemMessage(content=content).model_dump(exclude_none=True)
