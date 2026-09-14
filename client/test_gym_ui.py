# -*- coding: utf-8 -*-
"""관장 탭과 관장 배틀 창 검사.

    python client/test_gym_ui.py

**창을 진짜로 띄운다.** 화면이 있어야 돌아간다(CI 의 맥·윈도우 잡).
서버는 안 띄운다 - 가짜 api 가 저장소의 gyms.json·korea_map.json 을 읽고,
배틀은 서버와 같은 엔진(common/trainer_battle)을 이 프로세스에서 돌린다.

## 무엇을 못 박나

  1. **배틀 장면이 창 밖으로 안 나간다.** 장면은 글꼴 배율(U.h)로 키웠는데
     창은 설계 크기 그대로여서, 맥에서 내 이름표·체력 숫자가 오른쪽 밖으로
     잘려 있었다.
  2. **교체 칸이 그림이 오기 전에도 제 크기다.** 빈 Label 의 width/height 는
     글자 수라서 칸이 화면을 다 먹고 이름·체력이 안 보였다.
  3. **결과의 '지도로 돌아가기' 가 안 눌린다.** 줄을 다 쌓고 붙였더니 남은
     높이만 받아 글자가 반쯤 잘렸다.
  4. 지도·트레이너 카드·기술 칸·교체 칸에 눌린 위젯이 없다.
  5. 휠로 키우고 끌어 옮긴다. **끌고 놓는 순간 그 자리를 고르지 않는다.**
  6. 한 판을 끝까지 두고(이기기·기권), 창을 닫으면 지도가 다시 불러온다.
  7. **전국 지도에서 서울을 누를 수 있다.** 고리가 바깥선뿐이라 경기도 도형이
     서울을 덮는데, 목록 순서대로 그렸더니 경기가 위에 올라가 서울이 안 눌렸다.
  8. 배틀 창이 독을 뺀 화면 안에 들어온다 (맥북에서 기술 칸 아랫줄이 독에 가렸다).
  9. 기술을 쓰면 연출이 돈다. 남은 포켓몬은 몬스터볼 그림으로 보인다.
 10. 이스터에그: 카드는 렌트라와 함께 선 그림, 배틀은 혼자 선 그림.
"""
import io
import json
import os
import sys
import tempfile
import time

os.environ.setdefault("POKET_HOME", os.path.join(tempfile.gettempdir(), "poket-test-gym"))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import random                                               # noqa: E402
import tkinter as tk                                        # noqa: E402

from PIL import Image, ImageDraw                            # noqa: E402

from common import pokelogic as P                           # noqa: E402
from common import trainer_battle as TB                     # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_gym                             # noqa: E402
from poketdesktop import ui_gym_battle as GB                # noqa: E402
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


def fake_sprite():
    """포켓몬 도트 대신 쓸 그림. 실제 도트처럼 가운데만 칠해진 RGBA."""
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((20, 14, 76, 90), fill=(90, 160, 230, 255))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


