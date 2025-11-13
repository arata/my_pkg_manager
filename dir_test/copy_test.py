#!/usr/bin/env python3

import os
import sys
import shutil


from_pkg = "from_dir"
destination = ".prefix"
# destination = "empty"

for item in os.listdir(from_pkg):
    print(item)
    from_item = os.path.join(from_pkg, item)
    destination_item = os.path.join(destination, item)
    shutil.copytree(from_item, destination_item, dirs_exist_ok=True)
