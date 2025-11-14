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

base_conda_forge_donwload_url = "https://conda.anaconda.org/conda-forge/"
base_anaconda_donwload_url = "https://repo.anaconda.com/pkgs/main/"

# download url sample: both 2 packages url have same hash
# "https://anaconda.org/anaconda/llama.cpp/0.0.6872/download/linux-64/llama.cpp-0.0.6872-cuda124_h3e60e59_100.tar.bz2"
# https://repo.anaconda.com/pkgs/main/linux-64/llama.cpp-0.0.6872-cuda124_h3e60e59_100.tar.bz2

def download_repodata_json():
    if not "repodata.json" in os.listdir():
        response = requests.get("https://conda.anaconda.org/conda-forge/linux-64/repodata.json")
        _repodata = response.json()
        print(type(_repodata))
        with open('repodata.json', 'w') as f:
            json.dump(_repodata, f, indent=2)

    with open('repodata.json', mode="r") as f:
        _repodata = json.load(f)

    return _repodata

def parse_conda_filename(filename: str):
    basename = os.path.basename(filename).rsplit('.', 1)[0]
    parts = basename.rsplit('-', 2)
    if len(parts) != 3:
        raise ValueError(f"Unexpected conda filename format: {filename}")

    return {
        "filename": filename.replace('.conda', ''),
        "filename.conda": filename,
        "name": parts[0],
        "version": parts[1],
        "build": parts[2]
    }

def parse_conda_dependency(dep_str):
    """
    conda の依存関係文字列をパースして辞書にする
    例:
      'libgcc-ng >=12' -> {'name': 'libgcc-ng', 'version': '>=12', 'build': None}
      'libzlib 1.3.1 hd590300_0' -> {'name': 'libzlib', 'version': '1.3.1', 'build': 'hd590300_0'}
    """
    # 正規表現パターン
    pattern = r"^([A-Za-z0-9_\-\.\+]+)(?:\s+([^\s]+))?(?:\s+([^\s]+))?$"
    match = re.match(pattern, dep_str.strip())
    
    if not match:
        return {'name': dep_str.strip(), 'version': None, 'build': None}

    name, version, build = match.groups()
    return {'name': name, 'version': version, 'build': build}

def search_candidate(tp: str, repodata) -> list:
    _candidate_list = []
    for i in repodata["packages.conda"]:
        pcf = parse_conda_filename(i)
        if tp == pcf['name']:
            print('------ search candidate -------')
            pprint(pcf)
            print('------ search candidate -------')
            _candidate_list.append(pcf)
            
    return _candidate_list


# INSTALL TO .PREFIX/
# extract package
# 1. unzip numpy-1.23.5-py310h53a5b5f_0.conda
#   get info-numpy-1.23.5-py310h53a5b5f_0.tar.zst and pkg-numpy-1.23.5-py310h53a5b5f_0.tar.zst
# 2. unzstd tar.zst
# 3. tar -xvf .tar
def extract_conda_package(conda_file: str, output_dir: str):
    """
    .conda パッケージを展開して output_dir に配置する
    """

    print(f'extract {conda_file} to {output_dir}')
    
    os.makedirs(output_dir, exist_ok=True)

    # 1. .conda は zip として扱える
    import zipfile
    with zipfile.ZipFile(conda_file, 'r') as zip_ref:
        zip_ref.extractall(output_dir)
    
    # 2. 展開された .tar.zst ファイルをさらに解凍
    for filename in os.listdir(output_dir):
        if filename.endswith(".tar.zst"):
            tar_zst_path = os.path.join(output_dir, filename)
            tar_path = tar_zst_path[:-4]  # .zst を削除して tar ファイル名に
            print(f"Decompressing {tar_zst_path} -> {tar_path}")
            
            # zstd 解凍
            with open(tar_zst_path, 'rb') as f_in, open(tar_path, 'wb') as f_out:
                dctx = zstd.ZstdDecompressor()
                dctx.copy_stream(f_in, f_out)
            
            # 3. tar を展開
            print(f"Extracting {tar_path} ...")
            with tarfile.open(tar_path, 'r') as tar:
                tar.extractall(output_dir)
            
            # 不要になった .tar.zst と .tar を削除（任意）
            os.remove(tar_zst_path)
            os.remove(tar_path)

