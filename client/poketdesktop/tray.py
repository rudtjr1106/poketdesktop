# -*- coding: utf-8 -*-
"""트레이 아이콘 — 화면 오른쪽 아래 '숨겨진 아이콘 표시' 안에 뜬다.

pystray 는 자기 스레드에서 도는데 tkinter 는 다른 스레드에서 만지면 안 된다.
그래서 메뉴를 누르면 무조건 root.after 로 tk 스레드에 넘겨서 실행한다.

## 맥은 pystray 를 못 쓴다

pystray 의 맥 백엔드는 `NSApplication.run()` 을 부른다. 그걸 별도
스레드에서 부르면 파이썬 예외도 못 남기고 프로세스가 그 자리에서 죽는다
(SIGTRAP). tkinter 도 메인 스레드를 쓰므로 자리를 비켜 줄 수도 없다.
그래서 맥은 `tray_mac.py` 가 NSStatusItem 을 직접 만든다.

**메뉴에 무엇이 들어가는지는 여기 한 곳에만 적는다** (`TrayBase.spec`).
양쪽에 따로 적어 두면 한쪽만 고치는 날이 반드시 온다. 백엔드는 그
목록을 자기 방식으로 그리기만 한다.
"""
import threading

from . import autostart
from common import patchnotes
from common.version import VERSION

# ---------------------------------------------------------------- 메뉴 서술
SEP = object()          # 구분선


class Item(object):
    """메뉴 한 줄. 어느 트레이 라이브러리에도 안 매인 형태로 적는다.

    text/checked/enabled 는 값이어도 되고 인자 없는 함수여도 된다.
    함수로 주면 메뉴를 열 때마다 다시 물어본다 (받은 대전 개수처럼
    수시로 바뀌는 것).
    """

    __slots__ = ("text", "action", "submenu", "checked", "enabled",
                 "default", "radio")

    def __init__(self, text, action=None, submenu=None, checked=None,
                 enabled=True, default=False, radio=False):
        self.text = text
        self.action = action
        self.submenu = submenu
        self.checked = checked
        self.enabled = enabled
        self.default = default
        self.radio = radio


def val(v):
    return v() if callable(v) else v

# 84px 짜리 "아주 크게" 는 뺐다. 바탕화면을 너무 가린다.
# 그래도 크게 하고 싶으면 설정 창의 슬라이더로 120 까지 올릴 수 있다.
SIZE_PRESETS = [("작게", 36), ("보통", 48), ("크게", 64)]
AREA_PRESETS = [("좁게", 360, 240), ("보통", 520, 360),
                ("넓게", 760, 520), ("화면 전체", 0, 0)]


def make_icon_image(size=64):
    """트레이 아이콘 — 컴퓨터 화면 안의 몬스터볼.

    작업표시줄·exe 와 같은 그림을 쓴다 (appicon 에서 한 번만 그린다).
    """
    from . import appicon
    return appicon.make(size)


