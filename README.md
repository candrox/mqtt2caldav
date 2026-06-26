<img src="mqtt2caldav.png" width="300" height="131">  

# mqtt2caldav  
`mqtt2caldav` reads incoming MQTT events and translates them into predefined calendar events on a CalDAV server (such as Nextcloud, Radicale, Baïkal, Apple Calendar, or Google Calendar).
<br />
<br />

## Core Flow
**Subscribe**: The application runs as a persistent service listening to specific MQTT topics.<br />
**Process**: Upon receiving a designated trigger payload, the service builds a calendar event.<br />
**Publish**: The event is pushed directly to a CalDAV server.<br />
<br />
<br />

## Target Platforms
Because different generations of the Raspberry Pi Zero use distinct system architectures, this repository maintains separate directories tailored to each environment with different :
* **[Raspberry Pi Zero 1](./raspberry-pi-zero-1/)**
  * Optimiziation: Single-core ARMv6 (32-bit environment)
  * Development Timeline: Dec 2020 - May 2026

* **[Raspberry Pi Zero 2](./raspberry-pi-zero-2/)**
  * Optimized for: Quad-core ARMv8 (64-bit environment)
  * Development Timeline: Jun 2026 - Present
<br />
<br />

## Licence 
mqtt2caldav is licensed under the [GNU GENERAL PUBLIC LICENSE Version 3](https://github.com/107208579/mqtt2caldav/blob/main/LICENSE.gpl).
<br />
<br />
