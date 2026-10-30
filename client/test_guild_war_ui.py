# -*- coding: utf-8 -*-
"""길드 창의 '길드전' 칸 (시즌 4) — 진짜 Tk 로 확인. 서버 없이 돈다.

    python client/test_guild_war_ui.py
    python client/run_as_windows.py client/test_guild_war_ui.py

길드 창 검사(test_guild_ui)의 서버 흉내에 길드전 쪽 길만 얹었다. 응답 모양은
server/app/guild_war.py 의 state / map_view / tile_view / log 와 같다. 규칙(지도 나누기·3승·배치·분배)은
server/test_guild_war.py 가 본다. 여기서는 **화면**을 본다:

  1. 길드전이 안 열렸으면 칸 줄은 예전 그대로 여섯이다. 열렸으면 '길드전' 이 미션 다음에 낀다.
  2. 신청 단계: 마스터에게는 신청·취소 단추, 길드원에게는 안내. 참가한 길드, 내 두 팀과 '바꾸기'.
  3. 팀 바꾸기는 랭크 팀 창을 그대로 쓴다 (제목·설명만 길드전 것).
  4. 전쟁 단계: **왼쪽에 원형 지도** (칸마다 주인 길드의 색, 칸·길드 경계는 선, 부채꼴 바깥에 길드 이름),
     오른쪽에 남은 공격·칠 수 있는 칸 수·순위·(길드장) 공격 나누기·기록.
  5. 칸을 누르면 지키는 쪽과 방어팀 - **남의 칸은 앞 3마리 + '가려진 N마리'**, 우리 길드 승수, 공격 단추.
     맞닿지 않은 칸·넘어간 칸은 까닭이 적히고 단추가 죽는다. 우리 칸은 전부 보이고 노리는 길드가 적힌다.
  6. 공격하면 관장 배틀 창이 열리고, 창을 닫으면 지도를 다시 받는다 (승수 '1/3', 점령하면 우리 색 + '점령').
  7. 길드장은 공격 횟수를 나누고(최소 1번·이미 쓴 만큼, 합 30) 우리 칸을 지킬 사람을 옮긴다.
  8. 지도는 칸을 한 번만 그리고 색만 고친다 (걸린 시간을 잰다). 칸이 다시 만들어져도 보던 자리가 이어진다.
     전쟁 중에는 가끔 다시 받아 남이 뺏은 칸도 칠한다.
  9. 끝 단계: 마지막 지도와 순위, 보상 안내. 어느 단계에도 글이 잘리지 않고, 창은 그대로다.
 10. 시즌 5 (서버가 jokerMax · contrib 를 보낼 때만): 규칙 칸의 조커 · 기여 보상 줄, 길드장의 '조커로 숨기기'
     (몇 명인지, 꽉 차면 단추가 죽는다), 우리 조커 칸 표시, 남의 조커 칸은 '???' + 마릿수, 지도의 '?'.
     옛 서버에는 조커 단추가 없다.
"""
import io
import json
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-gwar-ui-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

import test_guild_ui as TG                                  # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_box, ui_common as U, ui_guild, ui_guild_war, ui_season  # noqa: E402
from poketdesktop import ui_war_map as WM                   # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

OK = FAIL = 0
SIX = ("마기라스", "메타그로스", "보만다", "한카리아스", "토게키스", "갸라도스")
GUILDS = {9: ("로켓단", 0), 1: ("피카단", 1), 8: ("아주아주긴이름의길드", 2)}


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def mon(pid, kr, level=50):
    return {"id": pid, "species": "X%d" % pid, "num": 1 + pid % 300, "kr": kr, "level": level, "shiny": False,
            "tint": None}


