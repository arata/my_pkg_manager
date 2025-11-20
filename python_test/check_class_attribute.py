#!/usr/bin/env python3

import sys

class PackageMetaInfo:

    def __repr__(self):
        return f"PackageMetaInfo(name={self.name!r}, version={self.version!r}, build={self.build!r})"

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

    def compare_to(self, other_pkg) -> bool:
        # ---------- name ----------
        if hasattr(self, "name") and hasattr(other_pkg, "name"):
            print('has name attrib')
        # ---------- version ----------
        if hasattr(self, "version") and hasattr(other_pkg, "version"):
            print('has version attrib')

    def compare_test(self, pkg) -> bool:
        print(hasattr(self, "version"))
        print(hasattr(self, "name"))
        print(hasattr(self, "hoge"))
        print("---")
        print(hasattr(pkg, "version"))
        print(hasattr(pkg, "name"))
        print(hasattr(pkg, "hoge"))

    def compare_test2(self) -> bool:
        print(hasattr(self, "version"))
        print(hasattr(self, "name"))
        print(hasattr(self, "hoge"))


pmi = PackageMetaInfo().from_direct('hoge', '1.2.3', 'alpha')
pmi2 = PackageMetaInfo().from_direct('fuga', '1.2.4', 'beta')
print(pmi)
print('---')
print(pmi2)

pmi2.compare_test(pmi)

