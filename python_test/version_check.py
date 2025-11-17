import re
from functools import total_ordering

@total_ordering
class LooseVersion:
    # 数字部分の最後に * を許可
    pattern = re.compile(r"""
        ^                       # 行頭
        (?P<num>(?:\d+\.)*\d+|\d+\.\*\*|\*)   # 1.2.3 または 1.2.* または *
        (?P<suffix>[a-zA-Z]+|\*)?            # サフィックス a, rc, s または *
        (?P<suffix_num>\d+)?                  # サフィックス数字 s2 など
        $                       # 行末
    """, re.X)

    def __init__(self, version: str):
        self.original = version.strip()

        # まず簡単に "*" を含む場合に置き換え
        if "*" in self.original:
            # ワイルドカードがある場合は数字部分も suffix も None として扱う
            self.num = None
            self.suffix = None
            self.suffix_num = -1
            return

        # ワイルドカードがない場合は通常パース
        m = self.pattern.fullmatch(self.original)
        if not m:
            raise ValueError(f"Invalid version: {version}")

        num_str = m.group("num")
        self.num = tuple(map(int, num_str.split(".")))

        suffix = m.group("suffix")
        self.suffix = suffix if suffix else None

        self.suffix_num = int(m.group("suffix_num")) if m.group("suffix_num") else -1

    def _cmp_key(self, other):
        # 数字部分
        if self.num is None:
            num_len = len(other.num) if other.num is not None else 1
            num_key = tuple(-1 for _ in range(num_len))
        else:
            num_len = len(other.num) if other.num is not None else len(self.num)
            num_key = self.num + (-1,) * (num_len - len(self.num))

        # サフィックス部分
        if self.suffix is None:
            suf_key = [0] if other.suffix is None else [0] * len(other.suffix)
        else:
            suf_key = [ord(c) for c in self.suffix]

        # サフィックス数字
        suf_num_key = self.suffix_num

        return (num_key, suf_key, suf_num_key)

    def __lt__(self, other):
        return self._cmp_key(other) < other._cmp_key(self)

    def __eq__(self, other):
        # ワイルドカードは任意の値に一致
        if self.num is None or other.num is None:
            return True

        # 数字部分
        min_len = min(len(self.num), len(other.num))
        for i in range(min_len):
            if self.num[i] != other.num[i]:
                return False

        # サフィックス
        if self.suffix is not None and other.suffix is not None:
            if self.suffix != other.suffix:
                return False

        # サフィックス数字
        if self.suffix_num != -1 and other.suffix_num != -1:
            if self.suffix_num != other.suffix_num:
                return False

        return True

# ----------- 使い方 -----------
if __name__ == "__main__":
    v1 = LooseVersion("1.2.*")
    v2 = LooseVersion("1.3.3")
    v3 = LooseVersion("1.2.3")
    v4 = LooseVersion("1.2.3a")
    v5 = LooseVersion("3.14.0")
    v6 = LooseVersion("3.14")

    print(v1 > v2)    # False
    print(v1 < v2)    # True
    print(v1 >= v2)    # False
    print(v1 <= v2)    # True
    print(v1 == v3)   # True
    print(v1 == v4)

    print(v5 > v6) # 1.2 > 1.3
    print(v5 < v6)
