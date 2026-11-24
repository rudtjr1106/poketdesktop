# -*- coding: utf-8 -*-
"""배틀타워 탭 검사 (시즌 7).

    python client/test_tower_ui.py
    python client/run_as_windows.py client/test_tower_ui.py

**창을 진짜로 띄운다.** 관장 화면 검사의 가짜 api 에 배틀타워 쪽 길만 얹었다 - 판은 서버와 같은
엔진(common/trainer_battle)이 이 프로세스에서 돌고, 층 자료는 서버가 쓰는 server/data/tower.json 그대로다.
응답 모양은 server/app/tower.py 의 overview / card 와 같다.

## 무엇을 못 박나

  1. 허브의 모험 묶음에 '배틀타워' 탭이 있다 (관장 다음).
  2. 층 목록: 50층, 위가 높은 층. 열면 내가 다음에 오를 층이 골라져 있다.
  3. 층 카드: 층 이름 · 트레이너 · 상대의 종과 레벨 · 처음 한 번 보상. 기술 · 도구는 안 보인다.
  4. 잠긴 층은 보상만 보이고 도전 단추가 꺼져 있다 - **서버에 카드를 묻지도 않는다** (409 가 온다).
  5. 도전하면 관장 배틀 창이 그대로 뜬다. 창 제목 · 끝 단추 · 닫기 물음만 배틀타워 것이다
     (관장 창의 기본 글은 그대로 남는다).
  6. 이기고 닫으면 목록이 다시 온다 - 그 층은 ✓, 다음 층이 열린다.
  7. 닫힌 시즌과 **옛 서버(404)** 는 같은 글 "배틀타워는 시즌 7에 열립니다." 로 보인다 (앱이 서버보다 먼저 나간다).
"""
import json
import os
import random
import sys
import tempfile

os.environ.setdefault("POKET_HOME", os.path.join(tempfile.gettempdir(), "poket-test-tower"))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

import test_gym_ui as TG                                    # noqa: E402
from common import pokelogic as P                           # noqa: E402
from common import trainer_battle as TB                     # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_gym_battle as GB                # noqa: E402
from poketdesktop import ui_hub                             # noqa: E402
from poketdesktop.api import ApiError                       # noqa: E402
from test_boss_ui import fight_to_end, texts                # noqa: E402
from test_learn_dialog import squeezed                      # noqa: E402

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


def all_texts(w):
    """창 안의 글 전부 - 라벨과, 캔버스에 그린 글자까지 (화면 테마는 배틀 창의 결과 칸을 캔버스에 그린다)."""
    out = list(texts(w))

    def walk(x):
        for c in x.winfo_children():
            if isinstance(c, tk.Canvas):
                out.extend(c.itemcget(i, "text") for i in c.find_all() if c.type(i) == "text" and c.itemcget(i, "text"))
            walk(c)
    walk(w)
    return out


