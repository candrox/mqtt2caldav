#!/usr/bin/env python3
VERSION = "20250902.0950"



### SECTION :: Module Imports ############################################################
import uuid
import datetime



### FUNCTION :: UUID ####################################################################
def decode_uuid(uuid_string):
  try:
    uuid_obj = uuid.UUID(uuid_string)
    hex_len = len(uuid_obj.hex)
    print("-" * (hex_len + 11) )
    print("[UUID]")
    print(f"  UUID:    {uuid_string}")

    if uuid_obj.version == 1:
        
      time_low = uuid_obj.time_low
      time_mid = uuid_obj.time_mid
      time_hi_version = uuid_obj.time_hi_version

      timestamp = (time_low + (time_mid << 32) + ((time_hi_version & 0x0FFF) << 48))
      timestamp = timestamp / 10000000.0  # Convert 100 ns intervals to seconds

      gregorian_epoch = datetime.datetime(1582, 10, 15, tzinfo=datetime.timezone.utc)
      datetime_obj = gregorian_epoch + datetime.timedelta(seconds=timestamp)

      print(f"  Time:    {datetime_obj.strftime('%Y-%m-%d %H:%M:%S.%f UTC')}")
      
      node_hex = f"{uuid_obj.node:012x}"
      address = ':'.join([node_hex[i:i+2] for i in range(0, 12, 2)])
      print(f"  Address: {address}")
      print(f"  Version: {uuid_obj.version}")
      print(f"  Variant: DCE 1.1, ISO/IEC 11578:1996") # Variant is constant for Version 1
      
      clock_id = (uuid_obj.clock_seq_hi_variant << 8) | uuid_obj.clock_seq_low
      print(f"  ClockID: {clock_id}")

    elif uuid_obj.version == 4:
      print(f"  Address: Random") #Node type is random for version 4
      print(f"  Version: {uuid_obj.version}")
      print(f"  Variant: RFC 4122") #Variant is constant for version 4
      print(f"  Random:  {uuid_obj.int & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFF}")  # Mask out version bits

    print(f"  Hex:     {uuid_obj.hex}")
    print(f"  Integer: {uuid_obj.int}")
    
    return hex_len


  except ValueError:
    print(f"Error: Invalid UUID string: {uuid_string}")
    return 0



### MAIN #################################################################################
if __name__ == "__main__":
  while True:
    uuid_str = input("Enter UUID: ")
    if uuid_str.lower() == 'exit':
      break
    hex_len = decode_uuid(uuid_str)
    print("-" * (hex_len + 11) )
