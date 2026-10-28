# -*- coding: utf-8 -*-
"""악당 출현 화면 검사 (시즌 4).

    python client/test_boss_ui.py
    python client/run_as_windows.py client/test_boss_ui.py

**창을 진짜로 띄운다.** 관장 화면 검사의 가짜 api 에 악당 쪽 길만 얹었다 - 판은 서버와 같은
엔진(common/trainer_battle)이 이 프로세스에서 돌고, 응답 모양은 server/app/boss.py 와 같다.

## 무엇을 못 박나

  1. 악당이 안 나타났으면 지도도 위쪽 단추도 그대로다.
  2. 나타나면 그 시·도가 **검게** 칠해지고 위쪽에 '악당 출현' 단추가 뜬다.
  3. 검은 곳을 누르면 그 시·도로 들어가는 대신 악당 창이 뜬다.
  4. 악당 창: 간부 셋의 상태(도전·잠김·이김), 전설은 다 이기기 전에는 '???'.
     창은 내용만큼이고 눌린 위젯이 없다.
  5. 승부를 열면 관장 배틀 창이 뜨고, 이기면 결과 칸에 서버가 준 줄이 그대로 나온다.
  6. 셋을 다 이기면 전설이 드러나고, 쓰러뜨리면 그 결과(알)가 창에 적힌다.
  7. 다 물리치면 지도가 원래 색으로 돌아오고 그 시·도로 다시 들어갈 수 있다.
"""
import json
import os
import random
import sys
import tempfile

os.environ.setdefault("POKET_HOME", os.path.join(tempfile.gettempdir(), "poket-test-boss"))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

import test_gym_ui as TG                                    # noqa: E402
from common import pokelogic as P                           # noqa: E402
from common import trainer_battle as TB                     # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_boss                            # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_gym                             # noqa: E402
from poketdesktop import ui_gym_battle as GB                # noqa: E402
from test_learn_dialog import squeezed                      # noqa: E402

OK = FAIL = 0
DATA = os.path.join(ROOT, "server", "data")
SIDO = "31"                     # 울산광역시
MEMBERS = ("mars", "jupiter", "saturn")
LEGEND = "DIALGA"


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class BossApi(TG.FakeApi):
    """관장 검사의 가짜 api + 악당 출현. 진행(stage)과 결과를 서버처럼 들고 있다."""

    def __init__(self, *a):
        TG.FakeApi.__init__(self, *a)
        self.on = False              # 악당이 나타났나
        self.stage = 0
        self.legend_done = False
        self.egg = None
        self.fight = None            # 지금 판의 자리 (0~2 간부, 3 전설)
        self.trainers = dict((t["id"], t) for t in self.gyms["trainers"])

    # ---- 응답 모양은 server/app/boss.py 의 brief / card 와 같다 ----
    def _brief(self):
        if not self.on:
            return {"active": False}
        return {"active": True, "day": "2026-10-17", "sido": SIDO, "sidoName": "울산광역시",
                "team": "갤럭시단", "stage": self.stage, "legend": self.legend_done,
                "done": self.legend_done, "endsIn": getattr(self, "ends_in", 5 * 3600 + 120)}

    def gym(self):
        out = TG.FakeApi.gym(self)
        out["boss"] = self._brief()
        if self.fight is not None and self.tb and not self.tb.over:
            out["active"] = {"id": 1, "region": "boss:2026-10-17:%d" % self.fight}
        return out

    def boss(self):
        self.calls.append("boss")
        if not self.on:
            return {"active": False}
        members = []
        for i, tid in enumerate(MEMBERS):
            t = self.trainers[tid]
            members.append({"id": tid, "name": t["name"], "role": t["role"], "sprite": t["sprite"],
                            "state": "won" if i < self.stage else ("next" if i == self.stage else "locked")})
        legend = {"open": self.stage >= 3, "done": self.legend_done, "egg": self.egg}
        if legend["open"]:
            sp = self.dex.get(LEGEND)
            legend.update({"species": LEGEND, "name": sp["kr"], "num": sp["num"],
                           "types": [self.dex.type_name(t) for t in sp["types"]]})
        busy = self.fight is not None and self.tb is not None and not self.tb.over
        return dict(self._brief(), teamId="galactic", members=members, legend=legend, eggRate=70,
                    battle={"id": 1} if busy else None)

    def _trainer(self):
        levels = sorted((m["level"] for m in self.party), reverse=True)
        if self.stage >= 3:
            sp = self.dex.get(LEGEND)
            return {"id": "legend:" + LEGEND, "name": sp["kr"], "role": "전설의 포켓몬", "sprite": None,
                    "level": levels[0], "wild": True,
                    "team": [{"species": LEGEND, "level": 5, "iv": 31, "evs": {}, "nature": "HARDY",
                              "ability": sp["abil"][0], "moves": ["SCRATCH"], "held": None, "gender": "N"}]}
        t = self.trainers[MEMBERS[self.stage]]
        # 검사가 빨리 끝나게 상대 레벨은 낮춰 둔다 (마릿수·순서는 서버와 같다)
        team = [dict(m, level=5, iv=31) for m in t["team"][:len(levels)]]
        return {"id": t["id"], "name": t["name"], "role": t["role"], "sprite": t["sprite"],
                "level": levels[0], "team": team}

    def boss_start(self):
        self.calls.append("boss_start")
        if self.tb and not self.tb.over and self.fight is not None:
            return self._out([], {"resumed": True})
        self.fight = min(self.stage, 3)
        self.region = "boss:2026-10-17:%d" % self.fight
        self.tb = TB.TrainerBattle(self.dex, [dict(m) for m in self.party], self._trainer(), random.Random(7))
        return self._out(self.tb.start())

    def gym_act(self, bid, kind, move="", slot=-1, mega=False, **kw):
        if kind == "move":
            ev = self.tb.act("move", move, mega=mega)
        else:
            ev = self.tb.act(kind, slot) if kind != "forfeit" else self.tb.act("forfeit")
        extra = {}
        if self.tb.over and self.tb.result == "won" and self.fight is not None:
            if self.fight < 3:
                self.stage += 1
                left = 3 - self.stage
                extra["reward"] = {"boss": True, "prize": 500, "stage": self.stage,
                                   "lines": ["상금 500원", "간부가 %d명 남았다." % left if left else
                                             "악당을 모두 물리쳤다! 전설의 포켓몬이 모습을 드러낸다..."]}
            else:
                self.legend_done, self.egg = True, 1
                extra["reward"] = {"boss": True, "egg": True, "legend": True,
                                   "lines": ["디아루가 이(가) 알을 남기고 사라졌다! 전설의 포켓몬 알을 얻었다."]}
        return self._out(ev, extra)


