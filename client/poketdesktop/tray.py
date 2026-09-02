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
        return "포스크탑 — %s   바탕화면 %d마리   몬스터볼 %d개" % (
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
            # 이제 창이 하나다. 메뉴는 어느 탭으로 열지만 고른다.
            MenuItem("열기...", lambda _i, _it: self.call(a.open_box),
                     default=True),
            MenuItem("바로 가기", Menu(
                MenuItem("포켓몬 관리", lambda _i, _it: self.call(a.open_box)),
                MenuItem("가방", lambda _i, _it: self.call(a.open_bag)),
                MenuItem("상점", lambda _i, _it: self.call(a.open_shop)),
                MenuItem("도감", lambda _i, _it: self.call(a.open_dex)),
                MenuItem("친구", lambda _i, _it: self.call(a.open_friends)),
                MenuItem("설정", lambda _i, _it: self.call(a.open_settings)),
                MenuItem("대전", lambda _i, _it: self.call(a.open_pvp)),
            )),
            MenuItem("랜덤 배틀", lambda _i, _it: self.call(a.pvp_random)),
            # 알림을 안 띄우기로 했으니, 놓치면 안 되는 것은 메뉴에
            # 남는다. 상대가 걸어온 대전은 화면에 아무 자국도 없어서
            # 여기 없으면 알 길이 없다.
            MenuItem(lambda _it: ("받은 대전 보기  (%d)" % a.pvp_unseen
                                  if getattr(a, "pvp_unseen", 0)
                                  else "받은 대전 보기"),
                     lambda _i, _it: self.call(a.open_pvp)),
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
            # 볼과 소지금은 가방·상점 창에 이미 크게 떠 있다. 메뉴에
            # 또 두면 길기만 하다. 여기는 버전 하나로 줄인다.
            MenuItem("버전 %s" % VERSION, None, enabled=False),
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

    # 윈도우 알림(토스트)은 쓰지 않는다. 켜 두고 잊어버리는 프로그램이라
    # 무슨 일이 있을 때마다 화면 구석에서 튀어나오면 하던 일을 방해한다.
    # 무슨 일이 있었는지는 메뉴 안에 한 줄로 남고, 기록에도 남는다.

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
