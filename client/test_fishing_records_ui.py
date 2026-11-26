# -*- coding: utf-8 -*-
"""낚시 기록 창 · 관리 창 무게 한 줄 (시즌 7 낚시) - 진짜 Tk.

    python client/test_fishing_records_ui.py

**창을 진짜로 띄운다.** 서버는 안 띄운다 - 가짜 api 가 /api/fish/board 와 같은 모양으로 답한다
(design-notes/2026-11-26-fishing-plan.md 의 'API 계약'). 못 박는 것:

  1. fish_text.line: '낚시 · 잉어킹일 때 84.2kg · 표준의 1.31배' · 10kg 미만은 소수 둘째 자리 · 낚은 것이 아니면 None
  2. 이번 주: 30줄 + 내 자리 줄, 머리글(순위 · 포켓몬 · 무게 · 배율 · 트레이너), 1.3배 이상 금색 '대물' · 1.6배 이상 '왕대물',
     '끝나기까지 N일 N시간'. 내 자리가 30줄 안이면 그 줄을 칠하고 따로 안 붙인다. 도트는 sprite_cache 로 받아 붙인다.
  3. 지난주 1~3위 · 내 기록(종마다) - 탭을 바꿔도 서버에 다시 묻지 않는다
  4. 빈 주 · 옛 서버(404)는 안내 글 (오류로 안 보인다) · 다른 오류는 까닭
  5. 허브 '이벤트' 묶음의 '낚시' 탭 · open_records 는 이미 열려 있으면 그것을 앞으로 (창이 늘지 않는다)
  6. 닫으면 남는 창 · 예약(after) 없음, 그리는 중 예외 없음
  7. 관리 창 상세: 기본 테마는 창을 띄워 이름 아래 한 줄, DP 계열 여섯 테마는 한 번씩 따로 띄워 요약 판에 그 글
     (+ 일곱 곳 소스에 fish_text.line)
"""
import inspect
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-fishrec-")
SKIN = os.environ.get("POKET_FISHREC_SKIN", "default")
os.environ["POKET_SKIN"] = SKIN

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "server", "data")
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from PIL import Image, ImageDraw                            # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins, ui_box                      # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

import smoke_box_filter as SB                               # noqa: E402

OK = FAIL = 0
DP_FAMILY = ("dp", "swsh", "bw", "pt", "gs", "emerald")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def settle(root, sec=0.2):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def pump(root, cond, sec=6.0):
    end = time.time() + sec
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.01)
    root.update()
    return cond()


def texts(w):
    out = []

    def walk(x):
        for c in x.winfo_children():
            try:
                if "text" in c.keys() and str(c.cget("text")):
                    out.append(str(c.cget("text")))
            except Exception:                               # noqa: BLE001
                pass
            walk(c)
    walk(w)
    return out


def tops(root):
    return [c for c in root.winfo_children() if isinstance(c, tk.Toplevel) and c.winfo_exists()]


# ---------------------------------------------------------------- 가짜 서버
class Err(Exception):
    """api.ApiError 와 같은 모양 - 화면은 message · status 를 읽는다."""

    def __init__(self, message, status=0):
        Exception.__init__(self, message)
        self.message, self.status = message, status


def _png():
    im = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle((8, 8, 30, 34), fill=(60, 120, 220, 255))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


PNG = _png()
WATER = [("MAGIKARP", 129, "잉어킹"), ("GOLDEEN", 118, "콘치"), ("HORSEA", 116, "쏘드라"),
         ("CHINCHOU", 170, "초라기"), ("WAILMER", 320, "고래왕자"), ("FEEBAS", 349, "빈티나")]
ENDS_IN = 3 * 86400 + 5 * 3600 + 100            # 끝나기까지 3일 5시간


def row(rank, ratio, name, i=0, shiny=False):
    sp, num, kr = WATER[i % len(WATER)]
    return {"rank": rank, "name": name, "species": sp, "num": num, "kr": kr, "shiny": shiny,
            "g": int(round(10000 * ratio)) + i, "ratio": ratio, "at": "2026-12-02T03:22:07+00:00"}


