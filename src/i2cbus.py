# i2cbus.py
# This class is the basic implementation of the I2C bus class for managing
# devices on as Raspberry Pi I2C system
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
import pigpio	# For GPIO control

#===============================================================================
# I2CBus Class
#===============================================================================
# Implements a high level class that communicates to a single device on the I2C
# bus of choice.
#
# Class Members
#	_bus_num:	The number of the bus
#				(if x is _bus_num, the bus is /dev/i2c-x)
#	_address:	The address of the I2C device
#	_bus:		The object containing the I2C bus interface
#
class I2CBus:
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, bus_number, address):
		# type: (int, int) -> none
		"""
		Constructor to set the bus number and device address.
		:param bus_number: The bus ID (0 or 1)
		:param address: The address of the I2C device
		"""
		self._bus_num = bus_number	# The bus number on the Pi
		self._address = address		# The address of the I2C device
		self._bus = pigpio.pi()		# The interface object for hte bus
		
	#---------------------------------------------------------------------------
	# _write Method
	#---------------------------------------------------------------------------
	# Write data buffer to the device
	def _write(self, msg_buffer):
		# type: (list) -> none
		"""
		Write data to the I2C device
		:param msg_buffer: The bytes to send
		"""
		handle = self._bus.i2c_open(self._bus_num, self._address)
		self._bus.i2c_write_device(handle, msg_buffer)	# Write bytes to device
		self._bus.i2c_close(handle)
	
	#---------------------------------------------------------------------------
	# _read Method
	#---------------------------------------------------------------------------
	# Read a data byte from the device
	def _read(self, size):
		# type: (int) -> list
		"""
		Reads a data buffer from the I2C device
		:param size: The number of byte to read from the device
		:return: The bytes read from the device
		"""
		handle = self._bus.i2c_open(self._bus_num, self._address)
		(count, data) = self._bus.i2c_read_device(handle, size)
		self._bus.i2c_close(handle)
		
		return data
	
	#---------------------------------------------------------------------------
	# _write_register Method
	#---------------------------------------------------------------------------
	# Writes a byte command to a defined register
	def _write_register(self, register, msg_buffer):
		# type: (int, list) -> none
		"""
		Writes a list of commends to a device register
		:param register: The register to write to
		:param msg: The list of commands to send to the register
		"""
		handle = self._bus.i2c_open(self._bus_num, self._address)
		self._bus.i2c_write_i2c_block_data(handle, register, msg_buffer)
		self._bus.i2c_close(handle)
	
	#---------------------------------------------------------------------------
	# _read_register Method
	#---------------------------------------------------------------------------
	# Reads a list of bytes from a register
	def _read_register(self, register, size):
		# type: (int, int) -> list
		"""
		Reads a list of bytes from a specified register
		:param register: The register to read from
		:param size: The number of bytes to read from the register
		:return: The bytes read from the device
		"""
		handle = self._bus.i2c_open(self._bus_num, self._address)
		(count, data) = self._bus.i2c_read_i2c_block_data(handle, register, size)
		self._bus.i2c_close(handle)
		
		return data
