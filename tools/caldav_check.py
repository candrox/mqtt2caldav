#!/usr/bin/env python3

import sys
import os
import json
import socket
from urllib.parse import urlparse
import caldav
from caldav.elements import dav

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
config_dir = os.path.join(project_dir, "config")
sys.path.insert(0, config_dir)


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
        print("Error: CALDAV configuration not complete in config.json. Missing CALDAV_SERVER_ADDRESS, CALDAV_USERNAME, or CALDAV_PASSWORD.")
        sys.exit(1)  # Exit with an error if config is incomplete

except FileNotFoundError:
    print("Error: config.json not found.")
    sys.exit(1) # Exit if config.json is not found
except json.JSONDecodeError:
    print("Error: config.json is not valid json.")
    sys.exit(1) # Exit if config.json contains invalid json.


### FUNCTION :: Server Info #############################################################
def get_server_info(caldav_url):
    try:
        parsed_url = urlparse(caldav_url)
        hostname = parsed_url.hostname
        port = parsed_url.port if parsed_url.port else (443 if parsed_url.scheme == 'https' else 80)
        ip_address = socket.gethostbyname(hostname)
        fqdn = socket.getfqdn(hostname)

        return ip_address, port, fqdn
    except Exception as e:
        print(f"Error getting server info: {e}")
        return None, None, None


### FUNCTION :: Calendar List ###########################################################
def list_calendars_enhanced(client):
    try:
        # SERVER Discovery
        caldav_url = str(client.url) # force it to be a string
        ip_address, port, fqdn = get_server_info(caldav_url)
        if ip_address and port and fqdn:
            print("[SERVER DISCOVERY]")
            print(f"  Addr: {ip_address}")
            print(f"  Host: {fqdn}")
            print(f"  Port: {port}")
            print(f"  User: {client.username}\n")

        # CALDAV Principal
        principal = client.principal()
        print("[CALDAV PRINCIPAL]")
        print(f"  URL: {principal.url}")

        # CALDAV Principal Listing
        props = principal.get_properties([dav.DisplayName()])
        for prop in props:
            if isinstance(prop, dav.DisplayName):
                print(f"  Display Name: {prop.value}")

        # CALDAV Calendar Listing
        calendars = principal.calendars()

        if not calendars:
            print("\nNo calendars found on the server.")
            return

        print("\n[CALDAV CALENDARS]")
        
        # Sort calendars by name
        sorted_calendars = sorted(calendars, key=lambda cal: cal.name.lower())

        for index, cal in enumerate(sorted_calendars):
            if index > 0:
                print()  # Add an empty line before each 'Name' starting after the first one
            print(f"  Name: {cal.name}")
            print(f"  Path: {cal.url}")

            # CALDAV Collection Properties
            print("    Collection Properties:")
            props = cal.get_properties([
                dav.DisplayName(),
                dav.Prop(name='{DAV:}description'),
                dav.Prop(name='{urn:ietf:params:xml:ns:caldav}timezone')
                ])

            for prop in props:
                if isinstance(prop, dav.DisplayName):
                    print(f"     Display Name: {prop.value}")
                elif isinstance(prop, dav.Prop):
                  if prop.name == "{DAV:}description" and prop.value is not None:
                    print(f"     Description: {prop.value}")
                  elif prop.name == "{urn:ietf:params:xml:ns:caldav}timezone" and prop.value is not None:
                    print(f"     Timezone: {prop.value}")
    except Exception as e:
        print(f"An error occurred during calendar discovery: {e}")

if __name__ == "__main__":
    client = caldav.DAVClient(
        url=CALDAV_SERVER_ADDRESS, username=CALDAV_USERNAME, password=CALDAV_PASSWORD
    )
    list_calendars_enhanced(client)
