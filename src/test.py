#!/usr/bin/python

# Imports
import serial
import time
import struct
from xbee import ZigBee

#===============================================================================
# CONSTANTS
#===============================================================================
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

# XBee Command Codes
CMD_THERMO_POWER	=  1
CMD_OVERRIDE		=  2
CMD_RULE_CHANGE		=  3
CMD_SENSOR_DATA		=  4
CMD_TIME_REQUEST	=  5
CMD_STATUS			=  6

# XBee Subcommand Codes
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

#===============================================================================
# FUNCTIONS
#===============================================================================

#-------------------------------------------------------------------------------
# binary_print Function
#-------------------------------------------------------------------------------
def binary_print(bin_data, separator):
	# type: (list, string) -> string
	"""
	This method take a list of bytes and converts to a string with formatted
	output.
	"""
	output = ''	# Empty string
	for byte in bin_data:
		output += '%02x%s' % ( ord(byte), separator )
	
	return output if separator == '' else output[0:-1]
	
#-------------------------------------------------------------------------------
# print_data Function
#-------------------------------------------------------------------------------
# Callback for when the xbee receives data - this runs in its own thread
def print_data(data):
    """
    This method is called whenever data is received from the associated XBee
    device. Its first and only argument is the data contained within the frame.
    """
    print 'Received data packet:'
    for cur_key in data.keys():
    	value = binary_print(data[cur_key], '-')
    	print '    %s = %s' % (cur_key, value)
    print '\n'
    
    if 'id' in data and data['id'] == 'rx':	# Only looking for rx-type transmissions
    	# Create the initial part of the insert query and add the radio
    	insert_query = 'GET /db_test_upload.php?radio_id='
    	radio_id = binary_print(data['source_addr_long'][-4:], '')
    	insert_query += radio_id
    	
    	# Check for funny number of bytes
    	data_length = len(data['rf_data']) - 1
    	
    	# Iterate through all the sensors adding data
    	num_sensors = len(data['rf_data']) / 5	# Data transferred in 5-byte chunks
    	print '\tThe number of sensors is %i' % num_sensors
    	for i in range(num_sensors):
    		# Read the first byte which gives the data type
    		is_pressure = False
    		is_override = False
    		type_byte = ord(data['rf_data'][5*i+1])
    		print '\tThe type byte for data block %i is %i' % ( i, type_byte )
    		if type_byte == TEMPERATURE_CODE:
    			insert_query += '&temperature='
    		elif type_byte == LUMINOSITY_CODE:
    			insert_query += '&luminosity='
    		elif type_byte == PRESSURE_CODE:
    			insert_query += '&pressure='
    			is_pressure = True
    		elif type_byte == HUMIDITY_CODE:
    			insert_query += '&humidity='
    		elif type_byte == POWER_CODE: 
    			insert_query += '&power='
    		elif type_byte == LUX_CODE:
    			insert_query += '&luminosity_lux='
    		elif type_byte == HEATING_CODE:
    			insert_query += '&heating_on='
    		elif type_byte == THERMOSTAT_CODE:
    			insert_query += '&thermo_on='
    		elif type_byte == BATTERY_SOC_CODE:
    			insert_query += '&battery_soc='
    		elif type_byte == OVERRIDE_CODE:
    			insert_query += '&override='
    			is_override = True
    		# Need to add else statement which handles this situation
    		
    		# Convert the binary data to a float and add to string
    		float_value = struct.unpack('f', data['rf_data'][5*i+2:5*i+7])
    		insert_query += '%f' % float_value
    	
    	print '\t%s' % insert_query
    else:
    	print '\tThis is not a data transmission'

#===============================================================================
# MAIN EXECUTION
#===============================================================================
# Create serial port object for xbee and set callback for received messages
serial_port = serial.Serial('/dev/ttyUSB0', 9600)
xbee = ZigBee(serial_port, callback=print_data)

# Wait some time for several messages to make their way through
time.sleep(20*60)

# Close the connection to the xbee
xbee.halt()
serial_port.close()