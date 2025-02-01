#!/usr/bin/env python3

### MODULES :: Import ##################################################################
import sys
import json
import time
import caldav
from caldav.lib.error import AuthorizationError
import paho.mqtt.client as mqttClient
from datetime import datetime, timedelta
from utils import logger
from utils.constants import (
    MQTT_SERVER_ADDRESS,
    MQTT_SERVER_PORT,
    MQTT_USERNAME,
    MQTT_PASSWORD,
    CALDAV_SERVER_ADDRESS,
    CALDAV_USERNAME,
    CALDAV_PASSWORD,
    TRIGGERS
)



### FUNCTION :: Round Time #############################################################
def roundTime(dt=None, dateDelta=timedelta(minutes=1)):
    roundTo = dateDelta.total_seconds()
    if dt is None:
        dt = datetime.now()
    seconds = (dt - dt.min).seconds
    rounding = (seconds + roundTo/2) // roundTo * roundTo
    return dt + timedelta(0, rounding-seconds, -dt.microsecond)
    # https://stackoverflow.com/questions/3463930/how-to-round-the-minute-of-a-datetime-object



### FUNCTION :: Offset Time #############################################################
def adjust_event_time(now_datetime, offset):
    try:
        offset_minutes = int(offset)
        adjusted_time = now_datetime + timedelta(minutes=offset_minutes)
        return adjusted_time
    except ValueError:
        # logger.error(f"[ERROR] Configuration | Invalid EVENT_OFFSET value: {offset}")
        return now_datetime



### FUNCTION :: Connect MQTT Client ####################################################
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"[MQTT] Broker Connection Successful | {MQTT_USERNAME}@{MQTT_SERVER_ADDRESS}:{MQTT_SERVER_PORT}")
        print(f"[MQTT] Broker Connection Successful | {MQTT_USERNAME}@{MQTT_SERVER_ADDRESS}:{MQTT_SERVER_PORT}")
        for trigger in TRIGGERS:
            client.subscribe(trigger['MQTT_TOPIC'])
    else:
        logger.error(f"[MQTT] Broker Connection Failed | {MQTT_USERNAME}@{MQTT_SERVER_ADDRESS}:{MQTT_SERVER_PORT}")
        print(f"[MQTT] Broker Connection Failed | {MQTT_USERNAME}@{MQTT_SERVER_ADDRESS}:{MQTT_SERVER_PORT}")



