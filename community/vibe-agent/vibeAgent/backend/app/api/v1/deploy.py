"""
工作流一键部署接口

提供工作流服务代码生成和自动部署功能
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger
from dotenv import load_dotenv

router = APIRouter(tags=["deploy"])


class DeployRequest(BaseModel):
    """部署请求"""
    workflow_dir: str = Field(description="工作流目录路径")


class DeployResponse(BaseModel):
    """部署响应"""
    success: bool
    message: str
    service_path: Optional[str] = None
    service_url: Optional[str] = None
    port: Optional[int] = None
    usage_info: Optional[str] = None
    api_key_note: Optional[str] = None
    quick_start: Optional[str] = None


def _normalize_workflow_path(workflow_dir: str) -> Path:
    """标准化工作流路径"""
    workflow_path = Path(workflow_dir)
    if not workflow_path.is_absolute():
        # 从 backend/app/api/v1/deploy.py 向上5层到项目根目录
        project_root = Path(__file__).parent.parent.parent.parent.parent
        workflow_path = project_root / workflow_dir
        logger.debug(f"路径转换: {workflow_dir} -> {workflow_path} (项目根: {project_root})")
    return workflow_path


def _get_api_key_from_env() -> str:
    """从 .env 文件读取 API_KEY"""
    # 获取 backend 目录路径（从 deploy.py 向上4层）
    backend_dir = Path(__file__).parent.parent.parent.parent
    env_path = backend_dir / ".env"
    
    # 如果 .env 文件存在，加载它
    if env_path.exists():
        load_dotenv(env_path)
        logger.debug(f"从 .env 文件加载环境变量: {env_path}")
    
    # 从环境变量读取 API_KEY
    api_key = os.getenv("API_KEY", "")
    if not api_key:
        logger.warning("未在 .env 文件中找到 API_KEY，服务可能无法正常工作")
    else:
        logger.info("已从 .env 文件读取 API_KEY")
    
    return api_key


def _generate_service_code(workflow_path: Path, api_key: str) -> str:
    """生成服务代码"""
    # 读取工作流配置，获取工作流名称和描述
    workflow_name = "工作流服务"
    workflow_description = "工作流服务"
    
    config_file = workflow_path / "config.py"
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # 尝试提取工作流名称
                if 'WORKFLOW_NAME' in content:
                    for line in content.split('\n'):
                        if 'WORKFLOW_NAME' in line and '=' in line:
                            try:
                                workflow_name = line.split('=')[1].strip().strip('"').strip("'")
                                break
                            except:
                                pass
                # 尝试提取工作流描述
                if 'WORKFLOW_DESCRIPTION' in content:
                    for line in content.split('\n'):
                        if 'WORKFLOW_DESCRIPTION' in line and '=' in line:
                            try:
                                workflow_description = line.split('=')[1].strip().strip('"').strip("'")
                                break
                            except:
                                pass
        except Exception as e:
            logger.warning(f"读取配置文件失败: {e}")
    
    # 生成服务代码模板
    service_code = f'''"""
{workflow_name}服务

