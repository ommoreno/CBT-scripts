#!/usr/bin/python
#
# Parse CBT output directory and return a summary of test statistics
#
# Orlando Moreno
# 03-13-2017

import os
import pprint
import re
import sys
import math
import argparse
from operator import itemgetter

def parse_args():
	parser = argparse.ArgumentParser(description='Parse CBT output directory.')
	parser.add_argument('-p', '--pctiles', dest='pctiles', action='store', nargs="?", const="50.00,80.00,90.00,95.00,99.00", required=False, help='Print the specified comma-seperated latency percentiles (##.##).')
	parser.add_argument('-s', '--split', dest='split', action='store_true', default=False, required=False, help='Seperate IOPS and latency between reads and writes.')
	parser.add_argument('-c', '--csv', dest='csv', action='store_true', default=False, required=False, help='Print output in CSV format.')
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

def get_percentile(values, p):
	s = sorted(values)
	k = (len(s) - 1) * p
	f = math.floor(k)
	c = math.ceil(k)
	if f == c:
		return s[int(k)]
	return (s[int(f)] * (c - k)) + (s[int(c)] * (k - f))

def display_results(testRuns):
	for testRun in testRuns:
		print "========================================="
		testRun.print_testRun()


class TestRun(object):
	def __init__(self, ctx, dn):
		self.ctx = ctx
		self.tests = []
		self.index = -1
		self.parse_testRun(dn)

	def parse_testRun(self, dn):
		for path, dirs, files in os.walk(dn):
			for file in files:
				if re.match('output\.\d+\.\w+', file):
					if not any(Test.path == path for Test in self.tests):
						self.index += 1
						Iteration = Benchmark = OSD_RA = IOSize = Procs = IODepth = Pattern = Mix = ""
						for subdir in path.split('/'):
							if re.match('\d+', subdir):
								Iteration = subdir
							elif re.match('LibrbdFio', subdir):
								Benchmark = subdir
							elif re.match('osd_ra-\d+', subdir):
								OSD_RA = subdir.split('-')[1]
							elif re.match('op_size-\d+', subdir):
								IOSize = subdir.split('-')[1]
							elif re.match('concurrent_procs-\d+', subdir):
								Procs = subdir.split('-')[1]
							elif re.match('iodepth-\d+', subdir):
								IODepth = subdir.split('-')[1]
							elif re.match('randrw|rw', subdir):
								Pattern = subdir
							elif re.match('readmix-\d+', subdir):
								Mix = subdir.split('-')[1]

						self.add_test(path, Iteration, Benchmark, OSD_RA, IOSize, Procs, IODepth, Pattern, Mix)
						#parse and add output
						self.tests[self.index].add_output(os.path.join(path, file))
					else:
						#parse and add output
						self.tests[self.index].add_output(os.path.join(path, file))

	def add_test(self, path, iteration, benchmark, osd_ra, iosize, procs, iodepth, pattern, mix):
		test = Test(self.ctx, path, iteration, benchmark, osd_ra, iosize, procs, iodepth, pattern, mix)
		self.tests.append(test)

	def print_testRun(self):

		#self.tests = sorted(self.tests, key=itemgetter('Benchmark', 'Iteration', 'Procs', 'IOSize', 'Mix', 'IODepth'))
		self.tests.sort(key=lambda x: (x.benchmark, x.iteration, x.procs, x.iosize, x.mix, x.iodepth))

		if self.ctx.csv:
			if self.ctx.pctiles:
				sys.stdout.write("Benchmark,Iteration,Procs,IOSize,Pattern,Mix,IODepth,Bandwidth(KB/s),IOPS,AvgLat(ms),MinLat(ms),%s" % (self.ctx.pctiles))
				print ",MaxLat(ms)"
			else:
				print "Benchmark,Iteration,Procs,IOSize,Pattern,Mix,IODepth,Bandwidth(KB/s),IOPS,AvgLat(ms),MinLat(ms),MaxLat(ms)"
		else:
			if self.ctx.pctiles:
				sys.stdout.write("Benchmark | Iteration | Procs | IOSize   | Pattern | Mix | IODepth | Bandwidth(KB/s) | IOPS | AvgLat(ms) | MinLat(ms) ")
				for bucket in self.ctx.pctiles.split(','):
					sys.stdout.write("| %s " % (bucket))
				print "| MaxLat(ms)"
				sys.stdout.write("----------+-----------+-------+----------+---------+-----+---------+-----------------+------+------------+------------")
				for bucket in self.ctx.pctiles.split(','):
					sys.stdout.write("+-------")
				print "+-----------"
			else:
				print "Benchmark | Iteration | Procs | IOSize   | Pattern | Mix | IODepth | Bandwidth(KB/s) | IOPS | AvgLat(ms) | MinLat(ms) | MaxLat(ms)"
				print "----------+-----------+-------+----------+---------+-----+---------+-----------------+------+------------+------------+-----------"

		for test in self.tests:
			test.print_test()


