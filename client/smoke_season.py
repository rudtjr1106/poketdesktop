# -*- coding: utf-8 -*-
"""시즌 2 화면 — 랭킹·랭크 팀·칭호·대전 기록·이로치사탕·선물 창이 뜨는가.

    python client/smoke_season.py

**창을 실제로 만든다** (화면에는 안 띄운다). 서버 대신 가짜 API 가 시즌 2
응답을 준다. 보는 것:

  · 랭킹 탭이 티어·RP·보상표·명예의 전당을 그리고, 옛 서버 응답(rp 없음)
    에도 안 터진다
  · 랭크 팀 창에서 고르고 등록·등록 풀기를 하면 그 id 가 서버로 간다
  · 칭호·명패 창에서 고른 것이 서버로 간다
  · 대전 기록에 RP 변화가 뜬다
  · 가방이 이로치사탕을 이미 이로치인 포켓몬에게는 막는다
  · 선물 창이 칭호·명패 줄을 '칭호 · ...' 로 적는다
"""
import os
import sys
import tempfile
import time

os.environ.setdefault("POKET_HOME",
                      os.path.join(tempfile.gettempdir(), "poket-smoke-season"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                       # noqa: E402

from poketdesktop import platform_os as PLAT               # noqa: E402
from poketdesktop import ui_bag, ui_pvp, ui_rank, ui_season  # noqa: E402
from poketdesktop import ui_common as U                    # noqa: E402

OK = FAIL = 0
ERRORS = []


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mon(pid, name, level, desk=False, shiny=False, slot=None):
    return {"id": pid, "level": level, "shiny": shiny, "onDesktop": desk,
            "slot": slot, "info": {"name": name, "species": name}}


RULES = {
    "season": 2, "startsAt": "2026-09-15", "endsAt": "2026-10-27", "levelCap": 50,
    "tiers": [{"tier": "monster", "tierKr": "몬스터볼", "rp": 0},
              {"tier": "super", "tierKr": "슈퍼볼", "rp": 300},
              {"tier": "hyper", "tierKr": "하이퍼볼", "rp": 700},
              {"tier": "master", "tierKr": "마스터볼", "rp": 1200},
              {"tier": "elite", "tierKr": "사천왕", "seats": 4},
              {"tier": "champion", "tierKr": "챔피언", "seats": 1}],
    "safeRp": 300,
    "rp": {"win": [10, 30], "lose": [5, 25], "firstWin": 10, "lossGuard": 3},
    "rewards": [{"tier": "champion", "tierKr": "챔피언", "title": "시즌 2 챔피언",
                 "frame": "금빛 명패", "frameColor": "#ffc043", "shiny": 1,
                 "egg": "전설의 포켓몬 알"},
                {"tier": "super", "tierKr": "슈퍼볼", "title": "시즌 2 슈퍼볼",
                 "frame": None, "frameColor": None, "shiny": 0, "egg": None}],
}


class FakeApi(object):
    def __init__(self):
        self.sent_team = []
        self.sent_equip = []
        self.old_server = False

    def pvp_ranking(self, limit=50):
        rows = [
            {"rank": 1, "name": "bro2000", "rp": 1500, "tier": "champion",
             "tierKr": "챔피언", "title": "시즌 1 챔피언", "frame": "gold",
             "frameColor": "#ffc043", "games": 40, "wins": 30, "losses": 10,
             "draws": 0, "streak": 3},
            {"rank": 2, "name": "나", "rp": 320, "tier": "super",
             "tierKr": "슈퍼볼", "games": 10, "wins": 6, "losses": 4,
             "draws": 0, "streak": -2, "me": True},
        ]
        me = {"rp": 320, "tier": "super", "tierKr": "슈퍼볼", "ranked": True,
              "games": 10, "wins": 6, "losses": 4, "nextTier": "hyper",
              "nextTierKr": "하이퍼볼", "rpToNext": 380, "floorRp": 300,
              "firstWinToday": False, "teamRegistered": True, "teamSize": 6,
              "title": "시즌 1 상위권", "frameColor": None}
        if self.old_server:
            for r in rows:
                for k in ("rp", "tier", "tierKr", "title", "frame", "frameColor"):
                    r.pop(k, None)
                r["rating"] = 1200
            return {"ranking": rows, "me": {"rating": 1200, "ranked": True},
                    "season": 1, "placement": 5}
        return {"ranking": rows, "me": me, "season": 2, "placement": 5,
                "rules": RULES,
                "hall": {"season": 1, "rows": [
                    {"rank": 1, "name": "bro2000", "rating": 1786, "wins": 90,
                     "losses": 12, "title": "시즌 1 챔피언"}]}}

    def pvp_team(self):
        return {"registered": False, "ids": [1, 2], "levelCap": 50, "maxParty": 6,
                "restrictedMax": 1, "restrictedNums": [150, 151]}

    def pokemon(self):
        out = [mon(1, "피카츄", 80, desk=True, slot=0),
               mon(2, "이브이", 30, desk=True, slot=1),
               mon(3, "리자몽", 55), mon(4, "잉어킹", 5, shiny=True),
               mon(5, "뮤츠", 50), mon(6, "뮤", 40)]
        out[4]["num"], out[5]["num"] = 150, 151
        return out

    def pvp_set_team(self, ids):
        self.sent_team.append(list(ids))
        return {"registered": bool(ids), "ids": list(ids) or [1, 2]}

    def rewards(self):
        return {"titles": [{"id": "s1_top30", "name": "시즌 1 상위권", "season": 1}],
                "frames": [{"id": "bronze", "name": "동빛 명패", "color": "#d08a52"}],
                "equipped": {"title": "s1_top30", "frame": None}}

    def equip_reward(self, title=None, frame=None):
        self.sent_equip.append((title, frame))
        return {}

    def pvp_records(self, limit=30):
        return {"summary": {"games": 3, "wins": 2, "losses": 1, "draws": 0,
                            "rp": 40, "tier": "monster", "tierKr": "몬스터볼",
                            "ranked": False, "winReward": 500, "dailyCap": 6000},
                "records": [
                    {"id": 1, "foe": "상대", "foeId": 9, "kind": "random",
                     "result": "win", "started": True, "delta": 16, "rp": 40,
                     "rpDelta": 20, "reward": 500, "turns": 12, "myLeft": 2,
                     "foeLeft": 0, "matchId": 5, "at": "2026-09-15T01:00:00+00:00",
                     "canFight": False, "whyNot": "친구에게만"},
                    {"id": 2, "foe": "옛상대", "foeId": 8, "kind": "random",
                     "result": "lose", "started": True, "delta": -14, "rp": 0,
                     "rpDelta": 0, "reward": 0, "turns": 9, "myLeft": 0,
                     "foeLeft": 1, "matchId": None, "at": "2026-09-01T01:00:00+00:00",
                     "canFight": False, "whyNot": ""}]}

    def pvp_pending(self):
        return {"matches": [], "fight": {"left": 17}}


class FakeApp(object):
    def __init__(self, root):
        self.root = root
        self.api = FakeApi()
        self.rank_window = None
        self.pvp_window = None
        self.said = []

    def pvp_random(self, on_done=None):
        self.random_calls = getattr(self, "random_calls", 0) + 1
        if on_done:
            on_done(None, "랜덤 배틀은 12초 뒤에 다시 걸 수 있습니다.")

    def notify(self, msg):
        self.said.append(msg)


def pump(root, cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def texts(w):
    out = []

    def walk(x):
        for c in x.winfo_children():
            try:
                if "text" in c.keys():
                    out.append(str(c.cget("text")))
            except tk.TclError:
                pass
            walk(c)
    walk(w)
    return "\n".join(out)


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    root.report_callback_exception = lambda *a: ERRORS.append(a)
    U.init_fonts(root)
    U.apply_theme(root)
    app = FakeApp(root)

    print("랭킹 탭")
    rw = ui_rank.RankWindow(app)
    pump(root, lambda: not rw.busy and "명예의 전당" in texts(rw.win))
    t = texts(rw.win)
    chk("티어 칩이 뜬다", "★ 챔피언" in t and "슈퍼볼" in t, t[:200])
    chk("RP 가 뜬다", "1,500 RP" in t and "320 RP" in t)
    chk("다음 티어까지", "하이퍼볼까지 380 RP" in t)
    chk("칭호가 뜬다", "시즌 1 챔피언" in t)
    chk("보상표에 알과 이로치사탕", "전설의 포켓몬 알 · 칭호 '시즌 2 챔피언'" in t
        and "이로치사탕 1개" in t, t)
    chk("레벨 상한 규칙", "Lv.50 상한" in t)
    chk("시즌 끝나는 날", "10월 27일까지" in rw.sub.cget("text"), rw.sub.cget("text"))
    chk("명예의 전당", "시즌 1 명예의 전당" in t)
    rw._random()
    pump(root, lambda: "초 뒤에" in rw.status._label.cget("text"))
    chk("랜덤 배틀이 막히면 '찾는 중' 대신 이유를 적는다",
        "초 뒤에" in rw.status._label.cget("text"), rw.status._label.cget("text"))
    rw._battle_done({"matchId": 1}, None)
    pump(root, lambda: False, 0.2)
    chk("끝나면 '찾는 중' 글을 걷는다", rw.status._label.cget("text") == "",
        rw.status._label.cget("text"))
    app.api.old_server = True
    rw.reload()
    pump(root, lambda: not rw.busy and "1200" in texts(rw.win))
    chk("옛 서버 응답(rp 없음)도 그린다", "1200" in texts(rw.win))
    app.api.old_server = False
    rw.close()

    print("랭크 팀")
    tw = ui_season.TeamWindow(app)
    pump(root, lambda: len(tw.rows) == 6)
    chk("내 포켓몬이 다 뜬다", len(tw.rows) == 6, len(tw.rows))
    chk("전설·환상 표시", "전설·환상" in texts(tw.win))
    tw.toggle(5)
    tw.toggle(6)
    chk("전설·환상 두 마리째는 안 들어간다", 5 in tw.picked and 6 not in tw.picked,
        tw.picked)
    chk("왜 안 되는지 말한다", "1마리까지" in tw.status._label.cget("text"),
        tw.status._label.cget("text"))
    tw.toggle(5)
    chk("처음에는 지금 파티가 골라져 있다", tw.picked == [1, 2], tw.picked)
    chk("레벨 상한이 줄에 적힌다", "Lv.80 → 50" in texts(tw.win))
    tw.toggle(3)
    tw.toggle(1)
    chk("누르면 넣고 빼기", tw.picked == [2, 3], tw.picked)
    for pid in (1, 4):
        tw.toggle(pid)
    tw.save()
    pump(root, lambda: app.api.sent_team)
    chk("등록하면 고른 순서 그대로 보낸다", app.api.sent_team[-1] == [2, 3, 1, 4],
        app.api.sent_team)
    pump(root, lambda: tw.registered)
    tw.unregister()
    pump(root, lambda: len(app.api.sent_team) == 2)
    chk("등록 풀기는 빈 목록", app.api.sent_team[-1] == [], app.api.sent_team)
    tw.fill_party()
    chk("바탕화면 파티로 채우기", tw.picked == [1, 2], tw.picked)
    tw.close()

    print("칭호·명패")
    ew = ui_season.RewardsWindow(app)
    pump(root, lambda: "시즌 1 상위권" in texts(ew.win))
    chk("가진 칭호가 뜬다", "시즌 1 상위권" in texts(ew.win))
    chk("달고 있는 칭호가 골라져 있다", ew.title_var.get() == "s1_top30")
    ew.frame_var.set("bronze")
    ew.title_var.set(ui_season.NONE)
    ew.save()
    pump(root, lambda: app.api.sent_equip)
    chk("고른 것을 보낸다 (칭호 떼기 + 명패)", app.api.sent_equip[-1] == ("", "bronze"),
        app.api.sent_equip)
    ew.close()

    print("대전 기록")
    pw = ui_pvp.PvpWindow(app)
    pump(root, lambda: not pw.busy and "옛상대" in texts(pw.win))
    t = texts(pw.win)
    chk("RP 변화가 뜬다", "RP +20" in t, t[:300])
    chk("시즌 1 기록은 점수로", "점수 -14" in t)
    chk("요약에 티어와 RP", "몬스터볼 40 RP" in pw.sub.cget("text"), pw.sub.cget("text"))
    pw.close()

    print("진화 알림 (가방·관장)")
    from poketdesktop import app as APP, desktop_battle, ui_bag as UB

    class EvoApp(object):
        show_evolutions = APP.App.show_evolutions

        def __init__(self, root):
            self.root = root
            self.learn = []

            class Ov(object):
                hidden = False
                pets = {7: object()}
            self.overlay = Ov()

        def want_learn(self, pid, name):
            self.learn.append(pid)
    played, boxed = [], []
    orig_play, orig_box = desktop_battle.play_evolutions, UB.announce_evolve
    desktop_battle.play_evolutions = lambda a, infos: played.extend(infos)
    UB.announce_evolve = lambda parent, a, info: boxed.append(info)
    try:
        ea = EvoApp(root)
        ea.show_evolutions([{"pokemonId": 7, "fromKr": "파이리", "toKr": "리자드"},
                            {"pokemonId": 8, "fromKr": "꼬부기", "toKr": "어니부기",
                             "pendingIds": ["BITE"]}])
        chk("바탕화면에 있는 포켓몬은 진화 연출", [i["pokemonId"] for i in played] == [7], played)
        chk("박스에 있는 포켓몬은 진화 창", [i["pokemonId"] for i in boxed] == [8], boxed)
        chk("박스에 있어도 배울 기술은 묻는다", ea.learn == [8], ea.learn)
        played[:] = []
        boxed[:] = []
        ea.overlay.hidden = True
        ea.show_evolutions([{"pokemonId": 7, "fromKr": "파이리", "toKr": "리자드"}])
        chk("도트를 숨겨 둔 중이면 창으로", not played and len(boxed) == 1, (played, boxed))
    finally:
        desktop_battle.play_evolutions, UB.announce_evolve = orig_play, orig_box
    from poketdesktop import ui_gym_battle as GBW
    import inspect as _inspect
    chk("관장은 결과가 뜨는 순간 진화를 시작한다",
        "_after_flow" in _inspect.getsource(GBW.GymBattleWindow.show_result))

    print("가방 · 선물")
    candy = {"id": "SHINYCANDY", "kr": "이로치사탕", "cat": "misc",
             "effect": {"kind": "shiny"}, "desc": "먹이면 이로치가 된다."}
    st = ui_bag.BagWindow._target_state(None, candy, {"shiny": True, "info": {}})
    chk("이미 이로치면 막는다", st[1] and "이미" in st[2], st)
    st = ui_bag.BagWindow._target_state(None, candy, {"shiny": False, "info": {}})
    chk("아니면 쓸 수 있다", not st[1], st)
    chk("가방에서 쓸 수 있는 도구", "shiny" in ui_bag.USABLE)
    from poketdesktop import ui_shop
    chk("상점 탭도 '쓸 수 없는 물건' 이라고 안 적는다",
        "쓸 수 없" not in ui_shop.effect_text(candy)
        and "이로치" in ui_shop.effect_text(candy), ui_shop.effect_text(candy))
    # 도구 목록에 있는 모든 종류를 두 창이 다 아는가. 새 종류를 넣고 한쪽을
    # 빠뜨리면 여기서 걸린다 (이로치사탕이 그랬다).
    import json as _json
    cat = _json.load(open(os.path.join(os.path.dirname(HERE), "server", "data",
                                       "items.json"), encoding="utf-8"))["items"]
    kinds = sorted(set((it.get("effect") or {}).get("kind") for it in cat.values()))
    unknown = [k for k in kinds
               if ui_shop.effect_text({"effect": {"kind": k}}) == "아직 쓸 수 없는 물건"
               or ui_bag.item_desc({"effect": {"kind": k}}) == "아직 쓸 수 없는 도구다."]
    chk("도구 목록의 모든 종류를 상점·가방이 설명한다 (%s)" % ", ".join(kinds),
        not unknown, unknown)
    chk("설명에 되돌릴 수 없다", "되돌릴 수 없다" in ui_bag.item_desc(candy))
    chk("선물 줄: 칭호", ui_bag.gift_line({"kind": "title", "name": "시즌 1 사천왕",
                                          "count": 1}) == "칭호 · 시즌 1 사천왕")
    chk("선물 줄: 명패", ui_bag.gift_line({"kind": "frame", "name": "은빛 명패",
                                          "count": 1}) == "명패 · 은빛 명패")
    chk("선물 줄: 알", ui_bag.gift_line({"kind": "egg", "item": "mythical",
                                        "name": "환상의 포켓몬 알",
                                        "count": 1}) == "환상의 포켓몬 알")
    gifts = [{"kind": "egg", "item": "mythical", "name": "환상의 포켓몬 알",
              "count": 1, "title": "시즌 1 보상",
              "message": "시즌 1 을 3위로 마쳤습니다."},
             {"kind": "title", "name": "시즌 1 사천왕", "count": 1},
             {"kind": "frame", "name": "은빛 명패", "count": 1},
             {"kind": "item", "item": "SHINYCANDY", "name": "이로치사탕", "count": 2}]
    before = set(root.winfo_children())
    seen = {}

    def grab():
        # 선물 창은 닫을 때까지 기다린다(wait_window). 떠 있는 동안 읽고 닫는다.
        new = [w for w in root.winfo_children() if w not in before]
        if not new:
            return root.after(100, grab)
        seen["text"] = texts(new[0])
        for w in new:
            w.destroy()
    root.after(300, grab)
    ui_bag.announce_gifts(root, app, gifts)
    t = seen.get("text")
    chk("선물 창이 떴다", t is not None)
    if t:
        chk("칭호 줄과 사탕 줄", "칭호 · 시즌 1 사천왕" in t and "이로치사탕 ×2" in t, t)
        chk("칭호는 랭킹 탭에서 바꾼다고 알린다", "랭킹 탭" in t, t)
        chk("알 줄과 알 안내", "환상의 포켓몬 알" in t and "데리고 다니는 동안" in t, t)

    print("투기장 이름표")
    from poketdesktop import arena

    class FakeArena(object):
        ring = {"rect": (100, 100, 500, 300)}

        def __init__(self, view):
            self.view = view
            self.plates = []

        def _plate(self, sx, sy, text, color, anchor="center"):
            self.plates.append((text, color, anchor))

    fa = FakeArena({"levelCap": 50, "foe": {
        "name": "bro2000", "tierKr": "챔피언", "title": "시즌 1 챔피언",
        "frameColor": "#ffc043"}})
    arena.Arena._name_plates(fa)
    chk("상대 이름표에 티어·칭호·명패 색",
        fa.plates[0] == ("챔피언  bro2000  ·  시즌 1 챔피언", "#ffc043", "se"),
        fa.plates)
    chk("랭크 배틀이면 레벨 상한 이름표", any("Lv.50 상한" in p[0] for p in fa.plates),
        fa.plates)
    fa = FakeArena({"levelCap": None, "foe": {"name": "친구"}})
    arena.Arena._name_plates(fa)
    chk("친구 배틀은 이름만, 상한 이름표 없음",
        fa.plates == [("친구", "#ffb0b0", "se")], fa.plates)

    chk("그리는 중에 난 오류가 없다", not ERRORS,
        [str(e[1]) for e in ERRORS][:3])
    root.destroy()
    print("\n  합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
