import logging
import sys
import os
from utils.constants import LOG_DIR, LOG_FILE

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)


log_fn = os.path.join(LOG_DIR, LOG_FILE)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filename=log_fn)
logger = logging.getLogger('MQTT-CALDAV')


def __log_init():
    if os.path.isfile(log_fn):
        os.remove(log_fn)


def __log_msg(msg):
    sys.stdout.write(msg + '\n')
    if len(msg) > 0 and msg[0] == '\r':
        msg = msg[1:]
    return msg


def info(msg):
    logger.info(__log_msg(msg))


def warn(msg):
    logger.warning(__log_msg(msg))


def error(msg):
    logger.error(__log_msg(msg))
