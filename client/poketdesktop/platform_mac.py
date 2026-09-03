# -*- coding: utf-8 -*-
"""맥에서만 쓰는 것들.

윈도우와 제일 크게 다른 두 가지가 여기 들어 있다.

## 1. 투명 배경 — 색을 뚫는 게 아니라 창 자체가 투명하다

윈도우는 `-transparentcolor` 로 **특정 색**을 뚫는다. 맥에는 그 옵션이
아예 없고(`TclError`), 대신 `-transparent` 로 **창 배경 전체**를 투명하게
만든다. NSWindow 가 `isOpaque=False`, `backgroundColor=clear`,
`hasShadow=False` 로 바뀐다 — 창 그림자까지 알아서 꺼진다.

**그런데 여기 함정이 하나 있다.** Tk 8.6 aqua 는 배경이
`systemTransparent` 인 위젯에 그림(photo image)을 올리면 **아무것도 안
그린다.** 글자와 사각형 같은 벡터는 멀쩡히 그려지는데 그림만 사라진다.
Label 이든 Canvas 든, 알파가 있든 없든 똑같다.

그래서 맥에서는 창과 좌표와 마우스만 Tk 이 맡고, **도트는 CALayer 가
그린다.** 대신 얻는 것이 있다 — 색빼기가 아니라 진짜 알파라서 가장자리
반투명이 그대로 살고, 도트 안에 자홍색이 들어 있어도 구멍이 안 뚫린다.

## 2. 트레이 — pystray 를 안 쓴다

pystray 의 맥 백엔드는 `NSApplication.run()` 을 부른다. 그걸 별도
스레드에서 부르면 파이썬 예외도 못 남기고 프로세스가 SIGTRAP 으로 죽는다.
그런데 Tk aqua 의 `mainloop` 는 이미 Cocoa 메인 런루프를 돌리고 있으므로,
`NSStatusItem` 을 **같은 스레드에서 그냥 만들면** 된다. 별도 스레드도,
`NSApp.run()` 도 필요 없다.

지켜야 할 것: `tkinter.Tk()` 를 무조건 먼저 만든다. 그 전에
`NSApplication.sharedApplication()` 이 불리면 Tk 이 abort 한다.
"""
import ctypes
import os

APP_NAME = "poketdesktop"

# 맥은 도트가 없는 자리도 창이 클릭을 먹는다. 커서를 좇아가며 그때그때
# 통과를 켜고 꺼 줘야 한다. Overlay 가 이 값을 보고 그 일을 한다.
NEEDS_HIT_TRACKING = True

# **맥 Tk 은 오른쪽 단추가 2번이다.** 3번은 가운데 단추다. 윈도우 기준으로
# <Button-3> 만 걸어 두면 맥에서 오른쪽 클릭이 통째로 안 먹는다.
# Control+왼쪽 클릭도 맥에서는 오른쪽 클릭으로 친다.
RIGHT_CLICK = ("<Button-2>", "<Button-3>", "<Control-Button-1>")

# `tk.Menu` 는 aqua 에서 NSMenu 다. 여는 순간 앱이 죽는다 (tray_mac 의
# 첫 주석을 보라). 뜨는 메뉴는 ui_common.PopupMenu 로 그린다.
NATIVE_MENU = False

_ok = False
try:
    import objc                                             # noqa: F401
    import AppKit
    import Foundation
    import Quartz
    from Quartz import CALayer, CATransaction
    _ok = True
except Exception:                                           # noqa: BLE001
    _ok = False

_CS = Quartz.CGColorSpaceCreateDeviceRGB() if _ok else None


def available():
    """pyobjc 가 있는가. 없으면 투명 배경도 트레이도 안 된다."""
    return _ok


def gui_ready():
    return _ok


def missing_requirement():
    """pyobjc 가 없으면 게임을 할 수가 없다.

    투명 배경이 안 되면 도트가 네모난 판 위에 뜨고, 메뉴 막대 아이콘이
    없으면 포켓몬 관리도 가방도 상점도 설정도 열 방법이 없다 - 그게
    이 게임의 유일한 메뉴다. 반쯤 도는 채로 띄우느니 무엇을 깔아야
    하는지 말해 주는 편이 낫다.
    """
    if _ok:
        return None
    return ("맥에서 돌리려면 pyobjc 가 필요합니다.\n\n"
            "터미널에서 이렇게 쳐 주세요:\n\n"
            "  pip install pyobjc-framework-Cocoa pyobjc-framework-Quartz\n\n"
            "(이게 없으면 포켓몬이 네모난 판 위에 뜨고,\n"
            " 메뉴 막대 아이콘이 없어 게임을 조작할 수 없습니다.)")


# ---------------------------------------------------------------- NSWindow
_GETVIEW = None            # None=아직 안 찾음, False=못 찾음


