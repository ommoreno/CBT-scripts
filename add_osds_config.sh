#!/bin/bash
#
# Creates the OSD/Journal definitions for ceph.conf.
# Prints result on screen, concatenate to a ceph.conf file using:
# ./add_osd_config.sh >> <Name of ceph.conf>
#
# Orlando Moreno

# List hostnames of Ceph storage nodes
NODES=(fmdcppzona01 fmdcppzona02 fmdcppzona03 fmdcppzona04 fmdcppzona05) #fmdcppzona06)
# OSDs per node
OSDS=16
# Path for OSD data
OSD_DATA="/tmp/cbt/mnt"
# Path for OSD journal
OSD_JOURNAL="/dev/disk/by-partlabel"
# Configure OSDs for BlueStore
BLUESTORE=true

numNodes=${#NODES[@]}
# Calculate total number of OSDs
total_osds=$(( numNodes * OSDS ))
# Calculate last OSD index of a node
osd_index=$(( OSDS - 1 ))

# Assign all OSDs to nodes
for (( i=0; i<total_osds; i++ ))
do
        osd=$i
        echo "[osd.$osd]"
        # Calculate which host OSD will be assigned to
        host=$(( i / OSDS ))
        # For OSDs past the first set, we must calculate the osd number for those hosts
        if [ "$osd" -gt "$osd_index" ]
        then
                osd=$(( i - OSDS * host ))
        fi
        echo -e "\thost = ${NODES[$host]}"
        if [ "$BLUESTORE" == true ]; then
                echo -e "\tosd data = $OSD_DATA/osd-device-$osd-data"
                echo -e "\tbluestore block path = $OSD_JOURNAL/osd-device-$osd-block"
                echo -e "\tbluestore block db path = $OSD_JOURNAL/osd-device-$osd-db"
                echo -e "\tbluestore block wal path = $OSD_JOURNAL/osd-device-$osd-wal"
        else
                echo -e "\tosd journal = $OSD_JOURNAL/osd-device-$osd-journal"
        fi
done

