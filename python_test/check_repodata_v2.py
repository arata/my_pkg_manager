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

    @staticmethod
    def from_depend_format(depend: str):
        # parse depends
        pattern = r"^([A-Za-z0-9_\-\.\+]+)(?:\s+([^\s]+))?(?:\s+([^\s]+))?$"
        match = re.match(pattern, depend)

        if not match:
            print("not match: ", {'name': depend, 'version': None, 'build': None})

        name, version, build = match.groups()
        if version:
           version = version.split(',') 

        pmi = PackageMetaInfo()
        setattr(pmi, "name", name)
        setattr(pmi, "version", version)
        setattr(pmi, "build", build)

        return pmi

def compare_to(package1, package2):
    """
    name・version・buildが一致 or 条件に合うかを判定する
    """
    # ---------- name ----------
    if hasattr(package1, "name") and hasattr(package2, "name"):
        # print("compare_to name: ", self.name, other_pkg.name)
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
        debug_print("version: ",version, type(version), 'conditions: ', conditions, type(conditions))

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

        return True # condition are satisifies

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

    def search_package_from_repodata(self, target_package: PackageMetaInfo, get_week_version=False) -> list:
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
                    if not self._satisfies_version(repodata_cl.version, target_package.version):
                        # check week version
                        if get_week_version:
                            for version in target_package.version:
                                m = re.match(r"(<=|>=|=|!=|<|>)(.+)", version.strip())
                                op, ver = m.groups()
                                if ver in repodata_cl.version:
                                    _candidate_list_week_version.append(repodata_cl)
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
            debug_print("------------- version list ------------------------")
            debug_print(version_list)
            debug_print("------------- version list ------------------------")
            max_version = max(version_list, key=LooseVersion)
            _candidate_list = [c for c in _candidate_list if c.version == max_version]
            print(f'最大値のバージョンで絞りました．候補はまだ {len(_candidate_list)} 個あります．')

            # grep with build number
            build_number_list = [int(c.build_number) for c in _candidate_list]
            max_build_number = max(build_number_list)
            _candidate_list = [c for c in _candidate_list if c.build_number == max_build_number]
            print(f'build numberのバージョンで絞りました．候補はまだ {len(_candidate_list)} 個あります．')

        print("_candidate_list: ", _candidate_list)
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

    repodata = RepoData()

    all_install_package_list = []
    have_to_check_dep = []
    # parse command
    for spec in all_package:

        # m = re.match(r"([A-Za-z0-9_\-]+)", spec)
        m = re.match(r"([A-Za-z0-9_\-\.\*]+)", spec)
        if not m:
            raise ValueError(f"Invalid package spec: {spec}")

        package_name = m.group(1)
        rest = spec[m.end():]  # package の後ろの比較表現部分

        # 比較式をすべて抽出（>=, <=, >, < の順で優先）
        # version_specs = re.findall(r"(>=|<=|>|<|=)\s*([0-9][0-9A-Za-z\.\-]*)", rest)
        version_specs = re.findall(r"(>=|<=|>|<|=)\s*([0-9][0-9A-Za-z\.\-\*]*)", rest)

        # リスト形式にする
        versions = [op + ver for op, ver in version_specs]
        debug_print(versions)

        # target_package = PackageMetaInfo.from_direct(package_name, versions, build=None)
        target_package = PackageMetaInfo.from_direct("numpy", ["=2.3.5"], build="py312h33ff503_0")
        # debug_print(target_package)
        debug_print(target_package)
        install_target = repodata.search_package_from_repodata(target_package, get_week_version=True)
        if not install_target:
            print('no package are found')
            sys.exit()

        print("----------- install packages and dependencies --------------")
        pprint(install_target)
        pprint(install_target.depends)
        print("--------------------------------------------------------")

        # have_to_check_dep += [PackageMetaInfo.from_depend_format(i) for i in install_target.depends]
        have_to_check_dep = all_install_package_list + [PackageMetaInfo.from_depend_format(i) for i in install_target.depends]
        all_install_package_list.append(install_target)

        while have_to_check_dep:

            print("=================================================================")
            dep = have_to_check_dep[0]
            print(f'Search dependent package of {dep}')
            virtual_package = ["__cuda", "__osx", "__glibc", "__linux", "__unix", "__win", "__conda"]
            if dep.name in virtual_package:
                print(f'{dep} is virtual packages, so continue')
                have_to_check_dep.pop(0)
                continue
            
            install_target = repodata.search_package_from_repodata(dep)
            if not install_target:
                print(f"COULD NOT FIND PACKAGE {dep}")
                input()
                have_to_check_dep.pop(0)
                continue

            print(f'{dep}の条件に一致するパッケージ{install_target}を発見しました')
            all_install_package_list.append(install_target)

            # もし新しいdependsに，すでに把握しているdependsがあった場合にバージョンをアップデートするか，
            # もし，なかったら追加する．
            for install_target_dep in install_target.depends:

                install_target_dep = PackageMetaInfo.from_depend_format(install_target_dep)
                virtual_package = ["__cuda", "__osx", "__glibc", "__linux", "__unix", "__win", "__conda"]
                if install_target_dep.name in virtual_package:
                    continue

                # 新しいdependsが既存のdependsチェックリストに入っているかを調べる
                # もし入っていなかったら追加
                if not install_target_dep.name in [_d.name for _d in have_to_check_dep]:
                    debug_print("no depends in check list: ", install_target_dep)
                    have_to_check_dep.append(install_target_dep)

                # もし入っていたらバージョンの確認
                else:
                    for d in have_to_check_dep.copy():
                        if d.name == install_target_dep.name:
                            debug_print("find same depends: ", d, install_target_dep)
                            new_version = compare_to(install_target_dep, d)
                            debug_print("find same depends, update to :", new_version)
                            input()
                            if new_version:
                                d.version = new_version

            have_to_check_dep.pop(0)
        input('end one package')
    print('fin')
    pprint(all_install_package_list)

# embed()

