import logging
import logging.handlers
import os

root_dir = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(root_dir, "../../logs")


class Logger:
    # 定义日志格式为类变量
    log_format = "[%(levelname)s|%(filename)s:%(lineno)s] %(asctime)s >> %(message)s"
    if not os.path.exists(log_dir):
        os.mkdir(log_dir)

    @staticmethod
    def get_log(name):
        """
        配置debug、info、error级别日志输出
        """
        # 创建一个日志对象
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)  # 设置日志对象的级别为DEBUG，这样可以捕获所有级别的日志

        # 确保只添加处理器一次
        if not logger.handlers:
            # 创建一个处理器，用于将debug级别的日志输出到debug.log文件
            log_file = os.path.join(log_dir, "debug.log")
            debug_handler = logging.handlers.RotatingFileHandler(
                log_file, encoding="utf-8", maxBytes=200 * 1024 * 1024, backupCount=15
            )
            debug_handler.setLevel(logging.DEBUG)
            debug_handler.setFormatter(logging.Formatter(Logger.log_format))
            logger.addHandler(debug_handler)

            # 创建一个处理器，用于将info级别的日志输出到info.log文件
            log_file = os.path.join(log_dir, "info.log")
            info_handler = logging.handlers.RotatingFileHandler(
                log_file, encoding="utf-8", maxBytes=200 * 1024 * 1024, backupCount=15
            )
            info_handler.setLevel(logging.INFO)
            info_handler.setFormatter(logging.Formatter(Logger.log_format))
            logger.addHandler(info_handler)

            # 创建另一个处理器，用于将error级别的日志输出到error.log文件
            log_file = os.path.join(log_dir, "error.log")
            error_handler = logging.handlers.RotatingFileHandler(
                log_file, encoding="utf-8", maxBytes=200 * 1024 * 1024, backupCount=15
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(logging.Formatter(Logger.log_format))
            logger.addHandler(error_handler)

            # 添加控制台处理器
            logger.addHandler(Logger.add_terminal_handler())

        return logger

    @staticmethod
    def get_custom_log(name, log_level=logging.DEBUG, **kwargs):
        # 创建一个日志对象
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        # 确保不添加终端处理器
        if not logger.handlers:
            # 创建一个处理器，用于将log_level级别的日志输出到文件
            log_file = os.path.join(log_dir, "{}.log".format(name))
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, encoding="utf-8", maxBytes=200 * 1024 * 1024, backupCount=15
            )
            file_handler.setLevel(log_level)  # 设置处理器的级别为INFO，这样只会处理INFO及以上级别的日志
            file_handler.setFormatter(logging.Formatter(Logger.log_format))
            logger.addHandler(file_handler)

        # 设置propagate为False，避免向父logger传播
        logger.propagate = False

        return logger

    @staticmethod
    def add_terminal_handler(log_level=logging.DEBUG, **kwargs):
        """
        在控制台打印日志
        """
        handler = logging.StreamHandler()
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter(Logger.log_format))
        return handler

    @staticmethod
    def _create_directory_if_not_exists(filename):
        directory = os.path.dirname(filename)
        if not os.path.exists(directory):
            os.makedirs(directory)

    def debug(self, message, *args, **kwargs):
        self.logger.debug(message, *args, **kwargs)

    def info(self, message, *args, **kwargs):
        self.logger.info(message, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        self.logger.error(message, *args, **kwargs)


logger = Logger.get_log("logger")
my_logger = Logger.get_log("my_logger")
request_logger = Logger.get_custom_log("request")
if __name__ == "__main__":
    # 使用日志工具类

    my_logger.debug("This is a debug message")
    my_logger.info("This is a info message")
    my_logger.error("This is an error message")

    request_logger.info("this is request message")

    my_logger.info("This is a info message2")

    multiline_text = "Line 1\r\nLine 2\\nLine 3"
    my_logger.info(multiline_text)
