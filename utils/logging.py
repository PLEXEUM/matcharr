import logging
import sys
from logging.handlers import RotatingFileHandler

# Single log file for everything
LOG_FILE = "matcharr.log"

FORMATTER = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

def get_console_handler():
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(FORMATTER)
    return console_handler

def get_file_handler():
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=1024 * 1024 * 5,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(FORMATTER)
    return file_handler

def get_logger(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(get_file_handler())
    logger.addHandler(get_console_handler())  # Also show on console
    logger.propagate = False
    return logger