def board(me_rank=41):
    top = []
    for i in range(30):
        ratio = (1.84, 1.62, 1.5973, 1.35, 1.31)[i] if i < 5 else round(1.2 - 0.01 * i, 3)
        top.append(row(i + 1, ratio, "트레이너%d" % (i + 1), i, shiny=(i == 3)))
    me = None
    if me_rank:
        me = dict(top[me_rank - 1]) if me_rank <= 30 else row(me_rank, 1.02, "나", 1)
    return {"week": "2026-11-30", "weekStart": "2026-11-29T15:00:00+00:00", "endsIn": ENDS_IN,
            "top": top, "me": me,
            "last": [row(1, 1.97, "지난챔프", 4), row(2, 1.71, "둘째", 0), row(3, 1.52, "셋째", 2)],
            "mine": [dict((k, v) for k, v in row(0, r, "", i).items() if k not in ("rank", "name", "shiny"))
                     for i, r in ((0, 1.31), (1, 1.12), (2, 0.95), (5, 1.66))]}


class BoardApi(object):
    def __init__(self):
        self.mode = "open"          # open | empty | 404 | down
        self.me_rank = 41
        self.calls = []
        self.sprites = []

    def fish_board(self, week="this"):
        self.calls.append(week)
        if self.mode == "404":
            raise Err("요청한 것을 찾을 수 없습니다. (404)", 404)
        if self.mode == "down":
            raise Err("서버에 연결할 수 없습니다.", 0)
        if self.mode == "empty":
            return {"week": "2026-11-30", "weekStart": "2026-11-29T15:00:00+00:00", "endsIn": 5 * 3600 + 150,
                    "top": [], "me": None, "last": [], "mine": []}
        return json.loads(json.dumps(board(self.me_rank)))

    def sprite(self, num, shiny=False, back=False):
        self.sprites.append((num, bool(shiny)))
        return PNG, ".png"


class App(object):
    def __init__(self, root, api):
        self.root = root
        self.api = api
        self.hub = None


class HubApp(App):
    """진짜 앱의 _tab 처럼: 허브를 만들고 그 탭으로 간다 (app._tab)."""

    def _tab(self, key):
        from poketdesktop import ui_hub
        if not self.hub:
            self.hub = ui_hub.make(self)
        self.hub.show(key)
        return self.hub.panes.get(key)


# ---------------------------------------------------------------- 1. 한 줄
def text_line():
    print("1. fish_text.line")
    from poketdesktop import fish_text
    big = {"fish": {"g": 84200, "ratio": 1.3149, "species": "MAGIKARP", "kr": "잉어킹"}}
    chk("84.2kg · 1.31배", fish_text.line(big) == "낚시 · 잉어킹일 때 84.2kg · 표준의 1.31배", fish_text.line(big))
    small = {"fish": {"g": 400, "ratio": 1.33, "species": "HORSEA", "kr": "쏘드라"}}
    chk("10kg 미만은 소수 둘째 자리 (0.40kg · 1.33배)", fish_text.line(small) == "낚시 · 쏘드라일 때 0.40kg · 표준의 1.33배",
        fish_text.line(small))
    chk("낚은 포켓몬이 아니면 None", fish_text.line({"species": "MAGIKARP"}) is None
        and fish_text.line({"fish": None}) is None and fish_text.line(None) is None)
    chk("  잰 때의 종으로 적는다 (진화해도)", "잉어킹일 때" in fish_text.line(dict(big, species="GYARADOS")))
    rt = fish_text.ratio_text
    chk("배율은 내려서 적는다 - '1.60배' 면 늘 1.6 이상 (1.5973 → 1.59배 · 대물, 1.6 → 1.60배 · 왕대물)",
        rt(1.5973) == "1.59배" and fish_text.badge(1.5973) == "big"
        and rt(1.6) == "1.60배" and fish_text.badge(1.6) == "huge", (rt(1.5973), rt(1.6)))
    chk("  소수 끝자리에 안 흔들린다 (1.15 · 1.3 · 1.2999 · 없음)",
        (rt(1.15), rt(1.3), rt(1.2999), rt(None)) == ("1.15배", "1.30배", "1.29배", "0.00배"),
        (rt(1.15), rt(1.3), rt(1.2999), rt(None)))