class Test(object):
	def __init__(self, ctx, path, iteration, benchmark, osd_ra, iosize, procs, iodepth, pattern, mix):
		self.ctx = ctx
		self.path = path
		self.iteration = iteration
		self.benchmark = benchmark
		self.osd_ra = osd_ra
		self.iosize = iosize
		self.procs = procs
		self.iodepth = iodepth
		self.pattern = pattern
		self.mix = mix
		self.iops = 0
		self.bw = 0
		self.avglat = 0
		self.minlat = 0
		self.maxlat = 0
		self.pctiles = {}
		self.outputs = []

	def add_output(self, fn):
		output = Output(self.ctx, fn)
		self.outputs.append(output)

	def calculate_results(self):
		for output in self.outputs:
			self.iops += output.iops
			self.avglat += output.iops * output.avglat
			self.bw += output.bw
		if self.iops > 0:
			self.avglat /= self.iops
		#self.minlat = min([item.minlat for item in self.outputs] or ['empty list'])
		self.minlat = min([item.minlat for item in self.outputs])
		if self.minlat == 'empty list':
			self.minlat = 0
		self.maxlat = min([item.maxlat for item in self.outputs])
		if self.maxlat == 'empty list':
			self.maxlat = 0
		if self.ctx.pctiles:
			for bucket in self.ctx.pctiles.split(','):
				self.pctiles[bucket] = get_percentile([item.pctiles[bucket] for item in self.outputs], float(bucket)/100)
	
	def print_test(self):
		self.calculate_results()
		if self.ctx.csv:
			if self.ctx.pctiles:
				sys.stdout.write("%s,%s,%s,%s,%s,%s,%s,%.2f,%d,%.2f,%.2f" % (self.benchmark, self.iteration, self.procs, self.iosize, self.pattern, self.mix, self.iodepth, self.bw, self.iops, self.avglat, self.minlat))
				for bucket in self.pctiles.keys():
					sys.stdout.write(",%.2f" % self.pctiles[bucket])
				print ",%.2f" % (self.maxlat)
			else:
				# print test results in csv format
				print "%s,%s,%s,%s,%s,%s,%s,%.2f,%d,%.2f,%.2f,%.2f" % (self.benchmark, self.iteration, self.procs, self.iosize, self.pattern, self.mix, self.iodepth, self.bw, self.iops, self.avglat, self.minlat, self.maxlat)
		else:
			if self.ctx.pctiles:
				sys.stdout.write("%s | %9s | %5s | %8s | %-7s | %-3s | %-7s | % 10.0f      | %4d | %7.2f | %7.2f" % (self.benchmark, self.iteration, self.procs, self.iosize, self.pattern, self.mix, self.iodepth, self.bw, self.iops, self.avglat, self.minlat))
				for bucket in self.pctiles.keys():
					sys.stdout.write(" | %.2f" % self.pctiles[bucket])
				print " | %.2f" % (self.maxlat)
			
			else:
				print "%s | %9s | %5s | %8s | %-7s | %-3s | %-7s | % 10.0f      | %4d | %7.2f | %7.2f | %7.2f" % (self.benchmark, self.iteration, self.procs, self.iosize.lstrip("0"), self.pattern, self.mix, self.iodepth, self.bw, self.iops, self.avglat, self.minlat, self.maxlat)
			

