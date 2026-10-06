# -*- coding: utf-8 -*-
"""길드 창 (1.10.0) — 진짜 Tk 로 확인. 서버 없이 돈다.

    python client/test_guild_ui.py

서버 흉내(FakeServer)는 server/app/guild.py 의 응답 모양 그대로다. 규칙 자체(돈·정원·
권한·보상)는 server/test_guild.py 가 본다. 여기서는 **화면**을 본다:

  · 길드가 없으면 찾기·만들기, 있으면 여섯 칸 (채팅·길드원·미션·코인 상점·다른 길드·관리)
  · (1.10.1) 코인 상점은 그림이 있는 카드 격자이고 이름으로 찾는다. 길드에 든 채로
    다른 길드를 둘러볼 수 있다.
  · 채팅: 웹소켓이 붙어 있으면 밀려오는 줄을 받고 서버에 묻지 않는다. 끊기면 2초마다
    묻는 길로 돌아간다. 두 길로 온 줄이 겹치거나 빠지지 않는다
  · 사람 수가 바뀌면 머리만 고친다 (채팅 칸은 그대로), 다른 칸에 있으면 안 읽은 수가 붙는다
  · 자리에 따라 보이는 것이 다르다 (마스터·부마스터·길드원)
  · 내보내지면 스스로 찾기 화면으로 돌아간다
  · 어느 화면에도 눌린 위젯이 없다
"""
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-guild-ui-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import api as apimod                      # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_box, ui_guild, ui_hub           # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

OK = FAIL = 0
COST, MAXN = 50000, 15
MISSIONS = (("attend", "길드에 출석하기", 1, 1), ("catch", "야생 포켓몬 잡기", 5, 2),
            ("battle", "야생 포켓몬과 싸워 이기기", 5, 2), ("gym", "관장 배틀에서 이기기", 3, 2),
            ("rank", "랜덤 배틀 하기", 10, 3))
TIERS = ((10, 5, 0), (25, 0, 10), (45, 5, 15), (70, 0, 20), (100, 10, 30))
ROLE_KR = {"master": "마스터", "sub": "부마스터", "member": "길드원"}


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class FakeServer(object):
    """길드 하나까지만 아는 서버 흉내. 사람마다 Api(server, uid) 로 붙는다."""

    def __init__(self):
        self.names = {1: "가람", 2: "나래", 3: "다솜"}
        self.money = {1: 60000, 2: 0, 3: 0}
        self.coin = {1: 0, 2: 0, 3: 0}
        self.balls = {1: 10, 2: 10, 3: 10}
        self.cool = {}
        self.g = None                 # {"name","intro","mode","master","points"}
        self.roles = {}               # {uid: role}
        self.reqs = []                # [(uid, message)]
        self.chat = []                # [{"id","userId","name","body"}]
        self.done = {}                # {uid: set(mission key)}
        self.claimed = {}             # {uid: set(tier)}
        self.calls = []
        self.long_profile = False     # 프로필에 칭호·시즌을 잔뜩 싣는다 (창 안쪽이 굴러가나 본다)
        self.others = []              # 목록에 같이 나오는 남의 길드들 (다른 길드 둘러보기)

    def fail(self, msg, code=400):
        raise apimod.ApiError(msg, code)

    def say(self, body, uid=None):
        self.chat.append({"id": len(self.chat) + 1, "userId": uid, "name": self.names.get(uid, ""),
                          "body": body, "at": "2026-10-06T03:04:05+00:00"})

    def points(self, uid=None):
        pts = dict((m[0], m[3]) for m in MISSIONS)
        if uid is not None:
            return sum(pts[k] for k in self.done.get(uid, ()))
        return sum(pts[k] for u in self.done for k in self.done[u])

    def stamp(self):
        return "%d.%d.%d.%s" % (len(self.roles), len(self.reqs), self.points(),
                                (self.g or {}).get("intro", ""))


