# -*- coding: utf-8 -*-
"""맥 자동 시작(LaunchAgent) 검사.

    python client/test_autostart_mac.py

**진짜 plist 는 절대 건드리지 않는다.** 레이블과 파일 경로를 검사용으로
바꿔치기하고, 끝나면 지운다. 로그도 마찬가지라 POKET_HOME 을 import
보다 먼저 잡는다.

마지막 검사 하나만 진짜 ~/Library/LaunchAgents 를 쓴다 - launchd 가
우리가 쓴 plist 를 실제로 받아들이는지 보려면 그 자리여야 한다. 레이블에
'test' 가 들어가고, 하는 일은 /usr/bin/true 이며, 끝나면 반드시 지운다.
"""
import os
import plistlib
import subprocess
import sys
import tempfile

os.environ["POKET_HOME"] = os.path.join(tempfile.gettempdir(),
                                        "poket-test-autostart-mac")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop import autostart                         # noqa: E402

OK = FAIL = 0

REAL_PLIST = autostart.PLIST
REAL_LABEL = autostart.LABEL

# **바꿔치기는 여기서 한다.** main() 안에서 하면, 디버깅한다고 t_ 하나만
# 직접 불렀을 때 진짜 자리에 쓴다.
SCRATCH_DIR = os.path.join(tempfile.gettempdir(), "poket-test-launchagents")
autostart.LABEL = "com.poketdesktop.test.autostart"
autostart.PLIST = os.path.join(SCRATCH_DIR, autostart.LABEL + ".plist")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def section(t):
    print("-- %s" % t)


def frozen(on, exe="/Applications/포스크탑.app/Contents/MacOS/poketdesktop"):
    """빌드된 .app 인 척한다."""
    if on:
        sys.frozen = True
        autostart._target = lambda: [exe]
    else:
        if hasattr(sys, "frozen"):
            del sys.frozen
        autostart._target = REAL_TARGET


REAL_TARGET = autostart._target


def read_plist():
    with open(autostart.PLIST, "rb") as f:
        return plistlib.load(f)


def clean():
    for p in (autostart.PLIST, autostart.PLIST + ".tmp"):
        try:
            os.remove(p)
        except OSError:
            pass


# ---------------------------------------------------------------- 검사
def t_supported():
    section("맥에서도 자동 시작을 지원한다고 말한다")
    chk("supported()", autostart.supported() is True)
    chk("state 가 unsupported 가 아니다", autostart.state()[0] != "unsupported",
        autostart.state())


def t_command():
    section("등록할 명령줄")
    frozen(True)
    try:
        cmd = autostart.command()
        chk("--autostart 가 붙는다", autostart.FLAG in cmd, cmd)
        chk("실행 파일이 앞에 온다", "/Applications" in cmd.split()[0], cmd)
        # 경로에 공백이나 한글이 있으면 shlex 가 따옴표를 친다. plist 는
        # 배열이라 따옴표가 필요 없지만, 이 문자열은 sync() 가 "지금 등록된
        # 것과 같은가" 를 견주는 데 쓰이므로 양쪽이 같은 방식이면 된다.
        chk("공백과 한글을 안전하게 감싼다",
            "'" in cmd or '"' in cmd or "\\" in cmd, cmd)
    finally:
        frozen(False)


def t_plist_shape():
    section("써 놓은 plist 의 모양")
    clean()
    frozen(True)
    try:
        ok, _msg = autostart.enable()
        chk("등록에 성공한다", ok)
        d = read_plist()
        chk("Label", d.get("Label") == autostart.LABEL, d.get("Label"))
        chk("RunAtLoad 가 켜져 있다", d.get("RunAtLoad") is True)
        # KeepAlive 가 켜져 있으면 사용자가 껐을 때 launchd 가 되살린다.
        chk("KeepAlive 는 꺼져 있다", d.get("KeepAlive") is False)
        chk("화면 있는 프로그램으로 알린다",
            d.get("ProcessType") == "Interactive", d.get("ProcessType"))
        args = d.get("ProgramArguments") or []
        chk("인자로 --autostart 를 넘긴다", autostart.FLAG in args, args)
        chk("실행 파일을 직접 띄운다 (open -a 를 안 쓴다)",
            args and "open" not in os.path.basename(args[0]), args)
        env = d.get("EnvironmentVariables") or {}
        chk("환경변수 표식도 같이 넣는다", env.get(autostart.ENVKEY) == "1", env)
        chk("반쪽짜리 임시 파일을 안 남긴다",
            not os.path.exists(autostart.PLIST + ".tmp"))
    finally:
        frozen(False)
        clean()


def t_roundtrip():
    section("켜고 끄기")
    clean()
    frozen(True)
    try:
        chk("처음에는 등록이 없다", autostart.registered() is None)
        autostart.enable()
        chk("켜면 등록이 보인다", autostart.registered() is not None)
        chk("등록된 것이 command() 와 같다",
            autostart.registered() == autostart.command(),
            "%r != %r" % (autostart.registered(), autostart.command()))
        chk("state 가 on", autostart.state()[0] == "on", autostart.state())
        ok, _ = autostart.disable()
        chk("끄면 성공한다", ok)
        chk("끄면 등록이 사라진다", autostart.registered() is None)
        chk("state 가 off", autostart.state()[0] == "off")
        ok2, _ = autostart.disable()
        chk("없는 것을 또 꺼도 성공이다", ok2)
    finally:
        frozen(False)
        clean()


