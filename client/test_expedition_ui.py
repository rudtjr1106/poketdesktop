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
  7. **쉬기 (1.10.5)**: 다녀온 포켓몬은 목록 아래쪽에 흐리게 서고 남은 시간이 적힌다. 골라도 못 보낸다.
     시간이 지나면 제자리로 올라온다.
  8. **성장 (1.10.5)**: 줄에 탐험 레벨이 보이고, 찍을 점수가 남았으면 표가 난다. [성장] 창에서 넣었다
     뺐다 하다가 [찍기] 를 눌러야 서버에 간다. 발걸음을 찍으면 걸리는 시간이 그 자리에서 줄어 보인다.
     되돌리기는 되묻고, 돈이 든다. 창은 내용만큼만 크다.
  9. 줄은 두 줄이다: 허브를 가장 좁게 줄여도 예상 성공도와 탐험 레벨이 줄 밖으로 안 나간다.
 10. **친화력 (1.10.5)**: 찍으면 보내기 줄에 데려올 확률이 적히고, 데려온 포켓몬은 받은 창에 물건보다
     먼저 적힌다. 포켓몬이 늘었으니 목록을 새로 받는다.
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
        self.grow = {}           # 포켓몬 id -> {"xp", "stats", "rest_until"(초), "runs"}  (1.10.5)
        self.money = 0
        self.friend_next = None  # 다음에 받을 때 데려올 포켓몬의 도감 번호 (친화력), "full" 이면 자리가 없다
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
                "items": X.item_count(o["hours"], o["grade"]), "left": max(0, left), "total": o["took"],
                "ready": left <= 0}

    def _grow_view(self, pid):
        g = self.grow.get(pid) or {"xp": 0, "stats": dict((k, 0) for k in X.STATS), "rest_until": 0, "runs": 0}
        lv, into, need = X.level_of(g["xp"])
        return {"xp": g["xp"], "level": lv, "into": into, "need": need, "stats": dict(g["stats"]),
                "free": X.free_points(g["xp"], g["stats"]), "rest": max(0, int(g["rest_until"] - self.now)),
                "runs": g["runs"]}

    def _grow_row(self, pid):
        return self.grow.setdefault(pid, {"xp": 0, "stats": dict((k, 0) for k in X.STATS), "rest_until": 0, "runs": 0})

    def expedition(self):
        self.calls.append("expedition")
        out = [self._view(o) for o in self.out]
        wait = [v["left"] for v in out if not v["ready"]]
        return {"slots": X.SLOTS, "hours": list(X.HOURS), "out": out, "free": X.SLOTS - len(out),
                "ready": sum(1 for v in out if v["ready"]), "nextIn": min(wait) if wait else None,
                "growth": dict((str(pid), self._grow_view(pid)) for pid in self.grow)}

    def expedition_grow(self, pid, add):
        self.calls.append(("grow", pid, dict(add)))
        if any(o["pid"] == pid for o in self.out):
            raise ApiError("탐험에 나가 있는 동안에는 성장치를 찍을 수 없습니다.")
        g = self._grow_row(pid)
        if sum(add.values()) > X.free_points(g["xp"], g["stats"]):
            raise ApiError("남은 성장치가 모자랍니다.")
        for k, v in add.items():
            g["stats"][k] += v
        return dict(self.expedition(), ok=True, message="성장치를 %d점 찍었습니다." % sum(add.values()))

    def expedition_reset(self, pid):
        self.calls.append(("reset", pid))
        g = self._grow_row(pid)
        if self.money < X.RESET_COST:
            raise ApiError("돈이 모자랍니다 (%s원)." % format(X.RESET_COST, ","))
        self.money -= X.RESET_COST
        g["stats"] = dict((k, 0) for k in X.STATS)
        return dict(self.expedition(), ok=True, money=self.money, message="성장치를 되돌렸습니다. 다시 찍을 수 있습니다.")

    def expedition_send(self, pid, place, hours):
        self.calls.append(("send", pid, place, hours))
        if len(self.out) >= X.SLOTS:
            raise ApiError("탐험 칸이 꽉 찼습니다 (3칸). 돌아온 보따리를 먼저 받아 주세요.")
        m = self._mon(pid)
        if m.get("onDesktop"):
            raise ApiError("데리고 다니는 포켓몬은 보낼 수 없습니다. 먼저 박스에 넣어 주세요.")
        g = self._grow_view(pid)
        if g["rest"] > 0:
            raise ApiError("아직 쉬는 중입니다. %s 뒤에 다시 나갈 수 있습니다." % X.hours_text(g["rest"]))
        pts = X.score(m["level"], self.dex.get(m["species"])["types"], place)
        took = X.duration(hours, g["stats"]["speed"])
        self.seq += 1
        self.out.append({"id": self.seq, "pid": pid, "place": place, "hours": hours, "grade": X.grade(pts),
                         "score": pts, "ends": self.now + took, "took": took})
        return dict(self.expedition(), ok=True, message="%s을(를) %s(으)로 보냈습니다. %s 뒤에 돌아옵니다."
                    % (m["info"]["name"], X.place(place)["kr"], X.time_text(took)))

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
            # 경험치를 주고 쉬게 한다 (돌아온 때부터 24시간)
            g = self._grow_row(o["pid"])
            lv0 = X.level_of(g["xp"])[0]
            gain = min(X.XP_MAX, g["xp"] + X.xp_for(o["hours"], o["grade"])) - g["xp"]
            g["xp"] += gain
            g["runs"] += 1
            g["rest_until"] = o["ends"] + X.REST_HOURS * 3600
            gv = self._grow_view(o["pid"])
            friend, full = None, False
            if self.friend_next == "full":
                full = True
            elif self.friend_next:
                # 서버처럼: 새 포켓몬이 박스에 들어가고, 받은 답에 실린다
                new_id = max(m["id"] for m in self.mons) + 1
                nm = SB.mon(self.dex, self.friend_next, new_id, on=False)
                nm["level"] = 37
                nm["info"]["level"] = 37
                nm["box"] = 0
                self.mons.append(nm)
                sp = self.dex.get(nm["species"])
                friend = {"id": new_id, "name": nm["info"]["name"], "species": nm["species"], "num": nm["num"],
                          "level": 37, "shiny": False, "types": list(sp["types"]), "new": True}
            self.friend_next = None
            got.append({"id": o["id"], "pokemon": v["pokemon"], "place": o["place"], "placeKr": v["placeKr"],
                        "hours": o["hours"], "grade": o["grade"], "gradeKr": v["gradeKr"],
                        "items": [dict(i) for i in self.loot], "tm": dict(self.tm) if o["place"] == "ruins" else None,
                        "bonus": 0, "growth": {"xp": gain, "levelBefore": lv0, "level": gv["level"], "into": gv["into"],
                                               "need": gv["need"], "free": gv["free"], "rest": gv["rest"]},
                        "friend": friend, "friendFull": full})
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
    # 쉬기와 성장 (1.10.5): 쉬는 포켓몬은 아래로, 데리고 다니는 포켓몬은 다녀온 적이 있을 때만 맨 아래에
    top3 = [rows[i][0]["id"] for i in range(3)]
    lead = next(m for m in api.pokemon() if m.get("onDesktop"))
    lead2 = [m for m in api.pokemon() if m.get("onDesktop")][1]
    gr = {str(top3[0]): {"rest": 7200, "xp": 120}, str(top3[1]): {"rest": 60, "xp": 20}, str(top3[2]): {"rest": 0, "xp": 500},
          str(lead["id"]): {"rest": 0, "xp": 100}, str(lead2["id"]): {"rest": 0, "xp": 0}}
    got = UE.candidates(api.pokemon(), dex, "forest", gr)
    ids = [m["id"] for m, _p, _g in got]
    chk("**쉬는 포켓몬은 보낼 수 있는 것들 아래에 선다** (곧 끝나는 것부터)", ids[0] == top3[2] and ids[-3:-1] == [top3[1], top3[0]]
        and len(got) == 301, (ids[:2], ids[-3:]))
    chk("  데리고 다니는 포켓몬은 탐험을 다녀온 적이 있는 것만 맨 아래에 선다 (성장치를 찍을 수 있게)",
        ids[-1] == lead["id"] and lead2["id"] not in ids, ids[-2:])
    chk("  줄에 적는 탐험 레벨: 찍을 점수가 남았으면 표가 난다",
        [UE.grow_text(g_) for g_ in ({}, {"level": 3, "free": 0}, {"level": 3, "free": 2}, {"level": 10, "free": 10})]
        == ["탐험 Lv.0", "탐험 Lv.3", "탐험 Lv.3 ● 2점", "탐험 Lv.10 ● 10점"], UE.grow_text({"level": 3, "free": 2}))
    note = XU.growth_note({"bonus": 1, "growth": {"xp": 120, "levelBefore": 1, "level": 2, "into": 0, "need": 180,
                                                 "free": 1, "rest": 82800}})
    chk("받은 것 아래에 적을 성장: 경험치 · 레벨이 올랐다 · 더 주워 온 것 · 쉬는 시간",
        note == ("탐험 경험치 +120 · 탐험 Lv.1 → Lv.2 (성장치 +1점)", "주머니 덕에 1개를 더 주워 왔습니다 · 23시간 동안 쉽니다", True)
        and XU.growth_note({"growth": {"xp": 20, "levelBefore": 0, "level": 0, "into": 20, "need": 100, "rest": 0}})
        == ("탐험 경험치 +20 · 탐험 Lv.0 (다음 레벨까지 80)", "", False)
        and XU.growth_note({"growth": {"xp": 0, "levelBefore": 10, "level": 10, "into": 0, "need": None, "rest": 60}})
        == ("탐험 Lv.10 (가장 높은 레벨)", "1분 동안 쉽니다", False) and XU.growth_note({}) is None, note)
    chk("친화력으로 데려온 포켓몬을 한 줄로: 이름·레벨, 처음이면 '도감에 새로 등록'",
        XU.friend_line({"friend": {"name": "꼬부기", "level": 37, "new": True}}) == ("Lv.37 꼬부기를 데려왔습니다!", "도감에 새로 등록")
        and XU.friend_line({"friend": {"name": "잉어킹", "level": 5, "new": False, "shiny": True}})
        == ("Lv.5 ★ 잉어킹을 데려왔습니다!", "새 포켓몬")
        and XU.friend_line({"friend": None, "friendFull": True})[1] is None
        and "가득 차서" in XU.friend_line({"friendFull": True})[0] and XU.friend_line({"friend": None}) is None
        and XU.friend_line({}) is None, XU.friend_line({"friend": {"name": "꼬부기", "level": 37, "new": True}}))
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
    # 보이는 줄 수는 보통 글자 크기 기준이다. 글자를 키우면 줄이 높아져 한 화면에 덜 보인다 (나머지는 굴려서 본다)
    rows_min = 6 if U.TEXT_SIZE == 0 else 3
    rows_narrow = 4 if U.TEXT_SIZE == 0 else 3          # 가장 낮은 창에서
    chk("  위에서부터 잘할 차례로: 이름 · 레벨 · 예상 성공도 · 탐험 레벨 (%d줄이 보인다)" % len(first),
        len(first) >= rows_min and [pid for pid, _r in first][:5] == [m["id"] for m, _p, _g in want[:len(first[:5])]]
        and first[0][1].lv.cget("text") == "Lv.%d" % want[0][0]["level"]
        and first[0][1].grade.cget("text") == X.GRADE_KR[want[0][2]]
        and first[0][1].grow.cget("text") == "탐험 Lv.0",
        (len(first), first[0][1].lv.cget("text"), first[0][1].grade.cget("text"), first[0][1].grow.cget("text")))

    def row_trouble():
        """보이는 줄마다: 글이 줄 밖으로 나가거나 서로 겹치면 적는다 (place 로 놓은 글은 '눌림' 으로 안 잡힌다)."""
        bad = []
        for _pid, r in w.shown():
            bw, bh = r.body.winfo_width(), r.body.winfo_height()
            bx = r.body.winfo_rootx()
            for x in (r.name, r.lv, r.grade, r.grow, r.types):
                x0 = x.winfo_rootx() - bx
                if x.winfo_height() < x.winfo_reqheight() or x.winfo_width() < x.winfo_reqwidth() or x0 < 0 \
                        or x0 + x.winfo_width() > bw or x.winfo_y() < 0 and x is not r.lv \
                        or x is not r.lv and x.winfo_y() + x.winfo_height() > bh:
                    bad.append(("칸 밖", x.cget("text") if x is not r.types else "타입", x0, x.winfo_width(), bw))
            if r.lv.winfo_rootx() + r.lv.winfo_width() > r.grade.winfo_rootx() - 4:
                bad.append(("윗줄 겹침", r.name.cget("text"), r.grade.cget("text")))
            if r.types.winfo_rootx() + r.types.winfo_reqwidth() > r.grow.winfo_rootx() - 4:
                bad.append(("아랫줄 겹침", r.name.cget("text"), r.grow.cget("text")))
            if r.name.winfo_y() + r.name.winfo_height() > r.types.winfo_y() + 1:
                bad.append(("두 줄이 겹침", r.name.cget("text")))
        return bad
    chk("  줄마다 글이 줄 안에 있고 서로 안 겹친다", not row_trouble(), row_trouble()[:4])
    chk("  맨 위의 포켓몬이 골라져 있고, 아래에 한 줄로 요약한다", w.pick == want[0][0]["id"] and [p for p, r in first if r.selected] == [w.pick]
        and "예상" in w.summary.cget("text") and X.place(w.place)["kr"] in w.summary.cget("text"), w.summary.cget("text"))
    def cols_bad():
        """세 단의 눌린 위젯. 왼쪽·가운데 단은 굴러가는 칸이라 squeezed 가 안 보므로 그 안쪽도 따로 본다."""
        return squeezed(w.body) + squeezed(w.slot_col.inner) + squeezed(w.mid_col.inner)

    def cards_seen():
        """탐험 칸 셋이 다 보이나. 글자를 키우면(1·2) 낮은 창에는 다 안 들어가므로 단 안에서 굴려서 닿으면 된다
        (막대가 보이고, 굴리는 범위가 마지막 칸의 끝까지 닿는다). 보통 크기는 굴리지 않고 셋이 다 보여야 한다."""
        last = w.cards[-1]
        if last.winfo_rooty() + last.winfo_height() <= w.body.winfo_rooty() + w.body.winfo_height():
            return True
        if U.TEXT_SIZE == 0:
            return False
        region = [float(v) for v in str(w.slot_col.cv.cget("scrollregion")).split()]
        return bool(w.slot_col.bar.winfo_ismapped()) and len(region) == 4 \
            and region[3] >= last.winfo_y() + last.winfo_height()
    bad = cols_bad()
    chk("  세 단(탐험 칸 · 어디로 · 누구를)에 눌린 위젯 없음", not bad, bad[:3])
    cards = [c.winfo_height() for c in w.cards]
    chk("  탐험 칸 셋이 다 제 높이로 보인다", min(cards) >= UE.CARD_H - 1 and cards_seen(), cards)
    # 허브 창을 가장 작게 줄였을 때 (980 x 620 - 탭 줄을 빼면 본문은 더 낮다)
    top.geometry("980x%d" % (620 - U.h(30)))
    rest(root, 0.4)
    bad = cols_bad()
    cards = [c.winfo_height() for c in w.cards]
    chk("**창을 가장 작게 줄여도** 세 단에 눌린 것이 없고 칸 셋이 다 보인다 (목록 %d줄)" % len(w.shown()),
        not bad and min(cards) >= UE.CARD_H - 1 and len(w.shown()) >= rows_narrow
        and cards_seen(), (bad[:3], cards, len(w.shown())))
    # (1.10.4 에서는 한 줄에 다섯 칸이라 여기서 '예상' 과 '물건' 이 창 밖으로 나가 있었다)
    chk("  **가장 좁은 창에서도 예상 성공도와 탐험 레벨이 줄 안에 있다**", not row_trouble(), row_trouble()[:4])
    hb = w.reload_btn.holder
    chk("  머리줄의 새로고침 단추가 눌리지 않는다 (윈도우에서 4px 눌려 있었다)", hb.winfo_height() >= hb.winfo_reqheight(),
        (hb.winfo_height(), hb.winfo_reqheight()))
    top.geometry("1020x664")
    rest(root, 0.4)

    print("\n=== 곳·시간을 바꾼다 ===")
    w.set_place("volcano")
    rest(root, 0.15)
    want = UE.candidates(api.pokemon(), dex, "volcano")
    first = w.shown()
    chk("곳을 바꾸면 그곳에서 잘할 차례로 다시 선다 (맨 위로 돌아간다)",
        [pid for pid, _r in first][:5] == [m["id"] for m, _p, _g in want[:len(first[:5])]] and len(first) >= rows_min
        and w.vl.canvas.yview()[0] == 0.0 and w.pick == want[0][0]["id"]
        and X.place("volcano")["hint"] in texts(w.win), [pid for pid, _r in first][:3])
    good = set(X.place("volcano")["types"])
    row = first[0][1]
    lit = [c.cget("text") for c in row.chips if c.winfo_manager() and c.cget("bg") != U.BG3]
    chk("  그곳과 맞는 타입만 제 색이다 (왜 그 성공도인지 보인다)",
        lit == [dex.type_name(t) for t in dex.get(want[0][0]["species"])["types"] if t in good], lit)
    w.set_hours(8)
    rest(root, 0.1)
    picked = w._picked()
    chk("시간을 바꾸면 물건 수가 그 자리에서 바뀐다 (8시간)",
        "8시간" in w.summary.cget("text") and "물건 %d개" % X.item_count(8, picked[2]) in w.summary.cget("text")
        and "물건 %d ~ %d개" % (X.ITEMS[8][0], X.ITEMS[8][-1]) in w.hours_note.cget("text"),
        (w.summary.cget("text"), w.hours_note.cget("text")))
    w.vl.canvas.yview_moveto(1.0)
    rest(root, 0.15)
    tail = w.shown()
    chk("목록을 끝까지 굴려도 줄마다 제 포켓몬이다 (맨 아래 = 가장 못할 포켓몬)", tail[-1][0] == want[-1][0]["id"]
        and tail[-1][1].lv.cget("text") == "Lv.%d" % want[-1][0]["level"] and w.vl.made <= 26, (tail[-1][0], w.vl.made))
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

    shown_first = dict(shown)
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


    print("\n=== 쉬기 (1.10.5) ===")
    ids = [m["id"] for _k, (m, _p, _g) in w.vl.entries]
    g_b = w.growth_of(b_id)
    chk("받은 포켓몬은 경험치를 얻고 쉬기 시작한다 (2시간 = %d, 24시간)" % g_b["xp"],
        g_b["xp"] == X.xp_for(2, next(c for c in shown_first["claimed"] if c["pokemon"]["id"] == b_id)["grade"])
        and g_b["rest"] == 24 * 3600 and w.mon_state(next(m for m in w.mons if m["id"] == b_id)) == "rest", g_b)
    chk("**쉬는 포켓몬은 목록의 맨 아래에 선다**", ids[-1] == b_id and "쉬는 중 1" in w.pick_note.cget("text")
        and "보낼 수 있는 298마리" in w.pick_note.cget("text") and len(ids) == 299, (ids[-2:], w.pick_note.cget("text")))
    w.vl.see(len(ids) - 1)
    rest(root, 0.2)
    rrow = next(r for pid, r in w.shown() if pid == b_id)
    chk("  흐리게, '쉬는 중 · 24시간 뒤' 라고 적는다", rrow.grade.cget("text") == "쉬는 중" and rrow.grow.cget("text") == "24시간 뒤"
        and rrow.name.cget("fg") == U.FG_FAINT and all(c.cget("bg") == U.BG3 for c in rrow.chips if c.winfo_manager()),
        (rrow.grade.cget("text"), rrow.grow.cget("text")))
    chk("  쉬는 줄도 글이 줄 안에 있다", not row_trouble(), row_trouble()[:4])
    w.pick_mon(b_id)
    rest(root, 0.1)
    chk("골라도 못 보낸다: 까닭과 남은 시간을 적고 보내기가 잠긴다", "쉬는 중입니다" in w.summary.cget("text")
        and "24시간 뒤" in w.summary.cget("text") and not w.send_btn.enabled, w.summary.cget("text"))
    n_calls = len(api.calls)
    w.do_send()
    rest(root, 0.1)
    # 보내기만 센다. 화면이 스스로 하는 상태 조회("expedition")는 느린 CI 에서 그사이에 끼어들 수 있다.
    chk("  눌러도 서버에 안 간다", not [c for c in api.calls[n_calls:] if isinstance(c, tuple) and c[0] == "send"],
        api.calls[n_calls:])
    chk("  성장 단추는 열려 있다 (쉬는 동안에도 성장치는 찍을 수 있다)", w.grow_btn.enabled)
    chk("쉬는 포켓몬이 있으면 다시 칠할 예약이 걸린다", w._rest_job is not None)
    api.now += 23 * 3600
    w._t0 -= 23 * 3600
    w._rest_tick()
    rest(root, 0.15)
    rrow = next(r for pid, r in w.shown() if pid == b_id)
    chk("23시간 뒤: 남은 시간이 줄어 있다 (1시간 뒤)", rrow.grow.cget("text") == "1시간 뒤" and "1시간 뒤" in w.summary.cget("text"),
        rrow.grow.cget("text"))
    api.now += 3600
    w._t0 -= 3600
    w._rest_tick()
    rest(root, 0.15)
    ids = [m["id"] for _k, (m, _p, _g) in w.vl.entries]
    chk("**24시간이 지나면 제자리로 올라온다** (다시 보낼 수 있다)", w.mon_state(next(m for m in w.mons if m["id"] == b_id)) == "ok"
        and ids[-1] != b_id and "쉬는 중" not in w.pick_note.cget("text") and w.send_btn.enabled
        and "예상" in w.summary.cget("text"), (ids.index(b_id), w.pick_note.cget("text"), w.summary.cget("text")))

    print("\n=== 성장 (1.10.5) ===")
    api.grow[b_id]["xp"] = 100 + 140 + 180          # 탐험 Lv.3
    api.grow[b_id]["rest_until"] = 0
    w.apply(api.expedition())
    w.set_place("forest")
    w.set_hours(8)
    w.pick_mon(b_id)
    w.vl.see(w.vl.index(lambda _k, d: d[0]["id"] == b_id))
    rest(root, 0.2)
    grow_row = next(r for pid, r in w.shown() if pid == b_id)
    chk("줄에 탐험 레벨이 보이고, 찍을 점수가 남았으면 금빛으로 표가 난다", grow_row.grow.cget("text") == "탐험 Lv.3 ● 3점"
        and grow_row.grow.cget("fg") == U.ACCENT_TEXT, (grow_row.grow.cget("text"), grow_row.grow.cget("fg")))
    chk("  성장 단추에도 점이 붙는다", w.grow_btn.label.cget("text") == "성장 ●", w.grow_btn.label.cget("text"))
    chk("  점이 붙은 줄도 글이 줄 안에 있다", not row_trouble(), row_trouble()[:4])
    other_row = next(r for pid, r in w.shown() if pid != b_id)
    chk("  다녀온 적 없는 포켓몬은 '탐험 Lv.0' (흐리게)", other_row.grow.cget("text") == "탐험 Lv.0"
        and other_row.grow.cget("fg") == U.FG_FAINT, other_row.grow.cget("text"))
    b_name = next(m for m in api.mons if m["id"] == b_id)["info"]["name"]
    chk("  아직 안 찍었으면 8시간 그대로", "· 8시간\n" in w.summary.cget("text"), w.summary.cget("text"))

    w.open_grow()
    d = w.grow_dialog
    rest(root, 0.4)
    tx = texts(d.top)
    chk("**성장 창**: 누구의 · 탐험 레벨 · 경험치 · 남은 점수 · 성장치 넷", any(b_name in t for t in tx) and "탐험 Lv.3" in tx
        and "다음 레벨까지 0 / 220" in tx and "남은 성장치 3점" in tx and all(X.STAT_KR[k] in tx for k in X.STATS)
        and all(X.STAT_HINT[k] in tx for k in X.STATS) and "되돌리기 1,000원" in tx and "찍기" in tx, tx)
    size = (d.top.winfo_width(), d.top.winfo_height())
    chk("  창은 내용만큼만 크고 눌린 것이 없다 (%dx%d)" % size, not squeezed(d.top) and size[0] == UE.GROW_W
        and abs(size[1] - d.top.winfo_reqheight()) <= 4 and size[1] < d.top.winfo_screenheight() * 0.8,
        (size, d.top.winfo_reqheight(), squeezed(d.top)[:3]))
    cv, num, effect, minus, plus = d.rows["speed"]
    chk("  처음에는 [찍기]·[-]·되돌리기가 잠겨 있고 [+] 만 열려 있다", not d.ok_btn.enabled and not minus.enabled and plus.enabled
        and not d.reset_btn.enabled)
    chk("  [+] [-] 가 글자 하나 폭이다 (넓지 않다)", plus.holder.winfo_width() <= U.h(40) and minus.holder.winfo_width() <= U.h(40)
        and plus.label.winfo_width() >= plus.label.winfo_reqwidth(), plus.holder.winfo_width())
    n_calls = len(api.calls)
    # 성장치를 보낸 것만 센다 (찍기 · 되돌리기). 돌아올 때가 된 탐험이 있으면 화면이 1.2초 뒤 상태를 다시
    # 묻는데("expedition"), 느린 CI(맥 러너)에서는 그 조회가 여기 끼어들어 이 검사만 두 번 연달아 떨어졌다 (1.13.1).
    sent = lambda: [c for c in api.calls[n_calls:] if isinstance(c, tuple) and c[0] in ("grow", "reset")]  # noqa: E731
    d.bump("speed", 1)
    d.bump("speed", 1)
    d.bump("luck", 1)
    rest(root, 0.1)
    lit = lambda k: [d.rows[k][0].itemcget(i, "fill") for i in d.rows[k][0].find_all()]     # noqa: E731
    chk("**넣어 본다 (발걸음 2, 눈썰미 1)**: 서버에는 아직 안 간다", not sent() and num.cget("text") == "0 +2"
        and "남은 성장치 0점" in texts(d.top) and lit("speed")[:3] == [U.ACCENT_TEXT, U.ACCENT_TEXT, U.INK]
        and "탐험 시간 -5%" in effect.cget("text") and d.ok_btn.enabled and minus.enabled, (num.cget("text"), effect.cget("text")))
    chk("  점수를 다 넣으면 [+] 가 전부 잠긴다", not any(d.rows[k][4].enabled for k in X.STATS))
    d.bump("haul", 1)
    chk("  잠긴 [+] 는 눌러도 안 오른다", d.pending["haul"] == 0 and d.left() == 0)
    d.bump("luck", -1)
    d.bump("luck", -1)                               # (넣은 것보다 더는 못 뺀다)
    rest(root, 0.1)
    chk("  [-] 로 넣은 것을 도로 뺀다", d.pending == dict(dict((k, 0) for k in X.STATS), speed=2) and d.left() == 1
        and d.rows["luck"][1].cget("text") == "0" and all(d.rows[k][4].enabled for k in X.STATS), d.pending)
    chk("  넣었다 뺐다 해도 창에 눌린 것이 없다", not squeezed(d.top), squeezed(d.top)[:3])
    d.commit()
    pump(root, lambda: not d.busy and w.growth_of(b_id)["stats"]["speed"] == 2, 6)
    rest(root, 0.2)
    chk("**[찍기] 를 눌러야 서버에 간다** (넣은 것만)", ("grow", b_id, {"speed": 2}) in api.calls and d.pending["speed"] == 0
        and num.cget("text") == "2" and lit("speed")[:3] == [U.ACCENT, U.ACCENT, U.INK] and "남은 성장치 1점" in texts(d.top)
        and "찍었습니다" in d.status.cget("text") and not d.ok_btn.enabled and d.reset_btn.enabled,
        (api.calls[-2:], num.cget("text"), d.status.cget("text")))
    chk("  이미 찍은 점수는 [-] 로 못 뺀다 (되돌리기다)", not minus.enabled)
    grow_row = next(r for pid, r in w.shown() if pid == b_id)
    chk("  목록의 줄과 보내기 줄이 같이 바뀐다: 8시간이 7시간 36분", grow_row.grow.cget("text") == "탐험 Lv.3 ● 1점"
        and "7시간 36분" in w.summary.cget("text"), (grow_row.grow.cget("text"), w.summary.cget("text")))

    print("  -- 되돌리기")
    from poketdesktop import ui_box as UB
    real_confirm = UB.confirm
    asked = []
    UB.confirm = lambda parent, title, message, **kw: (asked.append(message), True)[1]
    try:
        d.reset()
        pump(root, lambda: not d.busy and d.status.cget("text").strip(), 6)
        rest(root, 0.1)
        chk("돈이 모자라면 까닭을 붉게 적고 그대로다", asked and "1,000원" in asked[0] and "돈이 모자랍니다" in d.status.cget("text")
            and d.status.cget("fg") == U.RED and w.growth_of(b_id)["stats"]["speed"] == 2, d.status.cget("text"))
        api.money = 2500
        d.reset()
        pump(root, lambda: not d.busy and w.growth_of(b_id)["stats"]["speed"] == 0, 6)
        rest(root, 0.2)
    finally:
        UB.confirm = real_confirm
    chk("**되묻고 나서 되돌린다**: 점수가 돌아오고 돈이 빠진다", len(asked) == 2 and "2점" in asked[1]
        and api.calls.count(("reset", b_id)) == 2 and w.growth_of(b_id)["free"] == 3 and app.money == 1500
        and "남은 성장치 3점" in texts(d.top) and num.cget("text") == "0" and not d.reset_btn.enabled,
        (asked[-1:], app.money, num.cget("text")))
    chk("  되돌리면 걸리는 시간도 8시간으로 돌아온다", "· 8시간\n" in w.summary.cget("text"), w.summary.cget("text"))
    d.bump("haul", 1)
    d.commit()
    pump(root, lambda: not d.busy and w.growth_of(b_id)["stats"]["haul"] == 1, 6)
    rest(root, 0.1)
    chk("주머니를 찍으면 보내기 줄에 더 가져올 확률이 적힌다 (셋째 줄)", w.summary.cget("text").count("\n") == 2
        and w.summary.cget("text").endswith("물건 하나 더 3%"), w.summary.cget("text"))
    d.bump("charm", 2)
    d.commit()
    pump(root, lambda: not d.busy and w.growth_of(b_id)["stats"].get("charm") == 2, 6)
    rest(root, 0.2)
    chk("**친화력을 찍으면 데려올 확률이 적힌다** (2점 = 12%)", ("grow", b_id, {"charm": 2}) in api.calls
        and w.summary.cget("text").endswith("물건 하나 더 3% · 포켓몬을 데려올 확률 12%")
        and "포켓몬을 데려올 확률 12%" in d.rows["charm"][2].cget("text") and X.STAT_HINT["charm"] in d.rows["charm"][2].cget("text"),
        (w.summary.cget("text"), d.rows["charm"][2].cget("text")))
    chk("  성장치는 다섯 가지다 (창에 다섯 줄, 눌린 것 없음)", len(d.rows) == 5 == len(X.STATS) and "친화력" in texts(d.top)
        and not squeezed(d.top) and abs(d.top.winfo_height() - d.top.winfo_reqheight()) <= 4
        and d.top.winfo_height() < d.top.winfo_screenheight() * 0.85,
        (len(d.rows), d.top.winfo_height(), d.top.winfo_reqheight(), squeezed(d.top)[:3]))
    foot_h = w.summary.master.winfo_height()
    chk("  요약이 세 줄이어도 보내기 줄에 다 들어간다 (줄이 그만큼 자란다)", not cols_bad()
        and w.summary.winfo_height() >= w.summary.winfo_reqheight(), (foot_h, w.summary.winfo_height(), w.summary.winfo_reqheight()))
    top.geometry("980x%d" % (620 - U.h(30)))
    rest(root, 0.5)
    chk("  **가장 좁은 창에서도** 요약이 잘리지 않고 목록이 네 줄 넘게 남는다", not cols_bad()
        and w.summary.winfo_height() >= w.summary.winfo_reqheight() and len(w.shown()) >= rows_narrow
        and w.send_btn.holder.winfo_height() >= w.send_btn.holder.winfo_reqheight(),
        (w.summary.winfo_height(), w.summary.winfo_reqheight(), len(w.shown()), cols_bad()[:3]))
    top.geometry("1020x664")
    rest(root, 0.4)
    d.close()
    rest(root, 0.1)
    chk("닫으면 창이 사라진다", w.grow_dialog is None and not d.alive)

    print("  -- 다 키운 포켓몬")
    api.grow[b_id] = {"xp": X.XP_MAX, "stats": dict(dict((k, 0) for k in X.STATS), speed=10), "rest_until": 0, "runs": 30}
    w.apply(api.expedition())
    w.pick_mon(b_id)
    w.open_grow()
    d = w.grow_dialog
    rest(root, 0.3)
    tx = texts(d.top)
    chk("Lv.10: 가장 높은 레벨이라고 적고, 다 찍었으면 [+] 가 잠긴다", "탐험 Lv.10" in tx and "가장 높은 레벨입니다" in tx
        and "남은 성장치 0점" in tx and not any(d.rows[k][4].enabled for k in X.STATS) and d.rows["speed"][1].cget("text") == "10"
        and "탐험 시간 -25%" in d.rows["speed"][2].cget("text"), tx[:6])
    chk("  창에 눌린 것이 없다", not squeezed(d.top), squeezed(d.top)[:3])
    chk("  발걸음 10점: 8시간이 6시간으로 보인다", "· 6시간\n" in w.summary.cget("text"), w.summary.cget("text"))
    d.close()
    w.do_send()
    pump(root, lambda: len(w.state["out"]) == 2 and not w.busy, 6)
    rest(root, 0.2)
    sent = next(o for o in w.state["out"] if o["pokemon"]["id"] == b_id)
    chk("  보내면 칸의 남은 시간도 6시간이다 (막대는 그 시간 기준)", sent["left"] == 6 * 3600 and sent["total"] == 6 * 3600
        and "6시간 남음" in texts(w.win), (sent["left"], [t for t in texts(w.win) if "남음" in t]))

    print("  -- 받은 것을 보여 주는 창에 성장이 적힌다")
    api.now += 6 * 3600
    seen = {}
    real_wait = root.wait_window

    def no_wait2(win):
        root.update()
        rest(root, 0.4)
        seen["texts"] = texts(win)
        seen["squeezed"] = squeezed(win)
        seen["size"] = (win.winfo_width(), win.winfo_height(), win.winfo_reqheight())
        win.destroy()
    root.wait_window = no_wait2
    try:
        got = api.expedition_claim(sent["id"])
        got["claimed"][0]["bonus"] = 2
        w.apply(got)
        XU.show_loot(root, app, got["claimed"])
    finally:
        root.wait_window = real_wait
    chk("경험치·탐험 레벨과 쉬는 시간, 주머니로 더 가져온 수", any("탐험 Lv.10 (가장 높은 레벨)" in t for t in seen["texts"])
        and any("24시간 동안 쉽니다" in t and "주머니 덕에 2개를 더" in t for t in seen["texts"]), seen["texts"])
    chk("  창은 내용만큼만 크고 눌린 것이 없다", not seen["squeezed"] and abs(seen["size"][1] - seen["size"][2]) <= 4,
        (seen["size"], seen["squeezed"][:3]))


    print("  -- 친화력: 포켓몬을 데려온다")
    api.grow[b_id]["rest_until"] = 0
    w.apply(api.expedition())
    w.set_place("sea")
    w.set_hours(2)
    w.pick_mon(b_id)
    w.do_send()
    pump(root, lambda: any(o["pokemon"]["id"] == b_id for o in w.state["out"]) and not w.busy, 6)
    api.now += 2 * 3600
    w._t0 -= 2 * 3600
    pump(root, lambda: False, 0.1)
    n_mons = len(api.mons)
    api.friend_next = 7                               # 꼬부기 (물) 를 데려온다
    seen2 = {}
    real_show2 = XU.show_loot

    def show2(parent, app_, claimed):
        real_wait = parent.wait_window

        def no_wait3(win):
            root.update()
            rest(root, 0.5)
            seen2["texts"] = texts(win)
            seen2["squeezed"] = squeezed(win)
            seen2["size"] = (win.winfo_width(), win.winfo_height(), win.winfo_reqheight())
            seen2["thumbs"] = [k for k in getattr(win, "keep", {}) if str(k).startswith("friend")]
            win.destroy()
        parent.wait_window = no_wait3
        try:
            real_show2(parent, app_, claimed)
        finally:
            parent.wait_window = real_wait
        seen2["claimed"] = claimed
    XU.show_loot = show2
    calls0 = len(api.calls)
    sea_id = next(o["id"] for o in w.state["out"] if o["pokemon"]["id"] == b_id)
    try:
        app.expedition.claim(sea_id)                   # (유적에 나간 것은 그대로 둔다 - 아래 검사가 쓴다)
        pump(root, lambda: "claimed" in seen2, 8)
        rest(root, 0.4)
    finally:
        XU.show_loot = real_show2
    fr = (seen2.get("claimed") or [{}])[0].get("friend") or {}
    fname = fr.get("name", "?")
    chk("**받은 창에 데려온 포켓몬이 적힌다** (물건보다 먼저, 처음이면 '도감에 새로 등록')",
        fr.get("num") == 7 and any(fname in t and "데려왔습니다!" in t and "Lv.37" in t for t in seen2["texts"])
        and "도감에 새로 등록" in seen2["texts"] and any("포켓몬 1마리를 데려왔습니다." in t for t in seen2["texts"])
        and [i for i, t in enumerate(seen2["texts"]) if "데려왔습니다!" in t][0] < seen2["texts"].index("오랭열매 × 2"),
        seen2.get("texts"))
    chk("  도트가 붙고, 창은 내용만큼만 크고 눌린 것이 없다", seen2["thumbs"] and not seen2["squeezed"]
        and abs(seen2["size"][1] - seen2["size"][2]) <= 4, (seen2["thumbs"], seen2["size"], seen2["squeezed"][:3]))
    pump(root, lambda: len(w.mons) == n_mons + 1 and w._wait is None, 6)
    rest(root, 0.2)
    chk("  **포켓몬이 늘었으니 목록을 새로 받는다** (데려온 포켓몬을 바로 보낼 수 있다)", len(api.mons) == n_mons + 1
        and len(w.mons) == n_mons + 1 and fr.get("id") in [m["id"] for _k, (m, _p, _g) in w.vl.entries],
        (len(w.mons), n_mons, api.calls[calls0:][-4:]))
    # 자리가 없어 못 데려왔을 때
    lines = []
    real_wait = root.wait_window

    def no_wait4(win):
        root.update()
        rest(root, 0.3)
        lines.extend(texts(win))
        lines.append(("squeezed", squeezed(win)))
        win.destroy()
    root.wait_window = no_wait4
    try:
        XU.show_loot(root, app, [dict(seen2["claimed"][0], friend=None, friendFull=True)])
    finally:
        root.wait_window = real_wait
    chk("  자리가 없어 못 데려왔으면 그렇다고 적는다", any(isinstance(t, str) and "가득 차서 데려오지 못했습니다" in t for t in lines)
        and ("squeezed", []) in lines and "새 포켓몬" not in lines, [t for t in lines if isinstance(t, str)][:6])

    print("  -- 데리고 다니는 포켓몬")
    lead = next(m for m in w.mons if m.get("onDesktop"))
    api.grow[lead["id"]] = {"xp": 100, "stats": dict((k, 0) for k in X.STATS), "rest_until": 0, "runs": 1}
    w.apply(api.expedition())
    ids = [m["id"] for _k, (m, _p, _g) in w.vl.entries]
    w.pick_mon(lead["id"])
    w.vl.see(len(ids) - 1)
    rest(root, 0.2)
    prow = next(r for pid, r in w.shown() if pid == lead["id"])
    chk("탐험을 다녀온 적 있는 포켓몬은 데리고 다녀도 맨 아래에 선다 (성장치를 찍을 수 있게)", ids[-1] == lead["id"]
        and prow.grade.cget("text") == "데리고 다니는 중" and prow.grow.cget("text") == "탐험 Lv.1 ● 1점", prow.grade.cget("text"))
    chk("  보낼 수는 없다 (박스에 넣으라고 알린다). 성장 단추는 열려 있다", "박스에 넣으면" in w.summary.cget("text")
        and not w.send_btn.enabled and w.grow_btn.enabled and w.grow_btn.label.cget("text") == "성장 ●", w.summary.cget("text"))
    chk("  그 줄도 글이 줄 안에 있다", not row_trouble(), row_trouble()[:4])
    top.geometry("980x%d" % (620 - U.h(30)))
    rest(root, 0.4)
    w.vl.see(len(ids) - 1)
    rest(root, 0.2)
    chk("  **가장 좁은 창에서도** 쉬는 줄·데리고 다니는 줄이 줄 안에 있다", not row_trouble() and not cols_bad(),
        (row_trouble()[:4], cols_bad()[:3]))
    top.geometry("1020x664")
    rest(root, 0.3)
    del api.grow[lead["id"]]
    w.apply(api.expedition())

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
