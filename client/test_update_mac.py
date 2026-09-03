# -*- coding: utf-8 -*-
"""맥 자동 업데이트 검사.

    python client/test_update_mac.py

창을 안 만든다. dmg 를 하나 만들어 놓고 꺼내기와 갈아끼우기를 돌려 본다.

## 여기서 지키려는 것

**앱이 사라지면 안 된다.** 갈아끼우기는 돌고 있는 번들을 통째로 바꾸는
일이라, 중간에 실패하면 설치된 것이 없어질 수 있다. 실패하면 반드시
있던 것이 되돌아와야 한다.

그리고 **자산을 운영체제별로 골라야 한다.** 예전 코드는 `.zip` 으로
끝나는 첫 번째를 그냥 집었다. 한 릴리스에 윈도우 zip 과 맥 파일을 같이
올리므로, 잘못 고르면 서로 남의 것을 받는다.
"""
import os
import shutil
import subprocess
import sys
import tempfile

os.environ.setdefault("POKET_HOME",
                      os.path.join(tempfile.gettempdir(), "poket-test-update"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop import updater as U                      # noqa: E402

OK = FAIL = 0
WORK = os.path.join(tempfile.gettempdir(), "poket-test-update-work")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def section(t):
    print("-- %s" % t)


def make_dmg(marker):
    """작은 .app 하나가 든 dmg 를 만든다."""
    stage = os.path.join(WORK, "src")
    shutil.rmtree(stage, ignore_errors=True)
    app = os.path.join(stage, "포스크탑.app", "Contents", "MacOS")
    os.makedirs(app)
    with open(os.path.join(app, "포스크탑"), "w") as f:
        f.write("#!/bin/sh\nexit 0\n")
    os.chmod(os.path.join(app, "포스크탑"), 0o755)
    with open(os.path.join(stage, "포스크탑.app", marker), "w") as f:
        f.write(marker)
    # 심볼릭 링크가 살아남는지 볼 수 있게 하나 넣는다
    os.symlink("MacOS/포스크탑",
               os.path.join(stage, "포스크탑.app", "Contents", "link"))
    dmg = os.path.join(WORK, "new.dmg")
    if os.path.exists(dmg):
        os.remove(dmg)
    r = subprocess.run(["hdiutil", "create", "-quiet", "-volname", "포스크탑",
                        "-srcfolder", stage, "-ov", "-format", "UDZO", dmg],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return dmg


def t_pick_asset():
    section("자산을 운영체제별로 고른다")
    A = U.ALLOW_PREFIX + "v1.0.9/"
    assets = [{"name": "poketdesktop-v1.0.9-mac.dmg",
               "browser_download_url": A + "a.dmg"},
              {"name": "poketdesktop-v1.0.9.zip",
               "browser_download_url": A + "b.zip"}]
    real = U.IS_MAC
    try:
        U.IS_MAC = True
        chk("맥은 dmg 를 고른다",
            U.pick_asset(assets)["name"].endswith("-mac.dmg"))
        U.IS_MAC = False
        got = U.pick_asset(assets)["name"]
        chk("윈도우는 zip 을 고른다", got.endswith(".zip"), got)
        chk("윈도우가 맥 것을 안 집는다", "-mac" not in got, got)
        # 맥 것만 있을 때 윈도우는 아무것도 안 집어야 한다
        chk("맥 것뿐이면 윈도우는 안 받는다",
            U.pick_asset([assets[0]]) is None)
        U.IS_MAC = True
        chk("윈도우 것뿐이면 맥은 안 받는다",
            U.pick_asset([assets[1]]) is None)
        # 우리 릴리스가 아닌 주소는 안 받는다
        chk("남의 주소는 안 받는다",
            U.pick_asset([{"name": "x.dmg",
                           "browser_download_url": "https://evil/x.dmg"}])
            is None)
    finally:
        U.IS_MAC = real


def t_supported():
    section("어느 운영체제에서 하는가")
    chk("맥에서 한다", U.supported() is True)


def t_app_bundle():
    section("설치된 번들 자리 찾기")
    real = U.exe_path
    try:
        U.exe_path = lambda: "/Applications/포스크탑.app/Contents/MacOS/포스크탑"
        chk("번들 경로를 찾는다",
            U.app_bundle() == "/Applications/포스크탑.app", U.app_bundle())
        U.exe_path = lambda: "/usr/bin/python3"
        chk("번들이 아니면 None", U.app_bundle() is None, U.app_bundle())
    finally:
        U.exe_path = real


def t_extract():
    section("dmg 에서 .app 을 꺼낸다")
    dmg = make_dmg("새판")
    chk("시험용 dmg 를 만들었다", dmg is not None)
    if not dmg:
        return None
    seen = []
    out = U._mac_extract(dmg, "9.9.9", lambda i, t: seen.append((i, t)))
    chk("꺼낸 것이 .app 이다", out.endswith(".app") and os.path.isdir(out), out)
    chk("실행 파일이 있다",
        os.path.exists(os.path.join(out, "Contents", "MacOS", "포스크탑")))
    chk("실행 권한이 살아 있다",
        os.access(os.path.join(out, "Contents", "MacOS", "포스크탑"), os.X_OK))
    chk("심볼릭 링크가 살아 있다",
        os.path.islink(os.path.join(out, "Contents", "link")))
    chk("진행 상황을 알려준다", len(seen) >= 2, seen)
    chk("붙여 둔 것을 떼어냈다",
        not any("포스크탑" in v for v in os.listdir("/Volumes")),
        os.listdir("/Volumes"))
    return out


def swap(new_app, app, extra=None):
    """갈아끼우는 스크립트를 그대로 돌린다. (이미 끝난 PID 를 준다)"""
    sh = os.path.join(WORK, "swap.sh")
    with open(sh, "w") as f:
        f.write(U._SWAP)
    os.chmod(sh, 0o755)
    p = subprocess.Popen(["/bin/sh", "-c", "exit 0"])
    p.wait()
    env = dict(os.environ)
    if extra:
        env.update(extra)
    return subprocess.run(["/bin/sh", sh, str(p.pid), new_app, app],
                          capture_output=True, text=True, timeout=120, env=env)


def t_swap(new_app):
    section("갈아끼우기")
    app = os.path.join(WORK, "설치자리", "포스크탑.app")
    shutil.rmtree(os.path.dirname(app), ignore_errors=True)
    os.makedirs(app)
    with open(os.path.join(app, "옛판"), "w") as f:
        f.write("old")
    r = swap(new_app, app)
    chk("스크립트가 성공한다", r.returncode == 0,
        "rc=%s %s" % (r.returncode, (r.stderr or "").strip()[:120]))
    chk("새 판으로 바뀌었다",
        os.path.isdir(os.path.join(app, "Contents", "MacOS")))
    chk("옛 흔적이 안 남는다", not os.path.exists(os.path.join(app, "옛판")))
    left = [f for f in os.listdir(os.path.dirname(app))
            if ".old-" in f or ".new-" in f]
    chk("찌꺼기를 안 남긴다", not left, left)


def t_swap_rollback():
    section("갈아끼우다 실패하면 있던 것이 돌아온다")
    app = os.path.join(WORK, "되돌리기", "포스크탑.app")
    shutil.rmtree(os.path.dirname(app), ignore_errors=True)
    os.makedirs(app)
    with open(os.path.join(app, "옛판"), "w") as f:
        f.write("old")
    # 있지도 않은 새 판을 준다 -> ditto 가 실패한다
    r = swap(os.path.join(WORK, "없는앱.app"), app)
    chk("실패를 알린다", r.returncode != 0, r.returncode)
    chk("**앱이 그대로 있다**", os.path.isdir(app), app)
    chk("옛 판이 그대로다", os.path.exists(os.path.join(app, "옛판")))
    left = [f for f in os.listdir(os.path.dirname(app))
            if ".old-" in f or ".new-" in f]
    chk("찌꺼기를 안 남긴다", not left, left)


def t_cleanup_noop():
    section("맥에는 치울 지난 폴더가 없다")
    chk("cleanup_old 가 아무것도 안 한다", U.cleanup_old() == 0)


def _detach_leftovers():
    """앞선 검사가 붙여 둔 것이 남아 있으면 떼어낸다.

    붙어 있는 채로 폴더를 지우려 하면 안 지워지고, 다음 검사가 거기서
    막힌다.
    """
    try:
        out = subprocess.run(["mount"], capture_output=True, text=True).stdout
    except Exception:                                       # noqa: BLE001
        return
    for line in out.splitlines():
        if "poket-test-update" not in line:
            continue
        bits = line.split(" on ")
        if len(bits) < 2:
            continue
        mnt = bits[1].split(" (")[0]
        subprocess.run(["hdiutil", "detach", mnt, "-force", "-quiet"],
                       capture_output=True)


def main():
    if sys.platform != "darwin":
        print("맥에서만 하는 검사입니다.")
        return 0
    _detach_leftovers()
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    try:
        t_supported()
        t_pick_asset()
        t_app_bundle()
        new_app = t_extract()
        if new_app:
            t_swap(new_app)
        t_swap_rollback()
        t_cleanup_noop()
    finally:
        _detach_leftovers()
        shutil.rmtree(WORK, ignore_errors=True)
    print()
    print("=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
