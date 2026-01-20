"""
AI Agent服务模块
处理自然语言查询、意图识别、查询优化和工具调用
"""

import logging
import asyncio
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from contextvars import ContextVar
from ..config import get_settings

# 引入 OpenJiuwen Core 组件
try:
    from openjiuwen.agent.react_agent.react_agent import ReActAgent
    from openjiuwen.agent.config.react_config import ReActAgentConfig
    from openjiuwen.core.component.common.configs.model_config import ModelConfig
    from openjiuwen.core.utils.llm.base import BaseModelInfo
    from openjiuwen.core.utils.tool.tool import tool
    from openjiuwen.core.agent.agent import BaseAgent
    HAS_OPENJIUWEN = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"OpenJiuwen import failed: {e}")
    HAS_OPENJIUWEN = False
    ReActAgent = None
    tool = lambda x: x # Dummy decorator
    BaseModelInfo = None # Placeholder

logger = logging.getLogger(__name__)


class AgentService:
    """
    Agent服务类

    职责：
    1. 查询优化：将用户自然语言转换为更精确的搜索语义
    2. 意图识别：判断用户想做什么（搜索/上传/删除等）
    3. 工具调用：根据意图调用相应的后端服务
    4. 响应生成：组织自然语言回复

    核心升级：
    - 集成 OpenJiuwen ReActAgent
    - 支持 OpenAI 兼容 API
    """

    _instance: Optional["AgentService"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._initialized = getattr(self, '_initialized', False)
        self._sessions: Dict[str, Dict[str, Any]] = {}  # 会话管理
        self._agent: Optional[ReActAgent] = None  # ReActAgent实例
        self._tools: List[Any] = []    # 注册的工具列表
        self._current_conversation_id: ContextVar[Optional[str]] = ContextVar("current_conversation_id", default=None)
        self._last_images_by_conversation: Dict[str, List[Dict[str, Any]]] = {}

    def initialize(
        self,
        llm_model_path: Optional[str] = None,
        llm_api_url: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        初始化Agent服务
        """
        if self._initialized:
            logger.info("Agent服务已初始化")
            return

        settings = get_settings()
        logger.info(f"开始初始化Agent服务... (Enabled: {settings.AGENT_ENABLED})")
        
        # 配置OpenAI兼容的API接入并初始化Agent
        if settings.AGENT_ENABLED and settings.OPENAI_API_KEY:
            if not HAS_OPENJIUWEN:
                logger.error("OpenJiuwen库未安装或导入失败，无法启用Agent功能")
                return

            try:
                logger.info(f"正在配置ReAct Agent (Provider: {settings.AGENT_PROVIDER}, Model: {settings.OPENAI_MODEL_NAME})...")
                self._setup_agent(settings)
                
                # 验证连接性 (可选)
                logger.info("Agent服务初始化完成，已准备就绪")
            except Exception as e:
                logger.error(f"Agent初始化失败: {e}", exc_info=True)
                logger.warning("系统将以无Agent模式运行 (Rule-based Fallback)")
        else:
            logger.info("Agent服务初始化完成（简化模式，未配置OpenAI API）")

        self._initialized = True

    def _setup_agent(self, settings):
        """配置并初始化 ReActAgent"""
        ssl_verify = bool(settings.LLM_SSL_VERIFY)
        ssl_cert = settings.LLM_SSL_CERT
        if ssl_verify and not ssl_cert:
            logger.warning("LLM_SSL_VERIFY=true but LLM_SSL_CERT is missing; forcing LLM_SSL_VERIFY=false")
            ssl_verify = False

        os.environ["LLM_SSL_VERIFY"] = "true" if ssl_verify else "false"
        if ssl_cert:
            os.environ["LLM_SSL_CERT"] = ssl_cert
        else:
            os.environ.pop("LLM_SSL_CERT", None)

        logger.info(
            "LLM SSL config applied (LLM_SSL_VERIFY=%s, LLM_SSL_CERT=%s)",
            os.environ.get("LLM_SSL_VERIFY"),
            "set" if os.environ.get("LLM_SSL_CERT") else "unset",
        )

        # 1. 注册核心工具
        self._register_core_tools()
        
        # 2. 构建模型配置
        # 注意：BaseModelInfo 使用 api_base 而非 base_url
        model_name = (settings.OPENAI_MODEL_NAME or "").strip()
        if not model_name:
            raise ValueError("OPENAI_MODEL_NAME 为空，无法初始化Agent")

        model_info = BaseModelInfo(
            model=model_name,
            api_key=settings.OPENAI_API_KEY,
            api_base=settings.OPENAI_BASE_URL,
            streaming=False
        )
        
        # 构建 ModelConfig
        # 假设 settings.AGENT_PROVIDER 是 "openai" 或 "deepseek" 等
        model_config = ModelConfig(
            model_provider=settings.AGENT_PROVIDER,
            model_info=model_info
        )
        
        # 3. 构建Agent配置
        agent_config = ReActAgentConfig(
            id="smart_album_agent",
            version="1.0.0",
            description="Smart Album Agent powered by OpenJiuwen",
            model=model_config,
            prompt_template=[
                {"role": "system", "content": "You are a helpful smart album assistant. You can search images, check system time, and answer user questions. When user asks to search for images, use search_tool. When user asks for time, use get_current_time."}
            ]
        )
        
        # 4. 实例化 ReActAgent
        self._agent = ReActAgent(agent_config=agent_config)
        
        # 5. 绑定工具 (使用 BaseAgent 的 add_tools 方法)
        if self._tools:
            self._agent.add_tools(self._tools)

    def _register_core_tools(self):
        """注册Agent可用工具"""
        # 示例工具：获取当前时间
        
        @tool
        def get_current_time() -> str:
            """获取当前系统时间，格式为 YYYY-MM-DD HH:MM:SS"""
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        self._tools.append(get_current_time)
        
        @tool
        def search_tool(query: str, top_k: int = 5) -> str:
            """
            搜索图片工具。
            当用户想要查找、搜索、寻找图片时使用此工具。
            
            Args:
                query: 用户的搜索描述，例如 "穿红衣服的人" 或 "海边的日落"
                top_k: 返回结果的数量，默认为5
                
            Returns:
                搜索结果的JSON字符串，包含图片ID和相关性分数
            """
            from .search_service import get_search_service
            import json
            
            search_svc = get_search_service()
            if not search_svc.is_initialized:
                return "Error: Search service not initialized."
                
            try:
                results = search_svc.search_by_text(query_text=query, top_k=top_k)

                conversation_id = self._current_conversation_id.get() or "default_session"
                self._last_images_by_conversation[conversation_id] = results
                
                # 简化返回结果，只保留关键信息以节省Token
                simplified_results = []
                for res in results:
                    simplified_results.append({
                        "id": res.get("id"),
                        "score": res.get("score"),
                        "created_at": res.get("metadata", {}).get("created_at"),
                        "tags": res.get("metadata", {}).get("tags", [])
                    })
                    
                if not simplified_results:
                    return f"Found 0 images matching '{query}'."
                    
                return json.dumps(simplified_results, ensure_ascii=False)
            except Exception as e:
                return f"Error searching images: {str(e)}"
                
        self._tools.append(search_tool) 

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def create_session(self, user_id: Optional[str] = None) -> str:
        """创建新会话"""
        import uuid
        session_id = str(uuid.uuid4())

        self._sessions[session_id] = {
            "user_id": user_id,
            "created_at": datetime.now(),
            "history": [],  # 对话历史
            "context": {}   # 上下文信息
        }

        logger.info(f"创建会话: {session_id}")
        return session_id

    def ensure_session(self, session_id: str, user_id: Optional[str] = None) -> str:
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "user_id": user_id,
                "created_at": datetime.now(),
                "history": [],
                "context": {},
            }
            logger.info(f"恢复会话: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        return self._sessions.get(session_id)

    async def chat(self, query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        使用Agent进行对话 (ReAct模式)
        
        Args:
            query: 用户查询
            session_id: 会话ID
            
        Returns:
            {"answer": str, "images": list}
        """
        conversation_id = session_id or "default_session"
        self._last_images_by_conversation.pop(conversation_id, None)
        token = self._current_conversation_id.set(conversation_id)

        if self._agent:
            try:
                # 构造输入
                inputs = {
                    "query": query,
                    "conversation_id": conversation_id
                }

                if session_id:
                    self.ensure_session(session_id)

                # 调用 ReActAgent 执行任务 (异步)
                # invoke 返回格式: {"output": "...", "result_type": "answer"}
                result = await self._agent.invoke(inputs)
                
                response = result.get("output", "抱歉，我没有理解您的意思。")
                
                # 记录历史
                if session_id:
                    self._update_history(session_id, query, response)
                    
                images = self._last_images_by_conversation.get(conversation_id, [])
                return {"answer": response, "images": images}
            except Exception as e:
                logger.error(f"Agent执行异常: {e}", exc_info=True)
                try:
                    answer = await self._chat_openai_compatible(query=query, session_id=session_id)
                    images = self._last_images_by_conversation.get(conversation_id, [])
                    return {"answer": answer, "images": images}
                except Exception as fallback_e:
                    logger.error(f"OpenAI兼容调用也失败: {fallback_e}", exc_info=True)
                    return {"answer": "抱歉，智慧相册Agent暂时无法响应，请稍后再试。", "images": []}
            finally:
                self._current_conversation_id.reset(token)
        
        # 回退逻辑：使用原有规则引擎
        intent_data = self.detect_intent(query)
        self._current_conversation_id.reset(token)
        return {"answer": self.generate_response(intent_data["intent"], {"total": 0}, query), "images": []}

    async def _chat_openai_compatible(self, query: str, session_id: Optional[str] = None) -> str:
        from openai import OpenAI

        settings = get_settings()
        if not settings.OPENAI_API_KEY:
            return "未配置OPENAI_API_KEY，无法使用智能对话。"

        if session_id:
            self.ensure_session(session_id)

        conversation_id = session_id or "default_session"

        system_prompt = (
            "You are a helpful smart album assistant for a photo album. "
            "Each photo has metadata fields available for filtering: filename, file_size, width, height, format, created_at (ISO datetime), tags (list of strings), description, extra (object). "
            "Use meta_search_images when the user wants to filter by metadata (date like 1.18/1月18日/2026-01-18, tags, filename, etc.). "
            "If the user mixes date + semantic description (e.g. '1.18 海边'), call meta_search_images with BOTH date_text and query to perform a combined search (date filtering + semantic similarity). "
            "Use semantic_search_images when the user describes visual/semantic content and wants similarity matching without metadata constraints. "
            "When user asks for time, use get_current_time."
        )

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "description": "获取当前系统时间，格式为 YYYY-MM-DD HH:MM:SS",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "semantic_search_images",
                    "description": "语义相似度检索图片。适用于用户用自然语言描述画面内容（例如 '海边日落'、'红色跑车'）。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "用户的搜索描述"},
                            "top_k": {"type": "integer", "description": "返回结果数量", "default": 5},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "meta_search_images",
                    "description": "按元数据检索图片，或做组合检索（日期过滤 + 语义相似度）。适用于 '1.18 的照片'、'标签是猫'、'1.18 海边'。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date_text": {"type": "string", "description": "日期文本，如 1.18 / 1月18日 / 2026-01-18"},
                            "query": {"type": "string", "description": "语义查询（可选）。与 date_text 同时提供时执行组合检索"},
                            "tags": {"type": "array", "items": {"type": "string"}, "description": "标签过滤（可选）"},
                            "top_k": {"type": "integer", "description": "返回结果数量", "default": 5},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_photo_meta_schema",
                    "description": "获取相册图片可用的元数据字段与含义，用于指导后续元数据检索。",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
        ]

        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        if session_id:
            session = self.get_session(session_id)
            if session and session.get("history"):
                history = session["history"][-20:]
                for msg in history:
                    role = msg.get("role")
                    content = msg.get("content")
                    if role in ("user", "assistant") and isinstance(content, str):
                        messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": query})

        client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)

        def call_model(msgs: List[Dict[str, Any]]):
            return client.chat.completions.create(
                model=settings.OPENAI_MODEL_NAME,
                messages=msgs,
                tools=tools,
                tool_choice="auto",
            )

        max_iters = 4
        final_text = ""
        tool_called = False
        tool_names: List[str] = []
        collected_images: List[Dict[str, Any]] = []

        for _ in range(max_iters):
            resp = await asyncio.to_thread(call_model, messages)
            choice = resp.choices[0]
            msg = choice.message

            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                tool_called = True
                tool_names.extend([tc.function.name for tc in tool_calls])
                messages.append(
                    {
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                            }
                            for tc in tool_calls
                        ],
                    }
                )

                for tc in tool_calls:
                    tool_name = tc.function.name
                    args_raw = tc.function.arguments
                    try:
                        import json

                        args = json.loads(args_raw) if args_raw else {}
                    except Exception:
                        args = {}

                    tool_output = ""
                    if tool_name == "get_current_time":
                        tool_output = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    elif tool_name == "get_photo_meta_schema":
                        import json

                        tool_output = json.dumps(
                            {
                                "fields": {
                                    "filename": "文件名",
                                    "file_size": "文件大小（字节）",
                                    "width": "图片宽度",
                                    "height": "图片高度",
                                    "format": "图片格式",
                                    "created_at": "创建时间（ISO datetime）",
                                    "tags": "标签列表",
                                    "description": "图片描述",
                                    "extra": "扩展字段对象",
                                },
                                "examples": [
                                    "帮我找 1.18 的照片",
                                    "找标签是 猫 的照片",
                                    "找海边日落的照片（语义检索）",
                                ],
                            },
                            ensure_ascii=False,
                        )
                    elif tool_name == "semantic_search_images":
                        q = args.get("query", "")
                        top_k = args.get("top_k", 5)
                        from .search_service import get_search_service

                        search_svc = get_search_service()
                        if not search_svc.is_initialized:
                            tool_output = "Error: Search service not initialized."
                        else:
                            date_text, rest = search_svc.split_date_and_query(q)
                            if date_text:
                                if rest:
                                    results = search_svc.search_by_text_with_meta(
                                        query_text=rest,
                                        date_text=date_text,
                                        top_k=top_k,
                                    )
                                else:
                                    results = search_svc.search_by_meta(date_text=date_text, top_k=top_k)
                            else:
                                results = search_svc.search_by_text(query_text=q, top_k=top_k)

                            if results:
                                collected_images.extend(results)
                            simplified = []
                            for res in results:
                                simplified.append(
                                    {
                                        "id": res.get("id"),
                                        "score": res.get("score"),
                                        "created_at": res.get("metadata", {}).get("created_at"),
                                        "tags": res.get("metadata", {}).get("tags", []),
                                    }
                                )
                            tool_output = json.dumps(simplified, ensure_ascii=False)
                    elif tool_name == "meta_search_images":
                        date_text = args.get("date_text")
                        q = args.get("query")
                        tags = args.get("tags")
                        top_k = args.get("top_k", 5)
                        from .search_service import get_search_service
                        import json

                        search_svc = get_search_service()
                        if not search_svc.is_initialized:
                            tool_output = "Error: Search service not initialized."
                        else:
                            if (not date_text) and isinstance(q, str) and q.strip():
                                extracted_date, rest = search_svc.split_date_and_query(q)
                                if extracted_date:
                                    date_text = extracted_date
                                    q = rest

                            if isinstance(q, str) and q.strip() and isinstance(date_text, str) and date_text.strip():
                                extracted_date, rest = search_svc.split_date_and_query(q)
                                if extracted_date and extracted_date == date_text:
                                    q = rest

                            if isinstance(q, str) and q.strip():
                                results = search_svc.search_by_text_with_meta(
                                    query_text=q.strip(),
                                    date_text=date_text,
                                    tags=tags,
                                    top_k=top_k,
                                )
                            else:
                                results = search_svc.search_by_meta(date_text=date_text, tags=tags, top_k=top_k)

                            if results:
                                collected_images.extend(results)
                            simplified = []
                            for res in results:
                                simplified.append(
                                    {
                                        "id": res.get("id"),
                                        "score": res.get("score"),
                                        "created_at": res.get("metadata", {}).get("created_at"),
                                        "tags": res.get("metadata", {}).get("tags", []),
                                    }
                                )
                            tool_output = json.dumps(simplified, ensure_ascii=False)
                    else:
                        tool_output = f"Error: Unknown tool '{tool_name}'."

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": tool_output,
                        }
                    )
                continue

            final_text = msg.content or ""
            break

        if session_id:
            self._update_history(session_id, query, final_text)

        if collected_images:
            seen: set[str] = set()
            deduped: List[Dict[str, Any]] = []
            for img in collected_images:
                img_id = img.get("id")
                if not isinstance(img_id, str) or img_id in seen:
                    continue
                seen.add(img_id)
                deduped.append(img)
            self._last_images_by_conversation[conversation_id] = deduped

        logger.info(
            "OpenAI兼容对话完成 (tool_called=%s, tools=%s, session_id=%s)",
            tool_called,
            tool_names,
            session_id or "(none)",
        )
        return final_text or "抱歉，我没有理解您的意思。"

    def _update_history(self, session_id: str, query: str, response: str):
        """更新会话历史"""
        session = self.get_session(session_id)
        if session:
            session["history"].append({
                "role": "user",
                "content": query,
                "timestamp": datetime.now()
            })
            session["history"].append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now()
            })

    def optimize_query(self, user_query: str, session_id: Optional[str] = None) -> str:
        """
        查询优化：将自然语言转换为更精确的搜索语义
        (保留原有接口兼容性)
        """
        logger.info(f"查询优化: '{user_query}'")

        # 如果Agent可用，可使用Agent进行改写
        # if self._agent: ...

        optimized_query = user_query
        return optimized_query

    def detect_intent(self, user_query: str) -> Dict[str, Any]:
        """
        意图识别：判断用户想做什么
        (保留原有接口兼容性)
        """
        logger.info(f"意图识别: '{user_query}'")

        query_lower = user_query.lower()

        # 删除意图
        if any(kw in query_lower for kw in ["删除", "删掉", "remove", "delete"]):
            return {"intent": "delete", "confidence": 0.8, "entities": {}}

        # 上传意图
        if any(kw in query_lower for kw in ["上传", "添加", "upload", "add"]):
            return {"intent": "upload", "confidence": 0.8, "entities": {}}

        # 分析意图
        if any(kw in query_lower for kw in ["分析", "识别", "这是什么", "analyze"]):
            return {"intent": "analyze", "confidence": 0.7, "entities": {}}

        # 默认为普通聊天意图，而非搜索
        return {"intent": "chat", "confidence": 0.9, "entities": {}}

    def generate_response(
        self,
        intent: str,
        results: Any,
        user_query: str
    ) -> str:
        """
        生成自然语言回复
        (保留原有接口兼容性)
        """
        if intent == "search":
            if isinstance(results, dict):
                total = results.get("total", 0)
                if total == 0:
                    return f"抱歉，没有找到与「{user_query}」相关的照片。可以尝试换个描述方式。"
                elif total == 1:
                    return f"找到 1 张符合「{user_query}」的照片。"
                else:
                    return f"为您找到了 {total} 张与「{user_query}」相关的照片。"

        elif intent == "chat":
            return "我是智慧相册助手，有什么可以帮您？我可以帮您搜索图片、管理相册。"

        elif intent == "delete":
            return "删除操作已完成。"
        elif intent == "upload":
            return "图片上传成功。"
        elif intent == "analyze":
            return "图片分析功能即将上线，敬请期待。"

        return "已完成您的请求。"

    def generate_suggestions(
        self,
        intent: str,
        results: Any,
        history: Optional[List[str]] = None
    ) -> List[str]:
        """
        生成后续建议
        (保留原有接口兼容性)
        """
        suggestions = []
        if intent == "search":
            if isinstance(results, dict):
                total = results.get("total", 0)
                if total == 0:
                    suggestions = ["换个描述试试", "查看所有照片", "按日期筛选"]
                elif total > 10:
                    suggestions = ["添加更多细节缩小范围", "按标签过滤", "查看相似图片"]
                else:
                    suggestions = ["查找相似的照片", "这些照片是什么时候拍的", "给这些照片打标签"]
        return suggestions


# 全局服务实例
_agent_service: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    """获取Agent服务实例"""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
