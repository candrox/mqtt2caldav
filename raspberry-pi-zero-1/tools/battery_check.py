#!/usr/bin/env python3
VERSION = "20250903.1207"



### SECTION :: Module Imports ############################################################
import sys
from collections import defaultdict



### SECTION :: Configuration #############################################################
log_file_path = "/home/pi/mqtt2caldav/logs/mqtt2caldav.log"
prompt_user_for_input = False
default_log_lines = 10000
default_entries_per_device = 5
bar_char_filled = '▓'	# ░ ▒ ▓ █
bar_char_empty = '░'	# ░ ▒ ▓ █



### SECTION :: User Input ################################################################
if prompt_user_for_input:
    try:
        user_log_lines_input = input(f"Last Logfile Lines to Analyze (Default: {default_log_lines}): ")
        if user_log_lines_input == "":
            log_lines_to_check = default_log_lines
        else:
            log_lines_to_check = int(user_log_lines_input)
    except ValueError:
        print("Invalid input. Please enter a number.")
        sys.exit(1)

    try:
        user_entries_input = input(f"Entries per Device (Default: {default_entries_per_device}): ")
        if user_entries_input == "":
            entries_to_show = default_entries_per_device
        else:
            entries_to_show = int(user_entries_input)
    except ValueError:
        print("Invalid input. Please enter a number.")
        sys.exit(1)
else:
    log_lines_to_check = default_log_lines
    entries_to_show = default_entries_per_device


### SECTION :: Log Processing ############################################################
devices = defaultdict(list)

try:
    with open(log_file_path, 'r') as f:
        all_lines = f.readlines()
        last_lines = all_lines[-log_lines_to_check:]

    for line in reversed(last_lines):
        if "[APP] Event Received |" in line and "battery='" in line:
            try:
                # Extract timestamp
                parts = line.split()
                timestamp = f"{parts[1]} {parts[2]}"

                # Extract friendly name from MQTT topic
                topic_part = line.split("mqtt_topic='mqtt/")[1]
                friendly_name = topic_part.split("'")[0]
                
                # Extract battery value
                battery_part = line.split("battery='")[1]
                battery_value_str = battery_part.split("'")[0]
                battery_value = int(battery_value_str)

                # Store the latest readings for this device
                if len(devices[friendly_name]) < entries_to_show:
                    devices[friendly_name].append((timestamp, battery_value))

            except (IndexError, ValueError):
                continue

except FileNotFoundError:
    print(f"\n[ERROR] Log file not found at '{log_file_path}'")
    print("Please update the 'log_file_path' variable in the script.")
    sys.exit(1)
except Exception as e:
    print(f"\n[ERROR] An unexpected error occurred: {e}")
    sys.exit(1)



### SECTION :: Results Output ############################################################
def create_ascii_bar(battery_level, filled_char, empty_char, max_level=100, bar_width=25):
    """Generates a simple text-based bar for a given battery percentage."""
    if battery_level is None:
        return f"0 {empty_char*bar_width} {max_level}"
    
    percentage = max(0, min(1, battery_level / max_level))
    filled_chars = int(percentage * bar_width)
    empty_chars = bar_width - filled_chars
    
    bar = filled_char * filled_chars + empty_char * empty_chars
    return f"0 {bar} {max_level}"


if not devices:
    print(f"\nNo device battery data found in the analyzed log lines.")
    print("Try increasing the number of lines to analyze.")
    sys.exit(0)

# Get a sorted list of all device names with readings
sorted_device_names = sorted(devices.keys())
num_devices = len(sorted_device_names)

# Find the maximum topic length for clean column alignment
max_topic_len = 0
if devices:
    max_topic_len = max(len(name) for name in devices.keys()) + 5

# Calculate the full width for the separator line
# Length = timestamp(19) + topic(max_topic_len) + battery(18) + bar(31) + separators(9)
separator_length = 19 + max_topic_len + 18 + 31 + (3 * 3)

# Print the initial separator line after the prompt and before the results.
print('-' * separator_length)

# Print the formatted results, grouped by device
for i, name in enumerate(sorted_device_names):
    full_topic = f"mqtt/{name}"
    
    # Readings were added in reverse order, so we sort them to be chronological
    readings = devices[name]
    readings.sort()

    for timestamp, battery_level in readings:
        bar = create_ascii_bar(battery_level, bar_char_filled, bar_char_empty)
        topic_padded = full_topic.ljust(max_topic_len)
        battery_text_padded = f"Battery: {battery_level}%".ljust(18)

        print(f"{timestamp} | {topic_padded} | {battery_text_padded} | {bar}")

    # Print a separator line between devices, but not after the very last one
    if i < num_devices - 1:
        print('-' * separator_length)
