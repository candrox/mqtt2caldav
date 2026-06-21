### SECTION :: Module Imports ############################################################
import os



### SECTION :: Application Name ##########################################################
APP_NAME = "MQTT2CALDAV"



### SECTION :: Path Definitions ##########################################################
_cur_dir = os.path.dirname(os.path.realpath(__file__))
ROOT_DIR = os.path.join(_cur_dir, os.pardir)

LOG_DIR = os.path.join(ROOT_DIR, 'logs')
LOG_FILE_NAME = "mqtt2caldav.log"
LOCK_FILE_NAME = "mqtt2caldav.lock"
LOCK_FILE_PATH = os.path.abspath(os.path.join(LOG_DIR, LOCK_FILE_NAME))

CONFIG_DIR_NAME = "config"
SETTINGS_FILE_NAME = "settings.json"
TRIGGERS_FILE_NAME = "triggers.json"
CONFIG_DIR = os.path.join(ROOT_DIR, CONFIG_DIR_NAME)