class Output(object):
	def __init__(self, ctx, fn):
		self.ctx = ctx
		self.iops = None
		self.bw = None
		self.avglat = None
		self.minlat = 0
		self.maxlat = None
		self.buckets = ['50.00','80.00','90.00','99.00']
		self.pctiles = {}
		if self.ctx.pctiles:
			self.buckets = self.ctx.pctiles.split(',')
		self.parseFIO(fn)

	def parseFIO(self, fn):
		iothreads = []
		curthread = -1
		block = 'read'
		pct_unit = 'msec'

		f = open(fn, 'r')
		for line in f:
			if re.search('pid=\d+', line):
				curthread += 1
				iothread = {}
				iothread['pid'] = re.search('\spid=\d+', line).group(0).split('=')[1]
				iothread.update(dict.fromkeys(['read_iops', 'read_bw', 'read_runt', 'read_avglat', 'read_minlat', 'read_maxlat','read_stdev'], 0))
				iothread['read_pctiles'] = {}
				iothread.update(dict.fromkeys(['write_iops', 'write_bw', 'write_runt', 'write_avglat', 'write_minlat', 'write_maxlat', 'write_stdev'], 0))
				iothread['write_pctiles'] = {}
				iothread['thread_pctiles'] = {}
				iothreads.append(iothread)

			#m = re.match('\s+(?P<block>read|write)\s*: io=(?P<io>\d+)(?P<io_unit>\S+), bw=(?P<bw>\d+[\.\d]*)(?P<bw_unit>\S+), iops=(?P<iops>\d+), runt=(?P<runt>\d+)(?P<runt_unit>\S+)', line)
			m = re.match('\s+(?P<block>read|write)\s*: IOPS=(?P<iops>\d+[\.\d]*k*), BW=(?P<biw>\d+[\.\d]*)(?P<biw_unit>\S+) \((?P<bw>\d+[\.\d]*)(?P<bw_unit>\S+)\)\((?P<io>\d+)(?P<io_unit>\S+)/(?P<runt>\d+)(?P<runt_unit>\S+)\)', line)
			if m:
				block = m.groupdict()['block']
				if "k" in m.groupdict()['iops']:
					iothreads[curthread][block + '_iops'] = float(m.groupdict()['iops'].split('k')[0]) * 1000
				else:
					iothreads[curthread][block + '_iops'] = int(m.groupdict()['iops'])
				iothreads[curthread][block + '_bw'] = float(m.groupdict()['bw']) * convert_unit(m.groupdict()['bw_unit']) / 1000
				iothreads[curthread][block + '_runt'] = float(m.groupdict()['runt']) /  convert_unit(m.groupdict()['runt_unit']) * 1000

			m = re.match('\s+lat \((?P<unit>\S+)\):\s+min=\s*(?P<min>\d+[\.\d]*), max=\s*(?P<max>\d+[\.\d]*k*), avg=\s*(?P<avg>\d+[\.\d]*), stdev=\s*(?P<stdev>\d+[\.\d]*)', line)
			if m:
				mult = convert_unit(m.groupdict()['unit'])
				iothreads[curthread][block + '_minlat'] = float(m.groupdict()['min']) /  mult * 1000
				if "k" in m.groupdict()['max']:
					iothreads[curthread][block + '_maxlat'] = float(m.groupdict()['max'].split('k')[0]) * 1000 / mult * 1000
				else:
					iothreads[curthread][block + '_maxlat'] = float(m.groupdict()['max']) / mult * 1000
				iothreads[curthread][block + '_avglat'] = float(m.groupdict()['avg']) / mult * 1000
				iothreads[curthread][block + '_stdev'] = float(m.groupdict()['stdev']) / mult * 1000
			m = re.match('\s+clat percentiles \((?P<unit>\S+)\):', line)
			if m:
				pct_unit = m.groupdict()['unit']
			m = re.match('\s+\|\s+\d+[\.\d]*th=', line)
			if m:
				for pct in line.split(','):
					pctile = re.match('\s+[\|\s]*(?P<bucket>\d+[\.\d]*)th=\[\s*(?P<value>\d+[\.\d]*)\]', pct)
					if pctile:
						bucket = pctile.groupdict()['bucket']
						value = float(pctile.groupdict()['value']) / convert_unit(pct_unit) * 1000
						iothreads[curthread][block + '_pctiles'][bucket] = value

		totaliops = 0
		avglat = 0
		pctiles = {}

		self.iops = sum(item['read_iops'] for item in iothreads) + sum(item['write_iops'] for item in iothreads)
		self.bw = sum(item['read_bw'] for item in iothreads) + sum(item['write_bw'] for item in iothreads)

		for iothread in iothreads:
			if totaliops == 0:
			# Set minlat to either read or write lat initially
				if iothread['read_minlat'] > 0:
					self.minlat = iothread['read_minlat']
				else:
					self.minlat = iothread['write_minlat']
			thread_iops = iothread['read_iops'] + iothread['write_iops']
			if thread_iops > 0:
				thread_lat = (iothread['read_avglat'] * iothread['read_iops']) / thread_iops
				thread_lat += (iothread['write_avglat'] * iothread['write_iops']) / thread_iops
			totaliops += thread_iops
			if self.iops > 0:
				avglat += (thread_lat * thread_iops) / self.iops

			if self.minlat > iothread['read_minlat'] > 0:
				self.minlat = iothread['read_minlat']
			if self.minlat > iothread['write_minlat'] > 0:
				self.minlat = iothread['write_minlat']

			for bucket in self.buckets:
				threadpcts = []
				if bucket in iothread['read_pctiles'].keys():
					threadpcts.append(iothread['read_pctiles'][bucket])
				if bucket in iothread['write_pctiles'].keys():
					threadpcts.append(iothread['write_pctiles'][bucket])
				if len(threadpcts) > 0:
					iothread['thread_pctiles'][bucket] = get_percentile(threadpcts, float(bucket)/100)

		self.avglat = avglat
		self.maxlat = max([max([item['read_maxlat'] for item in iothreads] or ['empty list']), max([item['write_maxlat'] for item in iothreads] or ['empty list'])] or ['empty list'])

		for bucket in self.buckets:
			threadpcts = []
			for iothread in iothreads:
				if bucket in iothread['thread_pctiles'].keys():
					threadpcts.append(iothread['thread_pctiles'][bucket])
			if len(threadpcts) > 0:
				self.pctiles[bucket] = get_percentile(threadpcts, float(bucket)/100)


if __name__ == '__main__':
	ctx = parse_args()
	testRuns = []
	for dn in ctx.DIR:
		testRuns.append(TestRun(ctx, dn))
	
	display_results(testRuns)

	#if ctx.csv:
	#	print_csv(ctx, testRuns)
	#else:
	#	print_default(ctx, testRuns)



