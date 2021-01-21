#!/usr/bin/python
#
# Parse CBT output directory and return a summary of test statistics
#
# Orlando Moreno
# 07-30-2020

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
    parser.add_argument('-p', '--pctiles', dest='pctiles', action='store', nargs='?', const='50.00,80.00,90.00,95.00,99.00', required=False, help='Print the specified comma-seperated latency percentiles (##.##).')
    parser.add_argument('-s', '--split', dest='split', action='store_true', default=False, required=False, help='Seperate IOPS and latency between reads and writes.')
    parser.add_argument('-c', '--csv', dest='csv', action='store_true', default=True, required=False, help='Print output in CSV format.')
    parser.add_argument('DIR', help='CBT output directory(s) to parse', nargs='+')
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

def print_header(ctx):
    if ctx.pctiles:
        if ctx.split:
            sys.stdout.write('Benchmark, Iteration, Procs, IOSize, Pattern, Mix, IODepth, Bandwidth(KB/s), readIOPS, writeIOPS, readAvgLat(ms), writeAvgLat(ms), readMinLat(ms), writeMinLat(ms)')
            for bucket in ctx.pctiles.split(','):
                sys.stdout.write(', read%spctLat(ms), write%spctLat(ms)' % (bucket, bucket))
            print(', readMaxLat(ms), writeMaxLat(ms)')
        else:
            sys.stdout.write('Benchmark, Iteration, Procs, IOSize, Pattern, Mix, IODepth, Bandwidth(KB/s), IOPS, avgLat(ms), minLat(ms)')
            for bucket in ctx.pctiles.split(','):
                sys.stdout.write(', %spctLat(ms)' % bucket)
            print(', maxLat(ms)')
    else:
        if ctx.split:
            sys.stdout.write('Benchmark, Iteration, Procs, IOSize, Pattern, Mix, IODepth, Bandwidth(KB/s), readIOPS, writeIOPS, readAvgLat(ms), writeAvgLat(ms), readMinLat(ms), writeMinLat(ms)')
            print(', readMaxLat(ms), writeMaxLat(ms)')
        else:
            sys.stdout.write('Benchmark, Iteration, Procs, IOSize, Pattern, Mix, IODepth, Bandwidth(KB/s), IOPS, avgLat(ms), minLat(ms)')
            print(', maxLat(ms)')

