# -*- coding: utf-8 -*-
"""아르케의 여섯 봉인 (2.4.0) — 전설 배틀 창 검사.

    python client/test_arche_battle_ui.py
    python client/run_as_windows.py client/test_arche_battle_ui.py

**창을 진짜로 띄운다.** 서버는 안 띄운다 - 가짜 api 가 서버와 같은 엔진(common/trainer_battle)을 이 프로세스에서
돌리고, 볼 던지기 답(server/app/gym_routes 의 kind == "ball")은 약속된 꼴 그대로 만든다. 장소 그림은 진짜
arche_art 를 쓴다 (수수께끼 내용은 없다 - 장소 열쇠와 그림뿐).

## 무엇을 못 박나

  1. 일지 창이 준 자리 · 크기("WxH+X+Y") 그대로 뜨고, 제목은 '아르케 — <장 이름>'.
  2. 장면 바닥에 장소 그림(inside)이 깔리고, 창 크기를 바꿔도 새 크기로 다시 깔린다. 이름표는 그 위.
  3. 입장 장면: 창 전체를 덮고 돈다 · 누르면 건너뛴다 · 다 돌면 저절로 걷힌다. 걷히면 전설이 볼 없이
     나타나고 화면이 흔들리며 '<이름>의 울음소리가 <장소>을(를) 울렸다!'.
  4. '볼 던지기' 는 볼 메뉴(마스터볼 포함)를 열고, 고른 볼로 api.arche_ball 을 부른다.
  5. 놓치면 볼이 흔들리다 열리고, 전설의 턴을 재생한 뒤 명령 칸으로 돌아온다.
  6. 잡으면 '신난다! ... 을(를) 잡았다!' 와 결과 칸. 다음 자리가 있으면 '더 안쪽으로' → on_next(다음, 자리),
     닫혀도 on_close 는 부르지 않는다 (흐름이 다음 창으로 이어진다). 없으면 그 단추가 없다.
  7. 볼이 없다(409) 같은 거절은 그 말을 보이고 명령 칸으로 돌아온다.
"""
import io
import json
import os
import random
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-arche-battle-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from PIL import Image, ImageDraw                            # noqa: E402

from common import pokelogic as P                           # noqa: E402
from common import trainer_battle as TB                     # noqa: E402
from common.korean import natural                           # noqa: E402
from poketdesktop import arche_battle as AB                 # noqa: E402
from poketdesktop import ball_menu                          # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop.api import ApiError                       # noqa: E402
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
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((20, 14, 76, 90), fill=(150, 120, 90, 255))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def legend_trainer(dex, species, level):
    """server/app/boss.legend_trainer 와 같은 꼴 (트레이너가 없는 판 - 이름 칸에 포켓몬)."""
    sp = dex.get(species)
    return {"id": "legend:" + species, "name": sp["kr"], "role": "전설의 포켓몬", "sprite": None,
            "level": level, "wild": True,
            "team": [{"species": species, "level": level, "iv": P.IV_MAX, "evs": {}, "nature": "HARDY",
                      "ability": (sp.get("abil") or [None])[0], "moves": P.default_moveset(sp, level),
                      "held": None, "gender": "N"}]}


OPTS = [{"id": "POKEBALL", "kr": "몬스터볼", "count": 5, "mult": 1.0, "why": "", "best": False},
        {"id": "ULTRABALL", "kr": "하이퍼볼", "count": 2, "mult": 2.0, "why": "", "best": True},
        {"id": "MASTERBALL", "kr": "마스터볼", "count": 1, "mult": 255.0, "why": "", "best": False}]


