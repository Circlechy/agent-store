import os
os.environ["WORKFLOW_EXECUTE_TIMEOUT"] = '7200'

from typing import Any, Dict
from datetime import date
import asyncio
from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory
from openjiuwen.core.common.logging import logger
from openjiuwen.core.component.base import WorkflowComponent
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.graph.executable import Input, Output
from openjiuwen.core.runtime.base import ComponentExecutable
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.runtime.workflow import WorkflowRuntime

from jiuwenfintech.utils.stock_utils import StockUtils
from jiuwenfintech.agent_utils import Toolkit


class JiuwenFintechWorkflow:
    def __init__(self, config: Dict[str, Any] = None):

        self.config = config
        self.logger = logger

        os.makedirs(
            os.path.join(self.config["project_dir"], "dataflows/data_cache"),
            exist_ok=True,
        )

        self.workflow = create_workflow()

    def run(self, stock_code: str) -> Dict[str, Any]:
        runtime = WorkflowRuntime()
        asyncio.run(self.workflow.invoke({"stock_code": stock_code, "config": self.config}, runtime))

class BaseNode(ComponentExecutable, WorkflowComponent):
    def __init__(self):
        super().__init__()

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        return await self._do_invoke(inputs, runtime, context)

    def _pre_handle(self, inputs: Input, runtime: Runtime, context: Context):
        pass

    async def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        pass

    def _post_handle(self, inputs: Input, algorithm_output: object, runtime: Runtime, context: Context):
        pass


class StartNode(Start):
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context):
        try:
            import tushare as ts
            token = os.getenv('TUSHARE_TOKEN')
            pro = ts.pro_api(os.getenv(token))
            data = pro.etf_basic(list_status='L', fields='ts_code,extname,index_code,index_name,exchange,mgr_name')
        except Exception as e:
            raise ValueError("请设置足够积分的Tushare Token")

        runtime.update_global_state({"stock_code": inputs.get("stock_code", "")})
        # runtime.update_global_state({"current_date": date.today().strftime("%Y-%m-%d")})
        runtime.update_global_state({"current_date":"2026-01-01"})
        runtime.update_global_state({"config": inputs.get("config", "")})
        runtime.update_global_state({"debate_rounds": 0})
        runtime.update_global_state({"positive_researcher_debate": []})
        runtime.update_global_state({"negative_researcher_debate": []})

        toolkit = Toolkit(config=inputs.get("config", {}))
        market_data = await toolkit.get_stock_market_data_unified("000001", date.today().strftime("%Y-%m-%d"), date.today().strftime("%Y-%m-%d"))

        runtime.update_global_state({"toolkit": toolkit})


