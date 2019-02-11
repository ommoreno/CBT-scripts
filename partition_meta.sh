#!/bin/bash
#
# ALL-FLASH CONFIGURATION - NVMes for both OSDs and journals, multiple parti-tions
# BE SURE TO RUN NAMING SCRIPT TO LABEL THE PARTITIONS!
#
# Automates gdisk commands to partition specified device(s) into Ceph jour-nal(s)/WAL/rocksDB (BlueStore).
# Default gdisk inputs are used except for last sector input which is used to specify desired partition size.
#
# Orlando Moreno

# Number of OSDs to support
numOSDs=16
# Partition device for Bluestore
BLUESTORE=true
# Size of journal partitions (Filestore only)
JOURNAL="+10G"
# Size of rocksDB WAL partitions (Bluestore only)
WAL="+5G"
# Size of rocksDB DB partitions (Bluestore only)
DB="+5G"

# Check if user defines device(s)
if [ "$1" == "" ]; then
        echo "Usage: ./partition_meta.sh <device1> ... <device x>"
        exit
fi

for dev in "$@"
do
        # Send zap disk command to gdisk
        printf 'x\nz\ny\nn\n' | gdisk $dev
        sleep 1
        input=""

        if [ "$BLUESTORE" == true ]; then
                # Construct add partition commands for WALs
                for ((i=1; i<=numOSDs; i++ ))
                do
                        input+="n\n\n\n${WAL}\n\n"
                done
                # Construct add partition commands for DBs
                for ((i=1; i<=numOSDs; i++ ))
                do
                        input+="n\n\n\n${DB}\n\n"
                done
        else
                # Construct add partition commands for journals
                for ((i=1; i<=numOSDs; i++ ))
                do
                        input+="n\n\n\n${JOURNAL}\n\n"
                done
        fi

        # Tack on the write to disk command to the input string
        input+="w\ny\n"

        # Send entire command string to gdisk
        printf $input | gdisk $dev

        echo "Partitioned $dev"
        sleep 1
        sync
done

