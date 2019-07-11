#!/bin/bash
#
# Creates VGs and LVs for Bluestore OSDs
#
# Orlando Moreno

# List of device names
#DEVICES=(nvme0n1 nvme1n1 nvme4n1 nvme5n1 nvme6n1 nvme7n1)
DEVICES=(`lsblk | grep 7T | awk {'print $1'}`)

# OSDs per device
OSDS=2

# Collocate metadata on device. If false, use dedicated device
COLO_META=true
#META_DEVICES=(nvme2n1)
META_DEVICES=(`lsblk | grep 349.3G | awk {'print $1'} | head -n 1`)

# Calculate total number of OSDs per Node
numDevices=${#DEVICES[@]}
total_osds=$(( numDevices * OSDS ))

numMeta=${#META_DEVICES[@]}

# Calculate size of OSD as % of device capacity
SIZE=$(bc <<< "scale=0; 100/$OSDS")

# Calculate number of OSDs to meta device ratio
metaRatio=$(( total_osds / numMeta ))
# Evenly partition meta device for each OSD metadata and WAL (NEED TO CHANGE)
#META_SIZE=$(bc <<< "scale=0; 100/($metaRatio*2)")
META_SIZE=$(bc <<< "scale=0; 100/($metaRatio)")

/root/remove_ceph_lvms.sh

if [ "$COLO_META" == false ]; then
	for (( i=0; i<numMeta; i++ ))
	do
		#sgdisk -Z /dev/${META_DEVICES[$i]}
		vgcreate meta-vg$i /dev/${META_DEVICES[$i]}
	done
fi

# Create VGs for OSDs
for (( i=0; i<numDevices; i++))
do
	#sgdisk -Z /dev/${DEVICES[$i]}
        vgcreate data-vg$i /dev/${DEVICES[$i]}
done

# Create LVs for OSDs
for (( i=0; i<total_osds; i++ ))
do
        # Calculate which device OSD will be assigned to
        device=$(( i / OSDS ))
	metaDevice=$(( i / metaRatio ))

        lvcreate -l ${SIZE}%VG -n block-$i data-vg$device
	if [ "$COLO_META" == false ]; then
#		lvcreate -l ${META_SIZE}%VG -n wal-$i meta-vg$metaDevice
		lvcreate -l ${META_SIZE}%VG -n db-$i meta-vg$metaDevice
        	ceph-volume lvm create --bluestore --data data-vg${device}/block-$i --block.db meta-vg${metaDevice}/db-$i #--block.wal meta-vg${metaDevice}/wal-$i
#		echo "Created LVs"
        else
        	ceph-volume lvm create --bluestore --data data-vg${device}/block-$i
#		echo "Created LVs"
	fi
done

