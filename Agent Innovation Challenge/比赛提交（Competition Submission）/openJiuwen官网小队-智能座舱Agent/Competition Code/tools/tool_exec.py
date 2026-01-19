import json
import logging
import asyncio
import inspect
import os
from typing import Dict, List

from openjiuwen.core.utils.llm.messages import AIMessage, ToolMessage

logger = logging.getLogger(__name__)


def _get_max_concurrency_from_env(default_value: int = 3) -> int:
    raw_value = os.getenv("MAX_TOOL_CONCURRENCY")
    if raw_value is None:
        return default_value
    try:
        value = int(raw_value)
        return value if value > 0 else default_value
    except ValueError:
        return default_value


def _is_large_blob(value: str) -> bool:
    if not value:
        return False
    if len(value) > 2000:
        return True
    if value.startswith("data:image/"):
        return True
    return False


def _summarize_value(value, max_len: int = 80) -> str:
    text = str(value)
    if _is_large_blob(text):
        return "已省略(内容过大)"
    text = text.replace("\n", " ").strip()
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def _summarize_args(args) -> str:
    if not isinstance(args, dict):
        return _summarize_value(args)
    parts = []
    for key, value in args.items():
        parts.append(f"{key}={_summarize_value(value)}")
    return ", ".join(parts)


def _summarize_result(result, max_len: int = 120) -> str:
    if isinstance(result, dict):
        text = json.dumps(result, ensure_ascii=False)
    else:
        text = str(result)
    text = text.replace("\n", " ").strip()
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def _parse_status_code(value):
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return None


def _infer_success_from_dict(payload: dict):
    if "success" in payload:
        return bool(payload.get("success"))

    for key in ["error", "errors", "err", "exception", "failed", "failure"]:
        if key in payload:
            value = payload.get(key)
            if isinstance(value, bool):
                return not value if key in ["error", "errors", "err", "exception"] else not value
            if isinstance(value, (list, tuple, dict)):
                return len(value) == 0
            return not bool(value)

    status_value = payload.get("status")
    if status_value is not None:
        status_code = _parse_status_code(status_value)
        if status_code is not None:
            return status_code in [0, 200, 201]
        if isinstance(status_value, str):
            lowered = status_value.strip().lower()
            if lowered in ["ok", "success", "succeeded", "true"]:
                return True
            if lowered in ["failed", "failure", "error", "false"]:
                return False

    for key in ["code", "error_code", "errcode"]:
        if key in payload:
            code_value = payload.get(key)
            code = _parse_status_code(code_value)
            if code is not None:
                return code in [0, 200, 201]

    for key in ["message", "msg"]:
        if key in payload and isinstance(payload.get(key), str):
            lowered = payload.get(key, "").lower()
            if any(token in lowered for token in ["failed", "failure", "error", "错误", "失败"]):
                return False
            if any(token in lowered for token in ["ok", "success", "成功"]):
                return True

    return True


def _infer_success(tool_result):
    if tool_result is None:
        return None
    if isinstance(tool_result, dict):
        return _infer_success_from_dict(tool_result)
    if isinstance(tool_result, str):
        lowered = tool_result.lower()
        if any(token in lowered for token in ["failed", "failure", "error", "错误", "失败"]):
            return False
        return True
    return True


async def _emit_runtime_event(runtime, payload: dict):
    if runtime is None:
        return
    try:
        emitter = runtime.get_global_state("event_emitter")
    except Exception:
        emitter = None
    if not emitter:
        return
    try:
        result = emitter(payload)
        if asyncio.iscoroutine(result):
            await result
    except Exception as e:
        logger.debug(f"Runtime event emit failed: {e}")


