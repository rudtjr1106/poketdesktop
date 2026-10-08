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

from poketdesktop import config, ui_guild, ui_hub              # noqa: E402
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


class Box(object):
    """채팅 칸 흉내 (화면에 보이나, 끝으로 내리기)."""
    def __init__(self):
        self.viewable = True

    def winfo_viewable(self):
        return self.viewable

    def see(self, _index):
        pass

    def update_idletasks(self):
        pass

    def yview(self, *_a):
        return (0.5, 1.0)             # 줄이 넉넉해서 맨 위가 아니다 (앞의 줄을 더 받지 않는다)


class Cell(object):
    def __init__(self):
        self.text = None

    def configure(self, text=None, **_kw):
        self.text = text


class Seg(object):
    def __init__(self):
        self.cells = {"chat": Cell()}


class Api(object):
    def __init__(self):
        self.reply = {}

    def guild_chat(self, _after):
        return self.reply


class Win(object):
    """길드 창 흉내. **채팅을 받고 읽음을 알리는 함수는 GuildWindow 의 진짜 것**을 빌려 쓴다."""
    _poll_chat = ui_guild.GuildWindow._poll_chat
    _add_lines = ui_guild.GuildWindow._add_lines
    _tell_app = ui_guild.GuildWindow._tell_app
    _on_ws = ui_guild.GuildWindow._on_ws
    _paint_unread = ui_guild.GuildWindow._paint_unread
    chat_visible = ui_guild.GuildWindow.chat_visible

    def __init__(self, app):
        self.app, self.root = app, None
        app.api = Api()
        self.alive, self.mode, self.tab, self.live = True, "guild", "chat", True
        self.chat_box, self.chat_last, self.chat_ready = Box(), 0, False
        # 거슬러 받기 (1.10.3) 가 보는 것들. 이 검사는 탭의 점만 본다 - 줄을 그리지는 않는다.
        self.chat_rows, self.chat_more, self.chat_days, self.chat_first = [], False, 0, 0
        self._chat_busy, self._pending, self._stamp = False, [], "s"
        self.my_id, self.unread, self.shown, self.seg = app.user_id, 0, True, Seg()
        self.badged = []

    def _append(self, _msgs):
        pass

    def _prepend(self, _msgs, _more):
        pass

    def _want_older(self):
        pass

    def pane_visible(self):
        return self.shown

    def _badge(self, on):
        self.badged.append(on)

    def load(self, quiet=False):
        pass

    def say(self, *_a, **_k):
        pass


class Nb(object):
    def __init__(self):
        self.at = 0

    def index(self, _what):
        return self.at


class TkWin(object):
    def __init__(self):
        self.jobs = []

    def after(self, ms, fn):
        self.jobs.append((ms, fn))


class FakeHub(Hub):
    """허브 흉내. 탭이 바뀔 때 하는 일(_on_tab)은 HubWindow 의 진짜 것."""
    _on_tab = ui_hub.HubWindow._on_tab
    _key_at = ui_hub.HubWindow._key_at

    def __init__(self, app):
        Hub.__init__(self)
        self.app, self.nb, self.root = app, Nb(), TkWin()
        self.order = [t[0] for t in ui_hub.TABS]
        self.built = []

    def _build(self, key):
        self.built.append(key)


