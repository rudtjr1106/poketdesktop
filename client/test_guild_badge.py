# -*- coding: utf-8 -*-
"""길드 탭의 점과 코인 상점의 계산 (1.10.1). 창을 띄우지 않는다.

    python client/test_guild_badge.py

1.10.0 에서는 길드 탭을 한 번 열어야 점이 찍혔다 (그 탭의 웹소켓이 듣는 것이라).
프로그램을 켜고 다른 탭만 보던 사람은 채팅이 온 줄 몰랐다. 이제 앱이 안다:

  · 동기화(/api/me)에 '남이 쓴 가장 최근 줄의 번호' 가 실려 온다 - 본 데보다 뒤면 점.
  · 길드 탭이 안 떠 있는 동안에는 앱이 웹소켓을 하나 붙여 오는 즉시 안다.
    탭이 뜨면 그 탭의 웹소켓이 듣고, 앱의 것은 끊는다 (한 PC 에 연결 하나).
  · 채팅 칸에서 읽으면 거기까지 '본 것' 이 된다. 길드 탭을 보고 있는 동안에는 점이 없다.

App 의 실제 메서드를 빌려 쓴다 (test_new_settings 와 같은 방식).
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-guildbadge-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop import ui_guild                              # noqa: E402
from poketdesktop.app import App                               # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Hub(object):
    def __init__(self):
        self.panes, self.badges = {}, []

    def set_badge(self, key, on):
        self.badges.append((key, on))


class Pane(object):
    def __init__(self, visible=True):
        self.alive, self.visible = True, visible

    def pane_visible(self):
        return self.visible


class Sock(object):
    def __init__(self, on_event):
        self.on_event, self.stopped, self.gave_up = on_event, False, None

    def stop(self):
        self.stopped = True


class FakeApp(object):
    def __init__(self, hub=True):
        self.settings = {"guildChatSeen": 0}
        self.hub = Hub() if hub else None
        self.user_id = 7
        self.guild_id, self.guild_chat, self.guild_sock, self._guild_dot = None, 0, None, None

    # App 의 실제 메서드를 빌려 쓴다 (가짜로 다시 쓰지 않는다)
    _guild_pane = App._guild_pane
    guild_unseen = App.guild_unseen
    note_guild = App.note_guild
    note_guild_chat = App.note_guild_chat
    mark_guild_chat_seen = App.mark_guild_chat_seen
    _paint_guild = App._paint_guild
    _watch_guild = App._watch_guild
    _stop_guild_sock = App._stop_guild_sock
    _on_guild_ws = App._on_guild_ws


def main():
    socks = []

    def make_socket(app, on_event):
        socks.append(Sock(on_event))
        return socks[-1]
    ui_guild.make_socket = make_socket

    print("=== 동기화에 실려 온 번호 ===")
    app = FakeApp()
    app.note_guild(None)
    chk("길드가 없으면 점도 연결도 없다", app.hub.badges in ([], [("guild", False)]) and not socks
        and not app.guild_unseen, (app.hub.badges, len(socks)))
    app.note_guild({"id": 1, "chat": 5})
    chk("남이 쓴 줄이 본 데보다 뒤면 길드 탭에 점", app.guild_unseen and app.hub.badges[-1] == ("guild", True),
        app.hub.badges)
    chk("  길드 탭이 안 떠 있으니 앱이 웹소켓을 붙인다", len(socks) == 1 and app.guild_sock is socks[0])
    n = len(app.hub.badges)
    app.note_guild({"id": 1, "chat": 5})
    chk("같은 값이 또 와도 탭을 다시 건드리지 않고 연결도 하나", len(app.hub.badges) == n and len(socks) == 1)

    print("\n=== 읽으면 지운다 ===")
    app.mark_guild_chat_seen(5)
    chk("채팅 칸에서 거기까지 읽으면 점이 꺼진다", app.hub.badges[-1] == ("guild", False)
        and app.settings["guildChatSeen"] == 5 and not app.guild_unseen, app.hub.badges)
    app.mark_guild_chat_seen(3)
    chk("  본 데는 뒤로 물리지 않는다", app.settings["guildChatSeen"] == 5)
    from poketdesktop import config
    chk("  껐다 켜도 남게 설정에 적는다", config.load_settings().get("guildChatSeen") == 5,
        config.load_settings().get("guildChatSeen"))

    print("\n=== 웹소켓으로 온 줄 ===")
    socks[0].on_event({"t": "chat", "m": {"id": 6, "userId": 7, "system": False}})
    chk("내가 쓴 줄로는 점이 안 찍힌다", not app.guild_unseen and app.hub.badges[-1] == ("guild", False))
    socks[0].on_event({"t": "chat", "m": {"id": 7, "userId": None, "system": True}})
    chk("알림 줄(가입·미션)로도 안 찍힌다", not app.guild_unseen)
    socks[0].on_event({"t": "chat", "m": {"id": 9, "userId": 3, "system": False}})
    chk("남이 쓴 줄이 오면 바로 찍힌다", app.guild_unseen and app.guild_chat == 9
        and app.hub.badges[-1] == ("guild", True), (app.guild_chat, app.hub.badges[-2:]))
    app.note_guild({"id": 1, "chat": 8})
    chk("동기화가 한발 늦은 번호를 줘도 뒤로 물리지 않는다", app.guild_chat == 9 and app.guild_unseen)

    print("\n=== 길드 탭이 떠 있을 때 ===")
    pane = Pane(visible=True)
    app.hub.panes["guild"] = pane
    app.note_guild({"id": 1, "chat": 9})
    chk("길드 탭을 보고 있으면 안 읽은 줄이 있어도 점은 없다", app.guild_unseen
        and app.hub.badges[-1] == ("guild", False), app.hub.badges[-2:])
    chk("  탭이 떠 있으면 앱의 웹소켓은 끊는다 (그 탭의 것이 듣는다)", socks[0].stopped and app.guild_sock is None)
    pane.visible = False
    app._paint_guild()
    chk("다른 탭으로 가면(안 읽은 채로) 점이 다시 찍힌다", app.hub.badges[-1] == ("guild", True))
    pane.alive = False
    app.note_guild({"id": 1, "chat": 9})
    chk("탭이 닫히면 앱이 다시 듣는다", len(socks) == 2 and app.guild_sock is socks[1] and not socks[1].stopped)

    print("\n=== 길드에서 나왔다 ===")
    socks[1].on_event({"t": "left"})
    chk("'나왔다' 가 오면 연결을 끊는다", socks[1].stopped and app.guild_sock is None)
    app.note_guild(None)
    chk("길드가 없어지면 점도 꺼진다", not app.guild_unseen and app.guild_chat == 0
        and app.hub.badges[-1] == ("guild", False) and app.guild_id is None, app.hub.badges[-2:])
    app.note_guild({"id": 2, "chat": 3})
    chk("다른 길드에 들어가면 그 길드의 번호로 다시 센다 (본 데 5 보다 앞이면 점 없음)",
        app.guild_chat == 3 and not app.guild_unseen and len(socks) == 3, (app.guild_chat, len(socks)))
    socks[2].gave_up = 4404
    app.note_guild({"id": 2, "chat": 3})
    chk("서버가 '다시 오지 마라' 로 끊은 연결은 새로 만든다", len(socks) == 4 and socks[2].stopped)

    print("\n=== 창이 없을 때 ===")
    bare = FakeApp(hub=False)
    bare.note_guild({"id": 1, "chat": 4})
    bare.note_guild_chat(6)
    bare.mark_guild_chat_seen(6)
    chk("허브 창이 없어도 안 터진다 (번호만 기억한다)", bare.guild_chat == 6 and not bare.guild_unseen)
    bare.note_guild({"id": 1, "chat": "이상한 값"})
    chk("이상한 값이 와도 안 터진다", bare.guild_chat in (0, 6))

    print("\n=== 코인 상점: 찾기와 줄 수 ===")
    items = [{"id": "POKEBALL", "kr": "몬스터볼"}, {"id": "RARECANDY", "kr": "이상한사탕"},
             {"id": "HPUP", "kr": "맥스업"}]
    chk("이름 일부로 찾는다", [i["id"] for i in items if ui_guild.shop_match(i, "볼")] == ["POKEBALL"])
    chk("띄어쓰기·대소문자는 안 가린다", ui_guild.shop_match(items[1], " 이상한 사탕 ")
        and ui_guild.shop_match(items[2], "hpup") and ui_guild.shop_match(items[2], "HP"))
    chk("빈 말이면 전부", all(ui_guild.shop_match(i, "") and ui_guild.shop_match(i, None) for i in items))
    chk("없는 말이면 안 맞는다", not any(ui_guild.shop_match(i, "마스터") for i in items))
    chk("한 줄에 2~4장: 폭 %d 에 한 장씩" % ui_guild.SHOP_CARD_W,
        [ui_guild.shop_cols(w) for w in (0, 300, 470, 700, 930, 2000)] == [3, 2, 2, 3, 4, 4],
        [ui_guild.shop_cols(w) for w in (0, 300, 470, 700, 930, 2000)])
    chk("다른 길드 칸이 있다", [k for k, _l in ui_guild.TABS]
        == ["chat", "members", "mission", "shop", "guilds", "manage"], ui_guild.TABS)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
