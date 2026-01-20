import os
import asyncio
from dotenv import load_dotenv
import requests

from openjiuwen.core.common.logging import logger
script_dir = os.path.dirname(os.path.abspath(__file__))

# 加载环境变量 - 使用绝对路径确保能找到.env文件
env_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=env_path)
# 设置环境变量
API_BASE = os.getenv("API_BASE")
# 为了满足BaseModelInfo的验证要求，提供一个非空的默认API密钥（实际使用时需要替换为真实密钥）
API_KEY = os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER")  # 使用小写的openai以匹配model_library中的实现
os.environ["LLM_SSL_VERIFY"] = "False"

# 检查必要的环境变量
if API_KEY == "dummy-api-key-for-testing":
    logger.warning("使用默认的测试API密钥，实际使用时需要设置真实的API_KEY环境变量")

# 导入必要的模块
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.component.llm_comp import LLMComponent, LLMCompConfig
from openjiuwen.core.component.intent_detection_comp import IntentDetectionComponent, IntentDetectionCompConfig
from openjiuwen.core.component.tool_comp import ToolComponent, ToolComponentConfig
from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.service_api.restful_api import RestfulApi
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata
from openjiuwen.agent.common.schema import WorkflowSchema
from openjiuwen.agent.workflow_agent.workflow_agent import WorkflowAgent
from openjiuwen.agent.config.workflow_config import WorkflowAgentConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.memory.engine import MemoryEngine
from openjiuwen.core.memory.config import MemoryConfig, SysMemConfig
from openjiuwen.core.utils.llm.messages import BaseMessage
from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory
# 使用DBM存储
from openjiuwen.core.memory.store.impl.dbm_kv_store import DbmKVStore


# 创建模型配置
def _create_model_config() -> ModelConfig:
    """创建模型配置"""
    return ModelConfig(
        model_provider=MODEL_PROVIDER,
        model_info=BaseModelInfo(
            model=MODEL_NAME,
            api_base=API_BASE,
            api_key=API_KEY,
            temperature=0.7,
            top_p=0.9,
            timeout=120,
        ),
    )


# 初始化MemoryEngine
async def init_memory_engine():
    """初始化内存引擎"""
    logger.debug("开始初始化MemoryEngine")
    sys_config = SysMemConfig()
    logger.debug(f"MemoryEngine配置: {sys_config}")

    logger.debug("注册DBM存储")
    MemoryEngine.register_store(kv_store=DbmKVStore("memory.db"))

    logger.debug("创建MemoryEngine实例")
    mem_engine = await MemoryEngine.create_mem_engine_instance(sys_config)
    logger.debug("MemoryEngine实例创建成功")
    return mem_engine


# 创建开始组件

def _create_start_component():
    """创建开始组件"""
    return Start({"inputs": [
        {"id": "query", "type": "String", "required": "true", "sourceType": "ref"},
        {"id": "user_profile", "type": "String", "required": "true", "sourceType": "ref"},
        {"id": "raw_data", "type": "String", "required": "true", "sourceType": "ref"}
    ]})


# 创建结束组件
def _create_end_component():
    """创建结束组件"""
    return End({"responseTemplate": "{{output}}"})


# 创建意图识别组件（用于反馈处理）
def _create_feedback_intent_component() -> IntentDetectionComponent:
    """创建意图识别组件，用于检测用户反馈"""
    model_config = _create_model_config()
    config = IntentDetectionCompConfig(
        user_prompt="请判断用户对晨间简报的反馈意图",
        category_name_list=["正常反馈", "太长了", "不要推这方向"],
        model=model_config,
    )
    logger.debug(f"创建意图识别组件，配置: {config}")
    component = IntentDetectionComponent(config)
    # 根据意图分类结果决定下一步流向
    component.add_branch("${intent.classification_id} == 0", ["relevance_scoring"], "正常反馈")
    component.add_branch("${intent.classification_id} == 1", ["relevance_scoring"], "太长了反馈")
    component.add_branch("${intent.classification_id} == 2", ["relevance_scoring"], "主题反馈")
    component.add_branch("1 == 1", ["relevance_scoring"], "默认分支")  # 添加默认分支以处理所有情况
    return component


# 创建用户画像更新工具组件
def _create_update_profile_tool() -> ToolComponent:
    """创建更新用户画像的工具组件"""
    tool_config = ToolComponentConfig()

    # 定义更新用户画像的工具
    update_profile_tool = RestfulApi(
        name="UpdateUserProfile",
        description="更新用户画像工具",
        params=[
            Param(name="user_id", description="用户ID", type="string", required=True),
            Param(name="profile_type", description="画像类型", type="string", required=True),
            Param(name="value", description="更新值", type="string", required=True),
        ],
        path="http://localhost:9000/update_profile",
        headers={},
        method="POST",
        response=[],
    )

    tool_component = ToolComponent(tool_config)
    logger.debug(f"创建更新用户画像工具组件，配置: {tool_config}")
    return tool_component.bind_tool(update_profile_tool)


