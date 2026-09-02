# -*- coding: utf-8 -*-
"""자동 시작 등록 검사.

    python client/test_autostart.py

**진짜 Run 키는 절대 건드리지 않는다.** 카카오톡·원드라이브·도커가 들어
있는 그 키다. 검사용 가짜 자리(poketdesktop-test 아래)로 바꿔치기하고,
끝나면 지운다.

로그도 마찬가지다. POKET_HOME 을 먼저 잡아 두지 않으면 검사 한 번에
쓰던 설정과 로그인이 덮인다 - config 는 불러오는 순간 경로를 정하므로
import 보다 **먼저** 잡아야 한다.
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = os.path.join(tempfile.gettempdir(),
                                        "poket-test-autostart")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop import autostart                         # noqa: E402

OK = FAIL = 0

SCRATCH = r"Software\poketdesktop-test\Run"
SCRATCH_APPROVED = r"Software\poketdesktop-test\StartupApproved"
REAL_RUN = autostart.RUN_KEY
REAL_TARGET = autostart._target

# **바꿔치기는 여기서 한다.** main() 안에서 하면, 디버깅한다고 t_ 하나만
# 직접 불렀을 때(또는 나중에 pytest 로 옮겼을 때) 진짜 Run 키에 쓴다.
autostart.RUN_KEY = SCRATCH
autostart.APPROVED_KEY = SCRATCH_APPROVED
EXE_A = r"C:\p\game-v1.0.6.exe"
EXE_B = r"C:\p\game-v1.0.7.exe"
SPACED = r"C:\Program Files\포스크탑\game.exe"


def real_value():
    """진짜 Run 키에 들어 있는 우리 값. 없으면 None."""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REAL_RUN) as k:
            return winreg.QueryValueEx(k, autostart.VALUE)[0]
    except OSError:
        return None


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def wipe():
    import winreg
    for key in (SCRATCH, SCRATCH_APPROVED, r"Software\poketdesktop-test"):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
        except OSError:
            pass


def approve(first_byte):
    """작업 관리자가 남기는 기록을 흉내낸다 (12바이트)."""
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, SCRATCH_APPROVED, 0,
                            winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, autostart.VALUE, 0, winreg.REG_BINARY,
                          bytes([first_byte]) + bytes(11))


def target(*parts):
    autostart._target = lambda: list(parts)


def frozen(on):
    if on:
        sys.frozen = True
    elif hasattr(sys, "frozen"):
        del sys.frozen


# ---------------------------------------------------------------- 검사
def t_명령줄():
    target(SPACED)
    cmd = autostart.command()
    # 따옴표가 없으면 윈도우가 "C:\Program" 까지만 읽고 엉뚱한 것을 찾는다.
    chk("공백 있는 경로는 따옴표로 묶는다", cmd.startswith(chr(34) + "C:"), cmd)
    chk("경로가 그대로 들어간다", SPACED in cmd, cmd)
    chk("부팅 표시가 붙는다", cmd.endswith(autostart.FLAG), cmd)

    chk("부팅으로 켜진 것을 알아본다",
        autostart.started_by_autostart([autostart.FLAG]))
    chk("손으로 켠 것과 구분한다",
        not autostart.started_by_autostart([]) and
        not autostart.started_by_autostart(["--other"]))


def t_켜고_끄기():
    chk("처음엔 꺼져 있다", autostart.registered() is None
        and autostart.state()[0] == "off")

    ok, _ = autostart.enable()
    chk("켜면 등록된다", ok and autostart.registered() == autostart.command())
    chk("상태가 켜짐", autostart.state()[0] == "on")

    ok, _ = autostart.disable()
    chk("끄면 지워진다", ok and autostart.registered() is None)
    chk("상태가 꺼짐", autostart.state()[0] == "off")

    # 이미 꺼져 있는데 또 끄는 것은 실패가 아니다. 바라던 상태다.
    ok, _ = autostart.disable()
    chk("없는 것을 또 꺼도 괜찮다", ok)

    autostart.enable()
    autostart.enable()
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, SCRATCH) as k:
        chk("두 번 켜도 한 줄만 남는다", winreg.QueryInfoKey(k)[1] == 1)


def t_작업관리자():
    # 02 와 03 은 이 PC 에서 실제로 본 값이다 (카카오톡·원드라이브가 02,
    # 도커·엣지가 03). **06 과 07 은 실측이 아니라 "홀수면 꺼짐" 규칙에서
    # 따라온 것이다** - 구현과 같은 규칙을 되풀이하는 것뿐이라, 규칙 자체가
    # 틀렸다면 이 검사도 같이 틀린다. 그래서 모르는 값이 왔을 때 "꺼졌다"
    # 고 단정하지 않도록 해 두었다 (바로 아래 검사).
    for first, 막혔나 in ((0x02, False), (0x03, True),
                          (0x06, False), (0x07, True)):
        wipe()
        approve(first)
        chk("0x%02x -> %s" % (first, "꺼짐" if 막혔나 else "켜짐"),
            autostart.blocked() is 막혔나)

    wipe()
    chk("손댄 적 없으면 막힌 게 아니다", autostart.blocked() is False)
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, SCRATCH_APPROVED, 0,
                            winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, autostart.VALUE, 0, winreg.REG_BINARY, b"")
    # 잘 되고 있는 것을 "꺼져 있다" 고 말하는 쪽이 더 나쁘다.
    chk("형식이 이상하면 막혔다고 단정하지 않는다",
        autostart.blocked() is False)

    wipe()
    autostart.enable()
    approve(0x03)
    st, msg = autostart.state()
    chk("막혔으면 켜짐이라고 하지 않는다", st == "blocked", st)
    chk("무엇을 해야 하는지 말해 준다", "작업 관리자" in msg, msg)
    ok, msg = autostart.enable()
    chk("켤 때도 막힌 것을 알려 준다", ok and "작업 관리자" in msg, msg)
    # 사용자가 작업 관리자에서 내린 결정을 프로그램이 뒤집으면 안 된다.
    chk("막힌 것을 우리가 다시 켜지 않는다", autostart.blocked() is True)


def t_첫_설치에서_등록된다():
    """목표 그 자체다. 이게 없으면 sync 를 'cur 가 있을 때만 고쳐 쓴다'
    로 바꿔도 검사가 그대로 통과하고, 새로 설치한 PC 는 영영 등록되지
    않는다."""
    frozen(True)
    target(EXE_B)
    chk("아직 아무것도 없다", autostart.registered() is None)
    autostart.sync(True)
    chk("첫 설치에서 등록된다", autostart.registered() == autostart.command(),
        autostart.registered())
    frozen(False)


def t_끌_때_작업관리자_기록은_안_건드린다():
    """'우리 흔적은 우리가 치운다' 며 StartupApproved 까지 지우면, 사용자가
    작업 관리자에서 껐던 기록이 조용히 사라진다. 그 다음에 껐다 켜면 우리가
    사용자의 결정을 뒤집은 셈이 된다."""
    import winreg
    autostart.enable()
    approve(0x03)
    autostart.disable()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, SCRATCH_APPROVED) as k:
        data = winreg.QueryValueEx(k, autostart.VALUE)[0]
    chk("끈 기록이 그대로 남아 있다", data[0] == 0x03, data[:1])
    chk("Run 값만 지워졌다", autostart.registered() is None)


def t_실패하면_설정을_바꾸지_않는다():
    """레지스트리가 진실이고 설정 파일은 그 사본이다.

    등록에 실패했는데 설정만 True 로 바꾸면, 화면에는 '켜짐' 인데 실제로는
    부팅 때 안 뜨는 상태가 된다 - 회사 PC 처럼 정책으로 Run 키가 잠긴
    곳에서 실제로 일어난다.
    """
    from poketdesktop.app import App

    class 가짜(object):
        def __init__(self):
            self.settings = {"autostart": False}
            self.말 = []

        def notify(self, m):
            self.말.append(m)

        def refresh_tray(self):
            pass

        def _refresh_autostart_ui(self):
            pass

        켜기 = App.set_autostart

    a = 가짜()
    ok, _ = a.켜기(True)
    chk("되면 설정도 켜진다", ok and a.settings["autostart"] is True)

    막힌다 = lambda: (False, "등록하지 못했습니다")
    real = autostart.enable
    autostart.enable = 막힌다
    b = 가짜()
    try:
        ok, msg = b.켜기(True)
    finally:
        autostart.enable = real
    chk("실패하면 설정을 안 바꾼다",
        ok is False and b.settings["autostart"] is False, b.settings)
    chk("실패한 이유를 돌려준다", "등록하지 못했습니다" in msg, msg)


def t_맞추기():
    frozen(True)

    target(EXE_A)
    autostart.enable()
    old = autostart.registered()
    target(EXE_B)
    autostart.sync(True)
    # exe 이름이 바뀌면 등록해 둔 경로가 없는 파일을 가리킨다. 그러면
    # 다음 부팅 때 조용히 아무 일도 안 일어나는데, 설정 창에는 여전히
    # "켜짐" 이라 왜 안 되는지 알 길이 없다.
    chk("버전이 오르면 경로를 다시 쓴다",
        autostart.registered() != old and "1.0.7" in autostart.registered(),
        autostart.registered())

    before = autostart.registered()
    autostart.sync(True)
    chk("이미 맞으면 그대로 둔다", autostart.registered() == before)

    autostart.sync(False)
    chk("꺼 두었으면 남은 등록을 지운다", autostart.registered() is None)

    # 소스로 한 번 돌렸다고 exe 등록이 pythonw 경로로 덮이면 안 된다.
    # 덮이면 다음 부팅 때 게임 대신 개발용 소스가 뜨고, 소스가 없는
    # PC 로 옮기면 아예 아무것도 안 뜬다.
    target(EXE_B)
    autostart.enable()
    exe = autostart.registered()
    frozen(False)
    target(r"C:\python\pythonw.exe", r"C:\src\run.pyw")
    autostart.sync(True)
    chk("개발 중에는 등록을 건드리지 않는다",
        autostart.registered() == exe, autostart.registered())

    # 자동 시작은 부수적인 기능이다. 여기서 죽으면 게임이 안 켜진다.
    frozen(True)
    real = autostart.registered

    def 터진다():
        raise OSError("레지스트리가 막혔습니다")

    autostart.registered = 터진다
    try:
        autostart.sync(True)
        chk("맞추기는 실패해도 죽지 않는다", True)
    except Exception as e:                                  # noqa: BLE001
        chk("맞추기는 실패해도 죽지 않는다", False, e)
    finally:
        autostart.registered = real
        frozen(False)


def main():
    if sys.platform != "win32":
        print("윈도우에서만 하는 검사입니다.")
        return 0

    if autostart.RUN_KEY == REAL_RUN or "test" not in autostart.RUN_KEY:
        print("가짜 레지스트리 자리를 못 잡았습니다. 그만둡니다.")
        return 1

    # 검사 전 진짜 키의 우리 값을 적어 둔다. **자동 시작을 켜 둔 PC 에서는
    # 원래 값이 있는 게 정상이다** - 그걸 "검사가 더럽혔다" 고 읽으면
    # 멀쩡한 PC 에서 거짓 실패가 난다. 전후를 견줘야 한다.
    before = real_value()

    real_target = autostart._target
    try:
        for fn in (t_명령줄, t_켜고_끄기, t_작업관리자,
                   t_첫_설치에서_등록된다, t_끌_때_작업관리자_기록은_안_건드린다,
                   t_실패하면_설정을_바꾸지_않는다, t_맞추기):
            wipe()
            # 검사끼리 새지 않게 매번 되돌린다. 안 그러면 순서를 바꾸는
            # 것만으로 검사가 무엇을 보장하는지가 조용히 달라진다.
            autostart._target = REAL_TARGET
            frozen(False)
            print("-- %s" % fn.__name__[2:])
            fn()
    finally:
        wipe()
        autostart._target = real_target
        frozen(False)

    after = real_value()
    chk("진짜 Run 키를 건드리지 않았다", after == before,
        "%r -> %r" % (before, after))

    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