class FakeApi(object):
    """서버 대신. /api/arche/battle 은 관장 판 _out 꼴 + {place, legend}, 볼은 계획서의 약속 그대로."""

    def __init__(self, dex, party):
        self.dex = dex
        self.party = party
        self.tb = None
        self.png = fake_sprite()
        self.balls_thrown = []
        self.catch = False              # 다음 볼이 잡히나 (마스터볼은 늘)
        self.next = None                # 잡았을 때 남은 자리 {chapter, slot}
        self.refuse = None              # 다음 볼을 거절하는 말 (409)

    def start(self, species="REGIROCK", events=True):
        self.tb = TB.TrainerBattle(self.dex, [dict(m) for m in self.party],
                                   legend_trainer(self.dex, species, 60), random.Random(5))
        evs = self.tb.start() if events else []
        if not events:
            self.tb.started = True
        return {"id": 7, "region": "arche:1:0", "rev": 1, "battle": self.tb.view(), "events": evs,
                "place": "cave", "legend": self.dex.get(species)["num"], "ballOptions": [dict(o) for o in OPTS]}

    def sprite(self, num, shiny=False):
        return self.png, ".png"

    def gym_sprite(self, key):
        return None

    def gym_battle(self):
        return {"id": 7, "battle": self.tb.view(), "events": []}

    def arche_ball(self, bid, ball, hour=-1):
        self.balls_thrown.append((bid, ball, hour))
        if self.refuse:
            msg, self.refuse = self.refuse, None
            raise ApiError(msg, 409)
        left = [dict(o, count=o["count"] - (1 if o["id"] == ball else 0)) for o in OPTS]
        if self.catch or ball == "MASTERBALL":
            self.tb.over = True
            self.tb.result = "caught"
            foe = self.tb.foe_team[0]
            out = {"caught": True, "shakes": 3, "ball": ball, "balls": 4, "where": "box",
                   "pokemon": {"id": 99, "species": foe.mon["species"], "level": foe.mon["level"]},
                   "message": "신난다! %s 을(를) 잡았다!" % foe.name, "battle": self.tb.view(),
                   "ballOptions": left}
            if self.next:
                out["next"] = dict(self.next)
            return out
        # 놓쳤다 - 전설만 한 턴 움직인다 (서버의 tb.act("pass") 대신 같은 꼴의 사건을 만든다)
        me = self.tb.me_team[self.tb.mi]
        me.hp = max(1, me.hp - 20)
        evs = [{"t": "move", "who": "foe", "move": "스톤샤워", "moveType": "ROCK", "cat": "physical",
                "text": "레지락의 스톤샤워!"},
               {"t": "hit", "who": "foe", "target": "me", "hp": me.hp}]
        self.tb.turn += 1
        return {"caught": False, "shakes": 2, "ball": ball, "balls": 4,
                "message": "아깝다! 조금만 더 하면 잡을 수 있었는데!", "events": evs,
                "battle": self.tb.view(), "ballOptions": left}


class FakeApp(object):
    def __init__(self, root, api, dex):
        self.root = root
        self.api = api
        self.dex = dex
        self.gym_battle = None
        self.settings = {}
        self.balls = 9
        self.trays = 0

    def notify(self, *_a):
        pass

    def want_learn(self, *_a):
        pass

    def request_sync(self):
        pass

    def refresh_tray(self):
        self.trays += 1


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


def bg_items(w):
    return w.cv.find_withtag("arche_bg")