class Api(object):

    def __init__(self, server, me):
        self.s, self.me = server, me

    # ---- 화면 하나에 줄 것
    def guild(self):
        s, me = self.s, self.me
        s.calls.append("guild")
        base = {"me": me, "coin": s.coin[me], "money": s.money[me], "createCost": COST, "max": MAXN,
                "rejoinHours": 24, "cooldown": s.cool.get(me, 0),
                "limits": {"name": [2, 12], "intro": 80, "chat": 200, "subs": 1}}
        if not s.g or me not in s.roles:
            base.update({"guild": None, "role": None,
                         "pending": [{"guildId": 1, "name": s.g["name"], "ago": 5}]
                         if s.g and any(u == me for u, _m in s.reqs) else []})
            return base
        s.done.setdefault(me, set()).add("attend")
        total, mine = s.points(), s.points(me)
        role = s.roles[me]
        members = [{"id": u, "name": s.names[u], "role": r, "roleKr": ROLE_KR[r], "online": u == me,
                    "lastSeenAgo": 7200, "points": s.points(u), "today": s.points(u),
                    "title": None, "frameColor": None, "tierKr": None, "ranked": False,
                    "me": u == me} for u, r in s.roles.items()]
        members.sort(key=lambda x: ({"master": 0, "sub": 1, "member": 2}[x["role"]], x["name"]))
        base.update({
            "guild": {"id": 1, "name": s.g["name"], "intro": s.g["intro"],
                      "joinMode": s.g["mode"], "masterId": s.g["master"],
                      "masterName": s.names[s.g["master"]], "members": len(s.roles), "max": MAXN,
                      "points": total},
            "role": role, "roleKr": ROLE_KR[role], "members": members, "pending": [],
            "requests": [{"id": u, "name": s.names[u], "message": m, "ago": 3, "tierKr": None,
                          "ranked": False} for u, m in s.reqs] if role != "member" else [],
            "mission": {
                "day": "2026-10-06", "resetIn": 3 * 3600 + 720, "myPoints": mine, "myMax": 10,
                "guildPoints": total, "guildMax": 100,
                "missions": [{"key": k, "name": n, "goal": goal, "points": p,
                              "n": goal if k in s.done.get(me, ()) else 0,
                              "done": k in s.done.get(me, ())} for k, n, goal, p in MISSIONS],
                "tiers": [{"tier": i + 1, "need": need, "balls": b, "coin": c,
                           "reward": " · ".join(x for x in (("몬스터볼 %d개" % b) if b else "",
                                                             ("길드 코인 %d개" % c) if c else "") if x),
                           "reached": total >= need, "claimed": (i + 1) in s.claimed.get(me, ()),
                           "canClaim": total >= need and mine > 0
                           and (i + 1) not in s.claimed.get(me, ())}
                          for i, (need, b, c) in enumerate(TIERS)]},
            "chatLast": len(s.chat), "stamp": s.stamp(),
            "can": {"manage": role != "member", "master": role == "master"}})
        return base

    def guild_list(self, q="", page=1):
        s = self.s
        rows = []
        if s.g and (not q or q in s.g["name"]):
            rows.append({"id": 1, "name": s.g["name"], "intro": s.g["intro"], "joinMode": s.g["mode"],
                         "masterName": s.names[s.g["master"]], "members": len(s.roles), "max": MAXN,
                         "points": 0, "full": False,
                         "requested": any(u == self.me for u, _m in s.reqs)})
        rows += [dict(g) for g in s.others if not q or q in g["name"]]
        return {"guilds": rows, "page": 1, "pages": 1, "total": len(rows), "query": q}

    def guild_create(self, name, intro="", mode="open"):
        s, me = self.s, self.me
        if len(name) > 12:
            s.fail("길드 이름이 너무 깁니다. 길드 이름은 2~12자로 지어 주세요. 띄어쓰기도 글자 수에 "
                   "들어갑니다. 지금 적은 이름은 %d자입니다. 조금 줄여서 다시 만들어 주세요." % len(name))
        if not (2 <= len(name) <= 12):
            s.fail("길드 이름은 2~12자로 지어 주세요.")
        if s.money[me] < COST:
            s.fail("돈이 모자랍니다.")
        s.money[me] -= COST
        s.g = {"name": name, "intro": intro, "mode": mode, "master": me}
        s.roles = {me: "master"}
        s.say("%s 길드가 만들어졌습니다!" % name)
        return {"ok": True, "message": "%s 길드를 만들었습니다!" % name}

    def guild_join(self, gid, message=""):
        s, me = self.s, self.me
        if s.g["mode"] == "open":
            s.roles[me] = "member"
            s.say("%s 님이 길드에 들어왔습니다." % s.names[me])
            return {"ok": True, "joined": True, "message": "들어갔습니다!"}
        s.reqs.append((me, message))
        return {"ok": True, "joined": False, "message": "가입 신청을 넣었습니다."}

    def guild_cancel(self, gid):
        self.s.reqs = [(u, m) for u, m in self.s.reqs if u != self.me]
        return {"ok": True, "message": "가입 신청을 거뒀습니다."}

    def guild_accept(self, uid):
        s = self.s
        s.reqs = [(u, m) for u, m in s.reqs if u != uid]
        s.roles[uid] = "member"
        s.say("%s 님이 길드에 들어왔습니다." % s.names[uid])
        return {"ok": True, "message": "받았습니다."}

    def guild_reject(self, uid):
        self.s.reqs = [(u, m) for u, m in self.s.reqs if u != uid]
        return {"ok": True, "message": "돌려보냈습니다."}

    def guild_kick(self, uid):
        s = self.s
        s.roles.pop(uid, None)
        s.cool[uid] = 24 * 3600
        s.say("%s 님이 길드에서 내보내졌습니다." % s.names[uid])
        return {"ok": True, "message": "내보냈습니다."}

    def guild_role(self, uid, role):
        self.s.roles[uid] = role
        return {"ok": True, "message": "바꿨습니다."}

    def guild_master(self, uid):
        s = self.s
        s.roles[self.me], s.roles[uid] = "sub", "master"
        s.g["master"] = uid
        return {"ok": True, "message": "넘겼습니다."}

    def guild_settings(self, intro=None, mode=None):
        s = self.s
        s.calls.append(("settings", intro, mode))
        if intro is not None:
            s.g["intro"] = intro
        if mode is not None:
            s.g["mode"] = mode
        return {"ok": True, "message": "바꿨습니다."}

    def guild_leave(self):
        s = self.s
        s.roles.pop(self.me, None)
        s.cool[self.me] = 24 * 3600
        if not s.roles:
            s.g = None
        return {"ok": True, "message": "나왔습니다."}

    def guild_disband(self):
        s = self.s
        s.g, s.roles, s.reqs, s.chat = None, {}, [], []
        return {"ok": True, "message": "해산했습니다."}

    # ---- 채팅
    def guild_chat(self, after=0):
        s, me = self.s, self.me
        s.calls.append(("chat", after))
        if not s.g or me not in s.roles:
            return {"guild": None, "messages": [], "last": 0}
        rows = [dict(m, mine=m["userId"] == me, system=m["userId"] is None, ago=1)
                for m in s.chat if m["id"] > after]
        return {"guild": 1, "messages": rows, "last": s.chat[-1]["id"] if s.chat else after,
                "stamp": s.stamp()}

    def guild_say(self, body):
        s = self.s
        s.say(body, self.me)
        return {"ok": True, "id": len(s.chat)}

    # ---- 미션·상점
    def guild_claim(self, tier):
        s, me = self.s, self.me
        _need, balls, coin = TIERS[tier - 1]
        s.claimed.setdefault(me, set()).add(tier)
        s.balls[me] += balls
        s.coin[me] += coin
        return {"ok": True, "message": "%d단계 보상을 받았습니다" % tier, "coin": s.coin[me]}

    def guild_shop(self):
        s, me = self.s, self.me
        items = [{"id": "POKEBALL", "kr": "몬스터볼", "cat": "ball", "coin": 1,
                  "note": "야생 포켓몬에게 던져서 잡는 볼."},
                 {"id": "ULTRABALL", "kr": "하이퍼볼", "cat": "ball", "coin": 4, "note": ""},
                 {"id": "RARECANDY", "kr": "이상한사탕", "cat": "misc", "coin": 40,
                  "desc": "포켓몬의 레벨이 1 올라가는 사탕. 아주 긴 설명이 붙어도 줄을 바꿔 다 보여야 한다."}]
        return {"items": items, "coin": s.coin[me], "bag": {"POKEBALL": s.balls[me]},
                "inGuild": me in s.roles}

    def guild_buy(self, item, count=1):
        s, me = self.s, self.me
        price = {"POKEBALL": 1, "ULTRABALL": 4, "RARECANDY": 40}[item] * count
        if s.coin[me] < price:
            s.fail("길드 코인이 모자랍니다.")
        s.coin[me] -= price
        if item == "POKEBALL":
            s.balls[me] += count
        return {"ok": True, "spent": price, "coin": s.coin[me], "message": "샀습니다!"}

    def guild_profile(self, uid):
        """마이페이지에 보이는 것 (서버의 mypage.card) + 길드 쪽 정보."""
        s = self.s
        s.calls.append(("profile", uid))
        if uid not in s.roles or self.me not in s.roles:
            s.fail("같은 길드원의 프로필만 볼 수 있습니다.", 403)
        seasons = [{"season": 3, "current": True, "ranked": True, "rank": 4, "tierKr": "슈퍼볼",
                    "rp": 1234, "games": 20, "wins": 12, "losses": 7, "draws": 1, "title": None},
                   {"season": 2, "current": False, "ranked": True, "rank": 9, "tierKr": "몬스터볼",
                    "rp": 880, "games": 31, "wins": 15, "losses": 16, "draws": 0,
                    "title": "시즌 2 도전자"}]
        if s.long_profile:
            seasons += [{"season": n, "current": False, "ranked": True, "rank": 30 + n,
                         "tierKr": "몬스터볼", "rp": 500, "games": 10, "wins": 5, "losses": 5,
                         "draws": 0, "title": None} for n in (1,)]
        own = [{"id": "dex1", "name": "도감 수집가"}, {"id": "gym1", "name": "관동 정복자"}]
        if s.long_profile:
            own += [{"id": "t%d" % i, "name": "아주 긴 이름의 칭호 %d번" % i} for i in range(14)]
        return {"user": {"id": uid, "name": s.names[uid], "createdAt": "2026-09-23T03:00:00+00:00",
                         "days": 13, "title": "도감 수집가", "frameColor": None, "tier": "super",
                         "tierKr": "슈퍼볼"},
                "counts": {"pokemon": 132, "shiny": 3, "topLevel": 100, "dexCaught": 214,
                           "dexSeen": 380, "dexTotal": 1025, "friends": 7},
                "gym": {"cleared": 12, "total": 18, "wins": 31},
                "raid": {"games": 9, "wins": 5, "damage": 0},
                "titles": {"owned": own, "count": len(own), "total": 40, "equipped": "도감 수집가"},
                "seasons": seasons,
                "guild": {"role": s.roles[uid], "roleKr": ROLE_KR[s.roles[uid]],
                          "joinedAt": "2026-10-05T00:00:00+00:00", "points": 120, "today": 4,
                          "online": False, "lastSeenAgo": 7200, "me": uid == self.me}}


class FakeApp(object):
    def __init__(self, root, api):
        self.root, self.api = root, api
        self.guild_window = None
        self.synced = 0

    def request_sync(self):
        self.synced += 1


def wait(root, cond, sec=6.0):
    end = time.time() + sec
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.01)
    return cond()


def settle(root, sec=0.35):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def labels(w, text):
    out = []

    def walk(x):
        for c in x.winfo_children():
            try:
                if str(c.cget("text")) == text and c.winfo_ismapped():
                    out.append(c)
            except Exception:                               # noqa: BLE001
                pass
            walk(c)
    walk(w)
    return out


def size(win):
    return "%dx%d (내용이 바라는 높이 %d)" % (win.winfo_width(), win.winfo_height(),
                                         win.winfo_reqheight())


def slack(win):
    """창 높이 - 내용이 바라는 높이. 0 이면 딱 맞는다 (아래에 빈칸도, 눌린 것도 없다)."""
    win.update_idletasks()
    return win.winfo_height() - win.winfo_reqheight()


def inside(box, widget):
    """그 위젯이 box(창이나 굴러가는 칸) 안에 위아래로 다 들어와 있나."""
    y0 = widget.winfo_rooty()
    return (widget.winfo_ismapped() and y0 >= box.winfo_rooty()
            and y0 + widget.winfo_height() <= box.winfo_rooty() + box.winfo_height())


