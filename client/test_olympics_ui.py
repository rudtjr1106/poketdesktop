# -*- coding: utf-8 -*-
"""포스크탑 올림픽 화면 검사 — 바탕화면 중계 · 2시 예약 · 겹칠 때 · 올림픽 창.

    python client/test_olympics_ui.py
    python client/run_as_windows.py client/test_olympics_ui.py

**진짜 Overlay 와 도트 창을 띄운다.** 서버 대신 가짜 api 가 server/app/olympics.py 와 같은 모양으로 답한다
(서버 쪽은 server/test_olympics.py). 중계 시계는 빠르게 돌린다 (olympics_show.time 을 바꿔 끼운다).

못 박는 것:
  1. 달리기형(100m · 마라톤): 출전식에서 한 마리씩 들어와 자리에 서고(자막), 기록 차례대로 들어오고, 넘어진 선수 말,
     끝나면 선수 창이 없어지고 바탕화면 포켓몬이 되살아난다. 봅슬레이는 한 대씩 썰매를 타고 구간 기록을 띄운다.
  2. 시기형(장대 · 양궁 · 원반 · 스키점프): 전광판의 최고 기록이 서버 기록과 같다 · 파울을 센다 · 기다리는 선수는
     창을 안 옮긴다(맥 CPU) · 소품 창(스키 · 장대 · 활 · 원반)이 치워진다.
  2b. 일곱 종목 모두 8마리 · 세 번 시기여도 중계가 다음 종목 전에 끝난다 (계획 길이로 잰다).
      경기장은 유리판(창 투명도) · 높이 200pt 아래 (11/07 사용자 '너무 크고 색이 강렬' → '폭은 꽉 써도, 높이만').
  3. 도트가 없는 선수 · 걷기 그림뿐인 선수도 중계가 끝까지 간다. 응원은 연출뿐이다.
  4. 2시: 지나간 종목은 '다시 보기' 로, 남은 종목은 시간에 맞춰 중계 · 집중 중이면 건너뛴다 · 중계 중에는 풀숲 ·
     집중 시작이 쉰다.
  5. 올림픽 창 · 신청 창(별 · 표시 · 작전 → 신청) · 순위표 · 결과 카드 · 오른쪽 클릭 줄 · 관리 창 리본 글.
"""
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-oly-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from PIL import Image                                       # noqa: E402

import random                                               # noqa: E402

from common import olympics as O                            # noqa: E402
from common import olympics_rounds as OR                    # noqa: E402
from common import tint as T                                # noqa: E402
from poketdesktop import config                             # noqa: E402
from poketdesktop import olympics as OC                     # noqa: E402
from poketdesktop import olympics_show as OS                # noqa: E402
from poketdesktop import olympics_script as SC              # noqa: E402
from poketdesktop import overlay, sprite_cache, walk_cache, wild_ui  # noqa: E402
from poketdesktop import ui_box                             # noqa: E402
from poketdesktop import ui_olympics as UO                  # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

HOME = os.environ["POKET_HOME"]
OK = FAIL = 0
SHEETS = {}
FILES = {}


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


def pump(root, cond, sec=3.0):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return cond()


class FastTime(object):
    """중계 시계를 scale 배 빠르게."""

    def __init__(self, scale):
        self.scale = scale
        self.t0 = time.monotonic()

    def monotonic(self):
        return self.t0 + (time.monotonic() - self.t0) * self.scale

    def __getattr__(self, k):
        return getattr(time, k)


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


def entrant(i, num, rec, tries=None, mine=False, seed=None, rank=None):
    return {"entryId": 100 + i, "lane": i, "user": "선수%d" % i, "mine": mine,
            "pokemon": {"id": 900 + i, "name": "포켓%d" % i, "species": "S%d" % num, "num": num, "look": num,
                        "shiny": False, "tint": None},
            "tactic": "safe", "record": rec, "text": O.text("sprint", rec) if rec else "기록 없음",
            "tries": tries or [{"v": rec, "slip": False}], "seed": seed or (i * 31 + 7), "rank": rank or (i + 1)}


def heat(event, ents, heat_no=1):
    for e in ents:
        e["text"] = O.text(event, e["record"])
    return {"day": O.DAYS[0], "dayNo": 1, "event": event, "kr": O.EV[event]["kr"], "heat": heat_no, "heats": 2,
            "entrants": ents, "total": 40, "cheer": ["고스트", "불꽃"]}


def fake_comp(ev, n, seed=3):
    """실제 라운드 엔진(common/olympics_rounds)으로 가짜 대회 하나."""
    rng = random.Random(seed)
    pct = {ev: {}}
    ents = []
    for i in range(n):
        key = "SP%d" % i
        pct[ev][key] = rng.random()
        ents.append({"id": 100 + i, "sp": {"internal": key, "kg": O.EV[ev]["kg0"], "types": []}, "ability": None,
                     "tactic": "safe" if i % 2 else "bold", "fat": 0.0, "order": i})
    return OR.run(ev, ents, {"pct": pct, "cheer": (), "seed": seed})


def res_text(ev, fmt, res):
    if fmt == "ski":
        return "%.1f점" % float(res.get("total", res.get("pts")) or 0)
    if fmt in ("rank", "match"):
        return "%d" % int(res.get("v") or 0)
    return O.text(ev, res.get("total", res.get("v")))


def make_script(comp, rno, hno, mine=None):
    """서버 heat_script 와 같은 꼴의 각본 (mine = 내 신청 id, 없으면 그 조 첫 사람)."""
    ev = comp["event"]
    rnd = comp["rounds"][rno - 1]
    h = rnd["heats"][hno - 1]
    mine = h["ids"][0] if mine is None else mine
    ents = []
    for i in h["ids"]:
        res = h["res"].get(i) or {}
        num = (i % 6) + 1
        ents.append({"entryId": i, "lane": h["lanes"].get(i), "user": "선수%d" % i, "mine": i == mine,
                     "pokemon": {"id": 900 + i, "name": "포켓%d" % i, "species": "S%d" % num, "num": num, "look": num,
                                 "shiny": False, "tint": None},
                     "tactic": "safe", "res": res, "record": res.get("total", res.get("v")),
                     "text": res_text(ev, rnd["format"], res), "q": None, "place": (h.get("place") or {}).get(i)})
    sc = {"day": O.day_of(ev), "dayNo": O.day_no(O.day_of(ev)), "event": ev, "kr": O.EV[ev]["kr"],
          "round": {"no": rno, "key": rnd["key"], "kr": rnd["kr"], "of": len(comp["rounds"]),
                    "medal": rno == len(comp["rounds"]) or rnd["key"] == "bronze", "k": rnd.get("k", 0)},
          "heat": hno, "heats": len(rnd["heats"]), "format": rnd["format"], "note": rnd["note"], "entrants": ents,
          "total": comp["n"], "cheer": ["페어리", "물"], "released": False}
    for k in ("match", "after3", "heights"):
        if k in h:
            sc[k] = h[k]
    return sc


