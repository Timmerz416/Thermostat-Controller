# thermostat.py
# This class is a thermostat controller.
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
import messaging
import pigpio
import threading
import time
import display
from tsl2561 import TSL2561
from htu21d import HTU21D
from datetime import datetime

#===============================================================================
# Constants
#===============================================================================
# Command Codes
CMD_THERMO_POWER	=  1
CMD_OVERRIDE		=  2
CMD_RULE_CHANGE		=  3
CMD_SENSOR_DATA		=  4
CMD_TIME_REQUEST	=  5
CMD_STATUS			=  6
CMD_SHUTDOWN		=  7

# Subcommand Codes
CMD_NACK			=  0
CMD_ACK				=  1
STATUS_OFF			=  2
STATUS_ON			=  3
STATUS_GET			=  4
STATUS_ADD			=  5
STATUS_DELETE		=  6
STATUS_MOVE			=  7
STATUS_UPDATE		=  8
STATUS_SET			=  9

# Thermostat controls
RELAY_ON			= True
RELAY_OFF			= False
THERMOSTAT_ON		= RELAY_ON
THERMOSTAT_OFF		= RELAY_OFF

# Thermostat limits
MIN_TEMPERATURE		= 10.0	# Below this temperature, the relay opens no matter the programming
MAX_TEMPERATURE 	= 25.0	# Above this temperature, the relay closes no matter the programming
TEMPERATURE_BUFFER	=  0.15	# The buffer to apply in the thermostat set target in evaluation relay

# GPIO Pins
THERMO_POWER_PIN	= 21
RELAY_POWER_PIN		= 16
RELAY_STATUS_PIN	= 20
POWER_SWITCH_PIN	= 12

# Rules
RULE_DAYS = {
	'Monday': 0,
	'Tuesday': 1,
	'Wednesday': 2,
	'Thursday': 3,
	'Friday': 4,
	'Saturday': 5,
	'Sunday': 6,
	'Weekdays': 7,
	'Weekends': 8,
	'Everyday': 9 }


