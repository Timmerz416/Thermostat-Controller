# tsl2561.py
# This class implements the functionality of the TSL2561 Luminosity sensor
# through I2C.
#
# The MIT License (MIT)
# Copyright (c) 2017 Tim Lampman
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
import time
from i2cbus import I2CBus

#===============================================================================
# Constants
#===============================================================================
# Addresses
TSL2561_BUS_ADDRESS			= 0x39

# Registers
TSL2561_CONTROL_REG			= 0x00	# Control of basic functions
TSL2561_TIMING_REG			= 0x01	# Integration time/gain control
TSL2561_THRESHOLD_LOWLOW	= 0x02	# Low byte of low interrupt threshold
TSL2561_THRESHOLD_LOWHIGH	= 0x03	# High byte of low interrupt threshold
TSL2561_THRESHOLD_HIGHLOW	= 0x04	# Low byte of high interrupt threshold
TSL2561_THRESHOLD_HIGHHIGH	= 0x05	# High byte of high interrupt threshold
TSL2561_INTERRUPT			= 0x06	# Interrupt control
TSL2561_ID					= 0x0A	# Part number / revision ID
TSL2561_CH0_DATA_LOW		= 0x0C	# Low byte of ADC Channel 0
TSL2561_CH0_DATA_HIGH		= 0x0D	# High byte of ADC Channel 0
TSL2561_CH1_DATA_LOW		= 0x0E	# Low byte of ADC Channel 1
TSL2561_CH1_DATA_HIGH		= 0x0F	# High byte of ADC Channel 1

# Commands
TSL2561_COMMAND				= 0x80	# Identify transaction as a command
TSL2561_CLEAR_BIT			= 0x40	# Clears pending transactions
TSL2561_WORD_BIT			= 0x20	# Indicates if a word is to be read/written
TSL2561_BLOCK_BIT			= 0x10	# Turn on blocking

# Power options
TSL2561_POWER_OFF			= 0x00	# Power down the device
TSL2561_POWER_ON			= 0x03	# Power on the device

# Gain options
TSL2561_GAIN_LOW			= 0x00	# Low (x1) gain setting
TSL2561_GAIN_HIGH			= 0x10	# High (x16) gain setting

# Integration time options
TSL2561_INTEGRATE_SHORT		= 0x00	# Shortest (13.7 ms) window
TSL2561_INTEGRATE_MEDIUM	= 0x01	# Middle (101 ms) window
TSL2561_INTEGRATE_LONG		= 0x02	# Longest (402 ms) window

# Channel options
TSL2561_CHANNEL_0			= 0		# The visible + IR sensor
TSL2561_CHANNEL_1			= 1		# The IR only sensor

