#!/bin/bash
#
# ALL-FLASH CONFIGURATION - NVMes for both OSDs and journals, multiple parti-tions
# BE SURE TO RUN NAMING SCRIPT TO LABEL THE PARTITIONS!
#
# Automates gdisk commands to partition specified device(s) into Ceph OSD(s) and journal(s).
# Default gdisk inputs are used except for last sector input which is used to specify desired partition size.
#
# Orlando Moreno

# Number of OSD partitions on device, this also applies to journals
numOSDs=4
# Partition device for Bluestore
BLUESTORE=true
# Collocate WAL and rocksDB
COLO_META=false
# Size of journal partitions (Filestore only)
JOURNAL="+10G"
# Size of OSD partitions
OSD="+175G"
#OSD="+3600G"
# Size of rocksDB WAL partitions (Bluestore only)
WAL="+5G"
# Size of rocksDB DB partitions (Bluestore only)
DB="+5G"
# Device for non-colo metadata
META_DEV="/dev/nvme0n4"

# Check if user defines device(s)
if [ "$1" == "" ]; then
        echo "Usage: ./partition_osd.sh <device1> ... <device x>"
        exit
fi

lvs | grep osd | awk '{print $2"/"$1}' | xargs -n 1 lvremove --force
vgs | grep ceph | awk '{print $1}' | xargs -n 1 vgremove --force

for dev in "$@"
do
        # Send zap disk command to gdisk
        printf 'x\nz\ny\nn\n' | gdisk $dev
        sleep 1
        input=""

        if [ "$BLUESTORE" == true ]; then
                if [ "$COLO_META" == true ]; then
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
		fi
        else
		if [ "$COLO_META" == true ]; then
	                # Construct add partition commands for journals
	                for ((i=1; i<=numOSDs; i++ ))
	                do
	                        input+="n\n\n\n${JOURNAL}\n\n"
	                done
		fi
        fi
	
	# Uncomment this for non-colo DB on OSD device
	#for ((i=1; i<=numOSDs; i++ ))
        #do
        #	input+="n\n\n\n${DB}\n\n"
        #done
        # Construct add partition commands for OSDs
        for((i=1; i<=numOSDs; i++ ))
        do
                input+="n\n\n\n${OSD}\n\n"
        done

        # Tack on the write to disk command to the input string
        input+="w\ny\n"

        # Send entire command string to gdisk
        printf $input | gdisk $dev

        echo "Partitioned $dev"
        sleep 1
        sync
done


