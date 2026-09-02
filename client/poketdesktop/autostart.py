# -*- coding: utf-8 -*-
"""컴퓨터를 켜면 같이 시작하게 한다.

윈도우는 레지스트리의 **Run 키**에 한 줄 넣는 방식을 쓴다. 관리자
권한이 필요 없고, **작업 관리자 > 시작 프로그램**에 그대로 보인다.
남의 컴퓨터가 켜질 때 같이 켜지는 기능이라, 우리 설정 창을 열어야만
끌 수 있는 곳에 숨기지 않는 것이 맞다.

## 작업 관리자에서 끈 것은 다시 켜지 않는다

윈도우는 사용자가 작업 관리자에서 끈 것을 **StartupApproved** 라는
다른 키에 따로 적어 두고, Run 키보다 그쪽을 우선한다. 그래서 상태를
볼 때 두 곳을 다 봐야 한다. Run 키만 보면 설정 창에는 "켜짐" 이라고
떠 있는데 실제로는 안 켜지는, 제일 알아채기 어려운 상황이 된다.

이 PC 의 실제 값으로 확인한 형식이다 (12바이트):

    02 00 00 00 00 00 00 00 00 00 00 00   켜짐
    03 00 00 00 bd 31 4e 0e b4 07 dd 01   꺼짐 (뒤 8바이트는 끈 시각)

첫 바이트가 홀수면 꺼진 것이다. 우리는 이 키를 **읽기만 한다** -
사용자가 작업 관리자에서 내린 결정을 프로그램이 뒤집으면 안 된다.

## 경로는 켤 때마다 다시 쓴다

버전이 오르면 파일 이름이 바뀐다 (poketdesktop-v1.0.7.exe). 등록해 둔
경로를 그냥 두면 다음 부팅 때 없는 파일을 가리켜서 **아무 일도 안
일어난다.** 그런데 설정 창에는 여전히 "켜짐" 이라 왜 안 되는지 알
길이 없다. 그래서 켜질 때마다 지금 돌고 있는 파일로 다시 쓴다.

## 맥은 아직이다

맥은 Run 키가 없고 ~/Library/LaunchAgents 에 plist 를 두는 방식이다.
여기서는 supported() 가 False 를 돌려주고, 화면은 "이 운영체제에서는
아직 안 됩니다" 라고 말한다. **되는 척하지 않는다.**
"""
import os
import subprocess
import sys

from . import config

# 레지스트리에서 우리 줄을 가리키는 이름. 두 키에서 같은 이름을 쓴다.
VALUE = "poketdesktop"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APPROVED_KEY = (r"Software\Microsoft\Windows\CurrentVersion\Explorer"
                r"\StartupApproved\Run")

# 부팅 때 켜진 것인지 손으로 켠 것인지 구분하려고 붙인다.
# 인터넷이 아직 안 붙었을 때 어떻게 굴지가 달라진다 (app.py).
FLAG = "--autostart"


def supported():
    return sys.platform == "win32"


def started_by_autostart(argv=None):
    """부팅 때 켜진 것인가."""
    return FLAG in list(argv if argv is not None else sys.argv[1:])


# ---------------------------------------------------------------- 명령줄
def _target():
    """무엇을 띄울 것인가. [프로그램, 인자...]"""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    # 개발 중(파이썬으로 돌릴 때). 검은 콘솔 창이 뜨지 않게 pythonw 를 쓴다.
    exe = sys.executable or ""
    w = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(w):
        exe = w
    return [exe, os.path.join(config.CLIENT_DIR, "run.pyw")]


def command():
    """Run 키에 넣을 한 줄.

    따옴표는 list2cmdline 에 맡긴다. 경로에 공백이 있는데 따옴표를 안
    붙이면 윈도우가 앞 토막까지만 읽고 엉뚱한 것을 찾는다.
    """
    return subprocess.list2cmdline(_target() + [FLAG])


# ---------------------------------------------------------------- 읽기
def registered():
    """Run 키에 등록된 명령줄. 없으면 None."""
    if not supported():
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            return winreg.QueryValueEx(k, VALUE)[0]
    except OSError:
        return None


