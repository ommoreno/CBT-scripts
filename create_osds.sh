#!/bin/bash

for i in {0..15}
do
        ceph-volume lvm create --bluestore --data /dev/disk/by-partlabel/osd-device-${i}-block --block.db /dev/disk/by-partlabel/osd-device-${i}-db --block.wal /dev/disk/by-partlabel/osd-device-${i}-wal
done

