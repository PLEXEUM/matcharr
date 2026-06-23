import logging
import sys
from logging.handlers import RotatingFileHandler
import os

FORMATTER = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
LOG_FILE = 'logs/matcharr.log'

# Store the original stdout for tqdm
original_stdout = sys.stdout


class TeeLogger:
    """Writes to both stdout and the log file"""
    def __init__(self, file_path):
        self.file = open(file_path, 'a', encoding='utf-8')
        self.stdout = sys.stdout
        
    def write(self, message):
        self.stdout.write(message)
        self.file.write(message)
        self.file.flush()
        
    def flush(self):
        self.stdout.flush()
        self.file.flush()


def get_console_handler():
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(FORMATTER)
    # Only show WARNING and above in console to keep tqdm clean
    console_handler.setLevel(logging.WARNING)
    return console_handler


def get_file_handler():
    os.makedirs('logs', exist_ok=True)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=1024 * 1024 * 2,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(FORMATTER)
    # Log everything to file including DEBUG
    file_handler.setLevel(logging.DEBUG)
    return file_handler


def setup_logging():
    """Set up logging to both console and file"""
    # Redirect stdout to both console and file (for tqdm and prints)
    sys.stdout = TeeLogger(LOG_FILE)
    
    # Set up logging
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(get_file_handler())
    logger.addHandler(get_console_handler())
    
    return logger


def get_logger(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(get_file_handler())
    logger.addHandler(get_console_handler())
    logger.propagate = False
    return logger