def make_ring(owners=(9, 1, 8), rows=5, cols=3, inner=0.38, scale=1000.0):
    """흉내: 서버 guild_war.layout / ring_geo 와 같은 원형 지도 - 길드마다 부채꼴 15칸 (줄 5 x 칸 3).
    (칸 -> [줄, 차례, 한 바퀴], 칸 -> 맞닿은 칸들, 지도 그림)"""
    total = cols * len(owners)
    cells, at = {}, {}
    for k, _g in enumerate(owners):
        for row in range(rows):
            for j in range(cols):
                cid = "c%02d" % (len(cells) + 1)
                cells[cid] = [row, k * cols + j, total]
                at[(row, k * cols + j)] = cid
    adj = {}
    for cid, (row, col, _t) in cells.items():
        adj[cid] = set(at[key] for key in ((row - 1, col), (row + 1, col), (row, (col - 1) % total),
                                           (row, (col + 1) % total)) if key in at and at[key] != cid)
    seg = max(2, -(-120 // total))
    steps, thick = total * seg, (1.0 - inner) / rows

    def pt(b, m):
        import math
        r = (1.0 - b * thick) * scale
        a = 2 * math.pi * (m % steps) / steps - math.pi / 2
        return [round(r * math.cos(a), 1), round(r * math.sin(a), 1)]
    sgg = []
    for cid, (row, col, _t) in cells.items():
        ring = [pt(row, col * seg + j) for j in range(seg + 1)] + [pt(row + 1, col * seg + j) for j in range(seg, -1, -1)]
        sgg.append({"code": cid, "rings": [ring], "area": 1.0, "center": pt(row + 0.5, col * seg + seg / 2.0)})
    labels = []
    for k, g in enumerate(owners):
        x, y = pt(-0.55, (k * cols + cols / 2.0) * seg)
        labels.append({"text": GUILDS[g][0], "x": x, "y": y, "guildId": g})
    edge = scale * (1.0 + 0.55 * thick + 0.12)
    return cells, adj, {"sgg": sgg, "box": [-edge, edge, -edge, edge], "labels": labels}


CELLS, ADJ, GEO = make_ring()
IDS = sorted(CELLS)


class War(object):
    """길드전의 서버 흉내 (한 사람의 눈으로). 단계는 검사가 바꾼다."""

    def __init__(self):
        self.phase = None                     # None 이면 길드전이 안 열렸다 (옛 서버)
        self.role = "master"
        self.members = 6
        self.entered = False
        self.entries = [{"guildId": 9, "name": "로켓단", "state": "applied"}]
        self.teams = {"def": {"fixed": False, "set": False, "mons": [mon(1, "한카리아스"), mon(2, "망나뇽")]},
                      "atk": {"fixed": False, "set": False, "mons": [mon(1, "한카리아스"), mon(2, "망나뇽")]}}
        self.attacks = {1: [2, 0], 2: [2, 1], 3: [26, 0]}       # 사람 -> [나눈 수, 쓴 수]
        self.calls = []
        self.saved = []
        self.plans = []
        self.placed = []
        self.defends = {9: 3, 1: 0, 8: 2}
        self.wins = {}                        # 칸 -> 우리 길드 승수
        self.taken = set()
        self.battle = None                    # 끝나지 않은 판
        self.owner = dict((cid, (9, 1, 8)[i // 15]) for i, cid in enumerate(IDS))
        mine = [c for c in IDS if self.owner[c] == 1]
        self.guard = dict((cid, 0) for cid in IDS)               # 0 = AI 수비대
        for k, cid in enumerate(mine[:3]):
            self.guard[cid] = (1, 2, 3)[k]
        self.attacked = {mine[1]}            # 이 우리 칸은 공격받은 적이 있다
        self.v5 = False                      # 시즌 5 서버 (조커 · 기여 보상)
        self.jokers = set()                  # 우리 길드의 조커 (사람)
        self.foe_jokers = set()              # 남의 조커 칸 (우리에게 가려진 것)
        self.joked = []

    def lands(self, gid):
        return [c for c in IDS if self.owner[c] == gid]

    def hit(self):
        if self.phase != "war" or not self.entered or self.attacks[1][1] >= self.attacks[1][0]:
            return []
        mine = set(self.lands(1))
        return [c for c in IDS if self.owner[c] != 1 and c not in self.taken and ADJ[c] & mine]

    def ranking(self):
        rows = []
        for gid, (name, color) in GUILDS.items():
            n = len(self.lands(gid))
            rows.append({"guildId": gid, "name": name, "color": color, "tiles": n, "defends": self.defends[gid],
                         "wins": len(self.wins) if gid == 1 else 4, "score": n, "taken": 0, "lost": 0,
                         "attacks": 0, "received": 0})
        rows.sort(key=lambda r: (-r["tiles"], -r["defends"], -r["wins"]))
        for i, r in enumerate(rows, 1):
            r["rank"] = i
        return rows

    def state(self):
        ph = self.phase or "before"
        mine = self.attacks[1]
        st = {"season": 4, "phase": ph, "phaseKr": {"before": "준비 중", "apply": "참가 신청", "plan": "전략",
                                                   "war": "전쟁", "done": "끝"}[ph],
              "endsIn": {"before": 3600, "apply": 2 * 86400 + 5 * 3600, "plan": 3 * 86400 + 120,
                         "war": 3 * 3600 + 120, "done": None}[ph],
              "applyDays": 3, "planDays": 4, "warDays": 6, "minMembers": 5, "total": 30, "tilesPer": 15, "need": 3, "shown": 3,
              "regions": 256,
              "rewards": [{"rank": 1, "coins": 300}, {"rank": 2, "coins": 200}, {"rank": 3, "coins": 150},
                          {"rank": None, "coins": 50}],
              "title": "시즌 4 길드전 우승", "levelCap": 50,
              "jokerMax": 3 if self.v5 else None,
              "guild": {"id": 1, "members": self.members, "role": self.role},
              "entered": self.entered, "dropped": False,
              "can": {"apply": ph == "apply" and self.role in ("master", "sub"), "team": ph in ("apply", "plan"),
                      "attack": ph == "war" and self.entered and mine[1] < mine[0],
                      "manage": ph == "plan" and self.entered and self.role in ("master", "sub")},
              "entries": list(self.entries) + ([{"guildId": 1, "name": "피카단", "state": "applied"}]
                                               if self.entered else []),
              "ranking": self.ranking() if ph in ("plan", "war", "done") else [], "teams": self.teams}
        if self.v5:
            st["contrib"] = {"win": 20, "joker": 20, "defend": 20, "max": 300, "earned": 40}
        if ph in ("plan", "war", "done") and self.entered:
            st["attacks"] = {"total": mine[0], "used": mine[1],
                             "left": max(0, mine[0] - mine[1]) if ph in ("plan", "war") else 0}
            names = {1: "가람", 2: "나래", 3: "다솜"}
            where = dict((u, CELL_NAME(c)) for c, u in self.guard.items() if u and self.owner[c] == 1)
            st["mates"] = [{"userId": u, "name": names[u], "attacks": a, "used": used, "tile": where.get(u)}
                           for u, (a, used) in sorted(self.attacks.items())]
            if self.v5:
                for m in st["mates"]:
                    m["joker"] = m["userId"] in self.jokers
            st["received"] = 8
            if self.battle:
                st["battle"] = {"id": self.battle, "region": "c01"}
        return st

    def map(self, have=None):
        ph = self.phase or "before"
        if ph not in ("plan", "war", "done"):
            return {"phase": ph, "cells": {}, "guilds": [], "adj": {}, "hit": [], "mapDigest": "testdigest",
                    "myGuild": 1, "need": 3}
        cells = {}
        for cid in IDS:
            x = {"codes": [cid], "g": self.owner[cid], "name": CELL_NAME(cid)}
            if self.guard[cid] == 1 and self.owner[cid] == 1:
                x["me"] = 1
            if self.guard[cid] == 0:
                x["ai"] = 1
            if cid in self.taken:
                x["taken"] = 1
            if self.wins.get(cid) and self.owner[cid] != 1:
                x["wins"] = self.wins[cid]
            if self.v5 and cid not in self.taken and (cid in self.foe_jokers or (
                    self.owner[cid] == 1 and self.guard[cid] in self.jokers)):
                x["joker"] = 1
            cells[cid] = x
        rows = self.ranking()
        if have != "testdigest":
            self.calls.append("geo")                  # 지도 그림을 실어 보냈다
        return {"season": 4, "phase": ph, "mapDigest": "testdigest", "per": 15, "need": 3, "myGuild": 1,
                "geo": GEO if have != "testdigest" else None,
                "guilds": [dict((k, r[k]) for k in ("guildId", "name", "color", "tiles", "defends", "wins",
                                                     "score", "rank")) for r in rows],
                "cells": cells, "adj": dict((k, sorted(v)) for k, v in ADJ.items()), "hit": self.hit()}

    def tile(self, cid):
        gid, uid = self.owner[cid], self.guard[cid]
        mine = gid == 1
        hit = self.hit()
        why = ("아직 전략 기간이다 (공격은 전쟁이 시작되면)" if self.phase == "plan" else
               "지금은 전쟁 중이 아니다" if self.phase != "war" else
               "우리 길드의 칸이다" if mine else
               "이미 주인이 바뀐 칸이다 (다시 못 뺏는다)" if cid in self.taken else
               "공격 횟수를 다 썼다" if self.attacks[1][1] >= self.attacks[1][0] else
               "우리 칸과 맞닿지 않았다" if cid not in hit else None)
        team = [mon(900 + j, n) for j, n in enumerate(SIX)]
        shown = team if mine else [dict((k, v) for k, v in m.items() if k != "id") for m in team[:3]]
        out = {"region": cid, "name": CELL_NAME(cid), "codes": CELLS[cid], "guildId": gid, "guild": GUILDS[gid][0],
               "mine": mine, "ai": uid == 0, "guardId": uid or None,
               "guard": "AI 수비대 (난천)" if uid == 0 else {1: "가람", 2: "나래", 3: "다솜"}.get(uid, "?"),
               "team": shown, "size": 6, "hidden": 6 - len(shown), "taken": cid in self.taken,
               "home": "로켓단" if cid in self.taken else None, "wins": 0 if mine else self.wins.get(cid, 0),
               "need": 3, "guildReceived": 8, "guildMax": 30, "can": why is None, "blocked": why}
        if self.v5:
            veil = cid in self.foe_jokers and not mine
            out["joker"] = veil or (mine and uid in self.jokers)
            out["jokerHidden"] = veil
            if veil:
                out.update(guard="???", guardId=None, team=[], hidden=6, size=6)
        if mine:
            out["threats"] = [{"guild": "로켓단", "wins": 2}] if cid in self.attacked else []
            out["locked"] = cid in self.attacked
            out["manager"] = self.role in ("master", "sub") and self.phase == "plan"
            if out["manager"]:
                where = dict((u, CELL_NAME(c)) for c, u in self.guard.items() if u and self.owner[c] == 1)
                out["members"] = [{"userId": u, "name": n, "tile": where.get(u)}
                                  for u, n in ((1, "가람"), (2, "나래"), (3, "다솜"))]
                if self.v5:
                    out["jokerCount"], out["jokerMax"] = len(self.jokers), 3
        return out

    def log(self):
        rows = [{"id": 50, "ours": False, "atkName": "비주기", "defName": "나래", "atkGuild": "로켓단",
                 "defGuild": "피카단", "region": IDS[16], "regionName": CELL_NAME(IDS[16]), "result": "lose",
                 "took": False, "good": True, "at": ""}]
        for i, (cid, res, took) in enumerate(self.fought):
            rows.insert(0, {"id": 60 + i, "ours": True, "atkName": "가람", "defName": "AI 수비대",
                            "atkGuild": "피카단", "defGuild": "로켓단", "region": cid, "regionName": CELL_NAME(cid),
                            "result": res, "took": took, "good": res == "win", "at": ""})
        return rows

    fought = ()


def AI_FREE(w):
    """우리 길드의 AI 수비대 칸 하나 (넘어온 칸 말고)."""
    return next(c for c in w.lands(1) if not w.guard[c] and c not in w.taken)


def CELL_NAME(cid):
    """서버처럼 '처음 주인 길드 n번' (바깥 줄부터)."""
    row, col, _t = CELLS[cid]
    home = (9, 1, 8)[col // 3]
    return "%s %d번" % (GUILDS[home][0], row * 3 + col % 3 + 1)


class Api(TG.Api):
    """길드 창 검사의 가짜 api + 길드전."""

    def guild(self):
        out = TG.Api.guild(self)
        w = self.s.war
        if w.phase and out.get("guild"):
            out["war"] = {"phase": w.phase, "todo": False}
        return out

    def guild_war(self):
        self.s.war.calls.append("state")
        return self.s.war.state()

    def guild_war_apply(self, on=True):
        w = self.s.war
        w.calls.append("apply" if on else "withdraw")
        if on and w.members < 5:
            self.s.fail("길드원이 5명 이상이어야 길드전에 나갈 수 있습니다.", 409)
        w.entered = bool(on)
        return w.state()

    def guild_war_team(self, kind, ids):
        w = self.s.war
        w.saved.append((kind, list(ids)))
        w.teams[kind] = {"fixed": False, "set": True, "mons": [mon(i, "포켓몬%d" % i) for i in ids]}
        return w.state()

    def guild_war_map(self, have=None):
        self.s.war.calls.append("map")
        return self.s.war.map(have)

    def guild_war_tile(self, region):
        self.s.war.calls.append("tile:%s" % region)
        return self.s.war.tile(region)

    def guild_war_attack(self, region):
        w = self.s.war
        w.calls.append("attack:%s" % region)
        if w.tile(region)["blocked"]:
            self.s.fail("칠 수 없습니다: %s." % w.tile(region)["blocked"], 409)
        w.attacks[1][1] += 1
        w.battle = 70 + w.attacks[1][1]
        return {"id": w.battle, "region": "gw:4:%s" % region, "rev": 0, "battle": {"trainer": {"name": "AI 수비대"}},
                "events": [], "war": {"region": region, "wins": w.wins.get(region, 0), "need": 3}}

    def guild_war_attacks(self, plan):
        w = self.s.war
        w.plans.append(dict(plan))
        for k, v in plan.items():
            w.attacks[int(k)][0] = int(v)
        return w.state()

    def guild_war_guard(self, region, uid):
        w = self.s.war
        w.placed.append((region, uid))
        old = next((c for c, u in w.guard.items() if u == uid and w.owner[c] == 1), None)
        here = w.guard[region]
        w.guard[region] = uid
        if old:
            w.guard[old] = here
        return w.tile(region)

    def guild_war_joker(self, region, on=True):
        w = self.s.war
        w.joked.append((region, bool(on)))
        uid = w.guard[region]
        if on:
            w.jokers.add(uid)
        else:
            w.jokers.discard(uid)
        return w.tile(region)

    def gym_battle(self):
        w = self.s.war
        w.calls.append("resume")
        return {"id": w.battle, "region": "gw:4:c01", "rev": 3, "battle": {"trainer": {"name": "AI 수비대"}},
                "events": []}

    def guild_war_log(self):
        return self.s.war.log()

    # 팀 창이 부르는 것
    def pvp_team(self):
        return {"maxParty": 6, "levelCap": 50, "restrictedNums": [150], "restrictedMax": 1, "registered": False,
                "ids": []}

    def pokemon(self):
        out = []
        for i, (kr, lv, num) in enumerate((("한카리아스", 80, 445), ("망나뇽", 70, 149), ("뮤츠", 90, 150),
                                           ("잠만보", 60, 143), ("피카츄", 30, 25))):
            out.append({"id": i + 1, "level": lv, "num": num, "shiny": False, "onDesktop": i < 2, "slot": i,
                        "info": {"name": kr, "species": kr}})
        return out


class App(TG.FakeApp):
    def __init__(self, root, api):
        TG.FakeApp.__init__(self, root, api)
        self.team_window = None
        self.gym_battle = None


class Wheel(object):
    """휠 한 칸 (지도 한가운데에서)."""

    def __init__(self, cv, delta):
        self.delta = delta
        self.x_root = cv.winfo_rootx() + cv.winfo_width() // 2
        self.y_root = cv.winfo_rooty() + cv.winfo_height() // 2


def open_war(root, w):
    w.show_tab("war")
    TG.wait(root, lambda: getattr(w, "war", None) is not None and w.war.st is not None)
    TG.settle(root, 0.25)
    return w.war


def body_fits(war):
    """칸 안쪽이 굴러가는 틀 안에 들어 있나 (내용이 넘쳐도 창이 아니라 칸이 굴러간다)."""
    war.cv.update_idletasks()
    return war.inner.winfo_width() <= war.cv.winfo_width() + 2


def clipped(frame):
    """굴러가는 칸 안에서 **옆으로** 잘린 글 (squeezed 는 굴러가는 칸 안을 안 본다)."""
    out = []
    for w in frame.winfo_children():
        out.extend(clipped(w))
        if w.winfo_class() == "Label" and w.winfo_ismapped() and w.winfo_reqwidth() > w.winfo_width() + 1:
            out.append((w.cget("text")[:20], w.winfo_reqwidth(), w.winfo_width()))
    return out


def fill_of(war, cid):
    return war.map.cv.itemcget(war.map.items[cid][0], "fill")


def marks_of(war):
    cv = war.map.cv
    return [cv.itemcget(i, "text") for i in cv.find_withtag("mark") if cv.type(i) == "text"]


def pick(root, war, cid):
    """지도에서 그 칸을 누른 것처럼."""
    war.map.pick(cid)
    TG.wait(root, lambda: war.tile is not None and war.tile.get("region") == cid)
    TG.settle(root, 0.1)
    return texts(war.tile_box)


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda *a: errors.append(a)
    ui_guild.CHAT_MS = 150
    ui_box.confirm = lambda *a, **k: True
    ui_guild_war.POLL_MS = 300
    opened = []
    ui_guild_war.WarTab._open_battle = lambda self, data: opened.append(data)    # 관장 배틀 창 대신 적어 둔다
    print("글꼴 %s / 본문 %dpt (BASE_PT=%d)" % (U.FAMILY, U.FONT[1], U.BASE_PT))

    srv = TG.FakeServer()
    srv.war = War()
    srv.g = {"name": "피카단", "intro": "", "mode": "open", "master": 1, "points": 0}
    srv.roles = {1: "master", 2: "member", 3: "member"}
    A = Api(srv, 1)
    app = App(root, A)

    print("=== 길드전이 안 열렸을 때 ===")
    w = ui_guild.GuildWindow(app)
    top = w.win.winfo_toplevel()
    top.deiconify()
    top.geometry("1000x680+60+40")
    TG.wait(root, lambda: w.data is not None and w.mode == "guild")
    TG.settle(root)
    chk("칸 줄은 예전 그대로 여섯", [lb.cget("text") for lb in w.seg.cells.values()]
        == ["채팅", "길드원", "미션", "코인 상점", "다른 길드", "관리"])
    w.close()
    root.update()

    # 1.13.1 까지는 칸을 apply·war·done 에만 냈다 - 'plan' 이 빠져서 전략 기간(2026-10-20 0시 ~ 10-24 0시) 내내
    # 길드장까지 모두에게 '길드전' 칸이 사라졌다. 아래 검사들은 신청 단계에서 칸을 열어 둔 채 단계만 바꿔서
    # 그 경우를 한 번도 안 봤다. 그래서 단계마다 길드 창을 새로 연다.
    print("\n=== 단계마다 길드 창을 새로 열면 '길드전' 칸 (1.13.2, 전략 기간에 사라졌다) ===")
    for ph in ("apply", "plan", "war", "done"):
        srv.war.phase = ph
        w = ui_guild.GuildWindow(app)
        w.win.winfo_toplevel().deiconify()
        TG.wait(root, lambda: w.data is not None and w.mode == "guild")
        TG.settle(root)
        got = [lb.cget("text") for lb in w.seg.cells.values()]
        chk("%s: 미션 다음에 '길드전'" % ph, got == ["채팅", "길드원", "미션", "길드전", "코인 상점", "다른 길드", "관리"],
            got)
        w.close()
        root.update()
    srv.war.phase = "plan"
    member = ui_guild.GuildWindow(App(root, Api(srv, 2)))
    member.win.winfo_toplevel().deiconify()
    TG.wait(root, lambda: member.data is not None and member.mode == "guild")
    TG.settle(root)
    got = [lb.cget("text") for lb in member.seg.cells.values()]
    chk("전략 기간에 일반 길드원도 '길드전' 칸이 보인다", "길드전" in got, got)
    member.close()
    root.update()
    srv.war.phase = None

    print("\n=== 신청 단계 (마스터) ===")
    srv.war.phase = "apply"
    w = ui_guild.GuildWindow(app)
    top = w.win.winfo_toplevel()
    top.deiconify()
    top.geometry("1000x680+60+40")
    TG.wait(root, lambda: w.data is not None and w.mode == "guild")
    TG.settle(root)
    names = [lb.cget("text") for lb in w.seg.cells.values()]
    chk("'길드전' 칸이 미션 다음에 낀다", names == ["채팅", "길드원", "미션", "길드전", "코인 상점", "다른 길드", "관리"],
        names)
    war = open_war(root, w)
    tx = texts(war.inner)
    chk("단계와 남은 시간", "시즌 4 길드전" in tx and any("2일 5시간" in x and "지도가 나뉩니다" in x for x in tx), tx[:4])
    chk("규칙이 적혀 있다 (원형 지도 15칸씩·이웃 양옆, 맞닿은 칸, 같은 상대 3번, 칸이 많은 길드, 30번, 한 사람 한 칸, "
        "3마리만)", any(
        "원형 지도를 같은 모양으로 15칸씩" in x and "양옆 두 곳" in x and "맞닿은 남의 칸" in x and "같은 상대를 3번 이기면" in x and "칸이 가장 많은 길드가 이깁니다" in x
        and "합쳐 30번" in x and "한 사람이 한 칸씩" in x and "AI 수비대" in x and "3마리만" in x for x in tx), tx[:6])
    chk("보상이 적혀 있다", any("1위 300" in x and "시즌 4 길드전 우승" in x for x in tx))
    chk("아직 신청하지 않았다 + '참가 신청' 단추", "아직 신청하지 않았습니다" in tx
        and war.buttons["apply"].label.cget("text") == "참가 신청" and war.buttons["apply"].enabled)
    chk("신청 기간에는 지도가 없다 (칸 하나로 쓴다)", war.wide is False and "map" not in srv.war.calls)
    chk("  전략 기간이 시작되면 지도가 나오고, 길드장이 정한 뒤 전쟁이라고 알린다",
        any("전략 기간이 시작되면" in x and "이 칸에 지도가 나타납니다" in x and "전쟁이 시작되면" in x for x in tx))
    chk("  일정: 신청 3일 · 전략 4일 · 전쟁 6일", any("신청 3일 · 전략 4일 · 전쟁 6일" in x for x in tx))
    chk("내 두 팀과 '바꾸기', 앞의 3마리만 보인다는 안내", "team_def" in war.buttons and "team_atk" in war.buttons
        and any("앞의 3마리만 상대에게 미리 보입니다" in x for x in tx))
    chk("눌린 위젯이 없다", not squeezed(top) and not clipped(war.inner), (squeezed(top)[:4], clipped(war.inner)[:4]))
    size0 = (top.winfo_width(), top.winfo_height())
    war.apply(True)
    TG.wait(root, lambda: srv.war.entered and war.buttons.get("apply") is not None
            and war.buttons["apply"].label.cget("text") == "참가 취소")
    chk("신청하면 '참가 취소' 로", srv.war.entered)

    print("\n=== 팀 바꾸기 (랭크 팀 창을 쓴다) ===")
    war.pick_team("def", "방어팀")
    pk = war.picker
    TG.wait(root, lambda: len(pk.mons) == 5)
    TG.settle(root, 0.2)
    chk("설명이 길드전 것이다 (AI 가 굴린다, 앞의 3마리만)", any(
        "AI 가 굴립니다" in x and "앞의 3마리만 미리 보입니다" in x for x in texts(pk.win)), texts(pk.win)[:4])
    for pid in (4, 1, 3):
        pk.toggle(pid)
    pk.save()
    TG.wait(root, lambda: srv.war.saved[-1:] and srv.war.saved[-1][0] == "def")
    chk("저장된다", srv.war.saved[-1][0] == "def", srv.war.saved)
    pk.close()
    root.update()

    print("\n=== 전략 단계: 지도 (명단이 고정되고 지도가 나뉜다) ===")
    srv.war.phase = "plan"
    war.reload()
    TG.wait(root, lambda: war.wide and len(war.map.items) == 45)
    TG.settle(root, 0.4)
    wm = war.map
    tx = texts(war.inner)
    chk("지도가 왼쪽에 낀다 (오른쪽은 좁은 칸)", war.wide and wm.cv.winfo_ismapped()
        and wm.cv.winfo_rootx() < war.right.winfo_rootx() and wm.cv.winfo_width() > war.right.winfo_width())
    chk("지도 그림은 지도 응답에 한 번 실려 온다 (그 뒤로는 가진 요약값을 알려 다시 안 받는다)",
        srv.war.calls.count("geo") == 1 and war.geo and war.geo.get("_digest") == "testdigest", srv.war.calls)
    chk("칸 45개, 부채꼴이 다 그려진다 (칸마다 하나)", len(wm.items) == 45
        and sum(len(v) for v in wm.items.values()) == 45)
    labels = [wm.cv.itemcget(i, "text") for i in wm.cv.find_withtag("label")]
    chk("부채꼴 바깥에 길드 이름 (긴 이름도 판 안에)", set(labels) >= {"로켓단", "피카단", "아주아주긴이름의길드"}
        and all(0 <= wm.cv.coords(i)[0] <= wm.cv.winfo_width() and 0 <= wm.cv.coords(i)[1] <= wm.cv.winfo_height()
                for i in wm.cv.find_withtag("label")), labels)
    a9, a1, a8 = srv.war.lands(9)[0], srv.war.lands(1)[0], srv.war.lands(8)[0]
    chk("칸마다 주인 길드의 색", (fill_of(war, a9), fill_of(war, a1), fill_of(war, a8))
        == (WM.color_of(0), WM.color_of(1), WM.color_of(2))
        and all(fill_of(war, c) == WM.color_of(GUILDS[g][1]) for c, g in srv.war.owner.items()))
    chk("칸 안의 시·군·구 경계는 지운다 (테두리 = 칠)", all(
        wm.cv.itemcget(i, "outline") == wm.cv.itemcget(i, "fill") for ids in wm.items.values() for i in ids))
    looks = [wm.cv.itemcget(i, "fill") for i, _a, _b in wm.runs]
    chk("칸 경계·바닷가는 선으로, 우리 길드의 둘레는 흰 선", wm.runs and WM.LINE in looks and WM.MINE_LINE in looks,
        len(wm.runs))
    chk("  선은 칸 수보다 많지만 칸 경계의 선분보다 훨씬 적다 (이어지는 것을 한 줄로)",
        45 < len(wm.runs) < len(wm._edges) // 4, (len(wm.runs), len(wm._edges)))
    chk("내가 지키는 칸에 흰 점", len([i for i in wm.cv.find_withtag("mark") if wm.cv.type(i) == "oval"]) == 1)
    chk("내 몫 공격 2번, 내가 지키는 칸, 전쟁이 시작되면 쓴다고 (칠 수 있는 칸은 아직 없다)", "내 몫 공격 2번" in tx
        and any("내가 지키는 칸: %s" % CELL_NAME(a1) in x for x in tx)
        and any("전쟁이 시작되면 씁니다" in x for x in tx) and not any("지금 칠 수 있는 칸" in x for x in tx), tx[:10])
    chk("단계: 전략, 전쟁이 시작될 때까지 남은 시간", "전략" in tx and any("전쟁이 시작될 때까지 3일 0시간" in x for x in tx))
    chk("순위: 칸·방어·승리", all(h in tx for h in ("순위", "길드", "칸", "방어", "승리")) and "아주아주긴이름의길드" in tx)
    chk("길드장에게 공격 나누기", any("공격 나누기" in x for x in tx) and "plan" in war.buttons
        and any("합 30 / 30번" in x for x in tx))
    chk("팀은 아직 바꿀 수 있다", "team_def" in war.buttons and "team_atk" in war.buttons)
    chk("눌린 위젯이 없다 (옆 칸의 글도 안 잘린다)", not squeezed(top) and not clipped(war.inner),
        (squeezed(top)[:4], clipped(war.inner)[:4]))
    chk("창 크기는 그대로다 (옆 칸 안쪽이 굴러간다)", (top.winfo_width(), top.winfo_height()) == size0
        and war.inner.winfo_reqheight() > war.cv.winfo_height())
    chk("칸 안쪽 틀에 들어 있다", body_fits(war))

    print("\n=== 그리는 데 걸리는 시간 ===")
    t0 = time.time()
    wm.redraw()
    root.update_idletasks()
    draw_ms = (time.time() - t0) * 1000
    chk("한반도를 처음 그리는 데 1초를 안 넘는다 (%.0fms, 선 %d줄)" % (draw_ms, len(wm.runs)), draw_ms < 1000, draw_ms)
    data = srv.war.map()
    for cid in srv.war.lands(9)[:5]:
        data["cells"][cid]["g"] = 8
    t0 = time.time()
    count = len(wm.cv.find_all())
    wm.set_state(data)
    root.update_idletasks()
    paint_ms = (time.time() - t0) * 1000
    chk("주인이 바뀐 칸을 다시 칠하는 데 0.2초를 안 넘는다 (5칸, %.0fms)" % paint_ms, paint_ms < 200
        and fill_of(war, srv.war.lands(9)[0]) == WM.color_of(2), paint_ms)
    chk("  도형이 늘지 않는다 (색만 고친다)", len(wm.cv.find_all()) == count)
    wm.set_state(srv.war.map())
    chk("  바뀐 것이 없으면 아무것도 안 고친다", wm.recolor() == 0)

    print("\n=== 칸을 누르면 (전략 기간) ===")
    mine_set = set(srv.war.lands(1))
    foe = next(c for c in IDS if srv.war.owner[c] != 1 and ADJ[c] & mine_set)     # 우리 칸과 맞닿은 남의 칸
    tx = pick(root, war, foe)
    chk("칸 이름, 주인 길드, 지키는 쪽", CELL_NAME(foe).strip() in " ".join(tx) and GUILDS[srv.war.owner[foe]][0] in tx
        and any(x.startswith("지키는 쪽: AI 수비대") for x in tx), tx)
    chk("방어팀은 앞 3마리만 (전략 기간에 미리 살펴본다)",
        [x for x in tx if "Lv.50" in x] == ["마기라스  Lv.50", "메타그로스  Lv.50", "보만다  Lv.50"])
    chk("  나머지는 '가려진 3마리' 로만", any("가려진 3마리" in x for x in tx)
        and not any(n_ in " ".join(texts(top)) for n_ in ("토게키스", "갸라도스")))
    chk("아직 칠 수 없다 - 단추가 죽고 까닭이 적힌다", not war.buttons["attack"].enabled
        and "칠 수 없음: 아직 전략 기간이다 (공격은 전쟁이 시작되면)" in tx, tx)
    chk("고른 칸은 밝게 칠한다", fill_of(war, foe) == WM.lighten(WM.color_of(GUILDS[srv.war.owner[foe]][1])))
    far = next(c for c in IDS if srv.war.owner[c] != 1 and not (ADJ[c] & mine_set))
    own = srv.war.lands(1)[0]
    tx = pick(root, war, own)
    chk("우리 칸: 여섯 마리가 다 보이고 공격 단추 대신 '지키는 사람 바꾸기'", len([x for x in tx if "Lv.50" in x]) == 6
        and "우리 길드" in tx and "attack" not in war.buttons and "guard" in war.buttons
        and any("아직 이 칸을 이긴 길드가 없습니다" in x for x in tx), tx)
    chk("  앞서 고른 칸은 원래 색으로", fill_of(war, foe) == WM.color_of(GUILDS[srv.war.owner[foe]][1]))
    war.buttons["guard"].command()
    TG.settle(root, 0.2)
    menu = war.menu
    mt = texts(menu.win)
    chk("누르면 길드원 목록이 뜬다 (지금 지키는 칸과 함께)", any("가람" in x and "이 칸" in x for x in mt)
        and any("나래" in x for x in mt) and any("다솜" in x for x in mt), mt)
    U.close_all()
    war.place(own, 3)
    TG.wait(root, lambda: srv.war.placed[-1:] == [(own, 3)] and war.tile is not None
            and war.tile.get("guard") == "다솜", 3)
    chk("고르면 그 칸에 배치한다", srv.war.placed[-1:] == [(own, 3)] and srv.war.guard[own] == 3)
    tx = pick(root, war, srv.war.lands(1)[1])
    chk("공격받은 칸은 바꿀 수 없고 노리는 길드가 적힌다", "guard" not in war.buttons
        and any("바꿀 수 없습니다" in x for x in tx) and any("[로켓단] 2승" in x for x in tx), tx)

    print("\n=== 길드장: 공격 나누기 (전략 기간) ===")
    war.plan = None
    loaded = []
    war.reload(after=lambda: loaded.append(1))
    TG.wait(root, lambda: loaded and "plan" in war.buttons)
    war.bump(1, -1)
    war.bump(1, -1)
    chk("한 사람 최소 1번 (가람 2 -> 1 아래로 안 감)", war.plan[1] == 1)
    war.bump(2, -1)
    war.bump(2, -1)
    chk("  나래도 1 아래로 안 간다", war.plan[2] == 1, war.plan[2])
    war.bump(3, 5)
    chk("합이 30을 넘으면 저장 단추가 죽고 빨갛게 (1 + 1 + 31 = 33)", not war.buttons["plan"].enabled
        and any("합 33 / 30번" in x for x in texts(war.inner)), [x for x in texts(war.inner) if "합 " in x])
    war.bump(3, -5)
    chk("  돌리면 다시 산다", war.buttons["plan"].enabled and any("합 28 / 30번" in x for x in texts(war.inner)))
    war.buttons["plan"].command()
    TG.wait(root, lambda: srv.war.plans)
    chk("저장하면 서버에 나눈 것을 보낸다", srv.war.plans[-1] == {1: 1, 2: 1, 3: 26}, srv.war.plans)
    srv.war.attacks = {1: [2, 0], 2: [2, 1], 3: [26, 0]}                  # 전쟁 단계를 볼 때의 몫으로 되돌린다

    print("\n=== 전쟁 단계 (정해 둔 것은 고정) ===")
    srv.war.phase = "war"
    for k in ("def", "atk"):
        srv.war.teams[k]["fixed"] = True
    war.plan = None
    loaded = []
    war.reload(after=lambda: loaded.append(1))
    TG.wait(root, lambda: loaded and war.st.get("phase") == "war")
    TG.settle(root, 0.3)
    tx = texts(war.inner)
    chk("남은 공격 2번, 칠 수 있는 칸 수", "남은 공격 2번" in tx
        and any("지금 칠 수 있는 칸 %d곳" % len(srv.war.hit()) in x for x in tx), tx[:10])
    chk("공격 나누기·팀 바꾸기가 사라진다", "plan" not in war.buttons and "team_def" not in war.buttons
        and "team_atk" not in war.buttons and "고정됨" in tx)
    chk("기록: 막은 판", "방어" in tx and any("[로켓단] 비주기 → 나래" in x for x in tx), tx[-14:])
    hit = srv.war.hit()
    chk("(앞서 본 칸은 이제 칠 수 있는 칸)", foe in hit)
    tx = pick(root, war, foe)
    chk("우리 길드 승수와 공격 단추", any("3승 중 0승" in x for x in tx) and war.buttons["attack"].enabled
        and "관장 배틀" in war.buttons["attack"].label.cget("text"))
    tx = pick(root, war, far)
    chk("맞닿지 않은 칸은 까닭이 적히고 단추가 죽는다", not war.buttons["attack"].enabled
        and "칠 수 없음: 우리 칸과 맞닿지 않았다" in tx, tx)
    tx = pick(root, war, own)
    chk("우리 칸이어도 지키는 사람을 못 바꾼다", "guard" not in war.buttons and "attack" not in war.buttons, tx)
    war._hover(foe)
    chk("올리면 칸 이름·주인·칠 수 있는지 한 줄로", war.hint.cget("text").endswith("· 칠 수 있음")
        and "[%s]" % GUILDS[srv.war.owner[foe]][0] in war.hint.cget("text"), war.hint.cget("text"))
    war._hover(None)
    chk("  내리면 안내로", war.hint.cget("text") == ui_guild_war.MAP_HINT)
    chk("눌린 위젯이 없다", not squeezed(top) and not clipped(war.inner), (squeezed(top)[:4], clipped(war.inner)[:4]))

    print("\n=== 공격: 관장 배틀 창 -> 닫으면 지도를 다시 받는다 ===")
    pick(root, war, foe)
    war.buttons["attack"].command()
    TG.wait(root, lambda: len(opened) == 1)
    chk("그 칸에 승부를 걸고 관장 배틀 창을 연다", "attack:%s" % foe in srv.war.calls and opened[0]["id"] == 71
        and opened[0]["region"] == "gw:4:%s" % foe)
    srv.war.wins[foe] = 1
    srv.war.fought = ((foe, "win", False),)
    srv.war.battle = None
    war._battle_closed()
    TG.wait(root, lambda: "1/3" in marks_of(war) and war.tile is not None and war.tile.get("region") == foe)
    TG.settle(root, 0.2)
    tx = texts(war.inner)
    chk("이기면 그 칸에 '1/3', 고른 칸에 '3승 중 1승'", "1/3" in marks_of(war)
        and any("3승 중 1승" in x for x in texts(war.tile_box)), marks_of(war))
    chk("  남은 공격이 준다, 기록에 '승리'", "남은 공격 1번" in tx and "승리" in tx)
    srv.war.wins[foe] = 3
    srv.war.owner[foe], srv.war.guard[foe] = 1, 1
    srv.war.taken.add(foe)
    srv.war.fought = ((foe, "win", False), (foe, "win", True))
    war._battle_closed()
    TG.wait(root, lambda: fill_of(war, foe) in (WM.color_of(1), WM.lighten(WM.color_of(1))) and "점령" in marks_of(war))
    TG.settle(root, 0.2)
    chk("셋째 승: 그 칸이 우리 색으로, '점령' 표시", "점령" in marks_of(war)
        and fill_of(war, foe) in (WM.color_of(1), WM.lighten(WM.color_of(1))))
    chk("  기록에 '점령', 순위에 우리 칸 16", "점령" in texts(war.inner) and "16" in texts(war.rank_box))
    chk("  넘어온 칸은 우리 칸으로 그려진다", war.tile.get("mine") is True and any("넘어간 칸입니다" in x for x in texts(war.tile_box)))
    srv.war.attacks[1][1] = 2
    loaded = []
    war.reload(after=lambda: loaded.append(1))
    TG.wait(root, lambda: loaded and "남은 공격 0번" in texts(war.inner))
    tx = pick(root, war, srv.war.hit()[0] if srv.war.hit() else next(c for c in IDS if srv.war.owner[c] == 9))
    chk("횟수를 다 쓰면 단추가 죽고 까닭이 적힌다", not war.buttons["attack"].enabled
        and "칠 수 없음: 공격 횟수를 다 썼다" in tx, tx)

    print("\n=== 끝나지 않은 판 ===")
    srv.war.battle = 99
    loaded = []
    war.reload(after=lambda: loaded.append(1))
    TG.wait(root, lambda: loaded and "resume" in war.buttons)
    chk("'이어서 하기' 가 뜬다", any("끝나지 않은 길드전 승부" in x for x in texts(war.inner)))
    n0 = len(opened)
    war.buttons["resume"].command()
    TG.wait(root, lambda: len(opened) == n0 + 1)
    chk("  누르면 그 판을 관장 배틀 창으로 이어서 연다", "resume" in srv.war.calls and opened[-1]["id"] == 99)
    srv.war.battle = None

    print("\n=== 남이 뺏은 칸도 칠해진다 (가끔 다시 받는다) ===")
    other = next(c for c in srv.war.lands(9) if c not in (foe, war.sel))     # 고른 칸은 밝게 칠해져 있다
    srv.war.owner[other] = 8
    calls0 = len(srv.war.calls)
    TG.wait(root, lambda: fill_of(war, other) == WM.color_of(2), 4)
    chk("기다리면 지도의 색이 바뀐다", fill_of(war, other) == WM.color_of(2))
    chk("  칸을 새로 만들지 않는다", w.war is war and "map" in srv.war.calls[calls0:])

    print("\n=== 확대와, 칸이 다시 만들어졌을 때 ===")
    for _ in range(4):
        wm._on_wheel(Wheel(wm.cv, 120))
    chk("휠로 키운다", wm.zoom > 1.5, wm.zoom)
    pick(root, war, far)
    box = wm.cv.bbox(wm.items[far][0])
    w._reload_soon()                         # 길드원 누가 미션을 끝냈다 - 길드 창이 칸을 다시 만든다
    TG.wait(root, lambda: getattr(w, "war", None) is not war and w.war.wide and len(w.war.map.items) == 45, 4)
    TG.settle(root, 0.4)
    war2 = w.war
    chk("칸이 새로 만들어져도 키운 정도와 고른 칸이 이어진다", war2 is not war and abs(war2.map.zoom - wm.zoom) < 1e-6
        and war2.sel == far and war2.map.selected == far, (war2.map.zoom, war2.sel))
    box2 = war2.map.cv.bbox(war2.map.items[far][0])
    chk("  같은 자리에 그려진다", all(abs(a_ - b_) <= 3 for a_, b_ in zip(box, box2)), (box, box2))
    war2.map.reset_view()
    chk("맞춤 크기로 되돌릴 수 있다", war2.map.zoom == 1.0 and war2.map.pan == [0.0, 0.0])
    war, wm = war2, war2.map

    print("\n=== 일반 길드원 (전략 기간) ===")
    srv.war.role = "member"
    srv.war.phase = "plan"
    war.reload()
    TG.wait(root, lambda: "plan" not in war.buttons and war.st.get("guild", {}).get("role") == "member")
    tx = pick(root, war, own)
    chk("공격 나누기·지키는 사람 바꾸기가 없다", "plan" not in war.buttons and "guard" not in war.buttons)
    srv.war.role = "master"
    war.reload()
    TG.wait(root, lambda: "plan" in war.buttons and war.st.get("guild", {}).get("role") == "master")
    war.tile = None
    pick(root, war, next(c for c in srv.war.lands(1) if srv.war.guard[c] and c not in srv.war.taken))
    chk("옛 서버(시즌 4): 길드장에게도 조커 단추가 없다 (지키는 사람 바꾸기는 있다)", "guard" in war.buttons
        and "joker" not in war.buttons, list(war.buttons))

    print("\n=== 시즌 5: 조커 · 기여 보상 (전략 기간, 길드장) ===")
    srv.war.v5 = True
    srv.war.phase = "plan"
    war.reload()
    TG.wait(root, lambda: war.st.get("jokerMax") == 3 and "plan" in war.buttons)
    TG.settle(root, 0.2)
    tx = texts(war.inner)
    chk("규칙 칸에 조커 · 기여 보상 줄", any("조커로 숨길 수 있습니다" in x for x in tx)
        and any("기여 보상(판이 끝나면 바로)" in x and "조커를 이기면 40" in x and "지금 40개" in x for x in tx), tx)
    chk("  전략 카드: 조커 0 / 3명", any("조커 0 / 3명" in x for x in tx), tx)
    # 넘어온 칸(점령)은 조커가 아니다 - 처음부터 우리 것인 사람 칸을 고른다
    guarded = next(c for c in srv.war.lands(1) if srv.war.guard[c] and c not in srv.war.taken)
    war.tile = None                          # 앞서 받아 둔 같은 칸(시즌 4 응답)을 기다림으로 치지 않게
    pick(root, war, guarded)
    b = war.buttons.get("joker")
    chk("우리 사람 칸에 '조커로 숨기기 (0/3명)'", b is not None and b.enabled
        and b.label.cget("text") == "조커로 숨기기 (0/3명)", b and b.label.cget("text"))
    b.command()
    TG.wait(root, lambda: srv.war.joked and war.tile and war.tile.get("joker") and "joker" in war.buttons
            and war.buttons["joker"].label.cget("text").startswith("조커 풀기"))
    TG.wait(root, lambda: any("조커 1 / 3명" in x for x in texts(war.inner)))
    TG.settle(root, 0.2)
    tx = texts(war.tile_box)
    chk("누르면 숨겨지고 '조커 풀기 (1/3명)' · 우리 쪽 안내", srv.war.joked[-1] == (guarded, True)
        and war.buttons["joker"].label.cget("text") == "조커 풀기 (1/3명)"
        and any("다른 길드에는 이 칸이 '???'" in x for x in tx), tx)
    chk("  전략 카드: 조커 1 / 3명 + 이름", any("조커 1 / 3명: " in x for x in texts(war.inner)))
    chk("  지도에 '?'", "?" in marks_of(war), marks_of(war))
    srv.war.jokers |= {u for u in (1, 2, 3)}
    war.tile = None
    pick(root, war, AI_FREE(srv.war))
    chk("AI 수비대 칸에는 조커 단추가 없다", "joker" not in war.buttons)
    other = next(c for c in srv.war.lands(1) if srv.war.guard[c] and c != guarded and c not in srv.war.taken)
    srv.war.jokers.discard(srv.war.guard[other])
    srv.war.jokers.add(99)                   # 다른 칸의 조커 하나 더 (모두 3명)
    war.tile = None
    pick(root, war, other)
    b = war.buttons.get("joker")
    chk("3명이 차면 숨기기 단추가 죽고 까닭이 적힌다", b is not None and not b.enabled
        and any("조커는 3명까지입니다" in x for x in texts(war.tile_box)), b and b.label.cget("text"))
    foe = next(c for c in IDS if srv.war.owner[c] != 1)
    srv.war.foe_jokers.add(foe)
    war.reload()
    TG.wait(root, lambda: "?" in marks_of(war) and marks_of(war).count("?") >= 2)
    war.tile = None
    tx = pick(root, war, foe)
    chk("남의 조커 칸: 지키는 쪽 ??? · 방어팀은 마릿수만", "지키는 쪽: ???" in tx
        and any("조커 칸 - 지키는 사람과 방어팀이 숨겨져 있습니다" in x for x in tx)
        and any("방어팀 6마리 (싸워 봐야 압니다)" in x for x in tx)
        and not [x for x in tx if "Lv.50" in x], tx)
    chk("눌린 위젯이 없다 (시즌 5)", not squeezed(top) and not clipped(war.inner),
        (squeezed(top)[:4], clipped(war.inner)[:4]))
    srv.war.v5 = False
    srv.war.jokers, srv.war.foe_jokers = set(), set()

    print("\n=== 끝 ===")
    srv.war.phase = "done"
    war.reload()
    TG.wait(root, lambda: war.st.get("phase") == "done")
    TG.settle(root, 0.3)
    tx = texts(war.inner)
    chk("끝났다고 적힌다", any("이번 시즌의 길드전이 끝났습니다" in x for x in tx))
    chk("마지막 지도가 남는다", war.wide and len(wm.items) == 45)
    chk("순위표와 보상 안내가 남는다", "로켓단" in tx and any("보상(길드 코인)은 바로 들어갔고" in x for x in tx))
    tx = pick(root, war, srv.war.lands(9)[0])
    chk("칸을 눌러 볼 수는 있지만 칠 수는 없다", not war.buttons["attack"].enabled
        and "칠 수 없음: 지금은 전쟁 중이 아니다" in tx, tx)
    chk("눌린 위젯이 없다", not squeezed(top) and not clipped(war.inner), (squeezed(top)[:4], clipped(war.inner)[:4]))

    print("\n=== 참가하지 않은 길드 ===")
    srv.war.phase, srv.war.entered = "war", False
    war.reload()
    TG.wait(root, lambda: war.st.get("phase") == "war" and not war.st.get("entered"))
    TG.settle(root, 0.2)
    chk("참가하지 않았다고 알린다", any("이번 길드전에 참가하지 않았습니다" in x for x in texts(war.inner)))
    chk("지도는 구경할 수 있다", war.wide and len(wm.items) == 45)

    print("\n=== 다른 칸으로 갔다 오면 ===")
    w.show_tab("members")
    TG.settle(root, 0.2)
    chk("길드전 칸을 떠나면 그 칸은 멈춘다", war.alive is False)
    war3 = open_war(root, w)
    chk("돌아오면 새로 받는다", war3 is not war and war3.alive and war3.st is not None)

    chk("문구: 남은 시간", ui_guild_war.span_text(90061) == "1일 1시간" and ui_guild_war.span_text(None) == "")
    chk("문구: 기록의 앞머리", ui_guild_war.log_mark({"ours": True, "took": True, "result": "win"}) == ("점령", True)
        and ui_guild_war.log_mark({"ours": True, "result": "lose"}) == ("패배", False)
        and ui_guild_war.log_mark({"ours": False, "took": True, "result": "win"}) == ("뺏김", False)
        and ui_guild_war.log_mark({"ours": False, "good": True, "result": "lose"}) == ("방어", True)
        and ui_guild_war.log_mark({"result": "pending"}) == ("진행 중", None))
    w.close()
    TG.settle(root, 0.3)
    chk("Tk 콜백에서 난 오류가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