# Test class contains the list of output objects (FIO or RadosBench) and the summarized results of those outputs
class Test(object):
    def __init__(self, ctx, metadata, hashid):
        self.ctx = ctx
        self.metadata = metadata
        self.hashid = hashid
        self.outputs = []
        self.clients = 0
        self.iops = 0
        self.bw = 0
        self.lat = {'avg': 0, 'min': 0, 'max': 0}
        if self.metadata['benchmark'] == 'fio' or self.metadata['benchmark'] == 'librbdfio':
            self.read_lat = {'avg': 0, 'min': 0, 'max': 0}
            self.write_lat = {'avg': 0, 'min': 0, 'max': 0}
            self.read_iops = 0
            self.write_iops = 0
            self.read_bw = 0
            self.write_bw = 0

    def add_output(self, fn):
        output = Output(self.metadata['benchmark'], fn)
        self.outputs.append(output)

    def calculate_results(self):
        self.clients = len(self.outputs)
        self.iops = sum([item.iops for item in self.outputs])
        self.bw = sum([item.bw for item in self.outputs])
        if self.metadata['benchmark'] == 'fio' or self.metadata['benchmark'] == 'librbdfio':
            self.read_iops = sum([item.read_iops for item in self.outputs])
            self.write_iops = sum([item.write_iops for item in self.outputs])
            self.read_bw = sum([item.read_bw for item in self.outputs])
            self.write_bw = sum([item.write_bw for item in self.outputs])

            if not self.read_iops == 0:
                for key in self.outputs[0].read_lat.keys():
                    try:
                        self.read_lat[key] = np.ma.average([item.read_lat[key] for item in self.outputs], weights=[item.read_iops for item in self.outputs])
                        self.read_lat[key] /= 1000000
                    except KeyError:
                        continue
            else:
                for key in self.outputs[0].write_lat.keys():
                    try:
                        self.lat[key] = np.ma.average([item.write_lat[key] for item in self.outputs], weights=[item.write_iops for item in self.outputs])
                        self.read_lat[key] = 0
                        self.lat[key] /= 1000000
                    except KeyError:
                        continue

            if not self.write_iops == 0:
                for key in self.outputs[0].write_lat.keys():
                    try:
                        self.write_lat[key] = np.ma.average([item.write_lat[key] for item in self.outputs], weights=[item.write_iops for item in self.outputs])
                        self.write_lat[key] /= 1000000
                    except KeyError:
                        continue
            else:
                for key in self.outputs[0].read_lat.keys():
                    try:
                        self.lat[key] = np.ma.average([item.read_lat[key] for item in self.outputs], weights=[item.read_iops for item in self.outputs])
                        self.write_lat[key] = 0
                        self.lat[key] /= 1000000
                    except KeyError:
                        continue

            if not self.read_iops == 0 and not self.write_iops == 0:
                for key in self.outputs[0].read_lat.keys():
                    try:
                        self.lat[key] = np.ma.average([self.read_lat[key], self.write_lat[key]], weights=[self.read_iops, self.write_iops])
                    except KeyError:
                        continue

        elif self.metadata['benchmark'] == 'Radosbench':
            if not self.iops == 0:
                for key in self.outputs[0].lat.keys():
                    try:
                        self.lat[key] = np.ma.average([item.lat[key] for item in self.outputs], weights=[item.iops for item in self.outputs])
                        self.lat[key] /= 1000000
                    except KeyError:
                        continue
        else:
            print('Unknown benchmark!')

    def printTest(self):
        if self.ctx.pctiles:
            if self.ctx.split:
                sys.stdout.write('%s, %s, %s, %s, %s, %s, %s, %d, %d, %d, %.2f, %.2f, %.2f, %.2f' % (self.metadata['benchmark'], self.metadata['iteration'], self.clients,
                    self.metadata['op_size'], self.metadata['mode'], self.metadata['rwmixread'],
                    self.metadata['iodepth'], self.bw, self.read_iops, self.write_iops, self.read_lat['avg'], self.write_lat['avg'],
                    self.read_lat['min'], self.write_lat['min']))
                for bucket in self.ctx.pctiles.split(','):
                    sys.stdout.write(', %.2f, %.2f' % (self.read_lat[float(bucket)], self.write_lat[float(bucket)]))
                print(', %.2f, %.2f' % (self.read_lat['max'], self.write_lat['max']))
            else:
                sys.stdout.write('%s, %s, %s, %s, %s, %s, %s, %d, %d, %.2f, %.2f' % (self.metadata['benchmark'], self.metadata['iteration'], self.clients,
            self.metadata['op_size'], self.metadata['mode'], self.metadata['rwmixread'], 
            self.metadata['iodepth'], self.bw, self.iops, self.lat['avg'], self.lat['min']))
                for bucket in self.ctx.pctiles.split(','):
                    sys.stdout.write(', %.2f' % self.lat[float(bucket)])
                print(', %.2f' % self.lat['max'])
        else:
            if self.ctx.split:
                sys.stdout.write('%s, %s, %s, %s, %s, %s, %s, %d, %d, %d, %.2f, %.2f, %.2f, %.2f' % (self.metadata['benchmark'], self.metadata['iteration'], self.clients,
                self.metadata['op_size'], self.metadata['mode'], self.metadata['rwmixread'],
                self.metadata['iodepth'], self.bw, self.read_iops, self.write_iops, self.read_lat['avg'], self.write_lat['avg'],
                self.read_lat['min'], self.write_lat['min']))
                print(', %.2f, %.2f' % (self.read_lat['max'], self.write_lat['max']))
            else:
                sys.stdout.write('%s, %s, %s, %s, %s, %s, %s, %d, %d, %.2f, %.2f' % (self.metadata['benchmark'], self.metadata['iteration'], self.clients,
            self.metadata['op_size'], self.metadata['mode'], self.metadata['rwmixread'],
            self.metadata['iodepth'], self.bw, self.iops, self.lat['avg'], self.lat['min']))
                print(', %.2f' % self.lat['max'])
                