def _root_control():
    """Tk 이 내보내는 TkMacOSXGetRootControl 을 ctypes 로 잡아둔다.

    `winfo_id()` 가 돌려주는 것은 NSView 가 아니라 Tk 내부의
    MacDrawable* 이다. 그래서 이 함수를 거쳐 TKContentView 를 얻어야 한다.
    """
    global _GETVIEW
    if _GETVIEW is None:
        _GETVIEW = False
        try:
            lib = ctypes.CDLL(None)          # 이미 로드된 Tk 심볼을 그대로
            for nm in ("TkMacOSXGetRootControl",
                       "Tk_MacOSXGetNSViewForDrawable"):
                fn = getattr(lib, nm, None)
                if fn is not None:
                    fn.restype = ctypes.c_void_p
                    fn.argtypes = [ctypes.c_void_p]
                    _GETVIEW = fn
                    break
        except Exception:                                   # noqa: BLE001
            _GETVIEW = False
    return _GETVIEW


def nswindow(win):
    """Tk 창 -> 그 창의 NSWindow. 못 찾으면 None.

    창 제목이나 크기로 맞추는 방법은 창이 여럿이면 틀린 것을 잡는다
    (테두리 없는 창은 제목이 전부 같고, 같은 크기 창도 흔하다).
    이 방법은 포인터를 따라가므로 틀릴 수가 없다.
    """
    fn = _root_control()
    if not fn or not _ok:
        return None
    try:
        win.update_idletasks()
        ptr = fn(ctypes.c_void_p(win.winfo_id()))
        if not ptr:
            return None
        view = objc.objc_object(c_void_p=ctypes.c_void_p(ptr))
        return view.window()
    except Exception:                                       # noqa: BLE001
        return None


# ---------------------------------------------------------------- 창
def transparent_window(win, hexkey):
    """창 배경 자체를 투명하게. 도트 위젯에 칠할 배경색을 돌려준다.

    hexkey 는 안 쓴다 - 맥은 색을 뚫는 방식이 아니다. 같은 자리에서
    부를 수 있도록 인자만 맞춰 둔다.
    """
    if not _ok:
        # pyobjc 가 없으면 투명은 포기하고 창이라도 뜨게 한다.
        win.configure(bg=hexkey)
        return hexkey
    win.attributes("-transparent", True)
    win.configure(bg="systemTransparent")
    return "systemTransparent"


def raise_above(win):
    """항상 위로.

    맥에서 `-topmost` 는 **창이 화면에 올라간 뒤에** 걸어야 먹는다.
    Toplevel 을 만들자마자 걸면 조용히 씹히고, 읽어 보면 0 이 나온다.
    """
    try:
        win.update_idletasks()
        win.attributes("-topmost", True)
    except Exception:                                       # noqa: BLE001
        pass


def own_dialog(win, root):
    """**맥에서는 transient 를 걸지 않는다.**

    우리 root 는 withdraw 돼 있다(창은 전부 Toplevel 이다). 맥 Tk 은
    withdraw 된 창의 transient 를 **같이 withdraw 한다** - 걸자마자
    사라지고, 풀어도 그대로다. 그래서 '새로운 기능' 창, 새 버전을 묻는 창,
    받는 창이 맥에서 한 번도 안 떴다. 묻는 창은 답을 기다리느라 갈아타는
    일까지 조용히 멈췄다. 직접 재 본 것:

        만든 직후                 normal   viewable=1
        transient(withdrawn root) withdrawn viewable=0
        그 뒤 deiconify           normal   viewable=1
        transient 없이            normal   viewable=1

    transient 가 주는 것(작업 표시줄에 안 뜸)은 맥에 애초에 없다.
    """
    return


def surface(win):
    """대화창을 앞으로 꺼낸다.

    맥 14 부터 앱이 스스로 앞으로 나오는 것은 **부탁**이다(cooperative
    activation). 사용자가 방금 우리를 눌렀으면(트레이 메뉴) 들어주고,
    타이머가 띄운 창이면 거절한다. 거절돼도 창은 화면에 뜬다 - 새로 연
    창은 앞에 오고, 키보드만 쓰던 앱에 남는다. 그 정도면 된다.

    `-topmost` 는 일부러 안 건다. 도트와 설명은 바탕화면 장식이라 늘 위에
    있어야 하지만, 글 읽는 창이 닫을 때까지 브라우저 위에 떠 있으면
    그게 방해다.
    """
    activate()


def bind_right(widget, fn):
    """맥에서는 **걸지 않는다.**

    앱이 활성일 때만 오면 반쪽이고, 감시자(watch_right_click)와 둘 다
    걸리면 한 번 누른 것이 두 번 처리된다 - 볼이 두 개 날아간다.
    받는 곳을 하나로 둔다.
    """
    return


def show_again(win):
    """숨겨 둔 창을 다시 보여준다.

    맥에서 `deiconify()` 는 Tk 이 창 속성을 다시 거는 자리라, '항상 위'
    와 클릭 통과가 **둘 다 풀린다.** 숨겼다 켠 뒤가 아니라 그냥 부르기만
    해도 그렇다. 그래서 부른 직후에 다시 걸어 준다.
    """
    win.deiconify()
    raise_above(win)
    keep_click_through(win)


