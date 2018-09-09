#!/usr/bin/python
# 
# Imports
import xbee_network
import messaging
import thermostat
import lan_network
import display
import Queue
import logging.config
import threading
import argparse
import yaml
import urllib
from time import sleep
from datetime import datetime
from local_stores import LocalStorage

# ===============================================================================
# CONSTANTS
# ===============================================================================
# Timing
MESSAGE_DELAY = 0.001  # The delay between checking for new messages
NORM_CONTROL_INTERVAL = 10  # Number of sensor cycles for sensor data output
DEBUG_CONTROL_INTERVAL = 3  # As above for debugging
NORM_SENSOR_DELAY = 60  # Time in seconds between thermostat temperature readings
DEBUG_SENSOR_DELAY = 60  # As above for debugging

# Database
NORM_DB_UPLOAD = '/db_sensor_upload.php?'
DEBUG_DB_UPLOAD = '/db_test_upload.php?'

# ===============================================================================
# GLOBAL VARIABLES
# ===============================================================================
message_list = Queue.Queue()
shutdown = threading.Event()
config = None  # Contains the settings read from the config file

# ===============================================================================
# FUNCTIONS
# ===============================================================================
# -------------------------------------------------------------------------------
# queue_message Function
# -------------------------------------------------------------------------------
def queue_message(in_msg):
	if isinstance(in_msg, messaging.Message):
		# Add to the message list
		message_list.put(in_msg)
	else:
		logger.warning('Wrong type (%s) sent to queue, message will be ignored', type(in_msg))

# -------------------------------------------------------------------------------
# dispatch_message Function
# -------------------------------------------------------------------------------
def dispatch_message(cur_msg):
	# types: (string) -> None
	# Determine the type of message received
	msg_id = cur_msg.get_id()

	if msg_id == messaging.XBEE_TX_MESSAGE:  # Transmit command to XBees
		pass  # For future functionality, but not needed now

	elif msg_id == messaging.THERMO_TX_MESSAGE:  # Transmit thermostat command
		logger.debug('  Sending Thermostat transmission request, forwarding to the Thermostat')
		thermo_thread.process_command(cur_msg.get_data())

	elif msg_id == messaging.LAN_TX_MESSAGE:  # Send a message over the LAN
		# Send message over the LAN
		logger.debug('  Received LAN transmission request for %s', 'database' if cur_msg.is_http() else 'socket')
		if cur_msg.is_http():  # Database message via http
			logger.info('Sending LAN transmission request via HTTP')
			if not lan_thread.send_http_request(cur_msg.get_data().packet):
				add_time = "&time=" + urllib.quote("'" + datetime.now().isoformat(' ')[0:19] + "'")  # Create string addition to set measurement time
				saved_request = cur_msg.get_data().packet + add_time  # Updated request that sets current time as measurement time
				
				# Send the request to the local database to be saved and sent later when connected to main database
				local_db.push(saved_request)
		else:
			logger.info('Sending LAN transmission response via a socket')
			if not lan_thread.send_socket_request(cur_msg.get_data()):
				pass  # TODO - figure out how to deal with socket response not working - probably just log the error

	elif msg_id == messaging.DISPLAY_TX_MESSAGE:  # Transmitting message to the display
		# Send message to the display
		display_thread.process_message(cur_msg.get_data())

	else:  # Something not expected
		logger.warning('Message queue contains unknown message type: %i', msg_id.get_id())


# ===============================================================================
# MAIN EXECUTION
# ===============================================================================
# Parse any command line arguments
parser = argparse.ArgumentParser(description='Start the thermostat controller (defalut is NORMAL)')
parser.add_argument('-m', '--mode', dest='mode', choices=['NORMAL', 'DEBUG'], default='NORMAL', help='The mode to run the controller in')
parser.add_argument('-d', '--delay', dest='delay', type=int, default=0, required=False, help='Set the startup delay (in seconds) before initiating thermostat')

args = parser.parse_args()

# Pause for execution of any startup services
sleep(args.delay)  # Delay for specified seconds while system services start

# Initialize the logger
log_level = logging.INFO if args.mode == 'NORMAL' else logging.DEBUG
if log_level == logging.INFO:
	logging.config.fileConfig('/home/tl1/.thermopi.logger.conf')
else:
	logging.config.fileConfig('/home/tl1/.thermopi.logger.debug.conf')
logger = logging.getLogger('MAIN')

logger.info('Starting up the program in %s mode.', 'Normal' if args.mode == 'NORMAL' else 'Debug')

# Read in the configuration file
config_file = '/home/tl1/.thermopi.conf' if args.mode == 'NORMAL' else '/home/tl1/.thermopi.debug.conf'
with open(config_file, 'r') as ymlfile:
	config = yaml.load(ymlfile)

# Connect to the local storage database
local_db = LocalStorage(config['local_store'])

# Start the display
display_thread = display.DisplayControl(queue_message, shutdown)
display_thread.start()

# Start the thermostat
sensor_delay = NORM_SENSOR_DELAY if args.mode == 'NORMAL' else DEBUG_SENSOR_DELAY
control_interval = NORM_CONTROL_INTERVAL if args.mode == 'NORMAL' else DEBUG_CONTROL_INTERVAL
db_upload_string = NORM_DB_UPLOAD if args.mode == 'NORMAL' else DEBUG_DB_UPLOAD
thermo_thread = thermostat.Thermostat(queue_message, shutdown, sensor_delay, control_interval, db_upload_string, config)
thermo_thread.start()

# Start the LAN network
lan_thread = lan_network.LANNetwork(queue_message, shutdown, config['server_port'], config['db_address'])
lan_thread.start()

# Start the xbee network
xbee_thread = xbee_network.XBeeNetwork(queue_message, shutdown, db_upload_string, config['outdoor_radio'])
xbee_thread.start()

# Check to see if there are any http transmissions that are still stored one the local machine, and send them it so
while True:
	unsent_trans = local_db.pop()
	if unsent_trans is None:
		break  # Get out of this loop as there is nothing to send
	else:  # There is an unsent transmission
		# Try to resend
		queue_message(messaging.LANTxMessage(messaging.DBPacket(unsent_trans[1])))

# Loop to check the status of the queue and dispatch messages
while not shutdown.is_set():
	if not message_list.empty():
		dispatch_message(message_list.get())
	shutdown.wait(MESSAGE_DELAY)

# Wait for threads to finish
lan_thread.join()
xbee_thread.join()
thermo_thread.join()
display_thread.join()

# Display any remaining items
logger.info('Program closed with %i items in the queue', message_list.qsize())
while not message_list.empty():
	cur_message = message_list.get()
	logger.info('  Message unprocessed: %s', cur_message.to_string())