def canvas_of(win):
    """창 안의 굴러가는 칸."""
    found = []

    def walk(x):
        for c in x.winfo_children():
            if c.winfo_class() == "Canvas" and getattr(c, "wheel_div", 0):
                found.append(c)
            walk(c)
    walk(win)
    return found[0]


def clipped_wide(box):
    """굴러가는 칸 안에서 옆으로 잘린 글. (squeezed 는 굴러가는 칸 안을 안 본다.)"""
    out = []

    def walk(x):
        for c in x.winfo_children():
            try:
                if c.winfo_class() == "Label" and c.winfo_width() > 1 \
                        and c.winfo_reqwidth() > c.winfo_width() + 1:
                    out.append((str(c.cget("text"))[:20], c.winfo_reqwidth(), c.winfo_width()))
            except Exception:                               # noqa: BLE001
                pass
            walk(c)
    walk(box)
    return out


def shown(root, fn):
    """되묻는 창처럼 **닫힐 때까지 기다리는** 창을 띄우고, 기다리지 않고 그 창을 돌려준다."""
    got = {}
    keep = tk.Misc.wait_window
    tk.Misc.wait_window = lambda self, win=None: got.setdefault("win", win)
    try:
        fn()
    finally:
        tk.Misc.wait_window = keep
    settle(root, 0.3)
    return got["win"]


