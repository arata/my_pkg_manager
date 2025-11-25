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
from version_check import LooseVersion, connect_version

base_conda_forge_donwload_url = "https://conda.anaconda.org/conda-forge/"
base_anaconda_donwload_url = "https://repo.anaconda.com/pkgs/main/"

# download url sample: both 2 packages url have same hash
# "https://anaconda.org/anaconda/llama.cpp/0.0.6872/download/linux-64/llama.cpp-0.0.6872-cuda124_h3e60e59_100.tar.bz2"
# https://repo.anaconda.com/pkgs/main/linux-64/llama.cpp-0.0.6872-cuda124_h3e60e59_100.tar.bz2

def debug_print(*args):
    STYLE = "\033[1;32m"
    RESET = "\033[0m"
    
    print(f"{STYLE}DEBUG:", *args, RESET)

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
    def __repr__(self):
        return f"PackageMetaInfo(name={self.name!r}, version={self.version!r}, build={self.build!r})"

    @staticmethod
    def from_repodata(key: str, info: dict) -> "PackageMetaInfo":

        pmi = PackageMetaInfo()
        pmi.package_name = key

        # repodata のすべてのキーを属性として追加
        for key, value in info.items():
            setattr(pmi, key, value)
        
        return pmi

class SearchInfo():
    
    def __repr__(self):
        return f"SearchInfo(name={self.name!r}, version={self.version!r}, build={self.build!r})"

    @staticmethod
    def from_depend_format(depend: str):
        class VersionInfo:
            def __repr__(self):
                return f"VersionInfo(upper={self.upper}, upper_opertor={self.upper_operator}, lower={self.lower}, lower_operator={self.lower_operator})"
            upper = None
            upper_operator = None
            lower = None
            lower_operator = None
        

        pattern = r"^([A-Za-z0-9_\-\.\+]+)(?:\s+([^\s]+))?(?:\s+([^\s]+))?$"
        match = re.match(pattern, depend)
        name, versions, build = match.groups()

        if not versions:
            di = SearchInfo()
            setattr(di, "name", name)
            setattr(di, "version", VersionInfo())
            setattr(di, "build", build)

            return di
            
        versions = versions.split(',')
        # get min max
        version_info = VersionInfo()
        for version in versions:
            match = re.match(r"(<=|>=|=|!=|<|>)(.+)", version.strip())
            if not match:
                print("include only number")
                version_info.lower = version
                version_info.lower_operator = None
                version_info.upper = version
                version_info.upper_operator = None
                
            else:
                operator, ver = match.groups()
                debug_print(operator, ver)
                if ">" in operator:
                    version_info.lower = ver
                    version_info.lower_operator = operator
                elif "<" in operator:
                    version_info.upper = ver
                    version_info.upper_operator = operator
                else:
                    debug_print("no operator found: ", operator, ver)

        di = SearchInfo()
        setattr(di, "name", name)
        setattr(di, "version", version_info)
        setattr(di, "build", build)

        return di
    

def compare_to(package1, package2):
    """
    name・version・buildが一致 or 条件に合うかを判定する
    """
    # ---------- name ----------
    if hasattr(package1, "name") and hasattr(package2, "name"):
        if package1.name != package2.name:
            return None

    # ---------- version ----------
    if hasattr(package1, "version") and hasattr(package2, "version"):
        res_connect_version = connect_version(package1.version, package2.version)
        if not res_connect_version:
            print("Version are conflict !!!!!")
            return None

    # # ---------- build ----------
    # if hasattr(self, "build") and hasattr(other, "build"):
    #     # 完全一致
    #     if self.build != other.build:
    #         # 一致しない場合は prefix 一致など条件付き一致にも対応
    #         if not self.build.startswith(other.build) and not other.build.startswith(self.build):
    #             return False

    return res_connect_version
        