# 创建数据相关性打分组件
def _create_relevance_scoring_component() -> LLMComponent:
    """创建数据相关性打分组件"""
    model_config = _create_model_config()

    user_prompt = ("\n用户画像：{{user_profile}}\n\n原始数据列表：{{raw_data}}\n\n"
                   "请根据用户画像对每条数据进行相关性打分（0-10分），并给出清洗建议。\n"
                   "输出格式为JSON数组，包含每条数据的id、relevance_score和keep字段（true/false）。")

    config = LLMCompConfig(
        model=model_config,
        template_content=[{"role": "user", "content": user_prompt}],
        response_format={"type": "json"},
        output_config={
            "scored_data": {"type": "array", "description": "打分后的数据列表", "required": True}
        },
    )
    logger.debug(f"创建数据相关性打分组件，配置: {config}")
    return LLMComponent(config)


# 创建晨间简报生成组件

def _create_brief_generation_component() -> LLMComponent:
    """创建晨间简报生成组件"""
    model_config = _create_model_config()

    user_prompt = ("\n用户画像：{{user_profile}}\n\n原始新闻数据：{{raw_data}}\n\n新闻相关性评分：{{scored_data}}\n\n"
                   "请根据用户画像、原始新闻数据和相关性评分生成一份符合用户画像的个性化晨间简报。\n"
                   "要求：\n"
                   "1. 输出格式必须为JSON数组，每个元素包含三个字段：category（新闻类别）、content（新闻摘要）、url（新闻对应的原始链接，直接从输入数据中提取，不得编造）\n"
                   "2. 结构清晰，分模块呈现（如【今日头条】【技术深度】【行业动态】等）\n"
                   "3. 语言专业简洁\n"
                   "4. 根据相关性评分对新闻进行排序，优先展示相关性高的新闻\n"
                   "5. 有且仅生成3个新闻条目\n"
                   "6. 每个新闻条目的category必须唯一，不能重复\n"
                   "7. 控制在300字以内，重点突出\n"
                   "\n示例输出格式：\n"
                   "[\n"
                   "    {\n"
                   "        \"category\": \"今日头条\",\n"
                   "        \"content\": \"GPT-5最新进展曝光，多模态能力提升300%，预计Q3发布\",\n"
                   "        \"url\": \"https://example.com/gpt5-news\"\n"
                   "    },\n"
                   "    {\n"
                   "        \"category\": \"技术深度\",\n"
                   "        \"content\": \"国内首个开源大模型生态系统正式上线，支持多框架部署\",\n"
                   "        \"url\": \"https://example.com/open-source-llm\"\n"
                   "    },\n"
                   "    {\n"
                   "        \"category\": \"行业动态\",\n"
                   "        \"content\": \"量子计算突破！谷歌量子计算机实现4096量子比特稳定运行\",\n"
                   "        \"url\": \"https://example.com/quantum-computing\"\n"
                   "    }\n"
                   "]")

    config = LLMCompConfig(
        model=model_config,
        template_content=[{"role": "user", "content": user_prompt}],
        response_format={"type": "json"},
        output_config={
            "morning_brief": {"type": "string", "description": "生成的晨间简报", "required": True}
        },
    )
    logger.debug(f"创建晨间简报生成组件，配置: {config}")
    return LLMComponent(config)


# 创建工作流
def create_workflow():
    """创建具备长期记忆和即时反馈闭环的工作流"""
    # 工作流配置
    workflow_id = "memory_workflow_agent"
    workflow_version = "1.0"
    workflow_name = "memory_agent"

    workflow_config = WorkflowConfig(
        metadata=WorkflowMetadata(
            name=workflow_name,
            id=workflow_id,
            version=workflow_version,
        )
    )

    # 创建工作流对象
    logger.debug(f"开始构建工作流，配置: {workflow_config}")
    flow = Workflow(workflow_config=workflow_config)

    # 实例化所有组件
    start = _create_start_component()
    feedback_intent = _create_feedback_intent_component()
    relevance_scoring = _create_relevance_scoring_component()
    brief_generation = _create_brief_generation_component()
    end = _create_end_component()

    # 注册组件到工作流
    logger.debug("添加start组件到工作流")
    flow.set_start_comp("start", start, inputs_schema={
        "query": "${query}",
        "user_profile": "${user_profile}",
        "raw_data": "${raw_data}"
    })
    logger.debug("添加feedback_intent组件到工作流")
    flow.add_workflow_comp("feedback_intent", feedback_intent, inputs_schema={"query": "${start.query}"})
    logger.debug("添加relevance_scoring组件到工作流")
    flow.add_workflow_comp("relevance_scoring", relevance_scoring, inputs_schema={
        "user_profile": "${user_profile}",
        "raw_data": "${raw_data}"
    })
    logger.debug("添加brief_generation组件到工作流")
    flow.add_workflow_comp("brief_generation", brief_generation, inputs_schema={
        "user_profile": "${user_profile}",
        "raw_data": "${raw_data}",
        "scored_data": "${relevance_scoring.scored_data}"
    })
    logger.debug("添加end组件到工作流")
    flow.set_end_comp("end", end, inputs_schema={"output": "${brief_generation.morning_brief}"})

    # 连接工作流拓扑
    logger.debug("开始绑定工作流连接")
    flow.add_connection("start", "feedback_intent")
    flow.add_connection("feedback_intent", "relevance_scoring")
    flow.add_connection("relevance_scoring", "brief_generation")
    flow.add_connection("brief_generation", "end")
    logger.debug("工作流连接绑定完成")

    return flow