async def process_tool_exec(response, tool_dict: Dict, messages: List, runtime=None):
    tool_calls = response.get("tool_calls", [])
    if not tool_calls:
        return messages

    call_message = AIMessage(tool_calls=tool_calls).model_dump(exclude_none=True)
    messages.append(call_message)

    max_concurrency = _get_max_concurrency_from_env()

    semaphore = asyncio.Semaphore(max_concurrency) if max_concurrency and max_concurrency > 0 else None

    async def run_with_limit(tool_call):
        if semaphore is None:
            return await tool_execution(tool_call, tool_dict, runtime)
        async with semaphore:
            return await tool_execution(tool_call, tool_dict, runtime)

    tasks = [asyncio.create_task(run_with_limit(tool_call)) for tool_call in tool_calls]
    for task in asyncio.as_completed(tasks):
        tool_message = await task
        messages.append(tool_message)

    return messages


async def tool_execution(tool_call, tool_dict: Dict, runtime=None):
    tool_name = tool_call.get("function", {}).get("name", "")
    tool_id = tool_call.get("id", "")
    args = tool_call.get("function", {}).get("arguments", {})
    agent_name = None
    try:
        agent_name = runtime.get_global_state("current_agent") if runtime else None
    except Exception:
        agent_name = None

    await _emit_runtime_event(runtime, {
        "type": "tool_start",
        "tool": tool_name,
        "tool_call_id": tool_id,
        "agent": agent_name,
        "args_summary": _summarize_args(args)
    })
    try:
        tool_result = await exec_tool(tool_call, tool_dict, runtime)
    except Exception as e:
        tool_result = f"Tool execution failed: {str(e)}"

    success = _infer_success(tool_result)

    await _emit_runtime_event(runtime, {
        "type": "tool_end",
        "tool": tool_name,
        "tool_call_id": tool_id,
        "agent": agent_name,
        "success": success,
        "result_summary": _summarize_result(tool_result)
    })
    tool_message = gen_tool_message(tool_call, tool_result)

    return tool_message


def gen_tool_message(tool_call, tool_result):
    tool_name = tool_call.get("function", {}).get("name", "")
    tool_id = tool_call.get("id", "")
    
    # Convert tool_result to string if it's a dict
    if isinstance(tool_result, dict):
        content = json.dumps(tool_result, ensure_ascii=False)
    else:
        content = str(tool_result)
    
    tool_message = ToolMessage(
        tool_call_id=tool_id,
        name=tool_name,
        content=content
    )

    return tool_message.model_dump(exclude_none=True)