class RepoData():
    def __init__(self, path='.'):

        self.repodata = self._download_repodata_json(path)

    def _download_repodata_json(self, path):
        if not "repodata_linux-64.json" in os.listdir(path):
            response = requests.get("https://conda.anaconda.org/conda-forge/linux-64/repodata.json")
            _repodata_linux64 = response.json()
            with open(os.path.join(path, 'repodata_linux-64.json'), mode='w') as f:
                json.dump(_repodata_linux64, f, indent=2)

        if not "repodata_noarch.json" in os.listdir(path):
            response = requests.get("https://conda.anaconda.org/conda-forge/noarch/repodata.json")
            _repodata_noarch = response.json()
            with open(os.path.join(path, 'repodata_noarch.json'), mode='w') as f:
                json.dump(_repodata_noarch, f, indent=2)

        with open(os.path.join(path, 'repodata_linux-64.json'), mode="r") as f:
            _repodata_linux64 = json.load(f)

        with open(os.path.join(path, 'repodata_noarch.json'), mode="r") as f:
            _repodata_noarch = json.load(f)

        _repodata = {'linux-64': _repodata_linux64, 'noarch': _repodata_noarch}

        return _repodata

    def _satisfies_version(self, version, conditions) -> bool:
        """
        version: 実際のバージョン文字列（例: "2.18"）
        conditions: 比較条件リスト（例: [">=2.17", "<3.0.a0"]）
        """
        v = LooseVersion(version)
        if conditions.upper_operator == "<":
            if not v < LooseVersion(conditions.upper):
                debug_print("v: ", v)
                debug_print("upper: ", LooseVersion(conditions.upper))
                debug_print(v < LooseVersion(conditions.upper))
                return False
        elif conditions.upper_operator == "<=":
            if not v <= LooseVersion(conditions.upper):
                debug_print("v: ", v)
                debug_print("upper: ", LooseVersion(conditions.upper))
                debug_print(v <= LooseVersion(conditions.upper))
                return False
        if conditions.lower_operator == ">":
            if not v > LooseVersion(conditions.lower):
                debug_print("v: ", v)
                debug_print("lower: ", LooseVersion(conditions.lower))
                debug_print(v > LooseVersion(conditions.lower))
                return False
        elif conditions.lower_operator == ">=":
            if not v >= LooseVersion(conditions.lower):
                debug_print("v:", v)
                debug_print("lower: ", LooseVersion(conditions.lower))
                debug_print(v >= LooseVersion(conditions.lower))
                return False

        if conditions.lower_operator == None and conditions.upper_operator == None:
            print("only number")

        return True

        """
        for cond in conditions:
            debug_print('cond: ', cond)
            match = re.match(r"(<=|>=|=|!=|<|>)(.+)", cond.strip())
            if not match: # 不等号がなく数字だったときにはこっちに行く
                try:
                    target_v = LooseVersion(cond)
                    debug_print(v, target_v)
                    if v == target_v:
                        return True
                    else:
                        return False
                except:
                    raise ValueError(f"Invalid condition: {cond}")

            op, target = match.groups()
            target_v = LooseVersion(target.strip())
            if op == "=":
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
                # 3.14.0 > 3.14
                if not (v > target_v):
                    return False
            elif op == ">=":
                if not (v >= target_v):
                    return False
        """

    def _satisfies_build(self, repo_build, target_build):
        if repo_build == target_build:
            return True
        else:
            if "*" in target_build:
                match_hash = target_build.split("*")
                print(f"match_hash: {match_hash} | repo_build {repo_build}")
                for _hash in match_hash:
                    # if not _hash in repo_build:
                    print(f"repo_build.end_with: {repo_build.endswith(_hash)}")
                    if not repo_build.endswith(_hash):
                        return False

    def search_package_from_repodata(self, target_package: SearchInfo,
                                     get_week_version=False) -> list:
        _candidate_list = []
        _candidate_list_week_version = []
        # grep with name
        for arch in self.repodata.keys():
            for package_key in self.repodata[arch]["packages.conda"].keys():
                repodata_cl = PackageMetaInfo.from_repodata(package_key,
                                                            self.repodata[arch]['packages.conda'][package_key])
                # 名前が一致していなかったらcontinue
                if target_package.name != repodata_cl.name:
                    continue

                # 名前は一致，バージョンをチェックして一致しなかったらcontinue
                if target_package.version:
                    print(' \n ')
                    debug_print('target_package: ', target_package)
                    debug_print('repodata_cl: ', repodata_cl)
                    if not self._satisfies_version(repodata_cl.version, target_package.version):
                        # check week version
                        if get_week_version:
                            pass
                            # debug_print('get_week_version target_package: ', target_package)
                            # debug_print('get_week_version repodata_cl: ', repodata_cl)
                            # for version in target_package.version:
                            #     m = re.match(r"(<=|>=|=|!=|<|>)(.+)", version.strip())
                            #     op, ver = m.groups()
                            #     if ver in repodata_cl.version:
                            #         _candidate_list_week_version.append(repodata_cl)
                        continue
                # 名前とバージョンが一致，ビルドも一致したら特定のパッケージなのでreturn
                if target_package.build:
                    if self._satisfies_build(repodata_cl.build, target_package.build):
                        return repodata_cl

                # どれかしらに部分一致していたら代入
                _candidate_list.append(repodata_cl)

        # パッケージが見つからなかったら
        if len(_candidate_list) == 0:
            if get_week_version:
                debug_print(_candidate_list_week_version)
                _candidate_list = _candidate_list_week_version
            else:
                debug_print("return with no package")
                return None

            
        if len(_candidate_list) > 0:
            print(f'候補はまだたくさんあります．{len(_candidate_list)}')

            # grep with max version
            version_list = [c.version for c in _candidate_list]
            max_version = max(version_list, key=LooseVersion)
            _candidate_list = [c for c in _candidate_list if c.version == max_version]
            print(f'最大値のバージョンで絞りました．候補はまだ {len(_candidate_list)} 個あります．')

            # grep with build number
            build_number_list = [int(c.build_number) for c in _candidate_list]
            max_build_number = max(build_number_list)
            _candidate_list = [c for c in _candidate_list if c.build_number == max_build_number]
            print(f'build numberのバージョンで絞りました．候補はまだ {len(_candidate_list)} 個あります．')

        # debug_print("_candidate_list: ", _candidate_list)
        return _candidate_list[0]


