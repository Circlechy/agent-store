import os
from typing import Union

from openjiuwen.core.common.logging import logger

try:
    from .file_cache import StockDataCache
    FILE_CACHE_AVAILABLE = True
except ImportError:
    StockDataCache = None
    FILE_CACHE_AVAILABLE = False

try:
    from .db_cache import DatabaseCacheManager
    DB_CACHE_AVAILABLE = True
except ImportError:
    DatabaseCacheManager = None
    DB_CACHE_AVAILABLE = False

try:
    from .adaptive import AdaptiveCacheSystem
    ADAPTIVE_CACHE_AVAILABLE = True
except ImportError:
    AdaptiveCacheSystem = None
    ADAPTIVE_CACHE_AVAILABLE = False

try:
    from .integrated import IntegratedCacheManager
    INTEGRATED_CACHE_AVAILABLE = True
except ImportError:
    IntegratedCacheManager = None
    INTEGRATED_CACHE_AVAILABLE = False

try:
    from .app_adapter import get_basics_from_cache, get_market_quote_dataframe
    APP_CACHE_AVAILABLE = True
except ImportError:
    get_basics_from_cache = None
    get_market_quote_dataframe = None
    APP_CACHE_AVAILABLE = False

try:
    from .mongodb_cache_adapter import MongoDBCacheAdapter
    MONGODB_CACHE_ADAPTER_AVAILABLE = True
except ImportError:
    MongoDBCacheAdapter = None
    MONGODB_CACHE_ADAPTER_AVAILABLE = False

_cache_instance = None

DEFAULT_CACHE_STRATEGY = os.getenv("TA_CACHE_STRATEGY", "integrated")

def get_cache() -> Union[StockDataCache, IntegratedCacheManager]:
    """
    获取缓存实例（统一入口）

    根据环境变量 TA_CACHE_STRATEGY 选择缓存策略：
    - "file" (默认): 使用文件缓存
    - "integrated": 使用集成缓存（自动选择 MongoDB/Redis/File）
    - "adaptive": 使用自适应缓存（同 integrated）

    环境变量设置：
        export TA_CACHE_STRATEGY=integrated  # Linux/Mac
        set TA_CACHE_STRATEGY=integrated     # Windows

    返回：
        StockDataCache 或 IntegratedCacheManager 实例
    """
    global _cache_instance

    if _cache_instance is None:
        if DEFAULT_CACHE_STRATEGY in ["integrated", "adaptive"]:
            if INTEGRATED_CACHE_AVAILABLE:
                try:
                    _cache_instance = IntegratedCacheManager()
                    logger.info(" 使用集成缓存系统（支持 MongoDB/Redis/File 自动选择）")
                except Exception as e:
                    logger.warning(f" 集成缓存初始化失败，降级到文件缓存: {e}")
                    _cache_instance = StockDataCache()
            else:
                logger.warning(" 集成缓存不可用，使用文件缓存")
                _cache_instance = StockDataCache()
        else:
            _cache_instance = StockDataCache()
            logger.info(" 使用文件缓存系统")

    return _cache_instance

__all__ = [
    'get_cache',

    'StockDataCache',
    'IntegratedCacheManager',
    'DatabaseCacheManager',
    'AdaptiveCacheSystem',

    'FILE_CACHE_AVAILABLE',
    'DB_CACHE_AVAILABLE',
    'ADAPTIVE_CACHE_AVAILABLE',
    'INTEGRATED_CACHE_AVAILABLE',

    'get_basics_from_cache',
    'get_market_quote_dataframe',
    'APP_CACHE_AVAILABLE',

    'MongoDBCacheAdapter',
    'MONGODB_CACHE_ADAPTER_AVAILABLE',
]

