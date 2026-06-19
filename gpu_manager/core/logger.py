"""
日志工具：统一日志配置，替代散落的 print 与 except: pass。
"""
import logging
import os


class _NullHandler(logging.Handler):
    """无配置时静默丢弃日志，避免 'No handlers found' 警告"""
    def emit(self, record):
        pass


def get_logger(name: str,
               log_file: str = None,
               level: int = logging.INFO) -> logging.Logger:
    """
    获取或创建命名 logger。
    首次调用时自动配置 StreamHandler + 可选 FileHandler。
    """
    logger = logging.getLogger(name)
    if not logger.handlers and not logger.hasHandlers():
        logger.setLevel(level)
        formatter = logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S')
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger.addHandler(sh)
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            fh = logging.FileHandler(log_file, encoding='utf-8')
            fh.setFormatter(formatter)
            logger.addHandler(fh)
    return logger
