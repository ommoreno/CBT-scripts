#!/usr/bin/python
#
# Parse CBT output directory and return a summary of test statistics
#
# Orlando Moreno
# 06-20-2019

import os
import pprint
import re
import sys
import math
import argparse
from operator import itemgetter

import yaml
import json
import numpy as np
from collections import defaultdict

import sqlite3

def parse_args():
	parser = argparse.ArgumentParser(description='Parse CBT output directory.')
	parser.add_argument('-p', '--pctiles', dest='pctiles', action='store', nargs="?", const="50.00,80.00,90.00,95.00,99.00", required=False, help='Print the specified comma-seperated latency percentiles (##.##).')
	parser.add_argument('-s', '--split', dest='split', action='store_true', default=False, required=False, help='Seperate IOPS and latency between reads and writes.')
	parser.add_argument('-c', '--csv', dest='csv', action='store_true', default=True, required=False, help='Print output in CSV format.')
	parser.add_argument("DIR", help="CBT output directory(s) to parse", nargs="+")
	args = parser.parse_args()
	return args

def convert_unit(unit):
	if(unit == 'B/s' or unit == 'sec'):
		return 1
	elif(unit == 'KB/s' or unit == 'kB/s' or unit == 'msec'):
		return 1000
	elif(unit == 'MB/s' or unit == 'usec'):
		return 1000000
	elif(unit == 'GB/s' or unit == 'nsec'):
		return 1000000000
	else:
		return 0;

def printHeader(ctx):
	if ctx.pctiles:
		if ctx.split:
			sys.stdout.write("Benchmark, Iteration, Procs, IOSize, Pattern, Mix, IODepth, Bandwidth(KB/s), readIOPS, writeIOPS, readAvgLat(ms), writeAvgLat(ms), readMinLat(ms), writeMinLat(ms)")
			for bucket in ctx.pctiles.split(','):
				sys.stdout.write(", read%spctLat(ms), write%spctLat(ms)" % (bucket, bucket))
			print ", readMaxLat(ms), writeMaxLat(ms)"
		else:
			sys.stdout.write("Benchmark, Iteration, Procs, IOSize, Pattern, Mix, IODepth, Bandwidth(KB/s), IOPS, avgLat(ms), minLat(ms)")
			for bucket in ctx.pctiles.split(','):
				sys.stdout.write(", %spctLat(ms)" % bucket)
			print ", maxLat(ms)"
	else:
		if ctx.split:
			sys.stdout.write("Benchmark, Iteration, Procs, IOSize, Pattern, Mix, IODepth, Bandwidth(KB/s), readIOPS, writeIOPS, readAvgLat(ms), writeAvgLat(ms), readMinLat(ms), writeMinLat(ms)")
			print ", readMaxLat(ms), writeMaxLat(ms)"
		else:
			sys.stdout.write("Benchmark, Iteration, Procs, IOSize, Pattern, Mix, IODepth, Bandwidth(KB/s), IOPS, avgLat(ms), minLat(ms)")
			print ", maxLat(ms)"

