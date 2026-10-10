# -*- coding: utf-8 -*-
"""탐험 파견 화면 검사 (1.10.4).

    python client/test_expedition_ui.py

**창을 진짜로 띄운다.** 서버는 안 띄운다 - 가짜 api 가 server/app/expedition.py 와 같은 모양으로 답한다
(규칙은 서버와 같은 common/expedition.py 를 쓴다. 굴리기와 제한은 server/test_expedition.py 가 본다).

  1. 탐험 탭: 칸 셋, 갈 곳 여섯, 시간 셋, 박스의 포켓몬 목록 (잘할 차례로).
     데리고 다니는 포켓몬·알·이미 나간 포켓몬은 목록에 없다. 수백 마리여도 줄은 화면만큼만 만든다.
  2. 곳·시간을 바꾸면 예상 성공도와 물건 수가 그 자리에서 바뀐다 (보내기 전에 안다).
  3. 보내면 칸에 들어가고 목록에서 빠진다. 남은 시간이 흐른다. 칸이 꽉 차면 보내기가 잠긴다.
  4. 돌아오면 칸이 '돌아왔습니다' 로 바뀌고, **바탕화면에 보따리가 놓인다** (한 번만 알린다).
  5. 보따리를 누르면 받고, 받은 것을 보여 주는 창이 뜬다 (창은 내용만큼만 크다).
  6. 불러들이면 빈손이다. 포켓몬 관리 창에는 '탐험 중' 으로 뜨고 꺼내기·놓아주기가 막힌다.
"""
import io
import json
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-expedition-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from PIL import Image, ImageDraw                            # noqa: E402

from common import expedition as X                          # noqa: E402
from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
import smoke_box_filter as SB                               # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

OK = FAIL = 0
DATA = os.path.join(ROOT, "server", "data")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def png():
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((10, 8, 54, 60), fill=(90, 160, 230, 255))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


class ApiError(Exception):
    def __init__(self, message, status=409):
        Exception.__init__(self, message)
        self.message, self.status = message, status


