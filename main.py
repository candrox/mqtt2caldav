### SECTION :: Version ###################################################################
VERSION = "20250830.1928"



### SECTION :: Module Imports ############################################################
# Standard
import errno
import json
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Third Party
import caldav
import requests
from caldav.lib.error import AuthorizationError, DAVError, NotFoundError
from paho.mqtt.client import Client as MQTTClient, MQTTMessage

# Local
from utils import logger
from utils.constants import (APP_NAME, CONFIG_DIR, LOG_DIR, LOG_FILE_NAME, SETTINGS_FILE_NAME, TRIGGERS_FILE_NAME, LOCK_FILE_PATH)



### FUNCTION :: Format Log Data ##########################################################
def format_log_data(data: Dict[str, Any]) -> str:
    """Formats a dictionary into a key='value' string."""
    return ", ".join([f"{key}='{value}'" for key, value in data.items()])



### FUNCTION :: Load Config File #########################################################
def load_config(settings_file: str = os.path.join(CONFIG_DIR, SETTINGS_FILE_NAME),
                triggers_file: str = os.path.join(CONFIG_DIR, TRIGGERS_FILE_NAME)) -> Dict[str, Any]:
    """Loads settings and triggers from JSON files and returns a merged dictionary."""
    global LOG_PREFIX_APPLICATION, LOG_PREFIX_CALDAV, LOG_PREFIX_MQTT, \
           LOG_PREFIX_SYSTEM, LOG_PREFIX_USER

    config: Dict[str, Any] = {}
    settings_path = ""
    triggers_path = ""

    try:
        if not os.path.isabs(settings_file):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            settings_path = os.path.join(script_dir, settings_file)
        else:
            settings_path = os.path.abspath(settings_file)

        with open(settings_path, 'r') as f:
            config = json.load(f)
            log_prefixes = config.get('APPLICATION_SETTINGS', {}).get('LOG_PREFIXES', {})
            LOG_PREFIX_APPLICATION = log_prefixes.get('APPLICATION', '[APP]')
            LOG_PREFIX_CALDAV = log_prefixes.get('CALDAV', '[DAV]')
            LOG_PREFIX_MQTT = log_prefixes.get('MQTT', '[MQT]')
            LOG_PREFIX_SYSTEM = log_prefixes.get('SYSTEM', '[SYS]')
            LOG_PREFIX_USER = log_prefixes.get('USER', '[USR]')

            settings_object_count = 0
            settings_array_count = 0
            settings_key_count = 0

            def _recursive_count(item):
                nonlocal settings_object_count, settings_array_count, settings_key_count
                if isinstance(item, dict):
                    settings_object_count += 1
                    settings_key_count += len(item.keys())
                    for v in item.values():
                         if isinstance(v, (dict, list)):
                             _recursive_count(v)
                elif isinstance(item, list):
                    settings_array_count += 1
                    for i in item:
                        if isinstance(i, (dict, list)):
                            _recursive_count(i)

            _recursive_count(config)

            log_data = {
                "app_conf_file": settings_path,
                "json_array_count": settings_array_count,
                "json_object_count": settings_object_count,
                "json_key_count": settings_key_count
            }
            logger.info(f"{LOG_PREFIX_APPLICATION} Settings File Load Successful | {format_log_data(log_data)}")

	# Handle Missing Settings File
    except FileNotFoundError as e:
        _LOG_PREFIX_APP_ERR = '[Application]'
        log_data = {"app_conf_file": settings_path, "exception_type": type(e).__name__, "details": str(e)}
        print(f"crit  {datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]}: {_LOG_PREFIX_APP_ERR} Settings File Not Found     | {format_log_data(log_data)}")
        sys.exit(1)

	# Handle Invalid Json Format In Settings File
    except json.JSONDecodeError as e:
        _LOG_PREFIX_APP_ERR = '[Application]'
        log_data = {"app_conf_file": settings_path, "exception_type": type(e).__name__, "details": str(e)}
        print(f"crit  {datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]}: {_LOG_PREFIX_APP_ERR} Invalid JSON in Settings    | {format_log_data(log_data)}")
        sys.exit(1)

    log_level_str = config.get('APPLICATION_SETTINGS', {}).get('LOG_LEVEL', 'INFO')
    logger.set_log_level(log_level_str)

    try:
        if not os.path.isabs(triggers_file):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            triggers_path = os.path.join(script_dir, triggers_file)
        else:
            triggers_path = os.path.abspath(triggers_file)

        with open(triggers_path, 'r') as f:
            triggers_list: List[Dict[str, Any]] = json.load(f)
            config['TRIGGERS'] = triggers_list

            for i, trigger in enumerate(triggers_list):
                if 'MQTT_EVENT' not in trigger:
                    log_data = {"trigger_index": i, "trigger_content": str(trigger), "reason": "Trigger definition missing 'MQTT_EVENT' key"}
                    logger.critical(f"{LOG_PREFIX_APPLICATION} Invalid Trigger Config      | {format_log_data(log_data)}")
                    sys.exit(1)

            trigger_object_count = 0
            trigger_array_count = 0
            trigger_key_count = 0

			# Count Json Elements
            def _recursive_count_triggers(item):
                nonlocal trigger_object_count, trigger_array_count, trigger_key_count
                if isinstance(item, dict):
                    trigger_object_count += 1
                    trigger_key_count += len(item.keys())
                    for v in item.values():
                         if isinstance(v, (dict, list)):
                             _recursive_count_triggers(v)
                elif isinstance(item, list):
                    trigger_array_count += 1
                    for i in item:
                        if isinstance(i, (dict, list)):
                            _recursive_count_triggers(i)

            _recursive_count_triggers(triggers_list) # Start counting from the root trigger list

            log_data = {
                "app_conf_file": triggers_path,
                "json_array_count": trigger_array_count,
                "json_object_count": trigger_object_count,
                "json_key_count": trigger_key_count
            }
            logger.info(f"{LOG_PREFIX_APPLICATION} Triggers File Load Successful | {format_log_data(log_data)}")

    # Handle Missing Triggers File
    except FileNotFoundError as e:
        log_data = {"app_conf_file": triggers_path, "exception_type": type(e).__name__, "details": str(e)}
        logger.error(f"{LOG_PREFIX_APPLICATION} Triggers File Not Found     | {format_log_data(log_data)}")
        config['TRIGGERS'] = []
        logger.warn(f"{LOG_PREFIX_APPLICATION} Continuing without triggers defined in file.")

	# Handle Invalid Json Format In Triggers File
    except json.JSONDecodeError as e:
        log_data = {"app_conf_file": triggers_path, "exception_type": type(e).__name__, "details": str(e)}
        logger.error(f"{LOG_PREFIX_APPLICATION} Invalid JSON in Triggers    | {format_log_data(log_data)}")
        sys.exit(1)

    # Handle Errors When Processing Triggers
    except Exception as e:
        log_data = {"app_conf_file": triggers_path, "exception_type": type(e).__name__, "details": str(e)}
        logger.error(f"{LOG_PREFIX_APPLICATION} Error processing Triggers   | {format_log_data(log_data)}")
        sys.exit(1)

    return config



