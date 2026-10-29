# -*- coding: utf-8 -*-
"""랭크 팀 같은 지닌 도구 표시 (시즌 5) - 랭크 팀 창 · 랭킹 규칙 카드 · 내 카드. 진짜 Tk 로 본다.

    python client/test_held_rank_ui.py

서버(server/test_held_v5.py)는 시즌 5 에만 sameHeldMax · heldDupIds · heldDupes 를 싣는다. 화면은
  · 새 서버(시즌 5): 겹친 포켓몬을 '도구 겹침' 으로 표시 · 열 때 알림 · 두 마리째를 고르면 누가 지녔는지 말하고 막는다 ·
    규칙 카드에 한 줄 · 내 카드에 '랜덤 배틀을 걸 수 없음'
  · 시즌 4·옛 서버(칸 없음): 같은 도구 둘이어도 아무 표시도 막기도 없다
  · 길드전 팀(spec)은 시즌 5 여도 안 건다 (랭크만)
기본 화면을 본 뒤 같은 검사를 DP 테마로 한 번 더 돈다 (자식 프로세스).
"""
import os
import subprocess
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-held-rank-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins, ui_rank, ui_season          # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

OK = FAIL = 0
ERRORS = []


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def mon(pid, name, sp, held=None, held_kr=None, slot=None):
    out = {"id": pid, "level": 60, "shiny": False, "onDesktop": slot is not None, "slot": slot,
           "species": sp, "info": {"name": name, "species": name}}
    if held:
        out["held"], out["heldKr"] = held, held_kr
    return out


class FakeApi(object):
    def __init__(self):
        self.v5 = True

    def pvp_team(self):
        out = {"registered": True, "ids": [1, 2, 3], "levelCap": 50, "maxParty": 6,
               "restrictedMax": 1, "restrictedNums": [], "sameSpeciesMax": 1}
        if self.v5:
            out.update(sameHeldMax=1, heldDupIds=[3])
        return out

    def pokemon(self):
        return [mon(1, "한카리아스", "GARCHOMP", "FOCUSSASH", "기합의띠", 0),
                mon(2, "갸라도스", "GYARADOS", "LIFEORB", "생명의구슬", 1),
                mon(3, "메타그로스", "METAGROSS", "FOCUSSASH", "기합의띠", 2),
                mon(4, "루카리오", "LUCARIO", "LIFEORB", "생명의구슬"),
                mon(5, "잠만보", "SNORLAX")]

    def pvp_ranking(self, limit=50):
        rules = {"season": 5, "levelCap": 50, "sameSpeciesMax": 1}
        me = {"rp": 200, "tier": "super", "tierKr": "슈퍼볼", "ranked": True, "games": 5,
              "teamRegistered": True, "teamSize": 6, "fight": {"left": 10, "dailyBattles": 20}}
        if self.v5:
            rules["sameHeldMax"] = 1
            me.update(sameHeldMax=1, heldDupes=1)
        return {"ranking": [], "me": me, "season": 5, "placement": 5, "rules": rules, "hall": {}}

    def pvp_records(self, limit=30):
        return {"summary": {}, "records": []}

    def pvp_set_team(self, ids):
        return {"registered": True, "ids": list(ids)}


class FakeApp(object):
    def __init__(self, root):
        self.root = root
        self.api = FakeApi()
        self.rank_window = None
        self.team_window = None


