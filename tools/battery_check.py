#!/usr/bin/env python3
VERSION = "20250902.0950"



### SECTION :: Module Imports ############################################################
import sys
import os

# Default values
default_battery_value = 75
default_log_lines = 100

# Prompt user for log lines
try:
    user_log_lines_input = input(f"Last Logfile Lines (Default {default_log_lines}): ")
    if user_log_lines_input == "":
        log_lines = default_log_lines
    else:
        log_lines = int(user_log_lines_input)
except ValueError:
    print("Invalid input. Please enter a number.")
    sys.exit(1)

# Prompt user for battery value
try:
    user_battery_value_input = input(f"Below Battery Level (Default {default_battery_value}%): ")
    if user_battery_value_input == "":
        battery_threshold = default_battery_value
    else:
        battery_threshold = int(user_battery_value_input)
except ValueError:
    print("Invalid input. Please enter a number.")
    sys.exit(1)

processed_lines = set()
results = []
log_file_path = "/home/pi/mqtt2caldav/logs/mqtt2caldav.log"

try:
    with open(log_file_path, 'r') as f:
        # Read all lines and take the last 'n' lines
        all_lines = f.readlines()
        last_lines = all_lines[-log_lines:]

    for line in last_lines:
        if "Event Received" in line and "battery" in line:
            try:
                # Extract battery value
                battery_part = line.split("battery='")[1]
                battery_value_str = battery_part.split("'")[0]
                battery_value = int(battery_value_str)

                if battery_value < battery_threshold:
                    # Extract timestamp
                    parts = line.split()
                    timestamp = f"{parts[1]} {parts[2]}"

                    # Extract MQTT topic
                    mqtt_part = line.split("mqtt_topic='")[1]
                    mqtt_section = mqtt_part.split("'")[0]

                    if mqtt_section:
                        # Create a unique identifier for the combination of topic and battery value
                        unique_key = f"{mqtt_section}{battery_value}"
                        if unique_key not in processed_lines:
                            processed_lines.add(unique_key)
                            results.append((timestamp, mqtt_section, battery_value))
            except (IndexError, ValueError):
                # Ignore lines that don't have the expected format
                continue

except FileNotFoundError:
    print(f"Error: Log file not found at {log_file_path}")
    sys.exit(1)
except Exception as e:
    print(f"An error occurred: {e}")
    sys.exit(1)

# Sort results by battery value (the 3rd element in the tuple)
results.sort(key=lambda x: x[2])

# Print the formatted results
for timestamp, mqtt_section, battery_value in results:
    print(f"{timestamp} | {mqtt_section} | Battery: {battery_value}%")
