import re
from functools import total_ordering
from packaging.version import Version

import re
from functools import total_ordering

import re
from functools import total_ordering

import re
from functools import total_ordering

@total_ordering
class LooseVersion:
    pattern = re.compile(
        r"^(?P<num>(?:\d+\.)*\d+|\d+\.\*\*|\*)(?P<suffix>[a-zA-Z]+|\*)?(?P<suffix_num>\d+)?$"
    )

    def __init__(self, version: str):
        self.original = version.strip()
        self.is_inf = 0  # 0=通常, 1=+inf, -1=-inf

        # 無限大
        if self.original.lower() == "inf":
            self.is_inf = 1
            self.num = None
            self.fixed_prefix = ()
            self.suffix = None
            self.suffix_num = -1
            return
        elif self.original.lower() == "-inf":
            self.is_inf = -1
            self.num = None
            self.fixed_prefix = ()
            self.suffix = None
            self.suffix_num = -1
            return

        # ワイルドカード対応
        if "*" in self.original:
            parts = self.original.split(".")
            fixed = []
            for p in parts:
                if p == "*":
                    break
                fixed.append(int(p))
            self.fixed_prefix = tuple(fixed)
            self.num = None
            self.suffix = None
            self.suffix_num = -1
            return

        # 通常バージョン
        m = self.pattern.fullmatch(self.original)
        if not m:
            raise ValueError(f"Invalid version: {version}")

        self.num = tuple(map(int, m.group("num").split(".")))
        self.suffix = m.group("suffix") if m.group("suffix") else None
        self.suffix_num = int(m.group("suffix_num")) if m.group("suffix_num") else -1
        self.fixed_prefix = self.num

    def _cmp_key(self):
        # 無限大
        if self.is_inf != 0:
            return (self.is_inf,)
        # ワイルドカードは数字部分を inf にして自然な比較
        if self.num is None:
            return (float('inf'),)
        # 通常数字部分
        return self.num

    def __lt__(self, other):
        # 無限大
        if self.is_inf != 0 or other.is_inf != 0:
            return self._cmp_key() < other._cmp_key()

        # ワイルドカード同士
        if self.num is None and other.num is None:
            # 固定部分で先頭から比較
            min_len = min(len(self.fixed_prefix), len(other.fixed_prefix))
            return self.fixed_prefix[:min_len] < other.fixed_prefix[:min_len]

        # 片方だけワイルドカード
        if self.num is None:
            # 左が * → 左は inf 扱い
            return False
        if other.num is None:
            # 右が * → 右は inf 扱い
            return True

        # 通常数字部分
        return self.num < other.num

    def __eq__(self, other):
        # 無限大
        if self.is_inf != 0 or other.is_inf != 0:
            return self.is_inf == other.is_inf

        # 両方数字
        if self.num is not None and other.num is not None:
            return self.num == other.num

        # 片方がワイルドカード
        if self.num is None and other.num is not None:
            return other.num[:len(self.fixed_prefix)] == self.fixed_prefix
        if self.num is not None and other.num is None:
            return self.num[:len(other.fixed_prefix)] == other.fixed_prefix

        # 両方ワイルドカード
        min_len = min(len(self.fixed_prefix), len(other.fixed_prefix))
        return self.fixed_prefix[:min_len] == other.fixed_prefix[:min_len]

    def __repr__(self):
        return f"LooseVersion('{self.original}')"


import math
def connect_version(version1, version2):
    def _parse(version):
        _v = {"min": None, "max": None}
        for cond in version:
            match = re.match(r"(<=|>=|=|==|!=|<|>)(.+)", cond.strip())
            op, target = match.groups()
            if op == "=" or op == "==": return
            
            if ">" in op:
                _v["min"] = target
            if "<" in op:
                _v["max"] = target

        if _v["min"] == None:
            _v["min"] = "-inf"
        if _v["max"] == None:
            _v["max"] = "inf"
        
        return _v

    a = _parse(version1)
    b = _parse(version2)

    if not (a['min'] < b['max'] and b['min'] < a['max']):
        return None
    
    upper = min([a['max'], b['max']], key=LooseVersion)
    lower = max([a['min'], b['min']], key=LooseVersion)

    version_str = []
    if upper and upper != 'inf':
        version_str.append(f'<={upper}')
    if lower and lower != '-inf':
        version_str.append(f'>={lower}')

    return version_str


# ----------- 使い方 -----------
if __name__ == "__main__":
    v1 = LooseVersion("1.2.*")
    v2 = LooseVersion("1.3.3")
    v3 = LooseVersion("1.2.3")
    v4 = LooseVersion("1.2.3a")
    v5 = LooseVersion("3.14.0")
    v6 = LooseVersion("3.14")

    vv1 = Version("1.1.1")
    vv2 = Version("2.1.1")

    # print(v1 > v2)    # False
    # print(v1 < v2)    # True
    # print(v1 >= v2)    # False
    # print(v1 <= v2)    # True
    # print(v1 == v3)   # True
    # print(v1 == v4)

    # print(v5 > v6) # 1.2 > 1.3
    # print(v1 > v6)

    # print(vv1 > vv2)

    # print(LooseVersion("1.2.2") > LooseVersion("2.2.9"))
    # print(LooseVersion("1.2.2") < LooseVersion("2.2.9"))

    # print(LooseVersion("1.2.2") > LooseVersion("2.2.*"))
    # print(LooseVersion("1.2.2") < LooseVersion("2.2.*"))

    # print(LooseVersion("1.2.2") > LooseVersion("1.2.*"))
    # print(LooseVersion("1.2.2") < LooseVersion("1.2.*"))

    # print(LooseVersion("1.2.*") > LooseVersion("2.2.*"))
    # print(LooseVersion("1.2.*") < LooseVersion("2.2.*"))

    # print(LooseVersion("1.2.*") == LooseVersion("2.2.*"))
    # print(LooseVersion("1.2.1") == LooseVersion("1.2.*"))

    # print('-----------')


    # print(LooseVersion("1.2.2") >= LooseVersion("2.2.9")) # false
    # print(LooseVersion("1.2.2") <= LooseVersion("2.2.9")) # true

    # print(LooseVersion("1.2.2") >= LooseVersion("2.2.*")) # false
    # print(LooseVersion("1.2.2") <= LooseVersion("2.2.*")) # true

    # print(LooseVersion("1.2.2") >= LooseVersion("1.2.*")) # true, cannto comparison
    # print(LooseVersion("1.2.2") <= LooseVersion("1.2.*")) # true

    # print(LooseVersion("1.2.*") >= LooseVersion("2.2.*")) # false
    # print(LooseVersion("1.2.*") <= LooseVersion("2.2.*")) # true
    

    print("max is : ", 
        max(["1.2.2", "2.2.*"], key=LooseVersion)
    )

    # print(max(v3, v5, key=Version))

    a = [">3.14", "<3.20"]
    b = [">3.10", "<3.16"]

    c = ["<3.16"]
    d = [">3.18"]

    c = ["<3.16"]
    d = [">3.18"]

    e = [">3.14", "<3.20"]
    f = [">2.0", "<3.0"]

    g = [">3.*", "<5.*"]
    h = ['>1.*', "<2"]

    j = [">3.*", "<5.*"]
    k = ['>1.*', "<3.5"]

    l = ['>=18']
    m = ['>=18']

    ur = connect_version(l, m)