class TechnicalAnalysisNode(BaseNode):

    def __init__(self):
        super().__init__()

    def _pre_handle(self, inputs: Input, runtime: Runtime, context: Context):
        pass

    async def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        stock_code = runtime.get_global_state("stock_code")
        current_date = runtime.get_global_state("current_date")
        toolkit = runtime.get_global_state("toolkit")
        config = runtime.get_global_state("config")

        market_info = StockUtils.get_market_info(stock_code)
        company_name = self._get_company_name(stock_code, market_info)
        market_data = await toolkit.get_stock_market_data_unified(stock_code, current_date, current_date)
        logger.info(f"[技术分析师] 完成获取股票市场行情数据：{market_data}")

        factory = ModelFactory()
        llm = factory.get_model(
            model_provider="openai",
            api_base=config.get("backend_url"),
            api_key=os.getenv("API_KEY"),
            max_retries=3,
            timeout=60
        )
        messages = [
            {"role": "system", "content": (
                f"你是一位专业的股票技术分析师，基于用户输入的股票市场行情数据，输出股票技术分析报告。\n"
                f"\n"
                f"📋 **分析对象：**\n"
                f"- 公司名称：{company_name}\n"
                f"- 股票代码：{stock_code}\n"
                f"- 所属市场：{market_info['market_name']}\n"
                f"- 计价货币：{market_info['currency_name']}（{market_info['currency_symbol']}）\n"
                f"- 分析日期：{current_date}\n"
                f"\n"
                f" **输出格式要求（必须严格遵守）：**\n"
                f"\n"
                f"##  股票基本信息\n"
                f"- 公司名称：{company_name}\n"
                f"- 股票代码：{stock_code}\n"
                f"- 所属市场：{market_info['market_name']}\n"
                f"\n"
                f"##  技术指标分析\n"
                f"[在这里分析移动平均线、MACD、RSI、布林带等技术指标，提供具体数值]\n"
                f"\n"
                f"## 📉 价格趋势分析\n"
                f"[在这里分析价格趋势，考虑{market_info['market_name']}市场特点]\n"
                f"\n"
                f"## 💭 投资建议\n"
                f"[在这里给出明确的投资建议：买入/持有/卖出]\n"
                f"\n"
                f" **重要提醒：**\n"
                f"- 必须使用上述格式输出，不要自创标题格式\n"
                f"- 所有价格数据使用{market_info['currency_name']}（{market_info['currency_symbol']}）表示\n"
                f"- 确保在分析中正确使用公司名称\"{company_name}\"和股票代码\"{stock_code}\"\n"
                f"- 不要在标题中使用\"技术分析报告\"等自创标题\n"
                f"- 如果你有明确的技术面投资建议（买入/持有/卖出），请在投资建议部分明确标注\n"
                f"- 不要使用'最终交易建议'前缀，因为最终决策需要综合所有分析师的意见\n"
                f"\n"
                f"请使用中文，基于真实数据进行分析。"
            )},
            {"role": "user", "content": market_data}
        ]

        response = llm.invoke(model_name=config.get("model_name"), messages=messages, temperature=0.7, top_p=0.95)
        logger.info(f"[技术分析师] 完成生成股票技术分析报告：{response.content}")

        runtime.update_global_state({"company_name": company_name})
        runtime.update_global_state({"market_data": market_data})
        runtime.update_global_state({"market_report": response.content})

    def _post_handle(self, inputs: Input, algorithm_output: dict, runtime: Runtime, context: Context):
        pass

    def _get_company_name(self, ticker: str, market_info: dict) -> str:
        """
        根据股票代码获取公司名称

        Args:
            ticker: 股票代码
            market_info: 市场信息字典

        Returns:
            str: 公司名称
        """
        try:
            if market_info['is_china']:
                from jiuwenfintech.data.interface import get_china_stock_info_unified
                stock_info = get_china_stock_info_unified(ticker)

                logger.debug(f" [市场分析师] 获取股票信息返回: {stock_info[:200] if stock_info else 'None'}...")

                if stock_info and "股票名称:" in stock_info:
                    company_name = stock_info.split("股票名称:")[1].split("\n")[0].strip()
                    logger.info(f" [市场分析师] 成功获取中国股票名称: {ticker} -> {company_name}")
                    return company_name
                else:
                    logger.warning(f" [市场分析师] 无法从统一接口解析股票名称: {ticker}，尝试降级方案")
                    try:
                        from jiuwenfintech.data.data_source_manager import \
                            get_china_stock_info_unified as get_info_dict
                        info_dict = get_info_dict(ticker)
                        if info_dict and info_dict.get('name'):
                            company_name = info_dict['name']
                            logger.info(f" [市场分析师] 降级方案成功获取股票名称: {ticker} -> {company_name}")
                            return company_name
                    except Exception as e:
                        logger.error(f" [市场分析师] 降级方案也失败: {e}")

                    logger.error(f" [市场分析师] 所有方案都无法获取股票名称: {ticker}")
                    return f"股票代码{ticker}"

            elif market_info['is_hk']:
                try:
                    from jiuwenfintech.data.providers.hk.improved_hk import get_hk_company_name_improved
                    company_name = get_hk_company_name_improved(ticker)
                    logger.debug(f" [DEBUG] 使用改进港股工具获取名称: {ticker} -> {company_name}")
                    return company_name
                except Exception as e:
                    logger.debug(f" [DEBUG] 改进港股工具获取名称失败: {e}")
                    clean_ticker = ticker.replace('.HK', '').replace('.hk', '')
                    return f"港股{clean_ticker}"

            elif market_info['is_us']:
                us_stock_names = {
                    'AAPL': '苹果公司',
                    'TSLA': '特斯拉',
                    'NVDA': '英伟达',
                    'MSFT': '微软',
                    'GOOGL': '谷歌',
                    'AMZN': '亚马逊',
                    'META': 'Meta',
                    'NFLX': '奈飞'
                }

                company_name = us_stock_names.get(ticker.upper(), f"美股{ticker}")
                logger.debug(f" [DEBUG] 美股名称映射: {ticker} -> {company_name}")
                return company_name

            else:
                return f"股票{ticker}"

        except Exception as e:
            logger.error(f" [DEBUG] 获取公司名称失败: {e}")
            return f"股票{ticker}"