class Test(object):
	def __init__(self, ctx, metadata, hashid):
		self.ctx = ctx
		self.metadata = metadata
		self.hashid = hashid
		self.iops = 0
		self.readiops = 0
		self.writeiops = 0
	        self.bw = 0
        	self.readLat = {'avg': 0, 'min': 0, 'max': 0, 'pctiles': {}}
		self.writeLat = {'avg': 0, 'min': 0, 'max': 0, 'pctiles': {}}
		self.lat = {'avg': 0, 'min': 0, 'max': 0, 'pctiles': {}}
	        self.outputs = []
	        self.clients = 0

	def calculate_results(self):

		totReadIOPS = []
		totWriteIOPS = []
		totReadLat = defaultdict(list)
		totWriteLat = defaultdict(list)
		totReadPctLat = defaultdict(list)
		totWritePctLat = defaultdict(list)
		self.clients = len(self.outputs)

		lat_key = "lat_ns"
		clat_key = "clat_ns"

		for output in self.outputs:
			readIOPS = []
			writeIOPS = []
			readLat = defaultdict(list)
			writeLat = defaultdict(list)
			readPctLat = defaultdict(list)
			writePctLat = defaultdict(list)

			json_data = json.load(open(output))

			if "fio-2." in json_data['fio version']:
				lat_key = "lat"
				clat_key = "clat"

			for job in json_data['jobs']:
				readIOPS.append(int(job["read"]["iops"]))
				writeIOPS.append(int(job["write"]["iops"]))

				self.bw += job['read']['bw'] + job['write']['bw']

				readLat['avg'].append(job["read"][lat_key]["mean"])
				readLat['min'].append(job["read"][lat_key]["min"])
				readLat['max'].append(job["read"][lat_key]["max"])

				writeLat['avg'].append(job["write"][lat_key]["mean"])
				writeLat['min'].append(job["write"][lat_key]["min"])
				writeLat['max'].append(job["write"][lat_key]["max"])

				for pct in job["read"][clat_key]["percentile"].keys():
					readPctLat[round(float(pct),2)].append(job["read"][clat_key]["percentile"][pct])
				for pct in job["write"][clat_key]["percentile"].keys():
					writePctLat[round(float(pct),2)].append(job["write"][clat_key]["percentile"][pct])

			totReadIOPS.append(sum(readIOPS))
			totWriteIOPS.append(sum(writeIOPS))
			
			if not sum(readIOPS)==0:
				totReadLat['avg'].append(np.ma.average(readLat['avg'], weights=readIOPS))
				totReadLat['min'].append(np.ma.average(readLat['min'], weights=readIOPS))
				totReadLat['max'].append(np.ma.average(readLat['max'], weights=readIOPS))
				for pct in readPctLat.keys():
					totReadPctLat[pct].append(np.ma.average(readPctLat[pct], weights=readIOPS))
			if not sum(writeIOPS)==0:
				totWriteLat['avg'].append(np.ma.average(writeLat['avg'], weights=writeIOPS))
				totWriteLat['min'].append(np.ma.average(writeLat['min'], weights=writeIOPS))
				totWriteLat['max'].append(np.ma.average(writeLat['max'], weights=writeIOPS))
				for pct in writePctLat.keys():
					totWritePctLat[pct].append(np.ma.average(writePctLat[pct], weights=writeIOPS))

		self.iops = sum(totReadIOPS) + sum(totWriteIOPS)
		self.readiops = sum(totReadIOPS)
		self.writeiops = sum(totWriteIOPS)
		
		# Avoid division by 0, if no read IOPS to weigh against
		if not sum(totReadIOPS)==0:
			self.readLat['avg'] = np.ma.average(totReadLat['avg'], weights=totReadIOPS)
			self.readLat['min'] = np.ma.average(totReadLat['min'], weights=totReadIOPS)
			self.readLat['max'] = np.ma.average(totReadLat['max'], weights=totReadIOPS)
			for pct in totReadPctLat.keys():
				self.readLat['pctiles'][pct] = np.ma.average(totReadPctLat[pct], weights=totReadIOPS)
		# Same with writes
		if not sum(totWriteIOPS)==0:
			self.writeLat['avg'] = np.ma.average(totWriteLat['avg'], weights=totWriteIOPS)
			self.writeLat['min'] = np.ma.average(totWriteLat['min'], weights=totWriteIOPS)
			self.writeLat['max'] = np.ma.average(totWriteLat['max'], weights=totWriteIOPS)
			for pct in totWritePctLat.keys():
				self.writeLat['pctiles'][pct] = np.ma.average(totWritePctLat[pct], weights=totWriteIOPS)
		# Same with total latency
		if sum(totReadIOPS)==0:
			self.lat['avg'] = self.writeLat['avg']
			self.lat['min'] = self.writeLat['max']
			self.lat['max'] = self.writeLat['max']
			self.lat['pctiles'] = self.writeLat['pctiles']
		elif sum(totWriteIOPS)==0:
			self.lat['avg'] = self.readLat['avg']
			self.lat['min'] = self.readLat['min']
			self.lat['max'] = self.readLat['max']
			self.lat['pctiles'] = self.readLat['pctiles']
		else:
			self.lat['avg'] = np.ma.average([self.readLat['avg'],self.writeLat['avg']], weights=[sum(totReadIOPS), sum(totWriteIOPS)])
			self.lat['min'] = np.ma.average([self.readLat['min'],self.writeLat['min']], weights=[sum(totReadIOPS), sum(totWriteIOPS)])
			self.lat['max'] = np.ma.average([self.readLat['max'],self.writeLat['max']], weights=[sum(totReadIOPS), sum(totWriteIOPS)])
			for pct in self.readLat['pctiles'].keys():
				self.lat['pctiles'][pct] = np.ma.average([self.readLat['pctiles'][pct],self.writeLat['pctiles'][pct]], weights=[sum(totReadIOPS),sum(totWriteIOPS)])

	def printTest(self):
		if self.ctx.pctiles:
			if self.ctx.split:
				sys.stdout.write("%s, %s, %s, %s, %s, %s, %s, %d, %d, %d, %.2f, %.2f, %.2f, %.2f" % (self.metadata['benchmark'], self.metadata['iteration'], self.clients, \
																			  self.metadata['op_size'], self.metadata['mode'], self.metadata['rwmixread'], \
																			  self.metadata['iodepth'], self.bw, self.readiops, self.writeiops, self.readlat['avg'], self.writelat['avg'], \
																			  self.readlat['min'], self.writelat['min']))
				for bucket in self.ctx.pctiles.split(','):
					sys.stdout.write(", %.2f, %.2f" % (self.readlat['pctiles'][float(bucket)], self.writelat['pctiles'][float(bucket)]))
				print ", %.2f, %.2f" % (self.readlat['max'], self.writelat['max'])
			else:
				sys.stdout.write("%s, %s, %s, %s, %s, %s, %s, %d, %d, %.2f, %.2f" % (self.metadata['benchmark'], self.metadata['iteration'], self.clients, \
																			  self.metadata['op_size'], self.metadata['mode'], self.metadata['rwmixread'], \
																			  self.metadata['iodepth'], self.bw, self.iops, self.lat['avg'], self.lat['min']))
                                for bucket in self.ctx.pctiles.split(','):
					sys.stdout.write(", %.2f" % self.lat['pctiles'][float(bucket)])
				print ", %.2f" % self.lat['max']
		else:
			if self.ctx.split:
				sys.stdout.write("%s, %s, %s, %s, %s, %s, %s, %d, %d, %d, %.2f, %.2f, %.2f, %.2f" % (self.metadata['benchmark'], self.metadata['iteration'], self.clients, \
																			  self.metadata['op_size'], self.metadata['mode'], self.metadata['rwmixread'], \
																			  self.metadata['iodepth'], self.bw, self.readiops, self.writeiops, self.readlat['avg'], self.writelat['avg'], \
																			  self.readlat['min'], self.writelat['min']))
				print ", %.2f, %.2f" % (self.readlat['max'], self.writelat['max'])
			else:
				sys.stdout.write("%s, %s, %s, %s, %s, %s, %s, %d, %d, %.2f, %.2f" % (self.metadata['benchmark'], self.metadata['iteration'], self.clients, \
																			  self.metadata['op_size'], self.metadata['mode'], self.metadata['rwmixread'], \
																			  self.metadata['iodepth'], self.bw, self.iops, self.lat['avg'], self.lat['min']))
				print ", %.2f" % self.lat['max']