def make_click_through(win):
    """마우스가 창을 그냥 통과하게 만든다. 성공하면 True.

    윈도우의 WS_EX_TRANSPARENT 자리다. 맥은 NSWindow 의
    ignoresMouseEvents 인데, Tk 에서 직접 못 건드려서 NSWindow 를
    찾아가야 한다.

    **`deiconify()` 를 부르면 Tk 이 창 속성을 다시 걸면서 이 플래그를 푼다.**
    숨겼다 켠 뒤가 아니라 그냥 부르기만 해도 풀린다. 그래서 부르는 쪽이
    가끔 다시 걸어 줘야 한다 (fx_layer.raise_above 가 그렇게 한다).
    **이 창에는 deiconify 를 부르지 마라.**
    """
    nsw = nswindow(win)
    if nsw is None:
        return False
    try:
        nsw.setIgnoresMouseEvents_(True)
        ok = bool(nsw.ignoresMouseEvents())
    except Exception:                                       # noqa: BLE001
        return False
    if ok:
        # 찾아 둔 것을 창에 붙여 둔다. 다시 찾을 때마다 objc 객체를
        # 하나씩 붙잡게 되는데(autorelease pool 이 빌 때까지 쌓인다),
        # 매 프레임 도는 자리라 그냥 재사용하는 편이 낫다.
        try:
            win._poket_nswindow = nsw
        except Exception:                                   # noqa: BLE001
            pass
    return ok


def keep_click_through(win):
    """풀렸으면 다시 건다. 이미 걸려 있으면 아무 일도 안 한다."""
    nsw = getattr(win, "_poket_nswindow", None)
    if nsw is None:
        return
    try:
        if not nsw.ignoresMouseEvents():
            nsw.setIgnoresMouseEvents_(True)
    except Exception:                                       # noqa: BLE001
        pass


# ---------------------------------------------------------------- 도트
def _cgimage(pil_rgba):
    """알파를 미리 곱해둔 RGBA -> CGImage.

    PNG 로 한 번 굽는 것보다 열 배 빠르다. 도트 한 마리에 프레임이
    예순 장까지 있으므로 이 차이가 로딩 시간으로 나온다.
    """
    w, h = pil_rgba.size
    raw = pil_rgba.tobytes()
    data = Foundation.NSData.dataWithBytes_length_(raw, len(raw))
    prov = Quartz.CGDataProviderCreateWithCFData(data)
    return Quartz.CGImageCreate(
        w, h, 8, 32, w * 4, _CS,
        Quartz.kCGImageAlphaPremultipliedLast
        | Quartz.kCGBitmapByteOrderDefault,
        prov, None, False, Quartz.kCGRenderingIntentDefault)


_told_no_layer = False


def _no_layer(why):
    """도트를 그릴 레이어를 못 만들었다. **조용히 넘어가면 안 된다.**

    이 경우 포켓몬이 화면에서 그냥 안 보인다. 창은 떠 있고 예외도 안
    나서, 기록이 없으면 무엇이 잘못됐는지 알 길이 없다. 한 번만 남긴다 -
    도트 한 마리마다 찍으면 로그가 뒤덮인다.
    """
    global _told_no_layer
    if _told_no_layer:
        return
    _told_no_layer = True
    try:
        from . import config
        config.log("도트를 그릴 레이어를 못 만들었습니다 (%s). "
                   "포켓몬이 화면에 안 보일 수 있습니다." % (why,))
    except Exception:                                       # noqa: BLE001
        pass


# 커서에서 이만큼 안에 몸이 있으면 클릭을 안 통과시킨다. 도트 가장자리에서
# 클릭이 새어 나가지 않게 두는 여유다.
HIT_MARGIN = 4


def _near_solid(mask, w, h, x, y, r=HIT_MARGIN):
    """커서 둘레 r 픽셀 안에 몸이 있는가."""
    for yy in range(max(0, y - r), min(h, y + r + 1)):
        row = yy * w
        for xx in range(max(0, x - r), min(w, x + r + 1)):
            if mask[row + xx]:
                return True
    return False


class Frame(object):
    """CALayer 에 올릴 그림 한 장.

    윈도우의 `ImageTk.PhotoImage` 자리다. 부르는 쪽이 크기를 물어보는
    일이 있어서(진화 연출) `width()` / `height()` 를 같은 이름으로 둔다.
    """

    __slots__ = ("img", "_w", "_h", "mask")

    def __init__(self, img, w, h, mask=None):
        self.img, self._w, self._h = img, w, h
        # 어디가 몸이고 어디가 빈 자리인지. 한 픽셀에 한 바이트다.
        # 커서 밑이 비었는지 볼 때 쓴다.
        self.mask = mask

    def width(self):
        return self._w

    def height(self):
        return self._h


