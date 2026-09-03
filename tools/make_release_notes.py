# -*- coding: utf-8 -*-
"""`.github/release-notes.md` 의 '바뀐 것' 대목을 패치노트에서 다시 쓴다.

    python tools/make_release_notes.py            # 이번 버전으로 고쳐 쓴다
    python tools/make_release_notes.py --check    # 어긋나면 실패만 한다

## 왜 이게 있나

바뀐 것을 두 곳에 적으면 반드시 갈라진다. 앱 안의 '새로운 기능' 창은
`common/patchnotes.py` 를 읽고, GitHub 릴리스 본문은 이 md 파일을 읽는데,
사람이 양쪽을 다 고치는 날은 오지 않는다. 그러면 받은 사람은 자기가 받은
판에 무엇이 들어 있는지 알 수 없다.

그래서 **적는 곳은 `common/patchnotes.py` 한 곳**이고, 이 스크립트가
릴리스 본문을 거기에 맞춰 다시 쓴다. 받는 법 안내는 버전과 상관없는
내용이라 손으로 적어 둔 것을 그대로 둔다 - '바뀐 것' 아래만 갈아낀다.
"""
import argparse
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from common import patchnotes                              # noqa: E402
from common.version import VERSION                         # noqa: E402

NOTES_MD = os.path.join(ROOT, ".github", "release-notes.md")
HEADING = "## 바뀐 것"


def build(version=None):
    """이번 버전으로 채운 md 전체를 돌려준다."""
    version = version or VERSION
    entry = patchnotes.entry(version)
    if not entry:
        raise SystemExit(
            "  common/patchnotes.py 에 %s 가 없습니다. 먼저 적어 주세요." % version)
    text = io.open(NOTES_MD, encoding="utf-8").read().replace("\r\n", "\n")
    if HEADING not in text:
        raise SystemExit("  %s 에서 '%s' 를 못 찾았습니다." % (NOTES_MD, HEADING))
    # 받는 법 안내(앞부분)는 그대로 두고 그 뒤만 갈아낀다.
    head = text.split(HEADING, 1)[0].rstrip("\n")
    return "%s\n\n%s\n\n%s" % (head, HEADING, patchnotes.as_markdown(version))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="고치지 않고, 어긋나면 1 로 끝난다 (CI 용)")
    ap.add_argument("--version", help="기본값은 common/version.py 의 버전")
    a = ap.parse_args()

    want = build(a.version)
    have = io.open(NOTES_MD, encoding="utf-8").read().replace("\r\n", "\n")
    if have == want:
        print("  릴리스 본문이 패치노트와 같습니다 (%s)" % (a.version or VERSION))
        return 0
    if a.check:
        sys.stderr.write(
            "  릴리스 본문이 패치노트와 다릅니다.\n"
            "  `python tools/make_release_notes.py` 를 돌려 맞춰 주세요.\n")
        return 1
    io.open(NOTES_MD, "w", encoding="utf-8", newline="\n").write(want)
    print("  %s 를 %s 기준으로 다시 썼습니다."
          % (os.path.relpath(NOTES_MD, ROOT), a.version or VERSION))
    return 0


if __name__ == "__main__":
    sys.exit(main())