class FakeApi(object):
    def __init__(self):
        self.calls = []
        self.live = None
        self.shows = {}
        self.show_fail = 0
        self.heats = {}
        self.state = None
        self.cands = None
        self.board = None

    def olympics_live(self):
        self.calls.append(("live",))
        return self.live

    def olympics_show(self, rnd):
        self.calls.append(("show", rnd))
        if self.show_fail > 0:
            self.show_fail -= 1
            raise RuntimeError("서버가 바빠요")
        return {"script": self.shows.get(rnd)}

    def olympics_heat(self, event, rnd, heat_no):
        self.calls.append(("heat", event, rnd, heat_no))
        return self.heats[(event, rnd, heat_no)]

    def olympics(self):
        self.calls.append(("state",))
        return self.state

    def olympics_candidates(self, event):
        self.calls.append(("cands", event))
        return self.cands

    def olympics_enter(self, event, pid, tactic):
        self.calls.append(("enter", event, pid, tactic))
        return {"day": O.DAYS[0], "entry": {}, "message": "나가요"}

    def olympics_cancel(self, event):
        self.calls.append(("cancel", event))
        return {}

    def olympics_board(self, event):
        self.calls.append(("board", event))
        return self.board


class FakeWild(object):
    def __init__(self):
        self.stops = self.starts = 0

    def stop(self):
        self.stops += 1

    def start(self):
        self.starts += 1


class FakeFocus(object):
    def __init__(self):
        self.on = False
        self.pet_id = None

    def active(self):
        return self.on


class MiniApp(object):
    def __init__(self, root, ov):
        self.root, self.overlay = root, ov
        self.settings = ov.settings
        self.api = FakeApi()
        self.wild = FakeWild()
        self.focus = FakeFocus()
        self.battle = self.arena = None
        self.visit = None
        self.syncs = 0
        self.olympics_window = None
        self.olympics = OC.OlympicsController(self)

    def request_sync(self):
        self.syncs += 1

    def refresh_tray(self):
        pass

    def notify(self, m):
        pass


def shown(w):
    try:
        return w.state() != "withdrawn"
    except Exception:                                       # noqa: BLE001
        return False


def run_show(root, app, h, scale, sec=20.0, replay=False):
    OS.time = FastTime(scale)
    got = {}
    s = OS.Show(app, h, on_done=lambda sh, r: got.update(r=r, t=OS.time.monotonic()), replay=replay)
    ticks = [0]
    orig = s._tick

    def counted():
        ticks[0] += 1
        orig()
    s._tick = counted
    t0 = OS.time.monotonic()
    s.start()
    pump(root, lambda: "r" in got, sec)
    # 중계 시계로 잰 길이 - 첫 틱부터 (창을 만드는 동안은 빠른 시계가 실제 시간을 부풀린다)
    s.show_secs = (got["t"] - (s._t0 or t0)) if "t" in got else None
    OS.time = time
    return s, got.get("r"), ticks[0]


# ---------------------------------------------------------------- 1. 달리기형
def race_part(root, ov, app):
    print("=== 달리기형 ===")
    recs = [12.31, 11.84, 12.95, 12.02, 13.40, 12.60, 11.97, 12.20]
    ents = [entrant(i, (i % 6) + 1, r, mine=(i == 2)) for i, r in enumerate(recs)]
    for e in ents:
        e["lane"] += 1                                     # 레인은 1~8
    ents[2]["tries"] = [{"v": recs[2], "slip": True, "at": 0.5}]
    s0 = [shown(p.win) for p in ov.pets.values()]
    started = {}
    orig_start = OS.Show._race_setup

    def spy(self):
        orig_start(self)
        started["extra"] = len(ov.extra)
        started["hidden"] = all(not shown(p.win) for p in ov.pets.values())
        started["names"] = ov._names_block
    OS.Show._race_setup = spy
    crossed = []
    orig_cross = OS.Show._crossed

    def spy_cross(self, e):
        crossed.append(e["entryId"])
        return orig_cross(self, e)
    OS.Show._crossed = spy_cross
    cards = []
    orig_card = OS.Show._card

    def spy_card(self, num, e, sub, label="레인"):
        cards.append((num, e["entryId"], label, len([p for p in self.pets.values() if p.out])))
        return orig_card(self, num, e, sub, label)
    OS.Show._card = spy_card
    s, r, ticks = run_show(root, app, heat("sprint", ents), 10)
    OS.Show._race_setup = orig_start
    OS.Show._crossed = orig_cross
    OS.Show._card = orig_card
    chk("100m 출전식: 레인 차례로 한 마리씩 자막 (나온 선수 수가 하나씩 는다)",
        [c[0] for c in cards[:8]] == [e["lane"] for e in ents] and [c[3] for c in cards[:8]] == list(range(8))
        and all(c[2] == "레인" for c in cards[:8]), cards[:8])
    chk("100m: 선수 8마리가 나온다", started.get("extra") == 8, started)
    chk("100m: 그동안 바탕화면 포켓몬은 숨는다 · 이름표도", started.get("hidden") and started.get("names", 0) > 0, started)
    chk("100m: 끝까지 간다", r is not None and not r["aborted"], r)
    want = [e["entryId"] for e in sorted(ents, key=lambda e: e["record"])]
    chk("100m: 기록 차례대로 들어온다 (한 틱에 여럿이어도)", crossed == want, (crossed, want))
    chk("100m: 넘어진 내 선수에게 말", any("넘어졌어요" in x for x in s.said), s.said)
    chk("100m: 결과 - 조 순위", r["heatRank"] == 7 and r["text"] == "12.95초", r)
    chk("100m: 끝나면 선수 창이 없다", not ov.extra and not s.pets)
    chk("100m: 바탕화면 포켓몬이 되살아난다", [shown(p.win) for p in ov.pets.values()] == s0 and ov.only is None)
    chk("100m: 이름표 막음도 풀린다", ov._names_block == 0, ov._names_block)
    chk("100m: 창 옮기기는 틱 x 선수 수 안 (맥 CPU)", s.moves <= ticks * 8 + 16, (s.moves, ticks))

    # 봅슬레이: 한 대씩 - 썰매를 타고, 구간 기록, 벽에 부딪힌 내 썰매
    ents = [entrant(i, (i % 6) + 1, 49.0 + i * 0.6, mine=(i == 1)) for i in range(4)]
    ents[1]["tries"] = [{"v": ents[1]["record"], "slip": True, "at": 0.4}]
    sleds = []
    orig_run = OS.Show._bob_run

    def spy_run(self, k, n, e):
        steps = orig_run(self, k, n, e)
        def look(p, _fn=steps[2]["fn"]):
            _fn(p)
            sleds.append(sum(1 for a in self.arts if a.shown and a.w == a.h == 46 * self.S))
        steps[2]["fn"] = look
        return steps
    OS.Show._bob_run = spy_run
    s, r, _t = run_show(root, app, heat("bobsled", ents), 12, sec=25)
    OS.Show._bob_run = orig_run
    chk("봅슬레이: 끝까지", r is not None and not r["aborted"], r)
    chk("봅슬레이: 기록 = 서버 기록", all(s.best.get(e["entryId"]) == e["record"] for e in ents), s.best)
    chk("봅슬레이: 썰매는 한 번에 한 대만", sleds and max(sleds) == 1, (max(sleds or [0]), len(sleds)))
    chk("봅슬레이: 선수마다 구간 기록 셋", all(len(s.splits.get(e["entryId"], [])) == 3 for e in ents), s.splits)
    chk("봅슬레이: 벽에 부딪힌 내 썰매 말", any("벽에" in x for x in s.said), s.said)

    # 마라톤: 둘레를 돌고 다 들어온다 (한 마리는 도트가 없다)
    ents = [entrant(i, (i % 6) + 1, 7400 + i * 90, mine=(i == 1)) for i in range(5)]
    ents[4]["pokemon"]["num"] = ents[4]["pokemon"]["look"] = 777          # 도트 없음
    s, r, _t = run_show(root, app, heat("marathon", ents), 40)
    chk("마라톤: 도트 없는 선수가 있어도 끝까지", r is not None and not r["aborted"] and len(s.done_at) == 5, r)
    chk("마라톤: 중간 순위 말", any("지점" in x for x in s.said), s.said)
    # 가장 느린 마라톤(점수 0.58 = 3:44:08)이 있어도 중계가 프로그램 끝 전에 끝난다
    slow = [entrant(i, (i % 6) + 1, rec) for i, rec in enumerate((7400, 13448))]
    sh = OS.Show(app, heat("marathon", slow))
    sh._stage()
    sh.pets = {}
    sh.layer = None
    sh._race_setup()
    longest = max(sh.T.values())
    budget = (OR.slot("marathon", "final") - OC.READY_WAIT_MS / 1000.0
              - (8 * (OS.WALK_IN_MS + OS.INTRO_HOLD_MS) + OS.READY_MS + OS.OUTRO_MS) / 1000.0 - 2.0)
    chk("마라톤: 가장 느린 선수도 그 칸 안에 들어온다", longest <= budget, (longest, budget))


