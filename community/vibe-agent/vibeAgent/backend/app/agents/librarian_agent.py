"""
检索 Agent（LibrarianAgent）

负责检索 openJiuwen 文档和 API 接口信息
"""
from typing import Dict, Any, Optional, AsyncIterator, List
from loguru import logger

from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.agent.config.base import AgentConfig

from app.agents.base import VibeBaseAgent
from app.context.context_manager import ContextManager
from app.models.agent_result import AgentResult


class LibrarianAgent(VibeBaseAgent):
    """
    检索 Agent - 继承 openJiuwen.BaseAgent
    
    职责：检索 openJiuwen 相关的文档和 API 接口信息
    关键约束：
    - ❌ 禁止使用 delegate_task 工具
    - ✅ 可以使用其他所有工具
    """
    
    def __init__(
        self,
        agent_config: AgentConfig,
        context_manager: Optional[ContextManager] = None,
        retriever=None  # DocumentRetriever 实例（可选，延迟初始化）
    ):
        """
        初始化检索 Agent
        
        Args:
            agent_config: Agent 配置（必须包含 model）
            context_manager: 上下文管理器
            retriever: DocumentRetriever 实例（可选）
        """
        super().__init__(agent_config, context_manager)
        self._retriever = retriever
        logger.info("初始化 LibrarianAgent")
    
    async def invoke(self, inputs: Dict, runtime: Runtime = None) -> Dict:
        """
        实现 openJiuwen 的 invoke 接口
        
        Args:
            inputs: 输入数据 {query, top_k, doc_type}
            runtime: Runtime 实例
        
        Returns:
            执行结果 {documents: [...]}
        """
        try:
            query = inputs.get("query", "")
            top_k = inputs.get("top_k", 5)
            doc_type = inputs.get("doc_type", "all")
            
            # 检索文档
            documents = await self.retrieve_documents(query, top_k, doc_type)
            
            return AgentResult.success_result(
                data={
                    "documents": documents,
                    "query": query,
                    "total": len(documents)
                }
            ).to_dict()
        
        except Exception as e:
            logger.error(f"文档检索失败: {e}", exc_info=True)
            return AgentResult.failure_result(error=str(e)).to_dict()
    
    async def stream(self, inputs: Dict, runtime: Runtime = None) -> AsyncIterator[Any]:
        """实现 openJiuwen 的 stream 接口"""
        result = await self.invoke(inputs, runtime)
        yield result
    
    async def retrieve_documents(
        self,
        query: str,
        top_k: int = 5,
        doc_type: str = "all"
    ) -> List[Dict[str, Any]]:
        """
        检索文档
        
        Args:
            query: 查询内容（如 "如何构建 ReActAgent"、"Workflow API"）
            top_k: 返回文档数量
            doc_type: 文档类型（"api"=仅API文档, "guide"=仅开发指南, "all"=全部）
        
        Returns:
            文档列表，每个文档包含 path, content, relevance_score
        """
        # 延迟初始化 DocumentRetriever
        if self._retriever is None:
            try:
                from app.rag.retriever import DocumentRetriever
                from app.config.settings import get_settings
                settings = get_settings()
                
                self._retriever = DocumentRetriever(
                    model_provider=settings.model.provider,
                    api_key=settings.model.api_key,
                    api_base=settings.model.api_base,
                    model_name=settings.model.model_name,
                    temperature=0.3
                )
            except ImportError:
                logger.warning("DocumentRetriever 不可用，返回空结果")
                return []
            except Exception as e:
                logger.error(f"初始化 DocumentRetriever 失败: {e}")
                return []
        
        # 调用 DocumentRetriever 检索
        try:
            documents = await self._retriever.retrieve(query, top_k=top_k)
        except Exception as e:
            logger.error(f"检索文档失败: {e}")
            return []
        
        # 根据 doc_type 过滤
        if doc_type != "all":
            documents = self._filter_by_type(documents, doc_type)
        
        # 格式化返回结果
        return [
            {
                "path": doc["path"],
                "content": doc["content"],
                "relevance_score": doc.get("relevance_score", 0.0)
            }
            for doc in documents
        ]
    
    def _filter_by_type(self, documents: List[Dict], doc_type: str) -> List[Dict]:
        """根据文档类型过滤"""
        if doc_type == "api":
            # 只返回 API 文档（路径包含 "API文档"）
            return [doc for doc in documents if "API文档" in doc["path"]]
        elif doc_type == "guide":
            # 只返回开发指南（路径包含 "开发指南"）
            return [doc for doc in documents if "开发指南" in doc["path"]]
        return documents
