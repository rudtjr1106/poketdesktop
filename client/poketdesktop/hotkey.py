# -*- coding: utf-8 -*-
"""긴급 숨기기 단축키 (1.10.3) — 다른 프로그램을 쓰는 중에도 먹는 단축키 하나.

    hk = Hotkey()
    ok, why = hk.start("ctrl+alt+h")      # 등록. 못 하면 (False, 까닭)
    hk.fired()                            # 그사이 눌렸나 (물어보면 지워진다) - Tk 스레드에서 가끔 묻는다
    hk.stop()

## 키보드를 엿보지 않는다

이 프로그램은 **전역 키보드 훅을 쓰지 않는다** (SetWindowsHookEx, GetAsyncKeyState, 맥의
전역 이벤트 모니터). 그런 것은 모든 키 입력을 볼 수 있어서 백신이 키로거로 의심하고, 실제로도
남의 PC 에서 그러면 안 된다.

여기서 쓰는 것은 운영체제의 **단축키 등록**이다 - "이 조합이 눌리면 알려 달라" 고 맡겨 두면
그 조합이 눌렸다는 사실만 온다. 다른 키는 오지 않는다. 알림 창을 띄우는 프로그램·캡처
프로그램이 다 이 방식을 쓴다.

    윈도우   RegisterHotKey (자기 스레드에서 등록하고 WM_HOTKEY 를 기다린다)
    맥       Carbon 의 RegisterEventHotKey (접근성 권한이 필요 없다)

**기본은 꺼져 있다.** 설정에서 조합을 고른 사람에게만 등록한다.

## 고를 수 있는 조합

아무 조합이나 받지 않고 몇 가지 가운데 고르게 한다. 등록한 조합은 **다른 프로그램에 가지
않는다** - Ctrl+C 같은 것을 고르면 복사가 안 된다. 그래서 다른 프로그램이 잘 안 쓰는
Ctrl+Alt+글자 만 내놓는다. 이미 다른 프로그램이 등록한 조합이면 등록이 실패하고, 그렇게 알린다.
"""
import sys
import threading

# (설정에 적는 값, 윈도우에서 보이는 이름, 맥에서 보이는 이름)
CHOICES = (
    ("", "쓰지 않음", "쓰지 않음"),
    ("ctrl+alt+h", "Ctrl + Alt + H", "⌃ ⌥ H"),
    ("ctrl+alt+x", "Ctrl + Alt + X", "⌃ ⌥ X"),
    ("ctrl+alt+p", "Ctrl + Alt + P", "⌃ ⌥ P"),
    ("ctrl+alt+space", "Ctrl + Alt + Space", "⌃ ⌥ Space"),
)
KEYS = tuple(c[0] for c in CHOICES)
MAC = sys.platform == "darwin"
WIN = sys.platform.startswith("win")


def clean(combo):
    """설정에 적힌 값을 아는 조합으로. 모르는 값이면 빈 문자열(쓰지 않음)."""
    combo = str(combo or "").strip().lower()
    return combo if combo in KEYS else ""


def label(combo, mac=None):
    """화면에 적을 이름."""
    mac = MAC if mac is None else mac
    for key, win_name, mac_name in CHOICES:
        if key == clean(combo):
            return mac_name if mac else win_name
    return CHOICES[0][1]


def choices(mac=None):
    """[(값, 이름)] - 설정 창이 이 목록으로 고르는 칸을 만든다."""
    mac = MAC if mac is None else mac
    return [(key, mac_name if mac else win_name) for key, win_name, mac_name in CHOICES]


def parse(combo):
    """'ctrl+alt+h' -> ({'ctrl', 'alt'}, 'h'). 쓰지 않음이면 None."""
    combo = clean(combo)
    if not combo:
        return None
    parts = combo.split("+")
    return set(parts[:-1]), parts[-1]


def supported():
    return WIN or MAC


# ---------------------------------------------------------------- 윈도우
WIN_MODS = {"alt": 0x0001, "ctrl": 0x0002, "shift": 0x0004}
WIN_NOREPEAT = 0x4000         # 누르고 있어도 한 번만
WIN_KEYS = {"space": 0x20}    # 글자는 대문자의 코드가 곧 가상 키 코드다


def win_code(combo):
    """(modifiers, vk). RegisterHotKey 에 그대로 넣는다."""
    mods, key = parse(combo)
    m = WIN_NOREPEAT
    for name in mods:
        m |= WIN_MODS[name]
    return m, WIN_KEYS.get(key) or ord(key.upper())


class _Win(object):
    WM_HOTKEY, WM_QUIT = 0x0312, 0x0012

    def __init__(self, on_fire):
        self.on_fire = on_fire
        self.thread = None
        self.tid = 0

    def start(self, combo):
        import ctypes
        from ctypes import wintypes
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        mods, vk = win_code(combo)
        ready, result = threading.Event(), {}

        def loop():
            # 단축키는 **등록한 스레드의 대기열**로 온다. 그래서 등록도 기다리기도 이 스레드에서 한다.
            self.tid = kernel32.GetCurrentThreadId()
            ok = bool(user32.RegisterHotKey(None, 1, mods, vk))
            result["ok"] = ok
            ready.set()
            if not ok:
                return
            msg = wintypes.MSG()
            try:
                while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                    if msg.message == self.WM_HOTKEY:
                        self.on_fire()
            finally:
                user32.UnregisterHotKey(None, 1)
        self.thread = threading.Thread(target=loop, name="hotkey", daemon=True)
        self.thread.start()
        ready.wait(3.0)
        if not result.get("ok"):
            self.thread = None
            return False, "다른 프로그램이 이미 쓰고 있는 단축키입니다. 다른 조합을 골라 주세요."
        return True, ""

    def stop(self):
        t, self.thread = self.thread, None
        if t is None:
            return
        try:
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(self.tid, self.WM_QUIT, 0, 0)
            t.join(1.0)
        except Exception:                                   # noqa: BLE001
            pass