# ---------------------------------------------------------------- 2. 시기형
def field_part(root, ov, app):
    print("=== 시기형 ===")
    for ev, vals in (("pole", (5.1, 5.35, None)), ("archery", (10, None, 9)),
                     ("discus", (52.3, None, 55.0)), ("ski", (None, 118.5, 121.0))):
        ents = []
        for i in range(3):
            if ev == "archery":
                tries = [{"v": 10, "x": i == 0, "slip": False}, {"v": None, "slip": True},
                         {"v": 9 - i, "slip": False}]
                rec = O.archery_total(tries)
            else:
                tries = [{"v": (v + i * 0.1) if v else None, "slip": v is None} for v in vals]
                rec = O.best_of(ev, [t["v"] for t in tries])
            ents.append(entrant(i, i + 1, rec, tries=tries, mine=(i == 0)))
        props_made = []
        orig_prop = OS.Prop.__init__

        def spy_prop(self, *a, **kw):
            orig_prop(self, *a, **kw)
            props_made.append(self)
        OS.Prop.__init__ = spy_prop
        place_counts = {}
        orig_make = OS.Show._make_athletes

        def spy_make(self):
            orig_make(self)
            for eid, p in self.pets.items():
                c = place_counts.setdefault(eid, [0])
                o = p.place

                def place(o=o, c=c):
                    c[0] += 1
                    o()
                p.place = place
        OS.Show._make_athletes = spy_make
        s, r, ticks = run_show(root, app, heat(ev, ents), 14, sec=30)
        OS.Prop.__init__ = orig_prop
        OS.Show._make_athletes = orig_make
        name = O.EV[ev]["kr"]
        chk("%s: 끝까지" % name, r is not None and not r["aborted"], r)
        chk("%s: 점수판 최고 기록 = 서버 기록" % name,
            all(s.best.get(e["entryId"]) == e["record"] for e in ents), (s.best, [e["record"] for e in ents]))
        chk("%s: 파울을 센다" % name, sum(s.fouls.values()) == 3, s.fouls)
        chk("%s: 기다리는 선수는 창을 거의 안 옮긴다 (선수마다 자기 차례 몫만)" % name,
            max(c[0] for c in place_counts.values()) <= ticks * 0.6 + 20, (place_counts, ticks))
        chk("%s: 소품 · 카드 창이 다 치워진다" % name, props_made and all(p.win is None for p in props_made)
            and not ov.extra and not s.arts, (len(props_made), len(s.arts)))
        if ev == "pole":
            chk("장대: 내 차례 말", any("내 차례" in x for x in s.said), s.said)
        if ev == "ski":
            sk = OS.A.skis("flat", s.S)[0].size
            chk("스키점프: 스키 창을 띄웠다 (발에 스키)", any((p.w, p.h) == sk for p in props_made),
                ([(p.w, p.h) for p in props_made][:12], sk))
        if ev == "archery":
            chk("양궁: 과녁 확대 화면에 화살이 다 꽂혔다", all(len(s.arrows[e["entryId"]]) == 3 for e in ents), s.arrows)