class TowerApi(TG.FakeApi):
    """관장 검사의 가짜 api + 배틀타워. 진행(top)을 서버처럼 들고 있다."""

    def __init__(self, dex, gyms, kmap, party, tower, items):
        TG.FakeApi.__init__(self, dex, gyms, kmap, party)
        self.floors = dict((f["floor"], f) for f in tower["floors"])
        self.items = items
        self.top = 0
        self.mode = "open"           # open / closed (시즌 6) / 404 (배틀타워를 모르는 옛 서버)
        self.fight = None            # 지금 판의 층

    # ---- 응답 모양은 server/app/tower.py 와 같다 ----
    def _lines(self, reward):
        lines = ["상금 %s원" % format(reward["money"], ",")]
        lines += ["%s ×%d" % (self.items[iid]["kr"], n) for iid, n in reward["items"]]
        return lines + (["전설의 포켓몬 알"] if reward.get("egg") else [])

    def _state(self, n):
        return "cleared" if n <= self.top else ("next" if n == self.top + 1 else "locked")

    def _gate(self):
        if self.mode == "404":
            raise ApiError("Not Found", 404)

    def tower(self):
        self.calls.append("tower")
        self._gate()
        if self.mode == "closed":
            return {"open": False, "from": 7}
        floors = [{"floor": n, "name": f["name"], "kind": f["kind"], "level": f["trainer"]["level"],
                   "size": len(f["trainer"]["team"]), "state": self._state(n), "reward": self._lines(f["reward"]),
                   "bestTurns": 9 if n <= self.top else None} for n, f in sorted(self.floors.items())]
        busy = self.fight is not None and self.tb is not None and not self.tb.over
        return {"open": True, "from": 7, "total": len(floors), "top": self.top, "floors": floors,
                "active": {"id": 1, "floor": self.fight} if busy else None}

    def tower_floor(self, n):
        self.calls.append("tower_floor:%d" % n)
        self._gate()
        if n > self.top + 1:
            raise ApiError("아직 오를 수 없는 층입니다. %d층부터 도전하세요." % (self.top + 1), 409)
        f = self.floors[n]
        t = f["trainer"]
        team = [{"species": m["species"], "num": self.dex.get(m["species"])["num"],
                 "kr": self.dex.get(m["species"])["kr"], "level": m["level"],
                 "types": [self.dex.type_name(x) for x in self.dex.get(m["species"])["types"]]} for m in t["team"]]
        return {"floor": n, "name": f["name"], "kind": f["kind"], "state": self._state(n),
                "trainer": {"id": t["id"], "name": t["name"], "role": t["role"], "sprite": t["sprite"],
                            "level": t["level"]},
                "team": team, "reward": self._lines(f["reward"]),
                "wins": 1 if n <= self.top else 0, "bestTurns": 9 if n <= self.top else None}

    def tower_start(self, n):
        self.calls.append("tower_start:%d" % n)
        if self.tb and not self.tb.over and self.fight is not None:
            return self._out([], {"resumed": True})
        self.fight = n
        self.region = "tower:%d" % n
        # 검사가 빨리 끝나게 상대 레벨은 낮춰 둔다 (종 · 마릿수 · 순서는 자료와 같다)
        t = dict(self.floors[n]["trainer"])
        t["team"] = [dict(m, level=5) for m in t["team"]]
        self.tb = TB.TrainerBattle(self.dex, [dict(m) for m in self.party], t, random.Random(7))
        return self._out(self.tb.start())

    def gym_act(self, bid, kind, move="", slot=-1, mega=False, **kw):
        if kind == "move":
            ev = self.tb.act("move", move, mega=mega)
        else:
            ev = self.tb.act(kind, slot) if kind != "forfeit" else self.tb.act("forfeit")
        extra = {}
        if self.tb.over and self.tb.result == "won" and self.fight is not None:
            first = self.fight > self.top
            self.top = max(self.top, self.fight)
            lines = (self._lines(self.floors[self.fight]["reward"]) + ["%d층이 열렸다." % (self.fight + 1)]
                     if first else ["이미 오른 층이다. 보상은 처음 한 번뿐이다."])
            extra["reward"] = {"tower": True, "floor": self.fight, "first": first, "lines": lines,
                               "top": self.top, "total": len(self.floors), "money": 2000}
        return self._out(ev, extra)