# ---------------------------------------------------------------- 맥
MAC_MODS = {"cmd": 0x0100, "shift": 0x0200, "alt": 0x0800, "ctrl": 0x1000}
MAC_KEYS = {"h": 4, "x": 7, "p": 35, "space": 49}          # ANSI 자판의 가상 키 코드


def mac_code(combo):
    """(keycode, modifiers). RegisterEventHotKey 에 그대로 넣는다."""
    mods, key = parse(combo)
    m = 0
    for name in mods:
        m |= MAC_MODS[name]
    return MAC_KEYS[key], m


class _Mac(object):
    """Carbon 의 단축키 등록. 눌리면 앱의 이벤트 처리 중에 handler 가 불린다 (Tk 스레드)."""

    def __init__(self, on_fire):
        self.on_fire = on_fire
        self.ref = None
        self._handler = None      # 놓으면 안 된다 (C 쪽이 들고 있는 함수다)
        self._installed = False

    def _lib(self):
        import ctypes
        lib = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
        lib.GetApplicationEventTarget.restype = ctypes.c_void_p
        lib.GetApplicationEventTarget.argtypes = []
        return ctypes, lib

    def start(self, combo):
        try:
            ctypes, lib = self._lib()

            class Spec(ctypes.Structure):
                _fields_ = [("cls", ctypes.c_uint32), ("kind", ctypes.c_uint32)]

            class HotKeyID(ctypes.Structure):
                _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]
            proto = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
            target = lib.GetApplicationEventTarget()
            if not self._installed:
                def handler(_call, _event, _data):
                    try:
                        self.on_fire()
                    except Exception:                       # noqa: BLE001
                        pass
                    return 0
                self._handler = proto(handler)
                spec = Spec(0x6B657962, 5)                  # 'keyb', kEventHotKeyPressed
                lib.InstallEventHandler.argtypes = [ctypes.c_void_p, proto, ctypes.c_ulong, ctypes.POINTER(Spec),
                                                    ctypes.c_void_p, ctypes.c_void_p]
                lib.InstallEventHandler.restype = ctypes.c_int32
                err = lib.InstallEventHandler(target, self._handler, 1, ctypes.byref(spec), None, None)
                if err:
                    return False, "단축키를 받을 준비를 하지 못했습니다. (%d)" % err
                self._installed = True
            code, mods = mac_code(combo)
            ref = ctypes.c_void_p()
            lib.RegisterEventHotKey.argtypes = [ctypes.c_uint32, ctypes.c_uint32, HotKeyID, ctypes.c_void_p,
                                                ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
            lib.RegisterEventHotKey.restype = ctypes.c_int32
            err = lib.RegisterEventHotKey(code, mods, HotKeyID(0x706B6470, 1), target, 0, ctypes.byref(ref))
            if err or not ref.value:
                return False, "다른 프로그램이 이미 쓰고 있는 단축키입니다. 다른 조합을 골라 주세요."
            self.ref = ref
            return True, ""
        except Exception as e:                              # noqa: BLE001
            return False, "이 맥에서는 단축키를 등록하지 못했습니다. (%s)" % e

    def stop(self):
        ref, self.ref = self.ref, None
        if ref is None:
            return
        try:
            ctypes, lib = self._lib()
            lib.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
            lib.UnregisterEventHotKey(ref)
        except Exception:                                   # noqa: BLE001
            pass


# ---------------------------------------------------------------- 겉
class Hotkey(object):

    def __init__(self):
        self._flag = threading.Event()
        self.combo = ""
        self.back = None

    def _fire(self):
        self._flag.set()          # 여기서는 표시만 한다. 일은 Tk 스레드가 fired() 로 물어보고 한다

    def start(self, combo):
        """그 조합을 등록한다. (됐나, 안 됐으면 까닭). 빈 조합이면 등록을 풀기만 한다."""
        self.stop()
        combo = clean(combo)
        if not combo:
            return True, ""
        if not supported():
            return False, "이 운영체제에서는 단축키를 쓸 수 없습니다."
        back = _Win(self._fire) if WIN else _Mac(self._fire)
        try:
            ok, why = back.start(combo)
        except Exception as e:                              # noqa: BLE001
            ok, why = False, "단축키를 등록하지 못했습니다. (%s)" % e
        if ok:
            self.back, self.combo = back, combo
        return ok, why

    def stop(self):
        back, self.back, self.combo = self.back, None, ""
        self._flag.clear()
        if back is not None:
            back.stop()

    def fired(self):
        """그사이 눌렸나. 물어보면 지워진다."""
        if self._flag.is_set():
            self._flag.clear()
            return True
        return False
