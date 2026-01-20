"""
API 端点

提供智能体生成的 HTTP 接口
"""
from typing import Optional, Any, Dict
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger
import json
import time
import shutil
from pathlib import Path

from app.services.unified_generation_service import UnifiedGenerationService
from app.config.settings import get_settings
from app.sandbox.sandbox import generate_setup_path_code


router = APIRouter(tags=["agent"])

# 全局服务实例
_service: Optional[UnifiedGenerationService] = None

# 全局 Agent 实例缓存（用于支持多轮对话）
# key: workflow_dir, value: agent instance
_agent_cache: Dict[str, Any] = {}

# 全局 Group 实例缓存（用于 Multi-Agent 模式的多轮对话）
# key: workflow_dir, value: group instance
_group_cache: Dict[str, Any] = {}

# 全局模块文件修改时间缓存（用于检测文件更新）
# key: workflow_dir, value: {module_name: mtime, ...}
_module_mtimes: Dict[str, Dict[str, float]] = {}

# 全局 Workflow 执行状态缓存（用于人机交互）
# key: execution_id, value: {workflow_agent, response, conv_id, workflow_dir_str}
_workflow_execution_cache: Dict[str, Dict[str, Any]] = {}


def get_service() -> UnifiedGenerationService:
    """获取服务实例"""
    global _service
    if _service is None:
        _service = UnifiedGenerationService()
    return _service


def _extract_content_from_result(result: Any) -> str:
    """
    从工作流执行结果中提取可序列化的内容字符串
    
    Args:
        result: 工作流执行结果（可能是 dict, WorkflowOutput, 或其他类型）
    
    Returns:
        提取的内容字符串
    """
    # 检查是否为 WorkflowOutput 类型（Pydantic BaseModel）
    if hasattr(result, "result") and hasattr(result, "state"):
        # 这是 WorkflowOutput 对象，提取其中的 result 字段
        workflow_result = result.result
        if isinstance(workflow_result, dict):
            # 如果 result 是字典，尝试提取常见字段（优先提取 responseContent）
            content = (workflow_result.get("responseContent", "") or 
                      workflow_result.get("output", "") or 
                      workflow_result.get("content", "") or 
                      workflow_result.get("answer", ""))
            if content:
                return str(content)
            # 如果没有找到常见字段，将整个字典转换为字符串
            try:
                import json
                return json.dumps(workflow_result, ensure_ascii=False, default=str)
            except Exception:
                return str(workflow_result)
        elif isinstance(workflow_result, (list, tuple)):
            # 如果是列表，尝试提取其中的内容
            content_parts = []
            for item in workflow_result:
                if hasattr(item, "payload"):
                    # 可能是 OutputSchema，提取 payload
                    payload = item.payload
                    if isinstance(payload, dict):
                        content_parts.append(str(payload.get("answer", "") or payload.get("content", "")))
                    else:
                        content_parts.append(str(payload))
                else:
                    content_parts.append(str(item))
            return "".join(filter(None, content_parts))
        else:
            return str(workflow_result)
    
    # 如果是字典类型
    if isinstance(result, dict):
        # 优先提取 responseContent 字段，然后尝试其他常见字段
        content = (result.get("responseContent", "") or 
                  result.get("output", "") or 
                  result.get("content", "") or 
                  result.get("answer", ""))
        if content:
            # 如果 content 本身还是对象，继续提取
            if hasattr(content, "result"):
                return _extract_content_from_result(content)
            return str(content)
        # 如果没有找到常见字段，尝试序列化整个字典
        try:
            import json
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception:
            return str(result)
    
    # 其他类型，直接转换为字符串
    return str(result)


class BuildRequest(BaseModel):
    """构建请求"""
    user_input: str = Field(description="用户的自然语言描述")
    workflow_name: Optional[str] = Field(default="default", description="工作流名称")
    agent_mode: str = Field(default="workflow", description="生成模式: react/workflow/multi_agent")
    max_iterations: int = Field(default=3, ge=1, le=10, description="最大迭代次数")


class ModifyRequest(BaseModel):
    """修改请求"""
    workflow_dir: str = Field(description="工作流目录路径（相对或绝对路径）")
    modification_request: str = Field(description="当前修改需求（自然语言）")
    conversation_id: Optional[str] = Field(default=None, description="会话ID（用于获取历史需求）")
    max_iterations: int = Field(default=3, ge=1, le=10, description="最大迭代次数")


class ExecuteRequest(BaseModel):
    """执行请求"""
    workflow_dir: str = Field(description="工作流目录路径")
    query: str = Field(description="用户查询")
    conversation_id: Optional[str] = Field(default=None, description="会话 ID（用于多轮对话）")


class ClearHistoryRequest(BaseModel):
    """清除历史请求"""
    workflow_dir: str = Field(description="工作流目录路径")
    conversation_id: str = Field(description="会话 ID")


