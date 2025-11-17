#!/usr/bin/env python3

import sys
import os
import time
import json
import requests
from IPython import embed
from urllib.parse import urljoin
import os
import shutil
import tarfile
import zstandard as zstd
import re
from packaging.version import Version
from pprint import pprint
from version_check import LooseVersion

base_conda_forge_donwload_url = "https://conda.anaconda.org/conda-forge/"
base_anaconda_donwload_url = "https://repo.anaconda.com/pkgs/main/"

# download url sample: both 2 packages url have same hash
# "https://anaconda.org/anaconda/llama.cpp/0.0.6872/download/linux-64/llama.cpp-0.0.6872-cuda124_h3e60e59_100.tar.bz2"
# https://repo.anaconda.com/pkgs/main/linux-64/llama.cpp-0.0.6872-cuda124_h3e60e59_100.tar.bz2

class PackageMetaInfo:
    """
    >>> repodata["packages.conda"]["tensorflow-2.19.0-cpu_py310h42475c5_2.conda"]
    {
    'build': 'cpu_py310h42475c5_2',
    'build_number': 2,
    'depends': ['python >=3.10,<3.11.0a0', 'python_abi 3.10.* *_cp310', 'tensorflow-base 2.19.0 cpu_py310hc738c44_2', 'tensorflow-estimator 2.19.0 cpu_py310h05c6a32_2'],
    'license': 'Apache-2.0',
    'license_family': 'Apache',
    'md5': 'f994f4e784df82ac14a8d730b60cce9a',
    'name': 'tensorflow',
    'sha256': '175575346161c525ab7948659aaa3ea99c1b6696d66216ea531e677818fe7ad0',
    'size': 49249,
    'subdir': 'linux-64',
    'timestamp': 1761170056540,
    'track_features': 'tensorflow-cpu',
    'version': '2.19.0'
    }
    """
    # package_name: str = None
    # name: str = None
    # version = None

    @staticmethod
    def from_repodata(key: str, info: dict) -> "PackageMetaInfo":

        pmi = PackageMetaInfo()
        pmi.package_name = key

        # repodata のすべてのキーを属性として追加
        for key, value in info.items():
            setattr(pmi, key, value)
        
        return pmi

    @staticmethod
    def from_direct(name=None, version=None, build=None):

        pmi = PackageMetaInfo()
        setattr(pmi, "name", name)
        setattr(pmi, "version", version)
        setattr(pmi, "build", build)
        # pmi.name = name
        # pmi.version = version
        # pmi.build = build

        return pmi


class RepoData():
    def __init__(self, path='.'):

        self.repodata = self._download_repodata_json(path)

    def _download_repodata_json(self, path):
        if not "repodata.json" in os.listdir(path):
            response = requests.get("https://conda.anaconda.org/conda-forge/linux-64/repodata.json")
            _repodata = response.json()
            with open(os.path.join(path, 'repodata.json'), mode='w') as f:
                json.dump(_repodata, f, indent=2)

        with open(os.path.join(path, 'repodata.json'), mode="r") as f:
            _repodata = json.load(f)

        return _repodata

    def _satisfies_version(self, version, conditions) -> bool:
        """
        version: 実際のバージョン文字列（例: "2.18"）
        conditions: 比較条件リスト（例: [">=2.17", "<3.0.a0"]）
        """

        v = LooseVersion(version)

        for cond in conditions:
            match = re.match(r"(<=|>=|==|!=|<|>)(.+)", cond.strip())
            if not match:
                print('not match')
                try:
                    target_v = LooseVersion(cond)
                    if v == target_v:
                        return True
                    else:
                        return False
                except:
                    raise ValueError(f"Invalid condition: {cond}")

            op, target = match.groups()
            target_v = LooseVersion(target.strip())

            if op == "==":
                if not (v == target_v):
                    return False
            elif op == "!=":
                if not (v != target_v):
                    return False
            elif op == "<":
                if not (v < target_v):
                    return False
            elif op == "<=":
                if not (v <= target_v):
                    return False
            elif op == ">":
                print("op > ")
                # 3.14.0 > 3.14
                if not (v > target_v):
                    return False
            elif op == ">=":
                if not (v >= target_v):
                    return False

        return True # condition are satisifies

    def search_package_from_repodata(self, target_package: PackageMetaInfo) -> list:
        _candidate_list = []
        # grep with name
        for package_key in self.repodata["packages.conda"].keys():

            repodata_cl = PackageMetaInfo.from_repodata(package_key,
                                                        self.repodata['packages.conda'][package_key])
            # 名前が一致していなかったらcontinue
            if target_package.name != repodata_cl.name:
                continue

            # 名前は一致，バージョンをチェックして一致しなかったらcontinue
            if target_package.version:
                if not self._satisfies_version(repodata_cl.version, target_package.version):
                    print(package_key, repodata_cl.version, target_package.version)
                    continue

            # 名前とバージョンが一致，ビルドも一致したら特定のパッケージなのでreturn
            if target_package.build:
                input('here')
                if repodata_cl.build == target_package.build:
                    return repodata_cl

            # どれかしらに部分一致していたら代入
            _candidate_list.append(repodata_cl)

        # パッケージが見つからなかったら
        if len(_candidate_list) == 0:
            return None
            
        if len(_candidate_list) > 0:
            print(f'候補はまだたくさんあります．{len(_candidate_list)}')

            # grep with max version
            version_list = [c.version for c in _candidate_list]
            max_version = max(version_list, key=Version)
            _candidate_list = [c for c in _candidate_list if c.version == max_version]
            print(f'最大値のバージョンで絞りました．候補はまだ {len(_candidate_list)} 個あります．')

            # grep with build number
            build_number_list = [int(c.build_number) for c in _candidate_list]
            max_build_number = max(build_number_list)
            _candidate_list = [c for c in _candidate_list if c.build_number == max_build_number]
            print(f'build numberのバージョンで絞りました．候補はまだ {len(_candidate_list)} 個あります．')

        return _candidate_list[0]