# 创建WorkflowAgent
def create_memory_workflow_agent():
    """创建记忆型WorkflowAgent"""
    # 工作流配置
    workflow_id = "memory_workflow_agent"
    workflow_version = "1.0"
    workflow_name = "memory_agent"

    # 创建工作流schema
    schema = WorkflowSchema(
        id=workflow_id,
        name=workflow_name,
        description="具备长期记忆和即时反馈闭环的工作流代理",
        version=workflow_version,
        inputs={
            "query": {"type": "string"},
            "user_id": {"type": "string"},
            "user_profile": {"type": "string"},
            "raw_data": {"type": "string"}
        }
    )

    workflow_agent_config = WorkflowAgentConfig(
        id="memory_workflow_agent",
        version="1.0.0",
        description="具备长期记忆和即时反馈闭环的WorkflowAgent",
        workflows=[schema]
    )

    # 创建Agent实例
    logger.debug("创建WorkflowAgent实例")
    workflow_agent = WorkflowAgent(workflow_agent_config)

    # 创建并绑定工作流
    logger.debug("创建并绑定工作流到Agent")
    flow = create_workflow()
    workflow_agent.bind_workflows([flow])
    logger.debug("工作流绑定完成")

    return workflow_agent


# 获取新闻数据的函数
def get_news(apikey: str, key_words: str, country: str = "cn,us,kr", language: str = "zh,zht,en"):
    """通过newsdata.io API获取新闻数据

    Args:
        apikey (str): API密钥
        key_words (str): 搜索关键词
        country (str): 国家代码，多个用逗号分隔
        language (str): 语言代码，多个用逗号分隔

    Returns:
        list: 格式化后的新闻列表
    """
    base_url = "https://newsdata.io/api/1/latest"

    # 构建URL参数
    params = {
        'apikey': apikey,
        'q': key_words,
        'country': country,
        'language': language
    }

    try:

        # 发起接口网络请求
        response = requests.get(base_url, params=params, timeout=10)

        # 解析响应结果
        if response.status_code == 200:
            data = response.json()

            # 检查请求是否成功
            if data.get('status') == 'success':
                news_list = data.get('results', [])
                # 格式化新闻数据
                formatted_news = []
                for i, news in enumerate(news_list, 1):
                    # 获取新闻标题和描述
                    title = news.get('title', '')
                    description = news.get('description', '')
                    keywords = news.get('keywords', '')
                    url = news.get('link', '')
                    country = news.get('country', '')
                    pub_date = news.get('pubDate', '')
                    source_name = news.get('source_name', '')
                    language = news.get('language', '')
                    if language != "chinese":
                        translated_title = trans(title)
                    else:
                        translated_title = title

                    formatted_news.append({
                        'id': i,
                        'title': title,
                        'description': description,
                        'keywords': keywords,
                        'url': url,
                        'country': country,
                        'pub_date': pub_date,
                        'source_name': source_name,
                        'language': language,
                        'translated_title': translated_title
                    })
                logger.info(f"news data: {formatted_news}")
                return formatted_news
    except requests.exceptions.RequestException as e:
        # 网络异常时返回模拟数据，保持与正常返回数据结构一致
        return []


def trans(text: str) -> str:
    if not text or len(text) == 0:
        return ""
    model = ModelFactory().get_model(
        model_provider="openai",
        api_base=API_BASE,
        api_key=API_KEY,
    )
    prompt = f"请将以下文本翻译成中文：\n{text}"
    res = model.invoke(model_name=MODEL_NAME, messages=[BaseMessage(content=prompt, role="user")])
    translated_text = res.content if hasattr(res, 'content') else str(res)
    return translated_text