# ---------------------------------------------------------------- 2b. 중계 길이 (8마리 · 세 번 시기)
def script_part():
    print("=== 각본 -> 중계 꼴 (olympics_script) ===")
    sp = fake_comp("sprint", 30)
    h = SC.legacy(make_script(sp, 1, 1))
    k = sp["rounds"][0]["k"]
    chk("100m 예선: 8명 이하 · 내가 있다 · 시도 하나 · 칸 = 예선 칸 · 시상식 없음", len(h["entrants"]) <= 8
        and any(e["mine"] for e in h["entrants"]) and all(len(e["tries"]) == 1 for e in h["entrants"])
        and h["budget"] == OR.slot("sprint", "r1") and h["roundKr"] == "예선" and not h["medal"], h["roundKr"])
    chk("  조 상위 k명은 바로 Q (q 는 서버가 연 뒤)", sorted(e["place"] for e in h["entrants"] if e["q"] == "Q")
        == list(range(1, k + 1)), [(e["place"], e["q"]) for e in h["entrants"]])
    hf = SC.legacy(make_script(sp, 3, 1))
    chk("100m 결승: 메달 라운드 · 결승 칸", hf["medal"] and hf["budget"] == OR.slot("sprint", "final"))
    mr = fake_comp("marathon", 40)
    mine = mr["standings"][-1]["id"]
    hm = SC.legacy(make_script(mr, 1, 1, mine))
    chk("마라톤 40명: 선두 무리 7 + 꼴찌인 나 = 8", len(hm["entrants"]) == 8 and any(e["entryId"] == mine for e in hm["entrants"]))
    bo = fake_comp("bobsled", 25)
    b1 = SC.legacy(make_script(bo, 1, 1, bo["standings"][-1]["id"]))
    chk("봅슬레이 1차: 나 + 선두 = 2대", len(b1["entrants"]) == 2 and any(e["mine"] for e in b1["entrants"]))
    b4 = SC.legacy(make_script(bo, 4, 1, bo["standings"][-1]["id"]))
    chk("봅슬레이 4차: 마지막 세 대 (+ 나)", 3 <= len(b4["entrants"]) <= 4, len(b4["entrants"]))
    di = fake_comp("discus", 30)
    hd = SC.legacy(make_script(di, 2, 1))
    chk("원반 결승: 6명 이하 · 시도 3 또는 6", len(hd["entrants"]) <= 6
        and all(len(e["tries"]) in (3, 6) for e in hd["entrants"]), [len(e["tries"]) for e in hd["entrants"]])
    po = fake_comp("pole", 30)
    hp = SC.legacy(make_script(po, 2, 1))
    chk("장대 결승: 6명 이하 · 마지막 시도 셋까지 (바 높이)", len(hp["entrants"]) <= 6
        and all(1 <= len(e["tries"]) <= 3 and all("bar" in t for t in e["tries"]) for e in hp["entrants"]))
    sk = fake_comp("ski", 40)
    hs = SC.legacy(make_script(sk, 2, 1, sk["rounds"][1]["heats"][0]["ids"][0]))     # 결선 첫 순서 (1라운드 30위)
    chk("스키점프 결선: 마지막 셋 + 나", len(hs["entrants"]) == 4 and hs["medal"], len(hs["entrants"]))
    ar = fake_comp("archery", 10)
    fin = SC.legacy(make_script(ar, len(ar["rounds"]), 1))
    m = ar["rounds"][-1]["heats"][0]["match"]
    n_arrows = 3 * len(m["sets"]) + (1 if m["shoot"] else 0)
    chk("양궁 랭킹은 '결과만', 1대1 은 두 사람이 화살을 번갈아 (결승은 모든 세트)",
        SC.legacy(make_script(ar, 1, 1))["resultsOnly"] and not fin["resultsOnly"] and len(fin["entrants"]) == 2
        and all(len(e["tries"]) == n_arrows for e in fin["entrants"]) and fin["podium"], [len(e["tries"]) for e in fin["entrants"]])
    sf = next(r for r in ar["rounds"] if r["key"] == "qf")
    q = SC.legacy(make_script(ar, sf["no"], 1))
    chk("  8강 같은 경기는 마지막 두 세트만 (앞 세트 점수는 판에 먼저)", all(len(e["tries"]) <= 7 for e in q["entrants"])
        and q["setStart"]["skip"] == max(0, len(sf["heats"][0]["match"]["sets"]) - 2), q.get("setStart"))
    br = next(r for r in ar["rounds"] if r["key"] == "bronze")
    chk("  동메달전은 시상식 없이 (시상식은 결승 뒤)", not SC.legacy(make_script(ar, br["no"], 1))["podium"])
    # 독립 검토(11/08): 화면에 고른 몇 명 안에서 순위를 다시 세면 시상대 · '금메달!' 이 틀린다
    bad = []
    for sd in range(1, 16):
        for ev, n, rno in (("bobsled", 25, 4), ("ski", 40, 2)):
            c = fake_comp(ev, n, sd)
            ids = c["rounds"][rno - 1]["heats"][0]["ids"]
            h = SC.legacy(make_script(c, rno, 1, ids[0]))          # 나 = 먼저 출발한 쪽 (대개 아래 순위)
            truth = dict((x["id"], x["rank"]) for x in c["standings"])
            rk = OS.heat_rank(ev, h["entrants"])
            if not {1, 2, 3} <= set(e["place"] for e in h["entrants"]) or any(
                    rk[e["entryId"]] != truth[e["entryId"]] for e in h["entrants"]):
                bad.append((ev, sd))
    chk("봅슬레이 4차 · 스키점프 결선: 실제 1~3위가 화면에 있고 순위 = 진짜 순위 (시상대 · 메달 말이 맞다)", not bad, bad[:4])
    mr = fake_comp("marathon", 60)
    last = mr["standings"][-1]["id"]
    hm = SC.legacy(make_script(mr, 1, 1, last))
    chk("마라톤 꼴찌인 나: 화면 순위도 60위 (고른 8명 안 8위가 아니다)", OS.heat_rank("marathon", hm["entrants"])[last] == 60,
        OS.heat_rank("marathon", hm["entrants"])[last])
    chk("말: 조가 하나면 'N위 / 전체 M명', 여럿이면 '조 N위', 결승은 '결승 N위', 동메달전은 승 · 패",
        OS.place_text(hm, 60) == "60위 / 60명" and OS.place_text(SC.legacy(make_script(sp, 1, 1)), 2) == "조 2위"
        and OS.place_text(hf, 3) == "결승 3위" and OS.place_text(SC.legacy(make_script(ar, br["no"], 1)), 1)
        == "동메달 결정전 승" and OS.place_text(SC.legacy(make_script(ar, br["no"], 1)), 2) == "동메달 결정전 패",
        (OS.place_text(hm, 60), OS.place_text(hf, 3)))
    b4 = SC.legacy(make_script(bo, 4, 1, bo["rounds"][3]["heats"][0]["ids"][0]))
    me4 = b4["entrants"][0]
    want = 1 + sum(1 for x in bo["rounds"][3]["heats"][0]["ids"][:1] if False)
    chk("봅슬레이 '지금 N위' = 그때까지 출발한 모든 썰매의 합계로 (화면의 2~4대 안이 아니다)",
        OS.trial_place(b4, me4["entryId"]) == 1 and OS.trial_place(b4, b4["entrants"][-1]["entryId"]) == 1 + sum(
            1 for i in bo["rounds"][3]["heats"][0]["ids"]
            if bo["rounds"][3]["heats"][0]["res"][i]["total"] < bo["rounds"][3]["heats"][0]["res"][
                b4["entrants"][-1]["entryId"]]["total"]), (me4["entryId"], b4["entrants"][-1]["entryId"]))


def budget_part(root, ov, app):
    print("=== 유리판 높이 ===")
    from poketdesktop import olympics_art as A
    for ev in O.KEYS:
        v = A.venue(ev, 1360, 2)
        cap = 260 if ev == "ski" else 200          # 스키점프만 조금 높게 (사용자 11/07 '스키점프는 조금 더 높여주는데')
        chk("%s: 경기장 높이 %dpt <= %d (폭은 넓게 써도 높이는 낮게 - 사용자 11/07)" % (O.EV[ev]["kr"], v.h, cap),
            v.h <= cap, v.h)
    chk("경기장은 바탕화면이 비치는 유리판 (창 투명도 < 1)", 0 < A.VENUE_ALPHA < 1.0, A.VENUE_ALPHA)
    print("=== 라운드마다 중계 길이 ===")
    cases = [("sprint", 30, None), ("marathon", 40, None), ("bobsled", 25, None), ("pole", 30, None),
             ("discus", 30, None), ("ski", 60, None), ("archery", 8, None)]
    for ev, n, _x in cases:
        comp = fake_comp(ev, n)
        for rnd in comp["rounds"]:
            sc = make_script(comp, rnd["no"], 1)
            h = SC.legacy(sc)
            slot = OR.slot(ev, rnd["key"])
            planned = {}
            orig = OS.Show._program

            def prog(self):
                steps = orig(self)
                planned["s"] = sum(x["ms"] for x in steps) / 1000.0
                return steps
            OS.Show._program = prog
            _s, r, _t = run_show(root, app, h, 60, sec=20)
            OS.Show._program = orig
            need = planned.get("s", 9e9) + OC.READY_WAIT_MS / 1000.0
            chk("%s %s: 중계 %.0f초 + 준비 %.0f초 <= 칸 %d초" % (O.EV[ev]["kr"], rnd["kr"], planned.get("s", -1),
                                                         OC.READY_WAIT_MS / 1000.0, slot),
                r is not None and not r["aborted"] and need + 1.0 <= slot, (planned, slot, r and r.get("aborted")))


