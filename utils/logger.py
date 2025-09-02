### SECTION :: Module Imports ############################################################
import os
import sys
import logging
from utils.constants import LOG_DIR, LOG_FILE_NAME, APP_NAME



### SECTION :: Logfile Path ##############################################################
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)
log_fn = os.path.join(LOG_DIR, LOG_FILE_NAME)



### CLASS :: Custom Log Formatter Class ##################################################
class LowercaseLevelFormatter(logging.Formatter):
    """Custom formatter to use lowercase level names and shortened 'warning' and 'critical'"""
    def format(self, record):
        levelname = record.levelname
        if levelname == "WARNING":
            levelname = "warn"
        elif levelname == "CRITICAL":
            levelname = "crit"
        else:
            levelname = levelname.lower()

        record.levelname_padded = f"{levelname:<5}"
        return super().format(record)



### SECTION :: Logger And Handler Configuration ##########################################
formatter = LowercaseLevelFormatter(
	# Alternative to add milliseconds to time-stamps
    # fmt='%(levelname_padded)s %(asctime)s.%(msecs)03d: %(message)s',
    fmt='%(levelname_padded)s %(asctime)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Get Application Logger
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.INFO)

# Create File Handler
file_handler = logging.FileHandler(log_fn)
file_handler.setFormatter(formatter)

# Create Stream Handler
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)

# Add Handlers To Logger
logger.addHandler(file_handler)
logger.addHandler(stream_handler)
logger.propagate = False


### FUNCTION :: Set Log Level From Config ################################################
def set_log_level(level_str: str):
    """Sets the logger level based on a string name."""
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARN': logging.WARNING,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRIT': logging.CRITICAL,
        'CRITICAL': logging.CRITICAL
    }
    log_level = level_map.get(level_str.upper(), logging.INFO)
    logger.setLevel(log_level)
    if level_str.upper() not in level_map and level_str:
         warn_formatter = logging.Formatter(fmt='%(asctime)s.%(msecs)03d', datefmt='%Y-%m-%d %H:%M:%S')
         timestamp = warn_formatter.format(logging.LogRecord(name=APP_NAME, level=logging.WARNING, pathname='', lineno=0, msg='', args=[], exc_info=None, func=''))
         print(f"warn  {timestamp}: [APP] Invalid LOG_LEVEL set, defaulting to INFO.")


### SECTION :: Level-Based Logging Functions #############################################
def info(msg):
    logger.info(msg)

def warn(msg):
    logger.warning(msg)

def error(msg):
    logger.error(msg)

def debug(msg):
    logger.debug(msg)

def critical(msg):
    logger.critical(msg)
