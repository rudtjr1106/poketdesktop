# -*- coding: utf-8 -*-
"""한 번에 하나만 돌게 한다.

트레이 아이콘은 윈도우의 '숨겨진 아이콘' 안으로 들어가는 게 기본이라,
이미 켜져 있는 걸 못 보고 다시 누르기가 아주 쉽다. 그러면 오버레이가
두 벌이 되어 같은 포켓몬을 겹쳐 그리고, 두 클라이언트가 각자 서버를
두드려서 같은 풀숲을 두 개로 띄우거나 한쪽이 먼저 없애 버린다.
'야생이 여러 마리 나온다' 던 증상과 겹쳐서 원인 찾기도 어려워진다.

윈도우에서는 이름 있는 뮤텍스를 쓴다. 프로세스가 어떻게 죽든 - 강제
종료든 정전이든 - 커널이 알아서 놓아주기 때문에, 잠금 파일처럼 '지우지
못한 채 죽어서 다시는 못 켜는' 일이 없다.

그 밖의 환경에서는 잠금 파일로 대신하되, 파일에 적힌 프로세스가 실제로
살아 있는지 확인한다.
"""
import os
import sys

_HANDLE = None
NAME = "poketdesktop-single-instance"


def _win_lock():
    """이름 있는 뮤텍스. 이미 있으면 다른 인스턴스가 돌고 있다는 뜻."""
    import ctypes
    from ctypes import wintypes

    ERROR_ALREADY_EXISTS = 183
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.argtypes = [wintypes.LPCVOID, wintypes.BOOL,
                                 wintypes.LPCWSTR]
    k32.CreateMutexW.restype = wintypes.HANDLE
    # 이름 앞에 Local\ 을 붙여 같은 세션 안에서만 겹치게 한다. 여러 사용자가
    # 각자 로그인해 쓰는 컴퓨터에서 남의 것까지 막으면 안 된다.
    h = k32.CreateMutexW(None, False, "Local\\" + NAME)
    if not h:
        return None, False
    return h, k32.GetLastError() == ERROR_ALREADY_EXISTS


def _file_lock(path):
    """잠금 파일. 적힌 프로세스가 살아 있으면 이미 도는 것으로 본다."""
    try:
        if os.path.exists(path):
            with open(path) as f:
                pid = int((f.read() or "0").strip() or 0)
            if pid and pid != os.getpid():
                try:
                    os.kill(pid, 0)          # 살아 있나 보기만 한다
                    return None, True
                except OSError:
                    pass                     # 죽은 흔적이다. 덮어쓴다.
        with open(path, "w") as f:
            f.write(str(os.getpid()))
        return path, False
    except Exception:                                       # noqa: BLE001
        # 잠금을 못 걸었다고 게임을 못 켜게 하면 안 된다.
        return None, False


def acquire(data_dir):
    """이 프로세스가 유일한지. (잠금, 이미돌고있음) 을 돌려준다."""
    global _HANDLE
    if sys.platform == "win32":
        h, taken = _win_lock()
        _HANDLE = h
        return h, taken
    _HANDLE, taken = _file_lock(os.path.join(data_dir, "running.pid"))
    return _HANDLE, taken


def release():
    """붙잡은 것을 놓는다. 못 놓아도 문제는 없다 - 윈도우는 커널이,
    파일 쪽은 다음 실행이 죽은 흔적을 알아보고 덮어쓴다."""
    global _HANDLE
    h, _HANDLE = _HANDLE, None
    if h is None:
        return
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(h)
        except Exception:                                   # noqa: BLE001
            pass
    else:
        try:
            os.remove(h)
        except OSError:
            pass


def tell_user():
    """이미 돌고 있다고 알린다. 창 하나로 끝낸다.

    아무 말 없이 꺼지면 '눌렀는데 안 켜진다' 가 된다. 트레이가 숨겨진
    아이콘 안에 있다는 것까지 같이 알려줘야 사용자가 찾아낸다.
    """
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        messagebox.showinfo(
            "포스크탑",
            "이미 실행 중입니다.\n\n"
            "작업표시줄 오른쪽 끝의 '숨겨진 아이콘 표시'(^) 를 눌러\n"
            "몬스터볼 아이콘을 찾아보세요.")
        r.destroy()
    except Exception:                                       # noqa: BLE001
        pass
