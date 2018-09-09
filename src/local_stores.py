# local_stores.py
# This is a class that is used to store unsent http messages to the main
# database locally on the Pi.

# Imports
import sqlite3
import logging
import sys
from os.path import isfile


# =============================================================================
# LocalStorage class
# =============================================================================
# This contains an implementation to connect to a local database and store
# unsent LAN transmissions until a connection is made
#
# Members
#    _db : The connection to the database
#
class LocalStorage(object):
	# -------------------------------------------------------------------------
	# Constructor
	# -------------------------------------------------------------------------
	def __init__(self, filename):
		# Check if the database exists
		new_db = not isfile(filename)

		# Initialize logger
		self._logger = logging.getLogger('MAIN.STORE')

		# Connect to the database and get the cursor
		self._db = sqlite3.connect(filename)

		# Create the database table, if it does not exist
		if new_db:
			cursor = self._db.cursor()
			cursor.execute('CREATE TABLE transmissions (id INTEGER PRIMARY KEY, message TEXT)')
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
	def push(self, Requests):
		try:
			# Push in a new entry
			cursor = self._db.cursor()
			cursor.execute('INSERT INTO transmissions VALUES(NULL,?)', (Requests,))
			self._db.commit()  # Ensure its added to db now
		except sqlite3.DatabaseError as db_err:
			self._logger.error('Local database insertion failed with message: %s', db_err.message)

	# -------------------------------------------------------------------------
	# pop Method
	# -------------------------------------------------------------------------
	def pop(self):
		pop_item = None  # initialize the return object as None, indicating nothing happened
		try:
			# Get the first item in the database
			cursor = self._db.cursor()
			cursor.execute('SELECT * FROM transmissions ORDER BY id LIMIT 1')
			pop_item = cursor.fetchone()  # Get the first item in the local storage (or None if nothing)

			# Delete the item, if it exists
			if pop_item:
				try:
					qry = 'DELETE FROM transmissions WHERE id=%i' % pop_item[0]
					cursor.execute(qry)
					self._db.commit()
				except sqlite3.DatabaseError as del_error:
					self._logger.error('Local database error when trying to delete found pop item from local storage.  Error: %s', del_error.message)
					pop_item = None  # This indicates an error even though an item was found
		except sqlite3.DatabaseError as db_err:
			self._logger.error('Local database error when trying to find pop item from local storage.  Error: %s', db_err.message)

		return pop_item

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
			self._logger.error('Local database query failed with message: %s', db_err.message)

		return results


# =============================================================================
# UNIT TESTING
# =============================================================================
if __name__ == '__main__':
	try:
		# Create a test database
		print 'Creating database'
		test_db = LocalStorage('unit_test.db')

		# Test to make sure we get a null response with nothing in the database
		sys.stdout.write('Testing response when no entries in the database: ')
		response = test_db.pop()
		if response is None:
			print 'PASSED'
		else:
			print 'FAILED'

		# Testing the addition of values to the database
		sys.stdout.write('Testing the addition of multiple items into the database: ')
		n = 3
		for i in range(n):
			test_db.push('%i' % i)
		num_results = test_db.query('SELECT * FROM transmissions')
		if len(num_results) == n:
			print 'PASSED'
		else:
			print 'FAILED'

		# Testing that the popping of the items works correctly
		sys.stdout.write('Testing the popping of items works correctly: ')
		for i in range(n):
			result = test_db.pop()
			if i != int(result[1]):
				print 'FAILED'
				break
		else:
			print 'PASSED'

		# Testing that the db is empty
		sys.stdout.write('Testing that the database is empty: ')
		result = test_db.pop()
		if result is None:
			print 'PASSED'
		else:
			print 'FAILED'

	except:
		print 'Something unexpected happened!'
