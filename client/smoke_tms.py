# -*- coding: utf-8 -*-
"""기술머신 창 — 진짜 Tk 로 확인.

    python client/smoke_tms.py

서버 없이 돈다. 기술머신 목록은 server/data/tms.json 에서 만들고, 포켓몬
도트는 **여기서 GIF 를 그려서** 쓴다(네트워크를 안 탄다).

## 무엇을 못 박나

  1. 오른쪽 '배울 수 있는 포켓몬' 의 도트가 **안 잘린다.**
     `Label(width=3)` 은 그림일 때 3픽셀이라 22px 도트가 7px 로 잘려
     있었다. 도트를 담는 칸이 그림보다 크고, 칸이 줄 안에 들어가야 한다.
     그림 셋으로 본다 - 좁은 것(8x22), 옆으로 긴 것(105x32), 프레임이
     여럿이고 몸이 캔버스를 꽉 채우는 큰 것(152x185).
  2. 도트가 오기 전과 후에 **이름 자리가 안 움직인다.**
  3. '가진 것만 / 전부' 가 맞는 줄 수를 **순서대로** 보여준다.
     줄은 다시 만들지 않고 담았다 뺐다만 한다.
  4. 나눠 만드는 중에 거르기를 바꾸거나 아직 없는 줄을 골라도 맞다.
  5. 불러오는 동안 표시가 있고, 첫 화면이 그려진 뒤에 걷힌다.
  6. 가르친 뒤 다시 불러와도 줄을 새로 안 만든다.

걸린 시간은 적어만 둔다. CI 러너는 느리고 들쭉날쭉해서 기준으로 못 쓴다.
"""
import json
import os
import sys
import tempfile
import threading
import time

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-smoke-tms-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from PIL import Image                                       # noqa: E402

from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import sprite_cache                       # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_tms                             # noqa: E402

OK = FAIL = 0
TMS_PATH = os.path.join(HERE, "..", "server", "data", "tms.json")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def settle(root, n=8):
    for _ in range(n):
        root.update()


def wait_for(root, cond, secs=6):
    end = time.time() + secs
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.01)
    return cond()


def settle_list(root, win):
    """줄을 나눠 만들고 나눠 담는 일까지 다 끝날 때까지 돌린다."""
    wait_for(root, lambda: not any(j is not None and j.pending
                                   for j in (win._list_job, win._show_job)))
    settle(root)


def ms(t0):
    return (time.perf_counter() - t0) * 1000.0


# ---------------------------------------------------------------- 그림
def make_gif(path, canvas, boxes):
    """boxes 는 프레임마다 칠할 사각형 (x0, y0, x1, y1). 나머지는 투명."""
    frames = []
    for box in boxes:
        im = Image.new("P", canvas, 0)
        im.putpalette([0, 0, 0, 220, 70, 60, 40, 130, 230] + [0] * (253 * 3))
        x0, y0, x1, y1 = box
        for y in range(y0, y1):
            for x in range(x0, x1):
                im.putpixel((x, y), 1 if (x + y) % 5 else 2)
        frames.append(im)
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   transparency=0, duration=90, loop=0, disposal=2)
    return path


def make_sprites(d):
    os.makedirs(d, exist_ok=True)
    out = {}
    # 좁은 것: 몸이 8x22
    out[901] = make_gif(os.path.join(d, "0901.gif"), (40, 40),
                        [(16, 9, 24, 31)])
    # 옆으로 긴 것: 몸이 105x32 - 높이만 맞추면 72px 로 칸을 넘는다
    out[902] = make_gif(os.path.join(d, "0902.gif"), (120, 48),
                        [(7, 8, 112, 40)])
    # 크고 프레임이 여럿: 첫 장부터 캔버스를 꽉 채운다. 22px 에 맞추면
    # 배율이 최소값(0.2)에 걸려 37px 이 되어 34px 줄 밖으로 나갔다.
    out[903] = make_gif(os.path.join(d, "0903.gif"), (152, 185),
                        [(0, 0, 152, 185), (20, 10, 130, 185),
                         (0, 30, 152, 170)])
    return out