class SpriteView(object):
    """투명 창 안에서 도트를 그린다 (맥판).

    위젯은 빈 Frame 이다. 그림은 CALayer 가 그린다 - 위에 적은 대로
    Tk 이 systemTransparent 위젯에 그림을 못 그리기 때문이다.
    마우스 바인딩은 Frame 이 그대로 받는다.

    **도트 둘레의 투명한 자리도 클릭을 먹는다. 윈도우와 다른 점이다.**
    윈도우는 색으로 뚫은 픽셀로 클릭이 그대로 지나가는데, 여기서는
    도트 바운딩 박스 전체가 마우스를 받는다. 확인한 것은 이렇다.

      · 맥 창 서버는 원래 알파가 0 인 자리로 클릭을 통과시킨다.
        똑같이 설정한 **순수 NSWindow** 로는 통과한다.
      · 그런데 Tk 의 TKWindow 는 그 통과를 무력화한다. 창 레벨도,
        styleMask 도, contentView 를 평범한 NSView 로 갈아끼워도
        안 돌아온다.
      · 그래서 Tk 창에서 클릭을 통과시키는 수단은 `ignoresMouseEvents`
        하나뿐이다. 그건 창 **전체**에 걸리는 것이라 도트에는 못 쓴다 -
        걸면 포켓몬을 쓰다듬지도 잡지도 못한다.

    고치려면 커서 위치를 좇아가며 그 밑 픽셀이 비었는지 보고
    `ignoresMouseEvents` 를 켰다 껐다 해야 한다. 아직 안 했다.
    """

    def __init__(self, win, bg, w, h, **kw):
        import tkinter as tk

        self.win = win
        self.w, self.h = w, h
        self.layer = None
        self._cur = None            # 지금 그려져 있는 그림
        self._ignoring = False      # 지금 클릭을 통과시키고 있는가
        self.win_number = None      # 이 창의 NSWindow 번호
        self._acc = {}              # {(w,h): 알파를 전부 합친 것}
        self._solid = {}            # {(w,h): 그 바이트}
        if not _ok:
            # pyobjc 가 없다. 투명도 CALayer 도 못 쓰니 평범한 Label 에
            # 평범하게 그린다 - 네모난 판 위에 뜨겠지만 게임은 된다.
            self.widget = tk.Label(win, bd=0, highlightthickness=0, bg=bg,
                                   **kw)
            self.widget.pack()
            return
        accept_first_click()                 # 아직 안 걸렸으면 지금 건다
        keep_focus()                         # 포커스를 뺏지 않게
        kw.pop("image", None)                # Frame 은 그림을 받지 않는다
        self.widget = tk.Frame(win, width=w, height=h, bg=bg, **kw)
        self.widget.pack()
        raise_above(win)
        nsw = nswindow(win)
        if nsw is None:
            _no_layer("NSWindow 를 못 찾았다")
            return
        try:
            cv = nsw.contentView()
            cv.setWantsLayer_(True)
            lay = CALayer.layer()
            lay.setFrame_(((0, 0), (w, h)))
            lay.setContentsScale_(nsw.backingScaleFactor())
            lay.setMagnificationFilter_("nearest")   # 도트가 뭉개지면 안 된다
            lay.setMinificationFilter_("nearest")
            cv.layer().addSublayer_(lay)
            self.layer = lay
            self.win_number = nsw.windowNumber()
        except Exception as e:                              # noqa: BLE001
            _no_layer(e)
            self.layer = None

    def frames(self, pil_frames, key):
        """색빼기로 칠해 둔 도트를 알파 있는 그림으로 되돌려 CGImage 로.

        윈도우용으로 만들어 둔 그림을 그대로 받아서 되돌린다. 도트를
        만드는 쪽(sprites.py)은 양쪽이 같은 코드를 쓴다.
        """
        if self.layer is None:
            if not _ok:
                from PIL import ImageTk
                self._keep = [ImageTk.PhotoImage(f) for f in pil_frames]
                return self._keep
            # 레이어가 없으면 그릴 방법이 없다. 그래도 **계약은 지킨다** -
            # 부르는 쪽(진화 연출)이 width()/height() 를 물어보기 때문에,
            # 맨 PIL 이미지를 돌려주면 거기서 TypeError 로 터진다.
            return [Frame(None, f.width, f.height) for f in pil_frames]
        from PIL import ImageChops
        from . import sprites
        out = []
        for f in pil_frames:
            rgba = sprites.to_rgba(f, key) if f.mode != "RGBA" else f
            alpha = rgba.split()[3]
            key_wh = (f.width, f.height)
            # **프레임을 전부 합쳐 둔다.** 클릭을 통과시킬지 정할 때
            # 지금 프레임 하나만 보면, 도트가 움직이는 자리에서 같은
            # 점이 몸이었다 빈칸이었다 해서 클릭이 씹혔다 말았다 한다.
            acc = self._acc.get(key_wh)
            self._acc[key_wh] = (alpha if acc is None
                                 else ImageChops.lighter(acc, alpha))
            self._solid[key_wh] = self._acc[key_wh].tobytes()
            out.append(Frame(_cgimage(sprites.premultiply(rgba)),
                             f.width, f.height, alpha.tobytes()))
        return out

    def show(self, frame):
        if self.layer is None:
            if not _ok:
                self.widget.configure(image=frame)
            return
        if frame.img is None:            # 그릴 레이어가 없다. 이미 기록했다.
            return
        self._cur = frame
        # 그림마다 크기가 다를 수 있다 (볼 26px, 반짝임 52px, 진화 연출은
        # 단계마다 커진다). 윈도우는 Label 이 알아서 따라가지만 여기서는
        # 레이어 크기를 직접 맞춰 줘야 한다.
        if frame.width() != self.w or frame.height() != self.h:
            self.resize(frame.width(), frame.height())
        # 이걸 안 걸면 프레임을 바꿀 때마다 0.2초짜리 크로스페이드가 붙어서
        # 걷는 동작이 통째로 뭉개진다. CoreAnimation 의 기본 동작이다.
        CATransaction.begin()
        CATransaction.setDisableActions_(True)
        try:
            self.layer.setContents_(frame.img)
        finally:
            CATransaction.commit()

    def update_hit(self, lx, ly):
        """커서 밑이 비었으면 클릭을 통과시키고, 도트 위면 도로 막는다.

        맥에서는 창이 알파 0 인 자리도 클릭을 먹는다 (TKWindow 가 그렇게
        만든다 - 위 SpriteView 설명을 보라). 통과를 만드는 수단은 창
        전체에 걸리는 `ignoresMouseEvents` 뿐이라, 커서 위치를 보고
        그때그때 켜고 끄는 수밖에 없다.

        **창 밖이면 도로 막아 둔다.** 창 서버에 반영되기까지 한 틱쯤
        걸리는데, 밖에 있을 때 통과 상태로 두면 커서가 도트로 들어온
        직후의 클릭이 바탕화면으로 새어 나간다. 포켓몬을 못 누르는 것이
        빈 자리를 못 누르는 것보다 나쁘다.
        """
        if self.layer is None:
            return
        want = False
        fr = self._cur
        if lx is not None and fr is not None:
            w, h = fr.width(), fr.height()
            m = self._solid.get((w, h)) or fr.mask
            if m is not None and 0 <= lx < w and 0 <= ly < h:
                want = not _near_solid(m, w, h, lx, ly)
        if want == self._ignoring:
            return
        nsw = getattr(self.win, "_poket_nswindow", None)
        if nsw is None:
            nsw = nswindow(self.win)
            if nsw is None:
                return
            try:
                self.win._poket_nswindow = nsw
            except Exception:                               # noqa: BLE001
                pass
        try:
            nsw.setIgnoresMouseEvents_(want)
            self._ignoring = want
        except Exception:                                   # noqa: BLE001
            pass

    def resize(self, w, h):
        self.w, self.h = w, h
        try:
            self.widget.configure(width=w, height=h)
        except Exception:                                   # noqa: BLE001
            pass
        if self.layer is None:
            return
        CATransaction.begin()
        CATransaction.setDisableActions_(True)
        try:
            self.layer.setFrame_(((0, 0), (w, h)))
        finally:
            CATransaction.commit()

    def destroy(self):
        if self.layer is not None:
            try:
                self.layer.removeFromSuperlayer()
            except Exception:                               # noqa: BLE001
                pass
            self.layer = None


