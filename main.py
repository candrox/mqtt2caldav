#!/usr/bin/env python3

### SECTION :: Version ###################################################################
VERSION = "20250412.1200"



### SECTION :: Module Imports ############################################################
import os
import sys
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import caldav
from caldav.lib.error import AuthorizationError, DAVError, NotFoundError

import paho.mqtt.client as mqttClient
from paho.mqtt.client import Client as MQTTClient, MQTTMessage

from utils import logger
from utils.constants import LOG_FILE, LOG_DIR, APP_NAME, CONF_DIR, CONF_FILE



### FUNCTION :: Load Config File #########################################################
def load_config(config_file: str = os.path.join(CONF_DIR, CONF_FILE)) -> Dict[str, Any]:
    """Loads configuration from a JSON file and returns a dictionary."""
    try:
        if not os.path.isabs(config_file):
             script_dir = os.path.dirname(os.path.abspath(__file__))
             config_path = os.path.join(script_dir, config_file)
        else:
             config_path = os.path.abspath(config_file)
        with open(config_path, 'r') as f:
            loaded_config: Dict[str, Any] = json.load(f)
            logger.info(f"[APP] Config File Load Successful   | {{\"config_path\":\"{config_path}\"}}")
            return loaded_config

    except FileNotFoundError as e:
        logger.error(f"[CONF] File not found: {config_path} | {type(e).__name__}: {e}")
        sys.exit(1)

    except json.JSONDecodeError as e:
        logger.error(f"[CONF] Invalid JSON: {config_path} | {type(e).__name__}: {e}")
        sys.exit(1)



### FUNCTION :: Connect CalDAV Server ####################################################
def connect_caldav(caldav_server_address: str, caldav_username: str, caldav_password: str) -> caldav.DAVClient:
    """Connects to the CalDAV server and returns the client object."""
    try:
        caldav_client: caldav.DAVClient = caldav.DAVClient(url=caldav_server_address, username=caldav_username, password=caldav_password)
        my_principal = caldav_client.principal()
        calendars = my_principal.calendars()
        if calendars:
            logger.info(f"[DAV] Server Connection Successful  | {{\"caldav_host\":\"{caldav_username}@{caldav_server_address}\"}}")
            for calendar in calendars:
                logger.debug(f"[DAV] {calendar.name:<20} {calendar.url}")
        else:
            logger.debug("[DAV] Server Connection Successful | No calendars found")
        return caldav_client

    except AuthorizationError as e:
        handle_error(f"[DAV] Server Connection Failed | {caldav_username}@{caldav_server_address}", e, "CalDAV Connection")
        sys.exit(1)
    except DAVError as e:
        handle_error(f"[DAV] Server Connection Failed | {caldav_username}@{caldav_server_address}", e, "CalDAV Connection")
        sys.exit(1)
    except Exception as e:
        handle_error(f"[DAV] Server Connection Failed | {caldav_username}@{caldav_server_address} | Unexpected Error", e, "CalDAV Connection")
        sys.exit(1)