### FUNCTION :: Connect CalDAV Server ####################################################
def connect_caldav(caldav_server_address: str, caldav_username: str, caldav_password: str) -> Optional[caldav.DAVClient]:
    """Connects to the CalDAV server and returns the client object, or None on failure."""
    caldav_host_info = f"{caldav_username}@{caldav_server_address}"
    try:
        caldav_client: caldav.DAVClient = caldav.DAVClient(url=caldav_server_address, username=caldav_username, password=caldav_password)
        my_principal = caldav_client.principal()
        calendars = my_principal.calendars()
        log_data_conn = {"caldav_host": caldav_host_info}
        if calendars:
            logger.info(f"{LOG_PREFIX_CALDAV} Server Connection Successful  | {format_log_data(log_data_conn)}")
            for calendar in calendars:
                log_data_cal = {
                    "caldav_calendar": calendar.name,
                    "caldav_calendar_path": str(calendar.url)
                }
                logger.info(f"{LOG_PREFIX_CALDAV} Calendar Resource Discovered  | {format_log_data(log_data_cal)}")
        else:
            log_data_debug = {"caldav_host": caldav_host_info, "detail": "No calendars found"}
            logger.debug(f"{LOG_PREFIX_CALDAV} Server Connection Successful  | {format_log_data(log_data_debug)}")
        return caldav_client

    # Handle CalDAV Authentication Errors
    except AuthorizationError as e:
        log_data = {"caldav_host": caldav_host_info, "reason": type(e).__name__, "details": str(e)}
        logger.error(f"{LOG_PREFIX_CALDAV} Server Connection Failed      | {format_log_data(log_data)}")
        return None

    # Handle CalDAV Server And Protocol Errors
    except DAVError as e:
        log_data = {"caldav_host": caldav_host_info, "reason": type(e).__name__, "details": str(e)}
        logger.error(f"{LOG_PREFIX_CALDAV} Server Connection Failed      | {format_log_data(log_data)}")
        return None

	# Handle Network Errors During Initial Connection Attempt
    except requests.exceptions.ConnectionError as e:
        log_data = {"caldav_host": caldav_host_info, "reason": "Connection Error", "exception_type": type(e).__name__, "details": str(e)}
        logger.error(f"{LOG_PREFIX_CALDAV} Server Connection Failed      | {format_log_data(log_data)}")
        return None

	# Handle Other Unexpected Errors
    except Exception as e:
        log_data = {"caldav_host": caldav_host_info, "reason": "Unexpected Error", "exception_type": type(e).__name__, "details": str(e)}
        logger.error(f"{LOG_PREFIX_CALDAV} Server Connection Failed      | {format_log_data(log_data)}")
        return None