# ---------------------------------------------------------------- 2~4. 기록 창
def records(root):
    from poketdesktop import ui_fishing as F
    api = BoardApi()
    app = App(root, api)
    n_top = len(tops(root))

    print("2. 이번 주")
    w = F.open_records(app)
    chk("허브가 없는 앱이면 창 하나로 뜬다", w is not None and not U.is_embedded(w.win) and app.fish_records is w,
        type(w))
    w.win.geometry("760x620+20+20")
    pump(root, lambda: w.data is not None and not w._loading)
    seen = texts(w.win)
    chk("처음 탭은 이번 주", w.tab == "this" and w.seg.current == "this", w.tab)
    chk("머리글: 순위 · 포켓몬 · 무게 · 배율 · 트레이너",
        all(x in seen for x in ("순위", "포켓몬", "무게", "배율", "트레이너")), seen[:12])
    top = [r for r in w.rows if r["kind"] == "top"]
    mine = [r for r in w.rows if r["kind"] == "me"]
    chk("30줄", len(top) == 30 and [r["data"]["rank"] for r in top] == list(range(1, 31)), len(top))
    chk("  + 내 자리 줄 (41위 · '내 자리' 띠)", len(mine) == 1 and mine[0]["data"]["rank"] == 41 and "내 자리" in seen,
        [r["data"]["rank"] for r in mine])
    chk("  내 줄은 칠해져 있다 (다른 줄은 아니다)", mine and mine[0]["mine"]
        and mine[0]["cells"]["name"].cget("bg") == F.MINE_BG
        and not any(r["mine"] or r["cells"]["name"].cget("bg") == F.MINE_BG for r in top))
    first = top[0]["cells"]
    chk("줄의 글: 순위 · 이름 · 무게 · 배율 · 트레이너",
        first["rank"].cget("text") == "1" and "잉어킹" in texts(first["name"]) + [""]
        and first["kg"].cget("text") == "18.4kg" and first["ratio"].cget("text") == "1.84배"
        and first["who"].cget("text") == "트레이너1",
        (first["rank"].cget("text"), texts(first["name"]), first["kg"].cget("text"), first["ratio"].cget("text")))
    chk("1.6배 이상은 왕대물 빛깔 + '왕대물'", first["ratio"].cget("fg") == F.HUGE_FG and first["kg"].cget("fg") == F.HUGE_FG
        and "왕대물" in texts(first["name"]), (first["ratio"].cget("fg"), texts(first["name"])))
    third = top[2]["cells"]
    chk("1.3배 이상은 금색 '대물'", third["ratio"].cget("fg") == U.ACCENT and "대물" in texts(third["name"])
        and "왕대물" not in texts(third["name"]), (third["ratio"].cget("fg"), texts(third["name"])))
    chk("  1.5973 은 '1.59배' (반올림한 '1.60배' 에 '대물' 이 붙지 않게)", third["ratio"].cget("text") == "1.59배",
        third["ratio"].cget("text"))
    plain = top[10]["cells"]
    chk("그 아래는 물들이지 않는다", plain["ratio"].cget("fg") not in (U.ACCENT, F.HUGE_FG)
        and not any(t in ("대물", "왕대물") for t in texts(plain["name"])), texts(plain["name"]))
    chk("이로치는 ★", any("★" in t for t in texts(top[3]["cells"]["name"])), texts(top[3]["cells"]["name"]))
    chk("'끝나기까지 3일 5시간'", w.ends.cget("text") == "끝나기까지 3일 5시간", w.ends.cget("text"))
    chk("  주 (11/30(월) ~ 12/6(일))", "11/30" in w.week.cget("text") and "12/6" in w.week.cget("text"),
        w.week.cget("text"))
    chk("ends_text: 하루 안 · 한 시간 안 · 지남", F.ends_text(5 * 3600 + 120) == "끝나기까지 5시간 2분"
        and F.ends_text(600) == "끝나기까지 10분" and "끝나기까지" not in F.ends_text(0),
        (F.ends_text(5 * 3600 + 120), F.ends_text(600), F.ends_text(0)))
    pump(root, lambda: all(str(lb.cget("image")) for lb, _n, _s in w.pics), 8)
    chk("도트는 sprite_cache 로 받아 붙인다", w.pics and all(str(lb.cget("image")) for lb, _n, _s in w.pics)
        and (129, False) in api.sprites, (len(w.pics), api.sprites[:4]))
    chk("  이로치는 이로치 도트", (WATER[3][1], True) in api.sprites, api.sprites)
    chk("서버에는 한 번만 물었다 (이번 주 · 지난주 · 내 기록이 한 번에 온다)", api.calls == ["this"], api.calls)

    print("3. 지난주 · 내 기록")
    w.seg._click("last")
    root.update()
    last = [r for r in w.rows if r["kind"] == "last"]
    chk("지난주 1~3위", w.tab == "last" and [r["data"]["rank"] for r in last] == [1, 2, 3], [r["data"] for r in last])
    chk("  메달 빛깔 (1위 금)", last and last[0]["cells"]["rank"].cget("fg") == F.MEDAL[1])
    chk("  이번 주 줄은 치웠다", not [r for r in w.rows if r["kind"] in ("top", "me")])
    # 머리말도 지난주 것으로 (실제 앱 시험 11/27 - 이번 주 날짜 · '끝나기까지' 가 남아 있었다)
    chk("  머리말은 지난주 날짜, '끝나기까지' 는 없다",
        w.week.cget("text") == "11/23(월) ~ 11/29(일)" and w.ends.cget("text") == "",
        (w.week.cget("text"), w.ends.cget("text")))
    w._tick()
    chk("  초가 흘러도 지난주 탭에 '끝나기까지' 가 다시 안 생긴다", w.ends.cget("text") == "", w.ends.cget("text"))
    w.seg._click("this")
    root.update()
    chk("  이번 주로 돌아오면 이번 주 날짜 · 끝나기까지", w.week.cget("text") == "11/30(월) ~ 12/6(일)"
        and w.ends.cget("text") != "", (w.week.cget("text"), w.ends.cget("text")))
    w.seg._click("mine")
    root.update()
    mine = [r for r in w.rows if r["kind"] == "mine"]
    chk("내 기록: 종마다 한 줄 (서버 차례 그대로)", w.tab == "mine" and [r["data"]["kr"] for r in mine]
        == ["잉어킹", "콘치", "쏘드라", "빈티나"], [r["data"].get("kr") for r in mine])
    chk("  무게 · 배율 · 빛깔", mine and mine[3]["cells"]["kg"].cget("text") == "16.6kg"
        and mine[3]["cells"]["ratio"].cget("fg") == F.HUGE_FG, mine and mine[3]["cells"]["kg"].cget("text"))
    chk("탭을 바꿔도 서버에 다시 묻지 않는다", api.calls == ["this"], api.calls)

    print("  내 자리가 30줄 안이면")
    w.seg._click("this")
    api.me_rank = 7
    w.reload()
    pump(root, lambda: not w._loading and len(api.calls) == 2)
    top = [r for r in w.rows if r["kind"] == "top"]
    chk("그 줄을 칠하고 따로 안 붙인다", not [r for r in w.rows if r["kind"] == "me"]
        and [r["data"]["rank"] for r in top if r["mine"]] == [7] and "내 자리" not in texts(w.win),
        [r["data"]["rank"] for r in top if r["mine"]])

    print("4. 빈 주 · 옛 서버 · 오류")
    api.mode = "empty"
    w.reload()
    pump(root, lambda: not w._loading and len(api.calls) == 3)
    seen = "\n".join(texts(w.win))
    chk("빈 주: 안내 글 (줄 없음)", not w.rows and "아직" in seen, seen[-160:])
    chk("  끝나기까지 5시간 2분", w.ends.cget("text") == "끝나기까지 5시간 2분", w.ends.cget("text"))
    w.seg._click("last")
    root.update()
    chk("  지난주도 안내 글", not w.rows and "지난주" in "\n".join(texts(w.inner)), texts(w.inner))
    w.seg._click("mine")
    root.update()
    chk("  내 기록도 안내 글", not w.rows and "아직" in "\n".join(texts(w.inner)), texts(w.inner))
    api.mode = "404"
    w.reload()
    pump(root, lambda: not w._loading and w.closed)
    seen = "\n".join(texts(w.win))
    chk("옛 서버 · 안 연 시즌(404): '낚시는 시즌 7에 열립니다.'", w.closed and "낚시는 시즌 7에 열립니다." in seen
        and not w.rows, seen[:200])
    chk("  오류로 안 보인다 (빨간 글 없음)", "404" not in seen and "불러오지 못했" not in seen, seen[:200])
    api.mode = "open"
    w.reload()
    pump(root, lambda: not w._loading and not w.closed and w.rows)
    chk("열리면 기록이 돌아온다", not w.closed and w.rows)
    api.mode = "down"
    w.reload()
    pump(root, lambda: not w._loading and len(api.calls) == 6)
    seen = "\n".join(texts(w.win))
    chk("다른 오류는 까닭을 적는다 (그려 둔 기록은 둔다)", "서버에 연결할 수 없습니다." in seen and w.rows, seen[-200:])
    api.mode = "open"

    print("5-1. open_records 다시")
    again = F.open_records(app)
    chk("이미 열려 있으면 그 창을 앞으로 (창이 늘지 않는다)", again is w and len(tops(root)) == n_top + 1,
        (again is w, len(tops(root)) - n_top))
    pump(root, lambda: not w._loading)
    chk("  다시 불러온다", len(api.calls) == 7, api.calls)

    print("6. 닫기")
    w._loaded_at -= 10 ** 6
    w._ends_at = time.time() - 1                    # 주가 끝났다 - 다음 틱에 다시 불러온다
    w._tick()
    pump(root, lambda: not w._loading)
    chk("주가 끝나면 다시 불러온다", len(api.calls) == 8, api.calls)
    chk("  창을 띄워 둔 동안 남은 시간을 고쳐 적는 예약이 있다", w._tick_job is not None)
    w.close()
    root.update()
    chk("닫으면 창 · 예약이 없다", not w.alive and w._tick_job is None and len(tops(root)) == n_top
        and app.fish_records is None, (w._tick_job, len(tops(root)) - n_top))