class FakeApi(object):
    """서버 대신. 응답 모양은 server/app/gym_routes.py 와 같다."""

    def __init__(self, dex, gyms, kmap, party):
        self.dex = dex
        self.gyms = gyms
        self.kmap = kmap
        self.by_region = {code: next(t for t in gyms["trainers"] if t["id"] == tid)
                          for code, tid in gyms["regions"].items()}
        self.cleared = set()
        self.party = party
        self.tb = None
        self.region = None
        self.rev = 0
        self.png = fake_sprite()
        self.calls = []

    def _public(self, t):
        return {"id": t["id"], "name": t["name"], "role": t["role"], "sprite": t["sprite"],
                "level": t["level"], "type": t["type"], "typeKr": self.dex.type_name(t["type"]),
                "region": t["region"], "why": t.get("why") or "",
                "cleared": t["region"] in self.cleared, "wins": 1 if t["region"] in self.cleared else 0,
                "bestTurns": 9 if t["region"] in self.cleared else None}

    def gym(self):
        self.calls.append("gym")
        act = {"id": 1, "region": self.region} if self.tb and not self.tb.over else None
        return {"regions": [self._public(t) for t in self.by_region.values()],
                "cleared": len(self.cleared), "total": 256, "mapDigest": "test%d" % len(self.kmap["sgg"]),
                "active": act}

    def gym_map(self):
        return self.kmap

    def gym_trainer(self, region):
        t = self.by_region[region]
        out = self._public(t)
        out["team"] = [{"species": m["species"], "num": (self.dex.get(m["species"]) or {}).get("num"),
                        "kr": (self.dex.get(m["species"]) or {}).get("kr"), "level": m["level"],
                        "types": [self.dex.type_name(x) for x in (self.dex.get(m["species"]) or {}).get("types", [])]}
                       for m in t["team"]]
        out["prize"] = t["level"] * (5 if out["cleared"] else 50)
        return out

    def gym_sprite(self, key):
        p = os.path.join(DATA, "trainer_sprites", "%s.png" % key)
        if not os.path.exists(p):
            return None
        with open(p, "rb") as f:
            return f.read()

    def sprite(self, num, shiny=False):
        return self.png, ".png"

    def _out(self, events, extra=None):
        self.rev += 1
        out = {"id": 1, "region": self.region, "rev": self.rev, "battle": self.tb.view(), "events": events}
        out.update(extra or {})
        return out

    def gym_start(self, region):
        if self.tb and not self.tb.over and self.region == region:
            return self._out([], {"resumed": True})
        self.region = region
        self.tb = TB.TrainerBattle(self.dex, [dict(m) for m in self.party], self.by_region[region],
                                   random.Random(7))
        return self._out(self.tb.start())

    def gym_battle(self):
        return self._out([])

    def gym_act(self, bid, kind, move="", slot=-1):
        ev = self.tb.act(kind, move if kind == "move" else slot) if kind != "forfeit" else self.tb.act("forfeit")
        extra = {}
        if self.tb.over and self.tb.result == "won":
            first = self.region not in self.cleared
            self.cleared.add(self.region)
            extra["reward"] = {"prize": self.tb.trainer["level"] * (50 if first else 5), "first": first,
                               "money": 12345, "cleared": len(self.cleared), "total": 256}
            extra["exp"] = [{"id": 11, "name": "뮤츠", "level": 100, "leveledUp": False}]
        return self._out(ev, extra)


class FakeApp(object):
    def __init__(self, root, api, dex):
        self.root = root
        self.api = api
        self.dex = dex
        self.gym_battle = None
        self.settings = {}
        self.synced = 0

    def notify(self, *_a):
        pass

    def want_learn(self, *_a):
        pass

    def request_sync(self):
        self.synced += 1


def mon(dex, species, level, moves, ability, mid):
    return {"id": mid, "species": species, "level": level, "nickname": None, "nature": "HARDY",
            "ability": ability, "gender": "M", "shiny": False, "held": None, "moves": moves,
            "ivs": dict((s, 31) for s in TB.STATS), "evs": dict((s, 85) for s in TB.STATS)}


def pump(root, cond, timeout=20.0):
    end = time.time() + timeout
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return False


def canvas_inside(cv, item):
    bb = cv.bbox(item)
    return bb is not None and bb[0] >= -1 and bb[2] <= cv.winfo_width() + 1, bb


