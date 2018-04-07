# display.py
# This class is a 4D Systems display controller.
#
# The MIT License (MIT)
# Copyright (c) 2018 Tim Lampman
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
#
# REVISION HISTORY
#

# Imports
import logging
import threading
import messaging
import geniePi
import thermostat
from datetime import datetime
import urllib2
import xml.etree.ElementTree as ET

#===============================================================================
# CONSTANTS
#===============================================================================
# Display Addresses
CLOCK_ADD		= 0x00
INTEMP_ADD		= 0x01
OUTTEMP_ADD		= 0x02
SETPOINT_ADD	= 0x03
RELAY_LED_ADD	= 0x00
POWER_LED_ADD   = 0x01
PROGRAM_BTN_ADD	= 0x00
OVER_BTN_ADD	= 0x01
TRACKBAR_ADD	= 0x00
WEATHER_ADD		= 0x00

# Display Constants
LED_ON			= 1
LED_OFF			= 0
BTN_ON			= 1
BTN_OFF			= 0

# Commands
SET_STATUS      = 0

# Subcommands
PROGRAM_BTN     = 0
RELAY_LED       = 1
OVER_BTN        = 2
OVER_SCALE      = 4
INSIDE_TEMP     = 5
OUTSIDE_TEMP    = 6
SETPOINT_TEMP   = 7
POWER_LED       = 8

# Weather Icon Addresses
WX_SUNNY        =  0
WX_SCT_CLOUDS   =  1
WX_BKN_CLOUDS   =  2
WX_OVC_CLOUDS   =  3
WX_SHOWERS      =  4
WX_RAIN         =  5
WX_TSTORM       =  6
WX_SCAT_SNOW    =  7
WX_SNOW         =  8
WX_FZ_RAIN      =  9