if __name__ == '__main__':
	ctx = parse_args()

	cbtConfig = {}
	testIndex = -1

	sqlite_file = "/tmp/db.sqlite"
	conn = sqlite3.connect(sqlite_file)
	c = conn.cursor()
	q = 'CREATE TABLE if not exists results ('
	values = []
	FORMAT = ['hash', 'testname', 'benchmark', 'iteration', 'procs', 'iosize', 'pattern', 'mix', 'iodepth', 'bandwidth', 'iops', 'avglat']
	TYPES = {'hash': 'text', 'testname': 'text', 'benchmark': 'text', 'iteration': 'integer', 'procs': 'integer', 
		 'iosize': 'integer', 'pattern': 'text', 'mix': 'integer', 'iodepth': 'integer', 'bandwidth': 'integer', 'iops': 'real', 'avglat': 'real'}
	for key in FORMAT:
		values.append("%s %s" % (key,TYPES[key]))
	q += ', '.join(values)+', PRIMARY KEY (hash, testname))'
	c.execute(q)
	conn.commit()

	for dn in ctx.DIR:
		# List of test objects in CBT archive folder
		tests = []

		# Walk through given directory
		for path, dirs, files in os.walk(dn):
			for filename in files:
				fname = os.path.join(path,filename)
				# If we see a CBT config, we're in the CBT archive folder
				if 'cbt_config.yaml' in fname:
					with open(fname, 'r') as stream:
						cbtConfig = yaml.load(stream)
					#Save config
					#print cbtConfig['benchmarks']

				# If we see a benchmark config, we're in a test output dir
				if 'benchmark_config.yaml' in fname:
					with open(fname, 'r') as stream:
						benchConfig = yaml.load(stream)
						# Create new Test object with current benchmark metadata
						for subdir in path.split('/'):
							if re.match('id', subdir):
								hashid = subdir
						tests.append(Test(ctx, benchConfig['cluster'], hashid))
						testIndex+=1

					#Gather all output files in this test directory
					outputs = sorted((os.path.join(path, f) for f in os.listdir(path)), key=os.path.getctime)
					for json_file in outputs:
						# Only add/parse from json fio files
						if "json_" in json_file:
							# Check if file contains any data
							if os.path.getsize(json_file) > 0:
								# Add json data to test outputs
								tests[testIndex].outputs.append(json_file)
							else:
								#Found corrupted/empty JSON file
								print "%s is empty" % json_file
					# Calculate test statistics from outputs
					tests[testIndex].calculate_results();

				tests.sort(key=lambda x: (x.metadata['benchmark'], x.metadata['rwmixread'], x.clients, x.metadata['op_size'], x.metadata['iteration'], x.metadata['iodepth']))

		printHeader(ctx)

		for test in tests:
			test.printTest()

			values = (test.hashid, dn, test.metadata['benchmark'], int(test.metadata['iteration']), test.clients, int(test.metadata['op_size']), test.metadata['mode'],
				  int(test.metadata['rwmixread']), int(test.metadata['iodepth']), test.bw, test.iops, test.lat['avg'])
			c = conn.cursor()
			c.execute('INSERT OR IGNORE INTO results VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', values)
			conn.commit()
		conn.close()


