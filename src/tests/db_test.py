# db_test.py
# This is a simple test of the class used for saving data not sent through the
# LAN to a temporary local database.

# Imports
import sqlite3
from os.path import isfile


# =============================================================================
# DBStorage class
# =============================================================================
# This contains an implementation to connect to a local database and store
# unsend LAN transmissions until a connection is made
#
# Members
#    _db : The connection to the database
#
class DBStorage(object):
	# -------------------------------------------------------------------------
	# Constructor
	# -------------------------------------------------------------------------
	def __init__(self, filename):
		# Check if the database exists
		new_db = not isfile(filename)

		# Connect to the database and get the cursor
		self._db = sqlite3.connect(filename)

		# Create the database table, if it does not exist
		if new_db:
			cursor = self._db.cursor()
			cursor.execute('CREATE TABLE measurements (id INTEGER PRIMARY KEY, measure_time TEXT, temperature REAL)')
			self._db.commit()  # Make sure the table is added

	# -------------------------------------------------------------------------
	# with functionality
	# -------------------------------------------------------------------------
	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		# Close the database
		self._db.close()

	# -------------------------------------------------------------------------
	# push Method
	# -------------------------------------------------------------------------
	def push(self, MeasureData):
		try:
			# Push in a new entry
			cursor = self._db.cursor()
			cursor.execute('INSERT INTO measurements VALUES(NULL,?,?)', MeasureData)
			self._db.commit()  # Ensure its added to db now
		except sqlite3.DatabaseError as db_err:
			print 'Database insertion failed with message: %s' % db_err.message

	# -------------------------------------------------------------------------
	# query Method
	# -------------------------------------------------------------------------
	def query(self, Query):
		results = None
		try:
			# Send the query to the database
			cursor = self._db.cursor()
			cursor.execute(Query)

			# Read results and return
			results = []
			for row in cursor:
				results.append(row)
		except sqlite3.DatabaseError as db_err:
			print 'Database query failed with message: %s' % db_err.message

		return results


# =============================================================================
# Class testing
# =============================================================================
if __name__ == '__main__':
	try:
		# Create the connection to the database
		with DBStorage('test.db') as DBConn:
			kb_cmd = ''
			while kb_cmd != 'exit':
				# Get user input
				kb_cmd = raw_input('> ')
	except sqlite3.Error as db_error:
		print 'Database critical error (%s).  Exiting program' % db_error.message