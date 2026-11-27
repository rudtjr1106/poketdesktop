# -*- coding: utf-8 -*-
"""친구 집에 놀러 가기 · 친구 채팅 화면 검사 (1.11.0).

    python client/test_visit_ui.py
    python client/run_as_windows.py client/test_visit_ui.py

**진짜 Overlay 와 도트 창을 띄운다.** 서버 대신 가짜 api·소켓을 쓴다 (서버 쪽은 server/test_visit).

못 박는 것 (10/15 사용자 교정 뒤):

  1. 입력: 말 / '/춤' 같은 명령 / 없는 명령을 가른다. **채팅 창은 없다.**
  2. 손님: 내 도트는 잠시 빠지고, 보낸 포켓몬이 **화면 오른쪽 밖에서 걸어 들어와** 오른쪽 아래에 선다.
     풀숲을 멈추고, 동기화가 내 도트를 다시 깔지 못하게 잠근다.
  3. 친구 포켓몬은 주인의 **파티대로만** 만들고(자리는 안 맞춘다) 스스로 돌아다닌다. 같은 파티가 다시 와도
     자리를 건드리지 않는다. 처음 보는 종은 도트를 먼저 받는다. 빠진 것은 치운다. 모습이 바뀌면 메가진화 연출,
     이름·레벨이 바뀌면 고친다.
  4. 내 포켓몬을 누르면 포커스, Enter 면 그 머리 위에 입력 말풍선. 치고 Enter 면 말풍선으로 말하고 보낸다,
     Esc 면 닫는다. 없는 명령은 안 보내고 알려 준다. 상대 말은 상대가 고른 포켓몬(모르면 맨 앞) 위에.
  5. 우클릭: 내 포켓몬에 '말하기' 와 끝내기 (놀러 간 포켓몬은 박스로 못 거둔다), 남의 포켓몬은 누구 것인지와 끝내기.
     놀러 간 쪽에는 '여기에 두기' (들고 온 것이 없으면 못 누른다). 처음에 우클릭으로 무엇을 하는지 알려 준다.
  5-1. 보따리: '여기에 두기' 창(가방 모양)에서 고른 것을 보낸다. 서버가 보따리를 주면 놀러 간 포켓몬 왼쪽 바닥에
     머리 위에서 떨어진다 (두 화면 모두). 주인이 누르면 받고 "OO 님에게 ~를 받았다!", 손님에게는 "OO 님이 보따리를
     받았다!". 손님이 누르면 안내만. 안 받은 채 끝나면 돌려받았다고 알린다.
  6. 끝나면 친구 도트를 치우고, 보낸 포켓몬은 오른쪽 밖으로 걸어 나갔다가 집에 오른쪽에서 걸어 들어온다.
     내 도트·풀숲·잠금을 되살린다.
  7. 주인: 놀러 온 포켓몬이 오른쪽 밖에서 걸어 들어와 오른쪽 아래에 선다. **파티가 바뀔 때만** 보낸다
     (자리 없이, 맨 앞 표시). 내 포켓몬 누구나 말할 수 있고 상대에게 그 포켓몬을 알린다. 끝나면 걸어 나간다.
  8. 들고 갈 도구 창 (가방 모양): 가방 줄을 누르면 하나씩 담기고, 가진 것보다·6가지보다 많이는 못 담는다.
     '여기에 두기' 창: 들고 온 것만, 오늘 줄 수 있는 만큼만 (넘으면 단추가 죽는다).
"""
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-visit-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402
import tkinter.font as tkfont                               # noqa: E402

from PIL import Image                                       # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import config, mega_fx, overlay           # noqa: E402
from poketdesktop import sprite_cache, walk_cache           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import visit as V                         # noqa: E402
from poketdesktop.app import App                            # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

HOME = os.environ["POKET_HOME"]
DEX = P.Pokedex.load(os.path.join(ROOT, "server", "data", "pokedex.json"))
PIKA, LIZ, SAUR, BLAST, MEGA_X = 25, 6, 3, 9, 10034
OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def settle(root, sec=0.15):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def wait(root, cond, sec=5.0):
    end = time.time() + sec
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.01)
    return cond()


