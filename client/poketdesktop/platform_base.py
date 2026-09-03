# -*- coding: utf-8 -*-
"""플랫폼마다 다른 것들의 **계약**과, 어느 쪽도 아닐 때 쓸 기본 구현.

윈도우 전용 코드가 일곱 파일에 흩어져 있었다. 맥 코드를 그 옆에 `if` 로
덧붙이면 두 배로 헝클어지므로, 다른 것만 여기로 모으고 부르는 쪽은
`from . import platform_os as PLAT` 하나만 본다.

숨기는 것:

    transparent_window(win, hexkey)  창을 뚫는다. 도트 위젯에 칠할 배경색을 준다
    raise_above(win)                 항상 위로 (맥은 창이 뜬 뒤에 걸어야 먹는다)
    make_click_through(win)          마우스를 통과시킨다 (성공 여부를 돌려준다)
    SpriteView                       투명 창 안에서 도트를 그리는 것
    work_area(w, h)                  쓸 수 있는 화면 (작업표시줄/독 제외)
    double_click_ms()                두 번 클릭으로 치는 간격
    show_again(win)                  숨긴 창을 다시 보여준다 (항상 위를 다시 건다)
    bind_right(widget, fn)           오른쪽 클릭을 건다 (버튼 번호가 OS 마다 다르다)
    single_lock(dir) / single_release(h)   중복 실행 막기
    data_dir(app_name)               설정을 두는 자리 (None 이면 기본 자리)
    machine_raw()                    기기 ID 의 재료 (None 이면 MAC 주소로 간다)
    dpi_aware()                      고해상도 대응
    font_candidates()                이 OS 에서 먼저 찾아볼 글꼴
    pil_font_files(bold)             PIL 이 열어볼 글꼴 **파일** 이름들

여기 있는 것은 전부 "아무것도 안 한다" 에 가깝다. 리눅스에서 띄우면
도트가 네모난 판 위에 뜨겠지만 죽지는 않는다.
"""
# 커서가 도트의 빈 자리에 있을 때 클릭을 통과시켜야 하는 OS 인가.
# 윈도우는 투명색으로 칠한 픽셀이 알아서 통과하므로 할 일이 없다.
NEEDS_HIT_TRACKING = False

# 오른쪽 클릭이 어떤 이벤트로 오는가. 윈도우와 X11 은 3번 단추다.
RIGHT_CLICK = ("<Button-3>",)

# `tk.Menu` 를 써도 되는가. 맥에서는 그것이 NSMenu 라 여는 순간 앱이
# 죽는다 (platform_mac 을 보라). 그쪽은 ui_common.PopupMenu 로 그린다.
NATIVE_MENU = True

# tkinter 와 PIL 은 함수 안에서 들여온다. 화면이 없는 검사(투기장 좌표,
# 한국어 표기)는 이 모듈을 거치기만 하고 창은 안 만들기 때문이다.


# ---------------------------------------------------------------- 창
def transparent_window(win, hexkey):
    """창을 투명하게. 도트를 담을 위젯에 칠할 배경색을 돌려준다."""
    try:
        win.attributes("-topmost", True)
    except Exception:                                       # noqa: BLE001
        pass
    win.configure(bg=hexkey)
    return hexkey


def raise_above(win):
    """항상 위로 올린다. 창이 화면에 올라간 뒤에 부른다."""
    try:
        win.attributes("-topmost", True)
    except Exception:                                       # noqa: BLE001
        pass


def bind_right(widget, fn):
    """오른쪽 클릭을 건다.

    버튼 번호가 OS 마다 다르다. 한 곳에 모아 두지 않으면 한쪽에서만
    조용히 안 먹는다.
    """
    for seq in RIGHT_CLICK:
        widget.bind(seq, fn)


def show_again(win):
    """숨겨 둔 창을 다시 보여준다.

    맥에서는 `deiconify()` 가 창 속성을 다시 걸면서 '항상 위' 와 클릭
    통과를 **풀어 버린다.** 그래서 다시 보여줄 때는 항상 이걸 거쳐야
    한다. 그냥 `win.deiconify()` 를 부르면 배틀 한 판 하고 나서
    포켓몬이 다른 창 뒤로 숨는다.
    """
    win.deiconify()
    raise_above(win)


def make_click_through(win):
    """창 전체를 마우스가 통과하게. 못 하면 False.

    **False 를 돌려주면 부르는 쪽은 레이어를 아예 안 띄워야 한다.**
    통과하지 않는 투명 레이어는 화면을 덮는 벽이라, 이펙트가 안 보이는
    것보다 훨씬 나쁘다.
    """
    return False


