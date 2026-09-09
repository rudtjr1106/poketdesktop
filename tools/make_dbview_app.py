# -*- coding: utf-8 -*-
"""`포스크탑 관리.app` 을 만든다. 두 번 눌러 DB 를 브라우저로 본다.

## 왜 필요한가

윈도우에는 바탕화면 바로가기가 있어서 두 번 누르면 열린다(dbview.ps1).
맥에는 그게 없어서 터미널을 켜고 저장소로 들어가 명령을 쳐야 했다.
같은 일을 하는데 한쪽만 불편할 이유가 없다.

## 왜 터미널을 띄우나

창이 곧 연결이기 때문이다. **창을 닫으면 터널이 끊기고 서버 쪽 뷰어도
꺼진다.** 창 없이 뒤에서 돌리면 끄는 방법을 따로 만들어야 하고, 끄는 걸
잊으면 터널이 며칠씩 열려 있게 된다. 윈도우 판도 같은 이유로 창을 쓴다.

## 왜 스크립트를 안에 넣나

`.app` 을 응용 프로그램 폴더로 옮겨도 혼자 돌아야 한다. 저장소 경로를
가리키게 해 두면 저장소를 옮기거나 지운 날 조용히 죽는다.

스크립트를 고쳤으면 이걸 다시 돌려서 앱을 새로 만들면 된다.

## 돌리는 법

    python3 tools/make_dbview_app.py                 # dist/ 에 만든다
    python3 tools/make_dbview_app.py --install       # 응용 프로그램에 놓는다

서명은 안 한다. 내가 내 맥에서 만든 것이라 격리 딱지가 안 붙고,
Gatekeeper 도 묻지 않는다. 남에게 보낼 것이 아니다.
"""
import argparse
import io
import os
import plistlib
import shutil
import stat
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "deploy", "dbview-mac.sh")
APP_NAME = "포스크탑 관리"
# 실행 파일 이름은 ASCII 로 둔다. 한글은 NFC/NFD 가 갈려서 도구마다
# 다른 이름으로 보인다 (게임 앱에서 codesign 이 그것 때문에 깨졌다).
EXEC_NAME = "poket-admin"
BUNDLE_ID = "com.poketdesktop.admin"

LAUNCHER = '''#!/bin/bash
# 터미널을 열고 그 안에서 스크립트를 돌린다. 창이 곧 연결이다.
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/dbview-mac.sh"

if [ ! -f "$SCRIPT" ]; then
  osascript -e 'display alert "포스크탑 관리" message "앱이 깨졌습니다. tools/make_dbview_app.py 로 다시 만드세요." as critical'
  exit 1
fi

# 경로에 공백이 있어서(응용 프로그램 폴더) 반드시 따옴표로 감싼다.
# AppleScript 문자열 안에서는 \\ 와 " 를 escape 해야 한다.
esc=${SCRIPT//\\\\/\\\\\\\\}
esc=${esc//\\"/\\\\\\"}
osascript >/dev/null 2>&1 <<OSA
tell application "Terminal"
  activate
  do script "clear; bash \\"$esc\\"; exit"
end tell
OSA
'''


def build(dest_dir):
    if not os.path.exists(SRC):
        sys.stderr.write("스크립트가 없습니다: %s\n" % SRC)
        return None

    app = os.path.join(dest_dir, APP_NAME + ".app")
    if os.path.isdir(app):
        shutil.rmtree(app)
    macos = os.path.join(app, "Contents", "MacOS")
    res = os.path.join(app, "Contents", "Resources")
    os.makedirs(macos)
    os.makedirs(res)

    # 알맹이 - 진짜 일을 하는 스크립트
    shutil.copy2(SRC, os.path.join(macos, "dbview-mac.sh"))

    # 껍데기 - 터미널을 여는 것뿐
    launcher = os.path.join(macos, EXEC_NAME)
    with io.open(launcher, "w", encoding="utf-8", newline="\n") as f:
        f.write(LAUNCHER)
    for p in (launcher, os.path.join(macos, "dbview-mac.sh")):
        os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP
                 | stat.S_IXOTH)

    info = {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleExecutable": EXEC_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleVersion": "1.0",
        "CFBundleShortVersionString": "1.0",
        "CFBundlePackageType": "APPL",
        "LSMinimumSystemVersion": "11.0",
        # Dock 에 남지 않는다. 터미널을 띄우고 나면 할 일이 없다.
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
    }

    icns = os.path.join(ROOT, "build", "icon.icns")
    if os.path.exists(icns):
        shutil.copy2(icns, os.path.join(res, "icon.icns"))
        info["CFBundleIconFile"] = "icon"
    else:
        sys.stderr.write("  (아이콘 없음 - tools/build_app.py 를 먼저 돌리면"
                         " 생깁니다. 없어도 동작합니다.)\n")

    with open(os.path.join(app, "Contents", "Info.plist"), "wb") as f:
        plistlib.dump(info, f)

    # 파인더가 아이콘·이름을 다시 읽게 한다. 안 하면 옛 아이콘이 남는다.
    subprocess.run(["touch", app], check=False)
    return app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"))
    ap.add_argument("--install", action="store_true",
                    help="~/Applications 에 놓는다")
    a = ap.parse_args()

    if sys.platform != "darwin":
        sys.stderr.write("맥에서만 만듭니다.\n")
        return 1

    out = os.path.expanduser("~/Applications") if a.install else a.out
    if not os.path.isdir(out):
        os.makedirs(out)

    app = build(out)
    if not app:
        return 1
    print("  만들었습니다: %s" % app)
    if a.install:
        print("  런치패드나 응용 프로그램 폴더에서 두 번 누르세요.")
    else:
        print("  두 번 눌러 열거나, 응용 프로그램 폴더로 끌어다 놓으세요.")
        print("  (또는 python3 tools/make_dbview_app.py --install)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