### FUNCTION :: Create CalDAV Event ######################################################
def create_caldav_event(caldav_client: caldav.DAVClient, event_details: Optional[Dict[str, Any]], topic: str) -> None:
    """Creates an event on the CalDAV server."""
    try:
        start_time = event_details['start_time']
        end_time = event_details['end_time']

        main_event = "BEGIN:VCALENDAR\n" \
                "VERSION:2.0\n" \
                "PRODID:-//MQTT//EN\n" \
                "CALSCALE:GREGORIAN\n" \
                "BEGIN:VEVENT\n" \
                f"DTSTART;TZID={event_details['event_timezone']}:{start_time}\n" \
                f"DTEND;TZID={event_details['event_timezone']}:{end_time}\n" \
                f"DTSTAMP:{start_time}\n" \
                f"LOCATION:{event_details['event_location']}\n" \
                f"DESCRIPTION:{event_details['event_description']}\n" \
                f"URL;VALUE=URI:{event_details['event_url']}\n" \
                f"SUMMARY:{event_details['event_summary']}\n" \
                f"GEO:{event_details['event_geo']}\n" \
                f"TRANSP:{event_details['event_transp']}\n" \
                f"CATEGORIES:{event_details['event_categories']}\n" \
                f"CREATED:{start_time}\n"

        end_event = "END:VEVENT\n" \
            "END:VCALENDAR\n"

        alarm_event = ""
        if event_details['event_trigger']:
            alarm_event = "BEGIN:VALARM\n" \
                               f"TRIGGER:-PT{event_details['event_trigger']}M\n" \
                               "ATTACH;VALUE=URI:Chord\n" \
                               "ACTION:AUDIO\n" \
                               "END:VALARM\n"
        str_event = main_event + alarm_event + end_event


        event_calendar = caldav.Calendar(client=caldav_client, url=event_details['event_calendar_url'])
        caldav_event = event_calendar.save_event(str_event)
        logger.info(f"[DAV] Event Created  | {topic} | {{\"event_path\":\"{caldav_event.url}\"}}")

    except KeyError as e:
        logger.error(f"[DAV] Event Create Error | {topic} | Config Error: Missing event detail key: {e}")
    except ValueError as e:
        logger.error(f"[DAV] Event Create Error | {topic} | Data Error: Invalid event detail value: {e}")
    except DAVError as e:
        logger.error(f"[DAV] Event Create Error | {topic} | CalDAV Server Error: {type(e).__name__}: {e}")
    except Exception as e:
        logger.error(f"[DAV] Event Create Error | {topic} | Unexpected Error: {type(e).__name__}: {e}")



### FUNCTION :: Delete CalDAV Event ######################################################
def delete_caldav_event(caldav_client: caldav.DAVClient, event_url: str, topic: str) -> None:
    """Deletes a CalDAV event from the server."""
    try:
        event = caldav.Event(client=caldav_client, url=event_url)
        event.delete()
        logger.info(f"[DAV] Event Deleted  | {topic} | {{\"event_path\":\"{event_url}\"}}")

    except NotFoundError as e:
        logger.error(f"[DAV] Event Delete Error | {topic} | Not Found Error: Event URL not found: {event_url}")
    except DAVError as e:
        logger.error(f"[DAV] Event Delete Error | {topic} | CalDAV Server Error: {type(e).__name__}: {e}")
    except Exception as e:
        logger.error(f"[DAV] Event Delete Error | {topic} | Unexpected Error: {type(e).__name__}: {e}")



### FUNCTION :: Find Last Created Event URL ##############################################
def find_last_created_event_url() -> Optional[str]:
    """Searches the log file for the last created event URL."""
    log_file_path = os.path.join(LOG_DIR, LOG_FILE)
    if not os.path.exists(log_file_path):
        return None

    with open(log_file_path, 'r') as logfile:
        lines = logfile.readlines()

        for line in reversed(lines): # Iterate from log file end
            if "[DAV] Event Created" in line:
                try:
                    json_str_start = line.find('{')
                    if json_str_start != -1:
                        json_str = line[json_str_start:]
                        event_data = json.loads(json_str)
                        return event_data.get("event_path")
                except json.JSONDecodeError:
                    logger.warn(f"[Log] Invalid JSON: {line.strip()}")
    return None



### FUNCTION :: Connect MQTT Broker ######################################################
def on_connect(client: MQTTClient, userdata, flags, rc: int) -> None:
    """Callback function for MQTT connection events. Logs the connection status."""
    if rc == 0:
        logger.info(f"[MQT] Broker Connection Successful  | {{\"mqtt_host\":\"{config['MQTT_SERVER']['MQTT_USERNAME']}@{config['MQTT_SERVER']['MQTT_SERVER_ADDRESS']}:{config['MQTT_SERVER']['MQTT_SERVER_PORT']}\"}}")
    else:
        logger.error(f"[MQT] Broker Connection Failed  | {config['MQTT_SERVER']['MQTT_USERNAME']}@{config['MQTT_SERVER']['MQTT_SERVER_ADDRESS']}:{config['MQTT_SERVER']['MQTT_SERVER_PORT']}")



