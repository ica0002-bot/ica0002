#!/bin/sh -eu

curl -s http://193.40.157.25/students/$(cat name.txt | cut -d: -f2)/inventory.json
