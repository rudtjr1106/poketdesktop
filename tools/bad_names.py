# -*- coding: utf-8 -*-
"""이미 있는 닉네임 가운데 부적절한 닉네임 거르기(server/app/names.py, 2.5.8)에 걸리는 것을 뽑는다. **읽기만 한다.**

거르기는 가입 · 닉네임 변경 때만 돈다 - 이미 있는 계정은 그대로다. 그 가운데 걸리는 것은 운영자가 보고 정한다
(닉네임 변경권을 주고 바꿔 달라고 하기 등). 금지어 · 예외 목록을 고친 뒤 오탐이 늘지 않았는지 볼 때도 쓴다.

    bash deploy/prodq.sh sql "SELECT id, username FROM users" --limit 5000 | python tools/bad_names.py

표준 입력의 '번호<TAB>닉네임' 줄을 읽어 걸리는 줄만 '번호  닉네임  까닭' 으로 찍는다 (머리줄 · 다른 줄은 넘긴다).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server"))

from app import names                                       # noqa: E402

KR = {"profanity": "욕설", "sexual": "성적인 말", "hate": "혐오 표현", "staff": "운영진 사칭"}


def main():
    seen = hit = 0
    for line in sys.stdin:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 2 or not parts[0].strip().isdigit():
            continue
        seen += 1
        why = names.why(parts[1])
        if why:
            hit += 1
            print("%s\t%s\t%s" % (parts[0].strip(), parts[1], KR.get(why, why)))
    print("닉네임 %d개 가운데 %d개가 걸린다" % (seen, hit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