# ---------------------------------------------------------------- 3. 응원 · 닫기
def cheer_part(root, ov, app):
    print("=== 응원 · 닫기 ===")
    ents = [entrant(i, (i % 6) + 1, 12.0 + i * 0.2, mine=(i == 0)) for i in range(3)]
    OS.time = FastTime(1)
    got = {}
    s = OS.Show(app, heat("sprint", ents), on_done=lambda sh, r: got.update(r=r))
    s.start()
    settle(root, 0.3)
    me = s.pets[ents[0]["entryId"]]
    me.on_press(None)
    chk("응원: 내 포켓몬을 누르면 하트 (기록은 그대로)", "♥" in s.said and ents[0]["record"] == 12.0)
    s.stop()
    settle(root, 0.2)
    OS.time = time
    chk("× 로 닫으면 aborted · 선수 창 없음", got.get("r", {}).get("aborted") and not ov.extra, got)


# ---------------------------------------------------------------- 4. 2시
def live_part(root, ov, app):
    print("=== 2시 ===")
    o = app.olympics
    comp = fake_comp("sprint", 20)
    fin_ids = comp["rounds"][-1]["heats"][0]["ids"]
    me = fin_ids[0]                                  # 결승까지 간 나
    r1h = next(h["no"] for h in comp["rounds"][0]["heats"] if me in h["ids"])
    first = make_script(comp, 1, r1h, me)
    final = make_script(comp, 2, 1, me)
    app.api.live = {"day": O.DAYS[0], "dayNo": 1, "event": "sprint", "kr": "100m 달리기", "entered": True,
                    "elapsed": 130, "endIn": 300,
                    "program": [{"round": 1, "key": "r1", "kr": "예선", "showIn": -110, "len": 75},
                                {"round": 2, "key": "final", "kr": "결승", "showIn": 0, "len": 87, "medal": True}],
                    "first": first}
    app.api.shows = {2: final}
    played = []
    orig = OC.OlympicsController._play

    def spy(self, h, replay=False, ready=None, waited=0):
        if not waited:
            played.append((h["event"], h.get("roundKr"), replay))
        return orig(self, h, replay, ready, waited)
    OC.OlympicsController._play = spy
    OS.time = FastTime(30)
    o.note({"phase": "live", "nextDay": O.DAYS[0], "event": "sprint", "startsIn": -130, "endIn": 300})
    pump(root, lambda: played, 15)                   # CI 윈도우 러너는 느리다 - 4초로는 결승 중계 전에 끊겼다 (2.3.0 CI)
    chk("켰을 때 경기 중이면 바로 받는다", ("live",) in app.api.calls)
    chk("지나간 예선은 다시 보기로, 결승은 그 직전에 받아 중계", [p[1] for p in played] == ["결승"]
        and ("show", 2) in app.api.calls and len(o.missed) == 1, (played, app.api.calls[-3:], len(o.missed)))
    chk("지나간 라운드 말", any("다시 볼 수 있어요" in x for x in o.said), o.said)
    chk("중계 중에는 풀숲이 쉰다", wild_ui.WildController._focusing(type("W", (), {"app": app})()))
    from poketdesktop.app import App
    chk("중계 중에는 업적 · 부화 · 보따리 알림을 미룬다 (focus_quiet)", App.focus_quiet(app))
    pump(root, lambda: not o.busy(), 14)
    OS.time = time
    chk("중계가 끝나면 풀숲 다시", app.wild.starts >= 1)
    chk("끝나면 알림을 다시 띄운다", not App.focus_quiet(app))
    n = len([c for c in app.api.calls if c == ("live",)])
    o.note({"phase": "live", "nextDay": O.DAYS[0], "startsIn": -200, "endIn": 200})
    settle(root, 0.2)
    chk("같은 날은 한 번만 받는다", len([c for c in app.api.calls if c == ("live",)]) == n)
    # 떨어진 라운드는 조용히 넘어간다 (서버가 script None)
    o.clear()
    app.api.shows = {2: None}
    app.api.live = dict(app.api.live, program=[{"round": 1, "showIn": -200}, {"round": 2, "showIn": 0}])
    played[:] = []
    o.note({"phase": "live", "nextDay": O.DAYS[0], "startsIn": -200, "endIn": 100})
    settle(root, 0.8)
    chk("내가 없는 라운드(서버가 없다고 하면)는 중계 없이 넘어간다", not played and ("show", 2) in app.api.calls)
    # 독립 검토: 둘째 라운드 각본 받기가 실패하면 한 번 더, 그래도 안 되면 다시 보기 안내 (조용히 버리지 않는다)
    o.clear()
    app.api.shows = {2: final}
    app.api.show_fail = 1
    played[:] = []
    n0 = len([c for c in app.api.calls if c == ("show", 2)])
    o.note({"phase": "live", "nextDay": O.DAYS[0], "startsIn": -200, "endIn": 100})
    pump(root, lambda: played, 6)
    chk("둘째 라운드 받기가 한 번 실패해도 다시 받아 중계", [p[1] for p in played] == ["결승"]
        and len([c for c in app.api.calls if c == ("show", 2)]) - n0 == 2, (played, app.api.calls[-4:]))
    pump(root, lambda: not o.busy(), 14)
    o.clear()
    app.api.show_fail = 5
    said0 = len(o.said)
    o.note({"phase": "live", "nextDay": O.DAYS[0], "startsIn": -200, "endIn": 100})
    pump(root, lambda: len(o.missed) >= 1, 6)
    chk("  계속 실패하면 놓친 것으로 · 다시 보기 안내", len(o.missed) >= 1
        and any("다시 볼 수 있어요" in x for x in o.said[said0:]), (o.missed, o.said[said0:]))
    app.api.show_fail = 0
    # 집중 중이면 건너뛴다
    o.clear()
    app.focus.on = True
    app.api.live = dict(app.api.live, program=[{"round": 1, "showIn": 0}], first=first)
    played[:] = []
    o.note({"phase": "live", "nextDay": O.DAYS[0], "startsIn": -5, "endIn": 300})
    settle(root, 0.6)
    chk("집중 중이면 중계를 건너뛰고 한 번 알린다", not played and sum("집중하는 중이라" in x for x in o.said) == 1,
        (played, o.said[-2:]))
    app.focus.on = False
    OC.OlympicsController._play = orig
    o.clear()
    # 2시 전: 예약만
    calls = len(app.api.calls)
    o.note({"phase": "entry", "nextDay": O.DAYS[0], "event": "sprint", "startsIn": 3600, "endIn": 4300, "dayNo": 1})
    chk("2시 전에는 예약만 (부르지 않는다)", len(app.api.calls) == calls and o._start_job is not None)
    o.clear()
    # 다시 보기
    app.api.heats[("sprint", 1, r1h)] = first
    res = {}
    OS.time = FastTime(30)
    o.replay("sprint", 1, r1h, lambda h, err: res.update(h=h, err=err))
    chk("다시 보기를 누른 순간부터 바쁨 (각본을 받는 동안에도)", o.busy())
    pump(root, lambda: o.show is not None and o.show.alive, 8)       # 도트 받기 기다림은 실제 시간 (바쁜 기계면 3초 넘게)
    chk("다시 보기: 종목 · 라운드 · 조로 받아 중계 (다시 보기 띠)", res.get("h") and res["h"]["roundKr"] == "예선"
        and o.busy() and o.show.replay and ("heat", "sprint", 1, r1h) in app.api.calls)
    res2 = {}
    o.replay("sprint", 1, r1h, lambda h, err: res2.update(err=err))
    chk("중계 중에는 다른 다시 보기를 막는다", "중계하고" in (res2.get("err") or ""), res2)
    pump(root, lambda: not o.busy(), 10)
    settle(root, 0.3)
    OS.time = time
    chk("다시 보기 뒤 결과 카드", o.result_card is not None and o.result_card.win.winfo_exists())
    # 독립 검토: 각본을 중계 꼴로 바꾸다 예외가 나도 '중계 중' 에 갇히지 않는다
    app.api.heats[("sprint", 9, 9)] = {"event": "sprint", "round": None, "entrants": [{"broken": True}]}
    bad = {}
    o.replay("sprint", 9, 9, lambda h, err: bad.update(err=err))
    pump(root, lambda: "err" in bad, 3)
    chk("다시 보기: 이상한 각본이면 알리고 바쁨이 풀린다", bad.get("err") and not o.busy(), (bad, o.busy()))
    o.clear()
    chk("정리하면 결과 카드도 닫힌다", o.result_card is None)


