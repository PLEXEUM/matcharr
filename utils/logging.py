import logging
import sys
from logging.handlers import RotatingFileHandler
import os

# Single log file for everything - in the mounted volume
LOG_FILE = "/app/logs/matcharr.log"

# Ensure the logs directory exists
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

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
    
    # Remove any existing handlers to avoid duplicates
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # Always add file handler
    logger.addHandler(get_file_handler())
    
    # Add console handler only if running interactively (not cron)
    if sys.stdout.isatty():
        logger.addHandler(get_console_handler())
    
    logger.propagate = False
    return logger