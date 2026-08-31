# -*- coding: utf-8 -*-
"""버전은 여기 한 곳에만 적는다.

서버, 클라이언트, exe 빌드가 전부 이 값을 읽는다.
릴리스할 때는 이 숫자를 올리고 `python tools/release.py` 를 돌린다.
"""

VERSION = "0.4.0"

# 서버와 클라이언트가 서로 너무 다른 버전이면 곤란하므로 앞 두 자리를 본다.
# (0.3.x 끼리는 호환, 0.4.0 이 되면 클라이언트도 새로 받아야 한다)
def series(v=None):
    parts = (v or VERSION).split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else (v or VERSION)


def compatible(other):
    """서버가 알려준 버전과 함께 써도 되는지."""
    if not other:
        return True
    return series(other) == series()
