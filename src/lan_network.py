# lan_network.py
# This class implements the functionality of communicating over the LAN
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
import threading
import messaging
import httplib
import logging
import socket
import select
import thermostat
import config

#===============================================================================
# CONSTANTS
#===============================================================================
SOCKET_DELAY			= 0.1	# Delay in seconds for socket client read
SOCKET_MESSAGE_LENGTH	= 50	# Maximum length for a LAN command

#===============================================================================
# LANMessages Class
#===============================================================================
# Implements a class that handles incoming messages over the LAN
#
# Class Members
#	_ehandler:	The callback function that will handle incoming LAN messages
#
class LANNetwork(threading.Thread):
	#---------------------------------------------------------------------------
	# Constructor
	#---------------------------------------------------------------------------
	#
	def __init__(self, event_handler, kill_event, port):
		# Set event handler
		self._ehandler = event_handler
		
		# Initialize the server - TODO to handle issues with connecting to the port
		self._port = port
		self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._server.bind(('', port))
		self._server.listen(5)
		self._descriptors = [ self._server ]
		logging.info('LANServer started on port %s', port)

		# Initialize as a thread
		self._kill_event = kill_event
		threading.Thread.__init__(self)
		
	#---------------------------------------------------------------------------
	# Main thread execution
	#---------------------------------------------------------------------------
	def run(self):
		# Open a listening socket
		logging.debug('Starting LAN thread')
		
		# Loop until time to close
		while not self._kill_event.is_set():
			# Await for activity on the socket for a delay
			(sread, swrite, sexc) = select.select(self._descriptors, [], [], SOCKET_DELAY)
		 
			# Iterate through any sockets with data to read
			for sock in sread:
				# Check socket type
				if sock == self._server:	# Received a new connection
					self._accept_new_connection()
				else:	# Activity on an existing socket
					# Read and check data on socket
					sock_packet = sock.recv(SOCKET_MESSAGE_LENGTH)
					host,port = sock.getpeername()
					if not sock_packet:	# Socket closing
						sock.close()
						self._descriptors.remove(sock)
						logging.debug('  Socket from %s:%s closing', host, port)
					else:	# Data here to process, send to the message queue
						logging.info('Received request from socket on %s:%s', host, port)
						logging.debug('  Message from socket is %s', sock_packet)
						self._handle_command(host, sock_packet)
	
		# Close the listening socket
		self._server.close()
		logging.debug('LAN thread closing')

	#---------------------------------------------------------------------------
	# _handle_command Method
	#---------------------------------------------------------------------------
	def _handle_command(self, host_address, command):
		# types: (string, string) -> none
		# Parse the command
		tokens = command.split(':')
		
		# Setup data structure based on command
		command_error = False
		if tokens[1] == 'TS':	# Thermostat power control
			# Check if the command is to turn on the thermostat
			if tokens[2] == 'ON':
				logging.info('  Received LAN command to turn on the thermostat')
				cmd = messaging.Command(thermostat.CMD_THERMO_POWER, thermostat.STATUS_ON, None)
			elif tokens[2] == 'OFF':
				logging.info('  Received LAN command to turn off the thermostat')
				cmd = messaging.Command(thermostat.CMD_THERMO_POWER, thermostat.STATUS_OFF, None)
			else:
				logging.error('  Received unrecognized thermostat power command %s - no action taken', tokens[2])
				command_error = True
			
		elif tokens[1] == 'PO':	# Program override
			# Check if the command is to turn the override on
			if tokens[2] == 'ON':
				logging.info('  Received LAN command to turn on override mode with a setpoint of %s', tokens[3])
				cmd = messaging.Command(thermostat.CMD_OVERRIDE, thermostat.STATUS_ON, float(tokens[3]))
			elif tokens[2] == 'OFF':
				logging.info('  Received LAN command to turn off override mode')
				cmd = messaging.Command(thermostat.CMD_OVERRIDE, thermostat.STATUS_OFF, float(tokens[3]) if len(tokens) >= 4 else None)
			else:
				logging.error('  Received unrecognized override command %s - no action taken', tokens[2])
				command_error = True
				
		elif tokens[1] == 'TR':	# Thermostat rule change
			logging.warning('  Thermostat rule change logic not implemented yet')
			command_error = True
		
		elif tokens[1] == 'CR':	# Clock control
			# Check clock control command
			if tokens[2] == 'GET':	# Get the current time information
				logging.info('  Received LAN command to get the current thermostat time')
				cmd = messaging.Command(thermostat.CMD_TIME_REQUEST, thermostat.STATUS_GET, None)
			else:
				logging.error('  Received unrecognized clock control command %s - no action taken', tokens[2])
				command_error = True
			
		elif tokens[1] == 'ST':	# Thermostat status
			logging.info('  Received LAN command to return the status of the thermostat')
			cmd = messaging.Command(thermostat.CMD_STATUS, None, None)
			
		elif tokens[1] == 'XX':	# Program shutdown
			logging.info('  Received LAN command to shutdown the thermostat program')
			cmd = messaging.Command(thermostat.CMD_SHUTDOWN, None, None)
			
		else:	# Unrecognized command type
			logging.warning('  Received LAN command %s was unexpected - no action taken', tokens[1])
			command_error = True
		
		# Pass the command on
		if not command_error:
			self._ehandler(messaging.LANRxMessage(messaging.DataPacket(host_address, tokens[0], cmd)))
		else:
			err_response = tokens[1]
			err_response += ':NACK' if tokens[1] else 'NACK'
			self._ehandler(messaging.LANTxMessage(messaging.DataPacket(host_address, tokens[0], err_response)))
	
	#---------------------------------------------------------------------------
	# _accept_new_connection Method
	#---------------------------------------------------------------------------
	def _accept_new_connection(self):
		newsock, (remhost, remport) = self._server.accept()
		self._descriptors.append(newsock)
		logging.info('Accepted new connection from %s on port %s', remhost, remport)

	#---------------------------------------------------------------------------
	# send_http_request Method
	#---------------------------------------------------------------------------
	@staticmethod
	def send_http_request(GetRequest):
		# types: (string) -> boolean
		# Create the connection to the HTTP server
		logging.debug('  Sending HTTP request to LAN: %s', GetRequest)
		httpconn = httplib.HTTPConnection(config.DB_ADDRESS)
		
		# Send request and read response
		httpconn.request('GET', GetRequest)
		httpresp = httpconn.getresponse()

		# Process the response
		if httpresp.reason == "OK":
			logging.debug('    LAN HTTP response received: OK')
			success = True
		else:
			resp_data = httpresp.read()
			logging.warning('  Issue with sent HTTP request (%s) returned: %s', GetRequest, resp_data)
			success = False
		
		# Close connection and return
		httpconn.close()
		return success
		
	#---------------------------------------------------------------------------
	# send_socket_request Method
	#---------------------------------------------------------------------------
	@staticmethod
	def send_socket_request(DPacket):
		# types: (list, string) -> boolean
		# Create the socket connection
		client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		client.connect((DPacket.host, int(DPacket.port)))
		
		# Send the response and close
		client.send(DPacket.packet)
		client.close()
		
		return True