#===============================================================================
# TSL2561 Class
#===============================================================================
# Implements an interface to the TSL2561 sensor through I2C.
#
# Class Members
#	_gain:			The current gain setting of the device
#	_int_period:	The current integration setting
#
class TSL2561(I2CBus):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, bus_number):
		# type: (int) -> none
		"""
		Constructor for the TSL2561 object.  Determines the integration/gain.
		:param bus_number: The number of the I2C bus that the TSL2561 is on
		"""
		I2CBus.__init__(self, bus_number, TSL2561_BUS_ADDRESS)
		
		# Determine the current sensor settings
		command = TSL2561_COMMAND | TSL2561_TIMING_REG
		response = self._read_register(command, 1)	# Get the integration/gain settings
		
		# Set settings
		self._gain = response[0] & TSL2561_GAIN_HIGH
		self._int_period = response[0] & TSL2561_INTEGRATE_LONG

	#---------------------------------------------------------------------------
	# enable Method
	#---------------------------------------------------------------------------
	# Turns on the power to the sensor
	def enable(self):
		# type: (none) -> none
		"""
		Turn on the power to the sensor.
		"""
		command = TSL2561_COMMAND | TSL2561_CONTROL_REG
		self._write_register(command, [ TSL2561_POWER_ON ])	# Send command to turn on power

	#---------------------------------------------------------------------------
	# disable Method
	#---------------------------------------------------------------------------
	# Turns off the power to the sensor
	def disable(self):
		# type: (none) -> none
		"""
		Turn off the power to the sensor.
		"""
		command = TSL2561_COMMAND | TSL2561_CONTROL_REG
		self._write_register(command, [ TSL2561_POWER_OFF ]) # Send command to turn off power

	#---------------------------------------------------------------------------
	# set_timing Method
	#---------------------------------------------------------------------------
	# Set the integration and gain settings on the sensor
	def set_timing(self, gain, int_period):
		# type: (int, int) -> none
		"""
		Set the integration/gain settings.
		:param gain: The gain setting
		:param int_period: The integration window
		"""
		# Set the internal setting
		self._gain = gain
		self._int_period = int_period
		
		# Update timing
		command = TSL2561_COMMAND | TSL2561_TIMING_REG
		option = self._gain | self._int_period
		self._write_register(command, [ option ])

	#---------------------------------------------------------------------------
	# get_channel_data Method
	#---------------------------------------------------------------------------
	# Reads the raw measured luminosity from the specified channel
	def get_channel_data(self, channel):
		# type (int) -> list
		"""
		Read the data from the specified channel.
		:param channel: The channel to read the data from
		"""
		# Turn on the sensor and wait for integration period
		self.enable()
		if self._int_period == TSL2561_INTEGRATE_SHORT:
			time.sleep(0.02)	# Sleep for 20 ms (6 ms extra)
		elif self._int_period == TSL2561_INTEGRATE_MEDIUM:
			time.sleep(0.11)	# Sleep for 110 ms (9 ms extra)
		else:
			time.sleep(0.41)	# Sleep for 410 ms (8 ms extra)
		
		# Get the data and return
		command = TSL2561_COMMAND | TSL2561_WORD_BIT | (TSL2561_CH0_DATA_LOW if channel == TSL2561_CHANNEL_0 else TSL2561_CH1_DATA_LOW)
		data = self._read_register(command, 2)
		self.disable()
		
		return (data[1] << 8) | data[0]

	#---------------------------------------------------------------------------
	# _convert_lux Method
	#---------------------------------------------------------------------------
	# Convert the measured luminosity in both channels to luminosity in lux
	def _convert_lux(self, chan0, chan1):
		# type: (int, int) -> double
		'''
		Convert the measured channel data from the sensors to lux.
		:param chan0: The sensor measurement from channel 0
		:param chan1: The sensor measurement from channel 1
		:return: The luminosity in lux
		'''
		# Calculate luminosity from measured data
		if chan0 != 0:
			# Determine scaling factor - account for integration time
			if self._int_period == TSL2561_INTEGRATE_SHORT:
				scale = 402.0/13.7
			elif self._int_period == TSL2561_INTEGRATE_MEDIUM:
				scale = 402.0/101.0
			else:
				scale = 1.0
			scale *= 16.0 if self._gain == TSL2561_GAIN_LOW else 1.0	# Account for gain
			
			# Scale measurements
			d0 = scale*chan0
			d1 = scale*chan1
			
			# Luminosity calculation from the TSL2561 datasheet
			ratio = chan1/chan0
			if ratio <= 0.5:
				lum_lux = 0.0304*d0 - 0.062*d0*ratio**1.4
			elif ratio <= 0.61:
				lum_lux = 0.0224*d0 - 0.031*d1
			elif ratio <= 0.8:
				lum_lux = 0.0128*d0 - 0.0153*d1
			elif ratio <= 1.3:
				lum_lux = 0.00146*d0 - 0.00112*d1
			else:
				lum_lux = 0.0
		else:
			lum_lux = 0.0;	# Set luminosity to zero
		
		return lum_lux
		
	#---------------------------------------------------------------------------
	# read_luminosity Method
	#---------------------------------------------------------------------------
	# Read the luminosity based on current sensor setting and report in lux
	def read_luminosity(self):
		# type: (none) -> double
		"""
		Reads the luminosity using the current integration/gain settings.
		:return: The measured luminosity in lux
		"""
		# Get the measured data in both channels
		chan0_data = self.get_channel_data(TSL2561_CHANNEL_0)
		chan1_data = self.get_channel_data(TSL2561_CHANNEL_1)
		print '\tRaw data: %04x %04x' % (chan0_data, chan1_data)
		
		# Return the lux
		return self._convert_lux(chan0_data, chan1_data)

	#---------------------------------------------------------------------------
	# read_luminosity_opt Method
	#---------------------------------------------------------------------------
	# Optimize the sensor measurements to give a reasonable luminosity
	# measurement, if possible, and report in lux
	def read_luminosity_opt(self):
		# type (none) -> double
		"""
		Optimizes the sensor settings to give best luminosity reading.
		:return: The measured luminosity in lux
		"""
		# Initialize variables
		lux_captured = False
		chan0_data = chan1_data = 0
		gain = self._gain
		int_period = self._int_period
		
		# Loop until acceptable luminosity found
		while not lux_captured:
			# Get raw luminosity measurement
			chan0_data = self.get_channel_data(TSL2561_CHANNEL_0)
			chan1_data = self.get_channel_data(TSL2561_CHANNEL_1)
			print '\tRaw data: %04x %04x %i %i' % (chan0_data, chan1_data, self._gain, self._int_period)
			
			# Evaluate signal strength - this is a bit crude with gain treatment
			if (chan0_data == 0xFFFF) or (chan1_data == 0xFFFF):	# Saturated signal
				# Sensor saturated, so adjust timing
				if gain == TSL2561_GAIN_HIGH:	# Lower the gain
					gain = TSL2561_GAIN_LOW
					int_period = TSL2561_INTEGRATE_LONG	# To search for a good integration for the gain setting
				elif int_period > TSL2561_INTEGRATE_SHORT:	# Reduce integration time
					int_period -= 1
				else:	# Can't make further adjustments, so have to live with this
					lux_captured = True
			elif (chan0_data < 10) or (chan1_data < 10):	# Low signal
				# Low signal, so try adjusting timing
				if int_period < TSL2561_INTEGRATE_LONG:	# Increase integration time
					int_period += 1
				elif gain == TSL2561_GAIN_LOW:	# Increase the gain
					gain = TSL2561_GAIN_HIGH
					int_period = TSL2561_INTEGRATE_SHORT	# To search for a good integration time for gain
				else:	# Can't make further changes
					lux_captured = True
			else:	# Signal is good
				lux_captured = True
			
			# If needed, reset the timing
			if not lux_captured: self.set_timing(gain, int_period)
		
		# Return the luminosity in lux
		return self._convert_lux(chan0_data, chan1_data)
