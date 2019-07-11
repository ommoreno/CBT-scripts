#!/bin/bash

lvs | egrep "db|block" | awk '{print $2"/"$1}' | xargs -n 1 lvremove --force
vgs | egrep "meta|data" | awk '{print $1}' | xargs -n 1 vgremove --force