class FundamentalAnalysisNode(BaseNode):

    def __init__(self):
        super().__init__()

    def _pre_handle(self, inputs: Input, runtime: Runtime, context: Context):
        pass

    async def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        stock_code = runtime.get_global_state("stock_code")
        current_date = runtime.get_global_state("current_date")
        toolkit = runtime.get_global_state("toolkit")
        config = runtime.get_global_state("config")

        fundamentals_data = await toolkit.get_stock_fundamentals_unified(stock_code, current_date, current_date, current_date)
        logger.info(f"[基本面分析师] 完成获取股票基本面数据：{fundamentals_data}")

        factory = ModelFactory()
        llm = factory.get_model(
            model_provider="openai",
            api_base=config.get("backend_url"),
            api_key=os.getenv("API_KEY"),
            max_retries=3,
            timeout=60
        )
        messages = [
            {"role": "system",
             "content": (
                 f"你是一位专业的股票基本面分析师，基于用户输入的股票基本面数据，输出股票基本面分析报告。\n"
                 f"🚨 现在你必须基于这些数据生成完整的基本面分析报告！🚨\n\n"
                 f"报告必须包含以下内容：\n"
                 f"1. 公司基本信息和财务数据分析\n"
                 f"2. PE、PB、PEG等估值指标分析\n"
                 f"3. 当前股价是否被低估或高估的判断\n"
                 f"4. 合理价位区间和目标价位建议\n"
                 f"5. 基于基本面的投资建议（买入/持有/卖出）\n\n"
                 f"要求：\n"
                 f"- 使用中文撰写报告\n"
                 f"- 基于消息历史中的真实数据进行分析\n"
                 f"- 分析要详细且专业\n"
                 f"- 投资建议必须明确（买入/持有/卖出）"
             )},
            {"role": "user", "content": fundamentals_data}
        ]

        response = llm.invoke(model_name=config.get("model_name"), messages=messages, temperature=0.7, top_p=0.95)
        logger.info(f"[基本面分析师] 完成生成股票基本面分析报告：{response.content}")

        runtime.update_global_state({"fundamentals_data": fundamentals_data})
        runtime.update_global_state({"fundamentals_report": response.content})

    def _post_handle(self, inputs: Input, algorithm_output: dict, runtime: Runtime, context: Context):
        pass


class NewsAnalysisNode(BaseNode):

    def __init__(self):
        super().__init__()

    def _pre_handle(self, inputs: Input, runtime: Runtime, context: Context):
        pass

    async def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        stock_code = runtime.get_global_state("stock_code")
        current_date = runtime.get_global_state("current_date")
        toolkit = runtime.get_global_state("toolkit")
        config = runtime.get_global_state("config")

        news_data = toolkit.get_stock_news_unified(stock_code, current_date)
        news_data += "\n" + toolkit.get_realtime_stock_news(stock_code, current_date)
        logger.info(f"[数字媒体分析师] 完成获取股票新闻数据：{news_data}")

        factory = ModelFactory()
        llm = factory.get_model(
            model_provider="openai",
            api_base=config.get("backend_url"),
            api_key=os.getenv("API_KEY"),
            max_retries=3,
            timeout=60
        )
        messages = [
            {"role": "system",
             "content": (
                 f"你是一位专业的财经新闻分析师，需要基于用户提供的最新的股票市场财经新闻和事件详细分析对{stock_code}股票价格的潜在影响，你需要：\n"
                 f"- 评估新闻事件的紧急程度和市场影响\n"
                 f"- 识别可能影响股价的关键信息\n"
                 f"- 分析新闻的时效性和可靠性\n"
                 f"- 提供基于新闻的交易建议和价格影响评估\n\n"
                 f"若存在以下类型的新闻，你需要重点关注：\n"
                 f"- 财报发布和业绩指导\n"
                 f"- 重大合作和并购消息\n"
                 f"- 政策变化和监管动态\n"
                 f"- 突发事件和危机管理\n"
                 f"- 行业趋势和技术突破\n"
                 f"- 管理层变动和战略调整\n\n"
                 f"分析要点：\n"
                 f"- 市场影响程度（对股价的潜在影响）\n"
                 f"- 投资者情绪变化（正面/负面/中性）\n"
                 f"- 与历史类似事件的对比\n\n"
                 f"新闻影响分析要求：\n"
                 f"- 评估新闻对股价的短期影响和市场情绪变化\n"
                 f"- 分析新闻的利好/利空程度和可能的市场反应\n"
                 f"- 评估新闻对公司基本面和长期投资价值的影响\n"
                 f"- 识别新闻中的关键信息点和潜在风险\n"
                 f"- 对比历史类似事件的市场反应\n"
                 f"- 聚焦新闻内容本身的解读，不涉及技术指标分析\n\n"
                 f"请撰写详细的中文分析报告，并在报告末尾附上Markdown表格总结关键发现：\n"
                 f"- 总结最新的新闻事件和市场动态\n"
                 f"- 分析新闻对股票的潜在影响\n"
                 f"- 评估市场情绪和投资者基于新闻的市场反应预期\n"
                 f"- 提供基于新闻的投资建议\n"
                 f"- 不允许回复'无法评估影响'或'需要更多信息'等类似结果"
             )},
            {"role": "user", "content": news_data}
        ]

        response = llm.invoke(model_name=config.get("model_name"), messages=messages, temperature=0.7, top_p=0.95)
        logger.info(f"[数字媒体分析师] 完成生成股票新闻分析报告：{response.content}")

        runtime.update_global_state({"news_data": news_data})
        runtime.update_global_state({"news_report": response.content})
        pass

    def _post_handle(self, inputs: Input, algorithm_output: dict, runtime: Runtime, context: Context):
        pass