### FUNCTION :: Create CalDAV Event ######################################################
def create_caldav_event(caldav_client: caldav.DAVClient, event_details: Optional[Dict[str, Any]], topic: str) -> None:
    """Creates an event on the CalDAV server with retry logic for network errors."""
    if event_details is None:
        log_data_payload = {"reason": "Internal Error - event_details is None"}
        logger.error(f"{LOG_PREFIX_CALDAV} Event Create Error | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")
        return
    try:
        start_time = event_details['start_time']
        end_time = event_details['end_time']
        mqtt_action = event_details.get('mqtt_action', 'unknown')

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

        max_attempts = config.get('CALDAV_SERVER', {}).get('CALDAV_EVENT_RETRY_ATTEMPTS', 3)
        initial_retry_delay = config.get('CALDAV_SERVER', {}).get('CALDAV_EVENT_RETRY_DELAY_SECONDS', 60)
        initial_retry_delay = max(1, int(initial_retry_delay))
        event_calendar_url = event_details['event_calendar_url']

        current_delay = initial_retry_delay

        for attempt in range(max_attempts):
            is_retryable_error = False
            try:
                event_calendar = None
                try:
                    event_calendar = caldav.Calendar(client=caldav_client, url=event_calendar_url)
                except Exception as cal_init_e: # Catch any exception during Calendar object instantiation
                    # Log specific error for instantiation failure
                    # current_attempt here refers to the outer loop's attempt count for the whole operation
                    log_data_instantiation_error_payload = {
                        "attempt": attempt + 1,
                        "max_attempts": max_attempts,
                        "reason": "Calendar Object Instantiation Failed",
                        "calendar_url": str(event_calendar_url), # Ensure URL is string for logging
                        "exception_type": type(cal_init_e).__name__,
                        "details": str(cal_init_e)
                    }
                    logger.error(f"{LOG_PREFIX_CALDAV} Event Create Error (Instantiation) | {format_log_data({'mqtt_topic': topic, **log_data_instantiation_error_payload})}")
                    raise cal_init_e # Re-raise the exception to be caught by the outer handlers

                # If instantiation was successful, event_calendar is now set.
                caldav_event = event_calendar.save_event(str_event)
                log_data_payload = {
                    "action": mqtt_action,
                    "event_path": str(caldav_event.url)
                }
                logger.info(f"{LOG_PREFIX_CALDAV} Event Created  | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")
                return

			# Handle CalDAV Event Create Errors
            except DAVError as e:
                current_attempt = attempt + 1
                if e.args and isinstance(e.args[0], requests.exceptions.RequestException):
                    is_retryable_error = True
                    log_data_payload = {"attempt": current_attempt, "max_attempts": max_attempts, "reason": "Network Error", "exception_type": type(e.args[0]).__name__, "details": str(e.args[0])}
                    logger.error(f"{LOG_PREFIX_CALDAV} Event Create Error | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")
                else:
                    log_data_payload = {"attempt": current_attempt, "max_attempts": max_attempts, "reason": "CalDAV Server Error", "exception_type": type(e).__name__, "details": str(e)}
                    logger.error(f"{LOG_PREFIX_CALDAV} Event Create Error | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")

			# Handle CalDAV Network Errors During Event Creation
            except requests.exceptions.RequestException as e:
                is_retryable_error = True
                current_attempt = attempt + 1
                log_data_payload = {"attempt": current_attempt, "max_attempts": max_attempts, "reason": "Network Error", "exception_type": type(e).__name__, "details": str(e)}
                logger.error(f"{LOG_PREFIX_CALDAV} Event Create Error | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")

            # Handle Remaining CalDAV Event Creation Exceptions
            except Exception as e:
                current_attempt = attempt + 1
                if isinstance(e, requests.exceptions.RequestException) or \
                   (hasattr(e, 'args') and e.args and isinstance(e.args[0], requests.exceptions.RequestException)) or \
                   'ConnectionError' in str(e) or 'Temporary failure in name resolution' in str(e) or 'Failed to establish a new connection' in str(e):
                    is_retryable_error = True
                    log_data_payload = {"attempt": current_attempt, "max_attempts": max_attempts, "reason": "Likely Network Error", "exception_type": type(e).__name__, "details": str(e)}
                    logger.error(f"{LOG_PREFIX_CALDAV} Event Create Error | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")
                else:
                    log_data_payload = {"attempt": current_attempt, "max_attempts": max_attempts, "reason": "Unexpected Error", "exception_type": type(e).__name__, "details": str(e)}
                    logger.error(f"{LOG_PREFIX_CALDAV} Event Create Error | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")
                    break

            if is_retryable_error:
                if attempt + 1 < max_attempts:
                    log_data_retry = {
                        "mqtt_topic": topic, # This log message does not start with "Event ", so it's unchanged.
                        "original_action": mqtt_action,
                        "next_attempt": attempt + 2,
                         "max_attempts": max_attempts,
                        "delay_seconds": current_delay
                    }
                    logger.info(f"{LOG_PREFIX_CALDAV} Retry Started  | {format_log_data(log_data_retry)}")
                    time.sleep(current_delay)
                    current_delay *= 2
                else:
                    log_data_fail_payload = {"reason": "Failed after max attempts", "attempts": max_attempts, "final_cause": "Network Errors"}
                    logger.error(f"{LOG_PREFIX_CALDAV} Event Create Error | {format_log_data({'mqtt_topic': topic, **log_data_fail_payload})}")
            else:
                break

	# Handle Missing Trigger Keys
    except KeyError as e:
        log_data_payload = {"reason": "Config Error - Missing event detail key", "key": str(e)}
        logger.error(f"{LOG_PREFIX_CALDAV} Event Create Error | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")

	# Handle Missing Trigger Values
    except ValueError as e:
        log_data_payload = {"reason": "Data Error - Invalid event detail value", "details": str(e)}
        logger.error(f"{LOG_PREFIX_CALDAV} Event Create Error | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")

	# Handle Type Errors
    except TypeError as e:
         if 'int()' in str(e) and 'CALDAV_EVENT_RETRY_DELAY_SECONDS' in str(config.get('CALDAV_SERVER', {})):
              log_data = {"reason": "Config Error - CALDAV_EVENT_RETRY_DELAY_SECONDS must be an integer", "value": config.get('CALDAV_SERVER', {}).get('CALDAV_EVENT_RETRY_DELAY_SECONDS')}
              logger.error(f"{LOG_PREFIX_APPLICATION} Invalid Config     | {format_log_data(log_data)}")
         else:
              log_data = {"mqtt_topic": topic, "reason": "Data Type Error during event processing", "details": str(e)} # This log message does not start with "Event "
              logger.error(f"{LOG_PREFIX_APPLICATION} Processing Error   | {format_log_data(log_data)}")




### FUNCTION :: Delete CalDAV Event ######################################################
def delete_caldav_event(caldav_client: caldav.DAVClient, event_url: str, topic: str, action: Optional[str] = None) -> None:
    """Deletes a CalDAV event from the server."""
    try:
        event = caldav.Event(client=caldav_client, url=event_url)
        event.delete()
        log_data_payload = {
            "action": action if action else "unknown",
            "event_path": event_url
        }
        logger.info(f"{LOG_PREFIX_CALDAV} Event Deleted  | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")

	# Handle CalDAV Event Not Found
    except NotFoundError as e:
        log_data_payload = {"reason": "Not Found Error", "event_url": event_url}
        logger.error(f"{LOG_PREFIX_CALDAV} Event Delete Error | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")

	# Handle CalDAV Server Errors
    except DAVError as e:
        log_data_payload = {"reason": "CalDAV Server Error", "exception_type": type(e).__name__, "details": str(e)}
        logger.error(f"{LOG_PREFIX_CALDAV} Event Delete Error | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")

	# Handle Unexpected Errors
    except Exception as e:
        log_data_payload = {"reason": "Unexpected Error", "exception_type": type(e).__name__, "details": str(e)}
        logger.error(f"{LOG_PREFIX_CALDAV} Event Delete Error | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")



### FUNCTION :: Find Last Created Event ##################################################
def find_last_created_event_url() -> Optional[str]:
    """Searches the log file for the last created event URL that has not been deleted."""
    log_file_path = os.path.join(LOG_DIR, LOG_FILE_NAME)
    if not os.path.exists(log_file_path):
        return None

    deleted_event_urls = set()

    try:
        with open(log_file_path, 'r') as logfile:
            lines = logfile.readlines()

            for line in reversed(lines):
                if " | " not in line or "event_path='" not in line:
                    continue

                try:
                    data_str = line.split(" | ", 1)[1]
                    path_part = data_str.split("event_path='")[1]
                    event_url = path_part.split("'")[0]
                except IndexError:
                    continue

                if f"{LOG_PREFIX_CALDAV} Event Deleted" in line:
                    deleted_event_urls.add(event_url)

                elif f"{LOG_PREFIX_CALDAV} Event Created" in line:
                    if event_url not in deleted_event_urls:
                        return event_url

    except (IOError, Exception) as e:
        log_data = {"file_path": log_file_path, "exception_type": type(e).__name__, "details": str(e)}
        logger.error(f"{LOG_PREFIX_APPLICATION} Log Parsing Error    | {format_log_data(log_data)}")
        return None

    return None