提供 HTTP API 接口，可以通过 Postman 或其他工具调用
"""
import asyncio
import os
import sys
import io
import json
import time
from typing import List, Optional, Dict, Any
from pathlib import Path

# 设置标准输出编码为 UTF-8（避免 Windows 控制台 GBK 编码错误）
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到 Python 路径
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 添加 openjiuwen 路径（如果需要）
workspace_root = project_root.parent.parent
openjiuwen_parent = workspace_root / "agent-core"
if openjiuwen_parent.exists() and str(openjiuwen_parent) not in sys.path:
    sys.path.insert(0, str(openjiuwen_parent))

# SSL 验证配置
if "LLM_SSL_VERIFY" not in os.environ:
    os.environ["LLM_SSL_VERIFY"] = "False"
if "RESTFUL_SSL_VERIFY" not in os.environ:
    os.environ["RESTFUL_SSL_VERIFY"] = "False"
if "SSRF_PROTECT_ENABLED" not in os.environ:
    os.environ["SSRF_PROTECT_ENABLED"] = "False"

# 设置工作流执行超时时间
os.environ["WORKFLOW_EXECUTE_TIMEOUT"] = "300"

# 设置 API Key（从环境变量读取，如果未设置则使用传入的值）
# 注意：这里设置的是默认值，实际运行时应该通过环境变量传递
os.environ.setdefault("API_KEY", "{api_key}")

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from loguru import logger

# 导入工作流相关模块
from config import create_llm_client
from workflow_builder import build_workflow_agent
from openjiuwen.core.runtime.interaction.interactive_input import InteractiveInput
from openjiuwen.core.stream.base import OutputSchema

# 配置日志
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{{time:YYYY-MM-DD HH:mm:ss}}</green> | <level>{{level: <8}}</level> | <cyan>{{name}}</cyan>:<cyan>{{function}}</cyan>:<cyan>{{line}}</cyan> - <level>{{message}}</level>",
    level="INFO",
)

# 创建 FastAPI 应用
app = FastAPI(
    title="{workflow_name}服务",
    version="1.0.0",
    description="{workflow_description}"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局 Agent 实例缓存（用于多轮对话）
_agent_cache: Dict[str, Any] = {{}}

# 工作流执行状态缓存（用于人机交互）
_execution_cache: Dict[str, Dict[str, Any]] = {{}}

# LLM 客户端（用于自动处理人机交互）
llm_client = create_llm_client()


# ========== 请求/响应模型 ==========

class ChatRequest(BaseModel):
    """聊天请求（支持初始请求和继续执行两种模式）"""
    # 初始请求参数
    query: Optional[str] = Field(default=None, description="用户查询/消息（初始请求时必填）")
    conversation_id: Optional[str] = Field(default=None, description="会话 ID（用于多轮对话）")
    auto_reply: bool = Field(default=True, description="是否自动回复人机交互问题（True：自动回复，False：返回交互请求）")
    
    # 继续执行参数
    execution_id: Optional[str] = Field(default=None, description="执行 ID（继续执行时必填）")
    reply_value: Optional[str] = Field(default=None, description="用户回复内容（继续执行时必填）")
    component_id: Optional[str] = Field(default=None, description="组件 ID（继续执行时必填）")


class ChatResponse(BaseModel):
    """聊天响应"""
    success: bool
    content: str
    conversation_id: str
    execution_id: Optional[str] = None
    interaction_required: bool = False
    question: Optional[str] = None
    component_id: Optional[str] = None


# ========== 辅助函数 ==========

def _extract_content_from_result(result: Any) -> str:
    """从工作流执行结果中提取内容"""
    if hasattr(result, "result") and hasattr(result, "state"):
        workflow_result = result.result
        if isinstance(workflow_result, dict):
            content = (
                workflow_result.get("responseContent", "") or
                workflow_result.get("output", "") or
                workflow_result.get("content", "") or
                workflow_result.get("answer", "")
            )
            if content:
                return str(content)
            try:
                return json.dumps(workflow_result, ensure_ascii=False, default=str)
            except Exception:
                return str(workflow_result)
        elif isinstance(workflow_result, (list, tuple)):
            content_parts = []
            for item in workflow_result:
                if hasattr(item, "payload"):
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
    
    if isinstance(result, dict):
        content = (
            result.get("responseContent", "") or
            result.get("output", "") or
            result.get("content", "") or
            result.get("answer", "")
        )
        if content:
            return str(content)
        try:
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception:
            return str(result)
    
    return str(result)


def _get_or_create_agent(conversation_id: str):
    """获取或创建工作流 Agent 实例"""
    if conversation_id not in _agent_cache:
        logger.info(f"创建新的工作流 Agent 实例，conversation_id: {{conversation_id}}")
        _agent_cache[conversation_id] = build_workflow_agent()
    else:
        logger.info(f"复用已缓存的工作流 Agent 实例，conversation_id: {{conversation_id}}")
    return _agent_cache[conversation_id]


async def _execute_workflow(request: ChatRequest) -> ChatResponse:
    """
    统一的工作流执行函数（支持初始请求和继续执行两种模式）
    
    Args:
        request: 聊天请求
        
    Returns:
        聊天响应
    """
    # 判断请求类型：继续执行模式
    is_continue_mode = request.execution_id is not None
    
    if is_continue_mode:
        # 继续执行模式：验证必需参数
        if not request.reply_value or not request.component_id:
            raise HTTPException(
                status_code=400,
                detail="继续执行模式需要提供 execution_id、reply_value 和 component_id"
            )
        
        # 从缓存中获取执行状态
        if request.execution_id not in _execution_cache:
            raise HTTPException(
                status_code=404,
                detail=f"执行状态不存在或已过期: {{request.execution_id}}"
            )
        
        execution_state = _execution_cache[request.execution_id]
        workflow_agent = execution_state['workflow_agent']
        conv_id = execution_state['conversation_id']
        
        # 创建交互输入
        interactive_input = InteractiveInput()
        interactive_input.update(request.component_id, request.reply_value)
        
        logger.info(f"继续执行工作流，execution_id: {{request.execution_id}}, reply: {{request.reply_value[:50]}}...")
        
        # 继续执行工作流
        response = await workflow_agent.invoke({{"conversation_id": conv_id, "query": interactive_input}})
        current_execution_id = request.execution_id
        
    else:
        # 初始请求模式：验证必需参数
        if not request.query:
            raise HTTPException(
                status_code=400,
                detail="初始请求模式需要提供 query 参数"
            )
        
        # 生成会话ID（如果未提供）
        conv_id = request.conversation_id or f"workflow_{{int(time.time())}}"
        logger.info(f"收到初始聊天请求，query: {{request.query[:50]}}..., conversation_id: {{conv_id}}")
        
        # 获取或创建 Agent 实例
        workflow_agent = _get_or_create_agent(conv_id)
        
        # 执行工作流
        response = await workflow_agent.invoke({{"query": request.query, "conversation_id": conv_id}})
        current_execution_id = None
    
    # 处理人机交互流程（统一逻辑）
    while isinstance(response, List):
        interactive_input = InteractiveInput()
        has_interaction = False
        
        for item in response:
            if isinstance(item, OutputSchema) and item.type == '__interaction__':
                component_id = item.payload.id
                question = item.payload.value
                has_interaction = True
                
                # 如果需要自动回复
                if request.auto_reply:
                    logger.info(f"自动回复交互问题: {{question[:50]}}...")
                    # 使用 LLM 自动生成回复
                    reply_value = await llm_client.ainvoke(
                        model_name="qwen3-max",
                        messages=[{{
                            "role": "user",
                            "content": f"""##人设：你是工作流用户，正在试运行工作流，需要回答工作流执行过程中的人机交互问题。 ## 要求：1.直接代替用户做所有决策 2. 直接回答问题，禁止输出任何其他内容 3. 回答简洁明了 4. 禁止回复"无"、"不知道"、"不确定"等模糊不清的词语 \\n系统问题是：{{question}}"""
                        }}]
                    )
                    interactive_input.update(component_id, reply_value.content)
                else:
                    # 不需要自动回复，返回交互请求
                    if current_execution_id is None:
                        current_execution_id = f"exec_{{int(time.time())}}_{{hash(conv_id) % 1000000}}"
                    
                    _execution_cache[current_execution_id] = {{
                        'workflow_agent': workflow_agent,
                        'response': response,
                        'conversation_id': conv_id,
                        'component_id': component_id,
                    }}
                    return ChatResponse(
                        success=False,
                        content="",
                        conversation_id=conv_id,
                        execution_id=current_execution_id,
                        interaction_required=True,
                        question=str(question),
                        component_id=component_id
                    )
        
        if has_interaction and request.auto_reply:
            # 继续执行工作流
            response = await workflow_agent.invoke({{"conversation_id": conv_id, "query": interactive_input}})
        else:
            # 没有交互或不需要自动回复，跳出循环
            break
    
    # 提取结果内容
    content = _extract_content_from_result(response)
    logger.info(f"工作流执行完成，conversation_id: {{conv_id}}")
    
    # 清理执行状态缓存（如果是继续执行模式且执行完成）
    if is_continue_mode and current_execution_id and current_execution_id in _execution_cache:
        del _execution_cache[current_execution_id]
    
    return ChatResponse(
        success=True,
        content=content,
        conversation_id=conv_id,
        execution_id=None,
        interaction_required=False,
        question=None,
        component_id=None
    )