class MacroEconomyAnalysisNode(BaseNode):
    def __init__(self):
        super().__init__()

    def _pre_handle(self, inputs: Input, runtime: Runtime, context: Context):
        pass

    async def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        stock_code = runtime.get_global_state("stock_code")
        current_date = runtime.get_global_state("current_date")
        toolkit = runtime.get_global_state("toolkit")
        config = runtime.get_global_state("config")

        factory = ModelFactory()
        llm = factory.get_model(
            model_provider="openai",
            api_base=config.get("backend_url"),
            api_key=os.getenv("API_KEY"),
            max_retries=3,
            timeout=60
        )
        messages = [
            {"role": "system",
             "content": (
                 f"你是一位资深的宏观经济分析师，拥有20年国际经济研究经验，曾在IMF、世界银行等顶级机构担任顾问。具备深厚的理论功底和丰富的实战经验，能够准确把握全球经济脉搏。\n"
                 f"\n"
                 f"## 核心能力框架\n"
                 f"\n"
                 f"### 1. 数据解读能力\n"
                 f"- 精准解读GDP、CPI、PPI、PMI等核心经济指标\n"
                 f"- 识别统计数据背后的结构性变化和趋势拐点\n"
                 f"- 评估数据质量和可能的统计偏差\n"
                 f"\n"
                 f"### 2. 政策分析能力\n"
                 f"- 深入分析货币政策、财政政策、产业政策的影响机制\n"
                 f"- 评估政策传导效果和时滞特征\n"
                 f"- 预测政策路径和转向信号\n"
                 f"\n"
                 f"### 3. 风险评估能力\n"
                 f"- 系统识别系统性金融风险点\n"
                 f"- 评估外部冲击的传导路径和影响程度\n"
                 f"- 构建压力测试和情景分析框架\n"
                 f"\n"
                 f"### 4. 预测建模能力\n"
                 f"- 运用多元计量模型进行经济预测\n"
                 f"- 结合领先指标和滞后指标判断周期位置\n"
                 f"- 提供概率分布而非点预测\n"
                 f"\n"
                 f"## 分析方法论\n"
                 f"\n"
                 f"### 短期分析框架\n"
                 f"1. **需求侧三驾马车**：消费、投资、净出口的动态平衡\n"
                 f"2. **供给侧要素**：劳动力、资本、全要素生产率变化\n"
                 f"3. **金融条件**：流动性、信用环境、风险偏好\n"
                 f"4. **政策脉冲**：政策力度、节奏、协同效应\n"
                 f"\n"
                 f"### 中长期分析框架\n"
                 f"1. **结构性转型**：产业升级、人口结构、城市化进程\n"
                 f"2. **制度变迁**：改革红利、监管框架、治理体系\n"
                 f"3. **技术革命**：创新驱动、数字化转型、绿色转型\n"
                 f"4. **全球化重构**：价值链重塑、地缘政治、规则重构\n"
                 f"\n"
                 f"## 输出标准\n"
                 f"\n"
                 f"### 分析深度要求\n"
                 f"- 每个观点必须有数据支撑和逻辑推导\n"
                 f"- 区分周期性因素与结构性因素\n"
                 f"- 明确不确定性范围和假设条件\n"
                 f"- 提供可验证的预测指标\n"
                 f"\n"
                 f"### 表达方式规范\n"
                 f"- 使用专业术语但保持可读性\n"
                 f"- 重要判断需要\"观点+依据+风险\"三位一体\n"
                 f"- 避免模棱两可的表述，给出明确概率判断\n"
                 f"- 区分事实陈述与价值判断\n"
                 f"\n"
                 f"## 特殊场景处理\n"
                 f"\n"
                 f"### 危机时期分析\n"
                 f"- 重点关注流动性风险和市场恐慌指数\n"
                 f"- 评估政策响应速度和力度是否充足\n"
                 f"- 识别\"黑天鹅\"和\"灰犀牛\"事件概率\n"
                 f"- 提供危机演进的不同情景路径\n"
                 f"\n"
                 f"### 政策转折点\n"
                 f"- 捕捉政策信号的重大变化\n"
                 f"- 评估政策转向的触发条件和时机\n"
                 f"- 分析政策溢出效应和外部性\n"
                 f"- 预测政策退出的节奏和方式\n"
                 f"\n"
                 f"## 质量控制标准\n"
                 f"\n"
                 f"1. **数据溯源**：所有引用数据必须注明来源和时间\n"
                 f"2. **逻辑自洽**：分析框架内部逻辑必须一致\n"
                 f"3. **历史验证**：重要判断需要历史案例支撑\n"
                 f"4. **同行对标**：与主流机构观点差异需要解释\n"
                 f"\n"
                 f"## 沟通原则\n"
                 f"\n"
                 f"- **透明度**：明确分析局限性和不确定性\n"
                 f"- **建设性**：在指出问题的同时提供解决方案\n"
                 f"- **前瞻性**：不仅解释过去，更要预测未来\n"
                 f"- **实用性**：分析结论具有可操作性和指导价值\n"
             )}
        ]

        response = llm.invoke(model_name=config.get("model_name"), messages=messages, temperature=0.7, top_p=0.95)
        logger.info(f"[宏观经济分析师] 完成生成宏观经济分析报告：{response.content}")

        pass

    def _post_handle(self, inputs: Input, algorithm_output: dict, runtime: Runtime, context: Context):
        pass