def hub(root):
    print("5. 허브 '이벤트' 묶음")
    from poketdesktop import ui_fishing as F
    from poketdesktop import ui_hub
    row_ = next((t for t in ui_hub.TABS if t[0] == "fishing"), None)
    chk("탭 '낚시' 가 있다 (FishRecords, root 없이)", row_ is not None and row_[1] == "낚시"
        and row_[2] is F.FishRecords and row_[3] is False, row_)
    chk("  '이벤트' 묶음, 올림픽 다음", ui_hub.GROUP_TABS["event"] == ["arche", "olympics", "fishing"]
        and ui_hub.GROUP_OF["fishing"] == "event", ui_hub.GROUP_TABS["event"])
    chk("  마이페이지는 여전히 맨 끝", ui_hub.TABS[-1][0] == "my" and ui_hub.GROUPS[-1][0] == "my")
    api = BoardApi()
    app = HubApp(root, api)
    n_top = len(tops(root))
    pane = F.open_records(app)
    chk("앱이면 허브의 그 탭으로 연다", pane is not None and app.hub is not None and app.hub.current == "fishing"
        and app.hub.panes.get("fishing") is pane and U.is_embedded(pane.win), getattr(app.hub, "current", None))
    if pane is None:
        if app.hub is not None:
            app.hub.close()
        return
    app.hub.win.geometry("1040x700+20+20")
    pump(root, lambda: pane.data is not None and not pane._loading)
    chk("  탭 안에서도 30줄 + 내 자리", len([r for r in pane.rows if r["kind"] in ("top", "me")]) == 31,
        len(pane.rows))
    again = F.open_records(app)
    pump(root, lambda: not pane._loading)
    chk("  다시 열면 같은 탭 (창은 허브 하나)", again is pane and len(tops(root)) == n_top + 1
        and len(api.calls) == 2, (len(tops(root)) - n_top, api.calls))
    n = len(api.calls)
    pane.on_shown()
    root.update()
    chk("  방금 불러온 것이면 탭을 다시 골라도 그대로", len(api.calls) == n)
    pane._loaded_at -= F.STALE_SEC + 5
    pane.on_shown()
    pump(root, lambda: not pane._loading)
    chk("  오래됐으면 다시 불러온다", len(api.calls) == n + 1, api.calls)
    app.hub.close()
    root.update()
    chk("허브를 닫으면 탭도 정리된다 (예약 없음)", not pane.alive and pane._tick_job is None and len(tops(root)) == n_top)