# ---------------------------------------------------------------- 화면
_area_cache = (0.0, None)


def work_area(fallback_w, fallback_h):
    """메뉴 막대와 독을 뺀 화면 영역.

    AppKit 은 화면 **왼쪽 아래**가 원점이고 y 가 위로 간다. Tk 은
    **왼쪽 위**가 원점이고 y 가 아래로 간다. 그래서 뒤집어 준다.

    레티나는 신경 쓸 것이 없다. Tk aqua 도 NSScreen 도 둘 다 '포인트'
    단위라 그대로 맞는다. 여기서 배율을 곱하면 오히려 어긋난다.
    """
    global _area_cache
    import time

    now = time.monotonic()
    if _area_cache[1] and now - _area_cache[0] < 1.0:
        return _area_cache[1]
    r = _work_area_now(fallback_w, fallback_h)
    _area_cache = (now, r)
    return r


def _work_area_now(fallback_w, fallback_h):
    if not _ok:
        return 0, 0, fallback_w, fallback_h
    try:
        scrs = AppKit.NSScreen.screens()
        if not scrs:
            return 0, 0, fallback_w, fallback_h
        # 기준은 **주 화면**이다. mainScreen() 은 '지금 키 창이 있는 화면'
        # 이라 모니터가 둘이면 다른 화면을 가리킬 수 있고, 그러면 Tk 의
        # winfo_screenwidth(주 화면 기준)와 어긋난다.
        prim = scrs[0]
        h = prim.frame().size.height
        v = prim.visibleFrame()
        x1 = int(round(v.origin.x))
        x2 = int(round(v.origin.x + v.size.width))
        y1 = int(round(h - (v.origin.y + v.size.height)))    # 메뉴 막대 아래
        y2 = int(round(h - v.origin.y))                      # 독 위
        if x2 > x1 and y2 > y1:
            return x1, y1, x2, y2
    except Exception:                                       # noqa: BLE001
        pass
    return 0, 0, fallback_w, fallback_h


def screens(fallback_w, fallback_h):
    """모든 화면을 Tk 좌표로. 첫 번째가 주 화면.

    AppKit 은 **주 화면 왼쪽 아래**가 원점이고 y 가 위로 간다. Tk 은
    주 화면 왼쪽 위가 원점이고 y 가 아래로 간다. 두 번째 화면은 x 가
    음수일 수도 있다(주 화면 왼쪽에 두면).
    """
    if not _ok:
        return [(0, 0, fallback_w, fallback_h)]
    try:
        scrs = AppKit.NSScreen.screens()
        if not scrs:
            return [(0, 0, fallback_w, fallback_h)]
        h0 = scrs[0].frame().size.height
        out = []
        for s in scrs:
            f = s.frame()
            out.append((int(round(f.origin.x)),
                        int(round(h0 - (f.origin.y + f.size.height))),
                        int(round(f.origin.x + f.size.width)),
                        int(round(h0 - f.origin.y))))
        return out
    except Exception:                                       # noqa: BLE001
        return [(0, 0, fallback_w, fallback_h)]