class TrayBase(object):
    """양쪽 트레이가 같이 쓰는 것 — 제목과 메뉴 내용."""

    def __init__(self, app):
        self.app = app

    # ---- tk 스레드로 넘기기 ----
    def call(self, fn, *a):
        self.app.root.after(0, lambda: fn(*a))

    # ---- 알림 ----
    def toast(self, title, message):
        """운영체제 알림을 한 번 띄운다. 띄웠으면 True.

        **여기로 오는 것은 화면에 아무 자국도 남지 않는 일뿐이다** -
        새 버전과 친구 요청. 게임 안에서 벌어지는 일(잡았다, 레벨이
        올랐다)은 절대 여기로 보내지 않는다. 켜 두고 잊어버리는
        프로그램이라, 그런 것까지 구석에서 튀어나오면 하던 일을
        방해하고 결국 프로그램을 끄게 된다.

        띄울 수 없는 환경이면 조용히 False. 알림은 있으면 좋은 것이고,
        없다고 해서 하던 일이 멈춰서는 안 된다.
        """
        return False

    def _title(self):
        u = self.app.username or "로그인 안 됨"
        n = len(self.app.overlay.pets) if self.app.overlay else 0
        return "포스크탑 — %s   바탕화면 %d마리   몬스터볼 %d개" % (
            u, n, self.app.balls)

    # ---- 메뉴 ----
    def spec(self):
        a = self.app
        s = a.settings

        if a.api is None:
            # 아직 로그인 전이다(대개 부팅 직후 인터넷을 기다리는 중).
            # 아래 항목들은 전부 서버가 있어야 하는 일이라 눌러도 실패한다.
            # 그래도 아이콘은 떠 있어야 한다 - 아무것도 없으면 사용자는
            # "자동 시작이 안 됐다" 고 여기고 바탕화면 아이콘을 다시 누른다.
            return [
                Item("서버에 연결하는 중입니다...", enabled=False),
                Item("버전 %s" % VERSION, enabled=False),
                SEP,
                Item("종료", lambda: self.call(a.quit)),
            ]

        size_items = [
            Item(label, (lambda v: lambda: self.call(a.set_size, v))(v),
                 checked=(lambda v: lambda: s["targetHeight"] == v)(v),
                 radio=True)
            for label, v in SIZE_PRESETS]

        area_items = [
            Item(label,
                 (lambda w, h: lambda: self.call(a.set_area, w, h))(w, h),
                 checked=(lambda w, h: lambda: (
                     (s["areaW"], s["areaH"]) == (w, h) if w else s["areaW"] > 1200
                 ))(w, h),
                 radio=True)
            for label, w, h in AREA_PRESETS]

        return [
            # 이제 창이 하나다. 메뉴는 어느 탭으로 열지만 고른다.
            Item("열기...", lambda: self.call(a.open_box), default=True),
            # '바로 가기' 하위 메뉴는 뺐다. 창이 하나로 합쳐진 뒤로는
            # '열기...' 로 들어가서 탭을 고르면 되는데, 메뉴에 같은 것이
            # 일곱 줄 더 있으면 길기만 하다.
            Item("랜덤 배틀", lambda: self.call(a.pvp_random)),
            # 알림을 안 띄우기로 했으니, 놓치면 안 되는 것은 메뉴에
            # 남는다. 상대가 걸어온 대전은 화면에 아무 자국도 없어서
            # 여기 없으면 알 길이 없다.
            Item(lambda: ("받은 대전 보기  (%d)" % a.pvp_unseen
                          if getattr(a, "pvp_unseen", 0)
                          else "받은 대전 보기"),
                 lambda: self.call(a.open_pvp)),
            # 친구 요청도 화면에 자국이 없다. 알림을 껐거나 놓쳤을 때
            # 여기 숫자가 유일한 단서다.
            Item(lambda: ("친구 요청 보기  (%d)" % a.friend_unseen
                          if getattr(a, "friend_unseen", 0)
                          else "친구 요청 보기"),
                 lambda: self.call(a.open_friends)),
            SEP,
            Item("바탕화면", submenu=[
                Item("모두 거두기", lambda: self.call(a.recall_all)),
                Item("무작위로 내보내기", lambda: self.call(a.send_random)),
                SEP,
                Item("이름표 보이기", lambda: self.call(a.toggle_names),
                     checked=lambda: bool(s.get("showNames"))),
                # 걸어다니는 것만 보고 싶은 사람이 있다. 야생을 끄는
                # 자리가 메뉴에도 있어야 한다 - 설정 창까지 들어가야
                # 하면 있는 줄도 모른다.
                Item("풀숲 띄우기", lambda: self.call(a.toggle_grass),
                     checked=lambda: bool(s.get("showGrass", True))),
            ]),
            Item("포켓몬 크기", submenu=size_items),
            Item("활동 범위", submenu=area_items),
            # 켜 두고 잊어버리는 프로그램이라, 켤 때마다 손으로 켜야
            # 하면 그냥 안 켜게 된다. 여기에 둬야 손이 닿는다.
            # 켜져 있다고 표시되는데 실제로는 안 켜지는 상황(작업
            # 관리자에서 껐을 때)은 이름에 그대로 적는다.
            # 표시는 **레지스트리**를 보고 정한다. 설정 파일을 보면,
            # 등록이 실패했을 때 여기는 켜짐인데 설정 창은 꺼짐인
            # 정반대 화면이 나온다. 진실은 한 곳이어야 한다.
            Item(lambda: ("컴퓨터 켤 때 같이 시작  (%s)" % autostart.blocked_where()
                          if autostart.state()[0] == "blocked"
                          else "컴퓨터 켤 때 같이 시작"),
                 lambda: self.call(a.toggle_autostart),
                 checked=lambda: autostart.state()[0] in ("on", "blocked"),
                 enabled=autostart.supported()),
            SEP,
            # 볼과 소지금은 가방·상점 창에 이미 크게 떠 있다. 메뉴에
            # 또 두면 길기만 하다. 여기는 버전 하나로 줄인다.
            Item("버전 %s" % VERSION, enabled=False),
            Item("이번 버전 새로운 기능", lambda: self.call(a.show_patchnotes),
                 enabled=bool(patchnotes.entry(VERSION))),
            Item("로그아웃", lambda: self.call(a.logout)),
            Item("회원탈퇴", lambda: self.call(a.delete_account)),
            SEP,
            Item("종료", lambda: self.call(a.quit)),
        ]