# ---------------------------------------------------------------- 도트
class SpriteView(object):
    """투명 창 하나에 도트를 그린다.

    창은 부르는 쪽이 만들고(Toplevel + transparent_window), 그 안에 들어갈
    위젯과 그리는 방법만 여기서 정한다. `widget` 은 마우스 바인딩을 걸
    자리다.

    맥에서는 이 위젯이 Label 이 아니다. Tk 8.6 aqua 는 배경이
    systemTransparent 인 위젯에 그림을 올리면 **아무것도 안 그린다**.
    그래서 맥판은 빈 Frame 을 두고 CALayer 로 따로 그린다.
    """

    def __init__(self, win, bg, w, h, **kw):
        import tkinter as tk

        self.win = win
        self.w, self.h = w, h
        self.widget = tk.Label(win, bd=0, highlightthickness=0, bg=bg, **kw)
        self.widget.pack()

    def frames(self, pil_frames, key):
        """PIL 그림 목록을 이 플랫폼이 그릴 수 있는 형태로."""
        from PIL import ImageTk

        return [ImageTk.PhotoImage(f) for f in pil_frames]

    def show(self, frame):
        self.widget.configure(image=frame)

    def resize(self, w, h):
        self.w, self.h = w, h

    def update_hit(self, lx, ly):
        """커서가 이 도트 창 안 어디에 있는지 알려준다.

        lx/ly 는 창 왼쪽 위를 기준으로 한 좌표다. 창 밖이면 None 이다.
        윈도우는 투명색으로 칠한 자리가 알아서 클릭을 통과시키므로
        할 일이 없다.
        """
        pass

    def destroy(self):
        pass


# ---------------------------------------------------------------- 화면
def work_area(fallback_w, fallback_h):
    """작업표시줄/독을 뺀 화면 영역."""
    return 0, 0, fallback_w, fallback_h


def double_click_ms():
    return 350


def screens(fallback_w, fallback_h):
    """모든 화면을 Tk 좌표 (x1, y1, x2, y2) 로. **첫 번째가 주 화면.**

    모니터가 두 대일 때 메뉴를 어느 화면 안에 가둘지 정하는 데 쓴다.
    한 대뿐이면 화면 하나가 전부다.
    """
    return [(0, 0, fallback_w, fallback_h)]


# ---------------------------------------------------------------- 프로세스
def single_lock(data_dir):
    """(잠금, 이미돌고있음). 잠금을 못 걸었다고 게임을 막지는 않는다."""
    import os

    path = os.path.join(data_dir, "running.pid")
    try:
        if os.path.exists(path):
            with open(path) as f:
                pid = int((f.read() or "0").strip() or 0)
            if pid and pid != os.getpid():
                try:
                    os.kill(pid, 0)
                    return None, True
                except OSError:
                    pass
        with open(path, "w") as f:
            f.write(str(os.getpid()))
        return path, False
    except Exception:                                       # noqa: BLE001
        return None, False


def single_release(handle):
    import os

    try:
        os.remove(handle)
    except OSError:
        pass


def data_dir(app_name):
    """설정을 둘 자리. None 이면 부르는 쪽이 기본 자리를 쓴다."""
    return None


def machine_raw():
    """기기 ID 의 재료. None 이면 부르는 쪽이 MAC 주소로 간다."""
    return None


def dpi_aware():
    """고해상도에서 흐릿하지 않게. 맥/리눅스는 알아서 한다."""
    pass


def before_tk():
    """`tk.Tk()` 를 만들기 직전에 할 일. 대개 아무것도 없다."""
    pass


def gui_ready():
    """이 OS 에서 화면을 제대로 그릴 수 있는가."""
    return True


def hide_from_dock():
    """작업표시줄/Dock 에 안 보이게. 트레이 아이콘만 남긴다.

    윈도우는 `overrideredirect` 창들이라 원래 작업표시줄에 안 뜬다.
    """
    pass


def activate():
    """우리 창을 앞으로 꺼낸다. Dock 에 없는 앱은 이게 필요하다."""
    pass


def accept_first_click():
    """앱이 앞에 없어도 첫 클릭을 그대로 받는다. 윈도우는 원래 그렇다."""
    return True


def watch_right_click():
    """오른쪽 클릭을 따로 받아 둘 필요가 있는가. 윈도우는 없다."""
    pass


def take_right_clicks():
    return []


def mouse_buttons_down():
    """지금 눌려 있는 마우스 단추. 모르면 0 (윈도우는 Tk 이 알아서 준다)."""
    return 0


def missing_requirement():
    """없어서 못 도는 것이 있으면 사람에게 보여줄 한 줄. 없으면 None."""
    return None


# ---------------------------------------------------------------- 글꼴
def font_candidates():
    """이 OS 에서 먼저 찾아볼 글꼴. 공용 목록 뒤에 붙는다."""
    return []


def pil_font_files(bold=False):
    """PIL 은 Tk 과 달리 글꼴 **파일**을 찾는다. 이 OS 의 후보 파일들."""
    return ()


def already_running_hint():
    """이미 돌고 있다고 알릴 때, 어디를 보라고 할 것인가."""
    return "이미 떠 있는 창을 찾아보세요."
