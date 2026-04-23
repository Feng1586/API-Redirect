"""
日志模块
"""

import logging
import sys
from typing import Optional

# 日志等级常量
LOG_LEVEL_DEBUG = "DEBUG"
LOG_LEVEL_INFO = "INFO"
LOG_LEVEL_WARN = "WARN"
LOG_LEVEL_ERROR = "ERROR"
LOG_LEVEL_FATAL = "FATAL"


class Logger:
    """日志记录器"""

    def __init__(self, name: str, level: str = LOG_LEVEL_INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level))

        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(getattr(logging, level))

            formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def debug(self, message: str):
        self.logger.debug(message)

    def info(self, message: str):
        self.logger.info(message)

    def warn(self, message: str):
        self.logger.warning(message)

    def error(self, message: str):
        self.logger.error(message)

    def fatal(self, message: str):
        self.logger.critical(message)


_loggers = {}


def get_logger(name: str, level: Optional[str] = None) -> Logger:
    """
    获取指定名称的日志器
    """
    if name not in _loggers:
        _loggers[name] = Logger(name, level or LOG_LEVEL_INFO)
    return _loggers[name]


def log(level: str, message: str, module: str = "app"):
    """
    通用日志输出方法
    """
    logger = get_logger(module)
    getattr(logger, level.lower())(message)