def make_sheet(name, cell, color):
    path = os.path.join(HOME, name)
    im = Image.new("RGBA", (cell * 2, cell * 8), (0, 0, 0, 0))
    for row in range(8):
        for col in range(2):
            im.paste(Image.new("RGBA", (cell // 3, cell - 10), color), (col * cell + cell // 3, row * cell + 5))
    im.save(path)
    return path, {"ok": True, "frameW": cell, "frameH": cell, "durations": [8, 8]}


def make_dot(name, color):
    path = os.path.join(HOME, name)
    im = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    im.paste(Image.new("RGBA", (18, 24), color), (11, 8))
    im.save(path)
    return path


def mon(pid, num, slot, name):
    return {"id": pid, "num": num, "species": "X", "shiny": False, "slot": slot, "level": 30,
            "onDesktop": True, "info": {"name": name, "species": name, "level": 30, "types": []}}


class Sock(object):
    connected = True

    def __init__(self):
        self.sent = []

    def send(self, obj):
        self.sent.append(obj)
        return True

    def stop(self):
        pass


class Api(object):
    def __init__(self):
        self.calls = []
        self.start_reply = None
        self.state_visit = None

    def shop(self):
        return {"money": 0, "bag": {"GREATBALL": 7, "ULTRABALL": 2, "BLACKBELT": 2, "FOCUSSASH": 1,
                                    "MASTERBALL": 1, "FIRESTONE": 3},
                "items": [{"id": "GREATBALL", "kr": "슈퍼볼", "cat": "ball", "rarity": "uncommon"},
                          {"id": "ULTRABALL", "kr": "하이퍼볼", "cat": "ball", "rarity": "rare"},
                          {"id": "BLACKBELT", "kr": "검은띠", "cat": "held", "rarity": "uncommon"},
                          {"id": "FOCUSSASH", "kr": "기합의띠", "cat": "held", "rarity": "epic"},
                          {"id": "MASTERBALL", "kr": "마스터볼", "cat": "ball", "rarity": "legendary"},
                          {"id": "FIRESTONE", "kr": "불꽃의돌", "cat": "stone", "rarity": "common"}]}

    def visit_state(self):
        return {"visit": self.state_visit, "receivedToday": 0, "receivePerDay": 1, "ballMax": 5, "heldMax": 1,
                "rarities": ["common", "uncommon", "rare"]}

    def visit_start(self, friend, items, look):
        self.calls.append(("start", friend, items, look))
        return {"visit": self.start_reply}

    def visit_drop(self, items):
        self.calls.append(("drop", items))
        return {"bundle": {"id": 70, "items": items, "count": 1}}

    def visit_claim(self, bid):
        self.calls.append(("claim", bid))
        return {"bundle": {"id": bid, "items": [{"id": "BLACKBELT", "kr": "검은띠", "count": 1}], "count": 1,
                           "from": "손님"}}

    def visit_end(self):
        self.calls.append(("end",))
        return {"ended": True}


class Wild(object):
    def __init__(self):
        self.stops = self.starts = 0

    def stop(self):
        self.stops += 1

    def start(self):
        self.starts += 1


class MiniApp(object):
    """App 의 메가 걷기·우클릭 메뉴 메서드만 빌려 쓴다."""
    mega_ids = App.mega_ids
    mega_form = App.mega_form
    mega_menu_row = App.mega_menu_row
    toggle_mega_walk = App.toggle_mega_walk
    _box_look = App._box_look
    look_num = App.look_num
    pet_menu = App.pet_menu
    _pvp = App._pvp
    match_playing = App.match_playing      # _pvp 가 본다 (1.12.1)
    after_match = App.after_match
    _match_over = App._match_over
    _hit = staticmethod(App._hit)
    set_size = App.set_size

    def __init__(self, root, ov):
        self.root, self.overlay = root, ov
        self.api = Api()
        self.dex = DEX
        self.settings = ov.settings
        self.keystone = True
        self.arena = self.battle = None
        self._match_loading, self._after_match = False, []
        self.wild = Wild()
        self.notes, self.syncs, self.fetched = [], 0, []
        self.box_window = None
        self.visit = None
        self.bond_stones = type("Stones", (), {"apply": lambda _self: None})()

    def refresh_tray(self):
        pass

    def notify(self, m):
        self.notes.append(m)

    def request_sync(self):
        self.syncs += 1

    def _prefetch_anims(self, mons):
        self.fetched.append([overlay.look_num(m) for m in mons])

    def pet_open(self, pet):
        pass

    def _recall(self, pid):
        pass

    def open_box(self):
        pass

    def quit(self):
        pass


def menu_of(app, pet):
    """우클릭 메뉴의 줄 글 (그려지는 메뉴를 가로챈다 - 맥이든 윈도우든 같은 줄을 본다)."""
    got = []
    real_menu, real_native = U.PopupMenu, PLAT.NATIVE_MENU
    U.PopupMenu = lambda root, rows, x, y, width=None: got.append(rows)
    PLAT.NATIVE_MENU = False
    try:
        app.pet_menu(pet, type("E", (), {"x_root": 10, "y_root": 10})())
    finally:
        U.PopupMenu, PLAT.NATIVE_MENU = real_menu, real_native
    return [r.get("text") if r else None for r in (got[-1] if got else [])], (got[-1] if got else [])


class FakeMenu(object):
    """윈도우 우클릭 메뉴(tk.Menu) 대신: 넣은 줄만 적어 둔다 (맥에서 진짜 tk.Menu 를 띄우면 앱이 죽는다)."""
    made = []

    def __init__(self, *_a, **_k):
        self.rows, self.shown = [], False
        FakeMenu.made.append(self)

    def add_command(self, label="", command=None, state="normal"):
        self.rows.append({"text": label, "command": command, "state": state})

    def add_separator(self):
        self.rows.append(None)

    def tk_popup(self, *_a):
        self.shown = True

    def grab_release(self):
        pass


def native_menu_of(app, pet):
    """윈도우 길(PLAT.NATIVE_MENU)로 우클릭 메뉴를 열어 본다. (줄 글, 줄, 떴는지, 오류)"""
    real_menu, real_native = tk.Menu, PLAT.NATIVE_MENU
    tk.Menu, PLAT.NATIVE_MENU = FakeMenu, True
    FakeMenu.made = []
    err = None
    try:
        app.pet_menu(pet, type("E", (), {"x_root": 10, "y_root": 10})())
    except Exception as e:                                  # noqa: BLE001
        err = e
    finally:
        tk.Menu, PLAT.NATIVE_MENU = real_menu, real_native
    m = FakeMenu.made[-1] if FakeMenu.made else None
    rows = m.rows if m else []
    return [r["text"] if r else None for r in rows], rows, bool(m and m.shown), err


def guest_view(**kw):
    v = {"id": 7, "role": "guest", "host": 2, "guest": 1, "hostName": "집주인", "guestName": "나",
         "partner": "집주인", "mon": {"id": 1, "num": PIKA, "name": "피카츄", "level": 30}, "look": None,
         "carry": [{"id": "GREATBALL", "kr": "슈퍼볼", "count": 2}, {"id": "BLACKBELT", "kr": "검은띠", "count": 1}],
         "bundles": [], "canGive": True, "since": "x", "hostLead": None}
    v.update(kw)
    return v


def host_view(**kw):
    v = guest_view(role="host", partner="손님", mon={"id": 555, "num": BLAST, "name": "거북왕", "level": 40})
    v.update(kw)
    return v


def area_of(ov):
    x1, y1, x2, y2 = ov.area()
    return x1, y1, x2 - x1, y2 - y1


def shown(p):
    try:
        return p.win.winfo_viewable() == 1 or p.win.state() == "normal"
    except tk.TclError:
        return False


def at_corner(ov, p):
    x1, y1, W, H = area_of(ov)
    return abs(p.x + p.fw - (x1 + W)) < U.h(30) and abs(p.y + p.fh - (y1 + H)) < 12


def floaters(root):
    """떠 있는 창 (말풍선·입력 말풍선·메뉴) 말고 '친구 채팅' 같은 창이 있나 - 제목으로 찾는다."""
    out = []
    for w in root.winfo_children():
        try:
            if isinstance(w, tk.Toplevel) and "채팅" in (w.title() or ""):
                out.append(w.title())
        except tk.TclError:
            pass
    return out


def parse_part():
    print("=== 입력 ===")
    chk("말", V.parse("  안녕   하세요 ") == ("say", "안녕 하세요"))
    chk("명령은 동작", V.parse("/춤") == ("act", "dance") and V.parse("/자기") == ("act", "sleep")
        and V.parse("/일어나") == ("act", "wake"))
    chk("없는 명령", V.parse("/날기")[0] == "bad")
    chk("빈 줄은 아무것도", V.parse("   ") is None)


def btext(vis, pet):
    b = vis.bubbles.get(id(pet))
    return b.label.cget("text") if b is not None else None


def sent_now(vis, root, want, sec=2.0):
    return wait(root, lambda: want in vis.sock.sent, sec)


def guest_part(root, ov, app):
    print("\n=== 손님: 친구 집에 놀러 왔다 ===")
    vis = V.Visit(app)
    vis.sock = Sock()
    app.visit = vis
    pets = dict((p.id, p) for p in ov.pets.values())
    lead = pets[1]
    x1, y1, W, H = area_of(ov)
    vis.enter(guest_view())
    root.update()
    chk("내 도트는 빠지고 맨 앞 한 마리만 남는다", shown(lead) and not shown(pets[2]) and not shown(pets[3]))
    chk("  그 한 마리는 화면 오른쪽 밖에서 걸어 들어온다", lead.x >= x1 + W and lead.battling, (lead.x, x1 + W))
    settle(root, 0.4)
    chk("  걷는 중 (왼쪽으로)", lead.x < vis._offstage(lead) and lead.state == "walk" and lead.anim_name == "Walk",
        (lead.x, lead.state, lead.anim_name))
    wait(root, lambda: getattr(lead, "_stroll", None) is None, 8)
    chk("  오른쪽 아래에 닿으면 서서 안 움직인다", at_corner(ov, lead) and lead.state == "idle" and lead.battling,
        (lead.x, lead.y))
    chk("  풀숲을 멈추고, 동기화가 내 도트를 다시 깔지 못하게 잠근다", app.wild.stops == 1 and ov.locked)
    chk("  알린다", any("집주인 님의 집" in n for n in app.notes), app.notes)
    chk("채팅 창은 없다", not floaters(root) and not hasattr(vis, "bar"), floaters(root))
    wait(root, lambda: vis.bubbles.get(id(lead)) is not None, 3)
    hb = vis.bubbles.get(id(lead))
    chk("  대신 내 포켓몬 머리 위에 말하는 법과 우클릭(두기·돌아오기)을 알려 준다", hb is not None
        and hb.label.cget("text") == V.GUEST_HINT and "집으로 돌아오기" in V.GUEST_HINT and "여기에 두기" in V.GUEST_HINT)

    print("\n=== 친구 포켓몬: 파티만 맞추고 스스로 돌아다닌다 ===")
    party = [{"id": 50, "num": LIZ, "look": LIZ, "lead": True, "name": "리자몽", "level": 50},
             {"id": 51, "num": SAUR, "look": SAUR, "name": "이상해꽃", "level": 50}]
    vis.on_event({"t": "party", "party": party, "lead": 50})
    root.update()
    m50, m51 = vis.mirrors.get(50), vis.mirrors.get(51)
    chk("두 마리가 생긴다 (내 목록이 아니라 따로)", m50 is not None and m51 is not None and m50 in ov.extra
        and 50 not in ov.pets and m50.id < 0)
    chk("  남의 도트는 누르거나 끌 수 없다", m50.can_drag() is False)
    chk("  스스로 돌아다니는 도트다 (배틀 중처럼 묶이지 않는다)", isinstance(m50, V.FriendPet) and not m50.battling)
    start = dict((k, (p.x, p.y)) for k, p in vis.mirrors.items())
    wait(root, lambda: any((p.x, p.y) != start[k] for k, p in vis.mirrors.items()), 8)
    chk("  제 발로 걷는다", any((p.x, p.y) != start[k] for k, p in vis.mirrors.items()))
    here = (m50.x, m50.y)
    vis.on_event({"t": "party", "party": party, "lead": 50})
    chk("같은 파티가 다시 와도 자리를 건드리지 않는다 (순간이동 없음)", (m50.x, m50.y) == here
        and vis.mirrors.get(50) is m50)
    asked = []
    real_s, real_w = sprite_cache.ensure_many, walk_cache.ensure_many
    sprite_cache.ensure_many = lambda api, items: (asked.append(list(items)) or
                                                   dict(((n, s), FILES.get(n)) for n, s in items))
    walk_cache.ensure_many = lambda api, nums: dict(((n, s), SHEETS.get(n)) for n, s in nums if SHEETS.get(n))
    try:
        ov.walks.pop(BLAST, None)
        ov.paths.pop((BLAST, False), None)
        vis.on_event({"t": "party", "party": party + [{"id": 52, "num": BLAST, "name": "거북왕", "level": 9}],
                      "lead": 50})
        chk("처음 보는 종은 도트를 먼저 받는다 (그동안은 안 만든다)", 52 not in vis.mirrors)
        wait(root, lambda: 52 in vis.mirrors, 5)
        chk("  받고 나면 만든다 (자기·앉기 동작도 받는다)", 52 in vis.mirrors and asked
            and any(BLAST in f for f in app.fetched), (asked, app.fetched))
    finally:
        sprite_cache.ensure_many, walk_cache.ensure_many = real_s, real_w
    vis.on_event({"t": "party", "party": party, "lead": 50})
    chk("파티에서 빠진 포켓몬은 치운다", 52 not in vis.mirrors and not any(p.id == -1000052 for p in ov.extra))
    swaps = []
    real_play = mega_fx.play
    mega_fx.play = lambda app_, pet, num, revert=False, on_done=None: swaps.append((pet, num, revert))
    try:
        vis.on_event({"t": "party", "party": [dict(party[0], look=MEGA_X), party[1]], "lead": 50})
        chk("주인이 메가진화하면 메가진화 연출로 갈아 입는다", swaps and swaps[-1][0] is m50 and swaps[-1][1] == MEGA_X
            and swaps[-1][2] is False, swaps)
    finally:
        mega_fx.play = real_play
    vis.on_event({"t": "party", "party": [dict(party[0], look=MEGA_X), dict(party[1], level=51, name="꽃")],
                  "lead": 50})
    chk("  이름·레벨이 바뀌면 고친다 (같은 도트 그대로)", vis.mirrors.get(51) is m51
        and m51.mon["info"]["level"] == 51 and m51.mon["info"]["name"] == "꽃")
    asked = []
    real_s, real_w = sprite_cache.ensure_many, walk_cache.ensure_many
    sprite_cache.ensure_many = lambda api, items: (asked.append(list(items)) or {})
    walk_cache.ensure_many = lambda api, nums: {}
    try:
        vis.on_event({"t": "party", "party": [dict(party[0], look=MEGA_X), dict(party[1], level=51, name="꽃"),
                                             {"id": 53, "num": SAUR, "look": 10999, "name": "메가?", "level": 5}],
                      "lead": 50})
        settle(root, 0.6)
        vis.on_event({"t": "party", "party": [dict(party[0], look=MEGA_X), dict(party[1], level=51, name="꽃"),
                                             {"id": 53, "num": SAUR, "look": 10999, "name": "메가?", "level": 5}],
                      "lead": 50})
        settle(root, 0.6)
        chk("메가 모습 도트를 못 받으면 원래 모습으로 서고, 끝없이 다시 받지 않는다", 53 in vis.mirrors
            and vis.mirrors[53].look == SAUR and len(asked) == 1, (asked, vis.mirrors.get(53) and vis.mirrors[53].look))
    finally:
        sprite_cache.ensure_many, walk_cache.ensure_many = real_s, real_w
    vis.on_event({"t": "party", "party": [dict(party[0], look=MEGA_X), dict(party[1], level=51, name="꽃")], "lead": 50})
    chk("  가려진 내 도트는 우클릭을 받지 않는다, 친구 도트는 받는다",
        not app._hit(pets[2], pets[2].x + 2, pets[2].y + 2, -1) and app._hit(m50, m50.x + 2, m50.y + 2, -1))

    print("\n=== 말과 동작 ===")
    vis.say("안녕!")
    settle(root, 0.15)
    b = vis.bubbles.get(id(lead))
    chk("내 말은 내 포켓몬 위에 말풍선, 상대에게 보낸다 (손님은 포켓몬을 고르지 않는다)",
        b is not None and b.label.cget("text") == "안녕!" and vis.sock.sent[-1] == {"t": "say", "text": "안녕!"},
        vis.sock.sent[-1:])
    ok, got = over(b, lead)
    chk("  말풍선은 도트 머리 위에 (가로도 그 도트 위)", ok, got)
    vis.on_event({"t": "say", "from": "host", "text": "어서 와"})
    vis.on_event({"t": "say", "from": "host", "text": "나야", "pet": 51})
    settle(root, 0.15)
    chk("상대 말은 상대가 고른 포켓몬 위에 (모르면 주인의 맨 앞)",
        btext(vis, m50) == "어서 와" and btext(vis, m51) == "나야", (btext(vis, m50), btext(vis, m51)))
    n0 = len(vis.sock.sent)
    chk("없는 명령은 안 보내고 알려 준다", vis.say("/날기") is False and len(vis.sock.sent) == n0
        and "그런 명령은 없어요" in (btext(vis, lead) or ""))
    vis.say("/춤")
    chk("'/춤' 은 내 포켓몬이 춘다", lead._visit_act is not None)
    chk("  바로 이어 쳐도 조금 기다렸다 보낸다 (서버가 버리지 않게)",
        sent_now(vis, root, {"t": "act", "act": "dance"}), vis.sock.sent[-2:])
    wait(root, lambda: lead._visit_act is None, 6)
    chk("  끝나면 원래대로 (오른쪽 아래에 그대로 서 있다)", lead._visit_act is None and lead.battling
        and not hasattr(lead, "_visit_prev") and at_corner(ov, lead))
    vis.on_event({"t": "act", "from": "host", "act": "sleep", "pet": 51})
    chk("상대 동작은 상대가 고른 포켓몬이 한다 (그동안 안 걷는다)", m51._visit_act is not None and m51.battling)
    vis.on_event({"t": "act", "from": "host", "act": "wake", "pet": 51})
    chk("  '/일어나' 로 그치고 다시 돌아다닌다", m51._visit_act is None and not m51.battling)

    print("\n=== 누르고 Enter: 입력 말풍선 ===")
    lead.label.event_generate("<Button-1>", x=4, y=4)
    lead.label.event_generate("<ButtonRelease-1>", x=4, y=4)
    settle(root, 0.3)
    lead.win.event_generate("<Return>", when="tail")
    settle(root, 0.2)
    inp = vis.input
    chk("내 포켓몬을 누르고 Enter 면 그 머리 위에 입력 말풍선", inp is not None and inp.pet is lead
        and inp.win.winfo_y() + inp.win.winfo_height() <= lead.y + 2, inp and (inp.win.winfo_y(), lead.y))
    chk("  명령도 알려 준다", "/춤" in inp.tip.cget("text") and "Enter" in inp.tip.cget("text"))
    inp.var.set("가" * 80)
    chk("  60자까지만", len(inp.var.get()) == V.SAY_MAX)
    inp.var.set("/날기")
    inp.send()
    chk("  없는 명령이면 닫지 않고 빨갛게 알려 준다", not inp.dead and str(inp.tip.cget("fg")) == U.DANGER)
    inp.var.set("반가워")
    settle(root, 0.7)
    inp.send()
    settle(root, 0.15)
    chk("  Enter 면 닫고 말풍선으로 말한다, 상대에게 보낸다", inp.dead and vis.input is None
        and btext(vis, lead) == "반가워"
        and sent_now(vis, root, {"t": "say", "text": "반가워"}))
    inp = vis.open_input(lead)
    settle(root, 0.1)
    if root.focus_get() is not None:
        inp.entry.event_generate("<Escape>")
        settle(root, 0.1)
        chk("  Esc 면 그냥 닫는다", vis.input is None)
    else:
        # 앱이 화면 포커스를 못 가진 곳(CI 의 윈도우 러너)에서는 만든 키 이벤트가 어느 창에도 안 간다 -
        # 실제로는 포켓몬을 누르는 순간 앞으로 나온다. 여기서는 Esc 가 말풍선 칸과 창에 묶였는지만 본다.
        chk("  Esc 면 그냥 닫는다 (포커스가 없는 곳: 칸·창에 묶인 키)", "<Key-Escape>" in inp.entry.bind()
            and "<Key-Escape>" in inp.win.bind(), (inp.entry.bind(), inp.win.bind()))
        inp.close()
    chk("  남의 포켓몬에게는 안 열린다", vis.open_input(m50) is None)
    # 윈도우가 말풍선에 글자 포커스를 안 주면 글자는 포켓몬 창으로 간다 - 그때도 말풍선 일로 읽는다
    inp = vis.open_input(lead)
    vis.pet_typed(lead, "a", "안")
    vis.pet_typed(lead, "a", "녀")
    vis.pet_typed(lead, "BackSpace", "")
    vis.pet_typed(lead, "a", "녕")
    chk("포커스가 포켓몬 창에 남아도 친 글자는 말풍선 칸으로 간다", inp.var.get() == "안녕", inp.var.get())
    chk("  화살표 같은 글자 아닌 키는 넘기지 않는다", vis.pet_typed(lead, "Left", "") is False)
    settle(root, 0.7)
    vis.pet_enter(lead)
    chk("  Enter 는 보내기 (새 말풍선을 또 열지 않는다)", inp.dead and vis.input is None
        and sent_now(vis, root, {"t": "say", "text": "안녕"}), vis.sock.sent[-1:])
    vis.open_input(lead)
    chk("  Esc 는 닫기", vis.pet_escape(lead) is True and vis.input is None)

    print("\n=== 한글: 맥은 Enter 눌림을 입력기가 먹는다 (Enter 를 두 번 쳐야 보내지던 것) ===")
    inp = vis.open_input(lead)
    chk("칸에 Enter 뗌도 묶여 있다", "<KeyRelease-Return>" in inp.entry.bind()
        and "<KeyRelease-KP_Enter>" in inp.entry.bind(), inp.entry.bind())
    inp.var.set("안녕")
    inp.release_enter()
    chk("  막 뜬 말풍선의 뗌은 말풍선을 연 Enter 의 것이라 안 보낸다", not inp.dead and inp.var.get() == "안녕")
    inp._born -= 1.0
    settle(root, 0.7)
    n0 = len(vis.sock.sent)
    inp.release_enter()
    settle(root, 0.15)
    chk("  눌림 없이 뗌만 오면(입력기가 눌림을 먹었다) 친 글을 보낸다", inp.dead and vis.input is None
        and btext(vis, lead) == "안녕" and sent_now(vis, root, {"t": "say", "text": "안녕"}), vis.sock.sent[n0:])
    inp = vis.open_input(lead)
    inp._born -= 1.0
    inp.var.set("/날기")
    inp.press_enter()
    inp.release_enter()
    chk("  눌림을 받았으면 뗌으로 또 보내지 않는다 (없는 명령: 열린 채 빨갛게)", not inp.dead
        and str(inp.tip.cget("fg")) == U.DANGER)
    inp.var.set("")
    inp.release_enter()
    chk("  빈 칸의 뗌은 아무 일도 없다", not inp.dead)
    if root.focus_get() is not None:
        inp.var.set("또 봐")
        settle(root, 0.7)
        inp.entry.event_generate("<KeyRelease-Return>")
        settle(root, 0.15)
        chk("  진짜 키 뗌으로도 보낸다", inp.dead and sent_now(vis, root, {"t": "say", "text": "또 봐"}),
            vis.sock.sent[-1:])
    else:
        inp.close()

    print("\n=== 한글: 윈도우는 짜는 중인 글자를 칸에 안 그린다 (한 글자 늦게 보이던 것) ===")
    real_ime = PLAT.ime_composition
    inp = vis.open_input(lead)
    chk("입력기에 물을 수 없는 곳(맥)은 따로 그리지 않는다", (inp.comp is None) == (real_ime is None))
    inp.close()
    if sys.platform == "win32":
        from poketdesktop import platform_win
        u32, imm = platform_win._imm()               # 여기서 터지면 ime_composition 은 늘 빈 글만 준다 - 직접 부른다
        chk("  윈도우: 입력기에 묻는 함수가 준비된다 (짜는 중이 아니면 빈 글)", u32 is not None and imm is not None
            and platform_win.ime_composition() == "")
    comp = [""]
    PLAT.ime_composition = lambda: comp[0]
    try:
        inp = vis.open_input(lead)
        inp.var.set("안")
        inp.entry.icursor("end")
        comp[0] = "녀"
        settle(root, 0.15)
        font = tkfont.Font(root=root, font=inp.entry.cget("font"))
        want_x = 1 + font.measure("안")
        info = inp.comp.place_info() if inp.comp.winfo_manager() == "place" else {}
        chk("짜는 중인 글자를 칸의 커서 자리에 밑줄 글씨로 그린다", inp.comp.cget("text") == "녀"
            and abs(int(info.get("x", -99)) - want_x) <= 1 and "underline" in str(inp.comp.cget("font")),
            (inp.comp.cget("text"), info.get("x"), want_x, inp.comp.cget("font")))
        comp[0] = "녕"
        settle(root, 0.15)
        chk("  바뀌면 따라 바뀐다", inp.comp.cget("text") == "녕")
        comp[0] = ""
        inp.var.set("안녕")
        settle(root, 0.15)
        chk("  다 짜서 칸에 들어가면 치운다", inp.comp.winfo_manager() == "")
        inp.close()
        chk("  닫으면 그만 묻는다", inp._ime_job is None)
    finally:
        PLAT.ime_composition = real_ime

    print("\n=== 우클릭 ===")
    texts_, rows = menu_of(app, lead)
    chk("보낸 포켓몬: '말하기', '여기에 두기', '집으로 돌아오기', 박스로는 못 거둔다",
        "말하기 (Enter)" in texts_ and "여기에 두기..." in texts_ and "집으로 돌아오기" in texts_
        and "박스로 거두기" not in texts_, texts_)
    next(r for r in rows if r and r.get("text") == "말하기 (Enter)")["command"]()
    chk("  '말하기' 는 입력 말풍선을 연다", vis.input is not None and vis.input.pet is lead)
    vis.input.close()
    texts_, _r = menu_of(app, m50)
    chk("친구 포켓몬: 누구 것인지와 '집으로 돌아오기'", texts_[0] == "집주인 님의 리자몽" and "집으로 돌아오기" in texts_,
        texts_)

    print("\n=== 보따리 (손님) ===")
    from poketdesktop import ui_visit
    app.api.state_visit = vis.v
    dlg = next(r for r in rows if r and r.get("text") == "여기에 두기...")["command"]()
    wait(root, lambda: dlg.items, 4)
    settle(root, 0.2)
    chk("'여기에 두기' 는 가방 모양 창: 들고 온 것만, 친구가 오늘 받을 수 있나", isinstance(dlg, ui_visit.ItemPicker)
        and dlg.bag == {"GREATBALL": 2, "BLACKBELT": 1} and dlg.limit.cget("text") == "받을 수 있음",
        (dlg.bag, dlg.limit.cget("text")))
    chk("  담기 전에는 단추가 죽어 있다", not dlg.go_btn.enabled)
    for _ in range(3):
        dlg.pick_item("GREATBALL")
    chk("  들고 온 것보다 많이는 못 담는다", dlg.plan == {"GREATBALL": 2} and dlg.go_btn.enabled
        and "가진 만큼" in dlg.status._label.cget("text"), (dlg.plan, dlg.status._label.cget("text")))
    chk("  눌린 위젯이 없다", not squeezed(dlg.win), squeezed(dlg.win)[:3])
    dlg.go()
    wait(root, lambda: not dlg.alive, 4)
    chk("  두기를 누르면 보낸다 (가방을 새로 받는다)", app.api.calls[-1] == ("drop", [{"id": "GREATBALL", "count": 2}])
        and app.syncs >= 1)
    bundle = {"id": 70, "items": [{"id": "GREATBALL", "kr": "슈퍼볼", "count": 2}], "count": 2, "from": "나"}
    vis.on_event({"t": "bundles", "bundles": [bundle], "carry": [{"id": "BLACKBELT", "kr": "검은띠", "count": 1}],
                  "canGive": False})
    root.update()
    bo = vis.bundle_objs.get(70)
    gx, gy = vis._bundle_spot(0)
    chk("서버가 보따리를 주면 내 포켓몬 위에서 떨어진다", bo is not None and bo.y < gy and bo.x == gx, bo and (bo.y, gy))
    wait(root, lambda: bo._fall is None, 3)
    chk("  내 포켓몬 왼쪽 바닥에 놓인다", bo.y == gy and bo.x + bo.fw <= lead.x and abs(bo.y + bo.fh - (y1 + H)) < 12,
        (bo.x, bo.y, lead.x))
    chk("  들고 온 것은 그만큼 준다", vis.v["carry"] == [{"id": "BLACKBELT", "kr": "검은띠", "count": 1}])
    # 연못 · 화단(시즌 7)과 겹치는 자리면 그 위로 올린다 (실제 앱 시험 11/27: 보따리가 화분 위에 떨어졌다)
    ov = app.overlay
    old_avoid = getattr(ov, "avoid", None)
    bx, by = vis._bundle_spot(0)
    ov.avoid = [lambda: (bx - 10, by - 20, bx + 60, by + 80)]
    try:
        nx, ny = vis._bundle_spot(0)
        chk("  피할 자리(화단)와 겹치면 그 위로 올라간다", nx == bx and ny + 1 <= by - 20, (bx, by, nx, ny))
        ov.avoid = [lambda: (bx + 500, by, bx + 600, by + 40)]
        chk("  안 겹치면 자리 그대로", vis._bundle_spot(0) == (bx, by), vis._bundle_spot(0))
    finally:
        ov.avoid = old_avoid
    texts_, _r = menu_of(app, lead)
    chk("친구가 오늘 받았으면(안 받고 놓인 것도) '여기에 두기' 는 못 누른다 (하루 한 번)",
        "여기에 두기 (친구가 오늘 이미 받음)" in texts_ and "여기에 두기..." not in texts_, texts_)
    app.api.state_visit = vis.v
    dlg2 = ui_visit.DropDialog(app)
    wait(root, lambda: dlg2.items, 4)
    dlg2.pick_item("BLACKBELT")
    chk("  창을 열어도 '이미 받음', 담기지 않고 단추가 죽는다", dlg2.limit.cget("text") == "이미 받음"
        and not dlg2.plan and not dlg2.go_btn.enabled and "오늘 이미" in dlg2.status._label.cget("text"),
        (dlg2.limit.cget("text"), dlg2.plan))
    dlg2.close()
    vis.on_bundle_click(bo)
    tip = vis._tips.get(70)
    chk("  손님이 누르면 친구가 받는다고 알려 준다 (안 받는다)", tip is not None and "집주인 님이 누르면 받는다"
        in tip.label.cget("text") and not any(c[0] == "claim" for c in app.api.calls))
    vis.on_event({"t": "claimed", "bundle": bundle, "from": "나", "by": "집주인"})
    root.update()
    chk("친구가 받으면 보따리가 없어지고 'OO 님이 보따리를 받았다!'", 70 not in vis.bundle_objs and bo.dead
        and "집주인 님이 보따리를 받았다! (슈퍼볼 2개)" == btext(vis, lead), btext(vis, lead))
    vis.on_event({"t": "bundles", "bundles": [dict(bundle, id=71)], "carry": []})
    root.update()
    texts_, _r = menu_of(app, lead)
    chk("  들고 온 것을 다 두면 '여기에 두기' 는 못 누른다", "여기에 두기 (들고 온 도구 없음)" in texts_, texts_)
    ntexts, nrows, popped, err = native_menu_of(app, lead)
    chk("윈도우 메뉴도 내 포켓몬 우클릭에 '말하기'·'집으로 돌아오기' 가 나온다 (못 누르는 줄에서 멈추지 않는다)",
        err is None and popped and "말하기 (Enter)" in ntexts and "집으로 돌아오기" in ntexts, (err, ntexts))
    drop_row = next((r for r in nrows if r and r["text"] == "여기에 두기 (들고 온 도구 없음)"), None)
    chk("  못 누르는 줄은 윈도우 메뉴에서도 죽어 있다", drop_row is not None and drop_row["state"] == "disabled"
        and drop_row["command"] is None, drop_row)
    back = next((r for r in nrows if r and r["text"] == "집으로 돌아오기"), None)
    chk("  '집으로 돌아오기' 는 누를 수 있다", back is not None and back["state"] == "normal"
        and back["command"] == vis.end_visit, back)

    print("\n=== 놀러 간 채로 포켓몬 크기를 바꾸면 (10/15 제보) ===")
    old_lead, old_m = lead, dict(vis.mirrors)
    size0 = int(ov.settings["targetHeight"])
    app.set_size(size0 + 8)
    settle(root, 0.3)
    pets = dict((p.id, p) for p in ov.pets.values())
    lead = pets[1]
    chk("보낸 포켓몬은 새 도트로 바뀌어도 오른쪽 아래에 그대로 (연결도 그대로)", vis.active and vis.lead is lead
        and lead is not old_lead and at_corner(ov, lead) and lead.battling, (vis.active, lead.x, lead.y))
    chk("  내 다른 포켓몬은 계속 빠져 있고, 동기화 잠금도 그대로", not shown(pets[2]) and not shown(pets[3]) and ov.locked)
    chk("  친구 포켓몬도 새 크기로 다시 만든다", set(vis.mirrors) == set(old_m)
        and all(m in ov.extra for m in vis.mirrors.values()) and all(vis.mirrors[k] is not old_m[k] for k in old_m))
    bo71 = vis.bundle_objs.get(71)
    chk("  보따리도 그 자리에 다시 (떨어지지 않고)", bo71 is not None and not bo71.dead and bo71._fall is None
        and (bo71.x, bo71.y) == vis._bundle_spot(0))
    chk("  새 도트도 누르고 Enter 로 말할 수 있다", getattr(lead, "_visit_armed", False)
        and vis.open_input(lead) is not None)
    vis.input.close()
    app.set_size(size0)
    settle(root, 0.3)
    pets = dict((p.id, p) for p in ov.pets.values())
    lead = pets[1]

    print("\n=== 보낸 포켓몬을 메가진화하면 ===")
    n0 = len(vis.sock.sent)
    look0 = lead.look
    lead.look = MEGA_X
    wait(root, lambda: len(vis.sock.sent) > n0, 2)
    chk("상대에게 모습을 알린다", {"t": "look", "look": MEGA_X} in vis.sock.sent[n0:], vis.sock.sent[n0:])
    lead.look = look0

    print("\n=== 돌아오기 ===")
    vis.on_event({"t": "end", "id": 7, "by": "guest", "text": "돌아왔다",
                  "returned": [{"id": "GREATBALL", "kr": "슈퍼볼", "count": 2}]})
    root.update()
    chk("친구 도트를 바로 치운다", not vis.mirrors and not ov.extra and not vis.active)
    chk("  안 받은 보따리는 치우고, 돌려받았다고 알린다", not vis.bundle_objs
        and any("돌려받았다: 슈퍼볼 2개" in n for n in app.notes) and "돌려받았다" in (btext(vis, lead) or ""),
        app.notes[-2:])
    chk("  입력 말풍선을 치운다", vis.input is None)
    settle(root, 0.4)
    chk("보낸 포켓몬은 오른쪽 밖으로 걸어 나간다 (그동안 내 도트는 아직 빠져 있다)",
        lead.state == "walk" and not shown(pets[2]) and ov.locked, (lead.x, lead.state))
    wait(root, lambda: shown(pets[2]), 8)
    chk("  다 나가면 내 도트가 다시 보이고, 잠금을 풀고 풀숲을 다시 켜고 동기화한다",
        shown(pets[2]) and shown(pets[3]) and not ov.locked and app.wild.starts == 1 and app.syncs >= 1)
    chk("  집에는 오른쪽 밖에서 걸어 들어온다", lead.x > x1 + W - lead.fw and lead.battling, (lead.x, x1 + W))
    wait(root, lambda: vis._home is None, 8)
    chk("  들어오면 풀어 준다 (다시 스스로 돌아다닌다)", vis._home is None and lead.battling is False
        and x1 <= lead.x <= x1 + W, (lead.x, lead.battling))
    return vis


def host_part(root, ov, app):
    print("\n=== 주인: 친구 포켓몬이 놀러 왔다 ===")
    vis = V.Visit(app)
    vis.sock = Sock()
    app.visit = vis
    x1, y1, W, H = area_of(ov)
    vis.enter(host_view())
    root.update()
    vp = vis.visitor
    chk("놀러 온 포켓몬이 화면 오른쪽 밖에서 걸어 들어온다", vp is not None and vp in ov.extra and vp.x >= x1 + W,
        vp and (vp.x, x1 + W))
    chk("  걷는 동안에는 아직 '놀러 왔어요' 가 없다", vis.bubbles.get(id(vp)) is None)
    wait(root, lambda: getattr(vp, "_stroll", None) is None, 8)
    chk("  오른쪽 아래에 서서 안 움직인다", at_corner(ov, vp) and vp.state == "idle", (vp.x, vp.y))
    root.update()
    ab = vis.bubbles.get(id(vp))
    chk("서면 그 머리 위에 'OO 님이 놀러 왔어요!' (눈에 띄게, 조금 더 오래)", ab is not None
        and ab.label.cget("text") == "손님 님이 놀러 왔어요!" and ab.until - time.time() > V.BUBBLE_MS / 1000.0,
        ab and ab.label.cget("text"))
    ok, got = over(ab, vp)
    chk("  그 포켓몬 위에 있다", ok, got)
    chk("  다른 놀러 가기면 안 띄운다 (늦게 끝난 걸음)", vis._arrived(vp, -1) is None)
    chk("  알린다 (들고 온 도구)", any("들고 온 도구: 슈퍼볼 2개, 검은띠 1개" in n for n in app.notes), app.notes[-1:])
    chk("  내 도트는 그대로 돌아다닌다, 채팅 창은 없다", not ov.locked and all(shown(p) for p in ov.pets.values())
        and not floaters(root))
    lead1 = ov.pets[1]
    wait(root, lambda: vis.bubbles.get(id(lead1)) is not None, 3)
    chk("  내 맨 앞 포켓몬 위에 말하는 법과 '돌려보내기' 를 알려 준다", btext(vis, lead1) == V.HOST_HINT
        and "돌려보내기" in V.HOST_HINT, btext(vis, lead1))
    size0 = int(ov.settings["targetHeight"])
    app.set_size(size0 + 8)
    settle(root, 0.3)
    nvp = vis.visitor
    chk("크기를 바꿔도 놀러 온 포켓몬이 오른쪽 아래에 그대로 (새 도트, 걷지 않고 바로)", nvp is not None
        and nvp is not vp and nvp in ov.extra and at_corner(ov, nvp) and getattr(nvp, "_stroll", None) is None
        and vis.active and not ov.locked, nvp and (nvp.x, nvp.y))
    chk("  내 포켓몬도 다시 누르고 Enter 로 말할 수 있다", all(getattr(p, "_visit_armed", False) for p in ov.pets.values()))
    app.set_size(size0)
    settle(root, 0.3)
    vp = vis.visitor
    wait(root, lambda: any(m.get("t") == "party" for m in vis.sock.sent), 2)
    sends = [m for m in vis.sock.sent if m.get("t") == "party"]
    party = sends[-1]["party"] if sends else []
    chk("내 파티를 보낸다 (자리 없이, 맨 앞 표시)", len(party) == 3 and [p["id"] for p in party] == [1, 2, 3]
        and [p["id"] for p in party if p["lead"]] == [1] and not any("x" in p or "y" in p for p in party), party)
    settle(root, 1.2)
    chk("  안 바뀌면 다시 안 보낸다 (자리를 따라 보내지 않는다)",
        len([m for m in vis.sock.sent if m.get("t") == "party"]) == len(sends))
    own = ov.pets[1]
    look0 = own.look
    own.look = MEGA_X
    wait(root, lambda: len([m for m in vis.sock.sent if m.get("t") == "party"]) > len(sends), 2.5)
    last = [m for m in vis.sock.sent if m.get("t") == "party"][-1]["party"]
    chk("  메가진화하면 바뀐 파티를 보낸다", last[0]["look"] == MEGA_X, last[:1])
    own.look = look0
    swaps = []
    real_play = mega_fx.play
    mega_fx.play = lambda app_, pet, num, revert=False, on_done=None: swaps.append((pet, num, revert))
    try:
        vis.on_event({"t": "look", "look": MEGA_X})
        chk("손님이 메가진화하면 연출과 함께 바뀐다", swaps and swaps[-1][0] is vp and swaps[-1][1] == MEGA_X)
        vp.look = MEGA_X
        vis.on_event({"t": "look", "look": None})
        chk("  풀면 원래 모습으로 (되돌리는 연출)", swaps[-1][1] == BLAST and swaps[-1][2] is True, swaps[-1:])
    finally:
        mega_fx.play = real_play
    vis.on_event({"t": "say", "from": "guest", "text": "놀러 왔어"})
    second = ov.pets[2]
    vis.say("반가워", second)
    settle(root, 0.15)
    chk("손님 말은 놀러 온 포켓몬 위, 내 말은 말한 내 포켓몬 위", vis.bubbles.get(id(vp)) is not None
        and vis.bubbles.get(id(second)) is not None)
    ok, got = over(vis.bubbles[id(vp)], vp)
    chk("  놀러 온 포켓몬(오른쪽 아래 구석)의 말풍선이 가로로도 그 위에 있다", ok, got)
    # 10/16 윈도우 제보: 말풍선이 늘 화면 왼쪽 같은 자리에 떴다 (내 말도). 도트 자리는 운영체제가 알려 준
    # 화면으로 잡는데 말풍선만 Tk 가 켜질 때 재 둔 화면 폭(winfo_screenwidth)으로 화면 안에 맞췄다 - 그 값이
    # 실제보다 작은 PC 에서는 그보다 오른쪽 도트의 말풍선이 전부 그 폭 끝으로 끌려왔다.
    real_sw = root.winfo_screenwidth
    root.winfo_screenwidth = lambda: 300
    V._SCREENS.update(got=None, told=False)          # 모니터를 다시 묻게 (기억해 둔 것으로 통과하지 않게)
    try:
        vis.on_event({"t": "say", "from": "guest", "text": "여기 어때"})
        vis.say("나도", second)
        settle(root, 0.2)
        ok, got = over(vis.bubbles[id(vp)], vp)
        chk("  Tk 가 아는 화면 폭이 틀려도 말풍선은 그 도트 위에 (놀러 온 포켓몬)", ok, got)
        ok, got = over(vis.bubbles[id(second)], second)
        chk("    내 포켓몬도", ok, got)
        chk("    Tk 의 화면 폭이 모니터와 다르다고 기록에 한 번 남긴다", V._SCREENS["told"] is True)
    finally:
        root.winfo_screenwidth = real_sw
        V._SCREENS.update(got=None, told=False)
        settle(root, 0.2)
    real_screens = PLAT.screens
    PLAT.screens = lambda w, h: [(0, 0, 1000, 800), (1000, 0, 2600, 900)]
    V._SCREENS.update(got=None)
    try:
        chk("  모니터가 둘이면 그 도트가 있는 모니터 안으로만 당긴다", V.screen_of(root, 1500, 500) == (1000, 0, 2600, 900)
            and V.screen_of(root, 300, 500) == (0, 0, 1000, 800))
        chk("    걸어 들어오는 중(모니터 밖)이면 가장 가까운 모니터", V.screen_of(root, 2700, 500) == (1000, 0, 2600, 900)
            and V.screen_of(root, -50, 500) == (0, 0, 1000, 800))
    finally:
        PLAT.screens = real_screens
        V._SCREENS.update(got=None)
    chk("  상대에게 어느 포켓몬이 말했는지 알린다", sent_now(vis, root, {"t": "say", "text": "반가워", "pet": 2}),
        vis.sock.sent[-2:])
    stack_part(root, vis, vp, second)
    keys_part(root, vis, second)
    vis.say("/앉기", own)
    chk("내가 동작하면 그 포켓몬이 그동안 멈춘다", own.battling is True and own._visit_act is not None)
    vis.say("/일어나", own)
    chk("  그치면 다시 돌아다닌다", own.battling is False and own._visit_act is None)
    print("\n=== 보따리 (주인) ===")
    bundle = {"id": 80, "items": [{"id": "BLACKBELT", "kr": "검은띠", "count": 1}], "count": 1, "from": "손님"}
    vis.on_event({"t": "bundles", "bundles": [bundle], "carry": []})
    root.update()
    bo = vis.bundle_objs.get(80)
    wait(root, lambda: bo is not None and bo._fall is None, 3)
    chk("손님이 두면 놀러 온 포켓몬 왼쪽 바닥에 보따리", bo is not None and bo.x + bo.fw <= vp.x
        and abs(bo.y + bo.fh - (y1 + H)) < 12, bo and (bo.x, bo.y, vp.x))
    vis.bundle_tip(bo, True)
    chk("  올리면 누구의 무엇인지, 눌러서 받기", "손님 님의 보따리 (검은띠 1개)" in vis._tips[80].label.cget("text")
        and "눌러서 받기" in vis._tips[80].label.cget("text"))
    s0 = app.syncs
    vis.on_bundle_click(bo)
    vis.on_bundle_click(bo)
    wait(root, lambda: 80 not in vis.bundle_objs, 3)
    gb = vis.bubbles.get(id(vp))
    chk("누르면 받는다 (한 번만 보낸다): 'OO 님에게 ~를 받았다!' (그림과 함께), 가방을 새로 받는다",
        [c for c in app.api.calls if c[0] == "claim"] == [("claim", 80)] and gb is not None
        and gb.label.cget("text") == "손님 님에게 검은띠 1개를 받았다!" and app.syncs > s0, (gb and gb.label.cget("text"), app.api.calls[-2:]))
    n_note = len(app.notes)
    vis.on_event({"t": "claimed", "bundle": bundle, "from": "손님", "by": "나"})
    chk("  소켓으로 또 와도 두 번 알리지 않는다", len(app.notes) == n_note)
    texts_, _r = menu_of(app, second)
    chk("우클릭: 내 포켓몬 누구나 '말하기', '돌려보내기', 박스로도 거둔다 ('여기에 두기' 는 놀러 간 쪽만)",
        "말하기 (Enter)" in texts_ and "손님 님의 포켓몬 돌려보내기" in texts_ and "박스로 거두기" in texts_
        and not any("여기에 두기" in (t or "") for t in texts_), texts_)
    ntexts, _r, popped, err = native_menu_of(app, second)
    chk("  윈도우 메뉴도 같다", err is None and popped and "말하기 (Enter)" in ntexts
        and "손님 님의 포켓몬 돌려보내기" in ntexts and "박스로 거두기" in ntexts, (err, ntexts))
    texts_, _r = menu_of(app, vp)
    chk("  놀러 온 포켓몬: 누구 것인지와 돌려보내기", texts_[0] == "손님 님의 거북왕"
        and "손님 님의 포켓몬 돌려보내기" in texts_, texts_)
    vis.on_event({"t": "end", "id": 7, "by": "host", "text": "돌려보냈다"})
    root.update()
    chk("끝나면 그만 보낸다", vis.visitor is None and vis._job is None and not vis.active)
    chk("  쥐고 있던 키보드도 놓는다", vis._kb is None)
    settle(root, 0.4)
    chk("  놀러 온 포켓몬은 오른쪽 밖으로 걸어 나간다", vp in ov.extra and vp.state == "walk", (vp.x, vp.state))
    wait(root, lambda: not ov.extra, 8)
    chk("  다 나가면 치운다", not ov.extra and not vis._leaving)
    n1 = len(vis.sock.sent)
    settle(root, 1.2)
    chk("  더는 파티를 안 보낸다", len(vis.sock.sent) == n1)
    texts_, _r = menu_of(app, own)
    chk("  끝나면 우클릭에서 '말하기' 가 빠진다", "말하기 (Enter)" not in texts_ and "박스로 거두기" in texts_, texts_)


def send_part(root, ov, app):
    print("\n=== 들고 갈 도구 창 (가방 모양) ===")
    from poketdesktop import ui_bag, ui_visit
    vis = V.Visit(app)
    vis.sock = Sock()
    app.visit = vis
    app.api.start_reply = guest_view()
    app.api.state_visit = None
    d = ui_visit.SendDialog(app, {"id": 2, "name": "집주인"})
    wait(root, lambda: d.items, 4)
    settle(root, 0.3)
    tx = texts(d.win)
    rows = [r for _i, r in d.vl.shown()]
    chk("가방과 같은 목록: 분류 머리줄 + 도구 줄 (가진 수)", any(isinstance(r, ui_bag.HeadRow) for r in rows)
        and any("7개" == r.count.cget("text") for r in rows if isinstance(r, ui_visit.PickRow)), tx[:8])
    chk("  들고 갈 수 있는 것만: 볼·지닌 도구 중 귀함까지 (돌·마스터볼·진귀한 기합의띠는 빠진다)",
        set(d.bag) == {"GREATBALL", "ULTRABALL", "BLACKBELT"}, sorted(d.bag))
    chk("  누가 가는지 (파티 맨 앞)", d.who.cget("text").startswith("파이리"), d.who.cget("text"))
    chk("  담은 것이 없으면 안내", d.picked_note.winfo_manager() == "pack")
    for _ in range(3):
        d.pick_item("ULTRABALL")
    chk("줄을 누르면 하나씩 담긴다, 가진 것보다 많이는 못 담는다", d.plan["ULTRABALL"] == 2
        and "가진 만큼" in d.status._label.cget("text"))
    row = next(r for _i, r in d.vl.shown() if isinstance(r, ui_visit.PickRow) and r.item["id"] == "ULTRABALL")
    chk("  담은 줄은 고른 줄처럼 칠하고 '담음 / 가진 수'", row.selected and row.count.cget("text") == "2 / 2개")
    for _ in range(5):
        d.pick_item("GREATBALL")
    chk("  볼은 합쳐서 5개까지", d.plan == {"ULTRABALL": 2, "GREATBALL": 3} and "볼은 5개까지" in d.status._label.cget("text"),
        d.plan)
    d.pick_item("BLACKBELT")
    d.pick_item("BLACKBELT")
    chk("  지닌 도구는 1개까지", d.plan.get("BLACKBELT") == 1 and "지닌 도구는 1개까지" in d.status._label.cget("text")
        and d.limit.cget("text") == "볼 5/5 · 지닌 도구 1/1", (d.plan, d.limit.cget("text")))
    d.bump("GREATBALL", -1)
    d.remove("ULTRABALL")
    d.remove("BLACKBELT")
    chk("  -, 빼기", d.plan == {"GREATBALL": 2} and d.limit.cget("text") == "볼 2/5 · 지닌 도구 0/1",
        (d.plan, d.limit.cget("text")))
    chk("  눌린 위젯이 없다", not squeezed(d.win), squeezed(d.win)[:3])
    d.go()
    wait(root, lambda: not d.alive, 4)
    chk("놀러 가기를 누르면 들고 갈 것을 보내고 창을 닫는다, 바로 친구 집으로", app.api.calls[-1][0] == "start"
        and app.api.calls[-1][2] == [{"id": "GREATBALL", "count": 2}] and vis.guest and vis.active, app.api.calls[-1])
    vis.leave(None, tell=False, walk=False)
    settle(root, 0.2)


def over(b, p):
    """말풍선이 그 도트 위에 걸쳐 있나 (가로: 몸 가운데가 말풍선 폭 안, 세로: 머리 위). (참/거짓, 잰 값)"""
    b.win.update_idletasks()
    bx, bw = b.win.winfo_x(), b.win.winfo_width()
    by = b.win.winfo_y() + b.win.winfo_height()
    cx = p.x + getattr(p, "ax", p.fw / 2.0)
    return bx <= cx <= bx + bw and by <= p.y + 2, (bx, bw, by, round(cx), round(p.y))


def bottom(b):
    b.win.update_idletasks()
    return b.win.winfo_y() + b.win.winfo_height()


def stack_part(root, vis, vp, mine):
    """10/16 요청: 말풍선이 위로 쌓인다 - 5초쯤 떠 있고, 그 사이에 또 말하면 새 말이 도트 바로 위, 먼저 한 말은
    위로 밀려 올라간다. 사라질 때는 스르륵."""
    print("\n=== 말풍선 쌓기 ===")
    vis._close_bubbles()
    chk("한 말풍선은 5초쯤 떠 있다", 4.5 <= V.BUBBLE_MS / 1000.0 <= 6.0, V.BUBBLE_MS)
    vis.on_event({"t": "say", "from": "guest", "text": "하나"})
    settle(root, 0.3)
    first = vis.bubbles.get(id(vp))
    y_first = first.win.winfo_y()
    vis.on_event({"t": "say", "from": "guest", "text": "둘"})
    root.update()
    second = vis.bubbles.get(id(vp))
    st = vis._stacks.get(id(vp)) or []
    chk("또 말하면 앞 말풍선을 지우지 않고 둘 다 떠 있다", st == [first, second] and not first.dead and not second.dead,
        [b.label.cget("text") for b in st])
    chk("  새 말이 도트 바로 위, 먼저 한 말은 그 위로 (자리)", second.offset == 0
        and first.offset >= second.height() + V.STACK_GAP, (first.offset, second.offset, second.height()))
    chk("  먼저 한 말은 단번에 뛰지 않고 미끄러져 올라간다", 0 < first._shown < first.offset, (first._shown, first.offset))
    wait(root, lambda: first._shown == first.offset, 3)        # 느린 PC(CI)에서는 더 걸린다
    settle(root, 0.1)
    chk("  다 올라가면 새 말 바로 위에 선다 (겹치지 않는다)", first._shown == first.offset
        and bottom(first) <= second.win.winfo_y() and first.win.winfo_y() < y_first
        and bottom(second) <= vp.y + 2, (bottom(first), second.win.winfo_y(), y_first))
    vis.on_event({"t": "say", "from": "guest", "text": "셋"})
    wait(root, lambda: all(b._shown == b.offset for b in vis._stacks.get(id(vp), [])), 3)
    settle(root, 0.1)
    third = vis.bubbles.get(id(vp))
    chk("  셋째는 맨 아래, 첫째가 맨 위", bottom(first) <= second.win.winfo_y() and bottom(second) <= third.win.winfo_y(),
        (first.win.winfo_y(), second.win.winfo_y(), third.win.winfo_y()))

    print("\n=== 말풍선: 스르륵 사라지기 ===")
    first.until = time.time()                     # 첫째의 시간이 다 됐다 (5초 기다리지 않는다)
    settle(root, V.FADE_MS / 2000.0)
    try:
        a = float(first.win.attributes("-alpha"))
    except Exception:                             # noqa: BLE001
        a = None
    chk("시간이 다 되면 바로 없어지지 않고 흐려진다", not first.dead and a is not None and 0.0 < a < 1.0, a)
    wait(root, lambda: first.dead, 3)
    chk("  다 흐려지면 닫힌다, 남은 것은 그대로", first.dead and not second.dead and not third.dead
        and vis._stacks.get(id(vp)) == [second, third])
    second.until = third.until = time.time()
    wait(root, lambda: second.dead and third.dead, 3)
    chk("  다 사라지면 그 도트의 말풍선이 비워진다", vis.bubbles.get(id(vp)) is None and id(vp) not in vis._stacks)

    print("\n=== 말풍선: 너무 많이 쌓이면 ===")
    for i in range(V.STACK_MAX + 2):
        vis.on_event({"t": "say", "from": "guest", "text": "말 %d" % i})
        root.update()
    st = vis._stacks.get(id(vp)) or []
    live = [b for b in st if b._fade_at is None]
    chk("%d개까지만 남기고 가장 오래된 것부터 스르륵 사라진다" % V.STACK_MAX, len(live) == V.STACK_MAX
        and [b.label.cget("text") for b in live] == ["말 %d" % i for i in range(2, V.STACK_MAX + 2)]
        and all(b._fade_at is not None for b in st[:2]), [(b.label.cget("text"), b._fade_at is not None) for b in st])
    wait(root, lambda: len(vis._stacks.get(id(vp)) or []) == V.STACK_MAX, 3)
    chk("  사라진 뒤에는 %d개" % V.STACK_MAX, len(vis._stacks.get(id(vp)) or []) == V.STACK_MAX)
    vis._close_bubbles(vp)
    chk("  치우면 그 도트 것이 다 없어진다", id(vp) not in vis._stacks and vis.bubbles.get(id(vp)) is None
        and all(b.dead for b in st))

    print("\n=== 말풍선: 치는 중이면 입력 말풍선 위로 ===")
    vis.say("먼저 한 말", mine)
    settle(root, 0.3)
    said = vis.bubbles.get(id(mine))
    inp = vis.open_input(mine)
    wait(root, lambda: said._shown == said.offset and said.offset > 0, 3)
    settle(root, 0.1)
    chk("입력 말풍선을 열어도 떠 있던 말풍선은 안 지운다, 그 위로 올라간다", inp is not None and not said.dead
        and said.offset >= inp.height() and bottom(said) <= inp.win.winfo_y(),
        (said.dead, said.offset, inp.height(), bottom(said), inp.win.winfo_y()))
    inp.close()
    wait(root, lambda: said._shown == said.offset == 0, 3)
    settle(root, 0.1)
    chk("  입력 말풍선을 닫으면 내려온다", said.offset == 0 and said._shown == 0 and bottom(said) <= mine.y + 2,
        (said.offset, said._shown))
    vis._close_bubbles()


def keys_part(root, vis, mine):
    """10/16 제보: 말하고 나서 Enter 만으로 다시 안 열리고 매번 포켓몬을 눌러야 했다. 맥 Tk 는 창이 하나 없어질
    때마다(입력 말풍선·말풍선·툴팁) 키보드를 맨 앞의 제목 있는 창에 넘긴다 - 그 창이 가져가면 되찾는다.
    (실제 포커스는 PC 마다 달라서 여기서는 판단만 본다. 실제로 되찾는 것은 맥에서 따로 재 봤다.)"""
    print("\n=== 키보드를 쥔 포켓몬 ===")
    E = lambda w: type("E", (), {"widget": w})()      # noqa: E731
    panel = tk.Toplevel(root)
    panel.title("친구 창")
    settle(root, 0.1)
    vis.focus_pet(mine)
    chk("포켓몬을 누르면 그 포켓몬이 키보드를 쥔다", vis._kb is mine and str(panel) in vis._kb_known)
    vis.on_focus_in(E(mine.win))
    chk("  제 창에 포커스가 오는 것은 그대로", vis._kb is mine and vis._kb_job is None)
    vis.on_focus_in(E(panel))
    chk("  원래 있던 창이 포커스를 가져가면(창이 닫혀 Tk 가 넘긴 것) 되찾으려 한다", vis._kb is mine
        and vis._kb_job is not None)
    took, real_take, real_fg = [], PLAT.take_keys, root.focus_get
    PLAT.take_keys = lambda w: took.append(str(w)) or True
    root.focus_get = lambda: panel
    try:
        root.after_cancel(vis._kb_job)
        vis._kb_job = None
        vis._reclaim_keys()
        chk("    되찾는다 (그 포켓몬 창에 키보드를 준다)", took == [str(mine.win)], took)
        inp = vis.open_input(mine)
        took[:] = []
        focused = []
        real_focus, inp.focus = inp.focus, lambda: focused.append(1)
        vis._reclaim_keys()
        chk("    입력 말풍선이 열려 있으면 그리로 되돌린다", focused == [1] and not took, (focused, took))
        inp.focus = real_focus
        inp.close()
        root.focus_get = lambda: None
        took[:] = []
        vis._reclaim_keys()
        chk("    다른 프로그램으로 갔으면 끌어오지 않는다", not took, took)
    finally:
        PLAT.take_keys, root.focus_get = real_take, real_fg
    vis.focus_pet(mine)
    vis.on_any_press(E(panel))
    chk("  제목 있는 창을 누르면 그 창에 쓰려는 것이다 - 놓는다", vis._kb is None and vis._kb_job is None)
    vis.focus_pet(mine)
    vis.on_any_press(E(mine.win))
    chk("  제 포켓몬을 누른 것은 그대로 쥔다", vis._kb is mine)
    fresh = tk.Toplevel(root)
    settle(root, 0.1)
    vis.on_focus_in(E(fresh))
    chk("  새로 뜬 창이 포커스를 받으면(가방·설정을 열었다) 놓는다", vis._kb is None)
    fresh.destroy()
    panel.destroy()
    vis.focus_pet(mine)
    vis._close_bubbles()


def busy_part(root, ov, app):
    print("\n=== 바탕화면에서 싸우는 동안에는 못 간다 (야생 배틀·랜덤 배틀) ===")
    from poketdesktop import ui_spectate, wild_ui
    vis = V.Visit(app)
    vis.sock = Sock()
    app.visit = vis
    chk("아무 일도 없으면 갈 수 있다", vis.can_go() is None, vis.can_go())
    app.battle = object()
    chk("야생 배틀 중에는 못 간다", vis.can_go() == "배틀 중에는 놀러 갈 수 없습니다.", vis.can_go())
    app.battle = None
    app.arena = object()
    chk("  랜덤 배틀을 재생하는 중에도", vis.can_go() == "배틀 중에는 놀러 갈 수 없습니다.", vis.can_go())
    app.arena = None
    app.wild.throwing = True
    chk("  야생을 눌러 배틀을 여는 중(답을 기다리는 중)에도", vis.can_go() == "배틀 중에는 놀러 갈 수 없습니다.")
    app.wild.throwing = False
    app._pvp_busy = True
    chk("  랜덤 배틀 상대를 찾는 중에도 (찾으면 바로 바탕화면에서 재생한다)",
        vis.can_go() == "대전 상대를 찾는 중에는 놀러 갈 수 없습니다.", vis.can_go())
    app._pvp_busy = False
    app.friendly = type("Fr", (), {"watching": lambda _self: True})()
    chk("  친선전을 바탕화면에서 구경하는 중에도", vis.can_go() == "친선전을 구경하는 동안에는 놀러 갈 수 없습니다.")
    app.friendly = None

    print("\n=== 놀러 가기를 누르고 답을 기다리는 사이에 배틀이 시작되면 ===")
    app.api.start_reply = guest_view(id=31)
    n_calls, stops, got = len(app.api.calls), app.wild.stops, []
    vis.go(2, [], lambda r, e: got.append((r, e)))
    app.battle = object()                     # 답이 오기 전에 야생을 눌렀다
    wait(root, lambda: got, 4)
    settle(root, 0.2)
    chk("들어가지 않는다 (내 도트·풀숲 그대로)", not vis.active and app.wild.stops == stops
        and all(shown(p) for p in ov.pets.values()), (vis.active, app.wild.stops))
    chk("  서버에서도 끝내고 알린다", ("end",) in app.api.calls[n_calls:]
        and app.notes[-1] == "배틀이 시작돼서 놀러 가지 않았습니다.", (app.api.calls[n_calls:], app.notes[-1:]))
    n_end = app.api.calls.count(("end",))
    vis.on_event({"t": "visit", "visit": guest_view(id=31)})
    settle(root, 0.2)
    chk("  같은 것이 소켓으로 또 와도 한 번만", not vis.active and app.api.calls.count(("end",)) == n_end)
    vis.on_event({"t": "visit", "visit": host_view(id=32)})
    chk("친구가 놀러 오는 것은 배틀 중에도 받는다 (내 화면은 그대로 내 집)", vis.active and not vis.guest)
    vis.leave(None, tell=False, walk=False)
    app.battle = None
    settle(root, 0.3)

    print("\n=== 놀러 가 있는 동안 ===")
    vis.enter(guest_view(id=33))
    settle(root, 0.3)
    asked, told = [], []
    app._pvp(lambda: asked.append(1), lambda r, why: told.append(why))
    settle(root, 0.2)
    chk("랜덤 배틀·친구 배틀을 걸지 않는다 (끝나면 재생할 바탕화면이 친구 집이다)", not asked
        and told == ["친구 집에 놀러 가 있는 동안에는 대전을 걸 수 없습니다. 돌아온 뒤에 해 주세요."]
        and app.notes[-1] == told[0] and not getattr(app, "_pvp_busy", False), (asked, told))
    wc = wild_ui.WildController(app)
    app.api.wild = lambda force=False: asked.append("wild")
    wc.check(force=True)
    settle(root, 0.2)
    chk("풀숲을 묻지 않는다 (설정에서 다시 켜도)", "wild" not in asked and wc._job is None, asked)
    app.balls = 0
    wc.apply({"balls": 4, "wild": {"id": 9, "state": "grass"}, "nextInSeconds": 30})
    chk("  늦게 온 답은 볼 수만 챙기고 친구 집에 풀숲을 안 돋운다", app.balls == 4 and wc.grass is None
        and wc.pet is None and wc._job is None, (app.balls, wc.grass, wc._job))
    app.user_id = 1
    fr = ui_spectate.Friendly(app)
    fight = {"id": 5, "a": {"id": 8, "name": "가"}, "b": {"id": 9, "name": "나"}}
    fr.view["fights"] = [fight]
    n_note = len(app.notes)
    fr.watch(5)
    chk("친선전을 바탕화면에서 구경하지 않는다, 까닭을 알린다", fr.duel is None and len(app.notes) == n_note + 1
        and "놀러 가 있는 동안에는 친선전을 구경할 수 없습니다" in app.notes[-1], app.notes[-1:])
    heard = []
    fr.listeners.append(lambda: heard.append(fr.error) or setattr(fr, "error", None))
    fr.watch(5)
    chk("  길드 탭이 열려 있으면 거기에만 (두 번 알리지 않는다)", fr.duel is None and len(app.notes) == n_note + 1
        and heard and "친선전을 구경할 수 없습니다" in (heard[-1] or ""), heard)
    app.settings["friendlyAuto"], app.settings["friendlyNotify"] = True, False
    fr.fight(dict(fight, id=6))
    chk("  자동 구경을 켜 두었어도 새 판을 구경하지 않는다", fr.duel is None and 6 in fr.known)
    app.settings.pop("friendlyAuto", None)
    app.settings.pop("friendlyNotify", None)
    fr.close()
    vis.leave(None, tell=False, walk=False)
    settle(root, 0.3)
    app.visit = None


FILES, SHEETS = {}, {}


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-400:])
    root.report_callback_exception = on_err
    print("글꼴 %s / 본문 %dpt (BASE_PT=%d)" % (U.FAMILY, U.FONT[1], U.BASE_PT))
    parse_part()
    for n, col in ((PIKA, (240, 210, 40, 255)), (LIZ, (220, 120, 60, 255)), (SAUR, (60, 160, 90, 255)),
                   (BLAST, (60, 90, 200, 255)), (4, (230, 110, 40, 255)), (7, (80, 140, 220, 255)),
                   (MEGA_X, (40, 40, 60, 255))):
        SHEETS[n] = make_sheet("s%d.png" % n, 32, col)
        FILES[n] = make_dot("d%d.png" % n, col)
    sprite_cache.ensure = lambda api, num, shiny=False: FILES.get(num)
    walk_cache.ensure = lambda api, num, name="Walk", shiny=False: (
        SHEETS.get(num) if name == "Walk" and SHEETS.get(num) else (None, None))
    settings = dict(config.DEFAULTS)
    settings["megaWalk"] = []
    ov = overlay.Overlay(root, settings)
    ov.paths.update(dict(((n, False), p) for n, p in FILES.items()))
    ov.walks.update(dict(SHEETS))
    ov.sync([mon(1, 4, 0, "파이리"), mon(2, 7, 1, "꼬부기"), mon(3, SAUR, 2, "이상해씨")], {}, {})
    ov.start()
    settle(root, 0.3)
    app = MiniApp(root, ov)
    try:
        # 맨 앞 포켓몬은 파이리(4) - 손님 보기의 mon 번호(1)와 같은 도트다
        guest_part(root, ov, app)
        host_part(root, ov, app)
        send_part(root, ov, app)
        busy_part(root, ov, app)
    finally:
        ov.stop()
        ov.clear()
        settle(root, 0.2)
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