# ---------------------------------------------------------------- 4b. 겹침 · 정리 (독립 검토)
def guard_part(root, ov, app):
    print("=== 겹침 · 정리 ===")
    o = app.olympics
    o.clear()
    h = heat("sprint", [entrant(i, (i % 6) + 1, 12.0 + i * 0.3, mine=(i == 0)) for i in range(3)])
    sc = make_script(fake_comp("sprint", 6), 1, 1)
    app.api.heats[("sprint", 1, 1)] = sc
    shows, overlap = [], []
    real_start = OS.Show.start

    def spy_start(self):
        if any(x.alive for x in shows):
            overlap.append(self.ev)
        shows.append(self)
        return real_start(self)
    OS.Show.start = spy_start
    OS.time = FastTime(30)
    r1, r2 = {}, {}
    o.replay("sprint", 1, 1, lambda hh, err: r1.update(h=hh, err=err))
    o.replay("sprint", 1, 1, lambda hh, err: r2.update(h=hh, err=err))
    chk("다시 보기를 두 번 빨리 눌러도 두 번째는 막힌다", "중계하고" in (r2.get("err") or ""), r2)
    o._due(heat("bobsled", [entrant(i, (i % 6) + 1, 49.0 + i, mine=(i == 0)) for i in range(3)]))
    chk("다시 보기를 준비하는 사이 정해진 중계가 오면 줄을 선다", len(o.queue) == 1, len(o.queue))
    pump(root, lambda: len(shows) >= 2 and not o.busy(), 12)
    chk("중계가 둘 동시에 돌지 않는다", not overlap and len(shows) == 2, (overlap, len(shows)))
    OS.Show.start = real_start
    o.clear()
    # 준비 중에 오류가 나도 바탕화면이 갇히지 않는다
    real_setup = OS.Show._race_setup

    def boom(self):
        raise RuntimeError("시험")
    OS.Show._race_setup = boom
    o._ready_all = True
    o._play(h)
    settle(root, 0.3)
    OS.Show._race_setup = real_setup
    chk("중계 준비 중 오류: 포켓몬 · 이름표가 돌아온다", ov.only is None and ov._names_block == 0 and not ov.extra,
        (ov.only, ov._names_block, len(ov.extra)))
    chk("중계 준비 중 오류: 바쁨이 풀린다 (집중 · 대전이 안 막힌다)", not o.busy())
    # 로그아웃: 풀숲을 다시 켜지 않고, 카드 · 늦게 온 답을 버린다
    o.card = {"phase": "live"}
    o.replay("sprint", 1, 1)
    pump(root, lambda: o.show is not None and o.show.alive, 3)
    starts = app.wild.starts
    o.clear()
    settle(root, 0.2)
    chk("로그아웃 정리: 풀숲을 다시 켜지 않는다", app.wild.starts == starts, (starts, app.wild.starts))
    chk("로그아웃 정리: 트레이 줄이 사라진다", not o.on() and o.card is None)
    app.api.live = {"day": O.DAYS[0], "dayNo": 1, "event": "sprint", "entered": True, "elapsed": 5,
                    "program": [{"round": 1, "showIn": 0}], "first": sc}
    o.load_live(O.DAYS[0])
    o.clear()                                     # 받는 중에 로그아웃
    settle(root, 0.6)
    chk("로그아웃 뒤 늦게 온 경기 답은 버린다", o.live is None and not o.busy() and not o._jobs, (o.live, o._jobs))
    # 중계 중에 (다른 PC 에서 이어 받은) 집중이 시작되면 끝날 때 집중 포켓몬만 남긴다
    pid = next(iter(ov.pets))
    o.replay("sprint", 1, 1)
    pump(root, lambda: o.busy() and o.show is not None, 3)
    app.focus.on, app.focus.pet_id = True, pid
    pump(root, lambda: not o.busy(), 10)
    chk("중계 중에 집중이 시작됐으면 끝난 뒤 집중 포켓몬만 보인다", ov.only == pid, ov.only)
    app.focus.on, app.focus.pet_id = False, None
    ov.set_only(None)
    # 대전 상대를 찾는 중 · 대전을 불러오는 중에도 중계를 미룬다
    app._pvp_busy = True
    chk("대전 상대를 찾는 중이면 중계를 건너뛴다", o.blocked() == "pvp", o.blocked())
    app._pvp_busy = False
    app._match_loading = True
    chk("대전을 불러오는 중이어도", o.blocked() == "pvp", o.blocked())
    app._match_loading = False
    OS.time = time
    o.clear()