class PositiveResearcherNode(BaseNode):
    def __init__(self):
        super().__init__()

    def _pre_handle(self, inputs: Input, runtime: Runtime, context: Context):
        pass

    async def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        stock_code = runtime.get_global_state("stock_code")
        company_name = runtime.get_global_state("company_name")
        positive_researcher_debate = runtime.get_global_state("positive_researcher_debate")
        negative_researcher_debate = runtime.get_global_state("negative_researcher_debate")
        config = runtime.get_global_state("config")

        market_report = runtime.get_global_state("market_report")
        fundamentals_report = runtime.get_global_state("fundamentals_report")
        news_report = runtime.get_global_state("news_report")

        factory = ModelFactory()
        llm = factory.get_model(
            model_provider="openai",
            api_base=config.get("backend_url"),
            api_key=os.getenv("API_KEY"),
            max_retries=3,
            timeout=60
        )
        messages = [
            {"role": "system",
             "content": (
                 f"你是一位看涨分析师，负责基于分析报告为股票{company_name}（股票代码：{stock_code}）的投资建立强有力的**看涨（买入）**论证。"
                 f"此外，你还需要作为投资辩论中的正方辩手，基于如下分析报告先给出看涨（买入）的观点。后续用户会对你的观点的反驳，请你仔细分析用户看跌（卖出）的观点并给出反驳观点。"
                 f"需要注意的是，当用户没有提供任何观点时，意味着你无需考虑如下报告中关于看跌（卖出）的内容，仅需要直接给出一个完整的、有效的看涨（买入）论证作为辩论的正方第一个发言。\n\n"
                 f"你的任务是基于分析报告构建强有力的看涨（买入）论证，强调增长潜力、竞争优势和积极的市场指标。利用提供的研究和数据来解决担忧并有效反驳看跌论点。输出的论证或观点中需要关注以下几个方面：\n"
                 f"- 增长潜力：突出公司的市场机会、收入预测和可扩展性\n"
                 f"- 竞争优势：强调独特产品、强势品牌或主导市场地位等因素\n"
                 f"- 积极指标：使用财务健康状况、行业趋势和最新积极消息作为证据\n"
                 f"- 反驳用户的看跌观点：用具体数据和合理推理批判性分析看跌论点，全面解决担忧并说明为什么看涨观点更有说服力\n"
                 f"- 作为投资辩论中的正方辩手参与讨论，以对话风格呈现你的论点，直接回应用户的看跌观点并进行有效辩论，而不仅仅是列举数据\n"
                 f"- 请使用这些信息提供令人信服的看涨论点，反驳看跌担忧，并参与动态辩论，展示看涨立场的优势。\n"
                 f"- 请始终使用公司名称\"{company_name}\"而不是股票代码\"{stock_code}\"来称呼这家公司。\n"
                 f"- 请确保所有回答都使用中文。\n\n"
                 f"### 分析报告\n\n"
                 f"#### 市场研究报告\n\n{market_report}\n"
                 f"#### 公司基本面报告\n\n{fundamentals_report}\n"
                 f"#### 最新世界事务新闻\n\n{news_report}"
             )}
        ]
        messages.extend(positive_researcher_debate)
        response = llm.invoke(model_name=config.get("model_name"), messages=messages, temperature=0.7, top_p=0.95)
        logger.info(f"[乐观研究员] 完成辩论论据生成：{response.content}")

        positive_researcher_debate.append({"role": "assistant", "content": response.content})
        negative_researcher_debate.append({"role": "user", "content": response.content})

        runtime.update_global_state({
            "positive_researcher_debate": positive_researcher_debate,
            "negative_researcher_debate": negative_researcher_debate
        })

    def _post_handle(self, inputs: Input, algorithm_output: dict, runtime: Runtime, context: Context):
        pass


