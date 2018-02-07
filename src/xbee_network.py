# xbee_network.py
# This class implements the functionality of the XBee interface with all the
# sensors/controllers connected via the XBee mesh network
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
import serial
from xbee import ZigBee
import threading
import messaging
import logging
import struct
import config
import display

#===============================================================================
# CONSTANTS
#===============================================================================
# Timing
XBEE_WAIT_INTERVAL = 60	# Delay in seconds in each main thread loop

# XBee Data Codes
TEMPERATURE_CODE	=  1
LUMINOSITY_CODE		=  2
PRESSURE_CODE		=  3
HUMIDITY_CODE		=  4
POWER_CODE			=  5
LUX_CODE			=  6
HEATING_CODE		=  7
THERMOSTAT_CODE		=  8
TEMP_12BYTE_CODE	=  9
BATTERY_SOC_CODE	= 10
OVERRIDE_CODE		= 11


#===============================================================================
# XBeeMessages Class
#===============================================================================
# Implements a class that handles XBee messages
#
# Class Members
#	_ehandler	:	The callback function that will handle incoming XBee messages
#	_kill_event	:	The event signaling a shutdown of the thread
#
class XBeeNetwork(threading.Thread):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	#
	def __init__(self, event_handler, kill_event, query_base):
		# types: (callback, event) -> none
		# Set event handler and initialize class
		self._ehandler = event_handler
		self._qbase = query_base
		
		# Initialize as a thread
		self._kill_event = kill_event
		threading.Thread.__init__(self)
	
	#---------------------------------------------------------------------------
	# Main thread execution
	#---------------------------------------------------------------------------
	def run(self):
		# types: (none) -> none
		# Connect to the local XBee
		logging.debug('Starting the XBee Network thread')
		serial_port = serial.Serial('/dev/ttyUSB0', 9600)
		xbee = ZigBee(serial_port, callback=self._xbee_event)
		
		# Loop until time to close
		while not self._kill_event.is_set():
			self._kill_event.wait(XBEE_WAIT_INTERVAL)
	
		# Close the connection to the xbee
		xbee.halt()
		serial_port.close()
		logging.debug('XBee Network thread closing')
	
	#---------------------------------------------------------------------------
	# _xbee_event Method
	#---------------------------------------------------------------------------
	def _xbee_event(self, data):
		# types: (dict) -> none
		# Check the message type
		logging.info('Received an XBee data packet')
		if 'id' in data and data['id'] == 'rx':	# Sensor data received
			# Create database update string and send to the database over the LAN
			request_str = self._create_request(data)
			if request_str:	# Something to send
				# Send the message out to the database
				logging.info('  Sending XBee data to be transmitted through the LAN')
				self._ehandler(messaging.XBeeRxMessage(messaging.DBPacket(request_str)))

				# Check to see if this is the outdoor sensor, and update display if it is
				xbee_address = messaging.binary_print(data['source_addr_long'][-4:], '')
				logging.debug('    Checking if %s is the outdoor sensor', xbee_address)
				if xbee_address == config.outdoor_radio:  # outdoor_radio specified by user in config file
					logging.debug('    Updating the display with the outdoor temperature')
					self._update_display(data)
		else:	# Something else received
			logging.warning('  Received something unexpected from the XBee network: %s', data)

	#---------------------------------------------------------------------------
	# _create_request Method
	#---------------------------------------------------------------------------
	def _create_request(self, data):
		# types: (dict) -> string
		# Initialize the response string
		logging.debug('  Starting the creation of the database insert string')
		resp_str = self._qbase	# Set the base of the query
		logging.debug('    Initial query string is: %s', resp_str)

		# Check for funny number of bytes
		data_length = len(data['rf_data']) - 1
		logging.debug('    Length of byte data in packet is %i', data_length)
		if data_length % 5:
			logging.error('    Corrupted data transmitted through XBee network: incorrect XBee packet size')
			resp_str = ''	# Empty string signals an error
		else:
			# Include the radio
			logging.debug('    Adding radio id to the query string')
			resp_str += 'radio_id='
			resp_str += messaging.binary_print(data['source_addr_long'][-4:], '')
			
			# Iterate through all the sensors adding data
			num_sensors = data_length/5	# Data transferred in 5-byte chunks
			logging.debug('    Adding data for %i sensors to the query string', num_sensors)
			for i in range(num_sensors):
				# Read the first byte which gives the data type
#				is_pressure = False
#				is_override = False
				type_byte = ord(data['rf_data'][5*i+1])
				
				# Create the label for the sensor data
				type_error = False
				if type_byte == TEMPERATURE_CODE:
					resp_str += '&temperature='
				elif type_byte == LUMINOSITY_CODE:
					resp_str += '&luminosity='
				elif type_byte == PRESSURE_CODE:
					resp_str += '&pressure='
#					is_pressure = True
				elif type_byte == HUMIDITY_CODE:
					resp_str += '&humidity='
				elif type_byte == POWER_CODE: 
					resp_str += '&power='
				elif type_byte == LUX_CODE:
					resp_str += '&luminosity_lux='
				elif type_byte == HEATING_CODE:
					resp_str += '&heating_on='
				elif type_byte == THERMOSTAT_CODE:
					resp_str += '&thermo_on='
				elif type_byte == BATTERY_SOC_CODE:
					resp_str += '&battery_soc='
				elif type_byte == OVERRIDE_CODE:
					resp_str += '&override='
#					is_override = True
				else:	# Unrecognized
					logging.error('    Unrecognized sensor data type: %i -> skipping data', type_byte)
					type_error = True
				
				# Convert the binary data to a float and add to string
				if not type_error:
					float_value = struct.unpack('f', data['rf_data'][5*i+2:5*i+7])
					resp_str += '%f' % float_value
					
		# Return the string
		logging.debug('  Finished database insert string creation: %s', resp_str)
		return resp_str

	#---------------------------------------------------------------------------
	# _update_display Method
	#---------------------------------------------------------------------------
	def _update_display(self, data):
		# types: (map) -> None
		# Iterate through the data looking for the temperature - this coding assumes that the data is ok as a response
		# string was created in a previous function call.  No data quality checks are made.
		data_length = len(data['rf_data']) - 1
		num_sensors = data_length / 5  # Data transferred in 5-byte chunks
		for i in range(num_sensors):
			type_byte = ord(data['rf_data'][5 * i + 1])
			if type_byte == TEMPERATURE_CODE:  # Found temperature, convert to string and send to the display
				float_value = struct.unpack('f', data['rf_data'][5*i+2:5*i+7])  # Convert the bytes to a single-precision float
				display_str = 'Outdoor: %.1f' % float_value
				self._ehandler(messaging.DisplayTxMessage(messaging.Command(display.SET_STATUS, display.OUTSIDE_TEMP, display_str)))
