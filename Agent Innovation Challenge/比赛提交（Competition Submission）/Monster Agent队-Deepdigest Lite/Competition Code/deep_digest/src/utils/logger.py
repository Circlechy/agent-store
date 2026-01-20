"""
日志系统模块 - 基于 OpenJiuwen 框架
提供简化的日志接口，底层使用 OpenJiuwen 的日志管理器
"""

from pathlib import Path
from typing import Dict, Any
from openjiuwen.core.common.logging.manager import LogManager
from openjiuwen.extensions.common.log.default_impl import DefaultLogger


# 日志目录
LOGS_DIR = Path(__file__).parent.parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# 全局日志管理器
_log_manager = None


def get_log_config(log_type: str = "deepdigest", level: str = "INFO") -> Dict[str, Any]:
    """
    生成日志配置
    
    Args:
        log_type: 日志类型名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        日志配置字典
    """
    log_file = LOGS_DIR / f"{log_type}.log"
    
    return {
        'log_file': str(log_file),
        'output': ['console', 'file'],
        'level': level.upper(),
        'backup_count': 5,  # 保留 5 个备份文件
        'max_bytes': 10 * 1024 * 1024,  # 10MB
        'format': '%(asctime)s | %(log_type)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s',
        'log_file_pattern': None,
        'backup_file_pattern': None
    }


def get_logger(log_type: str = "deepdigest", level: str = "INFO"):
    """
    获取日志器实例（基于 OpenJiuwen 框架）
    
    Args:
        log_type: 日志类型名称
        level: 日志级别
    
    Returns:
        日志器对象（支持 debug, info, warning, error, critical 等方法）
    
    Example:
        >>> from src.utils import get_logger
        >>> logger = get_logger("deepdigest", "INFO")
        >>> logger.info("Night Agent 开始执行")
        >>> logger.error("卡片保存失败")
    """
    global _log_manager
    
    if _log_manager is None:
        _log_manager = LogManager()
    
    # 尝试获取已存在的日志器
    try:
        return _log_manager.get_logger(log_type)
    except (KeyError, RuntimeError):
        # 如果不存在，创建新的日志器
        config = get_log_config(log_type, level)
        logger = DefaultLogger(log_type, config)
        _log_manager.register_logger(log_type, logger)
        logger.info(f"✅ 日志系统初始化成功 - 类型: {log_type}, 级别: {level}")
        logger.info(f"📁 日志文件: {config['log_file']}")
        return logger


# 创建默认日志器实例（用于快速使用）
default_logger = get_logger("deepdigest", "INFO")


# 便捷函数（可选）
def debug(msg: str, *args, **kwargs):
    """记录 DEBUG 级别日志"""
    default_logger.debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs):
    """记录 INFO 级别日志"""
    default_logger.info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    """记录 WARNING 级别日志"""
    default_logger.warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    """记录 ERROR 级别日志"""
    default_logger.error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs):
    """记录 CRITICAL 级别日志"""
    default_logger.critical(msg, *args, **kwargs)


# ===================== 测试代码 =====================
if __name__ == "__main__":
    # 测试日志系统
    logger = get_logger("test", "DEBUG")
    
    logger.debug("这是 DEBUG 消息")
    logger.info("这是 INFO 消息")
    logger.warning("这是 WARNING 消息")
    logger.error("这是 ERROR 消息")
    logger.critical("这是 CRITICAL 消息")
    
    # 测试异常记录
    try:
        result = 1 / 0
    except Exception as e:
        logger.error("发生除零错误", exc_info=True)
    
    print(f"\n📁 日志文件位置: {LOGS_DIR}")
    print("✅ 日志系统测试完成")
