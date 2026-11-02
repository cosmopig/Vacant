#!/bin/bash
# Fix for R20261102_0700-1 (Problem B)
# Set MemoryMax to 6G for vacant-labd.service
sudo systemctl set-property vacant-labd.service MemoryMax=6G