def blocked():
    """작업 관리자에서 꺼 두었는가."""
    if not supported():
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY) as k:
            data = winreg.QueryValueEx(k, VALUE)[0]
    except OSError:
        return False            # 아무도 손댄 적 없다 = 막히지 않았다
    try:
        return bool(data[0] & 1)
    except (IndexError, TypeError):
        # 모르는 형식이면 **막혔다고 단정하지 않는다.** 잘 되고 있는
        # 것을 "꺼져 있다" 고 말하는 쪽이 더 나쁘다.
        return False


def state():
    """('on'|'off'|'blocked'|'unsupported', 사람이 읽을 한 줄)"""
    if not supported():
        return "unsupported", "이 운영체제에서는 아직 안 됩니다."
    if registered() is None:
        return "off", "컴퓨터를 켜도 자동으로 시작하지 않습니다."
    if blocked():
        return "blocked", ("등록은 되어 있지만 작업 관리자에서 꺼져 "
                           "있습니다.\n작업 관리자 > 시작 프로그램에서 켜 주세요.")
    return "on", "컴퓨터를 켜면 같이 시작합니다."


# ---------------------------------------------------------------- 쓰기
def enable():
    """(성공했는가, 사람에게 보여줄 한 줄)"""
    if not supported():
        return False, "이 운영체제에서는 아직 안 됩니다."
    cmd = command()
    try:
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                                winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, VALUE, 0, winreg.REG_SZ, cmd)
    except OSError as e:
        config.log("자동 시작 등록 실패: %s" % e)
        return False, "등록하지 못했습니다: %s" % e
    config.log("자동 시작 등록: %s" % cmd)
    if blocked():
        # 등록 자체는 됐다. 다만 윈도우가 안 띄운다. 이걸 말해 주지
        # 않으면 "켰는데 왜 안 되지" 로 남는다.
        return True, ("등록했지만 작업 관리자에서 꺼 두셨습니다.\n"
                      "작업 관리자 > 시작 프로그램에서 켜 주세요.")
    return True, "이제 컴퓨터를 켜면 같이 시작합니다."


def disable():
    if not supported():
        return False, "이 운영체제에서는 아직 안 됩니다."
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, VALUE)
    except FileNotFoundError:
        pass                    # 원래 없었다. 바라던 상태다.
    except OSError as e:
        config.log("자동 시작 해제 실패: %s" % e)
        return False, "해제하지 못했습니다: %s" % e
    config.log("자동 시작 해제")
    return True, "이제 자동으로 시작하지 않습니다."


def sync(want):
    """설정과 레지스트리를 맞춘다. 켤 때마다 한 번 부른다.

    하는 일은 두 가지다.
      · 켜 두었으면 **지금 돌고 있는 파일 경로로 다시 쓴다** (버전이
        오르면 파일 이름이 바뀌기 때문에).
      · 꺼 두었는데 등록이 남아 있으면 지운다.

    작업 관리자 쪽은 건드리지 않는다. 사용자가 거기서 껐으면 그대로 둔다.

    **개발 중(파이썬으로 돌릴 때)에는 아무것도 안 한다.** 설정 파일은
    exe 로 켤 때와 같은 자리를 쓰기 때문에, 소스로 한 번 돌리면 등록해 둔
    exe 경로가 pythonw 경로로 덮여 버린다. 그러면 다음 부팅 때 게임 대신
    개발용 소스가 뜬다 - 소스가 없는 PC 로 옮기면 아예 아무것도 안 뜬다.
    설정 창에서 손으로 켜는 것은 개발 중에도 그대로 된다.
    """
    if not supported() or not getattr(sys, "frozen", False):
        return
    try:
        cur = registered()
        if want:
            want_cmd = command()
            if cur != want_cmd:
                if cur:
                    config.log("자동 시작 경로가 바뀌었습니다. 다시 씁니다")
                enable()
        elif cur is not None:
            disable()
    except Exception as e:                                  # noqa: BLE001
        # 여기서 죽으면 게임이 아예 안 켜진다. 자동 시작은 부수적인
        # 기능이라 실패해도 나머지는 그대로 굴러가야 한다.
        config.log("자동 시작 맞추기 실패: %s" % e)