# ========== API 端点 ==========

@app.get("/")
async def root():
    """根路径"""
    return {{
        "name": "{workflow_name}服务",
        "version": "1.0.0",
        "description": "{workflow_description}",
        "docs": "/docs",
        "endpoints": {{
            "chat": "/chat - POST - 聊天接口（支持初始请求和继续执行）",
            "stream": "/chat/stream - POST - 流式聊天接口（SSE）"
        }}
    }}


@app.get("/health")
async def health():
    """健康检查"""
    return {{"status": "healthy", "service": "{workflow_name}服务"}}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    {workflow_name}聊天接口（支持初始请求和继续执行）
    
    使用方式：
    1. 初始请求：提供 query 参数
    2. 继续执行：提供 execution_id、reply_value 和 component_id 参数
    
    Args:
        request: 聊天请求
        
    Returns:
        聊天响应（如果 auto_reply=False 且需要交互，会返回 interaction_required）
    """
    try:
        return await _execute_workflow(request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"执行工作流失败: {{e}}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"执行工作流失败: {{str(e)}}")


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    {workflow_name}聊天接口（流式响应，SSE）
    
    返回 Server-Sent Events 流，支持实时返回执行状态。
    
    Args:
        request: 聊天请求
        
    Returns:
        SSE 事件流
    """
    async def event_generator():
        """生成 SSE 事件"""
        try:
            conv_id = request.conversation_id or f"workflow_{{int(time.time())}}"
            logger.info(f"收到流式聊天请求，query: {{request.query[:50]}}..., conversation_id: {{conv_id}}")
            
            # 获取或创建 Agent 实例
            workflow_agent = _get_or_create_agent(conv_id)
            
            # 执行工作流
            response = await workflow_agent.invoke({{"query": request.query, "conversation_id": conv_id}})
            
            # 处理人机交互流程
            while isinstance(response, List):
                interactive_input = InteractiveInput()
                has_interaction = False
                
                for item in response:
                    if isinstance(item, OutputSchema) and item.type == '__interaction__':
                        component_id = item.payload.id
                        question = item.payload.value
                        has_interaction = True
                        
                        if request.auto_reply:
                            # 自动回复
                            logger.info(f"自动回复交互问题: {{question[:50]}}...")
                            reply_value = await llm_client.ainvoke(
                                model_name="qwen3-max",
                                messages=[{{
                                    "role": "user",
                                    "content": f"""##人设：你是工作流用户，正在试运行工作流，需要回答工作流执行过程中的人机交互问题。 ## 要求：1.直接代替用户做所有决策 2. 直接回答问题，禁止输出任何其他内容 3. 回答简洁明了 4. 禁止回复"无"、"不知道"、"不确定"等模糊不清的词语 \\n系统问题是：{{question}}"""
                                }}]
                            )
                            interactive_input.update(component_id, reply_value.content)
                        else:
                            # 发送交互请求事件
                            execution_id = f"exec_{{int(time.time())}}_{{hash(conv_id) % 1000000}}"
                            _execution_cache[execution_id] = {{
                                'workflow_agent': workflow_agent,
                                'response': response,
                                'conversation_id': conv_id,
                                'component_id': component_id,
                            }}
                            interaction_event = {{
                                "type": "interaction_required",
                                "execution_id": execution_id,
                                "component_id": component_id,
                                "question": str(question),
                                "conversation_id": conv_id,
                                "timestamp": time.time()
                            }}
                            yield f"data: {{json.dumps(interaction_event, ensure_ascii=False)}}\\n\\n"
                            return
                
                if has_interaction and request.auto_reply:
                    response = await workflow_agent.invoke({{"conversation_id": conv_id, "query": interactive_input}})
                else:
                    break
            
            # 执行完成
            content = _extract_content_from_result(response)
            logger.info(f"工作流执行完成，conversation_id: {{conv_id}}")
            
            success_event = {{
                "type": "execution_completed",
                "success": True,
                "content": content,
                "conversation_id": conv_id,
                "timestamp": time.time()
            }}
            yield f"data: {{json.dumps(success_event, ensure_ascii=False)}}\\n\\n"
            
        except Exception as e:
            logger.error(f"流式执行失败: {{e}}", exc_info=True)
            error_event = {{
                "type": "error",
                "message": str(e),
                "error": str(e),
                "timestamp": time.time()
            }}
            yield f"data: {{json.dumps(error_event, ensure_ascii=False)}}\\n\\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={{
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }}
    )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8001"))
    
    logger.info("=" * 60)
    logger.info("{workflow_name}服务启动中...")
    logger.info(f"服务地址: http://0.0.0.0:{{port}}")
    logger.info(f"API 文档: http://0.0.0.0:{{port}}/docs")
    logger.info("=" * 60)
    
    uvicorn.run(
        "service:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )
'''
    return service_code


def _start_service(workflow_path: Path, port: int = 8001, api_key: str = None) -> subprocess.Popen:
    """启动服务（后台运行）"""
    service_file = workflow_path / "service.py"
    if not service_file.exists():
        raise FileNotFoundError(f"服务文件不存在: {service_file}")
    
    # 设置环境变量
    env = os.environ.copy()
    env["PORT"] = str(port)
    if api_key:
        env["API_KEY"] = api_key
    
    # 启动服务
    if sys.platform == "win32":
        # Windows 使用 start 命令后台运行
        process = subprocess.Popen(
            [sys.executable, str(service_file)],
            cwd=str(workflow_path),
            env=env,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    else:
        # Linux/Mac 使用 nohup 后台运行
        process = subprocess.Popen(
            [sys.executable, str(service_file)],
            cwd=str(workflow_path),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    
    return process


@router.post("/workflow/deploy", response_model=DeployResponse)
async def deploy_workflow(request: DeployRequest):
    """
    一键部署工作流服务
    
    在工作流目录生成服务代码并自动运行服务。
    
    Args:
        request: 部署请求（包含 workflow_dir，API_KEY 将从 .env 文件读取）
        
    Returns:
        部署结果（包含服务地址和使用方法）
    """
    try:
        logger.info(f"开始部署工作流，目录: {request.workflow_dir}")
        
        # 1. 标准化工作流路径
        workflow_path = _normalize_workflow_path(request.workflow_dir)
        if not workflow_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"工作流目录不存在: {request.workflow_dir}（完整路径: {workflow_path}）"
            )
        
        # 2. 检查是否已有 service.py（如果存在，先备份）
        service_file = workflow_path / "service.py"
        if service_file.exists():
            backup_file = workflow_path / "service.py.backup"
            shutil.copy2(service_file, backup_file)
            logger.info(f"已备份现有服务文件: {backup_file}")
        
        # 3. 从 .env 文件读取 API_KEY
        api_key = _get_api_key_from_env()
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail="未在 .env 文件中找到 API_KEY，请先配置 API_KEY"
            )
        
        # 4. 读取工作流配置，获取工作流名称和描述
        workflow_name = "工作流服务"
        workflow_description = "工作流服务"
        config_file = workflow_path / "config.py"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 尝试提取工作流名称
                    if 'WORKFLOW_NAME' in content:
                        for line in content.split('\n'):
                            if 'WORKFLOW_NAME' in line and '=' in line:
                                try:
                                    workflow_name = line.split('=')[1].strip().strip('"').strip("'")
                                    break
                                except:
                                    pass
                    # 尝试提取工作流描述
                    if 'WORKFLOW_DESCRIPTION' in content:
                        for line in content.split('\n'):
                            if 'WORKFLOW_DESCRIPTION' in line and '=' in line:
                                try:
                                    workflow_description = line.split('=')[1].strip().strip('"').strip("'")
                                    break
                                except:
                                    pass
            except Exception as e:
                logger.warning(f"读取配置文件失败: {e}")
        
        # 5. 生成服务代码
        logger.info("生成服务代码...")
        service_code = _generate_service_code(workflow_path, api_key)
        
        # 6. 写入服务文件
        service_file.write_text(service_code, encoding='utf-8')
        logger.info(f"服务代码已生成: {service_file}")
        
        # 7. 生成唯一端口（基于工作流目录路径的哈希值）
        import hashlib
        workflow_dir_hash = hashlib.md5(str(workflow_path).encode('utf-8')).hexdigest()
        # 将哈希值转换为端口号：8001-8999 范围（避免与常用端口冲突）
        port = 8001 + (int(workflow_dir_hash[:4], 16) % 998)
        logger.info(f"生成唯一端口: {port} (基于工作流目录: {workflow_path.name})")
        
        # 检查端口是否已被占用（简单检查，不保证100%准确）
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                if s.connect_ex(('localhost', port)) == 0:
                    # 端口已被占用，尝试下一个端口
                    port = port + 1 if port < 8999 else 8001
                    logger.warning(f"端口 {port-1} 已被占用，使用端口: {port}")
        except Exception:
            pass  # 忽略检查错误，直接使用生成的端口
        
        # 8. 启动服务（后台运行）
        logger.info(f"启动服务，端口: {port}")
        try:
            process = _start_service(workflow_path, port, api_key)
            logger.info(f"服务已启动，进程ID: {process.pid}")
        except Exception as e:
            logger.warning(f"自动启动服务失败: {e}，用户需要手动启动")
            process = None
        
        # 9. 生成使用方法
        service_url = f"http://localhost:{port}"
        
        # 注意信息（单独返回给前端）
        api_key_note = "已使用环境变量（.env文件）设置的 API_KEY 作为大模型相关组件的API Key。"
        
        # 快速开始信息（单独返回给前端）
        quick_start = f"""### 快速调用 Chat 服务

最简单的调用方式，使用 curl 命令：

```bash
curl -X POST {service_url}/chat \\
  -H "Content-Type: application/json" \\
  -d '{{"query": "你好", "conversation_id": "user_123"}}'
```

或使用 Python：

```python
import requests

response = requests.post(
    "{service_url}/chat",
    json={{
        "query": "你好",
        "conversation_id": "user_123"
    }}
)
print(response.json())
```

**响应示例**:
```json
{{
  "success": true,
  "content": "工作流执行结果",
  "conversation_id": "user_123"
}}
```"""
        
        # 使用说明（不包含快速开始，快速开始会单独显示）
        usage_info = f"""## 服务信息
- **服务地址**: {service_url}
- **API 文档**: {service_url}/docs

## 具体使用说明

### 1. GET / - 获取服务信息

获取服务的基本信息和可用端点列表。

**请求示例**:
```bash
curl {service_url}/
```

**响应示例**:
```json
{{
  "name": "{workflow_name}服务",
  "version": "1.0.0",
  "description": "{workflow_description}",
  "docs": "/docs",
  "endpoints": {{
    "chat": "/chat - POST - 聊天接口（支持初始请求和继续执行）",
    "stream": "/chat/stream - POST - 流式聊天接口（SSE）"
  }}
}}
```

### 2. GET /health - 健康检查

检查服务运行状态。

**请求示例**:
```bash
curl {service_url}/health
```

**响应示例**:
```json
{{
  "status": "healthy",
  "service": "{workflow_name}服务"
}}
```

### 3. POST /chat - 同步聊天接口

发送聊天消息并获取响应（同步方式）。支持初始请求和继续执行两种模式。

**初始请求参数**:
- `query` (string, 必需): 用户查询/消息
- `conversation_id` (string, 可选): 会话 ID（用于多轮对话）
- `auto_reply` (boolean, 可选, 默认: true): 是否自动回复人机交互问题

**继续执行参数**（当需要人机交互时）:
- `execution_id` (string, 必需): 执行 ID（从初始请求响应中获取）
- `reply_value` (string, 必需): 用户回复内容
- `component_id` (string, 必需): 组件 ID（从初始请求响应中获取）

**请求示例 (Postman)**:
- **方法**: `POST`
- **URL**: `{service_url}/chat`
- **Headers**: `Content-Type: application/json`
- **Body**:
```json
{{
  "query": "你好",
  "conversation_id": "user_123",
  "auto_reply": true
}}
```

**请求示例 (curl)**:
```bash
curl -X POST {service_url}/chat \\
  -H "Content-Type: application/json" \\
  -d '{{"query": "你好", "conversation_id": "user_123", "auto_reply": true}}'
```

**请求示例 (Python)**:
```python
import requests

response = requests.post(
    "{service_url}/chat",
    json={{
        "query": "你好",
        "conversation_id": "user_123",
        "auto_reply": True
    }}
)
print(response.json())
```

**响应格式**:
```json
{{
  "success": true,
  "content": "工作流执行结果",
  "conversation_id": "user_123",
  "execution_id": null,
  "interaction_required": false,
  "question": null,
  "component_id": null
}}
```

**当需要人机交互时** (`auto_reply=false`):
```json
{{
  "success": false,
  "content": "",
  "conversation_id": "user_123",
  "execution_id": "exec_1234567890_123456",
  "interaction_required": true,
  "question": "请输入您的姓名",
  "component_id": "component_123"
}}
```

### 4. POST /chat/stream - 流式聊天接口（SSE）

发送聊天消息并获取流式响应（Server-Sent Events）。

**请求参数**:
- `query` (string, 必需): 用户查询/消息
- `conversation_id` (string, 可选): 会话 ID（用于多轮对话）
- `auto_reply` (boolean, 可选, 默认: true): 是否自动回复人机交互问题

**请求示例 (curl)**:
```bash
curl -X POST {service_url}/chat/stream \\
  -H "Content-Type: application/json" \\
  -H "Accept: text/event-stream" \\
  -d '{{"query": "你好", "conversation_id": "user_123", "auto_reply": true}}'
```

**请求示例 (Python)**:
```python
import requests
import json

response = requests.post(
    "{service_url}/chat/stream",
    json={{
        "query": "你好",
        "conversation_id": "user_123",
        "auto_reply": True
    }},
    headers={{"Accept": "text/event-stream"}},
    stream=True
)

for line in response.iter_lines():
    if line:
        line_str = line.decode('utf-8')
        if line_str.startswith('data: '):
            data = json.loads(line_str[6:])
            print(data)
```

**响应事件类型**:

1. **执行完成事件**:
```json
{{
  "type": "execution_completed",
  "success": true,
  "content": "工作流执行结果",
  "conversation_id": "user_123",
  "timestamp": 1234567890.123
}}
```

2. **需要交互事件** (`auto_reply=false`):
```json
{{
  "type": "interaction_required",
  "execution_id": "exec_1234567890_123456",
  "component_id": "component_123",
  "question": "请输入您的姓名",
  "conversation_id": "user_123",
  "timestamp": 1234567890.123
}}
```

3. **错误事件**:
```json
{{
  "type": "error",
  "message": "错误信息",
  "error": "错误详情",
  "timestamp": 1234567890.123
}}
```

### 5. POST /chat - 继续执行（人机交互）

当工作流需要人机交互时，使用 `/chat` 接口提交用户回复并继续执行（使用继续执行模式）。

**请求参数**:
- `execution_id` (string, 必需): 执行 ID（从初始请求响应中获取）
- `reply_value` (string, 必需): 用户回复内容
- `component_id` (string, 必需): 组件 ID（从初始请求响应中获取）

**请求示例 (Postman)**:
- **方法**: `POST`
- **URL**: `{service_url}/chat`
- **Headers**: `Content-Type: application/json`
- **Body**:
```json
{{
  "execution_id": "exec_1234567890_123456",
  "reply_value": "张三",
  "component_id": "component_123"
}}
```

**请求示例 (curl)**:
```bash
curl -X POST {service_url}/chat \\
  -H "Content-Type: application/json" \\
  -d '{{"execution_id": "exec_1234567890_123456", "reply_value": "张三", "component_id": "component_123"}}'
```

**请求示例 (Python)**:
```python
import requests

response = requests.post(
    "{service_url}/chat",
    json={{
        "execution_id": "exec_1234567890_123456",
        "reply_value": "张三",
        "component_id": "component_123"
    }}
)
print(response.json())
```

**响应格式**:
与初始请求相同，可能返回：
- 执行完成的结果
- 新的交互请求（如果还有更多问题需要回答）

### 6. GET /docs - API 文档

访问 Swagger UI 交互式 API 文档。

**访问方式**:
在浏览器中打开: `{service_url}/docs`

## 完整使用流程示例

### 场景：需要人机交互的工作流

1. **发送初始请求**:
```bash
curl -X POST {service_url}/chat \\
  -H "Content-Type: application/json" \\
  -d '{{"query": "开始调研", "conversation_id": "user_123", "auto_reply": false}}'
```

2. **收到交互请求**:
```json
{{
  "success": false,
  "interaction_required": true,
  "execution_id": "exec_1234567890_123456",
  "question": "请输入您的姓名",
  "component_id": "component_123"
}}
```

3. **提交用户回复**（使用 /chat 接口的继续执行模式）:
```bash
curl -X POST {service_url}/chat \\
  -H "Content-Type: application/json" \\
  -d '{{"execution_id": "exec_1234567890_123456", "reply_value": "张三", "component_id": "component_123"}}'
```

4. **继续执行直到完成**:
如果还有更多交互，重复步骤 2-3，直到返回 `success: true`。

## 注意事项

1. 服务已在后台运行，进程ID: {process.pid if process else '未启动'}
2. API Key 已设置到环境变量中，可通过 `os.getenv("API_KEY")` 获取
3. 如需停止服务，请查找并终止进程
4. 如需修改端口，请设置环境变量 `PORT` 后重启服务
5. `conversation_id` 用于多轮对话，相同 ID 会复用同一个 Agent 实例
6. `auto_reply=true` 时，系统会自动使用 LLM 回复交互问题；`auto_reply=false` 时，需要手动调用 `/chat` 接口（使用继续执行模式）
7. 流式接口 (`/chat/stream`) 适合需要实时显示执行进度的场景
"""
        
        # 10. 保存使用说明到工作流文件夹（合并快速开始和详细使用说明）
        usage_file = workflow_path / "USAGE.md"
        try:
            # 提取详细使用说明部分（从"## 具体使用说明"开始的所有内容）
            if '## 具体使用说明' in usage_info:
                detailed_usage = '## 具体使用说明' + usage_info.split('## 具体使用说明', 1)[1]
            else:
                detailed_usage = usage_info
            # 合并快速开始和详细使用说明
            full_usage_info = f"""## 服务信息
- **服务地址**: {service_url}
- **API 文档**: {service_url}/docs
- **服务文件**: {service_file}

## 快速开始

{quick_start}

## 具体使用说明
{detailed_usage}"""
            usage_file.write_text(full_usage_info.strip(), encoding='utf-8')
            logger.info(f"使用说明已保存到: {usage_file}")
        except Exception as e:
            logger.warning(f"保存使用说明失败: {e}")
        
        return DeployResponse(
            success=True,
            message="工作流服务部署成功！",
            service_path=str(service_file),
            service_url=service_url,
            port=port,
            usage_info=usage_info,
            api_key_note=api_key_note,
            quick_start=quick_start
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"部署工作流失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"部署失败: {str(e)}")