def double_click_ms():
    """맥의 기본은 500ms 다. 시스템 설정에서 사람마다 바꾼다."""
    if not _ok:
        return 350
    try:
        v = AppKit.NSEvent.doubleClickInterval() * 1000.0
        return max(160, min(600, int(round(v))))
    except Exception:                                       # noqa: BLE001
        return 350


# ---------------------------------------------------------------- 프로세스
_LOCK = None


def single_lock(data_dir_):
    """flock. 프로세스가 어떻게 죽든 커널이 놓아준다.

    윈도우의 이름 있는 뮤텍스와 같은 성질이다. pid 를 적어 두고
    `os.kill(pid, 0)` 로 확인하는 방식은 두 군데가 샌다 - 재부팅 뒤
    PID 가 돌아 쓰이면 남의 프로세스를 우리로 오해해서 영영 안 뜨고,
    파일이 깨지면 int() 가 터져 잠금이 조용히 꺼진다.
    """
    global _LOCK
    import fcntl

    try:
        f = open(os.path.join(data_dir_, "running.lock"), "a+")
    except Exception:                                       # noqa: BLE001
        # 파일을 못 여는 것은 **다른 인스턴스가 있다는 뜻이 아니다.**
        # 여기서 True 를 돌려주면 폴더가 안 써지는 순간부터 앱이 영영
        # 안 뜬다. 잠금을 못 걸었다고 게임을 못 켜게 하면 안 된다.
        return None, False
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:                          # 이미 누가 잡고 있다
        try:
            f.close()
        except Exception:                                   # noqa: BLE001
            pass
        return None, True
    except Exception:                                       # noqa: BLE001
        try:
            f.close()
        except Exception:                                   # noqa: BLE001
            pass
        return None, False
    try:
        f.seek(0)
        f.truncate()
        f.write(str(os.getpid()))
        f.flush()
    except Exception:                                       # noqa: BLE001
        pass
    _LOCK = f                    # 살려 둬야 한다. 닫히면 잠금이 풀린다
    return f, False


def single_release(handle):
    global _LOCK
    _LOCK = None
    try:
        handle.close()           # 닫으면 flock 도 같이 풀린다
    except Exception:                                       # noqa: BLE001
        pass


def data_dir(app_name=APP_NAME):
    """맥 관례 자리. 옛 자리(~/poketdesktop)가 있으면 통째로 옮긴다."""
    base = os.path.expanduser("~/Library/Application Support")
    d = os.path.join(base, app_name)
    old = os.path.join(os.path.expanduser("~"), app_name)
    if not os.path.isdir(d) and os.path.isdir(old):
        try:
            os.makedirs(base, exist_ok=True)
            os.rename(old, d)
        except OSError:
            return old           # 못 옮기면 옛 자리를 그대로 쓴다
    os.makedirs(d, exist_ok=True)
    return d


_machine = None


def machine_raw():
    """맥판 MachineGuid — 이 기기에 박힌 UUID.

    `uuid.getnode()` 로 가면 안 된다. 맥에는 고정 MAC 이 없는 기기가
    많아서 파이썬이 `ifconfig` 출력의 첫 줄을 집는데, 와이파이 주소는
    사설 랜덤이고 awdl0 는 쓰는 중에도 바뀐다. 기기 ID 가 바뀌면 서버가
    자동 로그인을 거절해서 사용자가 영문도 모르고 로그아웃된다.

    **한 번 구한 값은 이 실행 동안 그대로 쓴다.** 그리고 길을 둘 둔다 -
    ioreg 는 프로세스를 띄우는 일이라 PATH·샌드박스·타임아웃 어느 하나만
    어긋나도 실패하는데, 그때마다 기기 ID 가 바뀌면 안 되기 때문이다.
    libSystem 의 gethostuuid 는 같은 값을 프로세스 안에서 바로 준다.
    """
    global _machine
    if _machine:
        return _machine
    _machine = _hostuuid() or _ioreg_uuid()
    return _machine


def _hostuuid():
    """libSystem 의 gethostuuid(2). 프로세스를 안 띄운다."""
    try:
        buf = (ctypes.c_ubyte * 16)()
        wait = (ctypes.c_int64 * 2)(0, 0)          # timespec {0, 0} = 안 기다림
        libc = ctypes.CDLL("/usr/lib/libSystem.dylib")
        if libc.gethostuuid(buf, wait) != 0:
            return None
        import uuid as _uuid
        return str(_uuid.UUID(bytes=bytes(buf))).upper()
    except Exception:                                       # noqa: BLE001
        return None


