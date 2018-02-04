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

#===============================================================================
# CONSTANTS
#===============================================================================
# Display Addresses
CLOCK_ADD		= 0x00
INTEMP_ADD		= 0x01
OUTTEMP_ADD		= 0x02
SETPOINT_ADD	= 0x03
RELAY_LED_ADD	= 0x00
POWER_BTN_ADD	= 0x00
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
POWER_BTN       = 0
RELAY_LED       = 1
OVER_BTN        = 2
OVER_SCALE      = 4
INSIDE_TEMP     = 5
OUTSIDE_TEMP    = 6
SETPOINT_TEMP   = 7


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
		
			# Start infinite loop listening for messages from the display
			while not self._kill_event.is_set():
				# Handle any data coming from the display
				while geniePi.genieReplyAvail():
					geniePi.genieGetReply(reply)  # Read next reply for message handling
					
					# Handle the message type - only expecting report events
					if reply.cmd == geniePi.GENIE_REPORT_EVENT:
						if reply.object == geniePi.GENIE_OBJ_4DBUTTON:  # Button pressed
							if reply.index == POWER_BTN_ADD:
								self._update_power_status(reply.data)
							elif reply.index == OVER_BTN_ADD:
								self._update_override(reply.data, self._setpoint)
							else:
								logging.error('  Unknown button pressed: %i.  No action taken', reply.index)
						elif reply.object == geniePi.GENIE_OBJ_TRACKBAR:  # Slider interacted with
							if reply.index == TRACKBAR_ADD:
								# Update the internal setpoint register
								self._setpoint = 15 + reply.data

								# Get the current override setting
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
			if cur_cmd.subcommand == POWER_BTN:
				self._update_btn(POWER_BTN_ADD, cur_cmd.data)
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