#===============================================================================
# DisplayControl Class
#===============================================================================
# Implements a class that handles the 4D Systems display
#
# Class Members
#	_ehandler	    :	The callback function that will handle incoming XBee messages
#	_kill_event	    :	The event signaling a shutdown of the thread
#	_display_error  : 	Indicates if there is an error with the display
#   _setpoint       :   Contains the setpoint in degrees
#
class DisplayControl(threading.Thread):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	#
	def __init__(self, event_handler, kill_event):
		# types: (callback, event) -> none
		# Set event handler and initialize class
		self._ehandler = event_handler
		self._display_error = False
		self._setpoint = 15

		# Initialize as a thread
		self._kill_event = kill_event
		threading.Thread.__init__(self)
	
	#---------------------------------------------------------------------------
	# Main thread execution
	#---------------------------------------------------------------------------
	def run(self):
		# Connect to the display
		if geniePi.genieSetup('/dev/serial0', 115200) < 0:  # Error occurred
			logging.error('  Cannot connect to the display - it will be updated')
			self._display_error = True
		else:	# Run the thread
			logging.debug('  Connected to the display')

			# Create the reply structure
			reply = geniePi.genieReplyStruct()

			# Start the clock thread
			clock_thread = ClockController(self._kill_event, self._display_error)
			clock_thread.start()

			# Start the weather display thread
			weather_thread = WeatherDisplay(self._kill_event, self._display_error)
			weather_thread.start()
		
			# Start infinite loop listening for messages from the display
			while not self._kill_event.is_set():
				# Handle any data coming from the display
				while geniePi.genieReplyAvail():
					geniePi.genieGetReply(reply)  # Read next reply for message handling
					
					# Handle the message type - only expecting report events
					if reply.cmd == geniePi.GENIE_REPORT_EVENT:
						if reply.object == geniePi.GENIE_OBJ_4DBUTTON:  # Button pressed
							if reply.index == PROGRAM_BTN_ADD:
								self._update_power_status(reply.data)
							elif reply.index == OVER_BTN_ADD:
								# Only allow this to change state if the thermostat power is on
								thermo_status = geniePi.genieReadObj(geniePi.GENIE_OBJ_4DBUTTON, PROGRAM_BTN_ADD)
								if thermo_status:
									self._update_override(reply.data, self._setpoint)
								else:  # Revert the override status to its initial state
									prev_override_status = BTN_OFF if reply.data else BTN_ON
									geniePi.genieWriteObj(geniePi.GENIE_OBJ_4DBUTTON, OVER_BTN_ADD, prev_override_status)
							else:
								logging.error('  Unknown button pressed: %i.  No action taken', reply.index)
						elif reply.object == geniePi.GENIE_OBJ_TRACKBAR:  # Slider interacted with
							if reply.index == TRACKBAR_ADD:
								# Update the internal setpoint register
								self._setpoint = 15 + reply.data

								# Update the thermostat controller iff override mode is on
								override_status = geniePi.genieReadObj(geniePi.GENIE_OBJ_4DBUTTON, OVER_BTN_ADD)
								logging.debug('    Current display override status: %i', override_status)
								if override_status:  # The override mode is on
									self._update_override(override_status, self._setpoint)
							else:
								logging.error('  Unknown trackbar changes: %i.  No action taken', reply.index)
						else:
							logging.error('  Unknown object changed: %i.  No action taken', reply.object)
					else:   # Unknown item
						logging.error('  Unknown display message type: %i.  No action taken', reply.cmd)

				# Wait for next message
				self._kill_event.wait(0.02)	# Check every 20 milliseconds

			# Cleanup the clock thread
			weather_thread.join()
			clock_thread.join()
		
		# Indicate the thread is ending
		logging.debug('Display thread closing')
			
	#---------------------------------------------------------------------------
	# process_message Method
	#---------------------------------------------------------------------------
	def process_message(self, command):
		# types: (DisplayPacket) -> None
		# Evaluate the message
		cur_cmd = command.packet
		if cur_cmd.command == SET_STATUS:
			# Check the subcommand
			if cur_cmd.subcommand == PROGRAM_BTN:
				self._update_btn(PROGRAM_BTN_ADD, cur_cmd.data)
			elif cur_cmd.subcommand == RELAY_LED:
				self._update_led(RELAY_LED_ADD, cur_cmd.data)
			elif cur_cmd.subcommand == OVER_BTN:
				self._update_btn(OVER_BTN_ADD, cur_cmd.data)
			elif cur_cmd.subcommand == OVER_SCALE:
				self._update_scale(TRACKBAR_ADD, cur_cmd.data)
			elif cur_cmd.subcommand == INSIDE_TEMP:
				self._update_string(INTEMP_ADD, cur_cmd.data)
			elif cur_cmd.subcommand == OUTSIDE_TEMP:
				self._update_string(OUTTEMP_ADD, cur_cmd.data)
			elif cur_cmd.subcommand == SETPOINT_TEMP:
				self._update_string(SETPOINT_ADD, cur_cmd.data)
			elif cur_cmd.subcommand == POWER_LED:
				self._update_led(POWER_LED_ADD, cur_cmd.data)
		else:
			logging.error('  Display message unrecognized - no action taken')

	#---------------------------------------------------------------------------
	# _update_power_btn Method
	#---------------------------------------------------------------------------
	def _update_btn(self, address, status):
		# types: (int, int) -> None
		# Only update is the display is connected
		if not self._display_error:
			if status == BTN_ON:
				logging.debug('  Received message to turn on a power button')
				geniePi.genieWriteObj(geniePi.GENIE_OBJ_4DBUTTON, address, BTN_ON)
			else:
				logging.debug('  Received message to turn off a power button')
				geniePi.genieWriteObj(geniePi.GENIE_OBJ_4DBUTTON, address, BTN_OFF)

	#---------------------------------------------------------------------------
	# _update_relay_led Method
	#---------------------------------------------------------------------------
	def _update_led(self, address, status):
		# types: (int, int) -> None
		# Only update if the display is connected
		if not self._display_error:
			if status == LED_ON:
				logging.debug('  Received message to turn on a LED')
				geniePi.genieWriteObj(geniePi.GENIE_OBJ_USER_LED, address, LED_ON)
			else:
				logging.debug('  Received message to turn off a LED')
				geniePi.genieWriteObj(geniePi.GENIE_OBJ_USER_LED, address, LED_OFF)

	#---------------------------------------------------------------------------
	# _update_string Method
	#---------------------------------------------------------------------------
	def _update_string(self, address, text):
		# types: (int, string) -> None
		# Only update if the display is connected
		if not self._display_error:
			geniePi.genieWriteStr(address, text)

	#---------------------------------------------------------------------------
	# _update_scale Method
	#---------------------------------------------------------------------------
	def _update_scale(self, address, setting):
		# types: (int, int) -> None
		# Only update if the display is connected
		if not self._display_error:
			scale_index = int(setting - 15.0)   # This is set for now assuming a single trackbar - may need to be changed if more trackbars added
			geniePi.genieWriteObj(geniePi.GENIE_OBJ_TRACKBAR, address, scale_index)

	#---------------------------------------------------------------------------
	# _update_power Method
	#---------------------------------------------------------------------------
	def _update_power_status(self, status):
		# Create the packet and send to the thermostat
		button_status = thermostat.STATUS_ON if status == BTN_ON else thermostat.STATUS_OFF
		data_packet = messaging.DisplayPacket(messaging.Command(thermostat.CMD_THERMO_POWER, button_status, None))
		self._ehandler(messaging.ThermostatTxMessage(data_packet))

	#---------------------------------------------------------------------------
	# _update_override Method
	#---------------------------------------------------------------------------
	def _update_override(self, status, setpoint):
		# Create the packet and send to the thermostat
		button_status = thermostat.STATUS_ON if status == BTN_ON else thermostat.STATUS_OFF
		data_packet = messaging.DisplayPacket(messaging.Command(thermostat.CMD_OVERRIDE, button_status, setpoint))
		self._ehandler(messaging.ThermostatTxMessage(data_packet))