def download_package(package: str, cd = ".cache"):
    # download package
    download_url = urljoin(base_conda_forge_donwload_url, os.path.join("linux-64", package['filename.conda']))
    print("download url: ", download_url)
    print("download to: ", os.path.join(cd, package['filename.conda']))
    pkg_data = requests.get(download_url).content
    # create .cache dir
    os.makedirs(cd, exist_ok=True)
    with open(os.path.join(cd, package['filename.conda']), mode='wb') as f: # wb でバイト型を書き込める
        f.write(pkg_data)    

def install_package(package_name: str):
    package_path = os.path.join(".cache", package_name)
    file_dir_list = os.listdir(package_path)

    print(file_dir_list)
    file_dir_list.remove("info")
    file_dir_list.remove("metadata.json")

    # for item in file_dir_list:
    #     print("item: ", item)
    #     from_path = os.path.join(package_path, item)
    #     destination_path = os.path.join(".prefix", item)
    #     print(from_path, " -> ", destination_path)
    #     if os.path.isdir(from_path):
    #         os.makedirs(destination_path, exist_ok = True)
    #     # TODO: if there are the dependencies install first
    #     # like below symbolic link. zlib has only libz.so
    #     # libz.so -> libz.so.1.2.13
    #     shutil.copytree(from_path, destination_path, dirs_exist_ok = True)

    for root, dirs, files in os.walk(from_path):
        for f in files:
            all_files.append(os.path.join(root, f))

# def find_dependencies(dependencies):
#     virtual_package = ["__cuda", "__osx", "__glibc", "__linux", "__unix", "__win", "__conda"]

def satisfies_version(version, conditions) -> bool:
    """
    version: 実際のバージョン文字列（例: "2.18"）
    conditions: 比較条件リスト（例: [">=2.17", "<3.0.a0"]）
    """
    v = Version(version)

    for cond in conditions:
        match = re.match(r"(<=|>=|==|!=|<|>)(.+)", cond.strip())
        if not match:
            try:
                target_v = Version(cond)
                if v == target_v:
                    return True
                else:
                    return False
            except:
                raise ValueError(f"Invalid condition: {cond}")

        op, target = match.groups()
        target_v = Version(target.strip())

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
            if not (v > target_v):
                return False
        elif op == ">=":
            if not (v >= target_v):
                return False

    return True # condition are satisifies

    