class FakeApi(SB.FakeApi):
    """server/app/expedition.py 와 같은 모양으로 답한다. 시계는 검사가 돌린다 (self.now, 초)."""

    def __init__(self, dex, n_box=60):
        nums = [s["num"] for s in dex.species if not s.get("mega")][:150]
        mons = []
        for i in range(6 + n_box):
            m = SB.mon(dex, nums[(i * 7) % len(nums)], 1000 + i, on=(i < 6))
            m["level"] = 5 + (i * 13) % 96
            m["info"]["level"] = m["level"]
            if i >= 6:
                m["box"] = (i - 6) // 30
            mons.append(m)
        mons[9]["shiny"] = True
        SB.FakeApi.__init__(self, mons)
        self.dex = dex
        self.now = 0.0
        self.out = []            # {"id", "pid", "place", "hours", "grade", "score", "ends"}
        self.seq = 0
        self.png = png()
        self.bag = {}
        self.loot = [{"id": "ORANBERRY", "kr": "오랭열매", "count": 2, "tier": "common", "rarity": "common", "sell": 40},
                     {"id": "LEAFSTONE", "kr": "리프의돌", "count": 1, "tier": "rare", "rarity": "rare", "sell": 1500}]
        self.tm = {"no": 42, "kr": "냉동빔", "type": "ICE", "cat": "special", "label": "기술머신042 냉동빔"}

    # ---- 포켓몬
    def pokemon(self):
        away = set(o["pid"] for o in self.out)
        out = []
        for m in SB.FakeApi.pokemon(self):
            m = dict(m)
            if m["id"] in away:
                m["away"] = True
            else:
                m.pop("away", None)
            out.append(m)
        return out

    def sprite(self, num, shiny=False):
        return self.png, ".png"

    def item_sprite(self, item_id):
        return None

    def set_desktop(self, pid, on):
        if on and any(o["pid"] == pid for o in self.out):
            raise ApiError("탐험에 나가 있는 포켓몬입니다. 돌아온 뒤에 데리고 다닐 수 있습니다.")
        return SB.FakeApi.set_desktop(self, pid, on)

    # ---- 탐험
    def _mon(self, pid):
        return next(m for m in self.mons if m["id"] == pid)

    def _view(self, o):
        m = self._mon(o["pid"])
        sp = self.dex.get(m["species"])
        left = int(o["ends"] - self.now)
        return {"id": o["id"], "pokemon": {"id": m["id"], "name": m["info"]["name"], "species": m["species"],
                                           "num": m["num"], "level": m["level"], "shiny": bool(m.get("shiny")),
                                           "tint": None, "types": list(sp["types"])},
                "place": o["place"], "placeKr": X.place(o["place"])["kr"], "hours": o["hours"],
                "grade": o["grade"], "gradeKr": X.GRADE_KR[o["grade"]], "score": o["score"],
                "items": X.item_count(o["hours"], o["grade"]), "left": max(0, left), "total": o["hours"] * 3600,
                "ready": left <= 0}

    def expedition(self):
        self.calls.append("expedition")
        out = [self._view(o) for o in self.out]
        wait = [v["left"] for v in out if not v["ready"]]
        return {"slots": X.SLOTS, "hours": list(X.HOURS), "out": out, "free": X.SLOTS - len(out),
                "ready": sum(1 for v in out if v["ready"]), "nextIn": min(wait) if wait else None}

    def expedition_send(self, pid, place, hours):
        self.calls.append(("send", pid, place, hours))
        if len(self.out) >= X.SLOTS:
            raise ApiError("탐험 칸이 꽉 찼습니다 (3칸). 돌아온 보따리를 먼저 받아 주세요.")
        m = self._mon(pid)
        if m.get("onDesktop"):
            raise ApiError("데리고 다니는 포켓몬은 보낼 수 없습니다. 먼저 박스에 넣어 주세요.")
        pts = X.score(m["level"], self.dex.get(m["species"])["types"], place)
        self.seq += 1
        self.out.append({"id": self.seq, "pid": pid, "place": place, "hours": hours, "grade": X.grade(pts),
                         "score": pts, "ends": self.now + hours * 3600})
        return dict(self.expedition(), ok=True, message="%s을(를) %s(으)로 보냈습니다. %d시간 뒤에 돌아옵니다."
                    % (m["info"]["name"], X.place(place)["kr"], hours))

    def expedition_claim(self, eid=None):
        self.calls.append(("claim", eid))
        got = []
        for o in list(self.out):
            if eid is not None and o["id"] != eid:
                continue
            if o["ends"] > self.now:
                if eid is not None:
                    raise ApiError("아직 돌아오지 않았습니다.")
                continue
            v = self._view(o)
            self.out.remove(o)
            for it in self.loot:
                self.bag[it["id"]] = self.bag.get(it["id"], 0) + it["count"]
            got.append({"id": o["id"], "pokemon": v["pokemon"], "place": o["place"], "placeKr": v["placeKr"],
                        "hours": o["hours"], "grade": o["grade"], "gradeKr": v["gradeKr"],
                        "items": [dict(i) for i in self.loot], "tm": dict(self.tm) if o["place"] == "ruins" else None})
        return dict(self.expedition(), ok=True, claimed=got, bag=dict(self.bag), money=0, balls=5,
                    message="탐험에서 돌아왔습니다!" if got else "아직 돌아온 포켓몬이 없습니다.")

    def expedition_recall(self, eid):
        self.calls.append(("recall", eid))
        o = next((x for x in self.out if x["id"] == eid), None)
        if o is None:
            raise ApiError("그런 탐험이 없습니다.", 404)
        self.out.remove(o)
        return dict(self.expedition(), ok=True, message="불러들였습니다. 빈손으로 돌아왔습니다.")


class FakeOverlay(object):
    """바탕화면 도트 층에서 보따리가 쓰는 것만."""
    key = (254, 1, 254)

    def __init__(self, root):
        self.root = root
        self.settings = {"targetHeight": 48, "areaMargin": 8}

    def area(self):
        return (0, 0, 900, 600)


class FakeHub(object):
    def __init__(self):
        self.panes = {}
        self.badges = {}

    def set_badge(self, key, on):
        self.badges[key] = bool(on)


class FakeApp(object):
    def __init__(self, root, api, dex):
        self.root, self.api, self.dex = root, api, dex
        self.settings, self.balls, self.money = {}, 5, 0
        self.overlay = FakeOverlay(root)
        self.hub = FakeHub()
        self.box_window = None
        self.notes = []
        self.synced = 0
        self.expedition = None

    def notify(self, m):
        self.notes.append(m)

    def request_sync(self):
        self.synced += 1