class ContinueExecutionRequest(BaseModel):
    """继续执行请求（用于人机交互）"""
    execution_id: str = Field(description="执行 ID")
    reply_value: str = Field(description="用户回复内容")
    component_id: str = Field(description="组件 ID")


class ContinueExecutionRequest(BaseModel):
    """继续执行请求（用于人机交互）"""
    execution_id: str = Field(description="执行 ID")
    reply_value: str = Field(description="用户回复内容")
    component_id: str = Field(description="组件 ID")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    settings = get_settings()
    return HealthResponse(status="healthy", version=settings.app_version)


@router.post("/agent/build")
@router.post("/agent/start")
async def build_agent(request: BuildRequest):
    """
    构建智能体（SSE 流式响应）
    
    支持两个端点：
    - /api/v1/agent/build (向后兼容)
    - /api/v1/agent/start (前端使用)
    
    Args:
        request: 构建请求
    
    Returns:
        SSE 事件流
    """
    service = get_service()
    
    async def event_generator():
        """生成 SSE 事件"""
        try:
            async for event_str in service.generate(
                user_input=request.user_input,
                agent_mode=request.agent_mode,
                workflow_name=request.workflow_name or "default",
                max_iterations=request.max_iterations
            ):
                yield event_str
                
        except Exception as e:
            logger.error(f"生成过程发生错误: {e}", exc_info=True)
            error_event = {
                "type": "error",
                "message": str(e),
                "error": str(e)
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


def _normalize_workflow_path(workflow_dir: str):
    """将 Agent 目录路径标准化为绝对路径（适用于所有模式）"""
    from pathlib import Path
    
    workflow_path = Path(workflow_dir)
    if not workflow_path.is_absolute():
        # 从 backend_v3/app/api/v1/endpoints.py 向上5层到项目根目录
        project_root = Path(__file__).parent.parent.parent.parent.parent
        workflow_path = project_root / workflow_dir
        logger.debug(f"路径转换: {workflow_dir} -> {workflow_path} (项目根: {project_root})")
    
    return workflow_path


def _setup_llm_environment():
    """从后端配置注入 LLM 环境变量"""
    import os
    settings = get_settings()
    env_vars_set = []
    
    env_mappings = [
        ("API_KEY", settings.model.api_key),
        ("API_BASE", settings.model.api_base),
        ("MODEL_NAME", settings.model.model_name),
        ("MODEL_PROVIDER", settings.model.provider),
    ]
    
    for env_name, config_value in env_mappings:
        if config_value and not os.environ.get(env_name):
            os.environ[env_name] = config_value
            env_vars_set.append(env_name)
            logger.debug(f"从配置注入 {env_name}")
    
    # 设置默认值（如果未设置）
    if "LLM_SSL_VERIFY" not in os.environ:
        os.environ["LLM_SSL_VERIFY"] = "False"
    if "SSRF_PROTECT_ENABLED" not in os.environ:
        os.environ["SSRF_PROTECT_ENABLED"] = "False"
    
    if env_vars_set:
        logger.info(f"已从后端配置注入 LLM 环境变量: {', '.join(env_vars_set)}")


def _ensure_setup_path(workflow_path):
    """检查并自动生成 setup_path.py（如果需要）"""
    from pathlib import Path
    
    setup_path_file = workflow_path / "setup_path.py"
    if setup_path_file.exists():
        return
    
    # 检查是否有文件导入了 setup_path
    for py_file in workflow_path.glob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            if "import setup_path" in content or "from setup_path" in content:
                setup_path_content = generate_setup_path_code()
                setup_path_file.write_text(setup_path_content, encoding="utf-8")
                logger.info(f"✅ 已自动生成 setup_path.py: {setup_path_file}")
                break
        except Exception:
            continue


def _normalize_path(path: str) -> str:
    """标准化路径（处理 Windows 路径分隔符）"""
    import os
    return os.path.normpath(path).replace('\\', '/')


def _clear_agent_modules(workflow_dir_str: str, module_name: str):
    """清除 Agent 目录相关的模块缓存（适用于所有模式：workflow/react/multi_agent）"""
    import sys
    import os
    
    # Agent 目录中可能存在的模块名
    agent_module_names = {
        'config', 'leader_agent', 'worker_agents', 'local_agent',
        'components', 'workflow_builder', 'setup_path'
    }
    
    # 标准化路径
    normalized_agent_dir = _normalize_path(workflow_dir_str)
    experiments_pattern = _normalize_path(os.path.join(workflow_dir_str, '..', '..', 'experiments'))
    
    cleared_modules = []
    
    for mod_name in list(sys.modules.keys()):
        mod = sys.modules[mod_name]
        mod_file = getattr(mod, '__file__', None)
        
        # 判断是否需要清除
        should_clear = False
        clear_reason = ""
        
        if mod_name.startswith('workflow_main_') and mod_name != module_name:
            # 其他工作流主模块
            should_clear = True
            clear_reason = "其他工作流主模块"
        elif mod_name in agent_module_names:
            # Agent 模块：检查是否来自其他实验目录
            if mod_file:
                mod_file_normalized = _normalize_path(str(mod_file))
                if (mod_file_normalized.startswith(experiments_pattern) and 
                    not mod_file_normalized.startswith(normalized_agent_dir)):
                    should_clear = True
                    clear_reason = f"来自其他实验目录: {mod_file}"
            elif mod_name in agent_module_names:
                # 无文件属性但可能是动态导入的冲突模块
                should_clear = True
                clear_reason = "无文件属性但可能是冲突模块（动态导入）"
        
        if should_clear:
            try:
                del sys.modules[mod_name]
                cleared_modules.append(f"{mod_name}({clear_reason})")
            except (KeyError, TypeError):
                pass
    
    if cleared_modules:
        logger.info(f"[模块清除] 已清除 {len(cleared_modules)} 个模块缓存:")
        for mod_info in cleared_modules[:10]:
            logger.info(f"[模块清除]   - {mod_info}")
        if len(cleared_modules) > 10:
            logger.info(f"[模块清除]   ... 还有 {len(cleared_modules) - 10} 个模块")
    
    return cleared_modules


def _check_files_updated(workflow_path, workflow_dir_str: str) -> bool:
    """检查 Agent 目录文件是否已更新（适用于所有模式）"""
    import os
    
    # 获取所有 Python 文件的修改时间
    py_files = list(workflow_path.glob("*.py"))
    if not py_files:
        logger.debug(f"[文件检查] 未找到 Python 文件: {workflow_path}")
        return False
    
    # 获取最新的修改时间
    latest_mtime = max(os.path.getmtime(f) for f in py_files)
    
    # 记录每个文件的修改时间
    file_mtimes = {f.name: os.path.getmtime(f) for f in py_files}
    logger.debug(f"[文件检查] 文件修改时间: {file_mtimes}")
    
    # 检查缓存
    if workflow_dir_str not in _module_mtimes:
        # 首次加载，记录修改时间
        _module_mtimes[workflow_dir_str] = {'latest': latest_mtime}
        logger.info(f"[文件检查] 首次检查，记录修改时间: {workflow_dir_str} -> {latest_mtime}")
        return False
    
    cached_mtime = _module_mtimes[workflow_dir_str].get('latest', 0)
    
    # 如果文件已更新
    if latest_mtime > cached_mtime:
        logger.info(f"[文件检查] 检测到文件已更新: {workflow_dir_str} (最新: {latest_mtime}, 缓存: {cached_mtime}, 差异: {latest_mtime - cached_mtime}秒)")
        _module_mtimes[workflow_dir_str]['latest'] = latest_mtime
        return True
    else:
        logger.debug(f"[文件检查] 文件未更新: {workflow_dir_str} (最新: {latest_mtime}, 缓存: {cached_mtime})")
    
    return False


def _cleanup_sys_path(workflow_dir_str: str, experiments_pattern: str):
    """清理 sys.path，移除其他实验目录，确保当前目录在最前面"""
    import sys
    
    # 移除所有其他实验目录（保留当前目录）
    sys.path = [
        p for p in sys.path 
        if not (_normalize_path(p).startswith(experiments_pattern) and p != workflow_dir_str)
    ]
    
    # 确保当前目录在 sys.path 的最前面
    if workflow_dir_str in sys.path:
        sys.path.remove(workflow_dir_str)
    sys.path.insert(0, workflow_dir_str)
    
    logger.info(f"[模块加载] 已清理 sys.path，当前目录已置顶: {workflow_dir_str}")
    logger.debug(f"[模块加载] sys.path 前5项: {sys.path[:5]}")


def _check_config_module_in_cache() -> dict:
    """检查 sys.modules 中是否有 config 模块"""
    import sys
    return {k: getattr(v, '__file__', None) for k, v in sys.modules.items() if k == 'config'}


def _load_workflow_module(workflow_path, workflow_dir_str: str):
    """动态加载 Agent 模块（支持缓存和自动重新加载，适用于所有模式：workflow/react/multi_agent）"""
    import importlib.util
    import sys
    import os
    from pathlib import Path
    
    main_file = workflow_path / "main.py"
    if not main_file.exists():
        raise FileNotFoundError(f"main.py 不存在: {main_file}")
    
    workflow_builder_file = workflow_path / "workflow_builder.py"
    if workflow_builder_file.exists():
        main_file = workflow_builder_file
    
    logger.info(f"[模块加载] main.py 路径: {main_file}")
    
    # 清理 sys.path
    experiments_pattern = _normalize_path(os.path.join(workflow_path.parent.parent, "experiments"))
    _cleanup_sys_path(workflow_dir_str, experiments_pattern)
    
    # 检查是否还有其他实验目录残留
    other_experiments = [
        p for p in sys.path 
        if _normalize_path(p).startswith(experiments_pattern) and p != workflow_dir_str
    ]
    if other_experiments:
        logger.warning(f"[模块加载] 警告：sys.path 中仍存在其他实验目录: {other_experiments}")
    
    # 生成唯一模块名
    module_name = f"workflow_main_{hash(workflow_dir_str) % 1000000}"
    logger.info(f"[模块加载] 模块名: {module_name}")
    
    # 检查文件是否已更新
    files_updated = _check_files_updated(workflow_path, workflow_dir_str)
    logger.info(f"[模块加载] 文件更新检查结果: {files_updated}")
    
    # 清除可能冲突的模块缓存（无论文件是否更新）
    config_modules_before = _check_config_module_in_cache()
    if config_modules_before:
        logger.warning(f"[模块加载] 检测到 sys.modules 中已有 'config' 模块: {config_modules_before}")
    
    cleared = _clear_agent_modules(workflow_dir_str, module_name)
    logger.info(f"[模块加载] 已清除 {len(cleared)} 个可能冲突的模块缓存")
    
    # 确认清除结果
    config_modules_after = _check_config_module_in_cache()
    if config_modules_after:
        logger.warning(f"[模块加载] 警告：清除后 sys.modules 中仍有 'config' 模块: {config_modules_after}")
    else:
        logger.info(f"[模块加载] 确认：sys.modules 中的 'config' 模块已清除")
    
    # 如果文件已更新，清除实例缓存
    if files_updated:
        if workflow_dir_str in _agent_cache:
            del _agent_cache[workflow_dir_str]
            logger.info(f"[模块加载] 已清除 Agent 实例缓存")
        if workflow_dir_str in _group_cache:
            del _group_cache[workflow_dir_str]
            logger.info(f"[模块加载] 已清除 Group 实例缓存")
    
    # 加载或重新加载模块
    module_in_cache = module_name in sys.modules
    if module_in_cache and not files_updated:
        module = sys.modules[module_name]
        logger.info(f"[模块加载] 复用已加载的模块 (文件: {getattr(module, '__file__', 'N/A')})")
        return module
    
    # 首次加载或重新加载
    load_type = "重新加载" if module_in_cache else "首次加载"
    logger.info(f"[模块加载] {load_type}模块: {workflow_dir_str}")
    
    try:
        spec = importlib.util.spec_from_file_location(module_name, main_file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        logger.info(f"[模块加载] 开始执行模块: {main_file}")
        spec.loader.exec_module(module)
        logger.info(f"[模块加载] 模块执行完成")
        return module
    except Exception as e:
        logger.error(f"[模块加载] 加载模块失败: {e}", exc_info=True)
        if module_name in sys.modules:
            del sys.modules[module_name]
        raise


async def _execute_multi_agent_mode(module: Any, cache_key: str, query: str, conv_id: str) -> str:
    """执行 Multi-Agent 模式"""
    from openjiuwen.core.agent.message.message import Message
    
    logger.info(f"[Multi-Agent] 开始执行，cache_key: {cache_key}, query: {query[:50]}...")
    
    # 获取或创建 Group 实例
    if cache_key not in _group_cache:
        logger.info(f"[Multi-Agent] 创建新的 Group 实例: {cache_key}")
        logger.info(f"[Multi-Agent] 调用 module.init_group()，模块文件: {getattr(module, '__file__', 'N/A')}")
        try:
            group_instance = await module.init_group()
            logger.info(f"[Multi-Agent] init_group() 执行成功，Group 类型: {type(group_instance)}")
        except Exception as e:
            logger.error(f"[Multi-Agent] init_group() 执行失败: {e}", exc_info=True)
            raise
        extract_response_func = getattr(module, "extract_response", None)
        logger.info(f"[Multi-Agent] extract_response 函数: {extract_response_func is not None}")
        _group_cache[cache_key] = {
            'group': group_instance,
            'extract_response': extract_response_func
        }
    else:
        logger.info(f"[Multi-Agent] 复用缓存的 Group 实例: {cache_key}")
    
    cached_data = _group_cache[cache_key]
    group_instance = cached_data['group']
    extract_response = cached_data.get('extract_response')
    
    # 执行 Group
    logger.info(f"[Multi-Agent] 开始执行 Group.invoke()，查询: {query[:50]}..., conversation_id: {conv_id}")
    message = Message.create_user_message(content=query, conversation_id=conv_id)
    result = await group_instance.invoke(message)
    logger.info(f"[Multi-Agent] Group.invoke() 执行完成，结果类型: {type(result)}")
    
    # 提取响应内容
    if extract_response:
        try:
            content = extract_response(result)
            logger.info("使用 main.extract_response() 提取响应内容")
        except Exception as e:
            logger.warning(f"extract_response 函数执行失败: {e}，使用默认提取方式")
            content = _extract_content_from_result(result)
    else:
        content = _extract_content_from_result(result)
    
    return content


async def _execute_agent_mode(module: Any, cache_key: str, query: str, conv_id: str) -> str:
    """执行 ReAct Agent 模式"""
    # 获取或创建 Agent 实例
    if cache_key not in _agent_cache:
        logger.info(f"创建新的 Agent 实例: {cache_key}")
        _agent_cache[cache_key] = module.create_agent()
    else:
        logger.info(f"复用缓存的 Agent 实例: {cache_key}")
    
    agent = _agent_cache[cache_key]
    logger.info(f"执行 Agent，conversation_id: {conv_id}, query: {query[:50]}...")
    result = await agent.invoke({"query": query, "conversation_id": conv_id})
    logger.info(f"Agent 执行完成，conversation_id: {conv_id}")
    
    return _extract_content_from_result(result)


async def _execute_workflow_mode(module: Any, query: str, conv_id: str, workflow_dir_str: str = None) -> str:
    """执行 Workflow 模式（同步版本，用于向后兼容）"""
    from typing import List
    from openjiuwen.core.runtime.interaction.interactive_input import InteractiveInput
    from openjiuwen.core.stream.base import OutputSchema
    logger.info(f"执行 Workflow 模式，conversation_id: {conv_id}, query: {query[:50]}...")
    build_workflow_agent = getattr(module, 'build_workflow_agent', None)
    workflow_agent = build_workflow_agent()
    response = await workflow_agent.invoke({"query": query, "conversation_id": conv_id})

    # 处理人机交互流程（必须严格遵守，不能有任何修改，不能有任何遗漏）
    while isinstance(response, List):
        interactive_input = InteractiveInput()
        for item in response:
            if isinstance(item, OutputSchema) and item.type == '__interaction__':
                component_id = item.payload.id
                question = item.payload.value

                reply_value = input(f"请输入回答: ")
                interactive_input.update(component_id, reply_value)
        response = await workflow_agent.invoke({"conversation_id": conv_id, "query": interactive_input})

    print(f"执行结果: {response}")
    logger.info(f"Workflow 执行完成，conversation_id: {conv_id}")
    return _extract_content_from_result(response)


async def _execute_workflow_mode_stream(module: Any, query: str, conv_id: str, workflow_dir_str: str, execution_id: str):
    """
    执行 Workflow 模式（流式版本，支持人机交互）
    
    Args:
        module: 工作流模块
        query: 用户查询
        conv_id: 会话ID
        workflow_dir_str: 工作流目录路径
        execution_id: 执行ID（用于缓存执行状态）
    
    Yields:
        SSE 事件（interaction_required 或 execution_completed）
    """
    from typing import List
    from openjiuwen.core.runtime.interaction.interactive_input import InteractiveInput
    from openjiuwen.core.stream.base import OutputSchema
    
    logger.info(f"执行 Workflow 模式（流式），conversation_id: {conv_id}, query: {query[:50]}...")
    build_workflow_agent = getattr(module, 'build_workflow_agent', None)
    if not build_workflow_agent:
        error_msg = "模块中未找到 build_workflow_agent 函数"
        logger.error(error_msg)
        error_event = _create_error_event(error_msg, error_msg)
        yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
        return
    
    workflow_agent = build_workflow_agent()
    response = await workflow_agent.invoke({"query": query, "conversation_id": conv_id})

    # 处理人机交互流程
    while isinstance(response, List):
        interactive_input = InteractiveInput()
        has_interaction = False
        
        for item in response:
            if isinstance(item, OutputSchema) and item.type == '__interaction__':
                component_id = item.payload.id
                question = item.payload.value
                has_interaction = True
                
                # 保存执行状态到缓存
                _workflow_execution_cache[execution_id] = {
                    'workflow_agent': workflow_agent,
                    'response': response,
                    'conv_id': conv_id,
                    'workflow_dir_str': workflow_dir_str,
                    'component_id': component_id,
                }
                
                # 发送交互请求事件
                interaction_event = {
                    "type": "interaction_required",
                    "execution_id": execution_id,
                    "component_id": component_id,
                    "question": str(question),
                    "conversation_id": conv_id,
                    "timestamp": time.time()
                }
                logger.info(f"[Workflow] 发送交互请求: execution_id={execution_id}, question={question[:50]}...")
                yield f"data: {json.dumps(interaction_event, ensure_ascii=False)}\n\n"
                return  # 暂停执行，等待前端回复
        
        # 如果没有交互请求，说明 response 是 List 但不是交互类型，跳出循环
        break

    # 执行完成
    print(f"执行结果: {response}")
    logger.info(f"Workflow 执行完成，conversation_id: {conv_id}")
    content = _extract_content_from_result(response)
    success_event = _create_success_event(content, conv_id)
    yield f"data: {json.dumps(success_event, ensure_ascii=False)}\n\n"
    
    # 清理执行状态缓存
    if execution_id in _workflow_execution_cache:
        del _workflow_execution_cache[execution_id]


def _create_error_event(message: str, error: str) -> Dict[str, Any]:
    """创建错误事件"""
    return {
        "type": "error",
        "message": message,
        "error": error,
        "timestamp": time.time()
    }


def _create_success_event(content: str, conv_id: str) -> Dict[str, Any]:
    """创建成功事件"""
    return {
        "type": "execution_completed",
        "success": True,
        "content": content,
        "error": None,
        "conversation_id": conv_id,
        "timestamp": time.time()
    }


@router.post("/agent/execute")
async def execute_agent(request: ExecuteRequest):
    """
    执行 Agent（SSE 流式响应，适用于所有模式：workflow/react/multi_agent）
    
    Args:
        request: 执行请求
    
    Returns:
        SSE 事件流
    """
    import time
    from pathlib import Path
    
    async def event_generator():
        """生成 SSE 事件"""
        try:
            logger.info(f"[执行 Agent] 开始执行，原始路径: {request.workflow_dir}, query: {request.query[:50]}...")
            
            # 1. 标准化 Agent 目录路径
            workflow_path = _normalize_workflow_path(request.workflow_dir)
            logger.info(f"[执行 Agent] 步骤1: 路径标准化完成，完整路径: {workflow_path}")
            
            if not workflow_path.exists():
                error_msg = f"Agent 目录不存在: {request.workflow_dir}（完整路径: {workflow_path}）"
                logger.error(f"Agent 目录不存在: 原始路径={request.workflow_dir}, 完整路径={workflow_path}")
                error_event = _create_error_event(error_msg, f"Agent 目录不存在: {request.workflow_dir}")
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
                return
            
            # 列出目录中的所有文件
            all_files = list(workflow_path.glob("*"))
            logger.info(f"[执行 Agent] 步骤1: 目录文件列表: {[f.name for f in all_files]}")
            
            # 2. 设置环境变量
            logger.info(f"[执行 Agent] 步骤2: 设置 LLM 环境变量")
            _setup_llm_environment()
            
            # 3. 确保 setup_path.py 存在（如果需要）
            logger.info(f"[执行 Agent] 步骤3: 检查 setup_path.py")
            _ensure_setup_path(workflow_path)
            
            # 4. 加载 Agent 模块（适用于所有模式）
            workflow_dir_str = str(workflow_path)
            logger.info(f"[执行 Agent] 步骤4: 开始加载模块，目录: {workflow_dir_str}")
            module = _load_workflow_module(workflow_path, workflow_dir_str)
            logger.info(f"[执行 Agent] 步骤4: 模块加载完成，模块类型: {type(module)}, 模块文件: {getattr(module, '__file__', 'N/A')}")
            
            # 检查模块中可用的函数
            module_attrs = [attr for attr in dir(module) if not attr.startswith('_')]
            logger.info(f"[执行 Agent] 步骤4: 模块可用属性: {module_attrs}")
            logger.info(f"[执行 Agent] 步骤4: 检查函数 - init_group: {hasattr(module, 'init_group')}, create_agent: {hasattr(module, 'create_agent')}, run_test: {hasattr(module, 'run_test')}")
            
            # 5. 生成或使用 conversation_id
            conv_id = request.conversation_id or f"conv_{int(time.time())}"
            logger.info(f"[执行 Agent] 步骤5: conversation_id: {conv_id}")
            
            # 6. 根据模块支持的模式执行
            cache_key = workflow_dir_str
            content = ""
            
            if hasattr(module, "init_group"):
                logger.info(f"[执行 Agent] 步骤6: 检测到 Multi-Agent 模式，开始执行")
                content = await _execute_multi_agent_mode(module, cache_key, request.query, conv_id)
                # 发送执行完成事件
                success_event = _create_success_event(content, conv_id)
                yield f"data: {json.dumps(success_event, ensure_ascii=False)}\n\n"
            elif hasattr(module, "create_agent"):
                logger.info(f"[执行 Agent] 步骤6: 检测到 ReAct Agent 模式，开始执行")
                content = await _execute_agent_mode(module, cache_key, request.query, conv_id)
                # 发送执行完成事件
                success_event = _create_success_event(content, conv_id)
                yield f"data: {json.dumps(success_event, ensure_ascii=False)}\n\n"
            elif hasattr(module, "build_workflow_agent"):
                logger.info(f"[执行 Agent] 步骤6: 检测到 Workflow 模式，开始执行（流式）")
                # Workflow 模式使用流式执行，支持人机交互
                execution_id = f"exec_{int(time.time())}_{hash(workflow_dir_str) % 1000000}"
                async for event_str in _execute_workflow_mode_stream(module, request.query, conv_id, workflow_dir_str, execution_id):
                    yield event_str
            else:
                error_msg = "无法识别 Agent 模式：main.py 中必须包含 create_agent()、init_group() 或 build_workflow_agent() 函数"
                logger.error(f"[执行 Agent] 步骤6: {error_msg}")
                error_event = _create_error_event(error_msg, error_msg)
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
                return
        
        except FileNotFoundError as e:
            logger.error(f"[执行 Agent] FileNotFoundError: {e}", exc_info=True)
            error_event = _create_error_event(str(e), str(e))
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
        except ImportError as e:
            logger.error(f"[执行 Agent] ImportError: {e}", exc_info=True)
            logger.error(f"[执行 Agent] 导入错误详情 - 错误类型: {type(e).__name__}, 消息: {str(e)}")
            # 打印 sys.path 信息
            import sys
            logger.error(f"[执行 Agent] 当前 sys.path: {sys.path[:5]}...")  # 只打印前5个
            error_event = _create_error_event(f"导入错误: {str(e)}", str(e))
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"[执行 Agent] 执行失败: {e}", exc_info=True)
            logger.error(f"[执行 Agent] 异常类型: {type(e).__name__}, 异常消息: {str(e)}")
            error_event = _create_error_event(f"执行 Agent 失败: {str(e)}", str(e))
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/agent/continue")
async def continue_execution(request: ContinueExecutionRequest):
    """
    继续执行工作流（用于人机交互后的继续执行）
    
    Args:
        request: 继续执行请求（包含 execution_id, reply_value, component_id）
    
    Returns:
        SSE 事件流
    """
    async def event_generator():
        """生成 SSE 事件"""
        try:
            logger.info(f"[继续执行] execution_id: {request.execution_id}, component_id: {request.component_id}")
            
            # 从缓存中获取执行状态
            if request.execution_id not in _workflow_execution_cache:
                error_msg = f"执行状态不存在或已过期: {request.execution_id}"
                logger.error(error_msg)
                error_event = _create_error_event(error_msg, error_msg)
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
                return
            
            execution_state = _workflow_execution_cache[request.execution_id]
            workflow_agent = execution_state['workflow_agent']
            conv_id = execution_state['conv_id']
            workflow_dir_str = execution_state['workflow_dir_str']
            
            # 创建交互输入
            from openjiuwen.core.runtime.interaction.interactive_input import InteractiveInput
            interactive_input = InteractiveInput()
            interactive_input.update(request.component_id, request.reply_value)
            
            logger.info(f"[继续执行] 使用用户回复继续执行: {request.reply_value[:50]}...")
            
            # 继续执行工作流
            response = await workflow_agent.invoke({"conversation_id": conv_id, "query": interactive_input})
            
            # 处理后续的交互或完成
            from typing import List
            from openjiuwen.core.stream.base import OutputSchema
            
            while isinstance(response, List):
                interactive_input = InteractiveInput()
                has_interaction = False
                
                for item in response:
                    if isinstance(item, OutputSchema) and item.type == '__interaction__':
                        component_id = item.payload.id
                        question = item.payload.value
                        has_interaction = True
                        
                        # 更新执行状态缓存
                        _workflow_execution_cache[request.execution_id] = {
                            'workflow_agent': workflow_agent,
                            'response': response,
                            'conv_id': conv_id,
                            'workflow_dir_str': workflow_dir_str,
                            'component_id': component_id,
                        }
                        
                        # 发送交互请求事件
                        interaction_event = {
                            "type": "interaction_required",
                            "execution_id": request.execution_id,
                            "component_id": component_id,
                            "question": str(question),
                            "conversation_id": conv_id,
                            "timestamp": time.time()
                        }
                        logger.info(f"[继续执行] 发送新的交互请求: question={question[:50]}...")
                        yield f"data: {json.dumps(interaction_event, ensure_ascii=False)}\n\n"
                        return  # 暂停执行，等待前端回复
                
                # 如果没有交互请求，说明 response 是 List 但不是交互类型，跳出循环
                break
            
            # 执行完成
            logger.info(f"[继续执行] 工作流执行完成，conversation_id: {conv_id}")
            content = _extract_content_from_result(response)
            success_event = _create_success_event(content, conv_id)
            yield f"data: {json.dumps(success_event, ensure_ascii=False)}\n\n"
            
            # 清理执行状态缓存
            if request.execution_id in _workflow_execution_cache:
                del _workflow_execution_cache[request.execution_id]
        
        except Exception as e:
            logger.error(f"[继续执行] 执行失败: {e}", exc_info=True)
            error_event = _create_error_event(f"继续执行失败: {str(e)}", str(e))
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
            # 清理执行状态缓存
            if request.execution_id in _workflow_execution_cache:
                del _workflow_execution_cache[request.execution_id]
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/agent/modify")
async def modify_agent(request: ModifyRequest):
    """
    修改 Agent（SSE 流式响应，适用于所有模式）
    
    Args:
        request: 修改请求（包含 workflow_dir, modification_request, conversation_id）
    
    Returns:
        SSE 事件流
    """
    async def event_generator():
        """生成 SSE 事件流"""
        try:
            service = get_service()
            
            async for event_str in service.modify(
                workflow_dir=request.workflow_dir,
                modification_request=request.modification_request,
                conversation_id=request.conversation_id,
                max_iterations=request.max_iterations
            ):
                yield event_str
                
        except Exception as e:
            logger.error(f"修改过程发生错误: {e}", exc_info=True)
            error_event = {
                "type": "error",
                "message": str(e),
                "error": str(e),
                "timestamp": time.time()
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/agent/modes")
async def list_modes():
    """列出支持的生成模式"""
    return {
        "modes": [
            {
                "name": "react",
                "description": "ReAct Agent 模式 - 通过思考-行动-观察循环完成任务",
                "files": ["config.py", "local_agent.py", "main.py"]
            },
            {
                "name": "workflow",
                "description": "Workflow 模式 - 预定义的多步骤任务流程",
                "files": ["config.py", "components.py", "workflow_builder.py", "main.py"]
            },
            {
                "name": "multi_agent",
                "description": "Multi-Agent 模式 - 多个 Agent 协作完成任务",
                "files": ["config.py", "leader_agent.py", "worker_agent.py", "main.py"]
            }
        ]
    }


def _delete_sandbox_directory(workflow_path: Path, conversation_id: str) -> bool:
    """删除持久化的沙箱目录"""
    sandbox_dir = workflow_path / ".sandbox" / conversation_id
    if not sandbox_dir.exists():
        return False
    
    try:
        shutil.rmtree(sandbox_dir)
        logger.info(f"删除持久化沙箱目录: {sandbox_dir}")
        return True
    except Exception as e:
        logger.error(f"删除沙箱目录失败 {sandbox_dir}: {e}")
        raise HTTPException(status_code=500, detail=f"清除历史失败: {str(e)}")


def _clear_agent_cache(cache_key: str, conversation_id: str) -> bool:
    """清除 Agent 模式的缓存"""
    if cache_key not in _agent_cache:
        return False
    
    try:
        agent = _agent_cache[cache_key]
        if not hasattr(agent, 'context_engine'):
            logger.debug(f"Agent 实例没有 context_engine 属性，跳过清除")
            return False
        
        agent.context_engine.clear_context(conversation_id)
        logger.info(f"清除 Agent 内存中的对话历史: {conversation_id}")
        return True
    except Exception as e:
        logger.warning(f"清除 Agent 对话历史失败: {e}")
        return False


def _clear_group_cache(cache_key: str) -> bool:
    """清除 Multi-Agent 模式的缓存"""
    if cache_key not in _group_cache:
        return False
    
    try:
        del _group_cache[cache_key]
        logger.info(f"清除 Multi-Agent Group 缓存: {cache_key}")
        return True
    except Exception as e:
        logger.warning(f"清除 Multi-Agent Group 缓存失败: {e}")
        return False


@router.post("/agent/clear-history")
async def clear_conversation_history(request: ClearHistoryRequest):
    """
    清除指定会话的对话历史
    
    Args:
        request: 包含 workflow_dir 和 conversation_id 的请求
        
    Returns:
        清除结果
    """
    try:
        # 验证并标准化 Agent 目录路径
        workflow_path = _normalize_workflow_path(request.workflow_dir)
        if not workflow_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Agent 目录不存在: {request.workflow_dir}（完整路径: {workflow_path}）"
            )
        
        cache_key = str(workflow_path)
        
        # 清除沙箱目录
        deleted_sandbox = _delete_sandbox_directory(workflow_path, request.conversation_id)
        
        # 清除缓存
        deleted_agent_cache = _clear_agent_cache(cache_key, request.conversation_id)
        deleted_group_cache = _clear_group_cache(cache_key)
        deleted_cache = deleted_agent_cache or deleted_group_cache
        
        if not deleted_cache:
            logger.debug(f"未找到缓存的实例: {cache_key}")
        
        # 生成响应消息
        if deleted_sandbox or deleted_cache:
            response_message = f"成功清除会话 {request.conversation_id} 的历史记录"
            logger.info(response_message)
        else:
            response_message = f"会话 {request.conversation_id} 无需清除（无历史记录或已清除）"
            logger.info(response_message)
        
        return {
            "success": True,
            "message": response_message,
            "deleted_sandbox": deleted_sandbox,
            "deleted_cache": deleted_cache
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清除历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
