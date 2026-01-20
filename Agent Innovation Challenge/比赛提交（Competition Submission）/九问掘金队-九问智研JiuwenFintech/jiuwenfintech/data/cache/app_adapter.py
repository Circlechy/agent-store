from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
from openjiuwen.core.common.logging import logger

_logger = logger

get_mongodb_client = None


BASICS_COLLECTION = "stock_basic_info"
QUOTES_COLLECTION = "market_quotes"


def get_basics_from_cache(stock_code: Optional[str] = None) -> Optional[Dict[str, Any] | List[Dict[str, Any]]]:
    """从 app 的 stock_basic_info 读取基础信息。"""
    if get_mongodb_client is None:
        return None
    client = get_mongodb_client()
    if not client:
        return None
    try:
        db_name = None
        try:
            from jiuwenfintech.config.database_manager import get_database_manager
            db_name = get_database_manager().mongodb_config.get("database", "tradingagents")
        except Exception:
            db_name = "tradingagents"
        db = client[db_name]
        coll = db[BASICS_COLLECTION]
        if stock_code:
            code6 = str(stock_code).zfill(6)
            try:
                _logger.debug(f"[app_cache] 查询基础信息 | db={db_name} coll={BASICS_COLLECTION} code={code6}")
            except Exception:
                pass
            doc = coll.find_one({"$or": [{"symbol": code6}, {"code": code6}]})
            if not doc:
                try:
                    _logger.debug(f"[app_cache] 基础信息未命中 | db={db_name} coll={BASICS_COLLECTION} code={code6}")
                except Exception:
                    pass
            return doc or None
        else:
            cursor = coll.find({})
            docs = list(cursor)
            return docs or None
    except Exception as e:
        try:
            _logger.debug(f"[app_cache] 基础信息读取异常（忽略）: {e}")
        except Exception:
            pass
        return None


def get_market_quote_dataframe(symbol: str) -> Optional[pd.DataFrame]:
    """从 app 的 market_quotes 读取单只股票的最新一条快照，并转为 DataFrame。"""
    if get_mongodb_client is None:
        return None
    client = get_mongodb_client()
    if not client:
        return None
    try:
        from jiuwenfintech.config.database_manager import get_database_manager
        db_name = get_database_manager().mongodb_config.get("database", "tradingagents")
        db = client[db_name]
        coll = db[QUOTES_COLLECTION]
        code = str(symbol).zfill(6)
        try:
            _logger.debug(f"[app_cache] 查询行情 | db={db_name} coll={QUOTES_COLLECTION} code={code}")
        except Exception:
            pass
        doc = coll.find_one({"code": code})
        if not doc:
            try:
                _logger.debug(f"[app_cache] 行情未命中 | db={db_name} coll={QUOTES_COLLECTION} code={code}")
            except Exception:
                pass
            return None
        row = {
            "code": code,
            "date": doc.get("trade_date"),
            "open": doc.get("open"),
            "high": doc.get("high"),
            "low": doc.get("low"),
            "close": doc.get("close"),
            "volume": doc.get("volume"),
            "amount": doc.get("amount"),
            "pct_chg": doc.get("pct_chg"),
            "change": None,
        }
        df = pd.DataFrame([row])
        return df
    except Exception as e:
        try:
            _logger.debug(f"[app_cache] 行情读取异常（忽略）: {e}")
        except Exception:
            pass
        return None