# ---------------------------------------------------------------- 5. 창
def state_sample():
    evs = []
    for e in O.EVENTS:
        d = O.day_of(e["key"])
        evs.append({"key": e["key"], "kr": e["kr"], "short": e["short"], "day": d, "status": "entry", "canEnter": True,
                    "statKr": e["statKr"], "kg0": e["kg0"], "types": ["전기"], "abil": ["속보"],
                    "cheer": [{"type": t, "kr": {"FAIRY": "페어리", "WATER": "물"}.get(t, t)} for t in O.cheer_of(d)],
                    "startsIn": 7200, "entry": None, "ran": False, "entrants": None, "result": None})
    evs[0].update(status="done", canEnter=False, ran=True, entrants=120,
                  entry={"id": 1, "event": "sprint", "day": O.DAYS[0], "tactic": "safe", "tacticKr": "안정",
                         "pokemon": {"id": 900, "name": "피카츄", "num": 25}},
                  result={"rank": 3, "total": 120, "text": "11.84초", "reached": "결승", "medal": True,
                          "watch": {"round": 3, "heat": 1}})
    evs[1]["entry"] = {"id": 2, "event": "bobsled", "day": O.DAYS[1], "tactic": "safe", "tacticKr": "안정",
                       "pokemon": {"id": 900, "name": "피카츄", "num": 25}}
    return {"phase": "entry", "days": list(O.DAYS), "at": "14:00", "nextDay": O.DAYS[1], "today": "bobsled",
            "dayNo": 2, "startsIn": 7200, "events": evs,
            "tactics": [{"key": "safe", "kr": "안정"}, {"key": "bold", "kr": "승부수"}],
            "medals": {"sprint": [{"rank": 1, "user": "가", "pokemon": {"name": "라이츄"}, "text": "11.20초"}]},
            "myMedals": [{"event": "sprint", "kr": "100m 달리기", "rank": 3, "text": "11.84초",
                          "pokemon": {"name": "피카츄"}}]}


def inside(win, widget):
    """widget 이 창 안에 다 보이나 (놓여 있고, 아래 끝이 창 아래 끝을 안 넘는다). 재서 본다."""
    try:
        win.update_idletasks()
        if not widget.winfo_ismapped():
            return False
        return widget.winfo_rooty() + widget.winfo_height() <= win.winfo_rooty() + win.winfo_height() + 1
    except Exception:                                       # noqa: BLE001
        return False


def many_cands(n):
    return {"event": "bobsled", "day": O.DAYS[1], "pokemon": [
        {"id": 2000 + i, "name": "포켓몬%d" % i, "species": "포켓몬%d" % i, "num": 7, "level": 10 + i, "shiny": False,
         "onDesktop": i < 3, "kg": 9.0, "types": ["물"], "stars": 1 + i % 5,
         "hints": ["물 특기", "체형 딱 맞음", "스피드 · 체력 좋음"], "away": False, "alsoIn": [], "entered": False}
        for i in range(n)]}


def texts_of(win):
    out = []

    def walk(wd):
        for c in wd.winfo_children():
            try:
                t = c.cget("text")
                if t:
                    out.append(t)
            except Exception:                               # noqa: BLE001
                pass
            walk(c)
    walk(win)
    return " | ".join(out)