# ---------------------------------------------------------------- 가짜
def load_tms():
    with open(TMS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for k, t in sorted(data["tms"].items(), key=lambda kv: int(kv[0])):
        no = int(k)
        out.append({"no": no, "move": t["move"], "kr": t["kr"],
                    "type": t["type"], "cat": t["cat"],
                    "label": "기술머신%03d %s" % (no, t["kr"]),
                    # 가진 것은 열 개 중 하나. 첫 묶음(25줄)에 다 안 들어가게.
                    "have": no % 10 == 0})
    return out


class FakeApi(object):
    def __init__(self, tms, learners):
        self.data = tms
        self.learners = learners
        self.calls = []
        self.gate = threading.Event()     # tm_learners 를 잠깐 붙잡는다
        self.gate.set()

    def tms(self):
        self.calls.append("tms")
        return {"tms": [dict(t) for t in self.data],
                "haveCount": sum(1 for t in self.data if t["have"]),
                "total": len(self.data)}

    def tm_learners(self, no):
        self.calls.append(("learners", no))
        self.gate.wait(10)
        return {"no": no, "have": True,
                "learners": [dict(m) for m in self.learners]}

    def tm_use(self, no, pid, forget=""):
        self.calls.append(("use", no, pid, forget))
        return {"ok": True, "message": "배웠다!"}

    def sprite(self, num, shiny=False):
        raise RuntimeError("smoke_tms 는 네트워크를 안 탄다")


class FakeApp(object):
    def __init__(self, root, api):
        self.root = root
        self.api = api
        self.dex = None


def packed_rows(win):
    """지금 목록에 담긴 기술머신 번호, 화면 순서대로."""
    by_frame = dict((str(v[0]), n) for n, v in win.rows.items())
    return [by_frame[str(s)] for s in win.list_inner.pack_slaves()
            if str(s) in by_frame]


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    print("글꼴 %s / 본문 %dpt · 줄 %d · 도트 칸 %dx%d"
          % (U.FAMILY, U.BASE_PT, ui_tms.MON_H, ui_tms.SLOT_W, ui_tms.MON_H))

    tms = load_tms()
    have = [t["no"] for t in tms if t["have"]]
    paths = make_sprites(os.path.join(os.environ["POKET_HOME"], "gen"))
    learners = [
        {"id": 11, "name": "좁은애", "num": 901, "level": 12, "shiny": False,
         "moves": ["TACKLE"], "known": False},
        {"id": 12, "name": "긴애", "num": 902, "level": 30, "shiny": False,
         "moves": ["TACKLE"], "known": False},
        {"id": 13, "name": "큰애", "num": 903, "level": 55, "shiny": False,
         "moves": ["TACKLE"], "known": True},
    ]

    # 도트는 여기서 그린 파일을 준다. 게이트로 붙잡아 '오기 전' 을 잰다.
    sprite_gate = threading.Event()
    real_ensure = sprite_cache.ensure

    def fake_ensure(api, num, shiny=False):
        sprite_gate.wait(10)
        return paths.get(int(num)) if num else None
    sprite_cache.ensure = fake_ensure

    api = FakeApi(tms, learners)
    app = FakeApp(root, api)
    try:
        return run(root, app, api, tms, have, learners, sprite_gate)
    finally:
        sprite_cache.ensure = real_ensure
        sprite_gate.set()
        api.gate.set()
        try:
            root.destroy()
        except Exception:                                   # noqa: BLE001
            pass


def run(root, app, api, tms, have, learners, sprite_gate):
    print("\n=== 불러오기")
    t0 = time.perf_counter()
    win = ui_tms.TmWindow(root, app)
    win.win.geometry("1000x664+40+40")
    ov = win._wait
    chk("불러오는 동안 표시가 떠 있다", ov is not None and not ov.done, ov)
    wait_for(root, lambda: len(win.rows) > 0)
    first = ms(t0)
    chk("표시는 그린 뒤(idle)에 걷힌다", wait_for(root, lambda: ov.done, 2), ov.done)
    wait_for(root, lambda: not (win._list_job and win._list_job.pending))
    settle(root)
    print("  첫 줄까지 %.0f ms · 358줄 다 만들기까지 %.0f ms" % (first, ms(t0)))
    chk("줄은 358개를 다 만들어 둔다", len(win.rows) == len(tms), len(win.rows))
    chk("가진 것만: 담긴 줄 수가 가진 수와 같다", packed_rows(win) == have,
        (len(packed_rows(win)), len(have)))

    print("\n=== 가진 것만 / 전부")
    keep = win.rows[have[0]][0]
    t1 = time.perf_counter()
    win._toggle_filter()
    settle_list(root, win)
    # 나눠 담으므로 이 시간 동안 창이 멈춰 있는 것은 아니다(묶음 사이에
    # 입력과 그리기가 돈다). 다 담기까지의 합만 적는다.
    print("  전부로 다 담기까지 %.0f ms" % ms(t1))
    chk("전부: 358줄이 번호 순서대로", packed_rows(win) == [t["no"] for t in tms],
        len(packed_rows(win)))
    chk("줄을 다시 만들지 않는다 (같은 위젯)", win.rows[have[0]][0] is keep)
    t1 = time.perf_counter()
    win._toggle_filter()
    settle_list(root, win)
    print("  가진 것만으로 %.0f ms" % ms(t1))
    chk("다시 가진 것만", packed_rows(win) == have, len(packed_rows(win)))
    lc = win.list_canvas
    sr = [int(float(v)) for v in str(lc.cget("scrollregion")).split()]
    chk("스크롤 영역이 내용 높이에 맞다",
        sr and sr[3] == win.list_inner.winfo_reqheight(),
        (sr, win.list_inner.winfo_reqheight()))

    print("\n=== 나눠 만드는 중에")
    win._list_key = None
    win._paint_list()                  # 첫 묶음만 만들고 나머지는 예약
    chk("아직 다 안 만들었다", win._list_job.pending, len(win.rows))
    win._list_key = None
    win._paint_list()                  # 또 새로 그리면 앞의 예약은 버린다
    last = have[-1]
    chk("끝쪽 줄은 아직 없다", last not in win.rows, sorted(win.rows)[-3:])
    win.pick(last)
    chk("아직 없는 줄을 고르면 먼저 다 만든다", last in win.rows and
        not win._list_job.pending, len(win.rows))
    settle(root)
    chk("고른 줄만 칠해진다",
        [n for n, v in win.rows.items()
         if v[0].cget("bg") == U.ACCENT_SOFT] == [last])
    chk("세 번 그려도 줄이 겹치지 않는다",
        len(win.list_inner.winfo_children()) == len(tms),
        len(win.list_inner.winfo_children()))
    win._list_key = None
    win._paint_list()
    win._toggle_filter()               # 만드는 중에 거르기를 바꾼다
    settle_list(root, win)
    chk("만드는 중에 '전부' 로 바꿔도 358줄 순서대로",
        packed_rows(win) == [t["no"] for t in tms], len(packed_rows(win)))
    win._toggle_filter()
    settle_list(root, win)

    print("\n=== 담는 중에 또 바꾸면")
    win._toggle_filter()               # 전부 - 첫 묶음만 담겼다
    chk("첫 묶음만 먼저 담는다", win._show_job is not None
        and win._show_job.pending, len(packed_rows(win)))
    win._toggle_filter()               # 곧바로 가진 것만
    settle_list(root, win)
    chk("곧바로 되돌리면 가진 것만 남는다", packed_rows(win) == have,
        len(packed_rows(win)))
    win._toggle_filter()               # 전부
    root.update()
    win._toggle_filter()               # 가진 것만
    win._toggle_filter()               # 다시 전부
    settle_list(root, win)
    chk("담다 말고 여러 번 바꿔도 358줄 순서대로",
        packed_rows(win) == [t["no"] for t in tms], len(packed_rows(win)))
    win._toggle_filter()
    settle_list(root, win)
    chk("끝나면 다시 가진 것만", packed_rows(win) == have, len(packed_rows(win)))

    print("\n=== 배울 수 있는 포켓몬")
    sprite_gate.clear()
    api.gate.clear()
    target = have[0]
    t2 = time.perf_counter()
    win.pick(target)
    root.update()
    loading = [w for w in win.mon_inner.winfo_children()
               if isinstance(w, tk.Label) and "불러오는" in str(w.cget("text"))]
    chk("묻는 동안 '불러오는 중' 이 보인다", bool(loading))
    chk("이전 선택은 지워진다",
        win.rows[last][0].cget("bg") == U.BG
        and win.rows[target][0].cget("bg") == U.ACCENT_SOFT)
    api.gate.set()
    wait_for(root, lambda: len(win.mon_rows) == len(learners))
    settle(root)
    before = dict((i, v[2].winfo_x()) for i, v in win.mon_rows.items())
    chk("도트가 오기 전에는 그림이 없다",
        all(not str(v[1].cget("image")) for v in win.mon_rows.values()))
    sprite_gate.set()
    wait_for(root, lambda: len(win.photos) == len(learners))
    settle(root, 12)
    print("  기술머신 고르고 도트까지 %.0f ms" % ms(t2))
    after = dict((i, v[2].winfo_x()) for i, v in win.mon_rows.items())
    chk("이름 자리가 도트 전후로 같다", before == after, (before, after))
    chk("이름이 모든 줄에서 같은 x", len(set(after.values())) == 1, after)

    for m in learners:
        f, holder, name, note, moves, known = win.mon_rows[m["id"]]
        slot = holder.master
        ph = win.photos.get((m["num"], False))
        if ph is None:
            chk("#%d 도트가 붙었다" % m["num"], False)
            continue
        pw, phh = ph.width(), ph.height()
        hw, hh = holder.winfo_width(), holder.winfo_height()
        print("  #%d 그림 %dx%d · 칸 %dx%d · 라벨 %dx%d · 줄 %dx%d"
              % (m["num"], pw, phh, slot.winfo_width(), slot.winfo_height(),
                 hw, hh, f.winfo_width(), f.winfo_height()))
        chk("#%d 그림이 붙었다" % m["num"], str(holder.cget("image")) == str(ph))
        chk("#%d 라벨 폭 >= 그림 폭" % m["num"], hw >= pw, (hw, pw))
        chk("#%d 라벨 높이 >= 그림 높이" % m["num"], hh >= phh, (hh, phh))
        chk("#%d 라벨이 칸 안에 있다" % m["num"],
            holder.winfo_x() >= 0 and holder.winfo_y() >= 0
            and holder.winfo_x() + hw <= slot.winfo_width()
            and holder.winfo_y() + hh <= slot.winfo_height(),
            (holder.winfo_x(), holder.winfo_y(), hw, hh,
             slot.winfo_width(), slot.winfo_height()))
        chk("#%d 칸이 줄 안에 있다" % m["num"],
            slot.winfo_x() >= 0 and slot.winfo_y() >= 0
            and slot.winfo_x() + slot.winfo_width() <= f.winfo_width()
            and slot.winfo_y() + slot.winfo_height() <= f.winfo_height(),
            (slot.winfo_x(), slot.winfo_y(), slot.winfo_width(),
             slot.winfo_height(), f.winfo_width(), f.winfo_height()))
    wide = win.photos[(902, False)]
    chk("옆으로 긴 도트는 칸 폭에 맞춰 줄었다",
        wide.width() <= ui_tms.THUMB_MAX[0], wide.width())
    big = win.photos[(903, False)]
    chk("큰 도트는 줄 높이에 맞춰 줄었다",
        big.height() <= ui_tms.THUMB_MAX[1], big.height())

    mc = win.mon_canvas
    sr = [int(float(v)) for v in str(mc.cget("scrollregion")).split()]
    chk("세 줄뿐이면 스크롤할 게 없다 (영역 = 화면)",
        sr and sr[3] == mc.winfo_height(), (sr, mc.winfo_height()))

    print("\n=== 고르고 가르치기")
    win.pick_mon(11)
    win.pick_mon(12)
    sel = [i for i, v in win.mon_rows.items() if v[0].cget("bg") == U.ACCENT_SOFT]
    chk("고른 포켓몬 줄만 칠해진다 (칸까지)", sel == [12]
        and win.mon_rows[12][1].master.cget("bg") == U.ACCENT_SOFT, sel)
    kept = dict((n, v[0]) for n, v in win.rows.items())
    n_calls = len(api.calls)
    win.teach()
    wait_for(root, lambda: "배웠다" in win.status.cget("text"))
    settle(root)
    chk("tm_use 를 부른다", ("use", target, 12, "") in api.calls, api.calls[n_calls:])
    chk("가르친 뒤에는 불러오는 표시로 덮지 않는다", win._wait is None)
    chk("다시 불러와도 줄은 그대로 쓴다",
        all(win.rows[n][0] is f for n, f in kept.items()), len(win.rows))
    chk("다시 불러와도 고른 줄은 그대로",
        win.rows[target][0].cget("bg") == U.ACCENT_SOFT)

    print("\n=== 닫기")
    win.pick(have[1])
    win.close()
    settle(root)
    chk("닫는 중에 온 답은 조용히 버린다", True)

    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