# ---------------------------------------------------------------- 7. 관리 창 상세
FISH = {"g": 84200, "ratio": 1.3149, "species": "MAGIKARP", "kr": "잉어킹"}
LINE = "낚시 · 잉어킹일 때 84.2kg · 표준의 1.31배"


def box_mons(dex):
    a = SB.mon(dex, 130, 1, on=True)                # 잉어킹일 때 낚아 갸라도스로 진화한 것
    a["fish"] = dict(FISH)
    b = SB.mon(dex, 25, 2, on=True)
    return [a, b]


def box_default(root, dex):
    print("7. 관리 창 상세 (기본 테마)")
    app = SB.FakeApp(root, dex, box_mons(dex))
    win = ui_box.BoxWindow(root, app)
    win.win.geometry("990x668+20+20")
    SB.wait_for(root, lambda: getattr(win, "mons", None))
    SB.settle_rows(root, win)
    win.select(1)
    settle(root, 0.2)
    lb = getattr(win, "d_fish", None)
    chk("낚은 포켓몬: 이름 아래 한 줄", lb is not None and lb.winfo_manager() == "pack" and lb.cget("text") == LINE,
        lb is not None and (lb.winfo_manager(), lb.cget("text")))
    if lb is not None:
        sl = win.d_sub.master.pack_slaves()
        chk("  분류 줄 바로 다음", lb in sl and sl.index(lb) == sl.index(win.d_sub) + 1,
            [str(x) for x in sl][:4])
    win.select(2)
    settle(root, 0.2)
    chk("다른 포켓몬을 고르면 그 줄이 빠진다", lb is not None and not lb.winfo_manager())
    win.select(1)
    settle(root, 0.1)
    win.clear_selection()
    settle(root, 0.1)
    chk("고른 것을 풀어도 빠진다", lb is not None and not lb.winfo_manager())
    win.close()
    settle(root, 0.1)