async def exec_tool(tool_call, tool_dict: Dict, runtime=None):
    tool_name = tool_call.get("function", {}).get("name", "")
    logger.info(f"[TOOL START] Executing tool: {tool_name}")
    args = tool_call.get("function", {}).get("arguments", {})
    
    if isinstance(args, str):
        logger.info(f"[TOOL ARGS] Raw arguments string for {tool_name}: {repr(args)}")
        try:
            # 尝试解析 JSON
            args = json.loads(args)
        except json.JSONDecodeError as e:
            logger.error(f"[TOOL ERROR] Failed to parse arguments for {tool_name}: {e}")
            logger.error(f"[TOOL ERROR] Arguments content: {repr(args)}")
            # 尝试修复：补全可能缺失的括号
            try:
                fixed_args = args.rstrip()
                # 计算缺失的括号数量
                open_braces = fixed_args.count('{')
                close_braces = fixed_args.count('}')
                missing_braces = open_braces - close_braces
                if missing_braces > 0:
                    fixed_args += '}' * missing_braces
                    logger.info(f"[TOOL RECOVERY] Added {missing_braces} missing braces")
                    args = json.loads(fixed_args)
                else:
                    raise
            except Exception as retry_e:
                logger.error(f"[TOOL ERROR] Recovery attempt failed: {retry_e}")
                return f"Tool execution failed: Invalid arguments format. Expected valid JSON, got: {args}"
    
    # 处理特殊的图片路径引用（支持多种格式）
    # 如果工具参数中包含图片路径引用，从 runtime 获取实际的图片数据
    if runtime is not None and isinstance(args, dict):
        # 需要处理图片路径的工具列表
        image_tools = ['analyze_image', 'ask_about_image', 'identify_location', 
                       'check_parking_spot', 'read_road_sign', 'analyze_dashcam_frame',
                       'scan_car_interior', 'identify_vehicle_ahead']
        
        for key, value in args.items():
            if not isinstance(value, str):
                continue
            
            new_value = None
            current_image_data = runtime.get_global_state("current_image_data")
            
            # 格式1: 直接匹配 "current_image_data"
            if value == "current_image_data":
                if current_image_data:
                    new_value = current_image_data
                    logger.info(f"[TOOL] Replaced 'current_image_data' with actual image data for param '{key}'")
                else:
                    logger.warning(f"[TOOL] 'current_image_data' referenced but no image data in runtime state")
            
            # 格式2: global://key 前缀格式
            elif value.startswith('global://'):
                global_key = value.replace('global://', '')
                global_value = runtime.get_global_state(global_key)
                if global_value:
                    new_value = global_value
                    logger.info(f"[TOOL] Resolved global://{global_key} for param '{key}'")
                elif current_image_data:
                    new_value = current_image_data
                    logger.info(f"[TOOL] global://{global_key} not found, using current_image_data as fallback")
                else:
                    logger.warning(f"[TOOL] Cannot resolve global://{global_key}, no fallback available")
            
            # 格式3: global_state://key 前缀格式
            elif value.startswith('global_state://'):
                global_key = value.replace('global_state://', '')
                global_value = runtime.get_global_state(global_key)
                if global_value:
                    new_value = global_value
                    logger.info(f"[TOOL] Resolved global_state://{global_key} for param '{key}'")
                elif current_image_data:
                    new_value = current_image_data
                    logger.info(f"[TOOL] global_state://{global_key} not found, using current_image_data as fallback")
                else:
                    logger.warning(f"[TOOL] Cannot resolve global_state://{global_key}, no fallback available")
            
            # 格式4: global_state:key 单冒号格式（Agent常用）
            elif 'global_state:' in value:
                if ':' in value:
                    global_key = value.split(':', 1)[1]
                    global_value = runtime.get_global_state(global_key)
                    if global_value:
                        new_value = global_value
                        logger.info(f"[TOOL] Resolved global_state:{global_key} for param '{key}'")
                    elif current_image_data:
                        new_value = current_image_data
                        logger.info(f"[TOOL] global_state:{global_key} not found, using current_image_data as fallback")
                    else:
                        logger.warning(f"[TOOL] Cannot resolve global_state:{global_key}, no fallback available")
            
            # 应用替换
            if new_value:
                args[key] = new_value

    try:
        tool = tool_dict.get(tool_name)
        if tool is None:
            return f"Tool execution failed: Tool '{tool_name}' not found"
        
        result = None
        last_error = None
        
        # 方式1: 尝试使用同步的 invoke 方法（openjiuwen 标准方式）
        # 根据测试代码，这是正确的调用方式
        if hasattr(tool, 'invoke'):
            try:
                logger.info(f"[TOOL] Trying invoke method for {tool_name}")
                result = tool.invoke(inputs=args)
                # 如果返回的是协程，等待它
                if asyncio.iscoroutine(result):
                    result = await result
                logger.info(f"[TOOL] invoke method succeeded for {tool_name}")
            except Exception as e:
                last_error = e
                logger.info(f"[TOOL] invoke method failed: {e}")
                result = None
        
        # 方式2: 尝试使用 ainvoke (异步版本)
        if result is None and hasattr(tool, 'ainvoke'):
            try:
                logger.info(f"[TOOL] Trying ainvoke method for {tool_name}")
                result = await tool.ainvoke(inputs=args)
                logger.info(f"[TOOL] ainvoke method succeeded for {tool_name}")
            except Exception as e:
                last_error = e
                logger.info(f"[TOOL] ainvoke method failed: {e}")
                result = None
        
        # 方式3: 尝试使用 run 方法
        if result is None and hasattr(tool, 'run'):
            try:
                logger.info(f"[TOOL] Trying run method for {tool_name}")
                result = tool.run(**args)
                if asyncio.iscoroutine(result):
                    result = await result
                logger.info(f"[TOOL] run method succeeded for {tool_name}")
            except Exception as e:
                last_error = e
                logger.info(f"[TOOL] run method failed: {e}")
                result = None
        
        # 方式4: 尝试获取底层函数并直接调用
        if result is None and hasattr(tool, 'func'):
            try:
                logger.info(f"[TOOL] Trying func attribute for {tool_name}")
                func = tool.func
                if asyncio.iscoroutinefunction(func):
                    result = await func(**args)
                else:
                    result = func(**args)
                logger.info(f"[TOOL] func attribute succeeded for {tool_name}")
            except Exception as e:
                last_error = e
                logger.info(f"[TOOL] func attribute failed: {e}")
                result = None
        
        # 方式5: 尝试获取 _func 属性
        if result is None and hasattr(tool, '_func'):
            try:
                logger.info(f"[TOOL] Trying _func attribute for {tool_name}")
                func = tool._func
                if asyncio.iscoroutinefunction(func):
                    result = await func(**args)
                else:
                    result = func(**args)
                logger.info(f"[TOOL] _func attribute succeeded for {tool_name}")
            except Exception as e:
                last_error = e
                logger.info(f"[TOOL] _func attribute failed: {e}")
                result = None
        
        # 方式6: 如果工具本身可调用，尝试直接调用
        if result is None and callable(tool):
            try:
                logger.info(f"[TOOL] Trying direct call for {tool_name}")
                if asyncio.iscoroutinefunction(tool):
                    result = await tool(**args)
                else:
                    result = tool(**args)
                logger.info(f"[TOOL] direct call succeeded for {tool_name}")
            except Exception as e:
                last_error = e
                logger.info(f"[TOOL] direct call failed: {e}")
                result = None
        
        # 方式7: 检查其他可能的属性
        if result is None:
            for attr_name in ['__wrapped__', 'original_func', 'wrapped_func', '_call']:
                if hasattr(tool, attr_name):
                    try:
                        logger.info(f"[TOOL] Trying {attr_name} attribute for {tool_name}")
                        func = getattr(tool, attr_name)
                        if callable(func):
                            if asyncio.iscoroutinefunction(func):
                                result = await func(**args)
                            else:
                                result = func(**args)
                            logger.info(f"[TOOL] {attr_name} attribute succeeded for {tool_name}")
                            break
                    except Exception as e:
                        last_error = e
                        logger.info(f"[TOOL] {attr_name} attribute failed: {e}")
        
        if result is None:
            # 记录工具对象的所有属性，帮助调试
            tool_attrs = [attr for attr in dir(tool) if not attr.startswith('_')]
            logger.error(f"[TOOL] Could not invoke tool '{tool_name}'. Tool type: {type(tool)}, available attrs: {tool_attrs}")
            if last_error:
                return f"Tool execution failed: {str(last_error)}"
            return f"Tool execution failed: Could not invoke tool '{tool_name}'"
        
        if tool_name == "get_camera_image" and runtime is not None and isinstance(result, dict):
            image_data = result.get("image_data")
            if image_data:
                runtime.update_global_state({"current_image_data": image_data})
                result.pop("image_data", None)
                result["image_ref"] = "current_image_data"
                logger.info("[TOOL] Stored camera image in runtime global_state: current_image_data")

        logger.info(f"[TOOL END] Tool {tool_name} executed successfully.")
        return result
        
    except Exception as e:
        result = f"Tool execution failed: {str(e)}"
        logger.error(f"[TOOL ERROR] Tool {tool_name} execution failed with error: {str(e)}")
        import traceback
        logger.error(f"[TOOL ERROR] Traceback: {traceback.format_exc()}")
        return result