def fill_of(gw, code):
    return gw.cv.itemcget("s%s" % code, "fill")


def texts(w):
    out = []
    for c in w.winfo_children():
        if isinstance(c, tk.Label) and c.cget("text"):
            out.append(c.cget("text"))
        out.extend(texts(c))
    return out


def fight_to_end(root, b):
    """관장 배틀 창에서 끝까지 싸운다 (늘 첫 기술, 교체가 필요하면 첫 자리)."""
    for _ in range(80):
        TG.pump(root, lambda: not b.busy, 30)
        if b.view.get("over"):
            return True
        if b.view.get("needSwitch"):
            side = b.view["me"]
            slot = next(i for i, m in enumerate(side["team"]) if not m.get("fainted") and i != side["slot"])
            b.do_switch(slot) if hasattr(b, "do_switch") else b.switch_to(slot)
            continue
        side = b.view["me"]
        b.use_move(side["team"][side["slot"]]["moves"][0]["key"])
    return bool(b.view.get("over"))


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
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-400:])
    root.report_callback_exception = on_err
    print("글꼴 %s / 본문 %dpt (BASE_PT=%d)" % (U.FAMILY, U.FONT[1], U.BASE_PT))
    orig_later = GB.GymBattleWindow.later
    GB.GymBattleWindow.later = lambda self, ms, fn: orig_later(self, max(1, ms // 10), fn)

    party = [TG.mon(dex, "GARCHOMP", 100, ["EARTHQUAKE", "DRAGONCLAW"], "ROUGHSKIN", 12),
             TG.mon(dex, "GYARADOS", 100, ["WATERFALL", "ICEFANG"], "INTIMIDATE", 13)]
    api = BossApi(dex, gyms, kmap, party)
    app = TG.FakeApp(root, api, dex)

    print("=== 안 나타났을 때 ===")
    gw = ui_gym.GymWindow(root, app)
    gw.win.geometry("1040x700+20+20")
    TG.pump(root, lambda: gw.data is not None and gw.map is not None)
    root.update_idletasks()
    plain = fill_of(gw, SIDO)
    chk("지도는 평소 색", plain != ui_gym.BOSS_FILL and gw.boss_sido() is None, plain)
    chk("'악당 출현' 단추가 없다", not gw.boss_btn.holder.winfo_ismapped())

    print("\n=== 나타나기 전에 켜 둔 탭도 나타나면 안다 (2026-10-17 게시판 #252) ===")
    import datetime
    import time
    from poketdesktop import ui_hub
    kst = ui_gym.KST

    def at(h, m):
        return datetime.datetime(2026, 10, 18, h, m, tzinfo=kst)
    w = ui_gym.boss_watch_in
    chk("09:00 전이면 09:00 에 다시 본다", w({"active": False}, at(8, 30)) == 30 * 60 + 5, w({"active": False}, at(8, 30)))
    chk("  09:00 ~ 12:05 에는 5분마다", w({"active": False}, at(9, 40)) == ui_gym.BOSS_POLL
        and w({"active": False}, at(12, 3)) == ui_gym.BOSS_POLL)
    chk("  12:05 가 지나면 안 본다 (그날은 안 나온다)", w({"active": False}, at(12, 10)) is None
        and w({"active": False}, at(15, 0)) is None)
    chk("  이미 나와 있으면 안 본다", w({"active": True}, at(9, 40)) is None)
    chk("  서버가 오늘은 기간이 아니라고 하면 안 본다", w({"active": False, "event": False}, at(9, 40)) is None)
    armed = []
    real_arm, real_watch = gw._arm_reset, ui_gym.boss_watch_in
    gw._arm_reset = lambda sec: (armed.append(sec), real_arm(sec))[1]
    ui_gym.boss_watch_in = lambda boss, now=None: 300
    gw.reload()
    TG.pump(root, lambda: armed)
    chk("안 나와 있으면 자정보다 먼저 다시 물어보게 걸어 둔다", armed and 300 <= armed[-1] <= 330, armed)
    gw._arm_reset, ui_gym.boss_watch_in = real_arm, real_watch
    n0 = gw._loaded_at
    gw.on_shown()
    root.update()
    chk("탭을 다시 골라도 방금 불러온 것이면 그대로", gw._loaded_at == n0 and not gw._loading)
    gw._loaded_at = time.time() - ui_gym.STALE_SEC - 5
    ui_hub.HubWindow._shown(gw)                    # 허브가 이미 만든 탭을 다시 보여 줄 때 부르는 것
    TG.pump(root, lambda: gw._loaded_at > time.time() - 5)
    chk("  오래된 것이면 다시 불러온다", gw._loaded_at > time.time() - 5, gw._loaded_at)

    print("\n=== 나타났다 ===")
    api.on = True
    gw.reload()
    TG.pump(root, lambda: (gw.boss or {}).get("active"))
    root.update()
    chk("그 시·도가 검게 칠해진다", fill_of(gw, SIDO) == ui_gym.BOSS_FILL, fill_of(gw, SIDO))
    chk("  다른 시·도는 그대로다", all(fill_of(gw, s["code"]) != ui_gym.BOSS_FILL
                              for s in kmap["sido"] if s["code"] != SIDO))
    # 악당은 밤 11시에 떠난다 (1.11.0) - 자정('오늘 완료' 가 풀리는 때)보다 먼저면 그때 다시 불러온다
    armed = []
    real_arm = gw._arm_reset
    gw._arm_reset = lambda sec: (armed.append(sec), real_arm(sec))[1]
    api.ends_in = 600
    gw.reload()
    TG.pump(root, lambda: armed)
    chk("악당이 떠나는 시각이 먼저면 그때 다시 불러온다 (밤 11시)", armed[-1] == 600, armed)
    api.ends_in = 5 * 3600 + 120
    gw.reload()
    TG.pump(root, lambda: len(armed) >= 2)
    chk("  자정이 먼저면 자정에", armed[-1] == 3600, armed)
    gw._arm_reset = real_arm
    chk("위쪽에 '악당 출현 · 갤럭시단' 단추가 뜬다", gw.boss_btn.holder.winfo_ismapped()
        and "갤럭시단" in gw.boss_btn.label.cget("text"), gw.boss_btn.label.cget("text"))
    chk("  머리줄에 눌린 것이 없다", not squeezed(gw.win), squeezed(gw.win)[:3])
    chk("알림 글이 뜬다", "나타났다" in gw.status.cget("text"), gw.status.cget("text"))
    gw._hover_sido(SIDO, True)
    chk("올리면 맞서라고 알린다", "맞서자" in gw.status.cget("text"), gw.status.cget("text"))
    gw._hover_sido(SIDO, False)
    chk("  내려도 붉은 테두리는 남는다", gw.cv.itemcget("s%s" % SIDO, "outline") == ui_gym.BOSS_LINE)

    print("\n=== 검은 곳을 누르면 악당 창 ===")
    gw._click_sido(SIDO)
    chk("그 시·도로 들어가지 않는다", gw.sido is None, gw.sido)
    bw = gw.boss_win
    chk("악당 창이 뜬다", bw is not None and bw.alive)
    TG.pump(root, lambda: bw.card is not None and bw.go_btn is not None)
    root.update()
    seen = texts(bw.body)
    chk("조직과 곳, 남은 시간", "갤럭시단" in seen and any("울산광역시" in s and "5시간 2분" in s for s in seen), seen[:3])
    chk("간부 셋의 이름", all(api.trainers[t]["name"] in seen for t in MEMBERS), seen)
    chk("상태: 첫째는 도전, 나머지는 잠김", [r["state"] for r in bw.rows[:3]] == ["next", "locked", "locked"]
        and [r["chip"].cget("text") for r in bw.rows[:3]] == ["도전", "잠김", "잠김"])
    chk("전설은 아직 '???'", bw.rows[3]["name"] == "???" and "???" in seen)
    chk("단추: 첫 간부와 승부", bw.go_btn.label.cget("text") == "%s 와(과) 승부" % api.trainers["mars"]["name"],
        bw.go_btn.label.cget("text"))
    root.update_idletasks()
    chk("창은 내용만큼이고 눌린 것이 없다", not squeezed(bw.top)
        and bw.top.winfo_height() >= bw.top.winfo_reqheight() - 2,
        (squeezed(bw.top)[:3], bw.top.winfo_height(), bw.top.winfo_reqheight()))
    TG.pump(root, lambda: len(bw.photos) >= 3, 6)
    chk("간부의 도트가 붙는다", len(bw.photos) >= 3, len(bw.photos))
    gw._click_sido(SIDO)
    chk("다시 눌러도 창은 하나다", gw.boss_win is bw)

    print("\n=== 승부 ===")
    bw.challenge()
    TG.pump(root, lambda: bw.battle is not None)
    b = bw.battle
    chk("관장 배틀 창이 뜬다", isinstance(b, GB.GymBattleWindow)
        and b.view["trainer"]["name"] == api.trainers["mars"]["name"])
    chk("  상대는 내 파티만큼 (두 마리)", len(b.view["foe"]["team"]) == 2, len(b.view["foe"]["team"]))
    chk("끝까지 싸워 이긴다", fight_to_end(root, b) and b.view.get("result") == "won", b.view.get("result"))
    root.update()
    shown = texts(b.left)
    chk("결과 칸에 서버가 준 줄이 나온다", any("상금 500원" in s for s in shown)
        and any("간부가 2명 남았다" in s for s in shown), shown)
    chk("  관장용 문구(이긴 곳 n/256)는 안 나온다", not any("이긴 곳" in s for s in shown), shown)
    b.close()
    TG.pump(root, lambda: bw.battle is None and (bw.card or {}).get("stage") == 1)
    root.update()
    chk("창을 닫으면 악당 창이 다시 받는다 (이김·도전·잠김)",
        [r["state"] for r in bw.rows[:3]] == ["won", "next", "locked"], [r["state"] for r in bw.rows[:3]])
    chk("지도도 다시 받는다 (아직 검다)", fill_of(gw, SIDO) == ui_gym.BOSS_FILL)

    for who in ("jupiter", "saturn"):
        TG.pump(root, lambda: bw.go_btn is not None and not bw.busy)
        bw.challenge()
        TG.pump(root, lambda: bw.battle is not None)
        b = bw.battle
        ok = fight_to_end(root, b) and b.view.get("result") == "won"
        chk("%s 을(를) 이긴다" % api.trainers[who]["name"], ok, b.view.get("result"))
        b.close()
        TG.pump(root, lambda: bw.battle is None and not bw.busy)
        TG.pump(root, lambda w=who: (bw.card or {}).get("stage") == MEMBERS.index(w) + 1)
    root.update()

    print("\n=== 전설 ===")
    TG.pump(root, lambda: len(bw.rows) == 4 and bw.rows[3]["name"] != "???")
    chk("셋을 다 이기면 전설이 드러난다", bw.rows[3]["name"] == "디아루가" and bw.rows[3]["state"] == "next",
        (bw.rows[3]["name"], bw.rows[3]["state"]))
    chk("단추: 전설과 맞서기", bw.go_btn is not None and "디아루가" in bw.go_btn.label.cget("text"))
    chk("볼을 못 던지고 70% 라고 알린다", any("볼은 던질 수 없다" in s and "70%" in s for s in texts(bw.body)),
        texts(bw.body)[-3:])
    root.update_idletasks()
    chk("창에 눌린 것이 없다 (전설이 드러난 뒤)", not squeezed(bw.top), squeezed(bw.top)[:3])
    bw.challenge()
    TG.pump(root, lambda: bw.battle is not None)
    b = bw.battle
    chk("마주친 포켓몬과의 판이다", b.view["trainer"].get("wild") and b.view["trainer"]["name"] == "디아루가")
    chk("쓰러뜨린다", fight_to_end(root, b) and b.view.get("result") == "won", b.view.get("result"))
    root.update()
    shown = texts(b.left)
    chk("결과 칸: 쓰러뜨렸다 + 알", any("디아루가 을(를) 쓰러뜨렸다" in s or "디아루가를 쓰러뜨렸다" in s for s in shown)
        and any("알을 얻었다" in s for s in shown), shown)
    b.close()
    TG.pump(root, lambda: bw.battle is None and (bw.card or {}).get("done"))
    root.update()

    print("\n=== 다 물리친 뒤 ===")
    chk("악당 창: 끝났다고 적히고 단추가 없다", bw.go_btn is None
        and any("알을 얻었다" in s for s in texts(bw.body)), texts(bw.body)[-2:])
    chk("  전설 칸은 '이김'", bw.rows[3]["chip"].cget("text") == "이김")
    TG.pump(root, lambda: (gw.boss or {}).get("done"))
    root.update()
    chk("지도가 원래 색으로 돌아온다", fill_of(gw, SIDO) == plain and gw.boss_sido() is None, fill_of(gw, SIDO))
    chk("위쪽 단추는 남는다 (결과를 다시 볼 수 있게)", gw.boss_btn.holder.winfo_ismapped())
    bw.close()
    gw._click_sido(SIDO)
    root.update()
    chk("이제 그 시·도로 들어간다", gw.sido == SIDO, gw.sido)

    if U.TEXT_SIZE:
        # 글자를 키웠을 때(2.0) 작은 화면: 창은 화면까지만 크고 안을 굴리면 승부 단추까지 닿는다
        # (작업 영역 높이 560 - 1366x768 에서 아주 크게 한 것과 같은 처지. 예전에는 창 아래가 잘렸다)
        print("\n=== 작은 화면 (글자를 키웠을 때) ===")
        keep = PLAT.work_area
        PLAT.work_area = lambda *_a: (0, 0, 1920, 560)
        try:
            gw.to_nation()
            gw.open_boss()
            bs = gw.boss_win
            TG.pump(root, lambda: bs.card is not None and bs.rows)
            root.update()
            room = U.work_size(bs.top)[1]
            chk("악당 창이 작업 영역에 든다 (<= %d)" % room, bs.top.winfo_height() <= room,
                (bs.top.winfo_height(), room))
            cv = bs._scroll[0]
            cv.yview_moveto(1.0)
            root.update()
            foot = bs.body.winfo_children()[-1]          # 맨 아래 줄 (안내 글 · 승부 단추)
            y_in = foot.winfo_rooty() - cv.winfo_rooty()
            chk("  안을 굴리면 맨 아래 줄(승부 단추 자리)까지 보인다",
                0 <= y_in and y_in + foot.winfo_height() <= cv.winfo_height() + 1,
                (y_in, foot.winfo_height(), cv.winfo_height()))
            root.update_idletasks()
            chk("  눌린 것이 없다 (막대만큼 창이 넓어진다)", not squeezed(bs.top), squeezed(bs.top)[:3])
            bs.close()
        finally:
            PLAT.work_area = keep

    print("\n=== 창을 닫으면 ===")
    gw.to_nation()
    gw.open_boss()
    bw2 = gw.boss_win
    gw.close()
    root.update()
    chk("관장 창을 닫으면 악당 창도 닫힌다", not bw2.alive)

    chk("문구: 남은 시간", ui_boss.left_text(3661) == "1시간 1분" and ui_boss.left_text(59) == "1분"
        and ui_boss.left_text(0) == "1분")
    chk("문구: 안 나타났을 때", ui_boss.action_of({"active": False})[2].startswith("지금은"))

    TG.pump(root, lambda: False, 0.5)
    chk("Tk 콜백에서 난 오류가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