def press(w, text, i=0):
    """그 글자가 적힌 단추를 진짜 마우스처럼 누른다."""
    b = labels(w, text)[i]
    b.event_generate("<ButtonPress-1>", x=3, y=3)
    b.event_generate("<ButtonRelease-1>", x=3, y=3)


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda *a: errors.append(a)
    ui_guild.CHAT_MS = 150            # 검사에서는 2초를 기다리지 않는다
    ui_box.confirm = lambda *a, **k: True
    srv = FakeServer()
    A, B, C = Api(srv, 1), Api(srv, 2), Api(srv, 3)

    print("=== 탭 ===")
    keys = [t[0] for t in ui_hub.TABS]
    chk("'길드' 탭이 친구 다음에 있다", "guild" in keys and keys.index("guild") == keys.index("friends") + 1, keys)
    chk("길드 탭의 창은 GuildWindow", dict((t[0], t[2]) for t in ui_hub.TABS)["guild"] is ui_guild.GuildWindow)
    chk("레이드 탭은 뺐다 (1.10.0 - 이벤트가 끝났다)", "raid" not in keys
        and "레이드" not in [t[1] for t in ui_hub.TABS], keys)

    print("\n=== 길드가 없을 때 ===")
    app = FakeApp(root, A)
    w = ui_guild.GuildWindow(app)
    top = w.win.winfo_toplevel()
    top.deiconify()
    top.geometry("1000x680+60+40")
    wait(root, lambda: w.data is not None and w.found is not None)
    settle(root)
    tx = texts(top)
    chk("만드는 값과 정원이 적혀 있다", any("50,000원" in x and "정원 15명" in x for x in tx), tx[:6])
    chk("아직 길드가 없다고 알려 준다", any("아직 길드가 없습니다" in x for x in tx))
    chk("채팅은 묻지 않는다 (길드가 없다)", not [c for c in srv.calls if c and c[0] == "chat"], srv.calls)
    chk("웹소켓도 안 붙는다 (길드가 없다)", w.sock is None and not w.live)
    bad = squeezed(top)
    chk("눌린 위젯 없음", not bad, bad[:3])
    dlg = w.create_dialog()
    settle(root, 0.3)
    bad = squeezed(dlg)
    chk("만들기 창: 이름·소개·가입 방식·값, 눌린 위젯 없음",
        not bad and any("가입 방식" in x for x in texts(dlg)) and any("50,000원" in x for x in texts(dlg)), bad[:3])
    chk("  창은 내용만큼만 (아래에 빈칸이 없다)", slack(dlg) == 0, size(dlg))
    w._dialog["ok"]()
    chk("이름을 안 적으면 창 안에서 알려 준다", "이름" in w._dialog["warn"].cget("text"))
    w._dialog["warn"].configure(text="")
    h0 = dlg.winfo_height()
    w._dialog["name"].set("가" * 30)
    w._dialog["ok"]()
    wait(root, lambda: "너무" in w._dialog["warn"].cget("text"), 3)
    settle(root, 0.3)
    bad = squeezed(dlg)
    chk("  까닭이 두 줄이면 창이 그만큼 늘어난다 (단추가 안 눌린다)", not bad and dlg.winfo_height() > h0
        and slack(dlg) == 0, (bad[:2], h0, size(dlg)))
    w._dialog["name"].set("가")
    w._dialog["ok"]()
    wait(root, lambda: "2~12자" in w._dialog["warn"].cget("text"), 3)
    chk("서버가 거절한 까닭도 창 안에 뜬다 (창은 안 닫힌다)", "2~12자" in w._dialog["warn"].cget("text")
        and dlg.winfo_exists(), w._dialog["warn"].cget("text"))
    w._dialog["name"].set("피카단")
    w._dialog["intro"].set("피카츄를 좋아하는 사람들")
    w._dialog["mode"]["v"] = "open"
    w._dialog["ok"]()
    wait(root, lambda: w.in_guild() and w.chat_box is not None and w.chat_lines > 0)
    settle(root)
    chk("만들면 길드 화면이 된다", w.mode == "guild" and w.h_name.cget("text") == "피카단"
        and not dlg.winfo_exists(), w.mode)
    chk("돈이 줄었으니 다른 화면도 맞춘다", srv.money[1] == 10000 and app.synced == 1, app.synced)

    print("\n=== 채팅 ===")
    chk("만들어졌다는 알림 줄", "피카단 길드가 만들어졌습니다" in w.chat_text(), w.chat_text())
    chk("칸 여섯: 채팅·길드원·미션·코인 상점·다른 길드·관리",
        [lb.cget("text") for lb in w.seg.cells.values()]
        == ["채팅", "길드원", "미션", "코인 상점", "다른 길드", "관리"])
    root.update_idletasks()
    cells = list(w.seg.cells.values())
    chk("  여섯 칸이 한 줄에 다 들어간다 (잘린 글자 없음)",
        all(c.winfo_reqwidth() <= c.winfo_width() + 1 for c in cells)
        and cells[-1].winfo_rootx() + cells[-1].winfo_width() <= top.winfo_rootx() + top.winfo_width(),
        [(c.cget("text"), c.winfo_reqwidth(), c.winfo_width()) for c in cells])
    w.chat_var.set("  안녕하세요   반갑습니다 ")
    w.send_chat()
    wait(root, lambda: "반갑습니다" in w.chat_text(), 3)
    chk("보낸 말이 뜨고 칸이 비워진다", "안녕하세요 반갑습니다" in w.chat_text() and w.chat_var.get() == "",
        w.chat_text())
    B.guild_join(1)
    B.guild_say("잘 부탁드려요")
    got = wait(root, lambda: "잘 부탁드려요" in w.chat_text(), 4)
    chk("다른 사람의 말을 스스로 받아 온다 (폴링)", got, w.chat_text()[-60:])
    chk("  번호 뒤의 줄만 묻는다", any(c[0] == "chat" and c[1] > 0 for c in srv.calls if c and c != "guild"))
    box = w.chat_box
    wait(root, lambda: w.data["guild"]["members"] == 2, 4)
    settle(root, 0.3)
    chk("사람 수가 바뀌면 머리가 따라 바뀐다", any("길드원 2 / 15명" in x for x in texts(top)))
    chk("  채팅 칸은 다시 그리지 않는다 (쓰던 글·읽던 자리가 그대로)", w.chat_box is box
        and "반갑습니다" in w.chat_text())
    lines = w.chat_text().split("\n")
    chk("줄마다 한 번씩만 들어온다", len(lines) == len(set(lines)) == w.chat_lines, lines)
    w.chat_var.set("가" * 201)
    w.send_chat()
    chk("너무 긴 말은 보내지 않고 알려 준다", "200자" in w.status._label.cget("text")
        and len(srv.chat) == 4, len(srv.chat))
    w.chat_var.set("")
    bad = squeezed(top)
    chk("눌린 위젯 없음", not bad, bad[:3])
    n = len([c for c in srv.calls if c and c[0] == "chat"])
    top.withdraw()                              # 창을 가리면
    settle(root, 0.8)
    chk("창이 안 보이면 채팅을 묻지 않는다", len([c for c in srv.calls if c and c[0] == "chat"]) == n,
        len([c for c in srv.calls if c and c[0] == "chat"]) - n)
    top.deiconify()
    settle(root, 0.5)
    chk("  다시 보이면 이어서 묻는다", len([c for c in srv.calls if c and c[0] == "chat"]) > n)

    print("\n=== 길드원 ===")
    w.show_tab("members")
    settle(root)
    tx = texts(top)
    chk("길드원 둘, 마스터 표시", "가람" in tx and "나래" in tx and "마스터" in tx, tx[-10:])
    chk("오늘 점수와 접속 표시", any("오늘 1점" in x for x in tx) and "접속 중" in tx and "2시간 전" in tx,
        [x for x in tx if "오늘" in x or "전" in x])
    chk("채팅 칸을 떠나면 채팅을 묻지 않는다", not w.chat_visible())
    mb = next(m for m in w.data["members"] if not m["me"])
    me = next(m for m in w.data["members"] if m["me"])
    chk("마스터가 길드원에게 할 수 있는 일", [a[0] for a in w.member_actions(mb)]
        == ["부마스터로 임명", "마스터 넘기기", "길드에서 내보내기"], [a[0] for a in w.member_actions(mb)])
    chk("나 자신에게는 할 것이 없다", w.member_actions(me) == [] and w.manage_dialog(me) is None)
    chk("'관리' 단추는 다른 사람 줄에만", len(labels(top, "관리")) == 2, len(labels(top, "관리")))    # 칸 이름 + 한 줄
    dlg = w.manage_dialog(mb)
    settle(root, 0.3)
    bad = squeezed(dlg)
    chk("관리 창에 눌린 위젯 없음", not bad, bad[:3])
    chk("  창은 단추 셋만큼만 (아래에 빈칸이 없다)", slack(dlg) == 0, size(dlg))
    three = dlg.winfo_height()
    press(dlg, "부마스터로 임명")
    wait(root, lambda: any(m["role"] == "sub" for m in w.data["members"]), 4)
    settle(root, 0.3)
    chk("부마스터로 임명된다", srv.roles[2] == "sub" and "부마스터" in texts(top))
    mb = next(m for m in w.data["members"] if not m["me"])
    chk("  부마스터에게는 '해제' 가 뜬다", [a[0] for a in w.member_actions(mb)][0] == "부마스터 해제")
    chk("  임명을 되묻는 말에 '공지' 가 없다 (공지 칸을 뺐다)",
        not any("공지" in a[3] for m in w.data["members"] for a in w.member_actions(m)))

    print("\n=== 프로필 (마이페이지에 보이는 것) ===")
    dlg = w.profile_dialog(2)
    wait(root, lambda: dlg.profile is not None, 4)
    settle(root, 0.4)
    tx = texts(dlg)
    chk("이름·티어·칭호·자리·가입일", "나래" in tx and "슈퍼볼" in tx and "도감 수집가" in tx
        and any("부마스터" in x and "함께한 지 13일째" in x and "2026.09.23 가입" in x for x in tx), tx[:8])
    chk("포켓몬·색이 다른 포켓몬·도감·이긴 관장·레이드·친구", all(x in tx for x in (
        "포켓몬", "132마리", "가장 높은 레벨 100", "색이 다른 포켓몬", "3마리", "도감", "214 / 1025",
        "본 종 380", "이긴 관장", "12 / 18", "모두 31번 승리", "레이드", "5승", "친구", "7명")), tx)
    chk("시즌 기록: 지금 시즌과 지난 시즌", "시즌 기록" in tx and "시즌 3 (진행 중)" in tx
        and any("4위" in x and "슈퍼볼" in x and "RP 1234" in x and "20전 12승 7패 1무" in x for x in tx)
        and "시즌 2" in tx and any("칭호 '시즌 2 도전자'" in x for x in tx), [x for x in tx if "시즌" in x])
    chk("칭호와 길드 미션 점수", "관동 정복자" in tx and "2 / 40" in tx
        and any("오늘 4점" in x and "누적 120점" in x for x in tx), tx[-8:])
    chk("소지금은 안 보인다 (본인만 본다)", not any("소지금" in x for x in tx))
    chk("길드원용 주소로 받는다", ("profile", 2) in srv.calls)
    bad = squeezed(dlg)
    chk("눌린 위젯 없음", not bad, bad[:3])
    chk("창이 정해 둔 크기를 안 넘는다", dlg.winfo_width() == ui_guild.PROFILE_W
        and dlg.winfo_height() <= ui_guild.PROFILE_H, size(dlg))
    chk("  '닫기' 가 창 안에 다 보인다", inside(dlg, labels(dlg, "닫기")[0]), size(dlg))
    short = dlg.winfo_height()
    dlg.destroy()

    srv.long_profile = True
    dlg = w.profile_dialog(2)
    wait(root, lambda: dlg.profile is not None, 4)
    settle(root, 0.5)
    cv = canvas_of(dlg)
    wide = clipped_wide(cv)
    chk("  굴러가는 칸 안에 옆으로 잘린 글이 없다", not wide, wide[:3])
    lo, hi = cv.yview()
    chk("내용이 길면 창을 키우지 않고 안쪽이 굴러간다", dlg.winfo_height() == ui_guild.PROFILE_H
        and hi - lo < 0.99, (size(dlg), lo, hi))
    chk("  '닫기' 는 굴러가지 않고 창 아래에 그대로 있다", inside(dlg, labels(dlg, "닫기")[0]))
    cv.yview_moveto(1.0)
    settle(root, 0.2)
    last = [x for x in labels(dlg, "아주 긴 이름의 칭호 13번")]
    chk("  끝까지 굴리면 마지막 칭호가 보인다", last and inside(cv, last[0]) and cv.yview()[1] > 0.99,
        cv.yview())
    bad = squeezed(dlg)
    chk("  눌린 위젯 없음", not bad, bad[:3])
    dlg.destroy()
    srv.long_profile = False

    print("\n=== 작은 창들의 크기 ===")
    one = next(m for m in w.data["members"] if not m["me"])
    dlg = w.manage_dialog(one)
    settle(root, 0.3)
    n = len(w.member_actions(one))
    chk("관리 창은 단추 수만큼 (%d개)" % n, slack(dlg) == 0 and not squeezed(dlg), size(dlg))
    dlg.destroy()
    # 검사는 위에서 confirm·ask_text 를 가짜로 바꿔 뒀다. 진짜(_confirm, _ask_text)를 띄운다.
    for name, fn in (
            ("되묻는 창 (한 줄)", lambda: ui_box._confirm(w.win, "길드 가입", "피카단 길드에 들어갈까요?",
                                                    danger=False, ok_text="들어가기")),
            ("되묻는 창 (긴 글)", lambda: ui_box._confirm(w.win, "길드에서 내보내기", w.member_actions(one)[-1][3])),
            ("한마디 묻는 창", lambda: ui_box._ask_text(w.win, "가입 신청", "피카단 길드에 가입 신청을 넣습니다.",
                                                  "마스터에게 남길 한마디 (안 적어도 됩니다)"))):
        dlg = shown(root, fn)
        bad = squeezed(dlg)
        chk("%s: 내용만큼만 뜨고 눌린 위젯 없음" % name, not bad and slack(dlg) == 0
            and dlg.winfo_height() < 320, (bad[:2], size(dlg)))
        dlg.destroy()
    small = tk.Toplevel(root)
    U.style_window(small, "작은 창", 380, 196)
    settle(root, 0.2)
    chk("창을 받은 크기보다 키우지 않는다 (예전에는 320 으로 부풀었다)", small.winfo_height() == 196
        and small.winfo_width() == 380, size(small))
    small.destroy()
    bad = squeezed(top)
    chk("눌린 위젯 없음", not bad, bad[:3])

    print("\n=== 미션 ===")
    w.show_tab("mission")
    settle(root)
    tx = texts(top)
    chk("길드 점수와 자정까지 남은 시간", "오늘의 길드 점수" in tx and any("3시간 12분 뒤" in x for x in tx),
        [x for x in tx if "뒤" in x])
    chk("단계 다섯과 보상", all(("%d단계" % i) in tx for i in range(1, 6)) and "몬스터볼 5개" in tx
        and "몬스터볼 10개 · 길드 코인 30개" in tx, [x for x in tx if "코인" in x])
    chk("내 미션 다섯 가지", all(m[1] in tx for m in MISSIONS) and "오늘 1 / 10점" in tx
        and not any("채팅" in x and "한마디" in x for x in tx))
    chk("한 것은 1 / 1, 안 한 것은 0 / 5, 랜덤 배틀은 0 / 10 에 +3점", "1 / 1" in tx and "0 / 5" in tx
        and "0 / 10" in tx and "+3점" in tx)
    chk("점수가 모자라면 '받기' 가 없다", not labels(top, "받기") and any("점 남음" in x for x in tx))
    bad = squeezed(top)
    chk("눌린 위젯 없음", not bad, bad[:3])
    srv.done[1] = set(m[0] for m in MISSIONS)                 # 10점
    w.refresh()
    wait(root, lambda: w.data["mission"]["guildPoints"] >= 10 and labels(top, "받기"), 4)
    settle(root, 0.3)
    chk("10점을 넘으면 1단계에 '받기' 가 생긴다", len(labels(top, "받기")) == 1)
    press(top, "받기")
    wait(root, lambda: 1 in srv.claimed.get(1, ()), 4)
    settle(root, 0.4)
    chk("받으면 '받음' 이 되고 몬스터볼이 는다", srv.balls[1] == 15 and "받음" in texts(top)
        and not labels(top, "받기") and app.synced == 2, app.synced)

    print("\n=== 코인 상점 ===")
    srv.coin[1] = 12
    # 몬스터볼 그림 하나를 이 PC 에 받아 둔 것으로 친다 (나머지는 그림 없이 자리만 있다)
    from PIL import Image
    from poketdesktop import item_icons
    Image.new("RGBA", (30, 30), (220, 60, 60, 255)).save(os.path.join(item_icons.icon_dir(), "POKEBALL.png"))
    w.show_tab("shop")
    wait(root, lambda: w.shop is not None, 4)
    settle(root)
    tx = texts(top)
    chk("물건과 코인 값", "몬스터볼" in tx and "코인 1" in tx and "이상한사탕" in tx and "코인 40" in tx, tx[-12:])
    chk("가진 수가 보인다", any("가진 것 15" in x for x in tx))
    on = dict((k, b.enabled) for k, b in w.shop_btns.items())
    chk("코인 12개로 살 수 있는 단추만 켜져 있다", w.h_coin.cget("text") == "길드 코인 12개"
        and on == {("POKEBALL", 1): True, ("POKEBALL", 10): True, ("ULTRABALL", 1): True,
                   ("ULTRABALL", 10): False, ("RARECANDY", 1): False, ("RARECANDY", 10): False}, on)
    bad = squeezed(top)
    chk("눌린 위젯 없음 (긴 설명이 줄을 바꾼다)", not bad, bad[:3])

    print("  -- 카드 격자·그림·찾기 (1.10.1)")
    root.update_idletasks()
    cards = [c for _it, c in w.shop_cards]
    cvw = w.shop_inner.master.winfo_width()
    cols = ui_guild.shop_cols(cvw)
    chk("폭을 모르면 석 장, 좁으면 두 장, 넓으면 넉 장까지", ui_guild.shop_cols(1) == 3
        and ui_guild.shop_cols(500) == 2 and ui_guild.shop_cols(700) == 3
        and ui_guild.shop_cols(940) == 4 and ui_guild.shop_cols(3000) == 4)
    n = min(cols, len(cards))
    chk("카드가 격자로 놓인다 (한 줄에 %d장)" % cols, w._shop_cols == cols and cols >= 2
        and len(set(c.winfo_y() for c in cards[:n])) == 1 and len(set(c.winfo_x() for c in cards[:n])) == n,
        (cvw, cols, [(c.winfo_x(), c.winfo_y()) for c in cards]))
    chk("  카드 폭이 같다", max(c.winfo_width() for c in cards[:n]) - min(c.winfo_width() for c in cards[:n]) <= 2,
        [c.winfo_width() for c in cards])
    chk("  같은 줄의 카드는 높이가 같다 (단추가 가지런하다)", len(set(c.winfo_height() for c in cards[:n])) == 1
        and len(set(w.shop_btns[(it["id"], 1)].holder.winfo_rooty() for it, _c in w.shop_cards[:n])) == 1,
        [c.winfo_height() for c in cards])
    chk("  칸 밖으로 나간 카드가 없다", all(c.winfo_x() + c.winfo_width() <= cvw + 1 for c in cards),
        [(c.winfo_x(), c.winfo_width()) for c in cards])
    wide = clipped_wide(w.shop_inner)
    chk("  카드 안에 옆으로 잘린 글이 없다", not wide, wide[:3])

    def pictures(card):
        out = []

        def walk(x):
            for c in x.winfo_children():
                try:
                    if c.winfo_class() == "Label" and str(c.cget("image")):
                        out.append(c)
                except Exception:                           # noqa: BLE001
                    pass
                walk(c)
        walk(card)
        return out

    def holders(card):
        return [c for a in card.winfo_children() for c in a.winfo_children()
                if c.winfo_class() == "Frame" and c.winfo_width() == ui_guild.SHOP_ICON
                and c.winfo_height() == ui_guild.SHOP_ICON]
    chk("받아 둔 그림이 카드에 보인다 (몬스터볼)", len(pictures(cards[0])) == 1, pictures(cards[0]))
    chk("  그림이 없어도 자리는 같다 (%dpx)" % ui_guild.SHOP_ICON,
        all(len(holders(c)) == 1 for c in cards) and not pictures(cards[2]),
        [len(holders(c)) for c in cards])
    w.shop_q.set("볼")
    settle(root, 0.25)
    chk("'볼' 로 찾으면 볼만 남는다", [it["id"] for it in w.shop_shown()] == ["POKEBALL", "ULTRABALL"]
        and [bool(c.winfo_ismapped()) for c in cards] == [True, True, False],
        [bool(c.winfo_ismapped()) for c in cards])
    chk("  몇 개인지 적힌다", w.shop_count.cget("text") == "2개", w.shop_count.cget("text"))
    w.shop_q.set("사 탕")
    settle(root, 0.25)
    chk("띄어쓰기는 안 가린다", [it["id"] for it in w.shop_shown()] == ["RARECANDY"]
        and cards[2].winfo_ismapped() and not cards[0].winfo_ismapped(),
        [it["id"] for it in w.shop_shown()])
    w.shop_q.set("없는도구")
    settle(root, 0.25)
    chk("맞는 것이 없으면 없다고 알린다", not any(c.winfo_ismapped() for c in cards)
        and w.shop_none.winfo_ismapped() and "없는도구" in w.shop_none.cget("text"),
        w.shop_none.cget("text"))
    w.shop_q.set("볼")
    settle(root, 0.25)
    w.buy("POKEBALL", 1)
    wait(root, lambda: srv.coin[1] == 11, 4)
    wait(root, lambda: w.shop is not None and w.shop.get("coin") == 11, 4)
    settle(root, 0.3)
    chk("사고 나서 다시 그려도 찾던 말은 남는다", w.shop_q.get() == "볼"
        and [it["id"] for it in w.shop_shown()] == ["POKEBALL", "ULTRABALL"], w.shop_q.get())
    w.shop_q.set("")
    settle(root, 0.25)
    chk("지우면 다 나온다", all(c.winfo_ismapped() for _it, c in w.shop_cards)
        and w.shop_count.cget("text") == "", w.shop_count.cget("text"))
    srv.coin[1] = 12
    srv.balls[1] -= 1
    w.shop = None
    w._draw_tab()
    wait(root, lambda: w.shop is not None, 4)
    settle(root)

    w.buy("POKEBALL", 10)
    wait(root, lambda: srv.coin[1] == 2, 4)
    wait(root, lambda: w.shop is not None and w.shop.get("coin") == 2, 4)
    settle(root, 0.3)
    chk("사면 코인이 줄고 머리의 숫자도 바뀐다", srv.balls[1] == 25 and w.h_coin.cget("text") == "길드 코인 2개",
        w.h_coin.cget("text"))

    print("\n=== 다른 길드 둘러보기 (1.10.1) ===")
    srv.others = [{"id": 2, "name": "꼬부기단", "intro": "물 타입만 받습니다. 매일 미션 열 점씩 채우실 분.",
                   "joinMode": "approve", "masterName": "라온", "members": MAXN, "max": MAXN,
                   "points": 1234, "full": True, "requested": False},
                  {"id": 3, "name": "파이리단", "intro": "", "joinMode": "open", "masterName": "마루",
                   "members": 3, "max": MAXN, "points": 20, "full": False, "requested": False}]
    w.show_tab("guilds")
    wait(root, lambda: w.found is not None and len(w.found.get("guilds") or []) == 3, 4)
    settle(root)
    tx = texts(top)
    chk("길드에 든 채로 다른 길드가 보인다", "꼬부기단" in tx and "파이리단" in tx and tx.count("피카단") >= 2,
        tx[-24:])
    chk("  인원·마스터·누적 점수·소개가 보인다", "%d / %d명" % (MAXN, MAXN) in tx and "마스터 라온" in tx
        and "누적 1,234점" in tx and any("물 타입만 받습니다" in x for x in tx), tx[-24:])
    chk("  내 길드에는 표시가 붙는다", len(labels(top, "내 길드")) == 1, len(labels(top, "내 길드")))
    chk("  가입 단추는 없다 (지금 길드를 나온 뒤에야 가입할 수 있다)",
        not labels(top, "가입") and not labels(top, "가입 신청") and not labels(top, "신청 취소"))
    bad = squeezed(top)
    chk("  눌린 위젯 없음", not bad, bad[:3])
    w.q_var.set("꼬부기")
    w.do_search()
    wait(root, lambda: len((w.found or {}).get("guilds") or []) == 1, 4)
    settle(root)
    tx = texts(top)
    chk("이름으로 찾는다", "꼬부기단" in tx and "파이리단" not in tx, tx[-12:])
    chk("  채팅·미션은 그대로 내 길드 것이다", w.mode == "guild" and w.h_name.cget("text") == "피카단")
    w.q_var.set("")
    w.do_search()
    wait(root, lambda: len((w.found or {}).get("guilds") or []) == 3, 4)
    srv.others = []
    w.show_tab("chat")
    settle(root)
    w.show_tab("guilds")
    wait(root, lambda: w.found is not None and len(w.found.get("guilds") or []) == 1, 4)
    chk("칸을 다시 열면 새로 받는다", len(w.found.get("guilds") or []) == 1, w.found)

    print("\n=== 관리 (마스터) ===")
    w.show_tab("manage")
    settle(root)
    tx = texts(top)
    chk("가입 신청·소개·가입 방식·나가기·해산이 다 있다",
        all(x in tx for x in ("가입 신청", "소개", "가입 방식", "길드 나가기", "길드 해산")), tx[:14])
    chk("  공지 칸은 없다", "공지" not in tx and not any(x.startswith("공지") for x in tx)
        and not hasattr(w, "v_notice"))
    chk("사람이 남아 있으면 '나가기' 대신 까닭을 적는다", any("그냥 나갈 수 없습니다" in x for x in tx)
        and len(labels(top, "길드 나가기")) == 1)                                          # 제목뿐
    bad = squeezed(top)
    chk("눌린 위젯 없음", not bad, bad[:3])
    w.v_intro.set("새 소개")
    press(top, "저장", 0)
    wait(root, lambda: srv.g["intro"] == "새 소개", 4)
    settle(root, 0.3)
    # 작업 스레드에서 입력칸을 읽으면 'main thread is not in main loop' 로 죽는다 (실제로 그랬다)
    chk("소개를 저장한다 (입력칸은 Tk 스레드에서 읽는다)", srv.g["intro"] == "새 소개"
        and "main thread" not in w.status._label.cget("text"), w.status._label.cget("text"))
    chk("  소개가 위쪽에 뜬다", "새 소개" in texts(top))
    w.set_mode("approve")
    wait(root, lambda: w.data["guild"]["joinMode"] == "approve", 4)
    settle(root, 0.3)
    chk("가입 방식을 바꾼다", srv.g["mode"] == "approve" and w.seg_mode.current == "approve")
    C.guild_join(1, "받아 주세요")
    w.refresh()
    wait(root, lambda: len(w.data.get("requests") or []) == 1, 4)
    settle(root, 0.4)
    tx = texts(top)
    chk("가입 신청이 한마디와 함께 보인다", "다솜" in tx and "받아 주세요" in tx and any("가입 신청 1건" in x for x in tx))
    bad = squeezed(top)
    chk("눌린 위젯 없음 (신청이 있을 때)", not bad, bad[:3])
    press(top, "받기")
    wait(root, lambda: 3 in srv.roles, 4)
    wait(root, lambda: w.data["guild"]["members"] == 3, 4)
    chk("받으면 길드원이 된다", srv.roles.get(3) == "member" and not srv.reqs)

    print("\n=== 부마스터·길드원의 화면 ===")
    app2 = FakeApp(root, B)
    w2 = ui_guild.GuildWindow(app2)
    top2 = w2.win.winfo_toplevel()
    top2.deiconify()
    top2.geometry("1000x680+90+70")
    wait(root, lambda: w2.in_guild() and w2.chat_box is not None and w2.chat_lines > 0)
    settle(root)
    chk("들어오기 전의 채팅도 보인다", "반갑습니다" in w2.chat_text())
    w2.show_tab("manage")
    settle(root)
    tx = texts(top2)
    chk("부마스터: 신청은 있고 소개·가입 방식·해산은 없다", "가입 신청" in tx and "공지" not in tx
        and "소개" not in tx and "가입 방식" not in tx and "길드 해산" not in tx, tx[:10])
    chk("  나가기 단추가 있다", len(labels(top2, "길드 나가기")) == 2)
    w2.show_tab("members")
    settle(root)
    m3 = next(m for m in w2.data["members"] if m["id"] == 3)
    m1 = next(m for m in w2.data["members"] if m["id"] == 1)
    chk("부마스터는 일반 길드원만 내보낼 수 있다", [a[0] for a in w2.member_actions(m3)] == ["길드에서 내보내기"]
        and w2.member_actions(m1) == [], ([a[0] for a in w2.member_actions(m3)], w2.member_actions(m1)))
    app3 = FakeApp(root, C)
    w3 = ui_guild.GuildWindow(app3)
    top3 = w3.win.winfo_toplevel()
    top3.deiconify()
    top3.geometry("1000x680+120+100")
    wait(root, lambda: w3.in_guild() and w3.chat_box is not None)
    w3.show_tab("manage")
    settle(root)
    tx = texts(top3)
    chk("길드원: 관리 칸에는 나가기만 있다", "가입 신청" not in tx and "공지" not in tx
        and len(labels(top3, "길드 나가기")) == 2, tx[:8])
    bad = squeezed(top3)
    chk("눌린 위젯 없음 (길드원의 관리 칸)", not bad, bad[:3])
    w3.show_tab("members")
    settle(root)
    chk("길드원에게는 '관리' 단추가 없다", len(labels(top3, "관리")) == 1)                 # 칸 이름뿐

    print("\n=== 내보내지면 ===")
    w3.show_tab("chat")
    settle(root, 0.4)
    A.guild_kick(3)
    wait(root, lambda: w3.mode == "none", 5)
    settle(root, 0.4)
    tx = texts(top3)
    chk("채팅을 묻다가 스스로 찾기 화면으로 돌아간다", w3.mode == "none" and not w3.in_guild()
        and any("길드에 들어가면" in x for x in tx), w3.mode)
    chk("나온 뒤 기다려야 한다는 안내와 꺼진 단추", any("24시간 뒤에 다시 가입" in x for x in tx)
        and not w3.b_create.enabled, [x for x in tx if "뒤에" in x])
    chk("  찾기 목록의 가입 단추도 꺼진다", labels(top3, "가입 신청") != [] and "피카단" in tx)
    bad = squeezed(top3)
    chk("눌린 위젯 없음", not bad, bad[:3])
    w3.close()

    print("\n=== 나가기·해산 ===")
    w2.leave()
    wait(root, lambda: w2.mode == "none", 4)
    chk("길드원이 나간다", 2 not in srv.roles and w2.mode == "none")
    w2.close()
    w.refresh()
    wait(root, lambda: w.data["guild"]["members"] == 1, 4)
    w.show_tab("manage")
    settle(root)
    chk("혼자 남은 마스터에게는 '나가기' 단추가 생긴다", len(labels(top, "길드 나가기")) == 2
        and any("길드가 없어집니다" in x for x in texts(top)))
    ui_box.ask_text = lambda *a, **k: "틀린이름"
    w.disband()
    settle(root, 0.3)
    chk("이름을 틀리게 적으면 해산하지 않는다", srv.g is not None and "다릅니다" in w.status._label.cget("text"))
    ui_box.ask_text = lambda *a, **k: None
    w.disband()
    settle(root, 0.2)
    chk("취소하면 아무 일도 없다", srv.g is not None)
    ui_box.ask_text = lambda *a, **k: "피카단"
    w.disband()
    wait(root, lambda: w.mode == "none", 4)
    settle(root, 0.4)
    chk("이름을 맞게 적으면 해산되고 찾기 화면으로", srv.g is None and w.mode == "none" and w.h_name.cget("text") == "")

    print("\n=== 길드 없이 코인 상점 ===")
    tx = texts(top)
    chk("남은 코인이 있으면 코인 상점 단추가 있다", any("길드 코인이 2개 남아" in x for x in tx) and labels(top, "코인 상점"))
    press(top, "코인 상점")
    wait(root, lambda: w.mode == "coinshop" and w.shop is not None, 4)
    settle(root, 0.4)
    chk("코인 상점만 따로 열린다", "← 길드 찾기" in texts(top) and "몬스터볼" in texts(top))
    w.buy("POKEBALL", 1)
    wait(root, lambda: srv.coin[1] == 1, 4)
    wait(root, lambda: w.shop is not None and w.shop.get("coin") == 1, 4)
    settle(root, 0.3)
    chk("길드가 없어도 살 수 있다", srv.coin[1] == 1 and w.mode == "coinshop" and "길드 코인 1개" in w.h_coin.cget("text"),
        w.h_coin.cget("text"))
    bad = squeezed(top)
    chk("눌린 위젯 없음", not bad, bad[:3])
    press(top, "← 길드 찾기")
    settle(root, 0.4)
    chk("돌아가면 찾기 화면", w.mode == "none" and "길드 만들기" in texts(top))

    print("\n=== 웹소켓으로 받기 ===")
    made = []

    class FakeSocket(object):
        """guild_ws.GuildSocket 대신. push() 로 서버가 민 것을 흉내 낸다."""

        def __init__(self, on_event):
            self.on_event, self.stopped, self.gave_up, self.connected = on_event, False, None, False

        def push(self, ev):
            self.on_event(ev)

        def stop(self):
            self.stopped = True
    keep_make = ui_guild.make_socket
    ui_guild.make_socket = lambda app_, on_event: made.append(FakeSocket(on_event)) or made[-1]

    class Hub(object):
        def __init__(self):
            self.badges = []

        def set_badge(self, key, on):
            self.badges.append((key, on))
    srv2 = FakeServer()
    A2, B2 = Api(srv2, 1), Api(srv2, 2)
    A2.guild_create("웹소켓단", "", "open")
    B2.guild_join(1)
    app4 = FakeApp(root, A2)
    app4.hub = Hub()
    w4 = ui_guild.GuildWindow(app4)
    top4 = w4.win.winfo_toplevel()
    top4.deiconify()
    top4.geometry("1000x680+70+50")
    wait(root, lambda: w4.in_guild() and w4.chat_box is not None and w4.chat_ready)
    settle(root)

    def polls():
        return len([c for c in srv2.calls if c and c[0] == "chat"])
    chk("길드에 들어 있으면 웹소켓을 하나 만든다", len(made) == 1 and w4.sock is made[0], len(made))
    chk("붙기 전에는 2초마다 묻는다", not w4.live and "2초마다" in w4.chat_state.cget("text"),
        w4.chat_state.cget("text"))
    n = polls()
    settle(root, 0.5)
    chk("  (실제로 묻고 있다)", polls() > n, polls() - n)
    sock = made[0]
    sock.push({"t": "open", "userId": 1, "guild": 1, "last": len(srv2.chat)})
    settle(root, 0.3)
    chk("붙으면 '실시간' 으로 바뀐다", w4.live and "실시간" in w4.chat_state.cget("text"),
        w4.chat_state.cget("text"))
    n = polls()
    settle(root, 0.7)
    chk("붙어 있는 동안에는 서버에 묻지 않는다", polls() == n, polls() - n)
    srv2.say("밀려온 말", 2)
    sock.push({"t": "chat", "m": dict(srv2.chat[-1], system=False)})
    root.update()
    chk("밀려온 줄이 그 자리에서 뜬다 (묻지 않고)", "밀려온 말" in w4.chat_text() and polls() == n, w4.chat_text()[-40:])
    sock.push({"t": "chat", "m": dict(srv2.chat[-1], system=False)})
    root.update()
    chk("같은 줄이 또 와도 한 번만 뜬다", w4.chat_text().count("밀려온 말") == 1)
    srv2.say("내가 한 말", 1)
    sock.push({"t": "chat", "m": dict(srv2.chat[-1], system=False)})
    root.update()
    mine = w4.chat_box.tag_ranges("mine")
    chk("내 말은 내 색으로 (내 번호로 가린다)", "내가 한 말" in w4.chat_text() and len(mine) == 2
        and "가람" in w4.chat_box.get(mine[0], mine[1]), len(mine))
    # 지난 줄을 받는 사이에 밀려온 줄: 답보다 먼저 붙이면 답에 든 앞 번호가 사라진다
    srv2.say("끊긴 사이의 말", 2)                # 5번: 웹소켓으로는 못 받았다 (끊겨 있었다 치고)
    srv2.say("다시 붙은 뒤의 말", 2)             # 6번: 답을 기다리는 사이에 밀려온다
    w4._poll_chat()                              # 다시 붙으면 한 번 받아 온다
    sock.push({"t": "chat", "m": dict(srv2.chat[-1], system=False)})
    wait(root, lambda: "다시 붙은 뒤의 말" in w4.chat_text(), 3)
    body = w4.chat_text()
    chk("받는 사이에 밀려온 줄 때문에 앞 줄이 빠지지 않는다", "끊긴 사이의 말" in body
        and body.index("끊긴 사이의 말") < body.index("다시 붙은 뒤의 말")
        and body.count("다시 붙은 뒤의 말") == 1, body[-80:])
    lines = [x for x in w4.chat_text().split("\n") if x.strip()]
    chk("줄 수가 서버의 줄 수와 같다", len(lines) == len(srv2.chat) == w4.chat_lines, (len(lines), len(srv2.chat)))

    print("\n=== 다른 칸·다른 탭에 있을 때 ===")
    w4.show_tab("members")
    settle(root, 0.3)
    srv2.say("안 보는 사이의 말", 2)
    sock.push({"t": "chat", "m": dict(srv2.chat[-1], system=False)})
    srv2.say("알림 줄")
    sock.push({"t": "chat", "m": dict(srv2.chat[-1], system=True)})
    srv2.say("내 말", 1)
    sock.push({"t": "chat", "m": dict(srv2.chat[-1], system=False)})
    root.update()
    chk("다른 칸에 있으면 '채팅' 옆에 수가 붙는다 (남이 한 말만 센다)",
        w4.seg.cells["chat"].cget("text") == "채팅 1" and w4.unread == 1, w4.seg.cells["chat"].cget("text"))
    chk("  길드 탭을 보고 있으니 탭의 점은 안 찍는다", not app4.hub.badges, app4.hub.badges)
    bad = squeezed(top4)
    chk("  눌린 위젯 없음", not bad, bad[:3])
    w4.show_tab("chat")
    wait(root, lambda: w4.chat_ready, 3)
    settle(root, 0.2)
    chk("채팅 칸으로 오면 수가 지워지고 그 말이 있다", w4.seg.cells["chat"].cget("text") == "채팅"
        and w4.unread == 0 and "안 보는 사이의 말" in w4.chat_text())
    top4.withdraw()                              # 다른 탭으로 갔다 (길드 탭이 안 보인다)
    settle(root, 0.3)
    srv2.say("탭 밖에서 온 말", 2)
    sock.push({"t": "chat", "m": dict(srv2.chat[-1], system=False)})
    root.update()
    chk("길드 탭이 안 보이면 탭에 점을 찍는다", app4.hub.badges == [("guild", True)], app4.hub.badges)
    top4.deiconify()
    settle(root, 0.5)
    chk("돌아오면 점을 지운다", app4.hub.badges[-1] == ("guild", False) and w4.unread == 0, app4.hub.badges)
    chk("  그 말은 이미 붙어 있다", "탭 밖에서 온 말" in w4.chat_text())

    print("\n=== '바뀌었다' ===")
    n = srv2.calls.count("guild")
    C2 = Api(srv2, 3)
    C2.guild_join(1)
    for _ in range(3):
        sock.push({"t": "changed"})
    wait(root, lambda: w4.data["guild"]["members"] == 3, 3)
    settle(root, 0.5)
    chk("연달아 와도 한 번만 다시 받는다", srv2.calls.count("guild") == n + 1, srv2.calls.count("guild") - n)
    chk("머리의 사람 수가 따라 바뀐다", any("길드원 3 / 15명" in x for x in texts(top4)))
    w4.show_tab("manage")
    settle(root, 0.3)
    w4.v_intro.set("쓰는 중인 소개")
    srv2.done.setdefault(2, set()).add("catch")
    sock.push({"t": "changed"})
    wait(root, lambda: w4.data["mission"]["guildPoints"] >= 3, 3)
    settle(root, 0.4)
    chk("관리 칸에서 쓰던 글은 다시 그려도 남는다", w4.v_intro.get() == "쓰는 중인 소개", w4.v_intro.get())
    w4.show_tab("chat")
    wait(root, lambda: w4.chat_ready, 3)

    print("\n=== 끊기면 ===")
    sock.push({"t": "closed"})
    settle(root, 0.2)
    chk("끊기면 '2초마다' 로 돌아간다", not w4.live and "2초마다" in w4.chat_state.cget("text"))
    srv2.say("끊긴 뒤의 말", 2)
    got = wait(root, lambda: "끊긴 뒤의 말" in w4.chat_text(), 3)
    chk("  폴링으로 이어서 받는다", got)
    sock.push({"t": "open", "userId": 1, "guild": 1, "last": len(srv2.chat)})
    settle(root, 0.3)
    chk("다시 붙으면 '실시간' 으로", w4.live and "실시간" in w4.chat_state.cget("text"))
    lines = [x for x in w4.chat_text().split("\n") if x.strip()]
    chk("오가는 동안 겹치거나 빠진 줄이 없다", len(lines) == len(srv2.chat) and len(set(lines)) == len(lines),
        (len(lines), len(srv2.chat)))
    B2.guild_kick(1) if False else None
    srv2.roles.pop(1)                            # 내보내졌다
    srv2.g["master"] = 2
    srv2.roles[2] = "master"
    sock.push({"t": "left"})
    wait(root, lambda: w4.mode == "none", 3)
    settle(root, 0.3)
    chk("'나왔다' 가 오면 찾기 화면으로 가고 웹소켓을 끈다", w4.mode == "none" and sock.stopped
        and w4.sock is None and not w4.live, (w4.mode, sock.stopped))
    sock2 = FakeSocket(lambda ev: None)
    sock2.gave_up = 4404
    w4.sock = sock2
    srv2.roles[1] = "member"                     # 다시 들어왔다
    w4.refresh()
    wait(root, lambda: w4.in_guild() and w4.chat_box is not None, 3)
    chk("서버가 끊어 버린 웹소켓은 버리고 새로 만든다", sock2.stopped and w4.sock is made[-1]
        and len(made) == 2, len(made))
    w4.close()
    chk("닫으면 웹소켓도 끈다", made[-1].stopped and w4.sock is None)

    print("\n=== 읽은 데를 앱에 알린다 (1.10.2) ===")
    # 진짜 앱은 허브의 길드 탭에 찍는 점을 스스로 그린다 (app.mark_guild_chat_seen).
    # 창이 '여기까지 읽었다' 를 언제 알리는지 본다. 2초 틱만 믿으면, 채팅을 흘끗 보고 다른
    # 칸으로 간 사람은 안 읽은 채로 남아 나중에 점이 다시 켜진다.
    app6 = FakeApp(root, A2)
    app6.seen, app6.guild_unseen = [], False
    app6.mark_guild_chat_seen = lambda n=None: app6.seen.append(n)
    app6._paint_guild = lambda: None
    w6 = ui_guild.GuildWindow(app6)
    top6 = w6.win.winfo_toplevel()
    top6.deiconify()
    top6.geometry("1000x680+90+60")
    wait(root, lambda: w6.in_guild() and w6.chat_box is not None and w6.chat_ready)
    got = wait(root, lambda: bool(app6.seen), 3)
    chk("채팅 칸이 뜨면 거기까지 읽었다고 알린다", got and app6.seen[-1] == w6.chat_last > 0,
        (app6.seen[-3:], w6.chat_last))
    sock6 = made[-1]
    sock6.push({"t": "open", "userId": 1, "guild": 1, "last": len(srv2.chat)})
    settle(root, 0.3)
    try:
        root.after_cancel(w6._chat_job)          # 틱을 세운다 - 아래는 틱 없이도 되어야 한다
    except Exception:                            # noqa: BLE001
        pass
    w6._chat_job = None
    srv2.say("보는 중에 온 말", 2)
    sock6.push({"t": "chat", "m": dict(srv2.chat[-1], system=False)})
    root.update()
    chk("보는 중에 온 줄은 틱을 기다리지 않고 바로 읽은 것이 된다",
        app6.seen and app6.seen[-1] == srv2.chat[-1]["id"] == w6.chat_last,
        (app6.seen[-2:], srv2.chat[-1]["id"], w6.chat_last))
    app6.guild_unseen = True                     # 앱이 안다: 안 읽은 줄이 남았다
    w6.show_tab("members")
    settle(root, 0.3)
    chk("다른 칸에 있을 때 안 읽은 채팅이 남았으면 '채팅 ●'",
        w6.seg.cells["chat"].cget("text") == "채팅 ●", w6.seg.cells["chat"].cget("text"))
    bad = squeezed(top6)
    chk("  눌린 위젯 없음", not bad, bad[:3])
    app6.guild_unseen = False
    w6.show_tab("chat")
    wait(root, lambda: w6.chat_ready, 3)
    chk("채팅 칸으로 오면 표시가 사라진다", w6.seg.cells["chat"].cget("text") == "채팅",
        w6.seg.cells["chat"].cget("text"))
    w6.close()
    ui_guild.make_socket = keep_make
    app5 = FakeApp(root, A2)
    chk("붙을 수 없는 앱이면 None (폴링으로 돈다)", ui_guild.make_socket(app5, lambda ev: None) is None)

    print("\n=== 말 만들기 ===")
    chk("남은 시간", ui_guild.span(3 * 3600 + 720) == "3시간 12분" and ui_guild.span(7200) == "2시간"
        and ui_guild.span(59) == "1분" and ui_guild.span(None) == "1분")
    chk("접속 표시", ui_guild.seen_text({"online": True})[0] == "접속 중"
        and ui_guild.seen_text({"lastSeenAgo": 300})[0] == "5분 전"
        and ui_guild.seen_text({"lastSeenAgo": 3 * 86400})[0] == "3일 전"
        and ui_guild.seen_text({})[0] == "")
    chk("기록이 없는 프로필도 안 죽는다", ui_guild.profile_head({}) == []
        and [x[0] for x in ui_guild.profile_head({"user": {"days": 1}, "guild": {"roleKr": "길드원"}})]
        == ["길드원  ·  함께한 지 1일째", "길드 미션  오늘 0점  ·  누적 0점"])
    chk("채팅 시각은 깨진 값에도 안 죽는다", ui_guild.clock(None) == "" and ui_guild.clock("x") == ""
        and len(ui_guild.clock("2026-10-06T03:04:05+00:00")) == 5)
    from poketdesktop import guild_ws
    chk("웹소켓 주소", guild_ws.ws_url("https://posktop.duckdns.org") == "wss://posktop.duckdns.org/ws/guild"
        and guild_ws.ws_url("http://127.0.0.1:8788/") == "ws://127.0.0.1:8788/ws/guild")

    w.close()
    chk("닫으면 채팅을 묻는 예약이 남지 않는다", w._chat_job is None and not w.alive)
    n = len(srv.calls)
    settle(root, 0.5)
    chk("  닫은 뒤에는 서버를 두드리지 않는다", len(srv.calls) == n, len(srv.calls) - n)
    chk("콜백에서 터진 곳 없음", not errors, errors[:1])
    try:
        root.destroy()
    except tk.TclError:
        pass
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