if __name__ == "__main__":
    start_time = time.time()

    all_package = []

    # target_package = "python=3.13"
    # all_package.append(target_package)
    target_package = "numpy"
    all_package.append(target_package)
    # target_package = "python>3.14"
    # all_package.append(target_package)
    # target_package = "python=3.14" # ng because python_abi for 3.14 are not found
    # all_package.append(target_package)
    # target_package = "python=3.13.*" # ok
    # all_package.append(target_package)
    # target_package = "python=3.13" # ok
    # all_package.append(target_package)
    # target_package = "python=3.13.3" # ok
    # all_package.append(target_package)
    # target_package = "python<3.14,>3.10"
    # all_package.append(target_package)
    # target_package = "python<3.14>3.10"
    # all_package.append(target_package)
    # target_package = "python>=3.10,<=3.15"
    # all_package.append(target_package)
    # target_package = "python>=3.10<=3.15"
    # all_package.append(target_package)

    target_package = "python>=3.10<=3.15"

    m = re.match(r"([A-Za-z0-9_\-\.\*]+)", target_package)
    if not m:
        raise ValueError(f"Invalid package spec: {target_package}")
    package_name = m.group(1)
    rest = target_package[m.end():]
    version_specs = re.findall(r"(>=|<=|>|<|=)\s*([0-9][0-9A-Za-z\.\-\*]*)", rest)
    versions = [op + ver for op, ver in version_specs]
    versions = ",".join(versions)
    debug_print(f"{package_name} {versions}")
    
    repodata = RepoData()

    packages = [f"{package_name} {versions}"]

    # parse command
    all_install_target = []
    while packages:
        package = packages.pop(0)

        print('------------')
        print("search: ", package)
        pprint(packages)

        target_package = SearchInfo.from_depend_format(package)

        if target_package.name in all_install_target:
            print('already searche  d')
        
        debug_print("target_package: ", target_package)

        install_target = repodata.search_package_from_repodata(target_package, get_week_version=True)
        all_install_target.append(install_target)
        
        if not install_target:
            print('no package are found')
            sys.exit()

        # 依存関係処理
        for d in install_target.depends:

            # check vertial package are in depends
            virtual_package = ["__cuda", "__osx", "__glibc", "__linux", "__unix", "__win", "__conda"]
            if d.split(' ')[0] in virtual_package:
                continue

            packages.append(d)

        packages = list(set(packages))
        

        # select depnds package
    pprint(all_install_target)