#===============================================================================
# Thermostat Class
#===============================================================================
# Implements a controller on the thermostat to process logic and control relays,
# switches and LEDs.
#
# Class Members
#	_thermo_on		:	Boolean indicating if the thermostat is on or off
#	_relay_on		:	Boolean indicating if the relay is open (heating on) or closed
#	_override_on	:	Boolean indicating if in override mode or not
#	_setpoint		:	Current temperature setpoint
#	_temperature	:	Last measured temperature
#	_gpio_bus		:	The instance of the GPIO bus access
#	_rules			:	An structure containing the thermostat rules
#	_kill_event		:	An event that signals that the thread is to end
#
class Thermostat(threading.Thread):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, event_handler, kill_event, sensor_period, data_cycles, query_base):
		# Set event handler
		self._ehandler = event_handler
		self._sensor_period = sensor_period
		self._data_cycles = data_cycles
		self._setpoint = 0.0	# Dummy value for startup
		self._setpoint_str = ''
		self._outdoor_temp_str = ''
		self._indoor_temp_str = ''
		self._override_on = False
		self._override_temp = 15.0  # Dummy to set the indicator at the bottom of the scale
		self._qbase = query_base
		self._thermo_on = False  # Set so first call to _set_thermo_status turns on the thermostat
		self._relay_on = True  # Set so first call to _set_relay_status turns off the relay
		
		# Setup default rules
		self._rules = [
			{ 'day': RULE_DAYS['Weekdays'], 'time': 23.5, 'temperature': 19.0 },
			{ 'day': RULE_DAYS['Weekdays'], 'time': 16.5, 'temperature': 22.0 },
			{ 'day': RULE_DAYS['Weekdays'], 'time':  8.0, 'temperature': 18.0 },
			{ 'day': RULE_DAYS['Weekdays'], 'time':  6.5, 'temperature': 22.0 },
			{ 'day': RULE_DAYS['Weekends'], 'time': 23.5, 'temperature': 19.0 },
			{ 'day': RULE_DAYS['Weekends'], 'time':  7.5, 'temperature': 22.0 } ]

		# Initialize the gpio
		self._gpio_bus = pigpio.pi()
		self._gpio_bus.set_mode(THERMO_POWER_PIN, pigpio.OUTPUT)
		self._gpio_bus.set_mode(RELAY_POWER_PIN, pigpio.OUTPUT)
		self._gpio_bus.set_mode(RELAY_STATUS_PIN, pigpio.OUTPUT)
		self._gpio_bus.set_mode(POWER_SWITCH_PIN, pigpio.INPUT)

		# Initialize Sensors
		self._lux_sensor = TSL2561(1)
		self._temp_sensor = HTU21D(1)

		# Initialize as a thread
		self._kill_event = kill_event
		threading.Thread.__init__(self)

	#---------------------------------------------------------------------------
	# run Method
	#---------------------------------------------------------------------------
	def run(self):
		# Connect to the GPIO bus
		logging.debug('Starting thermostat thread')
		
		# Initialize status of thermostat (set to on and relay closed)
		self._set_thermo_status(THERMOSTAT_ON)
		self._set_relay_status(RELAY_OFF)

		# Initialize the override settings on the display
		self._ehandler(messaging.DisplayTxMessage(messaging.Command(display.SET_STATUS, display.OVER_BTN, display.BTN_OFF)))
		self._ehandler(messaging.DisplayTxMessage(messaging.Command(display.SET_STATUS, display.OVER_SCALE, self._override_temp)))

		# Loop until time to close
		non_printing_loops = self._data_cycles
		while not self._kill_event.is_set():
			# Evaluate thermostat programming
			force_print = False
			if non_printing_loops == self._data_cycles:
				non_printing_loops = 1
				force_print = True
			else:
				non_printing_loops += 1
			self._evaluate_programming(force_print)
			
			# Wait until next control cycle
			self._kill_event.wait(self._sensor_period)

		# Shutdown the GPIO bus
		self._gpio_bus.stop()
		
		logging.debug('Thermostat thread closing')

	#---------------------------------------------------------------------------
	# process_command Method
	#---------------------------------------------------------------------------
	def process_command(self, Packet):
		# types: (DataPacket) -> none
		# Check that the passed type is correct
		logging.info('Thermostat received command and initiating processing')
		if type(Packet.packet) is messaging.Command:
			# Evaluate the type of command and get the response
			send_response = Packet.host != 'DISPLAY'
			cmd = Packet.packet
			if cmd.command == CMD_THERMO_POWER:
				logging.debug('  Request to change thermostat status received')
				response = self._update_thermo_status(Packet)
			elif cmd.command == CMD_OVERRIDE:
				logging.debug('  Request to change override status received')
				response = self._update_override(Packet)
			elif cmd.command == CMD_RULE_CHANGE:
				logging.debug('  Request to change rule received - not yet implemented')  # TODO implement this functionality
				response = messaging.DataPacket(Packet.Host, Packet.Port, 'TR:NACK')
			elif cmd.command == CMD_TIME_REQUEST:
				logging.debug('  Request for thermostat clock control received')
				response = self._clock_control(Packet)
			elif cmd.command == CMD_STATUS:
				logging.debug('  Request for thermostat status received')
				response = self._return_status(Packet)
			elif cmd.command == CMD_SHUTDOWN:
				# Force a shutdown
				logging.info('  Request for thermostat shutdown')
				self._force_shutdown()
				response = messaging.DataPacket(Packet.host, Packet.port, 'XX:ACK')

				# Set timer with delay and then set the kill event
				def signal_kill():
					self._kill_event.set()

				kill_timer = threading.Timer(1, signal_kill)  # 1 second delay
				kill_timer.start()
			else:
				logging.warning('  Unknown type of command received: %i - ignoring command', Packet.packet.command)
				send_response = False
			
			# Send response
			if send_response:
				logging.debug('  Sending Thermostat response to the LAN: %s', response.packet)
				self._ehandler(messaging.ThermostatRxMessage(response))
		else:	# Incorrect type passed
			logging.error('  Incorrect type of data passed to the thermostat - will not process')

	#---------------------------------------------------------------------------
	# _clock_control Method
	#---------------------------------------------------------------------------
	@staticmethod
	def _clock_control(dpack):
		# types: (DataPacket) -> DataPacket
		# Check the command type
		if dpack.packet.subcommand == STATUS_GET:
			# Get the current date and time
			cur_dt = datetime.now()
			
			# Create the response string
			resp_str = 'CR:GET:%i:%i:%i:%i:%i:%i:%i' % (cur_dt.year, cur_dt.month, cur_dt.day, cur_dt.weekday(), cur_dt.hour, cur_dt.minute, cur_dt.second)
		else:
			logging.critical('  Unknown clock control made it to the thermostat - THIS SHOULD NOT HAPPEN')
			return messaging.DataPacket(dpack.host, dpack.port, 'CR:NACK')
		
		# Return the acknowledgement/data
		return messaging.DataPacket(dpack.host, dpack.port, resp_str)
			
	#---------------------------------------------------------------------------
	# _update_thermo_status Method
	#---------------------------------------------------------------------------
	def _update_thermo_status(self, dpack):
		# types: (DataPacket) -> DataPacket
		# Check the status command
		if dpack.packet.subcommand == STATUS_ON:
			# Turn on the thermostat and evaluate relay status
			logging.info('  Thermostat is turning on')
			self._set_thermo_status(THERMOSTAT_ON)
			self._evaluate_programming(True)
		else:
			# Turn off the thermostat and open the relay
			logging.info('  Thermostat is turning off')
			self._set_thermo_status(THERMOSTAT_OFF)
			self._set_relay_status(RELAY_ON)
			self._update_database()
		
		# Return an acknowledgement
		return messaging.DataPacket(dpack.host, dpack.port, 'TS:ACK')

	#---------------------------------------------------------------------------
	# _force_shutdown Method
	#---------------------------------------------------------------------------
	def _force_shutdown(self):
		# Shutdown the thermostat
		self._set_thermo_status(THERMOSTAT_OFF)
		self._set_relay_status(RELAY_ON)
		self._update_database()

	#---------------------------------------------------------------------------
	# _update_override Method
	#---------------------------------------------------------------------------
	def _update_override(self, dpack):
		# types: (DataPacket) -> DataPacket
		# Check the status command
		if dpack.packet.subcommand == STATUS_ON:
			# Set the override mode and setpoint
			logging.info('  Thermostat is turning override mode on with setpoint %.2f', dpack.packet.data)
			self._override_on = True
			self._override_temp = dpack.packet.data
			self._setpoint = self._override_temp
			button_status = display.BTN_ON
		else:
			# Set override mode
			logging.info('  Thermostat is turning override mode off')
			self._override_on = False
			button_status = display.BTN_OFF
			if dpack.packet.data:
				self._override_temp = dpack.packet.data

		# Update the display if command was from the LAN
		if dpack.host != 'DISPLAY':
			self._ehandler(messaging.DisplayTxMessage(messaging.Command(display.SET_STATUS, display.OVER_BTN, button_status)))
			self._ehandler(messaging.DisplayTxMessage(messaging.Command(display.SET_STATUS, display.OVER_SCALE, self._override_temp)))
		
		# Re-evaluation relay status against the setpoint
		self._evaluate_programming(True)	# Force an update based on status
		
		# Return an acknowledgement
		return messaging.DataPacket(dpack.host, dpack.port, 'PO:ACK')
		
	#---------------------------------------------------------------------------
	# _return_status Method
	#---------------------------------------------------------------------------
	def _return_status(self, dpack):
		# types: (DataPacket) -> DataPacket
		# Create the response string
		resp_str = 'ST:'	# Status data identifier
		resp_str += 'ON:' if self._thermo_on else 'OFF:'	# Status of the thermostat power 
		resp_str += 'ON:' if self._relay_on else 'OFF:'		# Status of the relay
		resp_str += '%.2f:' % self._temperature			    # Last measured temperature
		resp_str += '%.2f:' % self._setpoint			    # Return the current temperature setpoint
		resp_str += 'ON' if self._override_on else 'OFF'	# Return status of the override
		
		# Create and return the response data packet
		return messaging.DataPacket(dpack.host, dpack.port, resp_str)
		
	#---------------------------------------------------------------------------
	# _set_thermo_status Method
	#---------------------------------------------------------------------------
	def _set_thermo_status(self, PowerStatus):
		# types: (boolean) -> none
		# Check to see if anything needs to change
		if self._thermo_on != PowerStatus:
			# Update object status
			logging.info('    Turning thermostat %s', 'on' if PowerStatus == THERMOSTAT_ON else 'off')
			self._thermo_on = PowerStatus

			# Update the power indicators
			if PowerStatus == THERMOSTAT_ON:	# Turn on the LED
				self._gpio_bus.write(THERMO_POWER_PIN, 1)	# Power up the button
				self._ehandler(messaging.DisplayTxMessage(messaging.Command(display.SET_STATUS, display.POWER_BTN, display.BTN_ON)))
			else:	# Turn off the LED
				self._gpio_bus.write(THERMO_POWER_PIN, 0)	# Power down the button
				self._ehandler(messaging.DisplayTxMessage(messaging.Command(display.SET_STATUS, display.POWER_BTN, display.BTN_OFF)))

	#---------------------------------------------------------------------------
	# _set_relay_status Method
	#---------------------------------------------------------------------------
	def _set_relay_status(self, RelayStatus):
		# types: (boolean) -> none
		# Check if relay status is actually changing, and take action
		if self._relay_on != RelayStatus:
			# Update object status
			logging.info('    Turning relay %s', 'on' if RelayStatus else 'off')
			self._relay_on = RelayStatus

			# Update the power indicators
			if RelayStatus == RELAY_ON:	# Close relay to turn on heat
				self._gpio_bus.write(RELAY_STATUS_PIN, 1)
				self._gpio_bus.write(RELAY_POWER_PIN, 0)
				self._ehandler(messaging.DisplayTxMessage(messaging.Command(display.SET_STATUS, display.RELAY_LED, display.LED_ON)))
			else:	# Open relay to turn off heat
				self._gpio_bus.write(RELAY_STATUS_PIN, 0)
				self._gpio_bus.write(RELAY_POWER_PIN, 1)
				self._ehandler(messaging.DisplayTxMessage(messaging.Command(display.SET_STATUS, display.RELAY_LED, display.LED_OFF)))

	#---------------------------------------------------------------------------
	# _evaluate_programming Method
	#---------------------------------------------------------------------------
	def _evaluate_programming(self, ForceUpdate = False):
		# types: (boolean) -> none
		# Read the current temperature
		logging.info('Thermostat control loop initiated')
		cur_temp = self._temp_sensor.read_temperature()
		self._temperature = cur_temp	# Store the last temperature read
		update_db = ForceUpdate
		
		# Update the display with the current temperature
		temp_str = '%.1f' % cur_temp
		if self._indoor_temp_str != temp_str:
			logging.debug('  Writing string %s to the display', temp_str)
			self._ehandler(messaging.DisplayTxMessage(messaging.Command(display.SET_STATUS, display.INSIDE_TEMP, temp_str)))
			self._indoor_temp_str = temp_str
		
		# Get the current time
		cur_time = time.localtime()
		cur_hour = cur_time.tm_hour + (60*cur_time.tm_min + cur_time.tm_sec)/3600.0
		cur_day = cur_time.tm_wday
		logging.debug('  Measured temperature %.2f Celsius on day %i at hour %.2f', cur_temp, cur_day, cur_hour)
		
		# Temperature checks
		# ----------------------------------------------------------------------
		if cur_temp < MIN_TEMPERATURE:	# Temperature below limit, turn on relay
			logging.debug('  Temperature below minimum temperature limit of %.2f Celsius', MIN_TEMPERATURE)
			if not self._relay_on:	# Turn on the relay if it is off
				self._set_relay_status(RELAY_ON)	# Turn on relay
				update_db = True	# Update the database due to relay state change
		elif cur_temp > MAX_TEMPERATURE:	# Temperature above limit, turn off relay
			logging.debug('  Temperature above maximum temperature limit of %.2f Celsius', MAX_TEMPERATURE)
			if self._relay_on:	# Turn off the relay if it is on
				self._set_relay_status(RELAY_OFF)	# Turn off relay
				update_db = True	# Update due to relay state change
		elif self._override_on:	# Override is on, so evaluate against setpoint
			# Evaluate against the override setpoint
			logging.debug('  Override Mode On - Checking against override setpoint (%.2f)', self._setpoint)
			if self._relay_on and (cur_temp > (self._setpoint + TEMPERATURE_BUFFER)):
				# Temperature exceeds override, so turn off relay
				self._set_relay_status(RELAY_OFF)
				update_db = True
			elif not self._relay_on and (cur_temp < (self._setpoint - TEMPERATURE_BUFFER)):
				# Temperature below override, so turn on relay
				self._set_relay_status(RELAY_ON)
				update_db = True
			else:
				# No change
				logging.debug('    Relay not changed')
		else:	# Temperature is within limits, so check against rules
			logging.debug('  Programming Mode On - Checking against programmed rules')
			rule_found = False	# Flag for finding the rule
			while not rule_found:	# Iterate through the rules until one is found
				for cur_rule in self._rules:
					if self._rule_applies(cur_rule, cur_day, cur_hour): # Rule applies
						# Determine how to control the relay
						if self._relay_on and (cur_temp > (cur_rule['temperature'] + TEMPERATURE_BUFFER)):
							# Temperature exceeds rule, so turn off relay
							logging.debug('    Relay turned off as temperature greater than setpoint (%.2f Celsius)', cur_rule['temperature'])
							self._set_relay_status(RELAY_OFF)
							update_db = True
						elif not self._relay_on and (cur_temp < (cur_rule['temperature'] - TEMPERATURE_BUFFER)):
							# Temperature below rule, so turn on relay
							logging.debug('    Relay turned on as temperature less than setpoint (%.2f Celsius)', cur_rule['temperature'])
							self._set_relay_status(RELAY_ON)
							update_db = True
						else:
							# No change
							logging.debug('    Relay remains %s as setpoint is %.2f Celsius', 'on' if self._relay_on else 'off', cur_rule['temperature'])
						
						# Rule found, so break from the loop
						rule_found = True
						self._setpoint = cur_rule['temperature']	# Keep track of current temperature setpoint
						break
				else:	# Rule not found
					# Decrease the day, but increase the time
					logging.debug('  Could not find the appropriate rule, moving back one day')
					if cur_day == RULE_DAYS['Monday']:
						cur_day = RULE_DAYS['Sunday']
					else:
						cur_day -= 1
					cur_hour += 24.0
			
		# Send thermostat status to database
		#-----------------------------------------------------------------------
		if update_db:
			self._update_database(cur_temp)

		# Update the display with the setpoint
		#-----------------------------------------------------------------------
		setpoint_str = 'Setpoint: %.1f' % self._setpoint
		if self._setpoint_str != setpoint_str:	# Only update if new string
			self._ehandler(messaging.DisplayTxMessage(messaging.Command(display.SET_STATUS, display.SETPOINT_TEMP, setpoint_str)))
			self._setpoint_str = setpoint_str

	#---------------------------------------------------------------------------
	# _update_database Method
	#---------------------------------------------------------------------------
	def _update_database(self, temperature = 0.0):
		# Get sensor data
		cur_temp = self._temp_sensor.read_temperature() if temperature == 0.0 else temperature
		cur_lux = self._lux_sensor.read_luminosity_opt()
		cur_h2o = self._temp_sensor.read_humidity()

		# Create the data package
		cur_data = {'temperature': cur_temp,
		            'luminosity_lux': cur_lux,
		            'humidity': cur_h2o,
		            'thermo_on': 1.0 if self._thermo_on else 0.0,
		            'heating_on': 1.0 if self._relay_on else 0.0}
		if self._override_on: cur_data['override'] = self._setpoint
		logging.debug('cur_data from thermostat._update_database: %s', cur_data)

		# Send the data package message
		logging.info('  Sending thermostat data to be transmitted through the LAN')
		request = self._create_request(cur_data)
		self._ehandler(messaging.ThermostatRxMessage(messaging.DBPacket(request)))

	#---------------------------------------------------------------------------
	# _create_request Method
	#---------------------------------------------------------------------------
	def _create_request(self, data):
		# types: (dict) -> string
		# Initialize the response string
		resp_str = self._qbase	# Set the base of the query

		# Include the radio
		resp_str += 'radio_id=40ab9778'
			
		# Iterate through all the sensors adding data
		for key, value in data.iteritems():
			resp_str += '&%s=%f' % ( key, value )
	
		# Return the string
		return resp_str

	#---------------------------------------------------------------------------
	# _rule_applies Method
	#---------------------------------------------------------------------------
	@staticmethod
	def _rule_applies(rule, weekday, hour):
		# types: (list, int, float) -> boolean
		# First check is to see that time is later than the rule
		if hour >= rule['time']:
			# Second round of checks
			if rule['day'] == RULE_DAYS['Everyday']: return True
			if weekday == rule['day']: return True
			if (rule['day'] == RULE_DAYS['Weekdays']) and (weekday <= RULE_DAYS['Friday']): return True
			if (rule['day'] == RULE_DAYS['Weekends']) and (weekday >= RULE_DAYS['Saturday']): return True
		
		return False	# Rule does not match