if __name__ == "__main__":
    start_time = time.time()

    # target_packages = "zlib=1.2.13"
    target_packages = "zlib"

    res = target_packages.split("=")
    if len(res) > 1:
        install_packages = res[0]
        install_version = res[1]
    else:
        install_packages = res[0]
        install_version: str = None

    repodata = download_repodata_json()
    
    candidate_list = search_candidate(install_packages, repodata)
    print('Install Candidate for root package: ', candidate_list)

    # get all install version
    if install_version:
        candidate_list = [c for c in candidate_list if c['version'] == install_version]
        print('install version candidate list')
        pprint(candidate_list)

        pkg = candidate_list[install_version]
        
    # get all install hash version
    # if 
    # install latest version
    else:
        version_list = [c['version'] for c in candidate_list]
        max_version = max(version_list, key=Version)
        candidate_list = [c for c in candidate_list if c['version'] == max_version]

        pprint(candidate_list)

        # select latest hash
        _hash = 0
        pkg = None
        for c in candidate_list:
            if int(c['build'].split('_')[-1]) > _hash:
                pkg = c
            
        print("selected: ", pkg)

    pkg_name = pkg['name']
    print("package name: ", pkg_name)

    pkg_info = repodata["packages.conda"][pkg['filename.conda']]
    print('-'*100)
    print("package info: ", pkg_info)

    # check dependencies
    print(" ----- check dependencies ----- ")
    all_install_package_list = [pkg]
    have_to_check_dep = []
    have_to_check_dep += pkg_info['depends']

    while have_to_check_dep:
        print("="*100)
        print("have to check dep: ", have_to_check_dep)
        dep = have_to_check_dep[0]
        print("search depends pkg: ", dep)
        
        target_package_parse_res = parse_conda_dependency(dep)
        pprint(target_package_parse_res)
        virtual_package = ["__cuda", "__osx", "__glibc", "__linux", "__unix", "__win", "__conda"]

        if target_package_parse_res['name'] in virtual_package:
            have_to_check_dep.pop(0)
            continue
        
        candidate_list = search_candidate(target_package_parse_res['name'], repodata)
        pprint(candidate_list)

        # check version if it have
        if target_package_parse_res['version']:
            version_satisfies_candidate_list = []
            for c in candidate_list:
                parse_res_version = target_package_parse_res['version']
                candidate_list_version = c['version']
                print(candidate_list_version, parse_res_version)
                if satisfies_version(candidate_list_version, parse_res_version.split(',')):
                    version_satisfies_candidate_list.append(c)

            candidate_list = version_satisfies_candidate_list

        print("------- here -----------")
        pprint(candidate_list)
        print(target_package_parse_res['build'])
        print("------- here -----------")
        if target_package_parse_res['build']:
            build_satisfies_candidate_list = []
            for c in candidate_list:
                parse_res_build = target_package_parse_res['build']
                candidate_list_build = c['build']
                print(candidate_list_build, parse_res_build)
                if candidate_list_build == parse_res_build:
                    build_satisfies_candidate_list.append(c)
            candidate_list = build_satisfies_candidate_list


        # if reache this if, the candidate still remaining because of version are like >= and target_package_parse_res['build'] is None
        if len(candidate_list) > 1:
            version_list = [c['version'] for c in candidate_list]
            max_version = max(version_list, key=Version)
            candidate_list = [c for c in candidate_list if c['version'] == max_version]

            # select latest build hash hash be like "h4ab18f5_1" or "3_gnu"

            # _hash = 0
            # last_pkg = None
            # for c in candidate_list:
            #     if int(c['build'].split('_')[-1]) > _hash:
            #         last_pkg = c
            # candidate_list = [c]

            # temporarily pick random one
            import random
            ind = random.randint(0, len(candidate_list)-1)
            print('=======================')
            print(candidate_list)
            print(len(candidate_list))
            print(candidate_list[ind])
            print('=======================')
            candidate_list = [candidate_list[ind]]
            
        print("-------------- selected ----------------------")
        pprint(candidate_list)
        print("-------------- selected ----------------------")
        all_install_package_list.append(candidate_list[0])

        pi_dep = repodata["packages.conda"][candidate_list[0]['filename.conda']]['depends']
        print("-------------- next dep ----------------")
        print(pi_dep)
        print("-------------- next dep ----------------")
        have_to_check_dep += pi_dep
        have_to_check_dep.pop(0)

    print("---------------- all_install_package_list -------------------")
    pprint(all_install_package_list)
    pprint([i['filename.conda'] for i in all_install_package_list])
    print("---------------- all_install_package_list -------------------")

    # package install
    for p in all_install_package_list[::-1]:
        print('*******************************************************')
        print(p)
        download_package(p)
        cache_dir = ".cache"
        extract_conda_package(
            os.path.join(cache_dir, p['filename.conda']),
            os.path.join(cache_dir, p['filename'].replace(".conda", ""))
        )
        print("Install: ", p['filename'])
        install_package(p['filename'])
        print('*******************************************************')

    print(time.time() - start_time)

# embed()