class FakeApp(object):
    def __init__(self, hub=True, settings=None, uid=7):
        # 기본은 '이 계정·이 길드를 이미 아는 PC' 다 (처음 보는 PC 는 따로 본다)
        self.settings = {"guildChatSeen": 0, "guildChatFor": "7:1"} if settings is None \
            else dict(settings)
        self.hub = Hub() if hub else None
        self.user_id = uid
        self.guild_id, self.guild_chat, self.guild_sock, self._guild_dot = None, 0, None, None
        self.friendly = None              # 길드 친선전 (1.10.3) - 길드에 들어 있는 동안만 있다

    # App 의 실제 메서드를 빌려 쓴다 (가짜로 다시 쓰지 않는다)
    _guild_pane = App._guild_pane
    guild_unseen = App.guild_unseen
    note_guild = App.note_guild
    _guild_first_sight = App._guild_first_sight
    note_guild_chat = App.note_guild_chat
    mark_guild_chat_seen = App.mark_guild_chat_seen
    _paint_guild = App._paint_guild
    _watch_guild = App._watch_guild
    guild_friendly = App.guild_friendly
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
    chk("다른 길드에 들어가면 그 길드의 번호로 다시 센다 (거기까지는 본 것으로 친다)",
        app.guild_chat == 3 and not app.guild_unseen and len(socks) == 3
        and app.settings["guildChatSeen"] == 3 and app.settings["guildChatFor"] == "7:2",
        (app.guild_chat, len(socks), app.settings))
    socks[2].gave_up = 4404
    app.note_guild({"id": 2, "chat": 3})
    chk("서버가 '다시 오지 마라' 로 끊은 연결은 새로 만든다", len(socks) == 4 and socks[2].stopped)

    print("\n=== 이 PC 가 처음 보는 길드 채팅 (1.10.2) ===")
    # 운영에서 있던 그대로다: 내 길드(1번)의 남이 쓴 마지막 줄은 110번이고 나는 이미 읽었다.
    # 그 뒤 111~124번은 전부 **다른 길드(2번)** 의 줄이다. 1.10.1 로 올리고 처음 켜면 '본 데'
    # 가 0 이라 110 > 0 으로 점이 켜졌다 - 내 길드에는 새 말이 없는데 점이 떠서, 다른 길드에
    # 일이 생기면 뜨는 것처럼 보였다.
    new = FakeApp(settings={}, uid=27)
    new.note_guild({"id": 1, "chat": 110})
    chk("처음 켠 PC: 이미 있던 줄로는 점이 안 켜진다", not new.guild_unseen
        and ("guild", True) not in new.hub.badges, (new.settings, new.hub.badges))
    chk("  거기까지를 본 것으로 적고, 누구의 어느 길드 것인지도 적는다",
        new.settings.get("guildChatSeen") == 110 and new.settings.get("guildChatFor") == "27:1",
        new.settings)
    chk("  껐다 켜도 남는다", config.load_settings().get("guildChatFor") == "27:1"
        and config.load_settings().get("guildChatSeen") == 110, config.load_settings())
    new.note_guild({"id": 1, "chat": 110})
    chk("  다른 길드에 줄이 아무리 쌓여도(111~124) 내 번호는 그대로라 점이 없다", not new.guild_unseen)
    socks[-1].on_event({"t": "chat", "m": {"id": 126, "userId": 36, "system": False}})
    chk("그 뒤 내 길드에서 남이 말하면 점이 켜진다", new.guild_unseen
        and new.hub.badges[-1] == ("guild", True), new.hub.badges[-2:])
    new.note_guild({"id": 1, "chat": 126})
    chk("  다음 동기화가 그걸 다시 '본 것' 으로 덮지 않는다", new.guild_unseen
        and new.settings["guildChatSeen"] == 110, new.settings)

    old = FakeApp(settings={"guildChatSeen": 105})
    old.note_guild({"id": 1, "chat": 110})
    chk("1.10.1 에서 읽어 둔 번호는 그대로 쓴다 (그 뒤의 줄은 안 읽은 줄)", old.guild_unseen
        and old.settings["guildChatSeen"] == 105 and old.settings["guildChatFor"] == "7:1",
        old.settings)

    other = FakeApp(settings={"guildChatSeen": 124, "guildChatFor": "9:2"})
    other.note_guild({"id": 1, "chat": 110})
    chk("같은 PC 에서 다른 계정으로 들어오면 그 계정의 번호로 새로 잡는다",
        not other.guild_unseen and other.settings["guildChatSeen"] == 110
        and other.settings["guildChatFor"] == "7:1", other.settings)

    anon = FakeApp(settings={}, uid=None)
    anon.note_guild({"id": 1, "chat": 110})
    chk("내 번호를 아직 모르면 아무것도 적지 않는다 (엉뚱한 주인으로 적지 않는다)",
        "guildChatFor" not in anon.settings, anon.settings)

    print("\n=== 채팅 칸이 뜨는 순간 읽은 것으로 (1.10.2) ===")
    # 1.10.1 은 2초마다 도는 틱에서만 '읽었다' 를 적었다. 채팅을 흘끗 보고 바로 다른 칸으로
    # 가면 안 읽은 채로 남아, 길드 탭을 나온 뒤(다음 동기화 때) 점이 다시 켜졌다.
    ui_guild.run_async = lambda _root, fn, done: done(fn(), None)       # 바로 답이 온다
    me = FakeApp(settings={"guildChatSeen": 100, "guildChatFor": "27:1"}, uid=27)
    me.note_guild({"id": 1, "chat": 110})
    win = Win(me)
    me.hub.panes["guild"] = win
    chk("(준비) 안 읽은 줄이 있다", me.guild_unseen)
    me.api.reply = {"guild": 1, "last": 125, "stamp": "s", "messages": [
        {"id": 110, "userId": 36, "name": "남", "body": "ㅎ", "system": False},
        {"id": 125, "userId": None, "name": "", "body": "미션 달성", "system": True}]}
    win._poll_chat(first=True)
    chk("채팅을 다 받으면 틱을 기다리지 않고 거기까지 읽은 것으로 적는다",
        me.settings["guildChatSeen"] == 125 and not me.guild_unseen, me.settings)
    win._on_ws({"t": "chat", "m": {"id": 126, "userId": 36, "name": "남", "body": "새 말",
                                    "system": False}})
    chk("채팅 칸을 보는 중에 온 줄도 바로 읽은 것이 된다", me.settings["guildChatSeen"] == 126
        and not me.guild_unseen, me.settings)
    win.chat_box.viewable = False
    win.shown = False                        # 다른 탭으로 갔다
    win._on_ws({"t": "chat", "m": {"id": 127, "userId": 36, "name": "남", "body": "또",
                                    "system": False}})
    chk("안 보는 동안 온 줄은 읽은 것이 아니다 (점이 켜진다)", me.settings["guildChatSeen"] == 126
        and me.guild_unseen and me.hub.badges[-1] == ("guild", True), (me.settings, me.hub.badges[-2:]))

    print("\n=== 다른 칸을 보고 있을 때 '채팅' 칸의 표시 ===")
    win.tab, win.chat_box, win.shown, win.unread = "shop", None, True, 0
    win._paint_unread()
    chk("안 읽은 줄이 남았으면 '채팅' 칸 이름에 점 (무엇이 안 읽혔는지 알 수 있다)",
        win.seg.cells["chat"].text == "채팅 ●", win.seg.cells["chat"].text)
    win.unread = 2
    win._paint_unread()
    chk("  세어 둔 수가 있으면 수를 쓴다", win.seg.cells["chat"].text == "채팅 2")
    me.mark_guild_chat_seen(127)
    win.unread = 0
    win._paint_unread()
    chk("  다 읽었으면 그냥 '채팅'", win.seg.cells["chat"].text == "채팅")

    print("\n=== 탭을 옮기면 점을 바로 다시 그린다 ===")
    # 1.10.1 은 길드 탭에서 나와도 다음 동기화(최대 90초 뒤)에야 점을 다시 찍었다 -
    # 아무 일도 없는데 한참 뒤에 점이 켜지니 남의 길드 일로 켜지는 것처럼 보였다.
    walker = FakeApp(settings={"guildChatSeen": 100, "guildChatFor": "7:1"})
    walker.hub = FakeHub(walker)
    pane = Pane(visible=True)
    walker.hub.panes["guild"] = pane
    walker.note_guild({"id": 1, "chat": 110})
    chk("(준비) 길드 탭을 보는 동안에는 점이 없다", walker.hub.badges[-1] == ("guild", False))
    pane.visible = False                     # 다른 탭을 눌렀다
    walker.hub._on_tab()
    for _ms, fn in walker.hub.root.jobs:
        fn()
    chk("길드 탭에서 나오면 안 읽은 줄이 남았을 때 점이 바로 찍힌다",
        walker.hub.badges[-1] == ("guild", True) and walker.hub.built, walker.hub.badges)
    pane.visible = True
    walker.hub.root.jobs = []
    walker.hub._on_tab()
    for _ms, fn in walker.hub.root.jobs:
        fn()
    chk("길드 탭으로 돌아오면 점이 바로 꺼진다", walker.hub.badges[-1] == ("guild", False))

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
    chk("칸: 채팅·길드원·미션·코인 상점·다른 길드·관리 (친선전은 칸이 아니다 - 채팅에서 한다)", [k for k, _l in ui_guild.TABS]
        == ["chat", "members", "mission", "shop", "guilds", "manage"], ui_guild.TABS)

    print("\n=== 길드 친선전 (1.10.3) ===")
    from poketdesktop import ui_spectate
    app.note_guild({"id": 1, "chat": 5})
    fr = app.friendly
    chk("길드에 들어 있는 동안 친선전을 들고 있다 (알림·구경용)", isinstance(fr, ui_spectate.Friendly))
    app.check_live = lambda: seen.append("live") if isinstance(seen, list) else None
    seen = []
    app._on_guild_ws({"t": "live"})
    app._on_guild_ws({"t": "friendly", "seeking": [], "fights": [], "limit": 3})
    chk("  앱의 웹소켓으로 온 친선전 소식은 그쪽으로 넘긴다 (탭이 없어도 알림이 뜬다)", seen == ["live"] and fr.view["limit"] == 3)
    app.note_guild(None)
    chk("  길드에서 나오면 치운다", app.friendly is None and fr.listeners == [])

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
