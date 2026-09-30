"""
Logging configuration
Unified logging to both console and file.
"""

import os
import sys
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler


def _ensure_utf8_stdout():
    """
        Force UTF-8 on stdout/stderr.
        Avoids garbled CJK text on Windows consoles.
    """
    if sys.platform == 'win32':
                # reconfigure stdout to UTF-8 on Windows
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# log directory
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')


def setup_logger(name: str = 'hivemind', level: int = logging.DEBUG) -> logging.Logger:
    """
        Configure a logger.
    
    Args:
                name: logger name
                level: log level
        
    Returns:
                The configured logger.
    """
        # make sure the log directory exists
    os.makedirs(LOG_DIR, exist_ok=True)
    
        # create the logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
        # stop propagation to the root logger (no duplicate lines)
    logger.propagate = False
    
        # do not add handlers twice
    if logger.handlers:
        return logger
    
        # log format
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    
        # 1. file handler - detailed log (dated name, rotated)
    log_filename = datetime.now().strftime('%Y-%m-%d') + '.log'
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, log_filename),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
        # 2. console handler - concise log (INFO and above)
        # UTF-8 on Windows to avoid garbled CJK
    _ensure_utf8_stdout()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    
        # attach handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str = 'hivemind') -> logging.Logger:
    """
        Get a logger (created on first use).
    
    Args:
                name: logger name
        
    Returns:
                The logger instance.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


# default logger
logger = setup_logger()


# convenience helpers
def debug(msg: str, *args, **kwargs) -> None:
    logger.debug(msg, *args, **kwargs)

def info(msg: str, *args, **kwargs) -> None:
    logger.info(msg, *args, **kwargs)

def warning(msg: str, *args, **kwargs) -> None:
    logger.warning(msg, *args, **kwargs)

def error(msg: str, *args, **kwargs) -> None:
    logger.error(msg, *args, **kwargs)

def critical(msg: str, *args, **kwargs) -> None:
    logger.critical(msg, *args, **kwargs)

