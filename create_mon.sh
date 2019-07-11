#!/bin/bash

DIR=/etc/ceph
HOST=wp01

rm -rf /var/lib/ceph/mon/*
rm -rf ${DIR}/ceph.mon.keyring ${DIR}/monmap

mkdir -p /var/lib/ceph/mon/

ceph-authtool --create-keyring ${DIR}/ceph.mon.keyring --gen-key -n mon. --cap mon 'allow *'
ceph-authtool --create-keyring /etc/ceph/ceph.client.admin.keyring --gen-key -n client.admin --cap mon 'allow *' --cap osd 'allow *' --cap mds 'allow'
ceph-authtool ${DIR}/ceph.mon.keyring --import-keyring /etc/ceph/ceph.client.admin.keyring
monmaptool --create --add ${HOST} 192.168.50.21 ${DIR}/monmap
mkdir /var/lib/ceph/mon/ceph-${HOST}
ceph-mon --mkfs -c /etc/ceph/ceph.conf -i ${HOST} --monmap=${DIR}/monmap --keyring=${DIR}/ceph.mon.keyring
touch /var/lib/ceph/mon/ceph-${HOST}/done
ceph-run sh -c "ulimit -n 16384 && ulimit -c unlimited && exec ceph-mon -c /etc/ceph/ceph.conf -i ${HOST} --keyring=${DIR}/ceph.mon.keyring --pid-file=${DIR}/mon.pid"

ceph-mgr -i ${HOST}
ceph osd set noscrub
ceph osd set nodeep-scrub
ceph mgr module enable prometheus --force
ceph mon enable-msgr2
