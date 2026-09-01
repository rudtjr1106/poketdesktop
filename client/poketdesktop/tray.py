# -*- coding: utf-8 -*-
"""트레이 아이콘 — 화면 오른쪽 아래 '숨겨진 아이콘 표시' 안에 뜬다.

pystray 는 자기 스레드에서 도는데 tkinter 는 다른 스레드에서 만지면 안 된다.
그래서 메뉴를 누르면 무조건 root.after 로 tk 스레드에 넘겨서 실행한다.
"""
import threading

import pystray
from PIL import Image, ImageDraw
from pystray import Menu, MenuItem

from common.version import VERSION

SIZE_PRESETS = [("작게", 36), ("보통", 48), ("크게", 64), ("아주 크게", 84)]
AREA_PRESETS = [("좁게", 360, 240), ("보통", 520, 360),
                ("넓게", 760, 520), ("화면 전체", 0, 0)]


def make_icon_image(size=64):
    """트레이 아이콘 — 컴퓨터 화면 안의 몬스터볼.

    작업표시줄·exe 와 같은 그림을 쓴다 (appicon 에서 한 번만 그린다).
    """
    from . import appicon
    return appicon.make(size)


class Tray(object):
    def __init__(self, app):
        self.app = app
        self.icon = None
        self._thread = None

    # ---- tk 스레드로 넘기기 ----
    def call(self, fn, *a):
        self.app.root.after(0, lambda: fn(*a))

    def _title(self):
        u = self.app.username or "로그인 안 됨"
        n = len(self.app.overlay.pets) if self.app.overlay else 0
        return "포켓 데스크톱 — %s   바탕화면 %d마리   몬스터볼 %d개" % (
            u, n, self.app.balls)

    # ---- 메뉴 ----
    def build_menu(self):
        a = self.app
        s = a.settings

        size_items = [
            MenuItem(label, (lambda v: lambda _i, _it: self.call(a.set_size, v))(v),
                     checked=(lambda v: lambda _it: s["targetHeight"] == v)(v),
                     radio=True)
            for label, v in SIZE_PRESETS]

        area_items = [
            MenuItem(label,
                     (lambda w, h: lambda _i, _it: self.call(a.set_area, w, h))(w, h),
                     checked=(lambda w, h: lambda _it: (
                         (s["areaW"], s["areaH"]) == (w, h) if w else s["areaW"] > 1200
                     ))(w, h),
                     radio=True)
            for label, w, h in AREA_PRESETS]

        return Menu(
            MenuItem("포켓몬 관리...", lambda _i, _it: self.call(a.open_box),
                     default=True),
            MenuItem("가방...", lambda _i, _it: self.call(a.open_bag)),
            MenuItem("친구...", lambda _i, _it: self.call(a.open_friends)),
            MenuItem("랜덤 배틀", lambda _i, _it: self.call(a.pvp_random)),
            MenuItem("상점...", lambda _i, _it: self.call(a.open_shop)),
            MenuItem("풀숲 찾아보기", lambda _i, _it: self.call(a.encounter_now)),
            Menu.SEPARATOR,
            MenuItem("바탕화면", Menu(
                MenuItem("모두 거두기", lambda _i, _it: self.call(a.recall_all)),
                MenuItem("무작위로 내보내기", lambda _i, _it: self.call(a.send_random)),
                Menu.SEPARATOR,
                MenuItem("이름표 보이기",
                         lambda _i, _it: self.call(a.toggle_names),
                         checked=lambda _it: bool(s.get("showNames"))),
            )),
            MenuItem("포켓몬 크기", Menu(*size_items)),
            MenuItem("활동 범위", Menu(*area_items)),
            Menu.SEPARATOR,
            MenuItem(lambda _it: "계정: %s" % (a.username or "-"), None,
                     enabled=False),
            MenuItem(lambda _it: "몬스터볼 %d개" % a.balls, None, enabled=False),
            MenuItem(lambda _it: "소지금 %s원" % format(getattr(a, "money", 0), ","),
                     None, enabled=False),
            MenuItem("버전 %s" % VERSION, None, enabled=False),
            MenuItem("만든 자료 출처", lambda _i, _it: self.call(a.open_credits)),
            MenuItem("서버 연결 확인", lambda _i, _it: self.call(a.check_server)),
            MenuItem("로그아웃", lambda _i, _it: self.call(a.logout)),
            MenuItem("회원탈퇴", lambda _i, _it: self.call(a.delete_account)),
            Menu.SEPARATOR,
            MenuItem("종료", lambda _i, _it: self.call(a.quit)),
        )

    # ---- 수명 ----
    def start(self):
        self.icon = pystray.Icon("poketdesktop", make_icon_image(),
                                 self._title(), self.build_menu())
        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()

    def refresh(self):
        if not self.icon:
            return
        try:
            self.icon.title = self._title()
            self.icon.update_menu()
        except Exception:
            pass

    def notify(self, message, title="포켓 데스크톱"):
        if not self.icon:
            return
        try:
            self.icon.notify(message, title)
        except Exception:
            pass

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
