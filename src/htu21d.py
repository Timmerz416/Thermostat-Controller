# htu21d.py
# This class implements the functionality of the HTU21D temperature/humidity
# sensor through I2C.
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

# Constants
HTU21D_BUS_ADDRESS			= 0x40

HTU21D_TEMPERATURE_HOLD		= 0xE3
HTU21D_TEMPERATURE_NOHOLD	= 0xF3
HTU21D_HUMIDITY_HOLD		= 0xE5
HTU21D_HUMIDITY_NOHOLD		= 0xF5
HTU21D_WRITE_USER_REGISTER	= 0xE6
HTU21D_READ_USER_REGISTER	= 0xE7
HTU21D_SOFT_RESET			= 0xFE

#===============================================================================
# HTU21D Class
#===============================================================================
# Implements an interface to the HTU21D sensor through I2C.
#
# Class Members
#
class HTU21D(I2CBus):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, bus_number):
		# types: (int) -> none
		"""
		Constructor for the HTU21D object.
		:param bus_number: The number of the I2C bus that the HTU21D is on
		"""
		I2CBus.__init__(self, bus_number, HTU21D_BUS_ADDRESS)
	
	#---------------------------------------------------------------------------
	# soft_reset Method
	#---------------------------------------------------------------------------
	def soft_reset(self):
		# types: (none) -> none
		"""
		Reset the HTU21D by power cycling on the chip.
		"""
		self._write([HTU21D_SOFT_RESET])	# Sent reset command
		time.sleep(0.03)	# Wait for 30 ms as the chip needs 15 ms
		
	#---------------------------------------------------------------------------
	# read_temperature Method
	#---------------------------------------------------------------------------
	def read_temperature(self):
		# types: (none) -> double
		"""
		Read the current temperature on the HTU21D
		:return: The temperature in degrees Celcius
		"""
		# Signal for measurement and wait
		self._write([HTU21D_TEMPERATURE_NOHOLD])
		time.sleep(0.06)	# The chip needs up to 50 ms
		
		# Read the measurement
		data = self._read(3)
		
		# Convert to temperature
		raw_temp = (data[0] << 8) | data[1]
		raw_temp &= 0xFFFC	# Remove any status bits
		
		return 175.72*(raw_temp/65536.0) - 46.85

	#---------------------------------------------------------------------------
	# read_humidity Method
	#---------------------------------------------------------------------------
	def read_humidity(self):
		# types: (none) -> double
		"""
		Read the current humidity on the HTU21D
		:return: The humidity in percent relative humidity
		"""
		# Signal for measurement and wait
		self._write([HTU21D_HUMIDITY_NOHOLD])
		time.sleep(0.06)	# The chip needs up to 50 ms
		
		# Read the measurement
		data = self._read(3)
		
		# Convert to humidity and return
		raw_humidity = (data[0] << 8) | data[1]
		raw_humidity &= 0xFFFC	# Remove the status bits
		
		return 125.0*(raw_humidity/65536.0) - 6.0