def _ioreg_uuid():
    import subprocess

    try:
        out = subprocess.run(
            ["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True, text=True, timeout=5).stdout
        for line in out.splitlines():
            if "IOPlatformUUID" in line:
                v = line.split('"')[3].strip()
                if v:
                    return v
    except Exception:                                       # noqa: BLE001
        pass
    return None


def dpi_aware():
    """맥은 알아서 한다."""
    pass


def hide_from_dock():
    """Dock 과 앱 전환기(Cmd+Tab)에서 감춘다. 메뉴 막대 아이콘만 남는다.

    이 게임은 켜 두고 잊어버리는 것이라, Dock 한 칸을 계속 차지하면
    안 된다. 윈도우판도 작업표시줄에 안 뜬다.

    **`tk.Tk()` 를 만든 뒤에 불러야 한다.** Tk 이 초기화하면서 정책을
    Regular 로 돌려놓기 때문이다.

    Accessory 정책이 되면 우리 창은 저절로 앞에 오지 않는다. 창을 띄울
    때 `activate()` 를 같이 불러야 글자를 칠 수 있다.
    """
    if not _ok:
        return
    try:
        app = AppKit.NSApplication.sharedApplication()
        app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    except Exception:                                       # noqa: BLE001
        pass
    # Dock 에서 숨기면 앱이 거의 늘 비활성이 된다. 그러면 창을 처음
    # 누르는 클릭을 맥이 가로채므로 같이 손봐 둔다.
    accept_first_click()
    # 그리고 제멋대로 앞으로 나오지 못하게 막는다.
    keep_focus()


_first_mouse = None            # None=아직, True=걸었음, False=못 걸었음


def accept_first_click():
    """앱이 앞에 나와 있지 않아도 **첫 클릭을 그대로 받는다.**

    맥은 활성 상태가 아닌 앱의 창을 처음 누르면 그 클릭을 "앱을 앞으로
    꺼내는 것" 에만 쓰고 창에는 주지 않는다. 이 게임은 Dock 에 안 뜨는
    앱이라 거의 항상 비활성이다. 그래서 포켓몬을 한 번 눌러 앱을 깨우기
    전에는 **오른쪽 클릭이 통째로 안 먹었다.** 사용자 눈에는 "어쩔 때만
    메뉴가 나온다" 로 보인다.

    바탕화면에 떠 있는 도트를 누르는 것은 늘 '그냥 누르는 것' 이어야
    한다. 앱을 앞으로 꺼내려고 한 번 헛클릭을 시키면 안 된다.

    NSView 의 acceptsFirstMouse: 가 그걸 정하는데 Tk 에서는 못 건드린다.
    Tk 이 쓰는 뷰 클래스(TKContentView)에 그 메서드를 직접 붙인다.
    """
    global _first_mouse
    if _first_mouse is not None:
        return _first_mouse
    _first_mouse = False
    if not _ok:
        return False
    try:
        view = objc.lookUpClass("TKContentView")
    except Exception:                                       # noqa: BLE001
        _first_mouse = None     # 아직 창이 하나도 없다. 다음에 다시 한다.
        return False

    # **respondsToSelector 로 확인하면 안 된다.** NSView 에서 물려받은
    # 것도 True 라, 이미 걸렸다고 착각하고 그냥 넘어간다. 물려받은 것은
    # False 를 돌려주므로 우리가 덮어써야 한다.
    def acceptsFirstMouse_(self, event):
        return True

    for sig in (b"B@:@", b"c@:@"):
        try:
            objc.classAddMethods(view, [objc.selector(
                acceptsFirstMouse_, selector=b"acceptsFirstMouse:",
                signature=sig)])
            _first_mouse = True
            return True
        except Exception:                                   # noqa: BLE001
            continue
    return False


_rclick = []
_rclick_mon = None


def watch_right_click():
    """오른쪽 클릭을 Cocoa 단계에서 직접 받는다.

    **Tk 은 앱이 활성이 아닐 때 온 오른쪽 클릭을 위젯에 전달하지 않는다.**
    맥이 우리 앱에 주기는 하는데(로컬 감시자에는 찍힌다) 거기서 멎는다.
    이 게임은 Dock 에 안 뜨는 앱이라 거의 늘 비활성이므로, 그대로 두면
    **포켓몬을 한 번 왼쪽 클릭해 앱을 깨우기 전에는 우클릭이 통째로 안
    먹는다.** 실제로 그랬고, 그게 이 감시자를 두는 이유다.

    감시자는 **우리 앱에 전달된 것만** 본다. 도트 창이 클릭을 통과시키고
    있으면(빈 자리) 맥이 애초에 우리에게 안 주므로 여기도 안 걸린다 -
    그래서 따로 걸러낼 필요가 없다.

    Cocoa 콜백이라 **여기서 tkinter 를 부르면 안 된다.** 적어만 두고
    꺼내 쓰는 것은 Tk 쪽이 한다 (App._mac_clicks).
    """
    global _rclick_mon
    if not _ok or _rclick_mon is not None:
        return

    def handler(ev):
        try:
            p = AppKit.NSEvent.mouseLocation()
            _rclick.append((float(p.x), float(p.y), int(ev.windowNumber())))
        except Exception:                                   # noqa: BLE001
            pass
        return ev

    _rclick_mon = AppKit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
        AppKit.NSEventMaskRightMouseDown, handler)


def mouse_buttons_down():
    """지금 눌려 있는 마우스 단추 (없으면 0).

    Tk 이 '뗐다' 를 못 받는 일이 있어서(앱이 비활성일 때) 그것 없이도
    확인할 수 있는 길을 둔다. 안 그러면 도트가 눌린 채로 굳는다.
    """
    if not _ok:
        return 0
    try:
        return int(AppKit.NSEvent.pressedMouseButtons())
    except Exception:                                       # noqa: BLE001
        return 0


def take_right_clicks():
    """쌓인 오른쪽 클릭을 Tk 화면 좌표로 꺼낸다. [(x, y, 창번호), ...]"""
    out, _rclick[:] = list(_rclick), []
    if not out or not _ok:
        return []
    try:
        h0 = AppKit.NSScreen.screens()[0].frame().size.height
    except Exception:                                       # noqa: BLE001
        return []
    return [(int(round(x)), int(round(h0 - y)), n) for x, y, n in out]


_guard = None


def keep_focus():
    """**Tk 이 제멋대로 앞으로 나오지 못하게 막는다.**

    창을 새로 만들어 화면에 올릴 때 Tk 이 `activateIgnoringOtherApps:` 를
    부른다. 그래서 풀숲이 돋거나 야생 포켓몬이 나올 때마다 쓰던 앱의
    포커스가 풀렸다. 글을 쓰다가 갑자기 커서가 사라지는 식이다.

    바탕화면에서 도트가 걸어다니는 프로그램은 **스스로 앞으로 나오면
    안 된다.** 그래서 그 메서드를 통째로 막는다.

    막고 나면 우리도 못 나오게 되므로, 정말 앞으로 나와야 할 때는
    `activate()` 가 **다른 선택자**로 부른다 (아래를 보라).

    (원래 구현을 살려 두고 문지기만 세우려고 메서드 맞바꾸기도 해
     봤지만 안 먹었다. 통째로 막고 다른 문을 내는 편이 확실하다.)
    """
    global _guard
    if _guard is not None or not _ok:
        return _guard
    try:
        cls = objc.lookUpClass("TKApplication")
    except Exception:                                       # noqa: BLE001
        return None        # 아직 Tk 이 안 떴다. 다음에 다시.
    _guard = False

    def activateIgnoringOtherApps_(self, flag):
        return             # Tk 이 저 혼자 부르는 것. 아무것도 안 한다.

    for sig in (b"v@:B", b"v@:c"):
        try:
            objc.classAddMethods(cls, [objc.selector(
                activateIgnoringOtherApps_,
                selector=b"activateIgnoringOtherApps:", signature=sig)])
            _guard = True
            return True
        except Exception:                                   # noqa: BLE001
            continue
    return False


def activate():
    """우리 창을 앞으로 꺼낸다. **여기서만** 앞으로 나온다.

    `activateIgnoringOtherApps:` 는 keep_focus 가 막아 두었다. 다행히
    맥에는 인자 없는 `activate` 가 따로 있어서(macOS 14 부터), 그쪽은
    막힌 문을 지나간다. 없는 맥에서는 NSRunningApplication 으로 간다.
    """
    if not _ok:
        return
    app = AppKit.NSApplication.sharedApplication()
    if app.respondsToSelector_(b"activate"):
        try:
            app.activate()
            return
        except Exception:                                   # noqa: BLE001
            pass
    try:
        AppKit.NSRunningApplication.currentApplication().activateWithOptions_(
            AppKit.NSApplicationActivateIgnoringOtherApps)
    except Exception:                                       # noqa: BLE001
        pass


def before_tk():
    """`tk.Tk()` 를 만들기 **직전에** 부른다.

    ## 왜 필요한가 — 한 번 죽으면 다음부터 안 뜨는 문제

    프로그램이 비정상 종료되면 맥은 다음 실행 때 "이전에 열려 있던 창을
    복구할까요?" 하는 대화상자를 띄운다. 그런데 이게 **Tk 초기화 안에서**
    뜬다 (NSApplication 이 실행 마무리를 하는 도중이다). 대화상자가 뜬
    동안 `tk.Tk()` 가 그 자리에 멈춰 서고, 화면에 그 창이 안 보이는
    상황이면 영영 안 끝난다.

    이 프로그램은 켜 두고 잊어버리는 것이라 **컴퓨터를 켤 때 자동으로
    시작한다.** 한 번 죽고 나면 그 다음 부팅부터 아무 소리 없이 안 뜨고,
    사용자는 이유를 알 길이 없다. 그래서 아예 안 물어보게 해 둔다 -
    우리는 복구할 창이 없다. 창은 전부 우리가 다시 만든다.

    (실제로 이 문제를 만나 봤다. 스택 맨 위가
     `NSAlert runModal` <- `promptToIgnorePersistentState` <- `TkpInit` 이었다.)
    """
    if not _ok:
        return
    try:
        Foundation.NSUserDefaults.standardUserDefaults().registerDefaults_(
            {"ApplePersistenceIgnoreState": True,
             "NSQuitAlwaysKeepsWindows": False})
    except Exception:                                       # noqa: BLE001
        pass


# ---------------------------------------------------------------- 글꼴
def font_candidates():
    # 애플 기본 한글 글꼴. 굵기도 진짜 자소가 들어 있다.
    return ["Apple SD Gothic Neo", "AppleGothic"]


def pil_font_files(bold=False):
    files = ("AppleSDGothicNeo.ttc",
             "/System/Library/Fonts/AppleSDGothicNeo.ttc",
             "AppleGothic.ttf",
             "/System/Library/Fonts/Supplemental/AppleGothic.ttf")
    return files


def already_running_hint():
    return ("화면 위쪽 메뉴 막대에서\n"
            "몬스터볼 아이콘을 찾아보세요.")