def pump(root, cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return False


def rest(root, sec=0.3):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def widgets(w):
    n, stack = 0, [w]
    while stack:
        kids = stack.pop().winfo_children()
        n += len(kids)
        stack.extend(kids)
    return n


def find_button(win, text):
    """글자가 text 인 단추의 라벨 (PushButton·ghost_button 은 Label 로 그린다)."""
    stack = [win]
    while stack:
        w = stack.pop()
        try:
            if w.winfo_class() == "Label" and w.cget("text") == text and w.winfo_ismapped():
                return w
        except tk.TclError:
            pass
        stack.extend(w.winfo_children())
    return None


def click(root, w):
    w.event_generate("<Button-1>", x=3, y=3)
    w.event_generate("<ButtonRelease-1>", x=3, y=3)
    root.update()


def main():
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))

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
    print("글꼴 %s / 본문 %dpt" % (U.FAMILY, U.FONT[1]))

    from poketdesktop import expedition_ui as XU
    from poketdesktop import ui_expedition as UE

    print("=== 보낼 수 있는 포켓몬 (창 없이) ===")
    api = FakeApi(dex, 300)
    rows = UE.candidates(api.pokemon(), dex, "forest")
    chk("데리고 다니는 여섯은 빠진다 (박스의 300마리만)", len(rows) == 300 and all(not m.get("onDesktop") for m, _p, _g in rows))
    chk("그곳에서 잘할 차례로 선다 (점수 높은 것부터, 같으면 레벨 높은 것부터)",
        [p for _m, p, _g in rows] == sorted((p for _m, p, _g in rows), reverse=True)
        and all(a[1] > b[1] or a[0]["level"] >= b[0]["level"] for a, b in zip(rows, rows[1:])))
    m0, p0, g0 = rows[0]
    chk("  점수와 성공도는 서버와 같은 규칙이다", p0 == X.score(m0["level"], dex.get(m0["species"])["types"], "forest")
        and g0 == X.grade(p0), (p0, g0))
    egg = dict(rows[0][0], id=-5, isEgg=True)
    away = dict(rows[1][0], away=True)
    got = UE.candidates([egg, away, rows[2][0]], dex, "forest")
    chk("알과 이미 나가 있는 포켓몬은 빠진다", [m["id"] for m, _p, _g in got] == [rows[2][0]["id"]], [m["id"] for m, _p, _g in got])
    lines = XU.loot_lines([{"pokemon": {"name": "이상해꽃"}, "placeKr": "숲", "hours": 8, "grade": "great", "gradeKr": "대성공",
                            "items": api.loot, "tm": api.tm}])
    chk("받은 것을 글로: 머리줄 · 성공도 · 물건(개수) · 기술머신", lines == [("이상해꽃 · 숲 8시간", "great", "대성공", [
        ("ORANBERRY", "오랭열매", 2, "common"), ("LEAFSTONE", "리프의돌", 1, "rare"), (None, "기술머신042 냉동빔", 1, "tm")])], lines)

    print("\n=== 탐험 탭 ===")
    app = FakeApp(root, api, dex)
    app.expedition = XU.Desk(app)
    w = UE.ExpeditionWindow(app)
    app.hub.panes["expedition"] = w
    top = w.win.winfo_toplevel()
    top.deiconify()
    pump(root, lambda: w.state is not None and w._wait is None and w.vl.shown())
    rest(root, 0.3)
    tx = texts(w.win)
    chk("칸 셋이 비어 있다", tx.count("빈 칸") == X.SLOTS and "0 / 3 칸 사용 중" in tx, [t for t in tx if "칸" in t][:5])
    chk("갈 곳 여섯이 이름·맞는 타입과 함께 보인다", all(p["kr"] in tx for p in X.PLACES)
        and all(dex.type_name(t) in tx for p in X.PLACES for t in p["types"]), [p["kr"] for p in X.PLACES if p["kr"] not in tx])
    chk("  고른 곳에서 잘 나오는 것을 적는다", "%s에서 잘 나오는 것" % X.place(w.place)["kr"] in tx and X.place(w.place)["hint"] in tx,
        [t for t in tx if "나오는" in t])
    chk("시간 셋", all("%d시간" % h in tx for h in X.HOURS))
    chk("**박스의 300마리가 목록에 있는데 줄은 화면만큼만 만든다** (줄 %d개, 위젯 %d개)" % (w.vl.made, widgets(w.win)),
        len(w.vl.entries) == 300 and w.vl.made <= 24 and widgets(w.win) < 700, (len(w.vl.entries), w.vl.made, widgets(w.win)))
    first = w.shown()
    want = UE.candidates(api.pokemon(), dex, w.place)
    chk("  위에서부터 잘할 차례로: 이름 · 레벨 · 예상 성공도 · 물건 수 (%d줄이 보인다)" % len(first),
        len(first) >= 6 and [pid for pid, _r in first][:5] == [m["id"] for m, _p, _g in want[:5]]
        and first[0][1].lv.cget("text") == str(want[0][0]["level"])
        and first[0][1].grade.cget("text") == X.GRADE_KR[want[0][2]]
        and first[0][1].items.cget("text") == "%d개" % X.item_count(w.hours, want[0][2]),
        (len(first), first[0][1].grade.cget("text"), first[0][1].items.cget("text")))
    chk("  맨 위의 포켓몬이 골라져 있고, 아래에 한 줄로 요약한다", w.pick == want[0][0]["id"] and [p for p, r in first if r.selected] == [w.pick]
        and "예상" in w.summary.cget("text") and X.place(w.place)["kr"] in w.summary.cget("text"), w.summary.cget("text"))
    bad = squeezed(w.body)
    chk("  세 단(탐험 칸 · 어디로 · 누구를)에 눌린 위젯 없음", not bad, bad[:3])
    cards = [c.winfo_height() for c in w.cards]
    chk("  탐험 칸 셋이 다 제 높이로 보인다", min(cards) >= UE.CARD_H - 1
        and w.cards[-1].winfo_rooty() + cards[-1] <= w.body.winfo_rooty() + w.body.winfo_height(), cards)
    # 허브 창을 가장 작게 줄였을 때 (980 x 620 - 탭 줄을 빼면 본문은 더 낮다)
    top.geometry("980x%d" % (620 - U.h(30)))
    rest(root, 0.4)
    bad = squeezed(w.body)
    cards = [c.winfo_height() for c in w.cards]
    chk("**창을 가장 작게 줄여도** 세 단에 눌린 것이 없고 칸 셋이 다 보인다 (목록 %d줄)" % len(w.shown()),
        not bad and min(cards) >= UE.CARD_H - 1 and len(w.shown()) >= 4
        and w.cards[-1].winfo_rooty() + cards[-1] <= w.body.winfo_rooty() + w.body.winfo_height(), (bad[:3], cards, len(w.shown())))
    top.geometry("1020x664")
    rest(root, 0.4)

    print("\n=== 곳·시간을 바꾼다 ===")
    w.set_place("volcano")
    rest(root, 0.15)
    want = UE.candidates(api.pokemon(), dex, "volcano")
    first = w.shown()
    chk("곳을 바꾸면 그곳에서 잘할 차례로 다시 선다 (맨 위로 돌아간다)", [pid for pid, _r in first][:5] == [m["id"] for m, _p, _g in want[:5]]
        and w.vl.canvas.yview()[0] == 0.0 and w.pick == want[0][0]["id"]
        and X.place("volcano")["hint"] in texts(w.win), [pid for pid, _r in first][:3])
    good = set(X.place("volcano")["types"])
    row = first[0][1]
    lit = [c.cget("text") for c in row.chips if c.winfo_manager() and c.cget("bg") != U.BG3]
    chk("  그곳과 맞는 타입만 제 색이다 (왜 그 성공도인지 보인다)",
        lit == [dex.type_name(t) for t in dex.get(want[0][0]["species"])["types"] if t in good], lit)
    w.set_hours(8)
    rest(root, 0.1)
    chk("시간을 바꾸면 물건 수가 그 자리에서 바뀐다 (8시간)", all(
        r.items.cget("text") == "%d개" % X.item_count(8, r.data[2]) for _p, r in w.shown())
        and "8시간" in w.summary.cget("text")
        and "물건 %d ~ %d개" % (X.ITEMS[8][0], X.ITEMS[8][-1]) in w.hours_note.cget("text"), w.hours_note.cget("text"))
    w.vl.canvas.yview_moveto(1.0)
    rest(root, 0.15)
    tail = w.shown()
    chk("목록을 끝까지 굴려도 줄마다 제 포켓몬이다 (맨 아래 = 가장 못할 포켓몬)", tail[-1][0] == want[-1][0]["id"]
        and tail[-1][1].lv.cget("text") == str(want[-1][0]["level"]) and w.vl.made <= 26, (tail[-1][0], w.vl.made))
    w.vl.canvas.yview_moveto(0.0)
    rest(root, 0.1)

    print("\n=== 보낸다 ===")
    a_id = w.pick
    a_name = next(m for m in api.mons if m["id"] == a_id)["info"]["name"]
    w.do_send()
    pump(root, lambda: len((w.state or {}).get("out") or []) == 1 and not w.busy)
    rest(root, 0.2)
    tx = texts(w.win)
    chk("칸에 들어갔다: 이름 · 곳 · 시간 · 성공도 · 물건 수 · 남은 시간", ("send", a_id, "volcano", 8) in api.calls and "1 / 3 칸 사용 중" in tx
        and tx.count("빈 칸") == 2 and "화산 · 8시간" in tx and "8시간 남음" in tx and "불러들이기" in tx
        and any(a_name in t for t in tx), [t for t in tx if "화산" in t or "남음" in t])
    chk("  보낸 포켓몬은 목록에서 빠지고 다음 포켓몬이 골라진다", a_id not in [m["id"] for _k, (m, _p, _g) in w.vl.entries]
        and len(w.vl.entries) == 299 and w.pick not in (None, a_id), (len(w.vl.entries), w.pick))
    chk("  돌아올 때 다시 보도록 예약해 둔다 (바탕화면 쪽)", app.expedition._job is not None and app.expedition.ready == 0
        and app.expedition.bundle is None)
    w.set_place("forest")
    w.set_hours(2)
    rest(root, 0.1)
    b_id = w.pick
    w.do_send()
    pump(root, lambda: len(w.state["out"]) == 2 and not w.busy)
    w.set_place("ruins")
    w.set_hours(4)
    rest(root, 0.1)
    c_id = w.pick
    w.do_send()
    pump(root, lambda: len(w.state["out"]) == 3 and not w.busy)
    rest(root, 0.2)
    chk("세 칸을 다 쓰면 보내기가 잠기고 까닭을 적는다", "3 / 3 칸 사용 중" in texts(w.win) and "꽉 찼습니다" in w.summary.cget("text")
        and "빈 칸" not in texts(w.win), w.summary.cget("text"))
    n_calls = len(api.calls)
    w.do_send()
    rest(root, 0.1)
    chk("  잠긴 동안에는 눌러도 서버에 안 간다", len(api.calls) == n_calls or api.calls[-1][0] != "send", api.calls[-2:])

    print("\n=== 시간이 흐른다 ===")
    api.now += 3600
    w._t0 -= 3600                       # 화면의 시계도 한 시간 흐른 셈 친다
    w._tick()
    rest(root, 0.1)
    tx = texts(w.win)
    chk("한 시간 뒤: 남은 시간이 줄어 있다 (7시간 · 1시간 · 3시간)", "7시간 남음" in tx and "1시간 남음" in tx and "3시간 남음" in tx,
        [t for t in tx if "남음" in t])
    fills = [round(float(f.place_info().get("relwidth")), 3) for _o, _l, f in w.live]
    chk("  막대가 그만큼 찼다 (8시간짜리 1/8, 2시간짜리 1/2, 4시간짜리 1/4)", fills == [0.125, 0.5, 0.25], fills)
    api.now += 3600
    w._t0 -= 3600
    w._tick()
    pump(root, lambda: any(o.get("ready") for o in w.state["out"]), 6)
    rest(root, 0.3)
    tx = texts(w.win)
    chk("**두 시간 뒤: 숲에서 돌아왔다** (서버에 물어 확인한 뒤에 바뀐다)", "돌아왔습니다!" in tx and "보따리 받기" in tx
        and "돌아옴 1" in "".join(tx) and api.calls.count("expedition") >= 2, [t for t in tx if "돌아" in t])
    chk("  **바탕화면에 보따리가 놓인다**, 탭에 점이 찍힌다", app.expedition.bundle is not None and app.expedition.ready == 1
        and app.hub.badges.get("expedition") is True)
    b = app.expedition.bundle
    b.win.update_idletasks()
    chk("  보따리는 돌아다니는 곳의 왼쪽 아래에 놓인다", b.x == 18 and b.y == 600 - b.fh - 8 and b.fw > 30 and b.fh > 30, (b.x, b.y, b.fw, b.fh))
    chk("  한 번만 알린다", len([n for n in app.notes if "보따리" in n]) == 1, app.notes)
    app.expedition.note(api.expedition())
    app.expedition.note({"out": 3, "ready": 1, "nextIn": 7000})      # 동기화가 또 왔다
    chk("  동기화가 또 와도 다시 알리지 않고 보따리도 하나다", len([n for n in app.notes if "보따리" in n]) == 1
        and app.expedition.bundle is b)
    b.show_hint()
    root.update()
    chk("  올려 두면 무엇인지 알려 준다", b.hint is not None and "보따리" in texts(b.hint)[0], b.hint and texts(b.hint))
    b.hide_hint()

    print("\n=== 받는다 ===")
    shown = {}
    real_show = XU.show_loot

    def fake_show(parent, app_, claimed):
        # 진짜 창을 띄우되 기다리지 않게: 띄우자마자 재고 닫는다
        from poketdesktop import ui_box
        real_wait = parent.wait_window

        def no_wait(win):
            root.update()
            rest(root, 0.4)
            shown["texts"] = texts(win)
            shown["size"] = (win.winfo_width(), win.winfo_height())
            shown["need"] = win.winfo_reqheight()
            shown["squeezed"] = squeezed(win)
            shown["screen"] = win.winfo_screenheight()
            win.destroy()
        parent.wait_window = no_wait
        try:
            real_show(parent, app_, claimed)
        finally:
            parent.wait_window = real_wait
        shown["claimed"] = claimed
        del ui_box
    XU.show_loot = fake_show
    try:
        app.expedition.claim()                               # 바탕화면의 보따리를 눌렀다
        pump(root, lambda: "claimed" in shown, 8)
        rest(root, 0.3)
    finally:
        XU.show_loot = real_show
    chk("보따리를 누르면 돌아온 것을 전부 받는다", ("claim", None) in api.calls and len(shown.get("claimed") or []) == 1
        and shown["claimed"][0]["place"] == "forest", api.calls[-2:])
    st = shown.get("texts") or []
    chk("**받은 것을 보여 주는 창**: 누가 어디서 · 성공도 · 물건과 개수", "탐험에서 돌아왔습니다" in st and "오랭열매 × 2" in st
        and "리프의돌" in st and "가방에 넣어 두었습니다." in st and any("숲 2시간" in t for t in st) and "확인" in st, st)
    chk("  창은 내용만큼만 크고 눌린 것이 없다 (%dx%d)" % shown.get("size", (0, 0)), not shown.get("squeezed")
        and shown["size"][0] == XU.LOOT_W and abs(shown["size"][1] - shown["need"]) <= 4
        and shown["size"][1] < shown["screen"] * 0.7, (shown.get("size"), shown.get("need"), shown.get("squeezed")))
    chk("보따리가 치워지고 점이 꺼진다", app.expedition.bundle is None and app.expedition.ready == 0
        and app.hub.badges.get("expedition") is False)
    tx = texts(w.win)
    chk("  탭의 칸이 비고, 돌아온 포켓몬이 목록에 다시 들어온다", "2 / 3 칸 사용 중" in tx and tx.count("빈 칸") == 1
        and b_id in [m["id"] for _k, (m, _p, _g) in w.vl.entries] and len(w.vl.entries) == 298
        and c_id not in [m["id"] for _k, (m, _p, _g) in w.vl.entries], (len(w.vl.entries),))
    chk("  가방이 바뀌었으니 동기화를 부른다", app.synced >= 1)
    chk("  다시 보낼 수 있다", w.send_btn is not None and "꽉" not in w.summary.cget("text"))

    print("\n=== 긴 보따리: 창이 화면을 넘지 않는다 ===")
    many = [{"id": i, "pokemon": {"name": "포켓몬%d" % i}, "place": "ruins", "placeKr": "유적", "hours": 8, "grade": "great",
             "gradeKr": "대성공", "items": [dict(api.loot[0], id="ITEM%d" % k, kr="도구 %d" % k) for k in range(4)],
             "tm": api.tm} for i in range(9)]
    # 아주 드물게 나오는 지닌 도구 (맨 위 보따리에 하나)
    many[0]["items"].insert(0, {"id": "CHOICEBAND", "kr": "구애머리띠", "count": 1, "tier": "held", "rarity": "epic", "sell": 7500})
    shown.clear()
    real_wait = root.wait_window

    def no_wait(win):
        root.update()
        rest(root, 0.4)
        shown["size"] = (win.winfo_width(), win.winfo_height())
        shown["screen"] = win.winfo_screenheight()
        shown["texts"] = texts(win)
        cvs = [c for c in _walk(win) if c.winfo_class() == "Canvas"]
        shown["scroll"] = cvs[0].yview() if cvs else None
        shown["btn"] = find_button(win, "확인")
        shown["btn_ok"] = shown["btn"] is not None and shown["btn"].winfo_rooty() + shown["btn"].winfo_height() \
            <= win.winfo_rooty() + win.winfo_height()
        win.destroy()
    root.wait_window = no_wait
    try:
        XU.show_loot(root, app, many)
    finally:
        root.wait_window = real_wait
    chk("지닌 도구가 나오면 그렇다고 적는다 (구애머리띠 · 지닌 도구)", "구애머리띠" in shown["texts"] and "지닌 도구" in shown["texts"]
        and XU.TIER_KR["held"] == "지닌 도구" and XU.TIER_COLOR["held"] == U.ACCENT, shown["texts"][:8])
    chk("물건이 많으면 창을 키우는 대신 안쪽이 굴러간다 (창 높이 %d / 화면 %d)" % (shown["size"][1], shown["screen"]),
        shown["size"][1] <= shown["screen"] * 0.66 + 4 and shown["scroll"] is not None and shown["scroll"][1] < 0.999
        and shown["btn_ok"], (shown["size"], shown["scroll"], shown["btn_ok"]))

    print("\n=== 불러들인다 ===")
    from poketdesktop import ui_box
    real_confirm = ui_box.confirm
    asked = []
    ui_box.confirm = lambda parent, title, message, **kw: (asked.append(message), True)[1]
    try:
        o = w.state["out"][0]
        w.recall(o)
        pump(root, lambda: len(w.state["out"]) == 1, 6)
        rest(root, 0.2)
    finally:
        ui_box.confirm = real_confirm
    chk("되묻고 나서 불러들인다 (빈손이라고 알린다)", asked and "빈손" in asked[0] and ("recall", o["id"]) in api.calls
        and "1 / 3 칸 사용 중" in texts(w.win) and tx.count("빈 칸") + 1 == texts(w.win).count("빈 칸"), asked)
    chk("  돌아온 포켓몬이 목록에 다시 들어온다", a_id in [m["id"] for _k, (m, _p, _g) in w.vl.entries])

    print("\n=== 포켓몬 관리 창 ===")
    box_app = SB.FakeApp(root, dex, api.pokemon())
    bw = ui_box.BoxWindow(root, box_app)
    SB.settle_rows(root, bw)
    away_id = api.out[0]["pid"]
    bw.select(away_id)
    SB.settle_rows(root, bw)
    rest(root, 0.2)
    row = bw.rows.get(away_id)
    chk("나가 있는 포켓몬의 줄에는 '탐험 중' 이라고 적힌다", row is not None and row.cells[-1].cget("text") == "탐험 중"
        and bw.sel == away_id, row and row.cells[-1].cget("text"))
    chk("  꺼내기 단추가 '탐험 중' 으로 잠기고 놓아주기도 잠긴다", bw.btn_party.label.cget("text") == "탐험 중"
        and "탐험 중" in texts(bw.win), bw.btn_party.label.cget("text"))
    n = len(box_app.api.calls)
    bw.toggle_party()
    bw.do_release()
    rest(root, 0.1)
    chk("  눌러도 서버에 안 가고 까닭을 적는다", len(box_app.api.calls) == n and "탐험" in bw.status.cget("text"), bw.status.cget("text"))
    other = next(m["id"] for m in api.pokemon() if not m.get("onDesktop") and not m.get("away") and int(m.get("box") or 0) == bw.box_no)
    bw.select(other)
    rest(root, 0.1)
    chk("  다른 포켓몬은 그대로 꺼낼 수 있다", bw.btn_party.label.cget("text") == "데리고 다니기"
        and bw.rows[other].cells[-1].cget("text") == "박스", bw.btn_party.label.cget("text"))
    bw.close()

    w.close()
    app.expedition.clear()
    root.update()
    chk("닫으면 보따리와 예약이 남지 않는다", app.expedition.bundle is None and app.expedition._job is None)
    chk("도는 동안 오류 없음", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


def _walk(w):
    out, stack = [], [w]
    while stack:
        x = stack.pop()
        out.append(x)
        stack.extend(x.winfo_children())
    return out


if __name__ == "__main__":
    sys.exit(main())