if __name__ == "__main__":
    start_time = time.time()

    all_package = []

    # target_package = "python"
    # all_package.append(target_package)
    # target_package = "python>3.14"
    # all_package.append(target_package)
    target_package = "python=3.14"
    all_package.append(target_package)
    # target_package = "python<3.14,>3.10"
    # all_package.append(target_package)
    # target_package = "python<3.14>3.10"
    # all_package.append(target_package)
    # target_package = "python>=3.10,<=3.15"
    # all_package.append(target_package)
    # target_package = "python>=3.10<=3.15"
    # all_package.append(target_package)

    repodata = RepoData()

    all_install_package_list = []
    # parse command
    for spec in all_package:

        m = re.match(r"([A-Za-z0-9_\-]+)", spec)
        if not m:
            raise ValueError(f"Invalid package spec: {spec}")

        package_name = m.group(1)
        rest = spec[m.end():]  # package の後ろの比較表現部分

        # 比較式をすべて抽出（>=, <=, >, < の順で優先）
        version_specs = re.findall(r"(>=|<=|>|<)\s*([0-9][0-9A-Za-z\.\-]*)", rest)

        # リスト形式にする
        versions = [op + ver for op, ver in version_specs]
        print(versions)
        input()

        target_package = PackageMetaInfo.from_direct(package_name, versions, build=None)

        install_target = repodata.search_package_from_repodata(target_package)
        print("----------- install packages dependencies --------------")
        pprint(install_target.depends)
        print("--------------------------------------------------------")
        all_install_package_list.append(install_target)

        have_to_check_dep = [] + install_target.depends 

        while have_to_check_dep:
            print("===============================================")

            print([i for i in have_to_check_dep])
            
            dep = have_to_check_dep[0]
            print(f"search dependencies: {dep}")

            # parse depends
            pattern = r"^([A-Za-z0-9_\-\.\+]+)(?:\s+([^\s]+))?(?:\s+([^\s]+))?$"
            match = re.match(pattern, dep)

            if not match:
                print("not match: ", {'name': dep, 'version': None, 'build': None})

            name, version, build = match.groups()
            if version:
               version = version.split(',') 
            print(f"name: {name}, version: {version}, build: {build}")

            virtual_package = ["__cuda", "__osx", "__glibc", "__linux", "__unix", "__win", "__conda"]
            if name in virtual_package:
                have_to_check_dep.pop(0)
                continue

            target_package = PackageMetaInfo.from_direct(name, version, build)
            
            install_target = repodata.search_package_from_repodata(target_package)
            if not install_target:
                print(f"COULD NOT FIND PACKAGE {target_package.name}")
                have_to_check_dep.pop(0)
                continue
            
            all_install_package_list.append(install_target)

            have_to_check_dep += install_target.depends 

            have_to_check_dep.pop(0)
            print("===============================================")

        for pkg in all_install_package_list:
            print(pkg)

# embed()

