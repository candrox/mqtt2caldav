### SECTION :: Module Imports ############################################################
import logging
import sys
import os
from utils.constants import LOG_DIR, LOG_FILE


### SECTION :: Logfile Path ##############################################################
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)

log_fn = os.path.join(LOG_DIR, LOG_FILE)



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

        levelname = f"{levelname:<5}"
        record.levelname_padded = levelname

        return super().format(record)



###  SECTION :: Formatter And Logger Configuration #######################################
formatter = LowercaseLevelFormatter(
    fmt='%(levelname_padded)s %(asctime)s: %(message)s', # Use padded levelname_padded
    datefmt='%Y/%m/%d %H:%M:%S') # Bracket moved to this line

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s: %(message)s',
                    datefmt='%Y/%m/%d %H:%M:%S',
                    filename=log_fn)



###  SECTION :: Logger And Handler Configuration #########################################
logger = logging.getLogger('MQTT-CALDAV')

root_logger = logging.getLogger()
if root_logger.handlers:
    handler = root_logger.handlers[0]
    handler.setFormatter(formatter)
else:
    print("[SYS] No handler found for root logger. Custom formatter might not be applied to file logging.")



### SECTION :: Log Message Output Function ###############################################
def __log_msg(msg):
    sys.stdout.write(msg + '\n')
    if len(msg) > 0 and msg[0] == '\r':
        msg = msg[1:]
    return msg



### SECTION :: Level-Based Logging Functions #############################################
def info(msg):
    logger.info(__log_msg(msg))

def warn(msg):
    logger.warning(__log_msg(msg))

def error(msg):
    logger.error(__log_msg(msg))

def debug(msg):
    logger.debug(__log_msg(msg))

def critical(msg):
    logger.critical(__log_msg(msg))
