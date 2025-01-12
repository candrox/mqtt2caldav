import sys
import os
import json
import requests
import icalendar
from datetime import datetime
import pytz
import re
from urllib.parse import urlparse

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
config_dir = os.path.join(project_dir, "config")
sys.path.insert(0, config_dir)



### USER CONFIGURATION ##################################################################
LOG_FILE_PATH = "/home/pi/mqtt2caldav/logs/mqtt2caldav.log"  # User-configurable log file path
URLS_TO_FETCH = 3  # User-configurable number of last logged URLs to fetch



### CONFIGURATION :: Load ##############################################################
try:
    with open(os.path.join(config_dir, "config.json"), 'r') as f:
        config = json.load(f)
    caldav_config = config.get("CALDAV_SERVER")
    if not caldav_config:
      print("Error: 'CALDAV_SERVER' not found in config.json")
      sys.exit(1)

    CALDAV_SERVER_ADDRESS = caldav_config.get("CALDAV_SERVER_ADDRESS")
    CALDAV_USERNAME = caldav_config.get("CALDAV_USERNAME")
    CALDAV_PASSWORD = caldav_config.get("CALDAV_PASSWORD")
    if not CALDAV_SERVER_ADDRESS or not CALDAV_USERNAME or not CALDAV_PASSWORD:
        print("Error: CALDAV configuration not complete in config.json.")
        sys.exit(1)  # Exit with an error if config is incomplete

except FileNotFoundError:
    print("Error: config.json not found.")
    sys.exit(1) # Exit if config.json is not found
except json.JSONDecodeError:
    print("Error: config.json is not valid json.")
    sys.exit(1) # Exit if config.json contains invalid json.



### FUNCTION :: Extract Log Details ####################################################
def get_ics_urls_and_timestamps_from_log(log_file, num_urls):
    entries = []
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            for line in reversed(lines):
                match = re.search(r'(\d{4}-\d{2}-\d{2})\s(\d{2}:\d{2}:\d{2}).*(https?://[^\s]+\.ics)', line)
                if match:
                   date_str = match.group(1)
                   time_str = match.group(2)
                   url = match.group(3)
                    # Normalize the URL: remove leading/trailing whitespace
                   url = url.strip()

                   # Validate URL
                   try:
                       result = urlparse(url)
                       if all([result.scheme, result.netloc]):
                          entries.append((url, f"{date_str} {time_str}"))
                          if len(entries) >= num_urls:
                              break
                   except:
                      print(f"Error: Invalid URL format: {url}")
                      continue
            return entries
    except FileNotFoundError:
        print(f"Error: Log file not found: {log_file}")
        return []
    except Exception as e:
        print(f"Error reading log file: {e}")
        return []



### FUNCTION :: Fetch Event Details ######################################################
def fetch_event_details(caldav_url, username, password, calendar_url):
    try:
        response = requests.get(calendar_url, auth=(username, password))
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        ical_text = response.text
        calendar = icalendar.Calendar.from_ical(ical_text)

        for component in calendar.walk():
            if component.name == "VEVENT":
                summary = component.get('summary')
                start = component.get('dtstart')
                end = component.get('dtend')
                description = component.get('description')
                location = component.get('location')

                print(f"  Summary:     {summary}")
                if start:
                    if isinstance(start.dt, datetime):
                        # Handling timezones if present
                        if start.dt.tzinfo:
                           print(f"  Start:       {start.dt.strftime('%Y-%m-%d %H:%M:%S')} ({start.dt.tzinfo})")
                        else:
                           print(f"  Start:       {start.dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    else:
                        print(f"  Start:       {start.dt.strftime('%Y-%m-%d')}")
                if end:
                    if isinstance(end.dt, datetime):
                        # Handling timezones if present
                        if end.dt.tzinfo:
                            print(f"  End:         {end.dt.strftime('%Y-%m-%d %H:%M:%S')} ({end.dt.tzinfo})")
                        else:
                           print(f"  End:         {end.dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    else:
                        print(f"  End:         {end.dt.strftime('%Y-%m-%d')}")
                if location:
                    print(f"  Location:    {location}")
                if description:
                    print(f"  Description: {description}")


    except requests.exceptions.RequestException as e:
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 404:
           print(f"Error: {e}")
        else:
            print(f"An error occurred while fetching event details: {e}")

    except Exception as e:
        print(f"An error occurred while processing the event details: {e}")


if __name__ == "__main__":
    entries = get_ics_urls_and_timestamps_from_log(LOG_FILE_PATH, URLS_TO_FETCH)

    if entries:
        for i, (url, date_time_str) in enumerate(entries):
            if i > 0:
                print() # Add an empty line before the [LOG] for the second and subsequent outputs
            print("[EVENT]")
            print(f"  Path: {url}")
            print(f"  Date: {date_time_str}")
            fetch_event_details(CALDAV_SERVER_ADDRESS, CALDAV_USERNAME, CALDAV_PASSWORD, url)
    else:
        print("No valid calendar URL found in the log file.")
