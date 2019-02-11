#!/bin/bash
#
# ALL-FLASH CONFIGURATION - NVMes for both OSDs and journals, multiple parti-tions
#
# Uses parted to name device partitions which correspond to assigned OSD/journal
# To check if partition labels were created correctly, use:
# ls -al /dev/disk/by-partlabel
#
# Orlando Moreno


# List of device names
DEVICES=(nvme0n1 nvme1n1 nvme2n1 nvme3n1)
#DEVICES=(sdb sdc sdd sdf sdg sdh sdi sdj sdk sdl sdm sdn sdo)
# OSDs per device
OSDS=4

BLUESTORE=true
COLO_META=false
SGDISK=true

# Calculate total number of OSDs per Node
numDevices=${#DEVICES[@]}
total_osds=$(( numDevices * OSDS ))
# Calculate last OSD index of a node
osd_index=$(( OSDS - 1 ))

rm -rf /dev/disk/by-partlabel/Linux\\x20filesystem
sync
#Assign all OSDs to devices
for (( i=0; i<total_osds; i++ ))
do
        # Calculate which device OSD will be assigned to
        device=$(( i / OSDS ))
        if [ "$BLUESTORE" == true ];then
                if [ "$COLO_META" == true ];then
                        # Partition numbers start at 1
                        WALpart=$(( i + 1 ))
                        dbPart=$(( WALpart + OSDS))
                        # Keep OSD and journal partitions sequentially placed
                        osdPart=$(( dbPart + OSDS ))
                        # For OSDs past the first set, we must calculate the partition number for those devices
                        if [ "$WALpart" -gt "$osd_index" ]
                        then
                                WALpart=$(( WALpart - OSDS * device ))
                                dbPart=$(( WALpart + OSDS))
                                osdPart=$(( dbPart + OSDS ))
                        fi
                        parted /dev/${DEVICES[$device]} name $WALpart "osd-device-$i-wal"
                        parted /dev/${DEVICES[$device]} name $dbPart "osd-device-$i-db"
                        parted /dev/${DEVICES[$device]} name $osdPart "osd-device-$i-block"
                else
                        osdPart=$(( i + 1 ))
                        if [ "$osdPart" -gt "$osd_index" ]
                        then
                                osdPart=$((osdPart - OSDS * device ))
                        fi
                        parted /dev/${DEVICES[$device]} name $osdPart "osd-device-$i-block"
                fi
        else
                if [ "$COLO_META" == true ];then
                        journalPart=$(( i + 1 ))
                        # Keep OSD and journal partitions sequentially placed
                        osdPart=$(( journalPart + OSDS ))

                        # For OSDs past the first set, we must calculate the partition number for those devices
                        if [ "$journalPart" -gt "$osd_index" ]
                        then
                                journalPart=$(( journalPart - OSDS * device ))
                                osdPart=$(( journalPart + OSDS ))
                        fi
			if [ "$SGDISK" == true ];then
				sgdisk -c ${osdPart}:osd-device-${i}-data /dev/${DEVICES[$device]}
				sgdisk -c ${journalPart}:osd-device-${i}-journal /dev/${DEVICES[$device]}
			else
	                        parted /dev/${DEVICES[$device]} name $osdPart "osd-device-$i-data"
	                        parted /dev/${DEVICES[$device]} name $journal-Part "osd-device-$i-journal"
			fi
                else
                        osdPart=$(( i + 1 ))
                        if [ "$osdPart" -gt "$osd_index" ]
                        then
                                osdPart=$((osdPart - OSDS * device ))
                        fi
			if [ "$SGDISK" == true ];then
				sgdisk -c ${osdPart}:osd-device-${i}-data /dev/${DEVICES[$device]}
			else
	                        parted /dev/${DEVICES[$device]} name $osdPart "osd-device-$i-data"
			fi
                fi
        fi
        sync
done

