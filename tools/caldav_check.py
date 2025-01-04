import sys
import os
import socket
from urllib.parse import urlparse
import caldav
from caldav.elements import dav
import pprint

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
utils_dir = os.path.join(project_dir, "utils")
sys.path.insert(0, utils_dir)


from constants import CALDAV_SERVER_ADDRESS, CALDAV_USERNAME, CALDAV_PASSWORD

def get_server_info(caldav_url):
    try:
        parsed_url = urlparse(caldav_url)
        hostname = parsed_url.hostname
        port = parsed_url.port if parsed_url.port else (443 if parsed_url.scheme == 'https' else 80)
        ip_address = socket.gethostbyname(hostname)

        return ip_address, port
    except Exception:
       return None, None


def list_calendars_enhanced(caldav_url, username, password):
    client = caldav.DAVClient(
        url=caldav_url, username=username, password=password
    )
    try:
        # SERVER Discovery
        print("[Server Discovery]")
        ip_address, port = get_server_info(caldav_url)
        if ip_address and port:
            print(f"  Host: {ip_address}")
            print(f"  Port: {port}")
            print(f"  User: {username}\n")
        else:
            print(f"  Could not retrieve server info from URL: {caldav_url}")
            print(f"  User: {username}\n")

        # CALDAV Principal
        print("[Caldav Principal]")
        principal = client.principal()
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

        print("\n[Caldav Calendars]")
        for i, cal in enumerate(calendars):
            print(f"  {i + 1}. Name: {cal.name}, URL: {cal.url}")

            # Collection Properties
            print("      Collection Properties:")
            props = cal.get_properties([
                dav.DisplayName(),
                dav.Prop(name='{DAV:}description'),
                dav.Prop(name='{urn:ietf:params:xml:ns:caldav}timezone')
                ])
            for prop in props:
                if isinstance(prop, dav.DisplayName):
                    print(f"        Display Name: {prop.value}")
                elif isinstance(prop, dav.Prop) and prop.name == "{DAV:}description":
                    if prop.value is not None:
                        print(f"        Description: {prop.value}")
                elif isinstance(prop, dav.Prop) and prop.name == "{urn:ietf:params:xml:ns:caldav}timezone":
                    if prop.value is not None:
                        print(f"        Timezone: {prop.value}")

    except Exception as e:
        print(f"An error occurred during calendar discovery: {e}")

if __name__ == "__main__":

    # List calendars enhanced
    list_calendars_enhanced(CALDAV_SERVER_ADDRESS, CALDAV_USERNAME, CALDAV_PASSWORD)
