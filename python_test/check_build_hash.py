#!/usr/bin/env python3

import json
import os
import sys
from IPython import embed

with open("repodata.json", mode='r') as f:
    j = json.load(f)

only_conda_format = [i for i in j["packages.conda"] if ".conda" in i]
# print(only_conda_format)
remove_package_name = [i.split("-")[-1].replace(".conda", "") for i in only_conda_format]
print(remove_package_name)

embed()
