# config.py
# This file includes all configurable items within the thermostat controller code
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

# Imports
from simple_types import RULE_DAYS

# The address of the radio attached to the thermostat
THERMO_RADIO = '40ab9778'

# The address of the outdoor radio to be used for outdoor temperatures
outdoor_radio  = '40aeb97f'

# The default rules for the thermostat
programming_rules = [
	{'day': RULE_DAYS['Weekdays'], 'time': 23.5, 'temperature': 19.0},
	{'day': RULE_DAYS['Weekdays'], 'time': 16.5, 'temperature': 22.0},
	{'day': RULE_DAYS['Weekdays'], 'time': 8.0, 'temperature': 18.0},
	{'day': RULE_DAYS['Weekdays'], 'time': 6.5, 'temperature': 22.0},
	{'day': RULE_DAYS['Weekends'], 'time': 23.5, 'temperature': 19.0},
	{'day': RULE_DAYS['Weekends'], 'time': 7.5, 'temperature': 22.0}]

# The IP address on the LAN where the database resides
DB_ADDRESS = '192.168.2.53'

# The port that the thermostat controller will listen on
SERVER_PORT = 5267