#===============================================================================
# ClockController Class
#===============================================================================
# Implements a class that updates the clock on the display
#
# Class Members
#	_kill_event	    :	The event signaling a shutdown of the thread
#	_display_error  : 	Indicates if there is an error with the display
#   _prev_datetime  :   The datetime currently displayed
#
class ClockController(threading.Thread):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, kill_event, display_error):
		# Initialize variables
		self._kill_event = kill_event
		self._display_error = display_error
		self._prev_datetime = ''

		# Initialize as a thread
		threading.Thread.__init__(self)

	#---------------------------------------------------------------------------
	# run method
	#---------------------------------------------------------------------------
	def run(self):
		# Infinite look until event signalling exit
		logging.debug('Starting clock thread')
		while not self._kill_event.is_set():
			# Get the current time as a string, and update display if different
			datetime_str = datetime.now().strftime('%A, %B %d  %H:%M')
			if (datetime_str != self._prev_datetime) and not self._display_error:
				geniePi.genieWriteStr(CLOCK_ADD, datetime_str)
				self._prev_datetime = datetime_str

			# Delay between date string updates - will give reasonable lag for the clock update
			self._kill_event.wait(1)  # 1 second

		logging.debug('Clock thread exiting.')


#===============================================================================
# WeatherDisplay Class
#===============================================================================
# Implements a class that updates the weather displayed on the screen
#
# Class Members
#	_kill_event	    :	The event signaling a shutdown of the thread
#	_display_error  : 	Indicates if there is an error with the display
#   _current_icon   :   Indicates the icon that is currently displayed
#
class WeatherDisplay(threading.Thread):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, kill_event, display_error):
		# Initialize variables
		self._kill_event = kill_event
		self._display_error = display_error
		self._prev_datetime = ''
		self._current_icon = WX_SUNNY

		# Initialize as a thread
		threading.Thread.__init__(self)

	#---------------------------------------------------------------------------
	# run method
	#---------------------------------------------------------------------------
	def run(self):
		# Infinite look until event signalling exit
		logging.debug('Starting weather display thread')
		while not self._kill_event.is_set():
			# Get the latest weather as an xml printout
			url_address = 'https://www.aviationweather.gov/adds/dataserver_current/httpparam?dataSource=metars&requestType=retrieve&format=xml&stationString=cykz&hoursBeforeNow=2'
			try:
				url_response = urllib2.urlopen(url_address)
				xml_data = url_response.read()
			except urllib2.URLError as error:
				if hasattr(error, 'reason'):
					logging.error('Could not reach the server: ', error.reason)
				elif hasattr(error, 'code'):
					logging.error('The server could not fulfill the request: ', error.code)
			else:
				# Get the node with the most recent weather data
				xml_root = ET.fromstring(xml_data)
				metar_list = xml_root.findall('./data/METAR')
				if len(metar_list) > 0:
					metar = metar_list[0]  # Get the latest METAR update despite type (can include SPECI's)
					new_icon = None

					# Determine if there is precipitation (implies that we don't have to worry about cloud type, just type of precip)
					if metar.find('./wx_string') is not None:  # We have possible rain, need to check the remarks
						wx_string = metar.find('./wx_string').text  # Get the string describing conditions

						# Check for types of rain
						if 'TS' in wx_string:  # Check for thunderstorms
							new_icon = WX_TSTORM
						elif 'FZ' in wx_string:  # Check for freezing rain
							new_icon = WX_FZ_RAIN
						elif 'SN' in wx_string:  # Check for snow
							if 'SH' in wx_string:  # Further check for snow showers
								new_icon = WX_SCAT_SNOW
							else:
								new_icon = WX_SNOW
						elif ('RA' in wx_string) or ('DZ' in wx_string):  # Finally, see if there is plain old rain
							if 'SH' in wx_string:  # Further check for showers
								new_icon = WX_SHOWERS
							else:
								new_icon = WX_RAIN

					# If no icon found for precipitation, check cloud types
					if new_icon is None:
						# Get all sky conditions and iterate through them
						new_icon = WX_SUNNY  # Default to no coverage, or sunny skies
						for layer in metar.findall('./sky_condition'):
							if layer.attrib['sky_cover'] == 'SKC' or layer.attrib['sky_cover'] == 'CLR':
								# Call this condition sunny skies and break out of the loop (not likely needed)
								new_icon = WX_SUNNY
								break
							elif int(layer.attrib['cloud_base_ft_agl']) <= 12000:  # Need to evaluate the work sky condition below 12,000 ft
								if layer.attrib['sky_cover'] == 'FEW':
									if new_icon < WX_SUNNY: new_icon = WX_SUNNY  # Treat this as sunny skies
								elif layer.attrib['sky_cover'] == 'SCT':
									if new_icon < WX_SCT_CLOUDS: new_icon = WX_SCT_CLOUDS
								elif layer.attrib['sky_cover'] == 'BKN':
									if new_icon < WX_BKN_CLOUDS: new_icon = WX_BKN_CLOUDS
								elif layer.attrib['sky_cover'] == 'OVC':
									if new_icon < WX_OVC_CLOUDS: new_icon = WX_OVC_CLOUDS

					# Update the weather display if a new icon is needed
					if self._current_icon != new_icon:
						self._current_icon = new_icon
						geniePi.genieWriteObj(geniePi.GENIE_OBJ_USERIMAGES, WEATHER_ADD, self._current_icon)

				else:  # No METAR information, so do not update the display
					logging.debug('  No METAR data to update weather display.')

			# Delay between date string updates - will give reasonable lag for the clock update
			self._kill_event.wait(15*60)  # 15 minutes

		logging.debug('Weather display thread exiting.')