def box_theme(root, dex):
    print("7. 관리 창 요약 (%s 테마)" % SKIN)
    app = SB.FakeApp(root, dex, box_mons(dex))
    win = ui_box.BoxWindow(root, app)
    top = win.win.winfo_toplevel()
    top.geometry("1180x760+20+20")
    top.deiconify()
    SB.wait_for(root, lambda: getattr(win, "mons", None))
    settle(root, 0.5)
    chk("이 테마의 박스", type(win).__module__.endswith("%s.box" % SKIN), type(win).__module__)
    win.select(1)
    settle(root, 0.4)
    cv = win.dcv

    def drawn():
        return [cv.itemcget(i, "text").replace("\n", " ") for i in cv.find_all() if cv.type(i) == "text"]
    got = [t for t in drawn() if t.startswith("낚시 ·")]
    chk("요약 판에 그 한 줄", len(got) == 1 and "잉어킹일 때 84.2kg" in got[0] and "1.31배" in got[0], got)
    name = [i for i in cv.find_all() if cv.type(i) == "text" and cv.itemcget(i, "text") == "갸라도스"]
    line = [i for i in cv.find_all() if cv.type(i) == "text" and cv.itemcget(i, "text").startswith("낚시 ·")]
    chk("  이름보다 아래", name and line and cv.bbox(line[0])[1] >= cv.bbox(name[-1])[3] - 2,
        (name and cv.bbox(name[-1]), line and cv.bbox(line[0])))
    win.select(2)
    settle(root, 0.4)
    chk("다른 포켓몬에는 없다", not [t for t in drawn() if t.startswith("낚시 ·")])
    win.close()
    settle(root, 0.1)


def sources():
    print("7. 일곱 곳 소스")
    import importlib
    from poketdesktop import ui_box as BX
    chk("기본 관리 창", "fish_text.line" in inspect.getsource(BX.BoxWindow), "ui_box")
    for key in DP_FAMILY:
        mod = importlib.import_module("poketdesktop.skins.%s.box" % key)
        src = inspect.getsource(mod.BoxWindow._paint_detail) if "_paint_detail" in vars(mod.BoxWindow) else ""
        chk("  %s 의 _paint_detail" % key, "fish_text.line" in src, key)


def main():
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-600:])
    root.report_callback_exception = on_err
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    print("== 테마: %s" % SKIN)
    chk("이번 실행의 테마", skins.active() == SKIN, skins.active())
    if SKIN == "default":
        text_line()
        records(root)
        hub(root)
        box_default(root, dex)
        sources()
    else:
        box_theme(root, dex)
    chk("그리는 중에 난 예외가 없다", not errors, errors[:2])
    try:
        root.destroy()
    except tk.TclError:
        pass


if __name__ == "__main__":
    main()
    if SKIN == "default":
        for key in DP_FAMILY:
            env = dict(os.environ, POKET_FISHREC_SKIN=key)
            env.pop("POKET_HOME", None)
            env.pop("POKET_SKIN", None)
            out = subprocess.run([sys.executable, os.path.abspath(__file__)], env=env, capture_output=True,
                                 text=True)
            for ln in out.stdout.splitlines():
                if ln.startswith("  ") or ln.startswith("==") or ln.startswith("7."):
                    print(ln)
            m = re.search(r"(\d+)개 통과, (\d+)개 실패", out.stdout)
            if m:
                OK += int(m.group(1))
                FAIL += int(m.group(2))
            if not m or (out.returncode != 0 and int(m.group(2)) == 0):
                FAIL += 1
                print("  FAIL %s 테마 검사가 끝나지 않았다\n%s" % (key, out.stderr[-1500:]))
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    sys.exit(1 if FAIL else 0)