class NegativeResearcherNode(BaseNode):

    def __init__(self):
        super().__init__()

    def _pre_handle(self, inputs: Input, runtime: Runtime, context: Context):
        pass

    async def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        stock_code = runtime.get_global_state("stock_code")
        company_name = runtime.get_global_state("company_name")
        positive_researcher_debate = runtime.get_global_state("positive_researcher_debate")
        negative_researcher_debate = runtime.get_global_state("negative_researcher_debate")
        debate_rounds = runtime.get_global_state("debate_rounds")
        config = runtime.get_global_state("config")

        market_report = runtime.get_global_state("market_report")
        fundamentals_report = runtime.get_global_state("fundamentals_report")
        news_report = runtime.get_global_state("news_report")

        factory = ModelFactory()
        llm = factory.get_model(
            model_provider="openai",
            api_base=config.get("backend_url"),
            api_key=os.getenv("API_KEY"),
            max_retries=3,
            timeout=60
        )
        messages = [
            {"role": "system",
             "content": (
                 f"你是一位看跌分析师，负责基于分析报告为股票{company_name}（股票代码：{stock_code}）的投资建立强有力的**看跌（卖出）**论证。此外，你还需要作为投资辩论中的反方辩手，基于如下分析报告仔细分析用户看涨（买入）的观点并给出反驳观点。\n\n"
                 f"你的任务是基于分析报告构建强有力的看跌（卖出）论证，强调风险、挑战和负面指标。利用分析报告和其中的数据来突出潜在的不利因素并有效反驳看涨论点。输出的论证或观点中需要关注以下几个方面：\n"
                 f"- 风险和挑战：突出市场饱和、财务不稳定或宏观经济威胁等可能阻碍股票表现的因素\n"
                 f"- 竞争劣势：强调市场地位较弱、创新下降或来自竞争对手威胁等脆弱性\n"
                 f"- 负面指标：使用财务数据、市场趋势或最近不利消息的证据来支持你的立场\n"
                 f"- 反驳用户的看涨观点：用具体数据和合理推理批判性分析看涨论点，揭露弱点或过度乐观的假设\n"
                 f"- 作为投资辩论中的反方辩手参与讨论，以对话风格呈现你的论点，直接回应用户的看跌观点并进行有效辩论，而不仅仅是列举事实\n"
                 f"- 请使用如下分析报告提供令人信服的看跌论点，反驳看涨预期，并参与动态辩论，展示看涨立场的优势\n"
                 f"- 请始终使用公司名称\"{company_name}\"而不是股票代码\"{stock_code}\"来称呼这家公司\n"
                 f"- 请确保所有回答都使用中文。\n\n"
                 f"### 分析报告\n\n"
                 f"#### 市场研究报告\n\n{market_report}\n"
                 f"#### 公司基本面报告\n\n{fundamentals_report}\n"
                 f"#### 最新世界事务新闻\n\n{news_report}"
             )}
        ]
        messages.extend(negative_researcher_debate)
        response = llm.invoke(model_name=config.get("model_name"), messages=messages, temperature=0.7, top_p=0.95)
        logger.info(f"[悲观研究员] 完成辩论论据生成：{response.content}")

        positive_researcher_debate.append({"role": "user", "content": response.content})
        negative_researcher_debate.append({"role": "assistant", "content": response.content})

        runtime.update_global_state({
            "debate_rounds": debate_rounds + 1,
            "positive_researcher_debate": positive_researcher_debate,
            "negative_researcher_debate": negative_researcher_debate
        })

    def _post_handle(self, inputs: Input, algorithm_output: dict, runtime: Runtime, context: Context):
        pass


