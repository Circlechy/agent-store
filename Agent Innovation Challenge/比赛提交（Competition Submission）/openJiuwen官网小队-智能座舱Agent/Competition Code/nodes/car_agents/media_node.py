import os
import logging
import dotenv

from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory
from openjiuwen.core.utils.llm.messages import HumanMessage, SystemMessage

from nodes.base_node import BaseNode
from prompts.template import apply_template
from tools.tool_exec import process_tool_exec
from nodes.utils.utils import requires_tool_call, trim_internal_messages, trim_tool_trace, emit_plan_update
from tools.carTools.media import (
    get_media_state,
    play_music,
    pause_music,
    resume_music,
    next_track,
    set_volume,
    play_radio,
)

dotenv.load_dotenv(dotenv_path=".env")

logger = logging.getLogger(__name__)
factory = ModelFactory()
model_name = os.getenv("MODEL_NAME")
max_tool_loop = int(os.getenv("MAX_TOOL_LOOP", 3))


class MediaNode(BaseNode):
    def __init__(self):
        super().__init__()
        self.name = "media_node"
        self.current_step = 0
        self.next_node = None

    async def _do_invoke(self, inputs, runtime, context):
        model = factory.get_model(
            model_provider=os.getenv("MODEL_PROVIDER"),
            api_base=os.getenv("API_BASE"),
            api_key=os.getenv("API_KEY"),
            max_retries=3,
            timeout=600,
        )
        plan = runtime.get_global_state("sub_context.plan")
        if plan:
            external_messages = runtime.get_global_state("sub_context.external_messages") or []
            # Use a fresh local context per task; do not reuse internal_messages in-flight.
            messages = []
            found_task = False
            for idx, step in enumerate(plan):
                if step.get("is_finished") == False and step.get("node") == self.name:
                    query = step.get("task")
                    self.current_step = idx
                    messages.append(HumanMessage(content=query).model_dump(exclude_none=True))
                    found_task = True

                    agent_input = {
                        "language": runtime.get_global_state("language"),
                        "messages": messages,
                        "external_messages": external_messages
                    }
                    break

            if not found_task:
                # Skip execution if this node has no pending task in plan.
                for step in plan:
                    if step.get("is_finished") == False and step.get("node"):
                        self.next_node = step.get("node")
                        break
                if not self.next_node:
                    self.next_node = "end"
                return dict(next_node=self.next_node)
        else:
            # Copy to avoid mutating shared messages in-place during tool loop.
            messages = list(runtime.get_global_state("messages") or [])
            query = runtime.get_global_state("query")
            messages.append(HumanMessage(content=query).model_dump(exclude_none=True))

            agent_input = {
                "language": runtime.get_global_state("language"),
                "messages": messages
            }

        messages = apply_template("car_agent", agent_input)
        result = None

        tools = [
            get_media_state.get_tool_info(),
            play_music.get_tool_info(),
            pause_music.get_tool_info(),
            resume_music.get_tool_info(),
            next_track.get_tool_info(),
            set_volume.get_tool_info(),
            play_radio.get_tool_info(),
        ]
        tools_dict = {
            "get_media_state": get_media_state,
            "play_music": play_music,
            "pause_music": pause_music,
            "resume_music": resume_music,
            "next_track": next_track,
            "set_volume": set_volume,
            "play_radio": play_radio,
        }

        final_assistant_message = None
        agent_name = self.name
        tool_calls_made = False
        for i in range(max_tool_loop):
            logger.info(f"Invocation Loop: {i+1}")
            response = await model.ainvoke(model_name=model_name, messages=messages, tools=tools)
            if response and response.tool_calls != []:
                tool_calls_made = True
                response_dict = response.model_dump(exclude_none=True)
                tool_names = [tc.get('function', {}).get('name', '') for tc in response_dict.get('tool_calls', [])]
                logger.info(f"{self.name.replace('_', ' ').title()}决定调用工具: {tool_names}")
                messages = await process_tool_exec(response_dict, tools_dict, messages, runtime)
            else:
                # 没有工具调用，检查是否真的需要调用工具
                if i == 0 and requires_tool_call(query) and not tool_calls_made:
                    # 第一轮且需要工具调用但没有调用，强制提醒
                    logger.warning(f"⚠️ 用户指令需要工具调用，但Agent未调用工具。强制提醒...")
                    messages.append(SystemMessage(
                        content="⚠️⚠️⚠️ 重要提醒：用户指令需要调用工具才能完成！\n\n" +
                               "请按照以下步骤执行：\n" +
                               "1. 先调用对应的 get_xxx_state 工具查询当前状态\n" +
                               "2. 根据查询结果，调用相应的控制工具执行操作\n" +
                               "3. 不要直接回复'已完成'，必须通过工具调用完成操作\n\n" +
                               "这是强制要求，请立即调用工具！"
                    ).model_dump(exclude_none=True))
                    continue  # 继续循环，不 break

                # 没有工具调用，说明Agent已经完成任务
                final_assistant_message = response.model_dump(exclude_none=True)
                messages.append(final_assistant_message)
                result = final_assistant_message.get("content", "")
                break

        if result is None:
            messages.append(SystemMessage(
                content="Please provide a final answer based on the previous information. No tool call allowed."
            ).model_dump(exclude_none=True))
            response = await model.ainvoke(model_name=model_name, messages=messages)
            final_assistant_message = response.model_dump(exclude_none=True)
            messages.append(final_assistant_message)
            result = final_assistant_message.get("content", "")

        if plan:
            logger.info(f"{self.name.replace('_', ' ').title()} Result: {result}")
            internal_messages = runtime.get_global_state("sub_context.internal_messages") or []
            if result:
                internal_messages.append({"role": "assistant", "agent": agent_name, "content": result})
            runtime.update_global_state({"sub_context.internal_messages": trim_internal_messages(internal_messages)})

            tool_trace = runtime.get_global_state("sub_context.tool_trace") or []
            query_idx = -1
            for idx, msg in enumerate(messages):
                if msg.get("role") == "user" and msg.get("content") == query:
                    query_idx = idx
                    break
            round_messages = messages[query_idx + 1:] if query_idx >= 0 else messages
            for msg in round_messages:
                role = msg.get("role")
                if role == "assistant" and msg.get("tool_calls"):
                    tool_trace.append({
                        "role": "assistant",
                        "agent": agent_name,
                        "tool_calls": msg.get("tool_calls")
                    })
                elif role == "tool":
                    tool_trace.append({
                        "role": "tool",
                        "agent": agent_name,
                        "tool_call_id": msg.get("tool_call_id"),
                        "name": msg.get("name"),
                        "content": msg.get("content")
                    })
            runtime.update_global_state({"sub_context.tool_trace": trim_tool_trace(tool_trace)})
            plan[self.current_step]["is_finished"] = True
            runtime.update_global_state({"sub_context.plan": plan})
            await emit_plan_update(runtime, plan, current_node=self.name)
            if self.current_step + 1 < len(plan):
                self.next_node = plan[self.current_step + 1].get("node")
            else:
                self.next_node = "end"
        else:
            runtime.update_global_state({"messages": messages})
            runtime.update_global_state({"result": result})

        return dict(next_node=self.next_node)
