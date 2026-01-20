import os
import logging
import dotenv

from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory
from openjiuwen.core.utils.llm.messages import HumanMessage, SystemMessage

from nodes.base_node import BaseNode
from nodes.utils.utils import (
    requires_tool_call,
    trim_internal_messages,
    trim_tool_trace,
    emit_plan_update,
    detect_location_update,
    get_user_location_prompt,
)
from prompts.template import apply_template
from tools.gitcode import search_repo
from tools.tavily import tavily_search, tavily_extract
from tools.tool_exec import process_tool_exec
from tools.baidu_map import (
    baidu_place_search,
    baidu_place_search_nearby,
)
from tools.vision_tools import (
    analyze_image,
    identify_location,
    check_parking_spot,
    read_road_sign,
    analyze_dashcam_frame,
    scan_car_interior,
    analyze_camera_view,
    identify_vehicle_ahead,
    check_surroundings,
    ask_about_image,
    create_traffic_report,
)

dotenv.load_dotenv(dotenv_path=".env")

logger = logging.getLogger(__name__)
factory = ModelFactory()
model_name = os.getenv("MODEL_NAME")
max_tool_loop = int(os.getenv("MAX_TOOL_LOOP", 3))


class AgentNode(BaseNode):
    def __init__(self):
        super().__init__()
        self.name = "agent_node"
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
            environment_alerts = runtime.get_global_state("sub_context.environment_alerts") or ""
            # Use a fresh local context per task; do not reuse internal_messages in-flight.
            messages = []
            found_task = False
            for idx, step in enumerate(plan):
                if step.get("is_finished") == False and step.get("node") == self.name:
                    query = step.get("task")
                    self.current_step = idx
                    detect_location_update(query)
                    messages.append(HumanMessage(content=query).model_dump(exclude_none=True))
                    found_task = True

                    agent_input = {
                        "language": runtime.get_global_state("language"),
                        "messages": messages,
                        "external_messages": external_messages,
                        "environment_alerts": environment_alerts,
                        "user_location_prompt": get_user_location_prompt(),
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
            detect_location_update(query)
            messages.append(HumanMessage(content=query).model_dump(exclude_none=True))

            agent_input = {
                "language": runtime.get_global_state("language"),
                "messages": messages,
                "environment_alerts": runtime.get_global_state("environment_alerts") or "",
                "user_location_prompt": get_user_location_prompt(),
            }

        messages = apply_template("standard", agent_input)
        result = None

        tools = [
            search_repo.get_tool_info(),
            tavily_search.get_tool_info(),
            tavily_extract.get_tool_info(),
            baidu_place_search.get_tool_info(),
            baidu_place_search_nearby.get_tool_info(),
            analyze_image.get_tool_info(),
            identify_location.get_tool_info(),
            check_parking_spot.get_tool_info(),
            read_road_sign.get_tool_info(),
            analyze_dashcam_frame.get_tool_info(),
            scan_car_interior.get_tool_info(),
            analyze_camera_view.get_tool_info(),
            identify_vehicle_ahead.get_tool_info(),
            check_surroundings.get_tool_info(),
            ask_about_image.get_tool_info(),
            create_traffic_report.get_tool_info(),
        ]
        tools_dict = {
            "search_repo": search_repo,
            "tavily_search": tavily_search,
            "tavily_extract": tavily_extract,
            "baidu_place_search": baidu_place_search,
            "baidu_place_search_nearby": baidu_place_search_nearby,
            "analyze_image": analyze_image,
            "identify_location": identify_location,
            "check_parking_spot": check_parking_spot,
            "read_road_sign": read_road_sign,
            "analyze_dashcam_frame": analyze_dashcam_frame,
            "scan_car_interior": scan_car_interior,
            "analyze_camera_view": analyze_camera_view,
            "identify_vehicle_ahead": identify_vehicle_ahead,
            "check_surroundings": check_surroundings,
            "ask_about_image": ask_about_image,
            "create_traffic_report": create_traffic_report,
        }

        final_assistant_message = None
        agent_name = self.name
        tool_calls_made = False
        # Tool invocation loop
        for i in range(max_tool_loop):
            logger.info(f"Invocation Loop: {i+1}")
            response = await model.ainvoke(model_name=model_name, messages=messages, tools=tools)
            if response and response.tool_calls != []:
                response_dict = response.model_dump(exclude_none=True)
                tool_calls = response_dict.get("tool_calls", [])
                allowed_tool_names = set(tools_dict.keys())
                valid_tool_calls = []
                invalid_tool_names = []
                for tool_call in tool_calls:
                    tool_name = tool_call.get("function", {}).get("name", "")
                    if tool_name in allowed_tool_names:
                        valid_tool_calls.append(tool_call)
                    else:
                        invalid_tool_names.append(tool_name or "(unknown)")

                if invalid_tool_names:
                    logger.warning(f"{self.name.replace('_', ' ').title()}尝试调用未授权工具: {invalid_tool_names}")
                    messages.append(SystemMessage(
                        content="⚠️⚠️⚠️ 重要提醒：你只能调用当前节点提供的工具，禁止调用未授权工具。\n\n"
                                f"未授权工具: {', '.join(invalid_tool_names)}\n"
                                f"允许的工具: {', '.join(sorted(allowed_tool_names))}\n\n"
                                "请改用允许的工具，或直接给出无需工具的最终答复。"
                    ).model_dump(exclude_none=True))

                if not valid_tool_calls:
                    continue

                tool_calls_made = True
                response_dict["tool_calls"] = valid_tool_calls
                tool_names = [tc.get('function', {}).get('name', '') for tc in valid_tool_calls]
                logger.info(f"{self.name.replace('_', ' ').title()}决定调用工具: {tool_names}")
                messages = await process_tool_exec(response_dict, tools_dict, messages, runtime)
            else:
                # 没有工具调用，检查是否真的需要调用工具
                has_image = bool(runtime.get_global_state("current_image_data"))
                if i == 0 and requires_tool_call(query, has_image=has_image) and not tool_calls_made:
                    # 第一轮且需要工具调用但没有调用，强制提醒
                    logger.warning(f"⚠️ 用户指令需要工具调用，但Agent未调用工具。强制提醒...")
                    messages.append(SystemMessage(
                        content="⚠️⚠️⚠️ 重要提醒：用户指令需要调用工具才能完成！\n\n" +
                               "请按照以下步骤执行：\n" +
                               "1. 先调用对应的工具查询相关信息\n" +
                               "2. 根据查询结果，调用相应的工具执行操作\n" +
                               "3. 不要直接回复'已完成'，必须通过工具调用完成操作\n\n" +
                               "4. 不要反复调用同一个工具，除非有新的信息需要查询\n\n" +
                               "这是强制要求，请立即调用工具！"
                    ).model_dump(exclude_none=True))
                    if has_image:
                        messages.append(SystemMessage(
                            content="⚠️⚠️⚠️ 重要提醒：用户输入了图片/视频，需要调用视觉工具分析当前视觉信息，再调用相应的工具执行操作。"
                        ).model_dump(exclude_none=True))
                    continue  # 继续循环，不 break

                # 没有工具调用，说明Agent已经完成任务
                final_assistant_message = response.model_dump(exclude_none=True)
                messages.append(final_assistant_message)
                result = final_assistant_message.get("content", "")
                break
        
        # Final response if no result yet
        if result is None:
            messages.append(SystemMessage(content="Please provide a final answer based on the previous information. No tool call allowed.").model_dump(exclude_none=True))
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
