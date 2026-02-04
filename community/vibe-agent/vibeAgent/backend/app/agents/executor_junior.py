"""
动态执行器（Executor-Junior）

根据类别动态创建，直接执行任务，禁止委托
"""
import asyncio
import time
from typing import Dict, Any, Optional, AsyncIterator
from loguru import logger

from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.agent.config.base import AgentConfig
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo

from app.agents.base import VibeBaseAgent
from app.config.categories import CategoryConfig, get_category_config
from app.context.context_manager import ContextManager
from app.models.agent_result import AgentResult
from app.modes.base import ModeGenerator, get_mode_generator
from app.utils import normalize_agent_mode


class ExecutorJunior(VibeBaseAgent):
    """
    动态执行器 - 继承 openJiuwen.BaseAgent
    
    关键约束：
    - ❌ 禁止使用 delegate_task 工具
    - ✅ 直接执行任务，使用所有可用工具
    """
    
    def __init__(
        self,
        agent_config: AgentConfig,
        category_config: CategoryConfig,
        system_content: str = "",
        context_manager: Optional[ContextManager] = None
    ):
        """
        初始化动态执行器
        
        Args:
            agent_config: Agent 配置（必须包含 model）
            category_config: 类别配置
            system_content: 系统内容（技能+类别提示）
            context_manager: 上下文管理器
        """
        super().__init__(agent_config, context_manager)
        self.category_config = category_config
        self.system_content = system_content
        
        # 注意：不注册 delegate_task 工具
        logger.info(f"创建动态执行器: {category_config.name}")
    
    async def invoke(self, inputs: Dict, runtime: Runtime = None) -> Dict:
        """
        实现 openJiuwen 的 invoke 接口
        
        Args:
            inputs: 输入数据 {query, agent_mode, mode_plan, ...}
            runtime: Runtime 实例
        
        Returns:
            执行结果
        """
        try:
            query = inputs.get("query", "")
            agent_mode = inputs.get("agent_mode", "workflow")
            mode_plan_data = inputs.get("mode_plan")
            
            # 🔍 [DEBUG] 执行器收到的输入
            logger.info(f"🔍 [DEBUG] ExecutorJunior.invoke 输入:")
            logger.info(f"🔍 [DEBUG]   agent_mode: {agent_mode}")
            logger.info(f"🔍 [DEBUG]   mode_plan_data type: {type(mode_plan_data).__name__}")
            logger.info(f"🔍 [DEBUG]   mode_plan_data: {str(mode_plan_data)[:300] if mode_plan_data else 'None'}...")
            logger.info(f"🔍 [DEBUG]   inputs keys: {list(inputs.keys())}")
            
            # 规范化 agent_mode（向后兼容：将 "agent" 映射到 "react"）
            agent_mode = normalize_agent_mode(agent_mode)
            
            # 转换 mode_plan 字典为对应的 Plan 对象
            mode_plan = None
            if mode_plan_data:
                from app.models.task import WorkflowPlan, ReActPlan, MultiAgentPlan
                if agent_mode == "workflow":
                    # 🔍 [DEBUG] 创建 WorkflowPlan 前验证必填字段
                    # 注意：WorkflowPlan.components 有默认值 default_factory=list，
                    # 所以即使缺失也能创建对象，但这是数据异常，应该记录警告
                    if isinstance(mode_plan_data, dict):
                        if "components" not in mode_plan_data:
                            # components 字段缺失：虽然 Pydantic 会使用默认值，但这是数据异常
                            # 说明数据在传递过程中丢失了字段，应该记录警告
                            logger.warning(
                                f"🔍 [DEBUG] ⚠️ WorkflowPlan 数据中缺少 components 字段！"
                                f"虽然会使用默认空列表，但这表明数据传递过程中可能出现了问题。"
                                f"mode_plan_data keys: {list(mode_plan_data.keys())}"
                            )
                        elif not mode_plan_data.get("components"):
                            # components 字段存在但为空列表，记录警告
                            logger.warning(
                                f"🔍 [DEBUG] ⚠️ components 字段存在但为空列表，"
                                f"这可能导致工作流生成失败"
                            )
                    mode_plan = WorkflowPlan(**mode_plan_data)
                    # 🔍 [DEBUG] 创建后检查
                    logger.info(f"🔍 [DEBUG] WorkflowPlan 创建后检查:")
                    logger.info(f"🔍 [DEBUG]   mode_plan.components type: {type(mode_plan.components).__name__}")
                    logger.info(f"🔍 [DEBUG]   mode_plan.components len: {len(mode_plan.components)}")
                    if not mode_plan.components:
                        logger.error(f"🔍 [DEBUG]   ❌ mode_plan.components 为空!")
                    else:
                        logger.info(f"🔍 [DEBUG]   ✅ mode_plan.components 包含 {len(mode_plan.components)} 个组件")
                elif agent_mode == "react":
                    mode_plan = ReActPlan(**mode_plan_data)
                elif agent_mode == "multi_agent":
                    mode_plan = MultiAgentPlan(**mode_plan_data)
                else:
                    logger.warning(f"未知的 agent_mode: {agent_mode}，尝试通用解析")
                    from app.models.task import ModePlan
                    mode_plan = ModePlan(**mode_plan_data)
            
            if not mode_plan:
                return AgentResult.failure_result(
                    error=f"{agent_mode.capitalize()}Plan 不能为 None，请确保规划器成功生成计划"
                ).to_dict()
            
            logger.info(f"📝 执行代码生成: mode={agent_mode}, files={mode_plan.files if mode_plan else 'N/A'}")
            
            # 使用模式生成器生成代码
            from app.modes.base import get_mode_generator
            generator = get_mode_generator(agent_mode)
            if not generator:
                return AgentResult.failure_result(
                    error=f"未知的模式: {agent_mode}"
                ).to_dict()
            
            # 准备 context，传递 LLM 调用能力
            generation_context = dict(inputs)  # 复制 inputs
            
            # 如果有事件队列，设置文件生成回调
            event_queue = inputs.get("_event_queue")
            runtime = inputs.get("runtime")
            user_input = inputs.get("user_input", "")
            
            if event_queue:
                from app.orchestrator.master_orchestrator import _get_file_display_name, _get_step_type
                
                # 构建文件到 step_id 的映射
                required_files = generator.get_required_files() if generator else []
                file_to_step_id = {fn: f"generate_{idx}" for idx, fn in enumerate(required_files)}
                
                def get_step_info(file_name: str):
                    """获取文件的步骤信息"""
                    step_id = file_to_step_id.get(file_name, f"generate_{len(file_to_step_id)}")
                    display_name = _get_file_display_name(file_name, agent_mode)
                    return step_id, display_name, _get_step_type(file_name)
                
                def emit_event(event_type: str, file_name: str, **extra):
                    """发送事件到队列"""
                    step_id, display_name, step_type = get_step_info(file_name)
                    event = {"type": event_type, "step_id": step_id, "step_name": display_name, "timestamp": time.time()}
                    event.update(extra)
                    event_queue.put_nowait(event)
                
                generation_context["on_file_start"] = lambda fn: emit_event(
                    "step_started", fn, 
                    message=f"开始{get_step_info(fn)[1]}",
                    data={"step": {"step_id": get_step_info(fn)[0], "step_name": get_step_info(fn)[1], 
                                   "step_type": get_step_info(fn)[2], "file_name": fn}}
                )
                generation_context["on_thinking"] = lambda fn, chunk, acc: emit_event(
                    "step_thinking", fn, message=chunk, data={"thought": acc}
                )
                generation_context["on_file_generated"] = lambda fn, content: emit_event(
                    "step_completed", fn,
                    message=f"{get_step_info(fn)[1]}完成",
                    data={"result": {"file_name": fn, "file_content": content}, "file_name": fn}
                )
                generation_context["user_input"] = user_input
                generation_context["agent_mode"] = agent_mode  # 传递给生成器，用于加载 skill 信息
            
            # 如果有 system_content，创建 LLM 调用函数
            if self.system_content:
                # 创建 LLM 调用函数（使用父类的 _call_llm 方法）
                async def llm_call_fn(prompt: str, system_prompt: str = None) -> str:
                    """LLM 调用函数，用于生成代码"""
                    try:
                        # 使用父类的 _call_llm 方法
                        return await self._call_llm(
                            prompt=prompt,
                            system_prompt=system_prompt or self.system_content,
                            runtime=runtime
                        )
                    except Exception as e:
                        logger.error(f"LLM 调用失败: {e}", exc_info=True)
                        raise
                
                # 创建 LLM 流式调用函数（用于思考过程生成）
                async def llm_stream_fn(prompt: str, system_prompt: str = None):
                    """LLM 流式调用函数，用于生成思考过程"""
                    try:
                        async for chunk in self._call_llm_stream(
                            prompt=prompt,
                            system_prompt=system_prompt or self.system_content,
                            runtime=runtime
                        ):
                            yield chunk
                    except Exception as e:
                        logger.warning(f"LLM 流式调用失败: {e}")
                        return
                
                # 将 LLM 调用函数和 system_content 添加到 context
                generation_context["llm_call_fn"] = llm_call_fn
                generation_context["llm_stream_fn"] = llm_stream_fn
                generation_context["system_content"] = self.system_content
                logger.info("✅ 已添加 LLM 调用能力到 context，将使用 LLM 生成代码")
            else:
                logger.warning("⚠️ 没有 system_content，将使用模板生成代码")
            
            # 生成代码文件
            files = await generator.generate(mode_plan, context=generation_context)
            
            # 注意：不在这里保存文件，文件保存将在验证通过后由 MasterOrchestrator 处理
            workflow_dir = inputs.get("workflow_dir", "")
            logger.info(f"📝 生成代码完成: {len(files)} 个文件，等待验证通过后保存到 {workflow_dir}")
            
            # 返回结果（包含生成的文件内容，但不保存到磁盘）
            return AgentResult.success_result(
                data={"files": files, "workflow_dir": workflow_dir},
                metadata={"agent_mode": agent_mode, "category": self.category_config.name}
            ).to_dict()
        
        except Exception as e:
            logger.error(f"执行器执行失败: {e}", exc_info=True)
            return AgentResult.failure_result(error=str(e)).to_dict()
    
    async def stream(self, inputs: Dict, runtime: Runtime = None) -> AsyncIterator[Any]:
        """
        实现 openJiuwen 的 stream 接口
        
        Args:
            inputs: 输入数据
            runtime: Runtime 实例
        
        Yields:
            流式数据
        """
        result = await self.invoke(inputs, runtime)
        yield result


def create_executor_junior(
    category: str,
    system_content: str = "",
    context_manager: Optional[ContextManager] = None
) -> ExecutorJunior:
    """
    创建动态执行器
    
    Args:
        category: 类别名称
        system_content: 系统内容
        context_manager: 上下文管理器
    
    Returns:
        ExecutorJunior 实例
    """
    # 获取类别配置
    category_config = get_category_config(category)
    
    # 创建模型配置
    from app.config.settings import get_settings
    settings = get_settings()
    
    model_config = ModelConfig(
        model_provider=category_config.model_provider,
        model_info=BaseModelInfo(
            api_key=settings.model.api_key,
            api_base=settings.model.api_base,
            model=category_config.model_name,  # 使用别名 'model'
            temperature=category_config.temperature,
            top_p=category_config.top_p,
            timeout=category_config.timeout
        )
    )
    
    # 创建 Agent 配置
    agent_config = AgentConfig(
        id=f"executor_junior_{category}",
        version="1.0.0",
        description=f"动态执行器 - {category_config.description}",
        model=model_config
    )
    
    return ExecutorJunior(
        agent_config=agent_config,
        category_config=category_config,
        system_content=system_content,
        context_manager=context_manager
    )