# ---------------------------------------------------------------- pystray 판
class Tray(TrayBase):
    """윈도우(와 리눅스) 트레이. pystray 를 자기 스레드에서 돌린다."""

    def __init__(self, app):
        TrayBase.__init__(self, app)
        self.icon = None
        self._thread = None

    def _menu(self):
        import pystray
        from pystray import Menu, MenuItem

        def one(it):
            if it is SEP:
                return Menu.SEPARATOR
            text = it.text
            if callable(text):
                text = (lambda f: lambda _it: f())(text)
            checked = it.checked
            if checked is not None:
                checked = (lambda f: lambda _it: bool(val(f)))(checked)
            if it.submenu is not None:
                return MenuItem(text, Menu(*[one(x) for x in it.submenu]))
            action = None
            if it.action is not None:
                action = (lambda f: lambda _i, _it: f())(it.action)
            return MenuItem(text, action, checked=checked, radio=it.radio,
                            default=it.default, enabled=bool(val(it.enabled)))

        return Menu(*[one(x) for x in self.spec()])

    # ---- 수명 ----
    def start(self):
        import pystray
        self.icon = pystray.Icon("poketdesktop", make_icon_image(),
                                 self._title(), self._menu())
        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()

    def refresh(self):
        if not self.icon:
            return
        try:
            self.icon.title = self._title()
            # 메뉴도 다시 만든다. 로그인 전에 띄운 줄인 메뉴가 그대로 남아
            # 있으면 로그인한 뒤에도 "연결하는 중" 만 보인다.
            self.icon.menu = self._menu()
            self.icon.update_menu()
        except Exception:                                   # noqa: BLE001
            pass

    def toast(self, title, message):
        """윈도우 알림. pystray 가 트레이 아이콘으로 띄워 준다.

        아이콘이 아직 안 떴거나(로그인 전) 이 백엔드가 알림을 못 하면
        (리눅스 일부) 조용히 넘어간다. HAS_NOTIFICATION 을 먼저 보는
        이유가 그것이다 - 없는데 부르면 NotImplementedError 가 난다.
        """
        icon = self.icon
        if icon is None or not getattr(icon, "HAS_NOTIFICATION", False):
            return False
        try:
            icon.notify(message, title)
            return True
        except Exception:                                   # noqa: BLE001
            return False

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:                               # noqa: BLE001
                pass
            self.icon = None