### FUNCTION :: Action MQTT Message ####################################################
def on_message(client, userdata, message):
    try:
        logger.info(f"[M2C] Event Received | {message.topic} | {message.payload.decode('ASCII')}")
        print(f"[M2C] Event Received | {message.topic} | {message.payload.decode('ASCII')}")

        mqtt_event = json.loads(message.payload.decode('ASCII'))

        for trigger in TRIGGERS:
            if trigger['MQTT_TOPIC'] == message.topic and all((k in mqtt_event and mqtt_event[k] == v) for k, v in trigger['MQTT_EVENT'].items()):
                print(f"[M2C] Event Matched  | {message.topic} | {message.payload.decode('ASCII')}")
                logger.info(f"[M2C] Event Matched  | {message.topic} | {message.payload.decode('ASCII')}")
                
                # Validate 'MODE' first
                if 'MODE' not in trigger:
                     logger.warn(f"[M2C] Event Skipped  | {message.topic} | {{\"event_mode\":\"MODE key missing\"}}")
                     print(f"[M2C] Event Skipped  | {message.topic} | {{\"event_mode\":\"MODE key missing\"}}")
                     continue
                
                if trigger.get('MODE', '').lower() != "create":
                   logger.warn(f"[M2C] Event Skipped  | {message.topic} | {{\"event_mode\":\"MODE key not allowed\"}}")
                   print(f"[M2C] Event Skipped  | {message.topic} | {{\"event_mode\":\"MODE key not allowed\"}}")
                   continue

                if "action" in mqtt_event:
                    event_location = trigger['EVENT_LOCATION'].replace('\\,', ',')
                    log_message = f"[M2C] Event Actioned | {message.topic} | {{\"event_summary\":\"{trigger['EVENT_SUMMARY']}\",\"event_location\":\"{event_location}\",\"event_duration\":\"{trigger['EVENT_DURATION']}\"}}"

                    logger.info(log_message)
                    print(log_message)

                
                now_datetime = datetime.now()

                # Store original time for comparison with adjusted time
                original_now_datetime = now_datetime

                if trigger.get('EVENT_OFFSET') and trigger['EVENT_OFFSET'] != '0':
                   now_datetime = adjust_event_time(now_datetime, trigger['EVENT_OFFSET'])

                # Check if adjust_event_time returned the original time - meaning there was a invalid 'EVENT_OFFSET' value
                if now_datetime == original_now_datetime and trigger.get('EVENT_OFFSET') and trigger['EVENT_OFFSET'] != '0':
                    print(f"[M2C] Event Skipped  | {message.topic} | {{\"event_offset\":\"Invalid EVENT_OFFSET value configured\"}}")
                    logger.warn(f"[M2C] Event Skipped  | {message.topic} | {{\"event_offset\":\"Invalid EVENT_OFFSET value configured\"}}")
                    continue

                if trigger['EVENT_ROUNDING'] and trigger['EVENT_ROUNDING'] != '0':
                    now_datetime = roundTime(now_datetime, timedelta(minutes=int(trigger['EVENT_ROUNDING'])))

                end_datetime = now_datetime + timedelta(minutes=int(trigger['EVENT_DURATION']))

                if trigger['EVENT_SECONDS'].lower() == 'false':
                    start_time = now_datetime.strftime('%Y%m%dT%H%M00')
                    end_time = end_datetime.strftime('%Y%m%dT%H%M00')
                else:
                    start_time = now_datetime.strftime('%Y%m%dT%H%M%S')
                    end_time = end_datetime.strftime('%Y%m%dT%H%M%S')

                
                event_calendar = caldav.Calendar(client=cal_client, url=trigger['EVENT_CALENDAR'])
                main_event = "BEGIN:VCALENDAR\n" \
                        "VERSION:2.0\n" \
                        "PRODID:-//MQTT//EN\n" \
                        "CALSCALE:GREGORIAN\n" \
                        "BEGIN:VEVENT\n" \
                        f"DTSTART;TZID={trigger['EVENT_TIMEZONE']}:{start_time}\n" \
                        f"DTEND;TZID={trigger['EVENT_TIMEZONE']}:{end_time}\n" \
                        f"DTSTAMP:{start_time}\n" \
                        f"LOCATION:{trigger['EVENT_LOCATION']}\n" \
                        f"DESCRIPTION:{trigger['EVENT_DESCRIPTION']}\n" \
                        f"URL;VALUE=URI:{trigger['EVENT_URL']}\n" \
                        f"SUMMARY:{trigger['EVENT_SUMMARY']}\n" \
                        f"GEO:{trigger['EVENT_GEO']}\n" \
                        f"TRANSP:{trigger['EVENT_TRANSP']}\n" \
                        f"CATEGORIES:{trigger['EVENT_CATEGORIES']}\n" \
                        f"CREATED:{start_time}\n"

                end_event = "END:VEVENT\n" \
                    "END:VCALENDAR\n"

                if trigger['EVENT_TRIGGER']:
                    alarm_event =  "BEGIN:VALARM\n" \
                                   f"TRIGGER:-PT{trigger['EVENT_TRIGGER']}M\n" \
                                   "ATTACH;VALUE=URI:Chord\n" \
                                   "ACTION:AUDIO\n" \
                                   "END:VALARM\n"
                    str_event = main_event + alarm_event + end_event
                else:
                    str_event = main_event + end_event
                try:
                    my_event = event_calendar.save_event(str_event)
                    logger.info(f"[DAV] Event Created  | {message.topic} | {{\"event_path\":\"{my_event.url}\"}}")
                    print(f"[DAV] Event Created  | {message.topic} | {{\"event_path\":\"{my_event.url}\"}}")

                except Exception as e:
                    logger.error(f"[DAV] Error Response | {{\"caldav_response\":\"{message.topic} | {e}\"}}")
                    print(f"[DAV] Error Response | {{\"caldav_response\":\"{message.topic} | {e}\"}}")

    except Exception as e:
        logger.error(f"[ERROR] Exception | on_message: {e}")
        print(f"[ERROR] Exception | on_message: {e}")

if __name__ == '__main__':



### Connect CalDAV Client ##############################################################
    global cal_client
    try:
        cal_client = caldav.DAVClient(url=CALDAV_SERVER_ADDRESS, username=CALDAV_USERNAME, password=CALDAV_PASSWORD)
        my_principal = cal_client.principal()
        calendars = my_principal.calendars()
        if calendars:
            logger.info(f"[DAV] Server Connection Successful | {CALDAV_USERNAME}@{CALDAV_SERVER_ADDRESS}")
            print(f"[DAV] Server Connection Successful | {CALDAV_USERNAME}@{CALDAV_SERVER_ADDRESS}")
            for c in calendars:
                print(f"[DAV] {c.name:<20} {c.url}")
        else:
            print("[DAV] Server Connection Successful | 0 Calendar")
    except AuthorizationError:
        logger.error(f"[DAV] Server Connection Failed | {CALDAV_USERNAME}@{CALDAV_SERVER_ADDRESS}")
        print(f"[DAV] Server Connection Failed | {CALDAV_USERNAME}@{CALDAV_SERVER_ADDRESS}")
        exit(1)



### Manage MQTT Connection #############################################################
    mqtt_client = mqttClient.Client("Python")
    mqtt_client.username_pw_set(MQTT_USERNAME, password=MQTT_PASSWORD)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_SERVER_ADDRESS, port=int(MQTT_SERVER_PORT))

    mqtt_client.loop_start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.warn("[USER] Keyboard Interrupt | Exit")
        print("[USER] Keyboard Interrupt | Exit")
        mqtt_client.disconnect()
        mqtt_client.loop_stop()
    except Exception as e:
        logger.error(f"[ERROR] Exception | main loop: {e}")
        print(f"[ERROR] Exception | main loop: {e}")
        mqtt_client.disconnect()
        mqtt_client.loop_stop()
