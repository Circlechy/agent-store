try:
    from .providers.us import get_data_in_range
except ImportError:
    try:
        from .finnhub_utils import get_data_in_range
    except ImportError:
        get_data_in_range = None

try:
    from .news import getNewsData, fetch_top_from_category
except ImportError:
    try:
        from .news.google_news import getNewsData
    except ImportError:
        getNewsData = None
    fetch_top_from_category = None

from openjiuwen.core.common.logging import logger

try:
    from .providers.us import YFinanceUtils, YFINANCE_AVAILABLE
except ImportError:
    try:
        from .yfin_utils import YFinanceUtils
        YFINANCE_AVAILABLE = True
    except ImportError as e:
        YFinanceUtils = None
        YFINANCE_AVAILABLE = False

try:
    from .technical import StockstatsUtils, STOCKSTATS_AVAILABLE
except ImportError as e:
    try:
        from .technical.stockstats import StockstatsUtils
        STOCKSTATS_AVAILABLE = True
    except ImportError as e:
        StockstatsUtils = None
        STOCKSTATS_AVAILABLE = False

from .interface import (

    get_finnhub_news,
    get_finnhub_company_insider_sentiment,
    get_finnhub_company_insider_transactions,
    get_google_news,
    get_reddit_global_news,
    get_reddit_company_news,
    get_simfin_balance_sheet,
    get_simfin_cashflow,
    get_simfin_income_statements,
    get_stock_stats_indicators_window,
    get_stockstats_indicator,
    get_YFin_data_window,
    get_YFin_data,
    get_china_stock_data_tushare,
    get_china_stock_fundamentals_tushare,
    get_china_stock_data_unified,
    get_china_stock_info_unified,
    switch_china_data_source,
    get_current_china_data_source,
    get_hk_stock_data_unified,
    get_hk_stock_info_unified,
    get_stock_data_by_market,
)

__all__ = [
    "get_finnhub_news",
    "get_finnhub_company_insider_sentiment",
    "get_finnhub_company_insider_transactions",
    "get_google_news",
    "get_reddit_global_news",
    "get_reddit_company_news",
    "get_simfin_balance_sheet",
    "get_simfin_cashflow",
    "get_simfin_income_statements",
    "get_stock_stats_indicators_window",
    "get_stockstats_indicator",
    "get_YFin_data_window",
    "get_YFin_data",
    "get_china_stock_data_tushare",
    "get_china_stock_fundamentals_tushare",
    "get_china_stock_data_unified",
    "get_china_stock_info_unified",
    "switch_china_data_source",
    "get_current_china_data_source",
    "get_hk_stock_data_unified",
    "get_hk_stock_info_unified",
    "get_stock_data_by_market",
]
