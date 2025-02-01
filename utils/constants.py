import os
import json

# PATHS
_cur_dir = os.path.dirname(os.path.realpath(__file__))
ROOT_DIR = os.path.join(_cur_dir, os.pardir)
LOG_DIR = os.path.join(ROOT_DIR, 'logs')
LOG_FILE = "mqtt2caldav.log"
CONF_DIR = os.path.join(ROOT_DIR, 'config')
CONF_FILE = "config.json"

with open(os.path.join(CONF_DIR, CONF_FILE)) as json_file:
    json_data = json.load(json_file)
    MQTT_SERVER_ADDRESS = json_data['MQTT_SERVER']['MQTT_SERVER_ADDRESS']
    MQTT_SERVER_PORT = json_data['MQTT_SERVER']['MQTT_SERVER_PORT']
    MQTT_USERNAME = json_data['MQTT_SERVER']['MQTT_USERNAME']
    MQTT_PASSWORD = json_data['MQTT_SERVER']['MQTT_PASSWORD']

    CALDAV_SERVER_ADDRESS = json_data['CALDAV_SERVER']['CALDAV_SERVER_ADDRESS']
    CALDAV_USERNAME = json_data['CALDAV_SERVER']['CALDAV_USERNAME']
    CALDAV_PASSWORD = json_data['CALDAV_SERVER']['CALDAV_PASSWORD']

    TRIGGERS = json_data['TRIGGERS']
