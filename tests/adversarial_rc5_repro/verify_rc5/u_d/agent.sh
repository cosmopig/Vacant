#!/bin/bash
sed -i 's/self.items.pop()/self.items.pop(0)/' queue.py