### FUNCTION :: Process MQTT Message #####################################################
def on_message(caldav_client: caldav.DAVClient, mqtt_client: MQTTClient, userdata, mqtt_message: MQTTMessage) -> None:
    """Callback function for processing received MQTT messages."""
    try:
        parsed_mqtt_event: Dict[str, Any] = json.loads(mqtt_message.payload.decode('ASCII'))

        logger.info(f"[APP] Event Received | {mqtt_message.topic} | {mqtt_message.payload.decode('ASCII')}")
        logger.debug(f"[APP] Event Received | {mqtt_message.topic} | {mqtt_message.payload.decode('ASCII')}")

        for config_trigger in config['TRIGGERS']:
            # Check if the MQTT topic from the config matches the received MQTT message topic
            if config_trigger['MQTT_TOPIC'] != mqtt_message.topic:
                continue  # Skip to the next trigger if the topic doesn't match

            # Check if the MQTT event payload matches the trigger configuration
            if match_mqtt_event(parsed_mqtt_event, config_trigger, mqtt_message):
                logger.info(f"[APP] Event Matched  | {mqtt_message.topic} | {mqtt_message.payload.decode('ASCII')}")
                logger.debug(f"[APP] Event Matched  | {mqtt_message.topic} | {mqtt_message.payload.decode('ASCII')}")

                # Validate mode
                trigger_mode = config_trigger.get('MODE', '').lower()
                if not validate_mode(config_trigger, mqtt_message):
                    logger.error(f"[APP] Event Skipped  | {mqtt_message.topic} | {{\"event_mode\":\"MODE key not allowed\"}}")
                    break  # Exit the loop: We found a matching topic and event, but MODE is wrong.

				### Handle "CREATE" mode
                if trigger_mode == "create":
                    event_details = None
                    try:
                        event_details = create_event_details(config_trigger, parsed_mqtt_event)

                        # Check if 'action' key exists in the parsed MQTT event payload to perform action specific logging
                        if "action" in parsed_mqtt_event:
                            event_location = config_trigger.get('EVENT_LOCATION', '').replace('\\,', ',')
                            actioned_log_message = f"[APP] Event Actioned | {mqtt_message.topic} | {{\"event_mode\":\"{trigger_mode}\", \"event_summary\":\"{config_trigger.get('EVENT_SUMMARY', '')}\",\"event_location\":\"{event_location}\",\"event_duration\":\"{config_trigger.get('EVENT_DURATION', '')}\"}}"
                            logger.info(actioned_log_message)

                        create_caldav_event(caldav_client, event_details, mqtt_message.topic)
                        break  # Stop processing after create

                    except ValueError as e: # Catch ValueError from create_event_details
                        logger.error(f"[APP] Event Skipped  | {mqtt_message.topic} | {{\"event_offset\":\"Invalid EVENT_OFFSET value configured\"}}")
                        break
                    except KeyError as e:
                        logger.error(f"[APP] Event Skipped  | {mqtt_message.topic} | Config Error in trigger: Missing key: {e}")
                        break
                    except Exception as event_creation_error:
                        logger.error(f"[APP] Event Create Error | {mqtt_message.topic} | Unexpected Error: {type(event_creation_error).__name__}: {event_creation_error}")
                        break

				### Handle "DELETE" mode
                elif trigger_mode == "delete":
                    logger.info(f"[APP] Event Actioned | {mqtt_message.topic} | {{\"event_mode\":\"{trigger_mode}\"}}")

                    try:
                        event_url_to_delete = find_last_created_event_url()
                        if event_url_to_delete:
                            delete_caldav_event(caldav_client, event_url_to_delete, mqtt_message.topic)
                        else:
                            logger.warn(f"[APP] Event Skipped  | {mqtt_message.topic} | {{\"event_delete\":\"No event to delete found in logs\"}}")

                    except NotFoundError as e:
                        logger.error(f"[APP] Event Delete Error | {mqtt_message.topic} | Not Found Error: Event URL not found in logs")
                        break
                    except Exception as event_deletion_error:
                        logger.error(f"[APP] Event Delete Error | {mqtt_message.topic} | Unexpected Error: {type(event_deletion_error).__name__}: {event_deletion_error}")
                    break

    except json.JSONDecodeError as json_decode_error:
        logger.error(f"[APP] Invalid JSON: {mqtt_message.topic} | {mqtt_message.payload.decode('ASCII')} | {type(json_decode_error).__name__}: {json_decode_error}")
    except KeyError as e:
        logger.error(f"[APP] Processing Error | {mqtt_message.topic} | Config Error: Missing key in trigger or MQTT event: {e}")
    except Exception as generic_message_error:
        logger.error(f"[APP] Processing Error | {mqtt_message.topic} | Unexpected Error: {type(generic_message_error).__name__}: {generic_message_error}")