class Output(object):
    def __init__(self, benchmark, fn):
        self.benchmark = benchmark
        self.iops = 0
        self.bw = 0
        self.lat = {'avg': 0, 'min': 0, 'max': 0}
        if self.benchmark == 'fio' or self.benchmark == 'librbdfio':
            self.read_lat = {'avg': 0, 'min': 0, 'max': 0}
            self.write_lat = {'avg': 0, 'min': 0, 'max': 0}
            self.read_iops = 0
            self.write_iops = 0
            self.read_bw = 0
            self.write_bw = 0
            self.parse_fio(fn)
        elif self.benchmark == 'Radosbench':
            self.parse_rados_bench(fn)
        else:
            print('Unknown benchmark!')

    def parse_rados_bench(self, fn):
        json_data = json.load(open(fn))
        self.iops = json_data['Average IOPS']
        self.bw = json_data['Bandwidth (MB/sec)']
        self.lat['avg'] = json_data['Average Latency(s)']
        self.lat['min'] = json_data['Min latency(s)']
        self.lat['max'] = json_data['Max latency(s)']

    def parse_fio(self, fn):
        read_job_iops = []
        write_job_iops = []
        read_job_bw = []
        write_job_bw = []
        read_job_lat = defaultdict(list)
        write_job_lat = defaultdict(list)
        lat_key = 'lat_ns'
        clat_key = 'clat_ns'

        json_data = json.load(open(fn))
        for job in json_data['jobs']:
            read_job_iops.append(int(job['read']['iops']))
            write_job_iops.append(int(job['write']['iops']))
            read_job_bw.append(job['read']['bw'])
            write_job_bw.append(job['write']['bw'])
            read_job_lat['avg'].append(job['read'][lat_key]['mean'])
            read_job_lat['min'].append(job['read'][lat_key]['min'])
            read_job_lat['max'].append(job['read'][lat_key]['max'])
            write_job_lat['avg'].append(job['write'][lat_key]['mean'])
            write_job_lat['min'].append(job['write'][lat_key]['min'])
            write_job_lat['max'].append(job['write'][lat_key]['max'])
            if 'percentile' in job['read'][clat_key]:
                for pct in job['read'][clat_key]['percentile'].keys():
                    read_job_lat[round(float(pct), 2)].append(job['read'][clat_key]['percentile'][pct])
            if 'percentile' in job['write'][clat_key]:           
                for pct in job['write'][clat_key]['percentile'].keys():
                    write_job_lat[round(float(pct), 2)].append(job['write'][clat_key]['percentile'][pct])

        self.read_iops = sum(read_job_iops)
        self.write_iops = sum(write_job_iops)
        self.iops = self.read_iops + self.write_iops
        self.read_bw = sum(read_job_bw)
        self.write_bw = sum(write_job_bw)
        self.bw = self.read_bw + self.write_bw

        if not self.read_iops == 0:
            for key in read_job_lat.keys():
                self.read_lat[key] = np.ma.average(read_job_lat[key], weights=read_job_iops)
        else:
            for key in write_job_lat.keys():
                self.lat[key] = np.ma.average(write_job_lat[key], weights=write_job_iops)
        if not self.write_iops == 0:
            for key in write_job_lat.keys():
                self.write_lat[key] = np.ma.average(write_job_lat[key], weights=write_job_iops)
        else:
            for key in read_job_lat.keys():
                self.lat[key] = np.ma.average(read_job_lat[key], weights=read_job_iops)
        if not self.read_iops == 0 and not self.write_iops == 0:
            for key in read_job_lat.keys():
                self.lat[key] = np.ma.average([self.read_lat[key], self.write_lat[key]], weights=[self.read_iops, self.write_iops])


if __name__ == '__main__':
    ctx = parse_args()

    cbtConfig = {}
    testIndex = -1

    sqlite_file = '/tmp/db.sqlite'
    conn = sqlite3.connect(sqlite_file)
    c = conn.cursor()
    q = 'CREATE TABLE if not exists results ('
    values = []
    FORMAT = ['hash', 'testname', 'benchmark', 'iteration', 'procs', 'iosize', 'pattern', 'mix', 'iodepth', 'bandwidth', 'iops', 'avglat']
    TYPES = {'hash': 'text', 'testname': 'text', 'benchmark': 'text', 'iteration': 'integer', 'procs': 'integer', 
         'iosize': 'integer', 'pattern': 'text', 'mix': 'integer', 'iodepth': 'integer', 'bandwidth': 'integer', 'iops': 'real', 'avglat': 'real'}
    for key in FORMAT:
        values.append('%s %s' % (key,TYPES[key]))
    q += ', '.join(values)+', PRIMARY KEY (hash, testname))'
    c.execute(q)
    conn.commit()

    # Iterate through each given archive directory
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
                        if 'json_output' in json_file:
                            # Check if file contains any data
                            if os.path.getsize(json_file) > 0:
                                # Add json data to test outputs
                                tests[testIndex].add_output(json_file)
                            else:
                                #Found corrupted/empty JSON file
                                print('%s is empty' % json_file)
                    # Calculate test statistics from outputs
                    tests[testIndex].calculate_results();

        tests.sort(key=lambda x: (x.metadata['benchmark'], x.metadata['rwmixread'], x.clients, x.metadata['op_size'], x.metadata['iteration'], x.metadata['iodepth']))

        print_header(ctx)

        for test in tests:
            test.printTest()

            values = (test.hashid, dn, test.metadata['benchmark'], int(test.metadata['iteration']), 
                test.clients, int(test.metadata['op_size']), test.metadata['mode'], int(test.metadata['rwmixread']), int(test.metadata['iodepth']), test.bw, test.iops, test.lat['avg'])
            c = conn.cursor()
            c.execute('INSERT OR IGNORE INTO results VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', values)
            conn.commit()
        conn.close()