def t_no_bootout():
    """**제일 중요한 검사.**

    `launchctl bootout` 은 그 잡의 프로세스에 SIGTERM 을 보낸다. 자동
    시작으로 켜진 우리가 바로 그 잡이므로, 끄거나 경로를 다시 쓸 때
    bootout 을 부르면 **그 자리에서 자기 자신이 죽는다.** 설정에서 체크를
    끄는 순간 앱이 사라지고, 로그아웃도 탈퇴도 중간에 끊긴다.
    """
    section("끌 때 launchctl 을 부르지 않는다 (자기 자신을 죽이지 않는다)")
    clean()
    frozen(True)
    called = []
    real_run = subprocess.run

    def spy(args, *a, **kw):
        called.append(list(args) if isinstance(args, (list, tuple)) else [args])
        return real_run(["/usr/bin/true"], *a, **kw)

    autostart.subprocess.run = spy
    try:
        autostart.enable()
        autostart.disable()
        bad = [c for c in called
               if any("bootout" in str(x) or "bootstrap" in str(x)
                      or "unload" in str(x) or "load" in str(x) for x in c)]
        chk("bootout/bootstrap/load 를 안 부른다", not bad, bad)
    finally:
        autostart.subprocess.run = real_run
        frozen(False)
        clean()


def t_started_flag():
    section("부팅으로 켜졌는지 알아본다")
    chk("인자에 있으면 참", autostart.started_by_autostart([autostart.FLAG]))
    chk("없으면 거짓", not autostart.started_by_autostart([]))
    old = os.environ.get(autostart.ENVKEY)
    os.environ[autostart.ENVKEY] = "1"
    try:
        chk("환경변수 표식으로도 알아본다", autostart.started_by_autostart([]))
    finally:
        if old is None:
            os.environ.pop(autostart.ENVKEY, None)
        else:
            os.environ[autostart.ENVKEY] = old
    old2 = os.environ.get("XPC_SERVICE_NAME")
    os.environ["XPC_SERVICE_NAME"] = autostart.LABEL
    try:
        chk("launchd 가 넣어주는 이름으로도 알아본다",
            autostart.started_by_autostart([]))
    finally:
        if old2 is None:
            os.environ.pop("XPC_SERVICE_NAME", None)
        else:
            os.environ["XPC_SERVICE_NAME"] = old2


def t_sync_dev():
    section("개발 중(파이썬)에는 sync 가 아무것도 안 한다")
    clean()
    frozen(False)
    autostart.sync(True)
    chk("소스로 돌릴 때는 등록하지 않는다", autostart.registered() is None)
    clean()


def t_sync_moves():
    section("앱을 옮기면 경로를 다시 쓴다")
    clean()
    frozen(True, "/Users/me/Downloads/포스크탑.app/Contents/MacOS/poketdesktop")
    try:
        autostart.enable()
        first = autostart.registered()
        frozen(True, "/Applications/포스크탑.app/Contents/MacOS/poketdesktop")
        autostart.sync(True)
        chk("옮긴 자리로 바뀐다", autostart.registered() != first,
            autostart.registered())
        chk("새 경로가 들어 있다", "/Applications" in (autostart.registered() or ""))
        autostart.sync(False)
        chk("꺼 두었으면 등록을 지운다", autostart.registered() is None)
    finally:
        frozen(False)
        clean()


def t_launchd_accepts():
    """launchd 가 우리가 쓴 plist 를 실제로 받아들이는가.

    이것만 진짜 ~/Library/LaunchAgents 를 쓴다. 레이블에 test 가 들어가고
    하는 일은 /usr/bin/true 다. 끝나면 반드시 내리고 지운다.
    """
    section("launchd 가 이 plist 를 받아들인다")
    label = "com.poketdesktop.test.accepts"
    path = os.path.expanduser("~/Library/LaunchAgents/%s.plist" % label)
    if "test" not in label:                      # 안전장치
        chk("검사용 레이블이 아니다", False)
        return
    dom = "gui/%d" % os.getuid()
    saved_label, saved_plist = autostart.LABEL, autostart.PLIST
    autostart.LABEL, autostart.PLIST = label, path
    frozen(True, "/usr/bin/true")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        autostart.enable()
        r = subprocess.run(["/bin/launchctl", "bootstrap", dom, path],
                           capture_output=True, text=True)
        chk("bootstrap 이 받아들인다", r.returncode == 0,
            "rc=%s %s" % (r.returncode, (r.stdout + r.stderr).strip()))
        p = subprocess.run(["/bin/launchctl", "print", "%s/%s" % (dom, label)],
                           capture_output=True, text=True)
        chk("등록된 잡으로 보인다", p.returncode == 0)
        chk("인자가 그대로 넘어간다", autostart.FLAG in (p.stdout or ""),
            "arguments 가 안 보인다")
        chk("환경변수 표식도 넘어간다", autostart.ENVKEY in (p.stdout or ""))
    finally:
        subprocess.run(["/bin/launchctl", "bootout", "%s/%s" % (dom, label)],
                       capture_output=True, text=True)
        try:
            os.remove(path)
        except OSError:
            pass
        frozen(False)
        autostart.LABEL, autostart.PLIST = saved_label, saved_plist
    chk("검사가 끝나면 아무것도 안 남는다", not os.path.exists(path))


def main():
    if sys.platform != "darwin":
        print("맥에서만 하는 검사입니다.")
        return 0
    if autostart.PLIST == REAL_PLIST or "test" not in autostart.LABEL:
        print("검사용 자리를 못 잡았습니다. 그만둡니다.")
        return 1

    before = os.path.exists(REAL_PLIST)
    os.makedirs(SCRATCH_DIR, exist_ok=True)

    for fn in (t_supported, t_command, t_plist_shape, t_roundtrip,
               t_no_bootout, t_started_flag, t_sync_dev, t_sync_moves,
               t_launchd_accepts):
        fn()

    after = os.path.exists(REAL_PLIST)
    chk("진짜 등록을 건드리지 않았다", before == after,
        "%s -> %s" % (before, after))

    print()
    print("=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