### FUNCTION :: Match MQTT Event #########################################################
def match_mqtt_event(mqtt_event: Dict[str, Any], trigger: Dict[str, Any], message: MQTTMessage) -> bool:
    """Checks if an MQTT event matches a trigger."""
    if trigger['MQTT_TOPIC'] != message.topic:
        return False

    for key, value in trigger['MQTT_EVENT'].items():
        if key not in mqtt_event or mqtt_event[key] != value:
            return False
    return True



### FUNCTION :: Validate 'MODE' value ####################################################
def validate_mode(trigger: Dict[str, Any], message: MQTTMessage) -> bool:
    """Validates the 'MODE' value after an MQTT event was received."""
    if 'MODE' not in trigger:
         return False

    allowed_modes = ["create", "delete"]
    if trigger.get('MODE', '').lower() not in allowed_modes:
       return False
    return True



### FUNCTION :: Round Event Time #########################################################
def roundTime(dt: Optional[datetime] = None, rounding_minutes: timedelta = timedelta(minutes=1)) -> datetime:
    """Rounds a datetime object to the nearest multiple of a given time delta."""
    roundTo = rounding_minutes.total_seconds()
    if dt is None:
        dt = datetime.now()
    seconds = (dt - dt.min).seconds
    rounding = (seconds + roundTo/2) // roundTo * roundTo
    return dt + timedelta(0, rounding-seconds, -dt.microsecond)



### FUNCTION :: Offset Event Time ########################################################
def adjust_event_time(now_datetime: datetime, offset: str) -> datetime:
    """Adjusts a datetime object by a given offset in minutes."""
    try:
        offset_minutes = int(offset)
        adjusted_time = now_datetime + timedelta(minutes=offset_minutes)
        return adjusted_time
    except ValueError:
        return now_datetime