def filter_news_fields(formatted_news: list, need_fields: list = None) -> list:
    """
    Args:
        formatted_news (list): get_news方法返回的格式化后的原始新闻列表
        need_fields (list, 可选): 需要保留的字段列表，不传则默认提取指定4个核心字段

    Returns:
        list: 仅包含指定字段的过滤后新闻列表
    """
    default_fields = ['translated_title', 'translated_description', 'translated_keywords', 'language', 'url']
    fields = need_fields if need_fields and isinstance(need_fields, list) else default_fields
    filtered_news = []

    # 参数合法性校验
    if not isinstance(formatted_news, list):
        logger.warning("传入的新闻数据格式错误，非列表类型")
        return filtered_news

    # 遍历提取字段，过滤非字典类型数据
    for news in formatted_news:
        if not isinstance(news, dict):
            continue
        filter_item = {field: news.get(field, "") for field in fields}
        filtered_news.append(filter_item)

    logger.info(f"新闻过滤完成：原数据{len(formatted_news)}条，过滤后{len(filtered_news)}条，提取字段：{fields}")
    return filtered_news


# 测试函数
async def main():
    """主函数"""
    logger.info("启动记忆工作流代理...")

    # 初始化内存引擎
    mem_engine = await init_memory_engine()

    # 设置用户ID和组ID
    user_id = "user_123"
    group_id = "group_001"

    # 设置内存配置
    mem_config = MemoryConfig(
        mem_variables={
            "interests": "用户的兴趣",
            "dislikes": "用户的负面偏好",
            "reading_preferences": "用户的阅读偏好",
            "career": "用户的职业"
        },
        enable_long_term_mem=True
    )
    mem_engine.set_group_config(group_id=group_id, config=mem_config)
    mem_engine.set_group_llm_config(group_id=group_id, llm_config=_create_model_config())

    # 初始化用户画像 - 互联网程序员，关注AI新闻
    await mem_engine.update_user_variable(user_id=user_id, group_id=group_id, name="interests",
                                          value="AI技术, 机器学习, 大模型, 量子计算, 编程语言, 开发者工具")
    await mem_engine.update_user_variable(user_id=user_id, group_id=group_id, name="dislikes",
                                          value="娱乐八卦, 体育新闻, 过长的内容")
    await mem_engine.update_user_variable(user_id=user_id, group_id=group_id, name="reading_preferences",
                                          value="喜欢量子位、机器之心、新纪元的风格, 偏好技术深度, 关注行业趋势")
    await mem_engine.update_user_variable(user_id=user_id, group_id=group_id, name="career",
                                          value="互联网后端程序员, 5年工作经验, 熟悉Python和Go语言")
    await mem_engine.update_user_variable(user_id=user_id, group_id=group_id, name="name", value="张三")

    # 获取用户画像
    # user_profile = await mem_engine.list_user_variables(user_id=user_id, group_id=group_id)
    # 直接设定用户画像为指定内容
    user_profile = "用户的姓名是张三，用户是一名互联网程序员，用户正在关注AI"

    # 通过API获取新闻数据
    logger.info("开始通过API获取新闻数据...")
    api_key = os.getenv("NEWSDATA_API_KEY")
    key_words = ["AI", "大模型", "量子计算"]
    country_enum = "cn,us,kr"
    language_enum = "zh,zht,en"

    raw_data = get_news(api_key, " OR ".join(key_words), country_enum, language_enum)
    logger.info(f"成功获取{len(raw_data)}条新闻数据")
    # 如果获取的新闻少于3条，补充一些模拟AI新闻数据
    if len(raw_data) < 3:
        logger.warning("获取的新闻数据不足3条，补充模拟数据")
        additional_news = [
            {"id": len(raw_data) + 1, "content": "量子位：GPT-5最新进展曝光，多模态能力提升300%，预计Q3发布"},
            {"id": len(raw_data) + 2, "content": "机器之心：国内首个开源大模型生态系统正式上线，支持多框架部署"},
            {"id": len(raw_data) + 3, "content": "新纪元：量子计算突破！谷歌量子计算机实现4096量子比特稳定运行"}
        ]
        raw_data.extend(additional_news[:3 - len(raw_data)])

    # 创建并运行WorkflowAgent
    workflow_agent = create_memory_workflow_agent()

    # 执行工作流
    result = await workflow_agent.invoke({
        "user_id": user_id,
        "user_profile": str(user_profile),
        "raw_data": str(raw_data),
        "query": "生成今天的AI行业晨间简报"
    })

    logger.info(f"\n\n===== 个性化晨间简报生成完成 =====")
    logger.info(f"用户：互联网程序员")
    logger.info(f"兴趣：AI技术、机器学习、大模型、量子计算")
    logger.info(f"阅读偏好：量子位、机器之心、新纪元风格")
    logger.info(f"\n简报内容：")
    logger.info(result['output'].result['responseContent'])


if __name__ == "__main__":
    asyncio.run(main())