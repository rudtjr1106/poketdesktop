# -*- coding: utf-8 -*-
"""버전을 올리고, exe 를 만들고, GitHub 릴리스까지 올린다.

    python tools/release.py            # common/version.py 의 버전 그대로 릴리스
    python tools/release.py 0.4.0      # 버전을 0.4.0 으로 바꾼 뒤 릴리스
    python tools/release.py --patch    # 0.3.0 -> 0.3.1
    python tools/release.py --minor    # 0.3.1 -> 0.4.0
    python tools/release.py --dry-run  # 빌드까지만 하고 올리지는 않는다

하는 일
    1. 버전 정하기 (common/version.py 수정)
    2. 커밋 안 된 변경이 있으면 멈춘다
    3. exe 빌드
    4. git tag vX.Y.Z 만들고 push
    5. gh release create 로 exe 를 올린다
"""
import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VERSION_FILE = os.path.join(ROOT, "common", "version.py")


def run(cmd, check=True, capture=False, **kw):
    if capture:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", **kw)
    else:
        r = subprocess.run(cmd, cwd=ROOT, **kw)
    if check and r.returncode != 0:
        if capture:
            sys.stderr.write((r.stdout or "") + (r.stderr or ""))
        raise SystemExit("  실패: %s" % " ".join(cmd))
    return r


def read_version():
    txt = open(VERSION_FILE, encoding="utf-8").read()
    m = re.search(r'^VERSION\s*=\s*"([^"]+)"', txt, re.M)
    if not m:
        raise SystemExit("common/version.py 에서 VERSION 을 못 찾았습니다.")
    return m.group(1)


def write_version(v):
    txt = open(VERSION_FILE, encoding="utf-8").read()
    txt = re.sub(r'^VERSION\s*=\s*"[^"]+"', 'VERSION = "%s"' % v, txt, count=1,
                 flags=re.M)
    open(VERSION_FILE, "w", encoding="utf-8").write(txt)


def bump(v, kind):
    a, b, c = (list(map(int, v.split("."))) + [0, 0, 0])[:3]
    if kind == "major":
        return "%d.0.0" % (a + 1)
    if kind == "minor":
        return "%d.%d.0" % (a, b + 1)
    return "%d.%d.%d" % (a, b, c + 1)


def notes(version, prev_tag):
    """지난 태그 이후 커밋 제목을 모아 릴리스 노트를 만든다."""
    rng = ("%s..HEAD" % prev_tag) if prev_tag else "HEAD"
    r = run(["git", "log", rng, "--no-merges", "--pretty=format:- %s"],
            capture=True, check=False)
    changes = (r.stdout or "").strip() or "- 첫 릴리스"
    return """## 받는 법

아래 **Assets** 에서 `poketdesktop-v{v}.exe` 를 받아 실행하세요.
파이썬을 따로 깔 필요 없습니다.

처음 실행하면 로그인 창이 뜹니다. **서버 주소**에 서버 주소를 넣고
회원가입하면 1~9세대 어태커 27마리 중 하나를 골라 시작합니다.

- 설정과 도트는 `%APPDATA%\\poketdesktop` 에 저장됩니다.
- 포켓몬 그림은 exe 에 들어있지 않고 실행할 때 서버에서 받아 캐시합니다.
- 백신이 처음 보는 exe 라며 경고할 수 있습니다 (서명이 없어서 그렇습니다).

## 바뀐 것

{changes}
""".format(v=version, changes=changes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version", nargs="?", help="예: 0.4.0")
    ap.add_argument("--patch", action="store_true")
    ap.add_argument("--minor", action="store_true")
    ap.add_argument("--major", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="빌드까지만")
    ap.add_argument("--skip-build", action="store_true")
    a = ap.parse_args()

    cur = read_version()
    if a.version:
        new = a.version.lstrip("v")
    elif a.major:
        new = bump(cur, "major")
    elif a.minor:
        new = bump(cur, "minor")
    elif a.patch:
        new = bump(cur, "patch")
    else:
        new = cur

    print("현재 버전 %s  ->  릴리스 %s" % (cur, new))

    # ---- 커밋 안 된 변경 확인 ----
    def changed():
        """git status --porcelain 을 파일 경로 목록으로.

        앞 두 글자가 상태 표시이고 그 뒤가 경로다. 앞 공백이 의미를 가지므로
        출력 전체를 strip 하면 안 된다 (한 글자씩 밀린다).
        """
        out = run(["git", "status", "--porcelain"], capture=True).stdout
        paths = []
        for line in out.splitlines():
            if not line.strip():
                continue
            p = line[2:].strip().replace("\\", "/")
            if " -> " in p:                       # 이름이 바뀐 경우
                p = p.split(" -> ", 1)[1]
            paths.append(p.strip('"'))
        return paths

    dirty = changed()
    if new != cur:
        if dirty:
            raise SystemExit("  커밋 안 된 변경이 있습니다:\n    "
                             + "\n    ".join(dirty))
        write_version(new)
        print("  common/version.py -> %s" % new)
        run(["git", "add", "common/version.py"])
        run(["git", "commit", "-q", "-m", "버전 %s" % new])
    elif dirty:
        raise SystemExit("  커밋 안 된 변경이 있습니다:\n    "
                         + "\n    ".join(dirty))

    tag = "v" + new
    exists = run(["git", "tag", "-l", tag], capture=True).stdout.strip()
    if exists:
        raise SystemExit("  태그 %s 가 이미 있습니다. 버전을 올려 주세요." % tag)

    # ---- 빌드 ----
    # zip(폴더형)만 낸다. 단일 exe 는 실행할 때 자기를 임시 폴더에 풀고
    # 도는데, 그 동작이 악성코드 패커와 같아서 백신이 자주 지운다.
    # 자동 업데이트도 zip 을 받도록 되어 있다.
    zip_path = os.path.join(ROOT, "dist", "poketdesktop-v%s.zip" % new)
    if not a.skip_build:
        print("")
        run([sys.executable, os.path.join(HERE, "build_exe.py"), "--onedir"])
    if not os.path.exists(zip_path):
        raise SystemExit("  배포 파일이 없습니다: %s" % zip_path)
    print("  zip %.1f MB" % (os.path.getsize(zip_path) / 1048576.0))

    if a.dry_run:
        print("\n  --dry-run 이라 여기서 멈춥니다.")
        return 0

    # ---- 태그 ----
    prev = run(["git", "describe", "--tags", "--abbrev=0"],
               capture=True, check=False).stdout.strip()
    print("")
    print("  태그 %s 만들고 올리는 중" % tag)
    run(["git", "tag", "-a", tag, "-m", "포켓 데스크톱 %s" % tag])
    run(["git", "push", "-q", "origin", "HEAD"])
    run(["git", "push", "-q", "origin", tag])

    # ---- 릴리스 ----
    body = notes(new, prev or None)
    body_path = os.path.join(ROOT, "build", "release-notes.md")
    os.makedirs(os.path.dirname(body_path), exist_ok=True)
    open(body_path, "w", encoding="utf-8").write(body)

    print("  GitHub 릴리스 생성")
    run(["gh", "release", "create", tag, zip_path,
         "--title", "포켓 데스크톱 %s" % tag,
         "--notes-file", body_path])

    url = run(["gh", "release", "view", tag, "--json", "url", "-q", ".url"],
              capture=True).stdout.strip()
    print("")
    print("  완료: %s" % url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