def main():
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    with open(os.path.join(DATA, "gyms.json"), encoding="utf-8") as f:
        gyms = json.load(f)
    with open(os.path.join(DATA, "korea_map.json"), encoding="utf-8") as f:
        kmap = json.load(f)
    with open(os.path.join(DATA, "tower.json"), encoding="utf-8") as f:
        tower = json.load(f)
    with open(os.path.join(DATA, "items.json"), encoding="utf-8") as f:
        items = dict(json.load(f)["items"])

    print("=== 허브 ===")
    from poketdesktop import ui_tower as T
    row = next((t for t in ui_hub.TABS if t[0] == "tower"), None)
    chk("탭 '배틀타워' 가 있다", row is not None and row[1] == "배틀타워" and row[2] is T.TowerWindow and row[3] is True, row)
    chk("모험 묶음에서 관장 다음", ui_hub.GROUP_TABS["adventure"] == ["gym", "tower", "expedition", "rank"],
        ui_hub.GROUP_TABS["adventure"])
    chk("마이페이지는 여전히 맨 끝", ui_hub.TABS[-1][0] == "my")

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
    orig_later = GB.GymBattleWindow.later
    GB.GymBattleWindow.later = lambda self, ms, fn: orig_later(self, max(1, ms // 10), fn)

    party = [TG.mon(dex, "GARCHOMP", 100, ["EARTHQUAKE", "DRAGONCLAW"], "ROUGHSKIN", 12),
             TG.mon(dex, "GYARADOS", 100, ["WATERFALL", "ICEFANG"], "INTIMIDATE", 13)]
    api = TowerApi(dex, gyms, kmap, party, tower, items)
    app = TG.FakeApp(root, api, dex)

    print("\n=== 층 목록 ===")
    api.top = 2                         # 2층까지 오른 사람
    w = T.TowerWindow(root, app)
    w.win.geometry("980x640+20+20")
    TG.pump(root, lambda: w.data is not None and w.card_floor is not None)
    root.update_idletasks()
    chk("50층이 목록에", len(w.rows) == 50, len(w.rows))
    chk("위가 높은 층", w.order[0] == 50 and w.order[-1] == 1, (w.order[0], w.order[-1]))
    chk("상태: 2층까지 이김 · 3층 다음 · 4층부터 잠김",
        [w.rows[n]["state"] for n in (1, 2, 3, 4, 50)] == ["cleared", "cleared", "next", "locked", "locked"])
    chk("머리줄에 내 기록", "2층 / 50층" in w.record.cget("text"), w.record.cget("text"))
    chk("  다음 큰 보상 (5층 관문)", "5층" in w.goal.cget("text") and "이상한사탕" in w.goal.cget("text"), w.goal.cget("text"))
    chk("열면 다음 층이 골라져 있다", w.selected == 3 and w.card_floor == 3, (w.selected, w.card_floor))
    chk("눌린 위젯이 없다", not squeezed(w.win), squeezed(w.win)[:3])

    print("\n=== 층 카드 ===")
    seen = "\n".join(texts(w.card))
    chk("층 이름 · 트레이너", "3층" in seen and "물가" in seen and "이슬" in seen, seen[:120])
    chk("상대의 종과 레벨", "아쿠스타" in seen and "Lv.34" in seen, seen)
    chk("처음 한 번 보상", "2,000원" in seen and "몬스터볼 ×5" in seen, seen)
    chk("기술 · 도구 · 특성은 안 보인다", not any(k in seen for k in ("파도타기", "자연회복", "먹다남은음식")), seen)
    chk("단추: 도전하기", w.go_btn is not None and w.go_btn.label.cget("text") == "도전하기" and w.go_btn.enabled)
    w.select(1)
    TG.pump(root, lambda: w.card_floor == 1)
    seen = "\n".join(texts(w.card))
    chk("이긴 층: 다시 도전 (보상은 받았다고 적는다)", w.go_btn.label.cget("text") == "다시 도전" and w.go_btn.enabled
        and "받았" in seen, seen)

    print("\n=== 잠긴 층 ===")
    api.calls[:] = []
    w.select(5)
    TG.pump(root, lambda: w.card_floor == 5)
    seen = "\n".join(texts(w.card))
    chk("이름 · 보상만 보인다", "노말의 벽" in seen and "이상한사탕 ×1" in seen and "4,000원" in seen, seen)
    chk("도전 단추가 꺼져 있다", w.go_btn is not None and not w.go_btn.enabled)
    chk("어디부터 올라야 하는지 알린다", "3층" in seen, seen)
    chk("서버에 카드를 묻지 않는다", "tower_floor:5" not in api.calls, api.calls)
    w.challenge(5)
    root.update()
    chk("눌러도 판이 안 열린다", w.battle is None and not any(c.startswith("tower_start") for c in api.calls), api.calls)

    print("\n=== 도전 ===")
    w.select(3)
    TG.pump(root, lambda: w.card_floor == 3)
    w.challenge(3)
    TG.pump(root, lambda: w.battle is not None)
    b = w.battle
    chk("관장 배틀 창이 뜬다", isinstance(b, GB.GymBattleWindow) and b.alive)
    chk("창 제목은 배틀타워", b.win.title() == "배틀타워 3층 — 이슬", b.win.title())
    chk("끝 단추 · 닫기 물음도 배틀타워", b.DONE_TEXT == "타워로 돌아가기" and "배틀타워" in b.LEAVE_TEXT,
        (b.DONE_TEXT, b.LEAVE_TEXT))
    chk("관장 창의 기본 글은 그대로", GB.GymBattleWindow.DONE_TEXT == "지도로 돌아가기"
        and GB.GymBattleWindow.TITLE_FMT == "관장 도전 — %s" and "지도" in GB.GymBattleWindow.LEAVE_TEXT)
    chk("한 번 더 눌러도 창은 하나", (w.challenge(3), w.battle is b)[1])
    chk("끝까지 싸워 이긴다", fight_to_end(root, b) and b.view["result"] == "won", b.view.get("result"))
    TG.pump(root, lambda: b.reward is not None, 10)
    root.update()
    seen = "\n".join(all_texts(b.win))
    chk("결과 칸에 서버가 준 줄", "상금 2,000원" in seen and "4층이 열렸다." in seen, seen[-200:])
    chk("  끝 단추가 '타워로 돌아가기'", "타워로 돌아가기" in seen and "지도로 돌아가기" not in seen, seen[-120:])
    b.close()
    TG.pump(root, lambda: w.battle is None and w.rows.get(4, {}).get("state") == "next")
    chk("닫으면 목록이 다시 온다: 3층 ✓, 4층 다음", w.rows[3]["state"] == "cleared" and w.rows[4]["state"] == "next"
        and "3층 / 50층" in w.record.cget("text"), (w.rows[3]["state"], w.rows[4]["state"]))
    chk("다음 층이 골라진다", w.selected == 4, w.selected)

    print("\n=== 하던 판 ===")
    w.challenge(4)
    TG.pump(root, lambda: w.battle is not None)
    w.battle.close()                    # 끝내지 않고 창만 닫는다 - 판은 서버에 남는다
    TG.pump(root, lambda: w.battle is None and (w.data or {}).get("active"))
    TG.pump(root, lambda: w.card_floor == 4)
    chk("단추가 '이어서 하기' 가 된다", w.go_btn.label.cget("text") == "이어서 하기", w.go_btn.label.cget("text"))
    api.tb.act("forfeit")
    api.fight = None

    print("\n=== 닫힌 시즌 · 옛 서버 ===")
    api.mode = "closed"
    w.reload()
    TG.pump(root, lambda: w.closed)
    chk("닫힌 시즌", "배틀타워는 시즌 7에 열립니다." in "\n".join(texts(w.win)) and not w.rows, texts(w.win)[:4])
    api.mode = "open"
    w.reload()
    TG.pump(root, lambda: not w.closed and len(w.rows) == 50)
    chk("열리면 목록이 돌아온다", len(w.rows) == 50 and not w.closed)
    api.mode = "404"
    w.reload()
    TG.pump(root, lambda: w.closed)
    chk("옛 서버(404)도 같은 글 (오류로 안 보인다)", "배틀타워는 시즌 7에 열립니다." in "\n".join(texts(w.win))
        and not w.rows, texts(w.win)[:4])
    w.close()

    print("\n=== 탭 안에 넣었을 때 ===")
    api.mode = "open"
    holder = tk.Toplevel(root)
    holder.geometry("980x640+40+40")
    frame = tk.Frame(holder)
    frame.pack(fill="both", expand=True)
    e = T.TowerWindow(root, app, frame)
    e.win.pack(fill="both", expand=True)
    TG.pump(root, lambda: e.data is not None and e.card_floor is not None)
    root.update_idletasks()
    chk("탭 안에서도 그려진다", U.is_embedded(e.win) and len(e.rows) == 50 and e.selected == 4, len(e.rows))
    n0 = api.calls.count("tower")
    e.on_shown()
    root.update()
    chk("탭을 다시 골라도 방금 불러온 것이면 그대로", api.calls.count("tower") == n0)
    e._loaded_at -= T.STALE_SEC + 5
    e.on_shown()
    TG.pump(root, lambda: api.calls.count("tower") > n0)
    chk("  오래된 것이면 다시 불러온다", api.calls.count("tower") > n0)
    e.close()

    chk("콜백 오류 없음", not errors, errors[:2])
    GB.GymBattleWindow.later = orig_later
    print("\n%d OK, %d FAIL" % (OK, FAIL))
    try:
        root.destroy()
    except tk.TclError:
        pass
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