def main():
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))

    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    callback_errors = []

    def on_callback_error(exc, val, tb):
        import traceback
        callback_errors.append("".join(traceback.format_exception(exc, val, tb))[-400:])
    root.report_callback_exception = on_callback_error

    party = [mon(dex, "GARCHOMP", 60, ["EARTHQUAKE", "DRAGONCLAW", "STONEEDGE", "SWORDSDANCE"], "ROUGHSKIN", 11),
             mon(dex, "GYARADOS", 60, ["WATERFALL", "ICEFANG", "CRUNCH", "DRAGONDANCE"], "INTIMIDATE", 12)]
    api = FakeApi(dex, party)
    app = FakeApp(root, api, dex)
    # 연출 대기를 1/10 로 (순서와 결과는 그대로)
    orig_later = AB.ArcheBattleWindow.later
    AB.ArcheBattleWindow.later = lambda self, ms, fn: orig_later(self, max(1, ms // 10), fn)
    said = []
    real_say = AB.ArcheBattleWindow.say
    AB.ArcheBattleWindow.say = lambda self, text: (said.append(text), real_say(self, text))[1]

    print("\n=== 자리 · 제목 · 배경 ===")
    closed = []
    w = AB.ArcheBattleWindow(app, api.start(events=False), "cave", geometry="900x640+40+50",
                             on_close=lambda: closed.append(1))
    root.update()
    pump(root, lambda: False, 0.2)
    chk("준 크기 그대로 뜬다", (w.win.winfo_width(), w.win.winfo_height()) == (900, 640),
        (w.win.winfo_width(), w.win.winfo_height()))
    chk("  준 자리를 건다", w.win.geometry().endswith("+40+50") or w._requested == (900, 640, 40, 50),
        (w.win.geometry(), getattr(w, "_requested", None)))
    chk("제목은 '아르케 — 돌의 문'", w.win.title() == "아르케 — 돌의 문", w.win.title())
    chk("앱의 배틀 칸에 든다", app.gym_battle is w)
    items = bg_items(w)
    chk("장면 바닥에 장소 그림이 깔린다", len(items) == 1, items)
    chk("  그림은 장면 맨 아래", items and w.cv.find_all()[0] == items[0], w.cv.find_all()[:3])
    bb = w.cv.bbox(items[0]) if items else None
    chk("  장면을 다 덮는다", bb and bb[2] - bb[0] >= w.sw - 1 and bb[3] - bb[1] >= w.sh - 1, (bb, w.sw, w.sh))
    chk("  그림을 쥐고 있다 (안 쥐면 사라진다)", w.photos.get("arche_bg") is not None)
    chk("  관장 장면의 바닥 사각형은 없다", not [i for i in w.cv.find_all() if w.cv.type(i) == "rectangle"
                                       and w.cv.bbox(i) and w.cv.bbox(i)[2] - w.cv.bbox(i)[0] >= w.sw - 1], "")
    chk("이름표는 그림 위", w.cv.find_all().index(w.box["me"]["bg"]) > w.cv.find_all().index(items[0]))
    chk("이어 하기: 명령 칸이 바로 선다", w.mode == "moves" and not w.busy, (w.mode, w.busy))
    chk("'볼 던지기' 단추가 있고 눌린다", "볼 던지기" in texts(w.win) and w.ball_btn.enabled, texts(w.win)[:12])
    chk("명령 칸에 눌린 위젯이 없다 (볼 단추를 더해도)", not squeezed(w.win), squeezed(w.win)[:4])
    chk("'기권' 대신 '도망치기'", "도망치기" in texts(w.win) and "기권" not in texts(w.win), "")

    old_sw = w.sw
    w.win.geometry("1040x720+40+50")
    root.update()
    w.zoom_apply()
    root.update()
    items = bg_items(w)
    bb = w.cv.bbox(items[0]) if items else None
    chk("창을 키우면 그림도 새 크기로 다시 깔린다", w.sw != old_sw and len(items) == 1 and bb
        and bb[2] - bb[0] >= w.sw - 1, (old_sw, w.sw, bb))
    chk("  '볼 던지기' 단추도 다시 선다", "볼 던지기" in texts(w.win), "")
    w.win.geometry("760x560+40+50")
    root.update()
    w.zoom_apply()
    root.update()
    chk("  줄인 창(단추 둘이 나란히)에서도 눌린 위젯이 없다", w.zoom < 1.0 and not squeezed(w.win)
        and "볼 던지기" in texts(w.win), (w.zoom, squeezed(w.win)[:4]))

    print("\n=== 볼 메뉴 ===")
    seen = {}
    real_popup = ball_menu.popup

    def fake_popup(root_, event, options, on_pick, on_close=None, **kw):
        seen.update(event=event, options=options, on_pick=on_pick, kw=kw)
        if on_close:
            on_close()
        return None
    ball_menu.popup = fake_popup
    try:
        w.ball_btn.command()
    finally:
        ball_menu.popup = real_popup
    ids = [o["id"] for o in seen.get("options") or []]
    chk("'볼 던지기' 는 볼 메뉴를 연다 (마스터볼 포함)", "MASTERBALL" in ids and "POKEBALL" in ids, ids)
    chk("  단추 옆에 뜬다", seen.get("event") is not None and seen["event"].x_root > 0, seen.get("event"))
    chk("  계속 던지기 줄은 없다", not seen.get("kw", {}).get("on_auto"), seen.get("kw"))
    rows = ball_menu.rows(seen["options"], lambda _i: None)
    chk("  마스터볼 줄이 보인다", any("마스터볼" in (r or {}).get("text", "") for r in rows), rows)

    print("\n=== 놓침 ===")
    said[:] = []
    turn0 = w.view.get("turn")
    seen["on_pick"]("POKEBALL")
    chk("고른 볼로 api.arche_ball", pump(root, lambda: api.balls_thrown, 5)
        and api.balls_thrown[-1][:2] == (w.bid, "POKEBALL"), api.balls_thrown)
    chk("  던지는 동안은 명령을 못 고른다", w.busy and not w.ball_btn.enabled, (w.busy, w.ball_btn.enabled))
    chk("  시각을 같이 보낸다", 0 <= api.balls_thrown[-1][2] <= 23, api.balls_thrown[-1])
    chk("놓치면 전설의 턴을 재생하고 명령 칸으로", pump(root, lambda: not w.busy and w.mode == "moves", 15),
        (w.busy, w.mode, said[-4:]))
    chk("  놓친 말을 보였다", any("아깝다" in (s or "") for s in said), said[:6])
    chk("  전설의 기술도 보였다", any("스톤샤워" in (s or "") for s in said), said[:8])
    chk("  판 상태를 서버 값으로", w.view.get("turn") == turn0 + 1 and w.shown["me"]["hp"] ==
        api.tb.me_team[api.tb.mi].hp, (w.view.get("turn"), w.shown["me"]))
    chk("  볼 개수를 맞춘다", app.balls == 4 and app.trays >= 1, (app.balls, app.trays))
    chk("  볼 목록도 서버 값으로", next(o for o in w.ball_opts if o["id"] == "POKEBALL")["count"] == 4,
        w.ball_opts)
    chk("  다시 볼을 던질 수 있다", w.ball_btn.enabled)
    chk("  전설이 다시 보인다", w.cv.itemcget(w.sprite["foe"], "state") != "hidden")

    print("\n=== 거절 (볼 없음) ===")
    api.refuse = "그 볼이 없습니다."
    said[:] = []
    w.throw("ULTRABALL")
    chk("거절 말을 보이고 명령 칸으로", pump(root, lambda: not w.busy, 5) and w.mode == "moves"
        and "그 볼이 없습니다." in said, (w.busy, said[-3:]))
    chk("  창은 살아 있다", w.alive)

    print("\n=== 잡음 (다음 자리 있음) ===")
    api.next = {"chapter": 1, "slot": 1}
    said[:] = []
    deeper = []
    w.on_next = lambda nxt, geom: deeper.append((nxt, geom))
    w.throw("MASTERBALL")
    chk("잡으면 결과 칸", pump(root, lambda: w.view.get("over") and not w.busy, 15), (w.view.get("result"), w.busy))
    chk("  '신난다! 레지락을 잡았다!'", any("신난다! 레지락을 잡았다!" in natural(s or "") for s in said), said[-4:])
    tx = texts(w.win)
    chk("  결과 칸에 잡은 글", any("잡았다" in t for t in tx), tx[:12])
    chk("  박스로 갔다고 적는다", any("박스" in t for t in tx), tx[:12])
    chk("  '더 안쪽으로' 단추", "더 안쪽으로" in tx, tx[:12])
    chk("  전설은 볼 안 (장면에서 사라짐)", not w.cv.itemcget(w.sprite["foe"], "image"), "")
    chk("  볼이 장면에 남는다", w.cv.find_withtag("arche_ball"), "")
    w.win.geometry("980x690+40+50")
    root.update()
    w.zoom_apply()
    root.update()
    chk("  창을 바꿔도 결과 칸 · 볼 · 그림이 남는다", "더 안쪽으로" in texts(w.win) and w.cv.find_withtag("arche_ball")
        and len(bg_items(w)) == 1, texts(w.win)[:8])
    w.next_btn.command()
    chk("'더 안쪽으로' → on_next(다음 자리, 지금 자리)", deeper and deeper[0][0] == {"chapter": 1, "slot": 1}
        and deeper[0][1].startswith("980x690"), deeper)
    chk("  창은 닫히고 on_close 는 안 부른다", not w.alive and not closed, (w.alive, closed))
    chk("  앱의 배틀 칸에서 빠진다", app.gym_battle is None)

    print("\n=== 입장 장면 (눌러서 건너뛰기) ===")
    api.next = None
    said[:] = []
    w2 = AB.ArcheBattleWindow(app, api.start(), "cave", geometry="880x620+60+60")
    e = w2._arche_entry
    thrown = []
    real_throw = w2.sendout.throw
    w2.sendout.throw = lambda who, *a, **k: (thrown.append(who), real_throw(who, *a, **k))[1]
    chk("입장 장면이 창을 덮는다", e is not None and e["cover"].winfo_exists(), e)
    chk("  그동안 명령을 못 고른다", w2.busy and not w2.ball_btn.enabled)
    root.update()
    chk("  덮개가 창 전체 크기", pump(root, lambda: e["cover"].winfo_width() >= 870, 3),
        (e["cover"].winfo_width(), e["cover"].winfo_height()))
    chk("  장면 그림이 돈다", pump(root, lambda: e["shown"] >= 2, 10), e["shown"])
    e["cover"].event_generate("<Button-1>", x=20, y=20)
    root.update()
    chk("누르면 건너뛴다", e["done"] and not e["cover"].winfo_exists(), e["done"])
    chk("  전설이 볼 없이 나타나 울음소리", pump(root, lambda: any("울음소리" in (s or "") for s in said), 10),
        said[-5:])
    cry = [s for s in said if "울음소리" in (s or "")]
    chk("  '레지락의 울음소리가 동굴을 울렸다!'", cry and natural(cry[0]) == "레지락의 울음소리가 동굴을 울렸다!", cry)
    chk("  그다음 기술을 고른다", pump(root, lambda: not w2.busy and w2.mode == "moves", 15), (w2.busy, w2.mode))
    chk("  전설은 볼에서 나오지 않는다 (내 포켓몬만)", "foe" not in thrown and "me" in thrown, thrown)
    chk("  흔들림이 끝나면 장면이 제자리", w2.cv.coords(bg_items(w2)[0])[:2] == [0.0, 0.0],
        w2.cv.coords(bg_items(w2)[0]))

    print("\n=== 잡음 (다음 자리 없음) ===")
    api.catch = True
    w2.throw("POKEBALL")
    chk("잡으면 결과 칸", pump(root, lambda: w2.view.get("over") and not w2.busy, 15), w2.view.get("result"))
    chk("  '더 안쪽으로' 는 없다", "더 안쪽으로" not in texts(w2.win), texts(w2.win)[:10])
    chk("  '일지로 돌아가기'", "일지로 돌아가기" in texts(w2.win), texts(w2.win)[:10])
    w2.close()
    api.catch = False

    print("\n=== 입장 장면 (끝까지) ===")
    said[:] = []
    w3 = AB.ArcheBattleWindow(app, api.start(), "volcano", geometry="880x620+60+60")
    e3 = w3._arche_entry
    chk("다 돌면 저절로 걷힌다", pump(root, lambda: e3["done"], 15), e3["shown"])
    chk("  장면을 다 틀었다", e3["shown"] >= 6, e3["shown"])
    chk("  화산 제목", w3.win.title() == "아르케 — 불의 산", w3.win.title())
    chk("  배경이 화산 그림", w3.place == "volcano")
    chk("  울음소리가 화산을 울렸다",
        pump(root, lambda: any("화산" in natural(s or "") and "울음소리" in (s or "") for s in said), 10), said[-4:])
    pump(root, lambda: not w3.busy, 10)
    w3.close()

    print("\n=== 입장 도중에 닫기 ===")
    w4 = AB.ArcheBattleWindow(app, api.start(), "abyss", geometry="880x620+60+60")
    root.update()
    w4.close()
    pump(root, lambda: False, 0.5)
    chk("닫으면 입장 장면도 멈춘다 (예외 없음)", not callback_errors, callback_errors[-1:])

    print("\n=== 볼 목록을 안 보낸 서버 ===")
    data = api.start(events=False)
    data.pop("ballOptions")
    w5 = AB.ArcheBattleWindow(app, data, "sky")
    root.update()
    opts = w5._ball_options()
    chk("가진 몬스터볼로 메뉴를 만든다", opts and opts[0]["id"] == "POKEBALL" and opts[0]["count"] == app.balls, opts)
    w5.close()

    AB.ArcheBattleWindow.later = orig_later
    AB.ArcheBattleWindow.say = real_say
    chk("콜백 예외가 없다", not callback_errors, callback_errors[-2:])
    root.destroy()
    print("\n%d OK, %d FAIL" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