### FUNCTION :: Collect Event Details ####################################################
def create_event_details(config_trigger: Dict[str, Any], parsed_mqtt_event: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Creates a dictionary containing event details based on the trigger and MQTT event."""
    now_datetime: datetime = datetime.now()
    original_now_datetime: datetime = now_datetime

    try:
        if config_trigger.get('EVENT_OFFSET') and config_trigger['EVENT_OFFSET'] != '0':
            now_datetime = adjust_event_time(now_datetime, config_trigger['EVENT_OFFSET'])

        if now_datetime == original_now_datetime and config_trigger.get('EVENT_OFFSET') and config_trigger['EVENT_OFFSET'] != '0':
            raise ValueError("Invalid EVENT_OFFSET value configured")

    except ValueError:
        raise

    if config_trigger['EVENT_ROUNDING'] and config_trigger['EVENT_ROUNDING'] != '0':
        now_datetime = roundTime(now_datetime, timedelta(minutes=int(config_trigger['EVENT_ROUNDING'])))

    end_datetime: datetime = now_datetime + timedelta(minutes=int(config_trigger['EVENT_DURATION']))

    if config_trigger['EVENT_SECONDS'].lower() == 'false':
        start_time = now_datetime.strftime('%Y%m%dT%H%M00')
        end_time = end_datetime.strftime('%Y%m%dT%H%M00')
    else:
        start_time = now_datetime.strftime('%Y%m%dT%H%M%S')
        end_time = end_datetime.strftime('%Y%m%dT%H%M%S')

    event_details: Dict[str, str] = {
        'start_time': start_time,
        'end_time': end_time,
        'event_calendar_url': config_trigger['EVENT_CALENDAR'],
        'event_timezone': config_trigger['EVENT_TIMEZONE'],
        'event_location': config_trigger['EVENT_LOCATION'],
        'event_description': config_trigger['EVENT_DESCRIPTION'],
        'event_url': config_trigger['EVENT_URL'],
        'event_summary': config_trigger['EVENT_SUMMARY'],
        'event_geo': config_trigger['EVENT_GEO'],
        'event_transp': config_trigger['EVENT_TRANSP'],
        'event_categories': config_trigger['EVENT_CATEGORIES'],
        'event_trigger': config_trigger['EVENT_TRIGGER']
    }

    return event_details



### FUNCTION :: Error Handling ###########################################################
def handle_error(message: str, exception: Exception, stage: str = "general") -> None:
    """Logs error messages consistently"""
    logger.error(f"[{stage}] Error: {message} | {type(exception).__name__}: {exception}")



### MAIN #################################################################################
if __name__ == '__main__':
    # Log Application Start
    logger.info(f"[SYS] App Load Successful           | {{\"app_name\":\"{APP_NAME}\", \"version\":\"{VERSION}\"}}")

    # Load MQTT Config File
    config = load_config()
    CALDAV_SERVER_ADDRESS = config['CALDAV_SERVER']['CALDAV_SERVER_ADDRESS']
    CALDAV_USERNAME = config['CALDAV_SERVER']['CALDAV_USERNAME']
    CALDAV_PASSWORD = config['CALDAV_SERVER']['CALDAV_PASSWORD']
    MQTT_SERVER_ADDRESS = config['MQTT_SERVER']['MQTT_SERVER_ADDRESS']
    MQTT_SERVER_PORT = config['MQTT_SERVER']['MQTT_SERVER_PORT']
    MQTT_USERNAME = config['MQTT_SERVER']['MQTT_USERNAME']
    MQTT_PASSWORD = config['MQTT_SERVER']['MQTT_PASSWORD']
    TRIGGERS = config['TRIGGERS']

    # Establish CalDAV Connection
    caldav_client = connect_caldav(CALDAV_SERVER_ADDRESS, CALDAV_USERNAME, CALDAV_PASSWORD)

    # Initialize MQTT Connection
    mqtt_client = mqttClient.Client(APP_NAME)
    mqtt_client.username_pw_set(MQTT_USERNAME, password=MQTT_PASSWORD)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = lambda client, userdata, message: on_message(caldav_client, client, userdata, message)
    mqtt_client.connect(MQTT_SERVER_ADDRESS, port=int(MQTT_SERVER_PORT))

    # Subscribe To MQTT Topics
    for trigger in TRIGGERS:
        mqtt_client.subscribe(trigger['MQTT_TOPIC'])

    # Start MQTT Background Loop
    mqtt_client.loop_start()
    try:
        while True:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                raise
            except Exception as loop_op_error:
                logger.error(f"[APP] Main Loop Error | {type(loop_op_error).__name__}: {loop_op_error}")
                continue

    # Handle User Keyboard Interrupts
    except KeyboardInterrupt:
        logger.warn("[USR] Keyboard Interrupt | Exit")
        mqtt_client.disconnect()
        mqtt_client.loop_stop()

    # Handle Main Loop Exceptions
    except Exception as e:
        logger.error(f"[APP] Main Loop Error | {type(e).__name__}: {e}")
        mqtt_client.disconnect()
        mqtt_client.loop_stop()