def main():
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    with open(os.path.join(DATA, "gyms.json"), encoding="utf-8") as f:
        gyms = json.load(f)
    with open(os.path.join(DATA, "korea_map.json"), encoding="utf-8") as f:
        kmap = json.load(f)

    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    # 콜백 안에서 난 예외는 tk 가 찍기만 하고 넘어간다. 검사가 그걸 모르고 통과하지 않게
    # 모아 뒀다가 끝에서 본다 (창을 닫은 뒤 도는 기술 연출이 없어진 캔버스를 지우다 났다).
    callback_errors = []

    def on_callback_error(exc, val, tb):
        import traceback
        callback_errors.append("".join(traceback.format_exception(exc, val, tb))[-300:])
    root.report_callback_exception = on_callback_error
    print("글꼴 %s / 본문 %dpt (BASE_PT=%d) / 화면 %dx%d"
          % (U.FAMILY, U.FONT[1], U.BASE_PT, root.winfo_screenwidth(), root.winfo_screenheight()))

    party = [mon(dex, "MEWTWO", 100, ["PSYSTRIKE", "AURASPHERE", "ICEBEAM", "RECOVER"], "PRESSURE", 11),
             mon(dex, "GARCHOMP", 100, ["EARTHQUAKE", "DRAGONCLAW", "STONEEDGE", "SWORDSDANCE"], "ROUGHSKIN", 12),
             mon(dex, "GYARADOS", 100, ["WATERFALL", "ICEFANG", "CRUNCH", "DRAGONDANCE"], "INTIMIDATE", 13),
             mon(dex, "PIKACHU", 5, ["THUNDERSHOCK"], "STATIC", 14)]
    api = FakeApi(dex, gyms, kmap, party)
    app = FakeApp(root, api, dex)
    # 연출 대기를 1/10 로 (검사 시간을 줄인다 - 순서와 결과는 그대로)
    orig_later = GB.GymBattleWindow.later
    GB.GymBattleWindow.later = lambda self, ms, fn: orig_later(self, max(1, ms // 10), fn)

    name_of = {t["name"]: t["region"] for t in gyms["trainers"]}

    print("\n=== 지도 ===")
    gw = ui_gym.GymWindow(root, app)
    gw.win.geometry("1040x700+20+20")
    chk("요약과 지도가 온다", pump(root, lambda: gw.data is not None and gw.map is not None), gw.data)
    root.update_idletasks()
    chk("전국: 시·도 16곳", len([k for k in gw.items if k.startswith("s")]) == 16, len(gw.items))
    chk("전국 화면에 눌린 것이 없다", not squeezed(gw.win), squeezed(gw.win)[:4])

    def topmost_tag(x, y):
        items = gw.cv.find_overlapping(x - 1, y - 1, x + 1, y + 1)
        for it in reversed(items):
            tags = [t for t in gw.cv.gettags(it) if t[:1] in ("s", "g") and t[1:].isdigit()]
            if tags:
                return tags[0]
        return None

    pump(root, lambda: gw._redraw_job is None, 3)
    root.update()
    tf = gw._fit([sd["rings"] for sd in kmap["sido"]])
    small = [sd for sd in kmap["sido"] if sd["code"] in ("11", "30", "36", "26", "27", "31")]
    hit = {sd["name"]: topmost_tag(*tf(sd["center"])) for sd in small}
    chk("전국: 서울·대전·세종·부산·대구·울산 한가운데를 누르면 그곳이 잡힌다",
        all(hit[sd["name"]] == "s" + sd["code"] for sd in small), hit)
    gw._hover_sido("41", True)
    gw._hover_sido("41", False)
    chk("경기에 마우스를 올렸다 내려도 서울이 위에 있다", topmost_tag(*tf(small[0]["center"])) == "s11",
        topmost_tag(*tf(small[0]["center"])))
    btns = [t for t in texts(gw.card) if t in ("서울", "세종", "제주", "경기")]
    chk("옆 칸에 시·도 바로 가기", len(btns) == 4, btns)

    gw.enter_sido("41")
    root.update()
    n41 = len([d for d in kmap["sgg"] if d["sido"] == "41"])
    chk("경기: 시·군·구가 다 그려진다 (%d)" % n41, len([k for k in gw.items if k.startswith("g")]) == n41,
        len(gw.items))
    labels = [gw.cv.itemcget(i, "text") for i in gw.cv.find_withtag("label") if gw.cv.type(i) == "text"]
    chk("경기: 이름표가 있다", "가평군" in labels and any(x.startswith("Lv.") for x in labels), labels[:8])

    print("\n=== 트레이너 카드 ===")
    # 이유 문장이 가장 긴 트레이너도 넣는다 (두 줄로 접히면 카드가 길어진다)
    longest_why = max(gyms["trainers"], key=lambda t: len(t.get("why") or ""))["name"]
    api.cleared.add(name_of["난천"])            # 이긴 곳 줄이 가장 길다
    chk("요약에 '가장 센 트레이너' 가 없다", not any("가장 센 트레이너" in t for t in texts(gw.card)))
    for who in ("난천", "나여조경석", "담죽", "지우", longest_why):
        code = name_of[who]
        gw.select(code)
        ok = pump(root, lambda: any(isinstance(w, tk.Frame) for w in gw.card.winfo_children())
                  and any("데리고 있는 포켓몬" in t for t in texts(gw.card)))
        root.update()
        pump(root, lambda: False, 0.3)
        tx = texts(gw.card)
        chk("%s 카드가 뜬다" % who, ok and who in tx, tx[:6])
        t = next(t for t in gyms["trainers"] if t["name"] == who)
        kr = [(dex.get(m["species"]) or {}).get("kr") for m in t["team"]]
        chk("%s: 여섯 마리 이름이 다 있다" % who, all(k in tx for k in kr), kr)
        chk("%s: 창에 눌린 것이 없다" % who, not squeezed(gw.win), squeezed(gw.win)[:4])
        chk("%s: 카드 안에 눌린 것이 없다" % who, not squeezed(gw.card), squeezed(gw.card)[:4])
        btn = gw.go_btn.holder
        side_bottom = gw.side.winfo_rooty() + gw.side.winfo_height()
        chk("%s: 도전 단추가 다 보인다" % who,
            btn.winfo_ismapped() and btn.winfo_height() >= btn.winfo_reqheight()
            and btn.winfo_rooty() + btn.winfo_height() <= side_bottom,
            (btn.winfo_height(), btn.winfo_reqheight(), btn.winfo_rooty() + btn.winfo_height(), side_bottom))
        need, view = gw.card.winfo_reqheight(), gw.card_cv.winfo_height()
        chk("%s: 기본 크기(1040x700)에서는 굴리지 않아도 에이스까지 보인다" % who, need <= view, (need, view))
        chk("%s: 카드가 넘치면 굴릴 수 있다" % who,
            need <= view or float(gw.card_cv.cget("scrollregion").split()[3]) >= need,
            (need, view, gw.card_cv.cget("scrollregion")))
        imgs = [w for w in gw.card.winfo_descendants() if isinstance(w, tk.Label) and str(w.cget("image"))] \
            if hasattr(gw.card, "winfo_descendants") else None
        if imgs is None:
            imgs = []
            stack = list(gw.card.winfo_children())
            while stack:
                w = stack.pop()
                stack.extend(w.winfo_children())
                if isinstance(w, tk.Label) and str(w.cget("image")):
                    imgs.append(w)
        chk("%s: 트레이너 도트와 포켓몬 그림 일곱 장" % who, len(imgs) >= 7, len(imgs))
        if who == "담죽":
            chk("경로에 일반구가 띄어 써진다", "부천시 원미구" in texts(gw.crumb), texts(gw.crumb))
        if who == "지우":
            ph = gw.photos.get("trainer")
            chk("지우 카드: 새 도트를 그대로 크기로", ph and (ph.width(), ph.height()) == (113, 146),
                ph and (ph.width(), ph.height()))
        if who == "나여조경석":
            ph = gw.photos.get("trainer")
            chk("이스터에그 카드: 렌트라와 함께 선 그림을 그대로 크기로", ph and ph.width() == 112 and ph.height() == 134,
                ph and (ph.width(), ph.height()))
    # 허브 탭 안이나 창을 줄였을 때 - 가장 작은 크기
    gw.win.geometry("900x600")
    pump(root, lambda: False, 0.6)
    btn = gw.go_btn.holder
    side_bottom = gw.side.winfo_rooty() + gw.side.winfo_height()
    chk("가장 작은 창에서도 도전 단추가 보인다",
        btn.winfo_height() >= btn.winfo_reqheight() and btn.winfo_rooty() + btn.winfo_height() <= side_bottom,
        (btn.winfo_height(), btn.winfo_reqheight()))
    need, view = gw.card.winfo_reqheight(), gw.card_cv.winfo_height()
    chk("가장 작은 창: 카드가 넘치면 스크롤 막대가 보인다 (안 넘치면 없다)",
        gw.card_sb.winfo_ismapped() == (need > view), (need, view, gw.card_sb.winfo_ismapped()))
    gw.win.geometry("1040x700")
    pump(root, lambda: False, 0.6)

    print("\n=== 확대와 끌기 ===")
    # 전국 지도도 휠로 키운다. **굴리는 순간** 그림이 커져야 한다 (다시 그리기 전에)
    gw.to_nation()
    root.update()
    b0 = gw.cv.bbox("s11")

    class E0(object):
        pass
    e0 = E0()
    sx, sy = tf(small[0]["center"])
    e0.x, e0.y, e0.delta = int(sx), int(sy), 120
    e0.x_root, e0.y_root = gw.cv.winfo_rootx() + e0.x, gw.cv.winfo_rooty() + e0.y
    gw._on_wheel(e0)
    b1 = gw.cv.bbox("s11")
    chk("전국: 휠을 굴린 즉시 커진다", (b1[2] - b1[0]) > (b0[2] - b0[0]) * 1.1, (b0, b1))
    pump(root, lambda: gw._redraw_job is None, 3)
    root.update()
    b2 = gw.cv.bbox("s11")
    chk("전국: 멈추면 같은 크기로 다시 그린다", abs((b2[2] - b2[0]) - (b1[2] - b1[0])) <= 3, (b1, b2))
    # 범례는 지도와 다른 캔버스다. 지도를 키우고 도형을 올려도 범례 자리를 못 덮는다.
    gw._hover_sido("41", True)
    root.update()
    map_bottom = gw.cv.winfo_rooty() + gw.cv.winfo_height()
    chk("범례는 지도 캔버스 아래 따로 있다", gw.legend_cv.winfo_rooty() >= map_bottom
        and gw.legend_cv.find_all(), (gw.legend_cv.winfo_rooty(), map_bottom))
    gw._hover_sido("41", False)
    gw.enter_sido("28")
    root.update()

    def extent():
        xs = []
        for i in gw.cv.find_withtag("region"):
            bb = gw.cv.bbox(i)
            if bb:
                xs.append(bb)
        return min(b[0] for b in xs), max(b[2] for b in xs)

    x0, x1 = extent()

    class E(object):
        def __init__(self, x, y, delta=0):
            self.x, self.y, self.delta = x, y, delta
            self.x_root = gw.cv.winfo_rootx() + x
            self.y_root = gw.cv.winfo_rooty() + y

    cw, ch = gw.cv.winfo_width(), gw.cv.winfo_height()
    for _ in range(3):
        gw._on_wheel(E(cw // 2, ch // 2, 120))
    pump(root, lambda: gw._redraw_job is None, 3)
    root.update()
    y0, y1 = extent()
    chk("휠로 키운다", gw.zoom > 1.45 and (y1 - y0) > (x1 - x0) * 1.4, (gw.zoom, x1 - x0, y1 - y0))
    chk("키우면 '원래 크기' 가 보인다",
        any(gw.cv.itemcget(i, "text") == "원래 크기" for i in gw.cv.find_withtag("reset")))
    sel_before = gw.selected
    code = next(d["code"] for d in kmap["sgg"] if d["name"] == "연수구")
    gw._drag_start(E(300, 300))
    gw._drag_move(E(360, 330))
    gw._drag_move(E(420, 340))
    moved = list(gw.pan)
    gw._click_region(code)          # 놓는 순간의 클릭
    gw._drag_end(E(420, 340))
    chk("끌면 옮겨진다", moved != [0.0, 0.0], moved)
    chk("끌고 놓은 자리를 고르지 않는다", gw.selected == sel_before, gw.selected)
    pump(root, lambda: not gw._dragged, 2)
    gw._click_region(code)
    chk("그냥 누르면 고른다", gw.selected == code, gw.selected)
    for _ in range(8):
        gw._on_wheel(E(cw // 2, ch // 2, -120))
    chk("줄이면 원래 크기에서 멈춘다", gw.zoom == 1.0 and gw.pan == [0.0, 0.0], (gw.zoom, gw.pan))
    gw._on_wheel(E(cw // 2, ch // 2, 120))
    gw.to_nation()

    # 윈도우처럼 휠이 창으로 가도, 창의 휠 처리가 포인터 밑의 지도를 찾아 키운다
    gw.enter_sido("28")
    root.update()
    U.install_wheel(gw.win)
    top = gw.win.winfo_toplevel()

    class TopE(object):
        pass
    te = TopE()
    te.x_root = gw.cv.winfo_rootx() + cw // 3
    te.y_root = gw.cv.winfo_rooty() + ch // 3
    te.x, te.y = te.x_root - top.winfo_rootx(), te.y_root - top.winfo_rooty()   # 창 기준
    te.delta = 120
    under = top.winfo_containing(te.x_root, te.y_root)
    handler = None
    w = under
    while w is not None and handler is None:
        handler = getattr(w, "wheel_handler", None)
        w = getattr(w, "master", None)
    chk("포인터 밑의 지도에 휠 처리가 붙어 있다", handler is not None, under)
    if handler:
        handler(te)
    chk("창을 거쳐 온 휠로도 키운다", gw.zoom > 1.0, gw.zoom)
    # 휠 아래 점이 제자리에 있다: 그 점의 지도 좌표가 키우기 전후로 같다
    gw._reset_view()
    cxp, cyp = cw / 2.0, gw.cv.winfo_height() / 2.0
    mx, my = cw // 3, ch // 3
    handler(te)
    z, (px, py) = gw.zoom, gw.pan
    back_x = (mx - cxp - px) / z + cxp
    back_y = (my - cyp - py) / z + cyp
    chk("휠 아래 점이 그 자리에 머문다", abs(back_x - mx) < 1.5 and abs(back_y - my) < 1.5,
        (back_x, back_y, mx, my))
    gw.to_nation()
    chk("전국으로 나가면 확대가 풀린다", gw.zoom == 1.0, gw.zoom)

    gw.enter_sido("47")
    root.update()
    dashed = [i for i in gw.cv.find_all() if gw.cv.type(i) == "rectangle" and gw.cv.itemcget(i, "dash")]
    chk("경북: 울릉군을 당겨 그리고 점선 상자를 두른다", len(dashed) == 1, len(dashed))

    print("\n=== 배틀 창 ===")
    region = name_of["담죽"]
    gw.select(region)
    pump(root, lambda: any("도전하기" in t for t in texts(gw.card)))
    gw.challenge(region)
    chk("배틀 창이 뜬다", pump(root, lambda: gw.battle is not None))
    b = gw.battle
    chk("시작 연출이 끝나고 기술을 고른다", pump(root, lambda: not b.busy and b.mode == "moves", 30), b.mode)
    root.update_idletasks()
    sh = root.winfo_screenheight()
    wx1, wy1, wx2, wy2 = PLAT.work_area(root.winfo_screenwidth(), sh)
    chk("창이 독·메뉴 막대를 뺀 화면 안에 들어온다",
        b.win.winfo_rooty() >= wy1 and b.win.winfo_rooty() + b.win.winfo_height() <= wy2,
        (b.win.winfo_rooty(), b.win.winfo_height(), wy1, wy2))
    balls = [cv_i for cv_i in b.box["me"]["balls"]]
    shown_balls = [i for i in balls if b.cv.itemcget(i, "image") == str(b.photos["ball"])]
    chk("내 남은 포켓몬 수만큼 몬스터볼 그림", len(shown_balls) == len(party), len(shown_balls))
    chk("상대는 여섯 개 볼", sum(1 for i in b.box["foe"]["balls"]
                            if b.cv.itemcget(i, "image") in (str(b.photos["ball"]), str(b.photos["ball_out"]))) == 6)
    cv = b.cv
    chk("장면 폭이 창 폭을 안 넘는다", cv.winfo_reqwidth() <= b.win.winfo_width(),
        (cv.winfo_reqwidth(), b.win.winfo_width()))
    for who in ("me", "foe"):
        inside, bb = canvas_inside(cv, b.box[who]["bg"])
        chk("%s 이름표가 장면 안에 있다" % who, inside, (bb, cv.winfo_width()))
    inside, bb = canvas_inside(cv, b.box["me"]["hp"])
    chk("내 체력 숫자가 장면 안에 있다", inside and cv.itemcget(b.box["me"]["hp"], "text"), bb)
    chk("포켓몬 그림이 선다", pump(root, lambda: all(cv.itemcget(b.sprite[w], "image") for w in ("me", "foe")), 10))
    chk("트레이너 도트가 선다", pump(root, lambda: cv.itemcget(b.trainer_item, "image"), 10))
    cells = b.left.winfo_children()[0].winfo_children()
    chk("기술 네 칸", len(cells) == 4, len(cells))
    chk("기술 칸에 눌린 것이 없다", not squeezed(b.win), squeezed(b.win)[:4])
    chk("기술 칸에 위력·PP 가 보인다",
        any("PP" in t for t in texts(b.left)) and any("위력" in t for t in texts(b.left)), texts(b.left)[:8])

    b.open_switch()
    root.update()
    pump(root, lambda: False, 0.5)
    grid = b.left.winfo_children()[1]
    cells = grid.winfo_children()
    chk("교체 칸이 파티 수만큼", len(cells) == len(party), len(cells))
    tallest = max(c.winfo_height() for c in cells)
    chk("교체 칸이 제 크기 (그림 칸이 글자 수로 커지지 않는다)", tallest <= U.h(110), tallest)
    chk("교체 칸에 이름과 레벨", all(any(k in t for t in texts(grid)) for k in ("뮤츠", "Lv.100", "피카츄")),
        texts(grid))
    chk("교체 화면에 눌린 것이 없다", not squeezed(b.win), squeezed(b.win)[:4])
    chk("돌아가기가 있다", any("돌아가기" in t for t in texts(b.left)))
    b.open_switch(forced=True)
    root.update()
    chk("강제 교체에는 돌아가기가 없다", not any("돌아가기" in t for t in texts(b.left)))
    b.show_commands()

    played = []
    orig_play = GB.FX.Effect.play
    GB.FX.Effect.play = lambda self: (played.append(self.style), orig_play(self))[1]
    turn0 = b.view["turn"]
    b.use_move("PSYSTRIKE")
    chk("한 턴이 돈다", pump(root, lambda: not b.busy and b.view["turn"] > turn0, 30), b.view["turn"])
    chk("기술을 쓰면 연출이 돈다", len(played) >= 1, played)

    # 끝까지 둔다: 가장 센 기술로
    for _ in range(80):
        if b.view.get("over"):
            break
        pump(root, lambda: not b.busy, 30)
        v = b.view
        if v.get("over"):
            break
        if v.get("needSwitch"):
            slot = next(i for i, m in enumerate(v["me"]["team"]) if not m["fainted"])
            b.do_switch(slot)
        else:
            mm = v["me"]["team"][v["me"]["slot"]]
            k = max([m for m in mm["moves"] if m["pp"] > 0], key=lambda m: m.get("power") or 0)["key"]
            b.use_move(k)
        pump(root, lambda: b.busy is False, 30)
    pump(root, lambda: not b.busy, 30)
    root.update()
    pump(root, lambda: False, 0.3)
    chk("이긴다", b.view.get("result") == "won", b.view.get("result"))
    tx = texts(b.left)
    chk("결과: 승리와 상금", "승리!" in tx and any("상금 2,500원" in t for t in tx), tx)
    chk("결과 화면에 눌린 것이 없다 (지도로 돌아가기)", not squeezed(b.win), squeezed(b.win)[:4])
    chk("끝나면 교체·기권을 못 누른다", not b.switch_btn.enabled and not b.forfeit_btn.enabled,
        (b.switch_btn.enabled, b.forfeit_btn.enabled))
    calls = len(api.calls)
    b.close()
    chk("닫으면 앱에서 빠진다", app.gym_battle is None)
    chk("닫으면 지도가 다시 불러온다", pump(root, lambda: len(api.calls) > calls, 5), api.calls[-3:])
    won_region = name_of["담죽"]
    chk("이긴 곳이 지도에 반영된다",
        pump(root, lambda: gw.data and gw.by_region.get(won_region, {}).get("cleared"), 5),
        gw.data and gw.data["cleared"])

    print("\n=== 기권 (이스터에그) ===")
    region = name_of["나여조경석"]
    gw.challenge(region)
    chk("다시 뜬다", pump(root, lambda: gw.battle is not None and not gw.battle.busy, 30))
    b = gw.battle
    chk("이스터에그 배틀: 혼자 선 그림", pump(root, lambda: b.photos.get("trainer") is not None, 10)
        and b.photos["trainer"].width() == 47, b.photos.get("trainer") and b.photos["trainer"].width())
    inside, bb = canvas_inside(b.cv, b.trainer_item)
    chk("이스터에그 배틀: 그림이 장면 안에 있다", inside and bb[1] >= 0, (bb, b.cv.winfo_width()))
    b._send("forfeit")
    chk("기권하면 결과로", pump(root, lambda: b.view.get("over") and not b.busy, 30), b.view.get("result"))
    root.update()
    pump(root, lambda: False, 0.3)
    chk("기권 결과에 눌린 것이 없다", not squeezed(b.win), squeezed(b.win)[:4])
    chk("기권은 상금이 없다", not any("상금" in t for t in texts(b.left)), texts(b.left))
    # 기술 연출이 도는 **도중에** 창을 닫는다. CI 러너가 느려서 실제로 났던 일이다 -
    # 안전 타이머가 먼저 넘어가 연출 참조를 놓치면 닫을 때 못 멈추고, 연출이 없어진
    # 캔버스를 지우다 TclError 를 냈다.
    md = dex.moves["FLAMETHROWER"]
    b._pending_data = {"battle": b.view}
    b._play_fx({"t": "move", "who": "me", "move": md["kr"], "moveType": md["type"], "cat": md["cat"]},
               "me", "foe")
    b.fx = None                              # 안전 타이머가 먼저 넘어간 것과 같은 상태
    b.close()

    gw.close()
    pump(root, lambda: False, 2.0)          # 닫은 뒤에도 남은 연출·예약이 다 돌 때까지
    chk("콜백에서 난 예외가 없다", not callback_errors, callback_errors[:2])
    root.destroy()
    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
