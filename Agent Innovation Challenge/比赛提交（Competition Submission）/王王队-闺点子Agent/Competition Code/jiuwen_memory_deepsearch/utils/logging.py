import logging
import os
from logging.handlers import RotatingFileHandler


class ProjectLogFilter(logging.Filter):
    """
    自定义日志过滤器，只允许项目相关模块的日志通过
    """

    def filter(self, record):
        # 只允许 jiuwen_memory_deepsearch 相关的日志记录
        return record.name.startswith('jiuwen_memory_deepsearch')


def setup_global_logger(log_file: str = "deepsearch.log", error_log_file: str = "deepsearch_error.log"):
    """
    配置全局日志记录器，影响所有通过 logging.getLogger() 创建的记录器
    但只将项目相关的日志写入文件
    
    Args:
        log_file: 常规日志文件名，默认为"deepsearch.log"
        error_log_file: 错误日志文件名，默认为"deepsearch_error.log"
    """
    # 获取根日志记录器
    root_logger = logging.getLogger()

    # 检查根日志记录器是否已经有我们的处理器，避免重复添加
    if not any(isinstance(handler, RotatingFileHandler) for handler in root_logger.handlers):
        # 日志格式
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        # 确保logs目录存在
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
        os.makedirs(log_dir, exist_ok=True)

        # 常规文件处理器，使用RotatingFileHandler来限制文件大小
        log_path = os.path.join(log_dir, log_file)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,  # 保留5个备份文件
            encoding="utf-8"  # 设置UTF-8编码，解决中文乱码问题
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        # 添加过滤器，只记录项目相关日志
        file_handler.addFilter(ProjectLogFilter())

        # 错误文件处理器，只记录ERROR级别及以上的日志
        error_log_path = os.path.join(log_dir, error_log_file)
        error_file_handler = RotatingFileHandler(
            error_log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(formatter)
        # 添加过滤器，只记录项目相关日志
        error_file_handler.addFilter(ProjectLogFilter())

        # 添加处理器到根日志记录器
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(error_file_handler)
        root_logger.setLevel(logging.INFO)
