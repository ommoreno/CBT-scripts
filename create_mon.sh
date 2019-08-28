#!/bin/bash

DIR=/etc/ceph
MON=wp01
MGR=wp01

rm -rf /var/lib/ceph/mon/*
rm -rf ${DIR}/ceph.mon.keyring ${DIR}/monmap

echo "CREATING MON KEYRING"
ceph-authtool --create-keyring ${DIR}/ceph.mon.keyring --gen-key -n mon. --cap mon 'allow *'

echo "CREATING CLIENT ADMIN KEYRING"
ceph-authtool --create-keyring /etc/ceph/ceph.client.admin.keyring --gen-key -n client.admin --cap mon 'allow *' --cap osd 'allow *' --cap mds 'allow'

echo "IMPORTING CLIENT ADMIN TO MON"
ceph-authtool ${DIR}/ceph.mon.keyring --import-keyring /etc/ceph/ceph.client.admin.keyring

echo "CREATING MONMAP"
monmaptool --create --add ${MON} 192.168.100.51 ${DIR}/monmap

mkdir /var/lib/ceph/mon/ceph-${MON}

echo "MKFS FOR MONITOR"
ceph-mon --mkfs -c /etc/ceph/ceph.conf -i ${MON} --monmap=${DIR}/monmap --keyring=${DIR}/ceph.mon.keyring
touch /var/lib/ceph/mon/ceph-${MON}/done

echo "STARTING MONITOR"
ceph-run sh -c "ulimit -n 16384 && ulimit -c unlimited && exec ceph-mon -c /etc/ceph/ceph.conf -i ${MON} --keyring=${DIR}/ceph.mon.keyring --pid-file=${DIR}/mon.pid"

echo "STARTING MGR"
ceph-mgr -i ${MGR}

echo "SETTING NOSCRUBS"
ceph osd set noscrub
ceph osd set nodeep-scrub

echo "ENABLING PROMETHEUS"
ceph mgr module enable prometheus --force

#echo "ENABLING RBD_STATS_POOLS"
#ceph config set mgr mgr/prometheus/rbd_stats_pools cbt-librbdfio

echo "ENABLING RBD_SUPPORT"
ceph mgr module enable rbd_support

echo "ENABLING MSGR2"
ceph mon enable-msgr2