def window_part(root, ov, app):
    print("=== 이벤트 탭 ===")
    from poketdesktop import ui_hub
    groups = [g[0] for g in ui_hub.GROUPS]
    chk("허브 묶음: 커뮤니티와 마이페이지 사이에 '이벤트' (올림픽 탭)", groups[-2:] == ["event", "my"]
        and ui_hub.GROUP_OF.get("olympics") == "event" and any(t[0] == "olympics" for t in ui_hub.TABS), groups)
    app.api.state = state_sample()
    holder = tk.Toplevel(root)
    holder.geometry("900x640+40+40")
    app._tab = lambda key: w                       # 허브 대신 (open_olympics 가 이 탭을 연다)
    w = UO.OlympicsPane(app, holder)
    w.win.pack(fill="both", expand=True)
    pump(root, lambda: w.st is not None, 2)
    settle(root, 0.3)
    blob = texts_of(w.win)
    chk("이벤트 탭: 다음 경기 날짜 · 종목 · 오후 2시 · 남은 때", "다음 경기" in blob and "봅슬레이" in blob
        and "오후 2시" in blob and "2시간" in blob and "14:00" not in blob, blob[:220])
    chk("이벤트 탭: 종목 일곱 줄 · 날짜 · 상태", sum(1 for e in O.EVENTS if e["kr"] in blob) == 7
        and "11/16(월)" in blob and "11/24(화)" in blob and "신청 중" in blob and "끝" in blob, blob[:400])
    chk("이벤트 탭: 그날 응원 타입", "그날 응원 타입" in blob and "페어리" not in blob.split("100m 달리기")[0], blob[:200])
    chk("이벤트 탭: 내 신청 · 내 결과(순위 · 간 라운드 · 메달) · 다시 보기", "신청: 피카츄 · 안정" in blob
        and "3위 / 120명" in blob and "결승" in blob and "동메달!" in blob and "다시 보기" in blob, blob[:600])
    chk("이벤트 탭: 내 메달 · 종목별 메달", "내 메달" in blob and "종목별 메달" in blob)
    chk("이벤트 탭: 1~3위 상 = 메달 꾸미기 · 그 종목 칭호 (스키점프 'Butterfly' · 마라톤 '%s')" % O.TITLE["marathon"],
        "메달 꾸미기" in blob and "'Butterfly'" in blob and "'%s'" % O.TITLE["marathon"] in blob, blob[:300])
    chk("트레이 · 오른쪽 클릭: 이벤트 탭을 연다", UO.open_olympics(app) is w)
    n_state = len([c for c in app.api.calls if c == ("state",)])
    w._loaded_at -= 120                           # 2분 전에 불러온 탭
    w.on_shown()
    pump(root, lambda: len([c for c in app.api.calls if c == ("state",)]) > n_state, 2)
    chk("이벤트 탭: 다시 보이면 (오래됐으면) 새로 불러온다 - 14:05 에 옛 '신청 중' 이 남지 않게",
        len([c for c in app.api.calls if c == ("state",)]) > n_state)
    w._replay("sprint", 3, 1)
    chk("다시 보기: 종목 · 라운드 · 조로 받는다", ("heat", "sprint", 3, 1) in app.api.calls or o_busy(app),
        app.api.calls[-2:])
    app.olympics.clear()
    # 신청 창
    app.api.cands = {"event": "bobsled", "day": O.DAYS[1], "total": 12,
                     "share": [{"species": "메타그로스", "pct": 25}, {"species": "피카츄", "pct": 8}], "pokemon": [
        {"id": 901, "name": "꼬부기", "species": "꼬부기", "num": 7, "level": 12, "shiny": False, "onDesktop": True,
         "kg": 9.0, "types": ["물"], "stars": 5, "hints": ["물 특기", "오늘 응원 타입!"], "away": False, "alsoIn": [],
         "entered": False},
        {"id": 900, "name": "피카츄", "species": "피카츄", "num": 25, "level": 30, "shiny": False, "onDesktop": True,
         "kg": 6.0, "types": ["전기"], "stars": 2, "hints": ["너무 가벼움"], "away": False, "alsoIn": ["100m"],
         "entered": False}]}
    e = UO.EntryWindow(app, "bobsled", w)
    pump(root, lambda: e.rows, 2)
    eb = texts_of(e.win)
    chk("신청 창: 후보 줄 · 지금 몫(지침) · 다른 종목에도 나감", len(e.rows) == 2 and "메타그로스 25%" in eb
        and "100m에도 나가요" in eb, eb[:300])
    chk("다른 종목에 나가는 포켓몬도 고를 수 있다 (하루 한 종목 - 11/08)", bool(e.rows[900].bind("<Button-1>")))
    app.api.cands = dict(many_cands(40), share=[], total=0)
    big = UO.EntryWindow(app, "bobsled", w)
    pump(root, lambda: len(big.rows) == 40, 3)
    settle(root, 0.3)
    big._choose(2005)
    settle(root, 0.3)
    chk("신청 창(40마리): 신청 단추가 창 안에 보인다", inside(big.win, big.go.holder),
        (big.win.winfo_height(), big.go.holder.winfo_ismapped()))
    chk("신청 창(40마리): 작전 단추도 보인다", inside(big.win, big.tac_btns["bold"]))
    chk("신청 창(40마리): 창은 화면 안 높이", big.win.winfo_height() <= U.h(700) + 4, big.win.winfo_height())
    big.close()
    e._choose(900)
    e._tac("bold")
    e._go()
    pump(root, lambda: not e.alive(), 2)
    chk("신청: 고른 포켓몬 · 작전으로 보낸다", ("enter", "bobsled", 900, "bold") in app.api.calls, app.api.calls[-3:])
    chk("신청 뒤 창이 닫히고 동기화", not e.alive() and app.syncs >= 1)
    # 결과 창
    me = {"rank": 12, "user": "나", "mine": True, "entryId": 7, "pokemon": {"name": "피카츄"}, "text": "11.84초",
          "reached": "준결승"}
    heats = [{"no": k, "match": None, "rows": [{"place": i + 1, "entryId": 10 * k + i, "user": "사람%d" % i,
                                                 "mine": k == 1 and i == 0, "pokemon": {"name": "라이츄"},
                                                 "text": "%.2f초" % (11.2 + i * 0.1),
                                                 "q": "Q" if i < 3 else ("q" if i == 3 else None)} for i in range(8)]}
             for k in (1, 2)]
    app.api.board = {"event": "sprint", "kr": "100m 달리기", "total": 120, "hidden": False,
                     "rounds": [{"no": 1, "key": "r1", "kr": "예선", "format": "race",
                                 "note": "조 상위 3명 + 기록 2명 준결승", "heats": heats}],
                     "standings": [{"rank": 1, "user": "가", "mine": False, "entryId": 5,
                                    "pokemon": {"name": "라이츄"}, "text": "11.20초", "reached": "결승"}], "me": me}
    b = UO.BoardWindow(app, "sprint")
    pump(root, lambda: b.inner.winfo_children(), 2)
    chk("결과 창: 라운드 탭 + 최종 순위 탭 · 처음엔 최종 순위 (1위 + ⋯ + 내 줄)", set(b.tabs) == {1, "final"}
        and len(b.inner.winfo_children()) == 3 and b.view == "final", (list(b.tabs), len(b.inner.winfo_children())))
    b._tab(1)
    settle(root, 0.2)
    rb = texts_of(b.inner)
    chk("결과 창: 예선 조마다 줄 · Q / q · 다시 보기", "1조" in rb and "2조" in rb and "Q" in rb and " q" in rb
        and "다시 보기" in rb and "조 상위 3명" in b.note.cget("text"), rb[:200])
    b.close()
    rows50 = [{"rank": i + 1, "user": "사람%d" % i, "mine": False, "entryId": 5 + i, "pokemon": {"name": "라이츄"},
               "text": "%.2f초" % (11.2 + i * 0.05), "reached": "예선"} for i in range(50)]
    app.api.board = {"event": "sprint", "total": 120, "hidden": False, "rounds": [], "standings": rows50, "me": None}
    b50 = UO.BoardWindow(app, "sprint")
    pump(root, lambda: len(b50.inner.winfo_children()) == 50, 3)
    settle(root, 0.3)
    chk("결과 창(50줄): 닫기 단추가 창 안에 보인다", inside(b50.win, b50.close_btn.holder), b50.win.winfo_height())
    b50.close()
    app.api.board = {"event": "ski", "total": 30, "hidden": True, "rounds": [], "standings": [], "me": None}
    bh = UO.BoardWindow(app, "ski")
    pump(root, lambda: "공개" in bh.note.cget("text"), 2)
    chk("결과 창: 공개 전 안내", "공개되지" in bh.note.cget("text"), bh.note.cget("text"))
    bh.close()
    holder.destroy()
    # 오른쪽 클릭 줄
    app.olympics.card = {"phase": "entry"}
    pet = next(iter(ov.pets.values()))
    row = UO.menu_row(app, pet)
    chk("오른쪽 클릭: '올림픽에 출전...'", row and row["text"] == "올림픽에 출전...", row)
    app.olympics.card = {"phase": "closed"}
    chk("기간 밖이면 줄이 없다", UO.menu_row(app, pet) is None)
    app.olympics.card = None
    # 리본 글
    chk("관리 창 리본: 가장 귀한 것과 개수",
        ui_box.ribbon_text({"ribbons": [{"kind": "oly_join", "name": "올림픽 참가 리본"},
                                        {"kind": "oly_gold", "name": "100m 금메달 리본"}]}) == "리본 2개 · 100m 금메달 리본")
    chk("리본 없으면 빈 글", ui_box.ribbon_text({}) == "")


def o_busy(app):
    return app.olympics.busy()


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-500:])
    root.report_callback_exception = on_err
    colors = [(230, 110, 40, 255), (80, 140, 220, 255), (60, 160, 90, 255), (200, 80, 160, 255),
              (220, 200, 60, 255), (120, 120, 200, 255)]
    for n in range(1, 7):
        SHEETS[n] = make_sheet("s%d.png" % n, 32, colors[n - 1])
        FILES[n] = make_dot("d%d.png" % n, colors[n - 1])
    poses = dict(((n, a), make_sheet("p%d_%s.png" % (n, a), 32, (240, 240, 240, 255)))
                 for n in (1, 2, 3) for a in ("Idle", "Hop", "Hurt"))
    sprite_cache.ensure = lambda api, num, shiny=False: FILES.get(num)
    walk_cache.ensure = lambda api, num, name="Walk", shiny=False: (
        SHEETS.get(num) if name == "Walk" and SHEETS.get(num) else poses.get((num, name), (None, None)))
    settings = dict(config.DEFAULTS)
    settings["megaWalk"] = []
    settings["showNames"] = True
    ov = overlay.Overlay(root, settings)
    ov.paths.update(dict(((n, False), p) for n, p in FILES.items()))
    ov.walks.update(dict(SHEETS))
    for (n, a), v in poses.items():
        ov.sheets[walk_cache.sheet_key(n, a, T.skin({}))] = v
    ov.sync([mon(1, 4 if 4 in SHEETS else 1, 0, "파이리"), mon(2, 2, 1, "꼬부기")], {}, {})
    ov.start()
    settle(root, 0.3)
    app = MiniApp(root, ov)
    try:
        script_part()
        race_part(root, ov, app)
        field_part(root, ov, app)
        budget_part(root, ov, app)
        cheer_part(root, ov, app)
        live_part(root, ov, app)
        guard_part(root, ov, app)
        window_part(root, ov, app)
    finally:
        app.olympics.clear()
        ov.stop()
        ov.clear()
        settle(root, 0.2)
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
