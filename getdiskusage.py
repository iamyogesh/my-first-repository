"""Example Google style docstrings.
Example:
	$ python getdiskusage_v1.py /tmp
Attributes:
    file path
"""
import os
import json
import subprocess
import sys

def get_disk_usage():
	"""
	Return list of follder and there disk usage.
	"""
	if len(sys.argv) != 2:
	    print "Usage: python getdiskusage.py <path>"
	    sys.exit(1)
	all_files = {}
	files_size = []
	for root, dirs, files in os.walk(sys.argv[1]):
	    size = subprocess.check_output(['du', '-b', root]).split()[0]
	    files_size.append(dict({root:size}))
	all_files['files'] = files_size
 	return json.dumps(all_files)

print get_disk_usage()
