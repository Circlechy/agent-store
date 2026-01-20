import asyncio
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List, Union

import pandas as pd
from openjiuwen.core.common.logging import logger

from jiuwenfintech.config.providers_config import get_provider_config
from jiuwenfintech.data.providers.base_provider import BaseStockDataProvider

try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False
    ts = None


class TushareProvider(BaseStockDataProvider):
    """
    统一的Tushare数据提供器
    合并app层和tradingagents层的所有优势功能
    """
    
    def __init__(self):
        super().__init__("Tushare")
        self.api = None
        self.config = get_provider_config("tushare")
        self.token_source = None

        if not TUSHARE_AVAILABLE:
            self.logger.error(" Tushare库未安装，请运行: pip install tushare")

    def _get_token_from_database(self) -> Optional[str]:
        """
        从数据库读取 Tushare Token

        优先级：数据库配置 > 环境变量
        这样用户在 Web 后台修改配置后可以立即生效
        """
        try:
            self.logger.info(" [DB查询] 开始从数据库读取 Token...")
            from app.core.database import get_mongo_db_sync
            db = get_mongo_db_sync()
            config_collection = db.system_configs

            self.logger.info(" [DB查询] 查询 is_active=True 的配置...")
            config_data = config_collection.find_one(
                {"is_active": True},
                sort=[("version", -1)]
            )

            if config_data:
                self.logger.info(f" [DB查询] 找到激活配置，版本: {config_data.get('version')}")
                if config_data.get('data_source_configs'):
                    self.logger.info(f" [DB查询] 配置中有 {len(config_data['data_source_configs'])} 个数据源")
                    for ds_config in config_data['data_source_configs']:
                        ds_type = ds_config.get('type')
                        self.logger.info(f" [DB查询] 检查数据源: {ds_type}")
                        if ds_type == 'tushare':
                            api_key = ds_config.get('api_key')
                            self.logger.info(f" [DB查询] 找到 Tushare 配置，api_key 长度: {len(api_key) if api_key else 0}")
                            if api_key and not api_key.startswith("your_"):
                                self.logger.info(f" [DB查询] Token 有效 (长度: {len(api_key)})")
                                return api_key
                            else:
                                self.logger.warning(f" [DB查询] Token 无效或为占位符")
                else:
                    self.logger.warning(" [DB查询] 配置中没有 data_source_configs")
            else:
                self.logger.warning(" [DB查询] 未找到激活的配置")

            self.logger.info(" [DB查询] 数据库中未找到有效的 Tushare Token")
        except Exception as e:
            self.logger.error(f" [DB查询] 从数据库读取 Token 失败: {e}")
            import traceback
            self.logger.error(f" [DB查询] 堆栈跟踪:\n{traceback.format_exc()}")

        return None

    def connect_sync(self) -> bool:
        """同步连接到Tushare"""
        if not TUSHARE_AVAILABLE:
            self.logger.error(" Tushare库不可用")
            return False

        test_timeout = 10

        try:
            self.logger.info(" [步骤1] 开始从数据库读取 Tushare Token...")
            db_token = self._get_token_from_database()
            if db_token:
                self.logger.info(f" [步骤1] 数据库中找到 Token (长度: {len(db_token)})")
            else:
                self.logger.info(" [步骤1] 数据库中未找到 Token")

            self.logger.info(" [步骤2] 读取 .env 中的 Token...")
            env_token = self.config.get('token')
            if env_token:
                self.logger.info(f" [步骤2] .env 中找到 Token (长度: {len(env_token)})")
            else:
                self.logger.info(" [步骤2] .env 中未找到 Token")

            if db_token:
                try:
                    self.logger.info(f" [步骤3] 尝试使用数据库中的 Tushare Token (超时: {test_timeout}秒)...")
                    ts.set_token(db_token)
                    self.api = ts.pro_api()

                    try:
                        self.logger.info(" [步骤3.1] 调用 stock_basic API 测试连接...")
                        test_data = self.api.stock_basic(list_status='L', limit=1)
                        self.logger.info(f" [步骤3.1] API 调用成功，返回数据: {len(test_data) if test_data is not None else 0} 条")
                    except Exception as e:
                        self.logger.warning(f" [步骤3.1] 数据库 Token 测试失败: {e}，尝试降级到 .env 配置...")
                        test_data = None

                    if test_data is not None and not test_data.empty:
                        self.connected = True
                        self.token_source = 'database'
                        self.logger.info(f" [步骤3.2] Tushare连接成功 (Token来源: 数据库)")
                        return True
                    else:
                        self.logger.warning(" [步骤3.2] 数据库 Token 测试失败，尝试降级到 .env 配置...")
                except Exception as e:
                    self.logger.warning(f" [步骤3] 数据库 Token 连接失败: {e}，尝试降级到 .env 配置...")

            if env_token:
                try:
                    self.logger.info(f" [步骤4] 尝试使用 .env 中的 Tushare Token (超时: {test_timeout}秒)...")
                    ts.set_token(env_token)
                    self.api = ts.pro_api()

                    try:
                        self.logger.info(" [步骤4.1] 调用 stock_basic API 测试连接...")
                        test_data = self.api.stock_basic(list_status='L', limit=1)
                        self.logger.info(f" [步骤4.1] API 调用成功，返回数据: {len(test_data) if test_data is not None else 0} 条")
                    except Exception as e:
                        self.logger.error(f" [步骤4.1] .env Token 测试失败: {e}")
                        return False

                    if test_data is not None and not test_data.empty:
                        self.connected = True
                        self.token_source = 'env'
                        self.logger.info(f" [步骤4.2] Tushare连接成功 (Token来源: .env 环境变量)")
                        return True
                    else:
                        self.logger.error(" [步骤4.2] .env Token 测试失败")
                        return False
                except Exception as e:
                    self.logger.error(f" [步骤4] .env Token 连接失败: {e}")
                    return False

            self.logger.error(" [步骤5] Tushare token未配置，请在 Web 后台或 .env 文件中配置 TUSHARE_TOKEN")
            return False

        except Exception as e:
            self.logger.error(f" Tushare连接失败: {e}")
            return False

    async def connect(self) -> bool:
        """异步连接到Tushare"""
        if not TUSHARE_AVAILABLE:
            self.logger.error(" Tushare库不可用")
            return False

        test_timeout = 10

        try:
            db_token = self._get_token_from_database()
            env_token = self.config.get('token')

            if db_token:
                try:
                    self.logger.info(f" 尝试使用数据库中的 Tushare Token (超时: {test_timeout}秒)...")
                    ts.set_token(db_token)
                    self.api = ts.pro_api()

                    try:
                        test_data = await asyncio.wait_for(
                            asyncio.to_thread(
                                self.api.stock_basic,
                                list_status='L',
                                limit=1
                            ),
                            timeout=test_timeout
                        )
                    except asyncio.TimeoutError:
                        self.logger.warning(f" 数据库 Token 测试超时 ({test_timeout}秒)，尝试降级到 .env 配置...")
                        test_data = None

                    if test_data is not None and not test_data.empty:
                        self.connected = True
                        self.logger.info(f" Tushare连接成功 (Token来源: 数据库)")
                        return True
                    else:
                        self.logger.warning(" 数据库 Token 测试失败，尝试降级到 .env 配置...")
                except Exception as e:
                    self.logger.warning(f" 数据库 Token 连接失败: {e}，尝试降级到 .env 配置...")

            if env_token:
                try:
                    self.logger.info(f" 尝试使用 .env 中的 Tushare Token (超时: {test_timeout}秒)...")
                    ts.set_token(env_token)
                    self.api = ts.pro_api()

                    try:
                        test_data = await asyncio.wait_for(
                            asyncio.to_thread(
                                self.api.stock_basic,
                                list_status='L',
                                limit=1
                            ),
                            timeout=test_timeout
                        )
                    except asyncio.TimeoutError:
                        self.logger.error(f" .env Token 测试超时 ({test_timeout}秒)")
                        return False

                    if test_data is not None and not test_data.empty:
                        self.connected = True
                        self.logger.info(f" Tushare连接成功 (Token来源: .env 环境变量)")
                        return True
                    else:
                        self.logger.error(" .env Token 测试失败")
                        return False
                except Exception as e:
                    self.logger.error(f" .env Token 连接失败: {e}")
                    return False

            self.logger.error(" Tushare token未配置，请在 Web 后台或 .env 文件中配置 TUSHARE_TOKEN")
            return False

        except Exception as e:
            self.logger.error(f" Tushare连接失败: {e}")
            return False
    
    def is_available(self) -> bool:
        """检查Tushare是否可用"""
        return TUSHARE_AVAILABLE and self.connected and self.api is not None
    
    
    def get_stock_list_sync(self, market: str = None) -> Optional[pd.DataFrame]:
        """获取股票列表（同步版本）"""
        if not self.is_available():
            return None

        try:
            df = self.api.stock_basic(
                list_status='L',
                fields='ts_code,symbol,name,area,industry,market,exchange,list_date,is_hs'
            )
            if df is not None and not df.empty:
                self.logger.info(f" 成功获取 {len(df)} 条股票数据")
                return df
            else:
                self.logger.warning(" Tushare API 返回空数据")
                return None
        except Exception as e:
            self.logger.error(f" 获取股票列表失败: {e}")
            return None

    async def get_stock_list(self, market: str = None) -> Optional[List[Dict[str, Any]]]:
        """获取股票列表（异步版本）"""
        if not self.is_available():
            return None

        try:
            params = {
                'list_status': 'L',
                'fields': 'ts_code,symbol,name,area,industry,market,exchange,list_date,is_hs'
            }
            
            if market:
                if market == "CN":
                    params['exchange'] = 'SSE,SZSE'
                elif market == "HK":
                    return None
                elif market == "US":
                    return None
            
            df = await asyncio.to_thread(self.api.stock_basic, **params)
            
            if df is None or df.empty:
                return None
            
            stock_list = []
            for _, row in df.iterrows():
                stock_info = self.standardize_basic_info(row.to_dict())
                stock_list.append(stock_info)
            
            self.logger.info(f" 获取股票列表: {len(stock_list)}只")
            return stock_list
            
        except Exception as e:
            self.logger.error(f" 获取股票列表失败: {e}")
            return None
    
    async def get_stock_basic_info(self, symbol: str = None) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """获取股票基础信息"""
        if not self.is_available():
            return None
        
        try:
            if symbol:
                ts_code = self._normalize_ts_code(symbol)
                df = await asyncio.to_thread(
                    self.api.stock_basic,
                    ts_code=ts_code,
                    fields='ts_code,symbol,name,area,industry,market,exchange,list_date,is_hs,act_name,act_ent_type'
                )
                
                if df is None or df.empty:
                    return None
                
                return self.standardize_basic_info(df.iloc[0].to_dict())
            else:
                return await self.get_stock_list()
                
        except Exception as e:
            self.logger.error(f" 获取股票基础信息失败 symbol={symbol}: {e}")
            return None
    
    async def get_stock_quotes(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取单只股票实时行情

        🔥 策略：使用 daily 接口获取最新一天的数据（不使用 rt_k 批量接口）
        - rt_k 接口是批量接口，单只股票调用浪费配额
        - daily 接口可以获取单只股票的最新日线数据，包含更多指标

        注意：此方法适合少量股票获取，大量股票建议使用 get_realtime_quotes_batch()
        """
        if not self.is_available():
            return None

        try:
            ts_code = self._normalize_ts_code(symbol)

            from datetime import datetime, timedelta

            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=3)).strftime('%Y%m%d')

            df = await asyncio.to_thread(
                self.api.daily,
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )

            if df is not None and not df.empty:
                row = df.iloc[0].to_dict()

                quote_data = {
                    'ts_code': row.get('ts_code'),
                    'symbol': symbol,
                    'trade_date': row.get('trade_date'),
                    'open': row.get('open'),
                    'high': row.get('high'),
                    'low': row.get('low'),
                    'close': row.get('close'),
                    'pre_close': row.get('pre_close'),
                    'change': row.get('change'),
                    'pct_chg': row.get('pct_chg'),
                    'volume': row.get('vol'),
                    'amount': row.get('amount'),
                }

                return self.standardize_quotes(quote_data)

            return None

        except Exception as e:
            if self._is_rate_limit_error(str(e)):
                self.logger.error(f" 获取实时行情失败（限流） symbol={symbol}: {e}")
                raise

            self.logger.error(f" 获取实时行情失败 symbol={symbol}: {e}")
            return None

    async def get_realtime_quotes_batch(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        批量获取全市场实时行情
        使用 rt_k 接口的通配符功能，一次性获取所有A股实时行情

        Returns:
            Dict[str, Dict]: {symbol: quote_data}
            例如: {'000001': {'close': 10.5, 'pct_chg': 1.2, ...}, ...}
        """
        if not self.is_available():
            return None

        try:
            df = await asyncio.to_thread(
                self.api.rt_k,
                ts_code='3*.SZ,6*.SH,0*.SZ,9*.BJ'
            )

            if df is None or df.empty:
                self.logger.warning(" rt_k 接口返回空数据")
                return None

            self.logger.info(f" 获取到 {len(df)} 只股票的实时行情")

            from datetime import datetime, timezone, timedelta
            cn_tz = timezone(timedelta(hours=8))
            now_cn = datetime.now(cn_tz)
            trade_date = now_cn.strftime("%Y%m%d")

            result = {}
            for _, row in df.iterrows():
                ts_code = row.get('ts_code')
                if not ts_code or '.' not in ts_code:
                    continue

                symbol = ts_code.split('.')[0]

                quote_data = {
                    'ts_code': ts_code,
                    'symbol': symbol,
                    'name': row.get('name'),
                    'open': row.get('open'),
                    'high': row.get('high'),
                    'low': row.get('low'),
                    'close': row.get('close'),
                    'pre_close': row.get('pre_close'),
                    'volume': row.get('vol'),
                    'amount': row.get('amount'),
                    'num': row.get('num'),
                    'trade_date': trade_date,
                }

                if quote_data.get('close') and quote_data.get('pre_close'):
                    try:
                        close = float(quote_data['close'])
                        pre_close = float(quote_data['pre_close'])
                        if pre_close > 0:
                            pct_chg = ((close - pre_close) / pre_close) * 100
                            quote_data['pct_chg'] = round(pct_chg, 2)
                            quote_data['change'] = round(close - pre_close, 2)
                    except (ValueError, TypeError):
                        pass

                result[symbol] = quote_data

            return result

        except Exception as e:
            if self._is_rate_limit_error(str(e)):
                self.logger.error(f" 批量获取实时行情失败（限流）: {e}")
                raise

            self.logger.error(f" 批量获取实时行情失败: {e}")
            return None

    def _is_rate_limit_error(self, error_msg: str) -> bool:
        """检测是否为 API 限流错误"""
        rate_limit_keywords = [
            "每分钟最多访问",
            "每分钟最多",
            "rate limit",
            "too many requests",
            "访问频率",
            "请求过于频繁"
        ]
        error_msg_lower = error_msg.lower()
        return any(keyword in error_msg_lower for keyword in rate_limit_keywords)
    
    async def get_historical_data(
        self,
        symbol: str,
        start_date: Union[str, date],
        end_date: Union[str, date] = None,
        period: str = "daily"
    ) -> Optional[pd.DataFrame]:
        """
        获取历史数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 数据周期 (daily/weekly/monthly)
        """
        if not self.is_available():
            return None

        try:
            ts_code = self._normalize_ts_code(symbol)

            start_str = self._format_date(start_date)
            end_str = self._format_date(end_date) if end_date else datetime.now().strftime('%Y%m%d')


            freq_map = {
                "daily": "D",
                "weekly": "W",
                "monthly": "M"
            }
            freq = freq_map.get(period, "D")

            df = await asyncio.to_thread(
                ts.pro_bar,
                ts_code=ts_code,
                api=self.api,
                start_date=start_str,
                end_date=end_str,
                freq=freq,
                adj='qfq'
            )

            if df is None or df.empty:
                self.logger.warning(
                    f" Tushare API 返回空数据: symbol={symbol}, ts_code={ts_code}, "
                    f"period={period}, start={start_str}, end={end_str}"
                )
                self.logger.warning(
                    f"可能原因: "
                    f"1) 该股票在此期间无交易数据 "
                    f"2) 日期范围不正确 "
                    f"3) 股票代码格式错误 "
                    f"4) Tushare API 限制或积分不足"
                )
                return None

            df = self._standardize_historical_data(df)

            self.logger.info(f" 获取{period}历史数据: {symbol} {len(df)}条记录 (前复权 qfq)")
            return df
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.logger.error(
                f" 获取历史数据失败 symbol={symbol}, period={period}\n"
                f"   参数: ts_code={ts_code if 'ts_code' in locals() else 'N/A'}, "
                f"start={start_str if 'start_str' in locals() else 'N/A'}, "
                f"end={end_str if 'end_str' in locals() else 'N/A'}\n"
                f"   错误类型: {type(e).__name__}\n"
                f"   错误信息: {str(e)}\n"
                f"   堆栈跟踪:\n{error_details}"
            )
            return None
    
    
    async def get_daily_basic(self, trade_date: str) -> Optional[pd.DataFrame]:
        """获取每日基础财务数据"""
        if not self.is_available():
            return None
        
        try:
            date_str = trade_date.replace('-', '')
            df = await asyncio.to_thread(
                self.api.daily_basic,
                trade_date=date_str,
                fields='ts_code,total_mv,circ_mv,pe,pb,turnover_rate,volume_ratio,pe_ttm,pb_mrq'
            )
            
            if df is not None and not df.empty:
                self.logger.info(f" 获取每日基础数据: {trade_date} {len(df)}条记录")
                return df
            
            return None
            
        except Exception as e:
            self.logger.error(f" 获取每日基础数据失败 trade_date={trade_date}: {e}")
            return None
    
    async def find_latest_trade_date(self) -> Optional[str]:
        """查找最新交易日期"""
        if not self.is_available():
            return None
        
        try:
            today = datetime.now()
            for delta in range(0, 10):
                check_date = (today - timedelta(days=delta)).strftime('%Y%m%d')
                
                try:
                    df = await asyncio.to_thread(
                        self.api.daily_basic,
                        trade_date=check_date,
                        fields='ts_code',
                        limit=1
                    )
                    
                    if df is not None and not df.empty:
                        formatted_date = f"{check_date[:4]}-{check_date[4:6]}-{check_date[6:8]}"
                        self.logger.info(f" 找到最新交易日期: {formatted_date}")
                        return formatted_date
                        
                except Exception:
                    continue
            
            return None
            
        except Exception as e:
            self.logger.error(f" 查找最新交易日期失败: {e}")
            return None
    
    async def get_financial_data(self, symbol: str, report_type: str = "quarterly",
                                period: str = None, limit: int = 4) -> Optional[Dict[str, Any]]:
        """
        获取财务数据

        Args:
            symbol: 股票代码
            report_type: 报告类型 (quarterly/annual)
            period: 指定报告期 (YYYYMMDD格式)，为空则获取最新数据
            limit: 获取记录数量，默认4条（最近4个季度）

        Returns:
            财务数据字典，包含利润表、资产负债表、现金流量表和财务指标
        """
        if not self.is_available():
            return None

        try:
            ts_code = self._normalize_ts_code(symbol)
            self.logger.debug(f" 获取Tushare财务数据: {ts_code}, 类型: {report_type}")

            query_params = {
                'ts_code': ts_code,
                'limit': limit
            }

            if period:
                query_params['period'] = period

            financial_data = {}

            try:
                income_df = await asyncio.to_thread(
                    self.api.income,
                    **query_params
                )
                if income_df is not None and not income_df.empty:
                    financial_data['income_statement'] = income_df.to_dict('records')
                    self.logger.debug(f" {ts_code} 利润表数据获取成功: {len(income_df)} 条记录")
                else:
                    self.logger.debug(f" {ts_code} 利润表数据为空")
            except Exception as e:
                self.logger.warning(f" 获取{ts_code}利润表数据失败: {e}")

            try:
                balance_df = await asyncio.to_thread(
                    self.api.balancesheet,
                    **query_params
                )
                if balance_df is not None and not balance_df.empty:
                    financial_data['balance_sheet'] = balance_df.to_dict('records')
                    self.logger.debug(f" {ts_code} 资产负债表数据获取成功: {len(balance_df)} 条记录")
                else:
                    self.logger.debug(f" {ts_code} 资产负债表数据为空")
            except Exception as e:
                self.logger.warning(f" 获取{ts_code}资产负债表数据失败: {e}")

            try:
                cashflow_df = await asyncio.to_thread(
                    self.api.cashflow,
                    **query_params
                )
                if cashflow_df is not None and not cashflow_df.empty:
                    financial_data['cashflow_statement'] = cashflow_df.to_dict('records')
                    self.logger.debug(f" {ts_code} 现金流量表数据获取成功: {len(cashflow_df)} 条记录")
                else:
                    self.logger.debug(f" {ts_code} 现金流量表数据为空")
            except Exception as e:
                self.logger.warning(f" 获取{ts_code}现金流量表数据失败: {e}")

            try:
                indicator_df = await asyncio.to_thread(
                    self.api.fina_indicator,
                    **query_params
                )
                if indicator_df is not None and not indicator_df.empty:
                    financial_data['financial_indicators'] = indicator_df.to_dict('records')
                    self.logger.debug(f" {ts_code} 财务指标数据获取成功: {len(indicator_df)} 条记录")
                else:
                    self.logger.debug(f" {ts_code} 财务指标数据为空")
            except Exception as e:
                self.logger.warning(f" 获取{ts_code}财务指标数据失败: {e}")

            try:
                mainbz_df = await asyncio.to_thread(
                    self.api.fina_mainbz,
                    **query_params
                )
                if mainbz_df is not None and not mainbz_df.empty:
                    financial_data['main_business'] = mainbz_df.to_dict('records')
                    self.logger.debug(f" {ts_code} 主营业务构成数据获取成功: {len(mainbz_df)} 条记录")
                else:
                    self.logger.debug(f" {ts_code} 主营业务构成数据为空")
            except Exception as e:
                self.logger.debug(f"获取{ts_code}主营业务构成数据失败: {e}")

            if financial_data:
                standardized_data = self._standardize_tushare_financial_data(financial_data, ts_code)
                self.logger.info(f" {ts_code} Tushare财务数据获取完成: {len(financial_data)} 个数据集")
                return standardized_data
            else:
                self.logger.warning(f" {ts_code} 未获取到任何Tushare财务数据")
                return None

        except Exception as e:
            self.logger.error(f" 获取Tushare财务数据失败 symbol={symbol}: {e}")
            return None

    async def get_stock_news(self, symbol: str = None, limit: int = 10,
                           hours_back: int = 24, src: str = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取股票新闻（需要Tushare新闻权限）

        Args:
            symbol: 股票代码，为None时获取市场新闻
            limit: 返回数量限制
            hours_back: 回溯小时数，默认24小时
            src: 新闻源，默认自动选择

        Returns:
            新闻列表
        """
        if not self.is_available():
            return None

        try:
            from datetime import datetime, timedelta

            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours_back)

            start_date = start_time.strftime('%Y-%m-%d %H:%M:%S')
            end_date = end_time.strftime('%Y-%m-%d %H:%M:%S')

            self.logger.debug(f" 获取Tushare新闻: symbol={symbol}, 时间范围={start_date} 到 {end_date}")

            news_sources = [
                'sina',
                'eastmoney',
                '10jqka',
                'wallstreetcn',
                'cls',
                'yicai',
                'jinrongjie',
                'yuncaijing',
                'fenghuang'
            ]

            if src and src in news_sources:
                sources_to_try = [src]
            else:
                sources_to_try = news_sources[:3]

            all_news = []

            for source in sources_to_try:
                try:
                    self.logger.debug(f" 尝试从 {source} 获取新闻...")

                    news_df = await asyncio.to_thread(
                        self.api.news,
                        src=source,
                        start_date=start_date,
                        end_date=end_date
                    )

                    if news_df is not None and not news_df.empty:
                        source_news = self._process_tushare_news(news_df, source, symbol, limit)
                        all_news.extend(source_news)

                        self.logger.info(f" 从 {source} 获取到 {len(source_news)} 条新闻")

                        if len(all_news) >= limit:
                            break
                    else:
                        self.logger.debug(f" {source} 未返回新闻数据")

                except Exception as e:
                    self.logger.debug(f"从 {source} 获取新闻失败: {e}")
                    continue

                await asyncio.sleep(0.2)

            if all_news:
                unique_news = self._deduplicate_news(all_news)
                sorted_news = sorted(unique_news, key=lambda x: x.get('publish_time', datetime.min), reverse=True)

                final_news = sorted_news[:limit]

                self.logger.info(f" Tushare新闻获取成功: {len(final_news)} 条（去重后）")
                return final_news
            else:
                self.logger.warning(" 未获取到任何Tushare新闻数据")
                return []

        except Exception as e:
            if any(keyword in str(e).lower() for keyword in ['权限', 'permission', 'unauthorized', 'access denied']):
                self.logger.warning(f" Tushare新闻接口需要单独开通权限（付费功能）: {e}")
            elif "积分" in str(e) or "point" in str(e).lower():
                self.logger.warning(f" Tushare积分不足，无法获取新闻数据: {e}")
            else:
                self.logger.error(f" 获取Tushare新闻失败: {e}")
            return None

    def _process_tushare_news(self, news_df: pd.DataFrame, source: str,
                            symbol: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """处理Tushare新闻数据"""
        news_list = []

        df_limited = news_df.head(limit * 2)

        for _, row in df_limited.iterrows():
            news_item = {
                "title": str(row.get('title', '') or row.get('content', '')[:50] + '...'),
                "content": str(row.get('content', '')),
                "summary": self._generate_summary(row.get('content', '')),
                "url": "",
                "source": self._get_source_name(source),
                "author": "",
                "publish_time": self._parse_tushare_news_time(row.get('datetime', '')),
                "category": self._classify_tushare_news(row.get('channels', ''), row.get('content', '')),
                "sentiment": self._analyze_news_sentiment(row.get('content', ''), row.get('title', '')),
                "importance": self._assess_news_importance(row.get('content', ''), row.get('title', '')),
                "keywords": self._extract_keywords(row.get('content', ''), row.get('title', '')),
                "data_source": "tushare",
                "original_source": source
            }

            if symbol:
                if self._is_news_relevant_to_symbol(news_item, symbol):
                    news_list.append(news_item)
            else:
                news_list.append(news_item)

        return news_list

    def _get_source_name(self, source_code: str) -> str:
        """获取新闻源中文名称"""
        source_names = {
            'sina': '新浪财经',
            'eastmoney': '东方财富',
            '10jqka': '同花顺',
            'wallstreetcn': '华尔街见闻',
            'cls': '财联社',
            'yicai': '第一财经',
            'jinrongjie': '金融界',
            'yuncaijing': '云财经',
            'fenghuang': '凤凰新闻'
        }
        return source_names.get(source_code, source_code)

    def _generate_summary(self, content: str) -> str:
        """生成新闻摘要"""
        if not content:
            return ""

        content_str = str(content)
        if len(content_str) <= 200:
            return content_str

        return content_str[:200] + "..."

    def _is_news_relevant_to_symbol(self, news_item: Dict[str, Any], symbol: str) -> bool:
        """判断新闻是否与股票相关"""
        content = news_item.get("content", "").lower()
        title = news_item.get("title", "").lower()

        symbol_clean = symbol.replace('.SH', '').replace('.SZ', '').zfill(6)

        return any([
            symbol_clean in content,
            symbol_clean in title,
            symbol in content,
            symbol in title
        ])

    def _deduplicate_news(self, news_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """新闻去重"""
        seen_titles = set()
        unique_news = []

        for news in news_list:
            title = news.get('title', '')
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_news.append(news)

        return unique_news

    def _analyze_news_sentiment(self, content: str, title: str) -> str:
        """分析新闻情绪"""
        text = f"{title} {content}".lower()

        positive_keywords = ['利好', '上涨', '增长', '盈利', '突破', '创新高', '买入', '推荐']
        negative_keywords = ['利空', '下跌', '亏损', '风险', '暴跌', '卖出', '警告', '下调']

        positive_count = sum(1 for keyword in positive_keywords if keyword in text)
        negative_count = sum(1 for keyword in negative_keywords if keyword in text)

        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'

    def _assess_news_importance(self, content: str, title: str) -> str:
        """评估新闻重要性"""
        text = f"{title} {content}".lower()

        high_importance_keywords = ['业绩', '财报', '重大', '公告', '监管', '政策', '并购', '重组']
        medium_importance_keywords = ['分析', '预测', '观点', '建议', '行业', '市场']

        if any(keyword in text for keyword in high_importance_keywords):
            return 'high'
        elif any(keyword in text for keyword in medium_importance_keywords):
            return 'medium'
        else:
            return 'low'

    def _extract_keywords(self, content: str, title: str) -> List[str]:
        """提取关键词"""
        text = f"{title} {content}"

        keywords = []
        common_keywords = ['股票', '公司', '市场', '投资', '业绩', '财报', '政策', '行业', '分析', '预测']

        for keyword in common_keywords:
            if keyword in text:
                keywords.append(keyword)

        return keywords[:5]

    def _parse_tushare_news_time(self, time_str: str) -> Optional[datetime]:
        """解析Tushare新闻时间"""
        if not time_str:
            return datetime.utcnow()

        try:
            return datetime.strptime(str(time_str), '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            self.logger.debug(f"解析Tushare新闻时间失败: {e}")
            return datetime.utcnow()

    def _classify_tushare_news(self, channels: str, content: str) -> str:
        """分类Tushare新闻"""
        channels = str(channels).lower()
        content = str(content).lower()

        if any(keyword in channels or keyword in content for keyword in ['公告', '业绩', '财报']):
            return 'company_announcement'
        elif any(keyword in channels or keyword in content for keyword in ['政策', '监管', '央行']):
            return 'policy_news'
        elif any(keyword in channels or keyword in content for keyword in ['行业', '板块']):
            return 'industry_news'
        elif any(keyword in channels or keyword in content for keyword in ['市场', '指数', '大盘']):
            return 'market_news'
        else:
            return 'other'

    async def get_financial_data_by_period(self, symbol: str, start_period: str = None,
                                         end_period: str = None, report_type: str = "quarterly") -> Optional[List[Dict[str, Any]]]:
        """
        按时间范围获取财务数据

        Args:
            symbol: 股票代码
            start_period: 开始报告期 (YYYYMMDD)
            end_period: 结束报告期 (YYYYMMDD)
            report_type: 报告类型 (quarterly/annual)

        Returns:
            财务数据列表，按报告期倒序排列
        """
        if not self.is_available():
            return None

        try:
            ts_code = self._normalize_ts_code(symbol)
            self.logger.debug(f" 按期间获取Tushare财务数据: {ts_code}, {start_period} - {end_period}")

            query_params = {'ts_code': ts_code}

            if start_period:
                query_params['start_date'] = start_period
            if end_period:
                query_params['end_date'] = end_period

            income_df = await asyncio.to_thread(
                self.api.income,
                **query_params
            )

            if income_df is None or income_df.empty:
                self.logger.warning(f" {ts_code} 指定期间无财务数据")
                return None

            financial_data_list = []

            for _, income_row in income_df.iterrows():
                period = income_row['end_date']

                period_data = await self.get_financial_data(
                    symbol=symbol,
                    period=period,
                    limit=1
                )

                if period_data:
                    financial_data_list.append(period_data)

                await asyncio.sleep(0.1)

            self.logger.info(f" {ts_code} 按期间获取财务数据完成: {len(financial_data_list)} 个报告期")
            return financial_data_list

        except Exception as e:
            self.logger.error(f" 按期间获取Tushare财务数据失败 symbol={symbol}: {e}")
            return None

    async def get_financial_indicators_only(self, symbol: str, limit: int = 4) -> Optional[Dict[str, Any]]:
        """
        仅获取财务指标数据（轻量级接口）

        Args:
            symbol: 股票代码
            limit: 获取记录数量

        Returns:
            财务指标数据
        """
        if not self.is_available():
            return None

        try:
            ts_code = self._normalize_ts_code(symbol)

            indicator_df = await asyncio.to_thread(
                self.api.fina_indicator,
                ts_code=ts_code,
                limit=limit
            )

            if indicator_df is not None and not indicator_df.empty:
                indicators = indicator_df.to_dict('records')

                return {
                    "symbol": symbol,
                    "ts_code": ts_code,
                    "financial_indicators": indicators,
                    "data_source": "tushare",
                    "updated_at": datetime.utcnow()
                }

            return None

        except Exception as e:
            self.logger.error(f" 获取Tushare财务指标失败 symbol={symbol}: {e}")
            return None


    def standardize_basic_info(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """标准化股票基础信息"""
        ts_code = raw_data.get('ts_code', '')
        symbol = raw_data.get('symbol', ts_code.split('.')[0] if '.' in ts_code else ts_code)

        return {
            "code": symbol,
            "name": raw_data.get('name', ''),
            "symbol": symbol,
            "full_symbol": ts_code,

            "market_info": self._determine_market_info_from_ts_code(ts_code),

            "area": self._safe_str(raw_data.get('area')),
            "industry": self._safe_str(raw_data.get('industry')),
            "market": raw_data.get('market'),
            "list_date": self._format_date_output(raw_data.get('list_date')),

            "is_hs": raw_data.get('is_hs'),

            "act_name": raw_data.get('act_name'),
            "act_ent_type": raw_data.get('act_ent_type'),

            "data_source": "tushare",
            "data_version": 1,
            "updated_at": datetime.utcnow()
        }

    def standardize_quotes(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """标准化实时行情数据"""
        ts_code = raw_data.get('ts_code', '')
        symbol = ts_code.split('.')[0] if '.' in ts_code else ts_code

        return {
            "code": symbol,
            "symbol": symbol,
            "full_symbol": ts_code,
            "market": self._determine_market(ts_code),

            "close": self._convert_to_float(raw_data.get('close')),
            "current_price": self._convert_to_float(raw_data.get('close')),
            "open": self._convert_to_float(raw_data.get('open')),
            "high": self._convert_to_float(raw_data.get('high')),
            "low": self._convert_to_float(raw_data.get('low')),
            "pre_close": self._convert_to_float(raw_data.get('pre_close')),

            "change": self._convert_to_float(raw_data.get('change')),
            "pct_chg": self._convert_to_float(raw_data.get('pct_chg')),

            "volume": self._convert_to_float(raw_data.get('vol')) * 100 if raw_data.get('vol') else None,
            "amount": self._convert_to_float(raw_data.get('amount')) * 1000 if raw_data.get('amount') else None,

            "total_mv": self._convert_to_float(raw_data.get('total_mv')),
            "circ_mv": self._convert_to_float(raw_data.get('circ_mv')),
            "pe": self._convert_to_float(raw_data.get('pe')),
            "pb": self._convert_to_float(raw_data.get('pb')),
            "turnover_rate": self._convert_to_float(raw_data.get('turnover_rate')),

            "trade_date": self._format_date_output(raw_data.get('trade_date')),
            "timestamp": datetime.utcnow(),

            "data_source": "tushare",
            "data_version": 1,
            "updated_at": datetime.utcnow()
        }


    def _normalize_ts_code(self, symbol: str) -> str:
        """标准化为Tushare的ts_code格式"""
        if '.' in symbol:
            return symbol

        if symbol.isdigit() and len(symbol) == 6:
            if symbol.startswith(('60', '68', '90')):
                return f"{symbol}.SH"
            else:
                return f"{symbol}.SZ"

        return symbol

    def _determine_market_info_from_ts_code(self, ts_code: str) -> Dict[str, Any]:
        """根据ts_code确定市场信息"""
        if '.SH' in ts_code:
            return {
                "market": "CN",
                "exchange": "SSE",
                "exchange_name": "上海证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai"
            }
        elif '.SZ' in ts_code:
            return {
                "market": "CN",
                "exchange": "SZSE",
                "exchange_name": "深圳证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai"
            }
        elif '.BJ' in ts_code:
            return {
                "market": "CN",
                "exchange": "BSE",
                "exchange_name": "北京证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai"
            }
        else:
            return {
                "market": "CN",
                "exchange": "UNKNOWN",
                "exchange_name": "未知交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai"
            }

    def _determine_market(self, ts_code: str) -> str:
        """确定市场代码"""
        market_info = self._determine_market_info_from_ts_code(ts_code)
        return market_info.get("market", "CN")

    def _format_date(self, date_value: Union[str, date]) -> str:
        """格式化日期为Tushare格式 (YYYYMMDD)"""
        if isinstance(date_value, str):
            return date_value.replace('-', '')
        elif isinstance(date_value, date):
            return date_value.strftime('%Y%m%d')
        else:
            return str(date_value).replace('-', '')

    def _standardize_historical_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化历史数据"""
        column_mapping = {
            'trade_date': 'date',
            'vol': 'volume'
        }
        df = df.rename(columns=column_mapping)

        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
            df.set_index('date', inplace=True)

        df = df.sort_index()

        return df

    def _standardize_tushare_financial_data(self, financial_data: Dict[str, Any], ts_code: str) -> Dict[str, Any]:
        """
        标准化Tushare财务数据

        Args:
            financial_data: 原始财务数据字典
            ts_code: Tushare股票代码

        Returns:
            标准化后的财务数据
        """
        try:
            latest_income = financial_data.get('income_statement', [{}])[0] if financial_data.get('income_statement') else {}
            latest_balance = financial_data.get('balance_sheet', [{}])[0] if financial_data.get('balance_sheet') else {}
            latest_cashflow = financial_data.get('cashflow_statement', [{}])[0] if financial_data.get('cashflow_statement') else {}
            latest_indicator = financial_data.get('financial_indicators', [{}])[0] if financial_data.get('financial_indicators') else {}

            symbol = ts_code.split('.')[0] if '.' in ts_code else ts_code
            report_period = latest_income.get('end_date') or latest_balance.get('end_date') or latest_cashflow.get('end_date')
            ann_date = latest_income.get('ann_date') or latest_balance.get('ann_date') or latest_cashflow.get('ann_date')

            income_statements = financial_data.get('income_statement', [])
            revenue_ttm = self._calculate_ttm_from_tushare(income_statements, 'revenue')
            net_profit_ttm = self._calculate_ttm_from_tushare(income_statements, 'n_income_attr_p')

            standardized_data = {
                "symbol": symbol,
                "ts_code": ts_code,
                "report_period": report_period,
                "ann_date": ann_date,
                "report_type": self._determine_report_type(report_period),

                "revenue": self._safe_float(latest_income.get('revenue')),
                "revenue_ttm": revenue_ttm,
                "oper_rev": self._safe_float(latest_income.get('oper_rev')),
                "net_income": self._safe_float(latest_income.get('n_income')),
                "net_profit": self._safe_float(latest_income.get('n_income_attr_p')),
                "net_profit_ttm": net_profit_ttm,
                "oper_profit": self._safe_float(latest_income.get('oper_profit')),
                "total_profit": self._safe_float(latest_income.get('total_profit')),
                "oper_cost": self._safe_float(latest_income.get('oper_cost')),
                "oper_exp": self._safe_float(latest_income.get('oper_exp')),
                "admin_exp": self._safe_float(latest_income.get('admin_exp')),
                "fin_exp": self._safe_float(latest_income.get('fin_exp')),
                "rd_exp": self._safe_float(latest_income.get('rd_exp')),

                "total_assets": self._safe_float(latest_balance.get('total_assets')),
                "total_liab": self._safe_float(latest_balance.get('total_liab')),
                "total_equity": self._safe_float(latest_balance.get('total_hldr_eqy_exc_min_int')),
                "total_cur_assets": self._safe_float(latest_balance.get('total_cur_assets')),
                "total_nca": self._safe_float(latest_balance.get('total_nca')),
                "total_cur_liab": self._safe_float(latest_balance.get('total_cur_liab')),
                "total_ncl": self._safe_float(latest_balance.get('total_ncl')),
                "money_cap": self._safe_float(latest_balance.get('money_cap')),
                "accounts_receiv": self._safe_float(latest_balance.get('accounts_receiv')),
                "inventories": self._safe_float(latest_balance.get('inventories')),
                "fix_assets": self._safe_float(latest_balance.get('fix_assets')),

                "n_cashflow_act": self._safe_float(latest_cashflow.get('n_cashflow_act')),
                "n_cashflow_inv_act": self._safe_float(latest_cashflow.get('n_cashflow_inv_act')),
                "n_cashflow_fin_act": self._safe_float(latest_cashflow.get('n_cashflow_fin_act')),
                "c_cash_equ_end_period": self._safe_float(latest_cashflow.get('c_cash_equ_end_period')),
                "c_cash_equ_beg_period": self._safe_float(latest_cashflow.get('c_cash_equ_beg_period')),

                "roe": self._safe_float(latest_indicator.get('roe')),
                "roa": self._safe_float(latest_indicator.get('roa')),
                "roe_waa": self._safe_float(latest_indicator.get('roe_waa')),
                "roe_dt": self._safe_float(latest_indicator.get('roe_dt')),
                "roa2": self._safe_float(latest_indicator.get('roa2')),
                "gross_margin": self._safe_float(latest_indicator.get('grossprofit_margin')),
                "netprofit_margin": self._safe_float(latest_indicator.get('netprofit_margin')),
                "cogs_of_sales": self._safe_float(latest_indicator.get('cogs_of_sales')),
                "expense_of_sales": self._safe_float(latest_indicator.get('expense_of_sales')),
                "profit_to_gr": self._safe_float(latest_indicator.get('profit_to_gr')),
                "saleexp_to_gr": self._safe_float(latest_indicator.get('saleexp_to_gr')),
                "adminexp_of_gr": self._safe_float(latest_indicator.get('adminexp_of_gr')),
                "finaexp_of_gr": self._safe_float(latest_indicator.get('finaexp_of_gr')),
                "debt_to_assets": self._safe_float(latest_indicator.get('debt_to_assets')),
                "assets_to_eqt": self._safe_float(latest_indicator.get('assets_to_eqt')),
                "dp_assets_to_eqt": self._safe_float(latest_indicator.get('dp_assets_to_eqt')),
                "ca_to_assets": self._safe_float(latest_indicator.get('ca_to_assets')),
                "nca_to_assets": self._safe_float(latest_indicator.get('nca_to_assets')),
                "current_ratio": self._safe_float(latest_indicator.get('current_ratio')),
                "quick_ratio": self._safe_float(latest_indicator.get('quick_ratio')),
                "cash_ratio": self._safe_float(latest_indicator.get('cash_ratio')),

                "raw_data": {
                    "income_statement": financial_data.get('income_statement', []),
                    "balance_sheet": financial_data.get('balance_sheet', []),
                    "cashflow_statement": financial_data.get('cashflow_statement', []),
                    "financial_indicators": financial_data.get('financial_indicators', []),
                    "main_business": financial_data.get('main_business', [])
                },

                "data_source": "tushare",
                "updated_at": datetime.utcnow()
            }

            return standardized_data

        except Exception as e:
            self.logger.error(f" 标准化Tushare财务数据失败: {e}")
            return {
                "symbol": ts_code.split('.')[0] if '.' in ts_code else ts_code,
                "data_source": "tushare",
                "updated_at": datetime.utcnow(),
                "error": str(e)
            }

    def _calculate_ttm_from_tushare(self, income_statements: list, field: str) -> Optional[float]:
        """
        从 Tushare 利润表数据计算 TTM（最近12个月）

        Tushare 利润表数据是累计值（从年初到报告期的累计）：
        - 2025Q1 (20250331): 2025年1-3月累计
        - 2025Q2 (20250630): 2025年1-6月累计
        - 2025Q3 (20250930): 2025年1-9月累计
        - 2025Q4 (20251231): 2025年1-12月累计（年报）

        TTM 计算公式：
        TTM = 去年同期之后的最近年报 + (本期累计 - 去年同期累计)

        例如：2025Q2 TTM = 2024年报 + (2025Q2 - 2024Q2)
                        = 2024年1-12月 + (2025年1-6月 - 2024年1-6月)
                        = 2024年7-12月 + 2025年1-6月
                        = 最近12个月

        Args:
            income_statements: 利润表数据列表（按报告期倒序）
            field: 字段名（'revenue' 或 'n_income_attr_p'）

        Returns:
            TTM 值，如果无法计算则返回 None
        """
        if not income_statements or len(income_statements) < 1:
            return None

        try:
            latest = income_statements[0]
            latest_period = latest.get('end_date')
            latest_value = self._safe_float(latest.get(field))

            if not latest_period or latest_value is None:
                return None

            month_day = latest_period[4:8]

            if month_day == '1231':
                self.logger.debug(f" TTM计算: 使用年报数据 {latest_period} = {latest_value:.2f}")
                return latest_value


            latest_year = latest_period[:4]
            last_year = str(int(latest_year) - 1)
            last_year_same_period = last_year + latest_period[4:]

            last_year_same = None
            for stmt in income_statements:
                if stmt.get('end_date') == last_year_same_period:
                    last_year_same = stmt
                    break

            if not last_year_same:
                self.logger.warning(f" TTM计算失败: 缺少去年同期数据（需要: {last_year_same_period}，最新期: {latest_period}）")
                return None

            last_year_value = self._safe_float(last_year_same.get(field))
            if last_year_value is None:
                self.logger.warning(f" TTM计算失败: 去年同期数据值为空（{last_year_same_period}）")
                return None

            base_period = None
            for stmt in income_statements:
                period = stmt.get('end_date')
                if period and period > last_year_same_period and period[4:8] == '1231':
                    base_period = stmt
                    break

            if not base_period:
                self.logger.warning(f" TTM计算失败: 缺少基准年报（需要在 {last_year_same_period} 之后的年报，最新期: {latest_period}）")
                return None

            base_value = self._safe_float(base_period.get(field))
            if base_value is None:
                self.logger.warning(f" TTM计算失败: 基准年报数据值为空（{base_period.get('end_date')}）")
                return None

            ttm_value = base_value + (latest_value - last_year_value)

            self.logger.debug(
                f" TTM计算: {base_period.get('end_date')}({base_value:.2f}) + "
                f"({latest_period}({latest_value:.2f}) - {last_year_same_period}({last_year_value:.2f})) = {ttm_value:.2f}"
            )

            return ttm_value

        except Exception as e:
            self.logger.warning(f" TTM计算异常: {e}")
            return None

    def _determine_report_type(self, report_period: str) -> str:
        """根据报告期确定报告类型"""
        if not report_period:
            return "quarterly"

        try:
            month_day = report_period[4:8]
            if month_day == "1231":
                return "annual"
            else:
                return "quarterly"
        except:
            return "quarterly"

    def _safe_float(self, value) -> Optional[float]:
        """安全转换为浮点数，处理各种异常情况"""
        if value is None:
            return None

        try:
            if isinstance(value, str):
                value = value.strip()
                if not value or value.lower() in ['nan', 'null', 'none', '--', '']:
                    return None
                value = value.replace(',', '').replace('万', '').replace('亿', '')

            if isinstance(value, (int, float)):
                if isinstance(value, float) and (value != value):
                    return None
                return float(value)

            return float(value)

        except (ValueError, TypeError, AttributeError):
            return None

    def _calculate_gross_profit(self, revenue, oper_cost) -> Optional[float]:
        """安全计算毛利润"""
        revenue_float = self._safe_float(revenue)
        oper_cost_float = self._safe_float(oper_cost)

        if revenue_float is not None and oper_cost_float is not None:
            return revenue_float - oper_cost_float
        return None

    def _safe_str(self, value) -> Optional[str]:
        """安全转换为字符串，处理NaN值"""
        if value is None:
            return None
        if isinstance(value, float) and (value != value):
            return None
        return str(value) if value else None


_tushare_provider = None
_tushare_provider_initialized = False

def get_tushare_provider() -> TushareProvider:
    """获取全局Tushare提供器实例"""
    global _tushare_provider, _tushare_provider_initialized
    if _tushare_provider is None:
        _tushare_provider = TushareProvider()
        if not _tushare_provider_initialized:
            try:
                _tushare_provider.connect_sync()
                _tushare_provider_initialized = True
            except Exception as e:
                logger.warning(f" Tushare自动连接失败: {e}")
    return _tushare_provider