### FUNCTION :: Connect MQTT Broker ######################################################
def on_connect(client: MQTTClient, userdata, flags, rc: int) -> None:
    """Callback function for MQTT connection events. Logs the connection status."""
    mqtt_host_info = f"{config['MQTT_SERVER']['MQTT_USERNAME']}@{config['MQTT_SERVER']['MQTT_SERVER_ADDRESS']}:{config['MQTT_SERVER']['MQTT_SERVER_PORT']}"
    log_data = {"mqtt_host": mqtt_host_info}
    if rc == 0:
        logger.info(f"{LOG_PREFIX_MQTT} Broker Connection Successful  | {format_log_data(log_data)}")

        # Subscribe To MQTT Topics
        triggers = config.get('TRIGGERS', [])
        unique_topics_subscribed = set()
        if not triggers:
            log_data_no_triggers = {'reason': 'No triggers defined in configuration, MQTT client will listen but perform no actions.'}
            logger.warn(f"{LOG_PREFIX_MQTT} Config Error       | {format_log_data(log_data_no_triggers)}")

        for trigger in triggers:
            try:
                topic_to_subscribe = trigger['MQTT_TOPIC']
                if topic_to_subscribe not in unique_topics_subscribed:
                    client.subscribe(topic_to_subscribe)
                    unique_topics_subscribed.add(topic_to_subscribe)
                    logger.info(f"{LOG_PREFIX_MQTT} Topic Subscription Successful | mqtt_topic='{topic_to_subscribe}'")

            # Handle Triggers Without An MQTT_TOPIC Key
            except KeyError:
                log_data_err = {"trigger_details": str(trigger), "reason": "Trigger definition missing 'MQTT_TOPIC' key"}
                logger.error(f"{LOG_PREFIX_APPLICATION} Invalid Trigger Skipped | {format_log_data(log_data_err)}")

            # Handle Unexpected Errors During Subscription Process.
            except Exception as sub_e:
                 log_data_err = {"mqtt_topic": trigger.get('MQTT_TOPIC', 'N/A'), "reason": "Error during MQTT subscription", "exception_type": type(sub_e).__name__, "details": str(sub_e)}
                 logger.error(f"{LOG_PREFIX_MQTT} Subscription Error | {format_log_data(log_data_err)}")
    else:
        log_data["return_code"] = rc
        logger.error(f"{LOG_PREFIX_MQTT} Broker Connection Failed      | {format_log_data(log_data)}")



### FUNCTION :: Process MQTT Message #####################################################
def on_message(caldav_client: caldav.DAVClient, mqtt_client: MQTTClient, userdata, mqtt_message: MQTTMessage) -> None:
    """Callback function for processing received MQTT messages."""
    topic = mqtt_message.topic
    payload_str = mqtt_message.payload.decode('utf-8')

    if caldav_client is None:
        log_data = {"mqtt_topic": topic, "reason": "CalDAV client not initialized, cannot process message"} # This log message does not start with "Event "
        logger.error(f"{LOG_PREFIX_APPLICATION} Processing Error   | {format_log_data(log_data)}")
        return

    try:
        parsed_mqtt_event: Dict[str, Any] = json.loads(payload_str)
        mqtt_action = parsed_mqtt_event.get('action', 'unknown')
        log_data_received = {'mqtt_topic': topic, **parsed_mqtt_event}
        logger.info(f"{LOG_PREFIX_APPLICATION} Event Received | {format_log_data(log_data_received)}")

        for config_trigger in config.get('TRIGGERS', []):
            if config_trigger['MQTT_TOPIC'] != topic:
                continue

            if match_mqtt_event(parsed_mqtt_event, config_trigger, mqtt_message):
                log_data_matched = {'mqtt_topic': topic, **parsed_mqtt_event}
                logger.info(f"{LOG_PREFIX_APPLICATION} Event Matched  | {format_log_data(log_data_matched)}")

                trigger_mode = config_trigger.get('MODE', '').lower()
                if not validate_mode(config_trigger, mqtt_message):
                    log_data_payload = {
                        "action": mqtt_action,
                        "reason": "MODE key not allowed or missing"
                    }
                    logger.error(f"{LOG_PREFIX_APPLICATION} Event Skipped  | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")
                    break

                if trigger_mode == "create":
                    event_details = None
                    try:
                        event_details = create_event_details(config_trigger, mqtt_action)

                        if "action" in parsed_mqtt_event:
                            event_location = config_trigger.get('EVENT_LOCATION', '').replace('\\,', ',')
                            log_data_payload = {
                                "action": mqtt_action,
                                "event_mode": trigger_mode,
                                "event_summary": config_trigger.get('EVENT_SUMMARY', ''),
                                "event_location": event_location,
                                "event_duration": config_trigger.get('EVENT_DURATION', '')
                            }
                            logger.info(f"{LOG_PREFIX_APPLICATION} Event Actioned | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")

                        create_caldav_event(caldav_client, event_details, topic)
                        break

					# Handle Invalid Configuration Value
                    except ValueError as e:
                        log_data_payload = {
                            "action": mqtt_action,
                            "reason": "Invalid EVENT_OFFSET value configured"
                        }
                        logger.error(f"{LOG_PREFIX_APPLICATION} Event Skipped  | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")
                        break

					# Handle Missing Configuration Value
                    except KeyError as e:
                        log_data_payload = {
                            "action": mqtt_action,
                            "reason": "Config Error in trigger - Missing key",
                            "key": str(e)
                        }
                        logger.error(f"{LOG_PREFIX_APPLICATION} Event Skipped  | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")
                        break

					# Handle Unexpected Errors
                    except Exception as event_creation_error:
                        log_data_payload = {"reason": "Unexpected Error during creation handling", "exception_type": type(event_creation_error).__name__, "details": str(event_creation_error)}
                        logger.error(f"{LOG_PREFIX_APPLICATION} Event Create Error | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")
                        break


                elif trigger_mode == "delete":
                    log_data_action_payload = {
                        "action": mqtt_action,
                        "event_mode": trigger_mode
                    }
                    logger.info(f"{LOG_PREFIX_APPLICATION} Event Actioned | {format_log_data({'mqtt_topic': topic, **log_data_action_payload})}")

                    try:
                        event_url_to_delete = find_last_created_event_url()
                        if event_url_to_delete:
                            delete_caldav_event(caldav_client, event_url_to_delete, topic, action=mqtt_action)
                        else:
                            log_data_skip_payload = {
                                "action": mqtt_action,
                                "reason": "No event to delete found in logs"
                            }
                            logger.warn(f"{LOG_PREFIX_APPLICATION} Event Skipped  | {format_log_data({'mqtt_topic': topic, **log_data_skip_payload})}")

					# Handle Unexpected Deletion Errors
                    except Exception as event_deletion_error:
                        log_data_payload = {"reason": "Unexpected Error during deletion handling", "exception_type": type(event_deletion_error).__name__, "details": str(event_deletion_error)}
                        logger.error(f"{LOG_PREFIX_APPLICATION} Event Delete Error | {format_log_data({'mqtt_topic': topic, **log_data_payload})}")
                    break

	# Handle MQTT Payload Decoding Errors
    except json.JSONDecodeError as json_decode_error:
        log_data = {"mqtt_topic": topic, "payload": payload_str, "exception_type": type(json_decode_error).__name__, "details": str(json_decode_error)} # This log message does not start with "Event "
        logger.error(f"{LOG_PREFIX_APPLICATION} Invalid JSON Received         | {format_log_data(log_data)}")

	# Handle Missing MQTT Key Errors
    except KeyError as e:
        log_data = {"mqtt_topic": topic, "reason": "Config Error - Missing key in trigger or MQTT event", "key": str(e)} # This log message does not start with "Event "
        logger.error(f"{LOG_PREFIX_APPLICATION} Processing Error   | {format_log_data(log_data)}")

	# Handle Unexpected Errors
    except Exception as generic_message_error:
        log_data = {"mqtt_topic": topic, "reason": "Unexpected Error", "exception_type": type(generic_message_error).__name__, "details": str(generic_message_error)} # This log message does not start with "Event "
        logger.error(f"{LOG_PREFIX_APPLICATION} Processing Error   | {format_log_data(log_data)}")



