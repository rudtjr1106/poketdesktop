# -*- coding: utf-8 -*-
"""클라이언트를 맥 앱 번들(.app)로 묶는다.

    python tools/build_app.py

결과: dist/포스크탑.app  와  dist/poketdesktop-vX.Y.Z-mac.dmg

**크로스 빌드는 안 된다.** 맥용 .app 은 맥에서만 만들어진다.
윈도우용은 tools/build_exe.py 가 따로 만든다 - 한 파일에 if 를 치면
버전 리소스·ico·exe 후처리가 전부 갈라져서 윈도우 쪽이 위험해진다.

## 윈도우 쪽과 다른 것

  · `--onefile` 을 안 쓴다. 맥에서 배포하는 단위는 파일 하나가 아니라
    **번들 폴더**다. `--windowed` 가 그 번들을 만들어 준다.
  · 아이콘이 .ico 가 아니라 .icns 다. iconutil 로 만든다.
  · **`.zip` 이 아니라 `.dmg` 로 낸다.** 맥에서 익숙한 형태이기도 하지만,
    그보다 중요한 이유가 있다 - 윈도우 클라이언트의 자동 업데이트가
    릴리스 자산에서 **`.zip` 으로 끝나는 첫 번째**를 운영체제도 안 보고
    집는다(`updater.check`). 같은 릴리스에 맥 zip 을 같이 올리면, 옛
    버전을 쓰던 윈도우 사용자가 그걸 받아서 "실행 파일을 찾지 못했습니다"
    로 끝날 수 있다. 이미 나가 있는 클라이언트는 고칠 수 없으니, **자산
    이름이 .zip 이 아니게** 두는 것이 확실하다.
  · dmg 안에는 `/Applications` 로 가는 바로가기를 같이 넣는다. 받는 사람이
    끌어다 놓기만 하면 된다.
  · pystray 를 안 쓰므로 그 hidden-import 도 없다. 대신 pyobjc 가
    필요하다.

## 서명 — 임시 서명까지만 한다

애플 실리콘에서는 **서명이 아예 없는 실행 파일은 실행 자체가 막힌다.**
그래서 임시 서명(ad-hoc)은 반드시 붙어 있어야 하고, PyInstaller 가
만들면서 붙여 준다.

개발자 서명(연 $99)과 공증(notarization)은 안 한다.

**그래서 받는 사람은 이 앱을 그냥 못 연다.** 인터넷에서 받은 파일에는
맥이 격리 표시를 붙이는데, 개발자 서명이 없으면 이렇게 막는다.

    "포스크탑"은(는) 손상되었기 때문에 열 수 없습니다.

**"확인되지 않은 개발자" 경고가 아니라 아예 막는 것이라, 우클릭 > 열기
로도 안 넘어간다.** 받는 사람이 한 줄을 쳐야 한다.

    xattr -dr com.apple.quarantine /Applications/포스크탑.app

직접 만든 판을 그 자리에서 실행할 때는 격리 표시가 없어서 잘 된다 -
그래서 만드는 쪽에서는 이 문제가 안 보인다. 실제로 받아서 열어 본
사람에게서 알았다. 릴리스 노트와 리드미에 적어 두었다.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from common.version import VERSION            # noqa: E402

# 번들 이름은 사람이 보는 이름이라 한글로 둔다. zip 파일 이름은 ASCII 다 -
# GitHub 릴리스가 첨부파일 이름의 한글을 지워 버린다.
APP_NAME = "포스크탑"
# 자산 이름. **.zip 으로 끝내지 마라** - 윈도우 자동 업데이트가 집어간다
# (make_dmg 의 설명을 보라).
ZIP_NAME = "poketdesktop-v%s-mac" % VERSION
BUNDLE_ID = "com.poketdesktop.app"
ENTRY = os.path.join(ROOT, "client", "run.pyw")
ICONSET = os.path.join(ROOT, "build", "poket.iconset")
ICNS = os.path.join(ROOT, "build", "icon.icns")

# 맥 아이콘은 크기별로 여러 장을 넣는다. @2x 는 레티나용이다.
ICON_SIZES = [(16, 1), (16, 2), (32, 1), (32, 2), (128, 1), (128, 2),
              (256, 1), (256, 2), (512, 1), (512, 2)]


def make_icns():
    """.icns 를 만든다. 트레이·윈도우 exe 와 같은 그림이다."""
    sys.path.insert(0, os.path.join(ROOT, "client"))
    from poketdesktop import appicon

    shutil.rmtree(ICONSET, ignore_errors=True)
    os.makedirs(ICONSET, exist_ok=True)
    for base, scale in ICON_SIZES:
        name = "icon_%dx%d%s.png" % (base, base, "@2x" if scale == 2 else "")
        appicon.make(base * scale).save(os.path.join(ICONSET, name))
    r = subprocess.run(["iconutil", "-c", "icns", ICONSET, "-o", ICNS],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("  iconutil 실패: %s" % (r.stderr or "").strip())
        return None
    print("  아이콘: %s" % ICNS)
    return ICNS


def set_info_plist(app_path):
    """번들 정보를 손본다.

    제일 중요한 것은 `LSUIElement` 다. 이게 있어야 Dock 과 앱 전환기
    (Cmd+Tab)에 안 뜬다 — 켜 두고 잊어버리는 프로그램이라 Dock 한 칸을
    계속 차지하면 안 된다. 프로그램 안에서도 같은 일을 하지만
    (`platform_mac.hide_from_dock`), 그건 창이 뜬 **뒤**라서 켤 때 Dock
    아이콘이 한 번 번쩍인다. 여기 적어 두면 처음부터 안 뜬다.
    """
    import plistlib

    path = os.path.join(app_path, "Contents", "Info.plist")
    try:
        with open(path, "rb") as f:
            d = plistlib.load(f)
    except Exception as e:                                  # noqa: BLE001
        print("  Info.plist 를 못 읽었습니다: %s" % e)
        return
    d["LSUIElement"] = True                 # Dock 에 안 뜬다
    d["CFBundleName"] = APP_NAME
    d["CFBundleDisplayName"] = APP_NAME
    d["CFBundleShortVersionString"] = VERSION
    d["CFBundleVersion"] = VERSION
    d["NSHumanReadableCopyright"] = (
        "Fan project. Pokemon is (c) Nintendo / Creatures / GAME FREAK.")
    # 서버와 https 로만 이야기한다. 예외를 열어 둘 이유가 없다.
    d["NSHighResolutionCapable"] = True
    try:
        with open(path, "wb") as f:
            plistlib.dump(d, f)
    except Exception as e:                                  # noqa: BLE001
        print("  Info.plist 를 못 썼습니다: %s" % e)
        return
    print("  Info.plist: LSUIElement (Dock 에 안 뜸), 버전 %s" % VERSION)


def make_dmg(app_path, dist):
    """받는 사람이 열어서 끌어다 놓는 dmg 하나.

    안에 `/Applications` 바로가기를 같이 넣어서 끌어다 놓기만 하면 되게
    한다. 압축(UDZO)까지 hdiutil 이 한다.
    """
    stage = os.path.join(ROOT, "build", "dmg")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage, exist_ok=True)
    # **ditto 로 복사한다.** cp -R 이나 shutil 은 번들 안의 심볼릭 링크를
    # 실체로 복제해서 크기가 몇 배가 되고 프레임워크가 깨진다.
    r = subprocess.run(["ditto", app_path,
                        os.path.join(stage, os.path.basename(app_path))],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("  번들을 옮기지 못했습니다: %s" % (r.stderr or "").strip())
        return None
    os.symlink("/Applications", os.path.join(stage, "Applications"))

    dmg_path = os.path.join(dist, ZIP_NAME + ".dmg")
    if os.path.exists(dmg_path):
        os.remove(dmg_path)
    r = subprocess.run(["hdiutil", "create", "-quiet",
                        "-volname", APP_NAME, "-srcfolder", stage,
                        "-ov", "-format", "UDZO", dmg_path],
                       capture_output=True, text=True)
    shutil.rmtree(stage, ignore_errors=True)
    if r.returncode != 0:
        print("  dmg 를 못 만들었습니다: %s" % (r.stderr or "").strip())
        return None
    return dmg_path


def check_signature(app_path):
    """서명이 붙어 있는지 본다. 없으면 아예 안 뜬다.

    애플 실리콘에서는 **서명이 아예 없는 실행 파일은 실행 자체가 막힌다.**
    개발자 등록이 없어도 임시 서명(ad-hoc)만 붙어 있으면 뜬다 - 처음
    한 번 우클릭 > 열기 로 넘기면 된다. PyInstaller 가 만들면서 붙여
    준다.

    빌드 로그에 `Error while signing the bundle ... --deep` 이 보여도
    대개 괜찮다. 그건 번들 **바깥쪽**을 한 번 더 서명하려다 실패한
    것이고, 안쪽 실행 파일에는 이미 붙어 있다. (`codesign --deep` 은
    이렇게 겹겹이 든 번들에서 재귀가 너무 깊어져 스스로 죽는 일이 있다.)
    """
    r = subprocess.run(["codesign", "-dv", app_path],
                       capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    if "Signature=adhoc" in out or "Authority=" in out:
        # 붙어 있다고 봉인까지 맞는 것은 아니다. 있는 그대로 알려준다.
        v = subprocess.run(["codesign", "--verify", "--strict", app_path],
                           capture_output=True, text=True)
        if v.returncode == 0:
            print("  서명: 임시 서명(ad-hoc), 검증 통과")
        else:
            print("  서명: 임시 서명(ad-hoc) — 다만 검증은 실패한다")
            print("        %s" % (v.stderr or "").strip()[:90])
            print("        공증이 없으면 어차피 받는 쪽에서 격리를 떼야 하므로")
            print("        지금은 그대로 낸다. 릴리스 노트에 적어 두었다.")
        print("")
        print("  받는 사람은 끌어다 놓은 뒤 이 한 줄이 필요하다:")
        print("    xattr -dr com.apple.quarantine /Applications/%s.app"
              % APP_NAME)
        return True
    print("")
    print("  ** 서명이 안 붙었습니다. 애플 실리콘에서는 안 뜰 수 있습니다. **")
    print("     이렇게 해 보세요:")
    print("       codesign --force --sign - '%s'" % app_path)
    print("     (--deep 은 쓰지 마세요. 재귀가 깊어져 codesign 이 죽습니다.)")
    return False


def build():
    if sys.platform != "darwin":
        print("맥에서만 됩니다. 윈도우용은 tools/build_exe.py 입니다.")
        return 1
    try:
        import PyInstaller                                  # noqa: F401
    except ImportError:
        print("PyInstaller 가 없습니다.  pip install pyinstaller")
        return 1
    try:
        import objc                                         # noqa: F401
    except ImportError:
        print("pyobjc 가 없습니다. 이게 없으면 투명 배경도 메뉴 막대 "
              "아이콘도 안 됩니다.")
        print("  pip install pyobjc-framework-Cocoa pyobjc-framework-Quartz")
        return 1

    print("포스크탑 v%s 맥 번들 빌드" % VERSION)
    icon = make_icns()
    if not icon:
        return 1

    shutil.rmtree(os.path.join(ROOT, "build", "pyi"), ignore_errors=True)
    dist = os.path.join(ROOT, "dist")
    os.makedirs(dist, exist_ok=True)
    app_path = os.path.join(dist, APP_NAME + ".app")
    shutil.rmtree(app_path, ignore_errors=True)
    shutil.rmtree(os.path.join(dist, APP_NAME), ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        # 맥에서 배포 단위는 번들이다. --onefile 은 쓰지 않는다.
        "--windowed",
        "--name", APP_NAME,
        "--icon", icon,
        "--osx-bundle-identifier", BUNDLE_ID,
        "--distpath", dist,
        "--workpath", os.path.join(ROOT, "build", "pyi"),
        "--specpath", os.path.join(ROOT, "build"),
        # common 패키지를 찾을 수 있게
        "--paths", ROOT,
        "--paths", os.path.join(ROOT, "client"),
        "--hidden-import", "common.pokelogic",
        "--hidden-import", "common.version",
        "--hidden-import", "PIL._tkinter_finder",
        # 인증서 꾸러미. 없으면 업데이트 확인이 SSL 에서 조용히 실패한다.
        "--hidden-import", "certifi",
        "--collect-data", "certifi",
        # 맥 전용. 이것들이 빠지면 창이 투명해지지 않고 메뉴 막대에
        # 아이콘이 안 올라간다 - 둘 다 없으면 게임을 조작할 수 없다.
        "--hidden-import", "poketdesktop.platform_mac",
        "--hidden-import", "poketdesktop.tray_mac",
        "--hidden-import", "AppKit",
        "--hidden-import", "Foundation",
        "--hidden-import", "Quartz",
        "--hidden-import", "objc",
        # 안 쓰는 무거운 것들은 뺀다
        "--exclude-module", "numpy",
        "--exclude-module", "scipy",
        "--exclude-module", "matplotlib",
        "--exclude-module", "pandas",
        "--exclude-module", "PyQt5",
        "--exclude-module", "PySide2",
        "--exclude-module", "test",
        # 맥에서는 pystray 를 안 쓴다 (tray_mac 을 보라).
        "--exclude-module", "pystray",
        ENTRY,
    ]
    print("  PyInstaller 실행...")
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        print("  실패")
        return 1
    if not os.path.isdir(app_path):
        print("  .app 이 안 만들어졌습니다: %s" % app_path)
        return 1

    exe = os.path.join(app_path, "Contents", "MacOS", APP_NAME)
    if not os.path.exists(exe):
        print("  번들 안에 실행 파일이 없습니다: %s" % exe)
        return 1

    set_info_plist(app_path)
    check_signature(app_path)

    dmg_path = make_dmg(app_path, dist)
    if not dmg_path:
        return 1

    mb = os.path.getsize(dmg_path) / 1048576.0
    print("")
    print("  완성: %s" % app_path)
    print("        %s  (%.1f MB)" % (dmg_path, mb))
    return 0


if __name__ == "__main__":
    sys.exit(build())
