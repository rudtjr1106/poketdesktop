# -*- coding: utf-8 -*-
"""한 번에 하나만 돌게 한다.

트레이 아이콘은 윈도우의 '숨겨진 아이콘' 안으로 들어가는 게 기본이라,
이미 켜져 있는 걸 못 보고 다시 누르기가 아주 쉽다. 그러면 오버레이가
두 벌이 되어 같은 포켓몬을 겹쳐 그리고, 두 클라이언트가 각자 서버를
두드려서 같은 풀숲을 두 개로 띄우거나 한쪽이 먼저 없애 버린다.
'야생이 여러 마리 나온다' 던 증상과 겹쳐서 원인 찾기도 어려워진다.

윈도우에서는 이름 있는 뮤텍스를, 맥에서는 flock 을 쓴다. 둘 다 프로세스가
어떻게 죽든 - 강제 종료든 정전이든 - 커널이 알아서 놓아주기 때문에,
잠금 파일처럼 '지우지 못한 채 죽어서 다시는 못 켜는' 일이 없다.
실제 방법은 platform_os 가 고른다.
"""
from . import platform_os as PLAT

_HANDLE = None


def acquire(data_dir):
    """이 프로세스가 유일한지. (잠금, 이미돌고있음) 을 돌려준다."""
    global _HANDLE
    _HANDLE, taken = PLAT.single_lock(data_dir)
    return _HANDLE, taken


def release():
    """붙잡은 것을 놓는다. 못 놓아도 문제는 없다 - 커널이 놓아주거나,
    다음 실행이 죽은 흔적을 알아보고 덮어쓴다."""
    global _HANDLE
    h, _HANDLE = _HANDLE, None
    if h is None:
        return
    PLAT.single_release(h)


def tell_user():
    """이미 돌고 있다고 알린다. 창 하나로 끝낸다.

    아무 말 없이 꺼지면 '눌렀는데 안 켜진다' 가 된다. 아이콘이 어디에
    숨어 있는지까지 같이 알려줘야 사용자가 찾아낸다.
    """
    try:
        import tkinter as tk
        from tkinter import messagebox
        # tk.Tk() 보다 먼저 해야 하는 것이 있다 (맥의 창 복구 대화상자).
        # 여기를 빼먹으면 한 번 죽은 뒤로는 이 창조차 안 뜬다.
        PLAT.before_tk()
        r = tk.Tk()
        r.withdraw()
        messagebox.showinfo(
            "포스크탑",
            "이미 실행 중입니다.\n\n" + PLAT.already_running_hint())
        r.destroy()
    except Exception:                                       # noqa: BLE001
        pass