### FUNCTION :: Match MQTT Event #########################################################
def match_mqtt_event(mqtt_event: Dict[str, Any], trigger: Dict[str, Any], message: MQTTMessage) -> bool:
    """Checks if an MQTT event matches a trigger."""
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

	# Handle Non-Integer Offset Value
    except ValueError:
        raise ValueError("Invalid offset value")



### FUNCTION :: Collect Event Details ####################################################
def create_event_details(config_trigger: Dict[str, Any], mqtt_action: str) -> Optional[Dict[str, Any]]:
    """Creates a dictionary containing event details based on the trigger and MQTT event."""
    now_datetime: datetime = datetime.now()
    try:
        event_offset = config_trigger.get('EVENT_OFFSET')
        if event_offset and event_offset != '0':
            adjusted_time = adjust_event_time(now_datetime, event_offset)
            if adjusted_time == now_datetime:
                 raise ValueError("Invalid EVENT_OFFSET value configured")
            now_datetime = adjusted_time

	# Handle Invalid Trigger Event Offset
    except ValueError as e:
        raise ValueError(f"Invalid EVENT_OFFSET value configured: {event_offset}") from e

	# Handle Missing Trigger Event Offset
    except KeyError as e:
        raise KeyError(f"Missing EVENT_OFFSET key in trigger config") from e

    try:
        event_rounding = config_trigger.get('EVENT_ROUNDING')
        if event_rounding and event_rounding != '0':
            now_datetime = roundTime(now_datetime, timedelta(minutes=int(event_rounding)))

        event_duration = config_trigger.get('EVENT_DURATION')
        if not event_duration:
            raise KeyError("Missing EVENT_DURATION key in trigger config")
        end_datetime: datetime = now_datetime + timedelta(minutes=int(event_duration))

        event_seconds = config_trigger.get('EVENT_SECONDS', 'False')
        use_seconds = str(event_seconds).lower() == 'true'
        if not use_seconds:
            start_time = now_datetime.strftime('%Y%m%dT%H%M00')
            end_time = end_datetime.strftime('%Y%m%dT%H%M00')
        else:
            start_time = now_datetime.strftime('%Y%m%dT%H%M%S')
            end_time = end_datetime.strftime('%Y%m%dT%H%M%S')

        required_keys = [
            'EVENT_CALENDAR', 'EVENT_TIMEZONE', 'EVENT_LOCATION', 'EVENT_DESCRIPTION',
            'EVENT_URL', 'EVENT_SUMMARY', 'EVENT_GEO', 'EVENT_TRANSP',
            'EVENT_CATEGORIES', 'EVENT_TRIGGER'
        ]
        for key in required_keys:
            if key not in config_trigger:
                raise KeyError(f"Missing required key in trigger config: {key}")

        event_details: Dict[str, Any] = {
            'mqtt_action': mqtt_action,
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

	# Handle Trigger Non-Integer Value
    except (ValueError, TypeError) as e:
         raise ValueError(f"Invalid non-integer value for EVENT_ROUNDING or EVENT_DURATION: {e}") from e

	# Handle Trigger Missing Key
    except KeyError as e:
        raise KeyError(f"Missing key in trigger config during event detail creation: {e}") from e



### MAIN #################################################################################
if __name__ == '__main__':
    # Log application start as the very first operational log message
    _app_path_init = os.path.abspath(__file__)
    _app_pid_init = os.getpid()
    _log_data_app_start = {
        "app_main_file": _app_path_init,
        "app_name": APP_NAME,
        "app_version": VERSION,
        "app_pid": _app_pid_init
    }
    logger.info(f"[SYS] Application Start Initiated   | {format_log_data(_log_data_app_start)}")

    config = load_config()
    app_path = os.path.abspath(__file__)
    log_data_start = {"app_main_file": app_path, "app_name": APP_NAME, "app_version": VERSION}
    logger.info(f"{LOG_PREFIX_SYSTEM} Application Load Successful   | {format_log_data(log_data_start)}")

    # Check Lock File
    if os.path.exists(LOCK_FILE_PATH):
        pid = "unknown"
        try:
            with open(LOCK_FILE_PATH, 'r') as f:
                pid_str = f.read().strip()
                pid = int(pid_str)

            try:
                os.kill(pid, 0)
                log_data_lock = {"app_lock_file": LOCK_FILE_PATH, "app_pid": pid}
                logger.error(f"{LOG_PREFIX_SYSTEM} Application Lock File Exists  | {format_log_data(log_data_lock)}")
                logger.critical(f"{LOG_PREFIX_SYSTEM} Application Already Running?  | {format_log_data(log_data_lock)}")
                sys.exit(1)

			# Handle Lock File Errors For Non-existent Process
            except OSError as e:
                if e.errno == errno.ESRCH:
                    log_data_stale = {"app_lock_file": LOCK_FILE_PATH, "app_pid": pid, "reason": "PID not found, assuming stale lock file"}
                    logger.warn(f"{LOG_PREFIX_SYSTEM} Stale Lock File Detected      | {format_log_data(log_data_stale)}")
                    try:
                        os.remove(LOCK_FILE_PATH)
                        log_data_removed = {"app_lock_file": LOCK_FILE_PATH}
                        logger.info(f"{LOG_PREFIX_SYSTEM} Stale Lock File Removed       | {format_log_data(log_data_removed)}")

					# Handle Stale Lock File Errors
                    except OSError as remove_e:
                        log_data_remove_err = {"app_lock_file": LOCK_FILE_PATH, "reason": "Failed to remove stale lock file", "exception_type": type(remove_e).__name__, "details": str(remove_e)}
                        logger.error(f"{LOG_PREFIX_SYSTEM} Application Lock File Error   | {format_log_data(log_data_remove_err)}")
                        sys.exit(1)
                elif e.errno == errno.EPERM:
                    log_data_perm = {"app_lock_file": LOCK_FILE_PATH, "app_pid": pid, "reason": "Permission error checking PID, assuming process is running"}
                    logger.error(f"{LOG_PREFIX_SYSTEM} Application Lock File Exists  | {format_log_data(log_data_perm)}")
                    logger.critical(f"{LOG_PREFIX_SYSTEM} Application Already Running?  | {format_log_data(log_data_perm)}")
                    sys.exit(1)
                else:
                    log_data_oserr = {"app_lock_file": LOCK_FILE_PATH, "app_pid": pid, "reason": "OS error checking PID", "exception_type": type(e).__name__, "details": str(e)}
                    logger.error(f"{LOG_PREFIX_SYSTEM} Lock File Check Error       | {format_log_data(log_data_oserr)}")
                    sys.exit(1)

		# Handle Lock File Content Errors
        except (ValueError, FileNotFoundError, IOError) as e:
            log_data_invalid = {"app_lock_file": LOCK_FILE_PATH, "pid_read": pid, "reason": "Invalid or unreadable lock file content, assuming stale", "exception_type": type(e).__name__, "details": str(e)}
            logger.warn(f"{LOG_PREFIX_SYSTEM} Invalid Lock File Detected    | {format_log_data(log_data_invalid)}")
            try:
                if os.path.exists(LOCK_FILE_PATH):
                    os.remove(LOCK_FILE_PATH)
                    log_data_removed = {"app_lock_file": LOCK_FILE_PATH}
                    logger.info(f"{LOG_PREFIX_SYSTEM} Invalid Lock File Removed     | {format_log_data(log_data_removed)}")

			# Handle Invalid Lock File Errors
            except OSError as remove_e:
                log_data_remove_err = {"app_lock_file": LOCK_FILE_PATH, "reason": "Failed to remove invalid lock file", "exception_type": type(remove_e).__name__, "details": str(remove_e)}
                logger.error(f"{LOG_PREFIX_SYSTEM} Application Lock File Error   | {format_log_data(log_data_remove_err)}")
                sys.exit(1)

    if not os.path.exists(LOCK_FILE_PATH):
        try:
            with open(LOCK_FILE_PATH, 'w') as f:
                f.write(str(os.getpid()))
            log_data_lock = {"app_lock_file": LOCK_FILE_PATH, "app_pid": os.getpid()}
            logger.info(f"{LOG_PREFIX_SYSTEM} Application Lock File Created | {format_log_data(log_data_lock)}")
        except Exception as e:
            log_data_lock_err = {"app_lock_file": LOCK_FILE_PATH, "reason": "Failed to create lock file", "exception_type": type(e).__name__, "details": str(e)}
            logger.critical(f"{LOG_PREFIX_SYSTEM} Application Lock File Error   | {format_log_data(log_data_lock_err)}")
            sys.exit(1)

    try:
        CALDAV_SERVER_ADDRESS = config['CALDAV_SERVER']['CALDAV_SERVER_ADDRESS']
        CALDAV_USERNAME = config['CALDAV_SERVER']['CALDAV_USERNAME']
        CALDAV_PASSWORD = config['CALDAV_SERVER']['CALDAV_PASSWORD']
        MQTT_SERVER_ADDRESS = config['MQTT_SERVER']['MQTT_SERVER_ADDRESS']
        MQTT_SERVER_PORT = config['MQTT_SERVER']['MQTT_SERVER_PORT']
        MQTT_USERNAME = config['MQTT_SERVER']['MQTT_USERNAME']
        MQTT_PASSWORD = config['MQTT_SERVER']['MQTT_PASSWORD']
        TRIGGERS = config.get('TRIGGERS', [])

    # Handle Essential Key Configuration Errors
    except KeyError as e:
        log_data_key_error = {"reason": "Missing essential configuration key in settings.json", "key": str(e)}
        logger.critical(f"{LOG_PREFIX_APPLICATION} Config Error       | {format_log_data(log_data_key_error)}")
        if os.path.exists(LOCK_FILE_PATH):
            try:
                os.remove(LOCK_FILE_PATH)
            except Exception as lock_e:
                 log_data_lock_rem_err = {"app_lock_file": LOCK_FILE_PATH, "reason": "Failed to remove lock file on config error exit", "exception_type": type(lock_e).__name__, "details": str(lock_e)}
                 logger.error(f"{LOG_PREFIX_SYSTEM} Application Lock File Error   | {format_log_data(log_data_lock_rem_err)}")
        sys.exit(1)

	# Handle Unexpected Configuration Access Errors
    except Exception as e:
        log_data_other_error = {"reason": "Unexpected error accessing configuration", "exception_type": type(e).__name__, "details": str(e)}
        logger.critical(f"{LOG_PREFIX_APPLICATION} Config Error       | {format_log_data(log_data_other_error)}")
        if os.path.exists(LOCK_FILE_PATH):
            try:
                os.remove(LOCK_FILE_PATH)
            except Exception as lock_e:
                 log_data_lock_rem_err = {"app_lock_file": LOCK_FILE_PATH, "reason": "Failed to remove lock file on config error exit", "exception_type": type(lock_e).__name__, "details": str(lock_e)}
                 logger.error(f"{LOG_PREFIX_SYSTEM} Application Lock File Error   | {format_log_data(log_data_lock_rem_err)}")
        sys.exit(1)

    # Establish CalDAV Connection
    caldav_client = None
    try:
        max_caldav_attempts = int(config.get('CALDAV_SERVER', {}).get('CALDAV_SERVER_RETRY_ATTEMPTS', 3))
        if max_caldav_attempts <= 0: max_caldav_attempts = 3

    # Handle Non-Integer Retry Attempts
    except (ValueError, TypeError):
        config_value = config.get('CALDAV_SERVER', {}).get('CALDAV_SERVER_RETRY_ATTEMPTS', 'Not Found')
        log_data_warn = {"reason": "Invalid config value type", "config_key": "CALDAV_SERVER_RETRY_ATTEMPTS", "value": config_value}
        logger.warn(f"{LOG_PREFIX_APPLICATION} Config Error       | {format_log_data(log_data_warn)}")
        max_caldav_attempts = 3

    try:
        caldav_retry_delay = int(config.get('CALDAV_SERVER', {}).get('CALDAV_SERVER_RETRY_DELAY_SECONDS', 10))
        if caldav_retry_delay < 0: caldav_retry_delay = 10

	# Handle CalDAV Server Retry Delay Second Errors
    except (ValueError, TypeError):
        config_value = config.get('CALDAV_SERVER', {}).get('CALDAV_SERVER_RETRY_DELAY_SECONDS', 'Not Found')
        log_data_warn = {"reason": "Invalid config value type", "config_key": "CALDAV_SERVER_RETRY_DELAY_SECONDS", "value": config_value}
        logger.warn(f"{LOG_PREFIX_APPLICATION} Invalid or missing CALDAV_SERVER_RETRY_DELAY_SECONDS, using default: 10 | {format_log_data(log_data_warn)}")
        caldav_retry_delay = 10

    for attempt in range(max_caldav_attempts):
        caldav_host_info = f"{CALDAV_USERNAME}@{CALDAV_SERVER_ADDRESS}"
        log_data_conn_init = {"caldav_host": caldav_host_info, "attempt": attempt + 1, "max_attempts": max_caldav_attempts}
        logger.info(f"{LOG_PREFIX_CALDAV} Server Connection Initiated   | {format_log_data(log_data_conn_init)}")

        caldav_client = connect_caldav(CALDAV_SERVER_ADDRESS, CALDAV_USERNAME, CALDAV_PASSWORD)
        if caldav_client is not None:
            break
        else:
            if attempt < max_caldav_attempts - 1:
                log_data_retry = {"caldav_host": caldav_host_info, "attempt": attempt + 1, "max_attempts": max_caldav_attempts, "delay_seconds": caldav_retry_delay}
                logger.warn(f"{LOG_PREFIX_CALDAV} Server Connection Retry...    | {format_log_data(log_data_retry)}")
                time.sleep(caldav_retry_delay)
            else:
                pass

    if caldav_client is None:
        log_data_exit = {"reason": f"Initial CalDAV connection failed after {max_caldav_attempts} attempts. Cannot proceed."}
        logger.critical(f"{LOG_PREFIX_SYSTEM} Application Exit              | {format_log_data(log_data_exit)}")
        if os.path.exists(LOCK_FILE_PATH):
            try:
                os.remove(LOCK_FILE_PATH)
            except Exception as lock_e:
                 log_data_lock_rem_err = {"app_lock_file": LOCK_FILE_PATH, "reason": "Failed to remove lock file on CalDAV connection exit", "exception_type": type(lock_e).__name__, "details": str(lock_e)}
                 logger.error(f"{LOG_PREFIX_SYSTEM} Application Lock File Error   | {format_log_data(log_data_lock_rem_err)}")
        sys.exit(1)

    # Initialize MQTT Connection
    mqtt_client = MQTTClient(APP_NAME)
    mqtt_client.username_pw_set(MQTT_USERNAME, password=MQTT_PASSWORD)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = lambda client, userdata, message: on_message(caldav_client, client, userdata, message)

    # Define Signal Handler
    def shutdown_handler(signum, frame):
        try:
            signal_name = signal.Signals(signum).name
        except AttributeError:
            signal_name = str(signum)

        shutdown_reason = "Shutdown Signal Received"
        if signum == signal.SIGINT:
            shutdown_reason = "Keyboard Interrupt Signal Received"
        elif signum == signal.SIGTERM:
            shutdown_reason = "Termination Signal Received"

        log_data = {"reason": shutdown_reason, "signal": signal_name}
        logger.warn(f"{LOG_PREFIX_SYSTEM} Initiating Graceful Shutdown  | {format_log_data(log_data)}")
        try:
            if mqtt_client.is_connected():
                mqtt_host_info_shutdown = f"{config.get('MQTT_SERVER', {}).get('MQTT_USERNAME', 'unknown')}@{config.get('MQTT_SERVER', {}).get('MQTT_SERVER_ADDRESS', 'unknown')}:{config.get('MQTT_SERVER', {}).get('MQTT_SERVER_PORT', 'unknown')}"
                log_data_disc_init = {"mqtt_host": mqtt_host_info_shutdown}
                logger.info(f"{LOG_PREFIX_SYSTEM} MQTT Disconnect Initiated     | {format_log_data(log_data_disc_init)}")
                mqtt_client.loop_stop()
                mqtt_client.disconnect()
            else:
                logger.info(f"{LOG_PREFIX_SYSTEM} MQTT client found but not connected, skipping disconnect.")
        except NameError:
            log_data_err = {"reason": "MQTT client or config not initialized when shutdown requested."}
            logger.error(f"{LOG_PREFIX_SYSTEM} MQTT Disconnect Error         | {format_log_data(log_data_err)}")
        # Handle MQTT Disconnect Errors
        except Exception as e:
            log_data_err = {"details": str(e), "exception_type": type(e).__name__}
            logger.error(f"{LOG_PREFIX_SYSTEM} MQTT Disconnect Error         | {format_log_data(log_data_err)}")

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    # Establish MQTT Connection
    try:
        mqtt_host_info_init = f"{MQTT_USERNAME}@{MQTT_SERVER_ADDRESS}:{MQTT_SERVER_PORT}"
        log_data_mqtt_init = {"mqtt_host": mqtt_host_info_init}
        logger.info(f"{LOG_PREFIX_MQTT} Broker Connection Initiated   | {format_log_data(log_data_mqtt_init)}")
        mqtt_port = int(MQTT_SERVER_PORT)
        mqtt_client.connect(MQTT_SERVER_ADDRESS, port=mqtt_port)

	# Handle MQTT Port Errors
    except ValueError as e:
        mqtt_host_info_fail = f"{MQTT_USERNAME}@{MQTT_SERVER_ADDRESS}:{MQTT_SERVER_PORT}"
        log_data = {"mqtt_host": mqtt_host_info_fail, "reason": "Invalid MQTT Port configured", "exception_type": type(e).__name__, "details": str(e)}
        logger.critical(f"{LOG_PREFIX_MQTT} Broker Connection Failed      | {format_log_data(log_data)}")
        if os.path.exists(LOCK_FILE_PATH):
            try:
                os.remove(LOCK_FILE_PATH)
            except Exception as lock_e:
                 log_data_lock_rem_err = {"app_lock_file": LOCK_FILE_PATH, "reason": "Failed to remove lock file on MQTT connection exit", "exception_type": type(lock_e).__name__, "details": str(lock_e)}
                 logger.error(f"{LOG_PREFIX_SYSTEM} Application Lock File Error   | {format_log_data(log_data_lock_rem_err)}")
        sys.exit(1)

    # Handle MQTT Connection Attempt Errors
    except Exception as e:
        mqtt_host_info_fail = f"{MQTT_USERNAME}@{MQTT_SERVER_ADDRESS}:{MQTT_SERVER_PORT}"
        log_data = {"mqtt_host": mqtt_host_info_fail, "reason": "MQTT Connection Failed", "exception_type": type(e).__name__, "details": str(e)}
        logger.critical(f"{LOG_PREFIX_MQTT} Broker Connection Failed      | {format_log_data(log_data)}")
        if os.path.exists(LOCK_FILE_PATH):
            try:
                os.remove(LOCK_FILE_PATH)
            except Exception as lock_e:
                 log_data_lock_rem_err = {"app_lock_file": LOCK_FILE_PATH, "reason": "Failed to remove lock file on MQTT connection exit", "exception_type": type(lock_e).__name__, "details": str(lock_e)}
                 logger.error(f"{LOG_PREFIX_SYSTEM} Application Lock File Error   | {format_log_data(log_data_lock_rem_err)}")
        sys.exit(1)

    # Start MQTT Blocking Loop
    try:
        if TRIGGERS:
            logger.debug(f"{LOG_PREFIX_MQTT} Processing Loop Initiated")
            mqtt_client.loop_forever()
        else:
            log_data_no_sub = {'reason': 'No triggers defined. MQTT loop not started. Exiting.'}
            logger.warn(f"{LOG_PREFIX_MQTT} No Subscriptions   | {format_log_data(log_data_no_sub)}")

    # Handle User Interruption During Shutdown
    except KeyboardInterrupt:
        log_data = {"reason": "KeyboardInterrupt Exception Caught Directly"}
        logger.warn(f"{LOG_PREFIX_USER} Keyboard Interrupt Exception  | {format_log_data(log_data)}")

	# Handle Unexpected Errors During MQTT Loop
    except Exception as e:
        log_data = {"exception_type": type(e).__name__, "details": str(e)}
        logger.error(f"{LOG_PREFIX_APPLICATION} Main Loop Error    | {format_log_data(log_data)}")

    # Attempt MQTT Client Disconnect
    finally:
        log_data_shutdown_init = {"app_name": APP_NAME, "app_version": VERSION}
        logger.info(f"{LOG_PREFIX_SYSTEM} Application Cleanup Initiated | {format_log_data(log_data_shutdown_init)}")
        try:
             if 'mqtt_client' in locals() or 'mqtt_client' in globals():
                 if mqtt_client.is_connected():
                     mqtt_client.disconnect()
                     mqtt_host_info_final = f"{config.get('MQTT_SERVER', {}).get('MQTT_USERNAME', 'unknown')}@{config.get('MQTT_SERVER', {}).get('MQTT_SERVER_ADDRESS', 'unknown')}:{config.get('MQTT_SERVER', {}).get('MQTT_SERVER_PORT', 'unknown')}"
                     log_data_disconnect = {"mqtt_host": mqtt_host_info_final}
                     logger.info(f"{LOG_PREFIX_MQTT} Broker Disconnect Successful  | {format_log_data(log_data_disconnect)}")

        # Handle Errors During MQTT Disconnect
        except Exception as e:
            log_data_disc_err = {"details": str(e) , "exception_type": type(e).__name__}
            logger.error(f"{LOG_PREFIX_SYSTEM} MQTT Disconnect Error         | {format_log_data(log_data_disc_err)}")

        # Remove Lock File During Cleanup
        try:
            current_pid = os.getpid()
            if os.path.exists(LOCK_FILE_PATH):
                lock_pid = -1
                try:
                    with open(LOCK_FILE_PATH, 'r') as f:
                        lock_pid = int(f.read().strip())
                except (ValueError, IOError):
                    lock_pid = -1

                if lock_pid == current_pid or lock_pid == -1:
                    os.remove(LOCK_FILE_PATH)
                    log_data_lock_rem = {"app_lock_file": LOCK_FILE_PATH, "app_pid": current_pid}
                    logger.info(f"{LOG_PREFIX_SYSTEM} Application Lock File Removed | {format_log_data(log_data_lock_rem)}")
                else:
                    log_data_lock_other = {"app_lock_file": LOCK_FILE_PATH, "current_pid": current_pid, "lock_pid": lock_pid}
                    logger.warn(f"{LOG_PREFIX_SYSTEM} Application Lock File Blocked | {format_log_data(log_data_lock_other)}")

    	# Handle Lock File Removal Errors
        except Exception as e:
            log_data_lock_rem_err = {"app_lock_file": LOCK_FILE_PATH, "reason": "Failed to remove lock file", "exception_type": type(e).__name__, "details": str(e)}
            logger.error(f"{LOG_PREFIX_SYSTEM} Application Lock File Error   | {format_log_data(log_data_lock_rem_err)}")
        
        _app_pid_final = os.getpid()
        log_data_shutdown_final = {"app_name": APP_NAME, "app_version": VERSION, "app_pid": _app_pid_final}
        logger.info(f"{LOG_PREFIX_SYSTEM} Application Stop Successful   | {format_log_data(log_data_shutdown_final)}")
