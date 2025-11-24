import re
import sys
import os

spec = sys.argv[1]

# m = re.match(r"([A-Za-z0-9_\-]+)", spec)
m = re.match(r"([A-Za-z0-9_\-\.\*]+)", spec)

if not m:
    raise ValueError(f"Invalid package spec: {spec}")

package_name = m.group(1)
rest = spec[m.end():]  # package の後ろの比較表現部分

print(package_name, ', ', rest)

# 比較式をすべて抽出（>=, <=, >, < の順で優先）
# version_specs = re.findall(r"(>=|<=|>|<|=)\s*([0-9][0-9A-Za-z\.\-]*)", rest)
version_specs = re.findall(r"(>=|<=|>|<|=)\s*([0-9][0-9A-Za-z\.\-\*]*)", rest)
print("version_specs: ", version_specs)

# リスト形式にする
versions = [op + ver for op, ver in version_specs]
print(versions)