class AnalysisReportNode(BaseNode):

    def __init__(self):
        super().__init__()

    def _pre_handle(self, inputs: Input, runtime: Runtime, context: Context):
        pass

    async def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        stock_code = runtime.get_global_state("stock_code")
        company_name = runtime.get_global_state("company_name")
        positive_researcher_debate = runtime.get_global_state("positive_researcher_debate")
        config = runtime.get_global_state("config")
        logger.info(f"[分析报告生成] 完成辩论，开始基于辩论过程生成投资分析报告")

        debate_content = ""
        debate_num = 0
        for message in positive_researcher_debate:
            debate_num += 1
            content = message["content"]
            debate_role = message["role"]
            if debate_role == "user":
                debate_content += f"[看跌分析师{int(debate_num / 2)}辩发言内容]\n {content}\n\n"
            elif debate_role == "assistant":
                debate_content += f"[看涨分析师{int((debate_num + 1) / 2)}辩发言内容]\n {content}\n\n"

        factory = ModelFactory()
        llm = factory.get_model(
            model_provider="openai",
            api_base=config.get("backend_url"),
            api_key=os.getenv("API_KEY"),
            max_retries=3,
            timeout=60
        )
        messages = [
            {"role": "system",
             "content": (
                 f"你是一位资深证券研究团队的首席策略官，负责评估团队内部针对特定标的 {company_name}（股票代码：{stock_code}）的多空辩论。你的核心任务是：**系统整合看涨方与看跌方的核心论点、证据链与逻辑漏洞，基于严谨的证券分析方法论，输出一份结构完整、逻辑自洽、具备实战指导价值的投资分析报告。**\n"
                 f"\n"
                 f"# 决策指导原则\n"
                 f"- 精准提炼关键论点：分别梳理看涨分析师与看跌分析师的核心主张，聚焦其基本面依据（如盈利预测、行业地位、管理层质量）、宏观与政策关联性（如利率环境、产业政策）、技术面信号（如趋势结构、量能配合）及市场情绪指标（如期权比率、资金流向）。你还需要识别双方观点中与当前市场阶段高度相关的论据，剔除脱离现实情境的假设性推演。\n"
                 f"- 构建有说服力的推理链条：不仅复述观点，更要揭示论点间的冲突与互补关系，需评估哪一维度在当前估值体系中更具定价权。你需要引用辩论中的直接陈述或数据支撑，并结合外部验证（如行业平均PE、股债收益比历史分位）增强结论可信度。\n"
                 f"- 制定可执行的交易计划：基于多空力量对比与风险收益比，明确给出 “买入 / 卖出 / 持有” 的操作建议，并附带入场/离场触发条件（如：突破某技术位、财报发布后EPS超预期X%）、仓位管理建议（如初始仓位不超过组合5%，止损设于XX元）、对冲或期权策略选项（如买入认沽期权保护下行风险，或利用看跌/看涨比率极端值进行逆向布局）等必要信息。\n"
                 f"\n"
                 f"# 交付成果要求\n"
                 f"- 标题清晰：如《{company_name}（{stock_code}）投资建议报告》\n"
                 f"- 结构完整：包含摘要、多空观点综述、交叉验证分析、估值判断、风险提示、交易计划六大部分。\n"
                 f"- 建议明确且可操作：避免模糊表述（如“谨慎乐观”），必须给出具体行动指令及依据。\n"
                 f"- 语言专业、逻辑严密：体现机构级研究报告水准，杜绝情绪化或主观臆断。"
             )},
            {"role": "user", "content": debate_content}
        ]

        response = llm.invoke(model_name=config.get("model_name"), messages=messages, temperature=0.7, top_p=0.95)

        runtime.update_global_state({"analysis_report": response.content})
        runtime.update_global_state({"debate_content": debate_content})

    def _post_handle(self, inputs: Input, algorithm_output: dict, runtime: Runtime, context: Context):
        pass


