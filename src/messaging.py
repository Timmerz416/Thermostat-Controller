# messaging.py
# This module contains several items related to messaging within the thermopi
# controller program
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

#===============================================================================
# CONSTANTS
#===============================================================================
#Message IDs
MESSAGE_ERROR		=  0
XBEE_RX_MESSAGE		=  1
XBEE_TX_MESSAGE		=  2
THERMO_RX_MESSAGE	=  3
THERMO_TX_MESSAGE	=  4
LAN_RX_MESSAGE		=  5
LAN_TX_MESSAGE		=  6
DISPLAY_RX_MESSAGE	=  7
DISPLAY_TX_MESSAGE	=  8


#===============================================================================
# FUNCTIONS
#===============================================================================
#-------------------------------------------------------------------------------
# binary_print Function
#-------------------------------------------------------------------------------
def binary_print(bin_data, separator):
	# types: (list, string) -> string
	"""
	This method take a list of bytes and converts to a string with formatted
	output.

	:param	bin_data:
	:param  separator:
	"""
	output = ''	# Empty string
	for byte in bin_data:
		output += '%02x%s' % ( ord(byte), separator )

	return output if separator == '' else output[0:-1]


#===============================================================================
# Message class
#===============================================================================
# Basic class that handles simple messages with associated data
class Message(object):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, ID, Data):
		self._id = ID
		self._data = Data
	
	#---------------------------------------------------------------------------
	# to_string Method
	#---------------------------------------------------------------------------
	def to_string(self):
		return 'Message object data: %i %s' % ( self._id, self._data )
		
	#---------------------------------------------------------------------------
	# _error_message Method
	#---------------------------------------------------------------------------
	def _error_message(self):
		return 'Message type is unrecognized, unexpected and therefore, assumed to be in error: %s' % self._data

	#---------------------------------------------------------------------------
	# get_id Function
	#---------------------------------------------------------------------------
	def get_id(self):
		return self._id
	
	#---------------------------------------------------------------------------
	# get_data Function
	#---------------------------------------------------------------------------
	def get_data(self):
		return self._data


#===============================================================================
# XBeeRxMessage Class
#===============================================================================
# Class for handling received XBee messages
class XBeeRxMessage(Message):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, Packet):
		# types: (DataPacket) -> none
		# Initialize members - TODO To CHECK FOR DataPacket TYPE
		Message.__init__(self, XBEE_RX_MESSAGE, Packet)


#===============================================================================
# ThermostatRxMessage
#===============================================================================
# Class for handling messages from the thermostat.  They could either be data
# messages for the database, or a response through a socket
class ThermostatRxMessage(Message):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, Packet):
		# types: (DataPacket) -> none
		# Initialize members - TODO TO CHECK FOR DataPacket TYPE
		Message.__init__(self, THERMO_RX_MESSAGE, Packet)


#===============================================================================
# ThermostatTxMessage Class
#===============================================================================
# Class for handling messages going to the thermostat.  These would contain
# commands from a socket.
class ThermostatTxMessage(Message):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, Packet):
		# types: (DataPacket) -> none
		# Initialize members - TODO TO CHECK FOR DataPacket TYPE
		Message.__init__(self, THERMO_TX_MESSAGE, Packet)


#===============================================================================
# Command Class
#===============================================================================
# Simple class containing a command, possible command type (subcommand), and
# possibly associated data for the command
class Command(object):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, Cmd, SubCmd, CmdData):
		# types: (int, int, list) -> none
		self.command = Cmd
		self.subcommand = SubCmd
		self.data = CmdData

	#---------------------------------------------------------------------------
	# __str__ Override
	#---------------------------------------------------------------------------
	def __str__(self):
		return '(%i, %i, %i)' % ( self.command, self.subcommand, self.data )


#===============================================================================
# DataPacket Class
#===============================================================================
# Simple class that contains the network host, port and transfer data packet,
# which can be of type Command or a response string
#
# Members
#	host	:	The IP of the host that sent, or will receive, the packet
#	port	:	The port to connect to at the host
#	packet	:	The data packet to be transferred
class DataPacket(object):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, Host, Port, Packet):
		self.host = Host
		self.port = Port
		self.packet = Packet

	#---------------------------------------------------------------------------
	# __str__ Override
	#---------------------------------------------------------------------------
	def __str__(self):
		return '(%s, %s, %s)' % ( self.host, self.port, self.packet )


#===============================================================================
# DBPacket Class
#===============================================================================
# Class inheriting DataPacket meant for the database - the host and port members
# are null
class DBPacket(DataPacket):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, Packet):
		DataPacket.__init__(self, None, None, Packet)


#===============================================================================
# DisplayPacket Class
#===============================================================================
# Class inheriting DataPacket meant for the display - the host and port members
# are set to the string DISPLAY
class DisplayPacket(DataPacket):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, Packet):
		DataPacket.__init__(self, 'DISPLAY', 'DISPLAY', Packet)


#===============================================================================
# LANRxMessage Class
#===============================================================================
# Class that contains a message from a socket on the LAN
class LANRxMessage(Message):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, Packet):
		# types: (DataPacket) -> none
		# Initialize members - TODO TO CHECK FOR DataPacket TYPE
		Message.__init__(self, LAN_RX_MESSAGE, Packet)

	#---------------------------------------------------------------------------
	# get_command Method
	#---------------------------------------------------------------------------
	def get_command(self):
		# types: (none) -> Command
		return self._data.packet
		

#===============================================================================
# LANTxMessage Class
#===============================================================================
# Class for contains messages going to the LAN.  These could either be for the
# the database (no host/port specified) or as a reply to a socket command.
class LANTxMessage(Message):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, Packet):
		# types: (DataPacket) -> none
		# Initialize members - TODO TO CHECK FOR DataPacket TYPE
		Message.__init__(self, LAN_TX_MESSAGE, Packet)

	#---------------------------------------------------------------------------
	# is_http Method
	#---------------------------------------------------------------------------
	def is_http(self):
		# types: (none) -> boolean
		return self._data.host is None
		
	#---------------------------------------------------------------------------
	# get_host Method
	#---------------------------------------------------------------------------
	def get_host(self):
		return self._data.host


#===============================================================================
# DisplayTxMessage Class
#===============================================================================
# Class for contains messages going to the 4D display.
class DisplayTxMessage(Message):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, command):
		# types: (Command) -> none
		# Initialize members - TODO To CHECK FOR DataPacket TYPE
		Message.__init__(self, DISPLAY_TX_MESSAGE, DisplayPacket(command))


#===============================================================================
# DisplayRxMessage Class
#===============================================================================
# Class contains messages from the 4D display.
class DisplayRxMessage(Message):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	def __init__(self, Packet):
		# types: (DataPacket) -> none
		# Initialize members - TODO TO CHECK FOR DataPacket TYPE
		Message.__init__(self, DISPLAY_RX_MESSAGE, Packet)