def pump(root, cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def status(tw):
    if hasattr(tw, "status"):
        return tw.status._label.cget("text")
    return (getattr(tw, "msg", None) or getattr(tw, "_msg", None) or ("",))[0]      # DP 테마는 판에 그린다


def slots_text(tw):
    if not hasattr(tw, "slots"):
        # DP 테마: 파티 판을 캔버스에 그린다 - 그 글을 모은다
        cv = tw.cv
        return "\n".join(str(cv.itemcget(i, "text")) for i in cv.find_all() if cv.type(i) == "text")
    return "\n".join(str(w.cget("text")) for w in tw.slots.winfo_children())


def close(root, w):
    # 맥 Tk 8.6.17: 화면 밖에서 안 그려진 창을 바로 없애면 update() 가 돌아오지 않는다 - 화면 안에서 없앤다
    try:
        w.win.geometry("+40+40")
        root.update()
    except tk.TclError:
        pass
    w.close()
    root.update()


def team_checks(root):
    app = FakeApp(root)
    print("-- 시즌 5 서버")
    tw = ui_season.TeamWindow(app)
    pump(root, lambda: tw.mons and tw._wait is None)
    pump(root, lambda: False, 0.2)
    chk("겹친 뒤의 것(메타그로스)을 고른다", tw.held_dup_ids(tw.picked) == [3], tw.held_dup_ids(tw.picked))
    chk("  겹친 도구를 이름으로", tw.held_text(tw.picked) == "기합의띠(한카리아스·메타그로스)", tw.held_text(tw.picked))
    chk("  아래 줄에 고칠 것", "기합의띠(한카리아스·메타그로스)" in status(tw), status(tw))
    want = "3. 메타그로스 · 도구 겹침" if hasattr(tw, "slots") else "도구 겹침"
    chk("  자리에 '도구 겹침'", want in slots_text(tw), slots_text(tw)[-300:])
    chk("  설명에 규칙 한 줄", "같은 지닌 도구는 1마리만" in tw.note_text(), tw.note_text())
    tw.toggle(3)
    chk("빼면 겹침이 없어진다", tw.held_dup_ids(tw.picked) == [] and "겹" not in status(tw), status(tw))
    tw.toggle(4)
    chk("같은 도구 두 마리째는 안 들어간다", 4 not in tw.picked, tw.picked)
    chk("  누가 지녔는지 말한다", "생명의구슬은 갸라도스가 이미 지니고 있습니다" in status(tw), status(tw))
    tw.toggle(5)
    chk("안 지닌 포켓몬은 그대로 들어간다", 5 in tw.picked, tw.picked)
    # 쉬는 포켓몬(같은 종 두 마리째)이 같은 도구를 지닌 것은 서버가 겹침으로 안 본다 - 앱도 나가는 팀으로 센다 (10/29 검토)
    tw.mons.append(mon(6, "한카리아스B", "GARCHOMP", "FOCUSSASH", "기합의띠"))
    tw.picked = [1, 2, 5, 6]
    tw.rank_min = {"count": 6, "level": 50}
    chk("같은 종 두 마리째는 나가는 팀에서 빠진다", tw._fighting(tw.picked) == [1, 2, 5], tw._fighting(tw.picked))
    chk("  그 포켓몬의 같은 도구는 겹침이 아니다", tw.held_dup_ids(tw._fighting(tw.picked)) == []
        and not tw.held_text(tw._fighting(tw.picked)))
    hint, _c = tw.team_hint()
    chk("  아래 줄은 진짜 까닭(마릿수)을 먼저", hint.startswith("랭크전은 Lv.50 이상 6마리"), hint)
    tw.rank_min = None
    close(root, tw)

    print("-- 시즌 4 · 옛 서버 (칸 없음)")
    app.api.v5 = False
    tw = ui_season.TeamWindow(app)
    pump(root, lambda: tw.mons and tw._wait is None)
    pump(root, lambda: False, 0.2)
    chk("표시 없음", tw.held_dup_ids(tw.picked) == [] and "기합의띠" not in status(tw), status(tw))
    chk("  설명에 규칙 줄 없음", "지닌 도구" not in tw.note_text())
    tw.toggle(4)
    chk("  같은 도구도 막지 않는다", 4 in tw.picked, tw.picked)
    close(root, tw)

    print("-- 길드전 팀 (spec) 은 시즌 5 여도 안 건다")
    app.api.v5 = True
    gw = ui_season.TeamWindow(app, spec={"title": "길드전 방어팀", "note": "길드전 설명",
                                         "load": lambda: (app.api.pvp_team(), app.api.pokemon()),
                                         "save": app.api.pvp_set_team, "saved": "짰습니다"})
    pump(root, lambda: gw.mons and gw._wait is None)
    pump(root, lambda: False, 0.2)
    chk("길드전 팀은 표시·막기 없음", gw.held_max is None and gw.held_dup_ids(gw.picked) == [], gw.held_max)
    close(root, gw)


def rank_checks(root):
    app = FakeApp(root)
    rw = ui_rank.RankWindow(app)
    pump(root, lambda: not rw.busy and rw.me)
    text = (rw._rules_data() or {}).get("text") or ""
    chk("규칙 카드에 한 줄", "같은 지닌 도구는 랭크 팀에 1마리까지" in text, text)
    short = (rw._me_data() or {}).get("short") or ""
    chk("내 카드: 랜덤 배틀을 걸 수 없음", "랜덤 배틀을 걸 수 없습니다" in short, short)
    app.api.v5 = False
    rw.reload()
    pump(root, lambda: not rw.busy and "sameHeldMax" not in rw.rules)
    chk("시즌 4 · 옛 서버: 규칙 줄 없음", "지닌 도구" not in ((rw._rules_data() or {}).get("text") or ""))
    chk("  내 카드 알림 없음", not (rw._me_data() or {}).get("short"))
    close(root, rw)


def main():
    print("=== 테마: %s ===" % skins.active())
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    root.report_callback_exception = lambda *a: ERRORS.append(a)
    U.init_fonts(root)
    U.apply_theme(root)
    team_checks(root)
    rank_checks(root)
    chk("화면 콜백 오류 없음", not ERRORS, ERRORS[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    bad = 1 if FAIL else 0
    if not os.environ.get("POKET_SKIN"):
        env = dict(os.environ, POKET_SKIN="dp")
        bad |= subprocess.call([sys.executable, os.path.abspath(__file__)], env=env)
    return bad


if __name__ == "__main__":
    sys.exit(main())
