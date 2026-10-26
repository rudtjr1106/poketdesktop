# -*- coding: utf-8 -*-
"""DP 화면 코드에 박힌 빛깔 표(client/poketdesktop/skins/dp/_literals.py)를 다시 만든다.

DP 틀을 물려받은 테마(플라티나 · 금은 …)는 이 표에 든 빛깔만 제 빛깔로 옮긴다 (skins/derive.py).
DP 화면 파일에 새 빛깔("#rrggbb")을 넣었으면 한 번 돌린다.

    python3 tools/gen_dp_literals.py
"""
import glob
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DP = os.path.join(HERE, "..", "client", "poketdesktop", "skins", "dp")
SKIP = ("_literals.py", "poke_icons.py")

HEAD = '''# -*- coding: utf-8 -*-
"""DP 화면 코드에 박혀 있는 빛깔 전부 (자동으로 만든 표 - 손으로 고치지 말 것).

DP 틀을 물려받은 테마(플라티나 · 금은 …)는 **이 표에 든 빛깔만** 제 빛깔로 옮긴다 (skins/derive.py).
타입 빛깔을 옅게 섞은 기술 단추처럼 코드가 셈해서 만든 빛깔은 표에 없으니 그대로 남는다.

DP 화면 파일에 새 빛깔을 넣었으면 다시 만든다:  python3 tools/gen_dp_literals.py
"""
LITERALS = frozenset((
'''


def main():
    lits = set()
    for f in sorted(glob.glob(os.path.join(DP, "*.py"))):
        if os.path.basename(f) in SKIP:
            continue
        with open(f, encoding="utf-8") as fh:
            for m in re.finditer(r'"#([0-9a-fA-F]{6})"', fh.read()):
                lits.add("#" + m.group(1).lower())
    items = sorted(lits)
    lines = ["    " + ", ".join('"%s"' % c for c in items[i:i + 8]) + "," for i in range(0, len(items), 8)]
    with open(os.path.join(DP, "_literals.py"), "w", encoding="utf-8") as fh:
        fh.write(HEAD + "\n".join(lines) + "\n))\n")
    print("빛깔 %d개" % len(items))


if __name__ == "__main__":
    main()