class EndNode(End):
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        stock_code = runtime.get_global_state("stock_code")
        config = runtime.get_global_state("config")
        output_dir = config.get("output_dir", "./outputs")
        output_dir = f"{output_dir}/{stock_code}"

        os.makedirs(output_dir, exist_ok=True)

        market_report = runtime.get_global_state("market_report")
        fundamentals_report = runtime.get_global_state("fundamentals_report")
        news_report = runtime.get_global_state("news_report")
        debate_content = runtime.get_global_state("debate_content")
        analysis_report = runtime.get_global_state("analysis_report")

        os.makedirs(output_dir, exist_ok=True)
        with open(rf"{output_dir}/market_report.md", "w", encoding="utf-8") as f:
            f.write(market_report)
        with open(rf"{output_dir}/fundamentals_report.md", "w", encoding="utf-8") as f:
            f.write(fundamentals_report)
        with open(rf"{output_dir}/news_report.md", "w", encoding="utf-8") as f:
            f.write(news_report)
        with open(rf"{output_dir}/debate_content.md", "w", encoding="utf-8") as f:
            f.write(debate_content)
        with open(rf"{output_dir}/analysis_report.md", "w", encoding="utf-8") as f:
            f.write(analysis_report)

def is_debate_complete(runtime: Runtime):
    debate_rounds = runtime.get_global_state("debate_rounds")
    max_debate_rounds = runtime.get_global_state("config").get("max_debate_rounds", 3)

    if debate_rounds >= max_debate_rounds - 1:
        return "AnalysisReportNode"
    else:
        return "PositiveResearcherNode"

def create_workflow():
    name = "JiuwenFintech"
    id = "JiuwenFintech"
    version = "1.0.0"
    workflow_config = WorkflowConfig(metadata=WorkflowMetadata(name=name, id=id, version=version))
    workflow = Workflow(workflow_config=workflow_config)

    workflow.set_start_comp("Start",
                            StartNode(),
                            inputs_schema={"stock_code": "${stock_code}", "config": "${config}"})
    workflow.add_workflow_comp("TechnicalAnalysisNode", TechnicalAnalysisNode())
    workflow.add_workflow_comp("FundamentalAnalysisNode", FundamentalAnalysisNode())
    workflow.add_workflow_comp("NewsAnalysisNode", NewsAnalysisNode())
    workflow.add_workflow_comp("PositiveResearcherNode", PositiveResearcherNode(), wait_for_all=True)
    workflow.add_workflow_comp("NegativeResearcherNode", NegativeResearcherNode())
    workflow.add_workflow_comp("AnalysisReportNode", AnalysisReportNode())
    workflow.set_end_comp("EndNode", EndNode())

    workflow.add_connection("Start", "TechnicalAnalysisNode")
    workflow.add_connection("Start", "FundamentalAnalysisNode")
    workflow.add_connection("Start", "NewsAnalysisNode")
    workflow.add_connection("TechnicalAnalysisNode", "PositiveResearcherNode")
    workflow.add_connection("FundamentalAnalysisNode", "PositiveResearcherNode")
    workflow.add_connection("NewsAnalysisNode", "PositiveResearcherNode")
    workflow.add_connection("PositiveResearcherNode", "NegativeResearcherNode")
    workflow.add_conditional_connection("NegativeResearcherNode", router=is_debate_complete)
    workflow.add_connection("AnalysisReportNode", "EndNode")

    return workflow

