# -*- coding: utf-8 -*-
"""투기장 재생 스모크 — 서버 없이 돌린다.

    python client/smoke_arena.py

엔진으로 판을 하나 만들어 그 로그를 그대로 재생한다. 서버도 계정도
필요 없어서 몇 번이든 반복할 수 있다.

제일 중요한 건 **강제 중단 매트릭스**다. 재생 도중 로그아웃하거나 앱을
끄거나 예외가 나도 바탕화면이 원래대로 돌아와야 한다. 여기가 깨지면
사용자는 재시작 말고는 푸는 방법이 없는데, 24시간 켜 두는 프로그램이라
그게 제일 아프다.
"""
import os
import random
import sys
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import party_battle as PB                  # noqa: E402
from common import pokelogic as P                      # noqa: E402
from client.poketdesktop import arena as A             # noqa: E402
from client.poketdesktop import config                 # noqa: E402
from client.poketdesktop import overlay as OV          # noqa: E402
from client.poketdesktop import ui_common as U         # noqa: E402

DEX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "server", "data", "pokedex.json")
OK = FAIL = 0
NUMS = []


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


class FakeApp(object):
    """App 에서 투기장이 실제로 쓰는 것만."""

    def __init__(self, root, dex):
        self.root = root
        self.dex = dex
        self.overlay = None
        self.said = []
        self.arena = None

    def notify(self, m):
        self.said.append(m)


def make_match(dex, rng, nums):
    """캐시된 도트가 있는 종으로만 판을 짠다. 양쪽 다 그 종을 쓴다."""
    def team():
        out = []
        for num in nums:
            sp = dex.get(num)
            if not sp:
                continue
            m = dex.roll_wild(28, 30, rng)
            m["species"] = sp["internal"]
            m["num"] = num
            out.append(m)
        return out
    out = PB.simulate(dex, team(), team(), seed=rng.randrange(1 << 30))
    return {"id": 1, "kind": "friend", "result":
            {"me": "win", "foe": "lose", "draw": "draw"}[out["winner"]],
            "turns": out["turns"], "events": out["events"],
            "me": {"name": "나"}, "foe": {"name": "상대"}, "reward": 500}


def cached_nums(k):
    """**걷는 도트까지** 받아 둔 도감 번호 몇 개.

    도트가 없으면 Pet 이 아예 안 만들어져서, '내 도트가 그대로 남는가' 를
    검사한다고 해놓고 0마리를 세는 꼴이 된다. 그리고 걷는 도트가 없으면
    옛날 배틀 도트로 나오는데, 그건 지금 확인하려는 것과 다르다.
    """
    from client.poketdesktop import sprite_cache as SC
    from client.poketdesktop import walk_cache as WC
    nums = []
    for f in sorted(os.listdir(WC.walk_dir())):
        stem, ext = os.path.splitext(f)
        if ext != ".png" or not stem.isdigit():
            continue
        n = int(stem)
        if WC.local(n)[0] and SC.find_local(n, False):
            nums.append(n)
    return nums[:k]


def paths_for(nums):
    from client.poketdesktop import sprite_cache as SC
    out = {}
    for n in nums:
        p = SC.find_local(n, False)
        if p:
            out[(n, False)] = p
    return out


def walks_for(nums):
    """받아 둔 걷는 도트. 이게 없으면 옛날 배틀 도트로 나온다."""
    from client.poketdesktop import walk_cache as WC
    out = {}
    for n in nums:
        sheet, meta = WC.local(n)
        if sheet and meta:
            out[n] = (sheet, meta)
    return out


def desktop(root, dex, nums):
    """바탕화면에 내 포켓몬을 띄운다. 실제 캐시된 도트를 쓴다."""
    ov = OV.Overlay(root, dict(config.DEFAULTS))
    mons = []
    for i, num in enumerate(nums):
        sp = dex.get(num) or {}
        mons.append({"id": i + 1, "num": num, "shiny": False,
                     "info": {"name": sp.get("kr") or str(num),
                              "species": sp.get("internal") or str(num),
                              "level": 30, "types": []}})
    ov.sync(mons, paths_for(nums), walks_for(nums))
    root.update()
    return ov


def run_until(root, secs, stop=None):
    """tk 를 돌린다. stop() 이 True 가 되면 일찍 끝낸다."""
    done = [False]

    def tick(left):
        if done[0]:
            return
        try:
            root.update()
        except Exception:                                   # noqa: BLE001
            done[0] = True
            return
        if stop and stop():
            done[0] = True
            return root.quit()
        if left <= 0:
            done[0] = True
            return root.quit()
        root.after(50, lambda: tick(left - 50))
    root.after(0, lambda: tick(int(secs * 1000)))
    root.mainloop()


FX_RUNS = [0]


def count_effects():
    """battle_fx.Effect 가 실제로 만들어지는지 센다.

    '전투 애니메이션이 있다' 는 눈으로만 확인할 수 있는 종류라 그냥 두면
    조용히 사라져도 모른다. 만들어진 횟수라도 세어 둔다.
    """
    real = A.FX.Effect

    class Counted(real):
        def __init__(self, *a, **kw):
            FX_RUNS[0] += 1
            real.__init__(self, *a, **kw)
    A.FX.Effect = Counted


def state_of(ov):
    return {"pets": len(ov.pets), "extra": len(ov.extra),
            "locked": bool(getattr(ov, "locked", False))}


def main():
    dex = P.Pokedex.load(DEX)
    rng = random.Random(20260901)
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    global NUMS
    NUMS = cached_nums(3)
    if len(NUMS) < 1:
        print("받아 둔 도트가 없습니다. 게임을 한 번 켜서 도트를 받아 주세요.")
        return 1
    print("쓰는 도감 번호:", NUMS)

    print("=== 끝까지 재생 ===")
    ov = desktop(root, dex, NUMS)
    before = state_of(ov)
    app = FakeApp(root, dex)
    app.overlay = ov
    count_effects()
    ar = A.Arena(app, make_match(dex, rng, NUMS))
    app.arena = ar
    ar.start()
    foe_pets, stage_rect, walked = [], None, 0

    bars_drawn = [0]

    def peek():
        # 재생 도중에 한 번 들여다본다. 끝나면 다 정리돼서 못 본다.
        if ar.foes and not foe_pets:
            foe_pets.extend(ar.foes)
        # 체력바가 실제로 캔버스에 그려졌나. 만들고 값만 넣어서는
        # 화면에 아무것도 안 나온다 - draw() 를 불러야 그려진다.
        drawn = sum(len(b.items) for b in ar.bars.values())
        bars_drawn[0] = max(bars_drawn[0], drawn)
        if not ar.closed:
            root.after(700, peek)
    root.after(4000, peek)
    run_until(root, 150, stop=lambda: ar.closed)
    stage_rect = ar.ring["rect"] if getattr(ar, "ring", None) else None
    walked = sum(1 for p in foe_pets if getattr(p, "walking_sprite", False))
    chk("끝까지 돌고 스스로 닫힌다", ar.closed)
    chk("상대 도트가 남지 않는다", len(ov.extra) == 0, ov.extra)
    chk("내 도트는 그대로", len(ov.pets) == before["pets"],
        (len(ov.pets), before["pets"]))
    chk("화면 잠금이 풀린다", not ov.locked)
    chk("결과를 알린다", any("대전" in m for m in app.said), app.said)
    chk("내 도트가 다시 움직일 수 있다",
        all(not p.battling for p in ov.pets.values()))
    chk("내 도트가 다 보인다",
        all(p.win.state() == "normal" for p in ov.pets.values()),
        [p.win.state() for p in ov.pets.values()])
    chk("기술 이펙트가 실제로 돌았다 (%d회)" % FX_RUNS[0], FX_RUNS[0] > 0)
    chk("체력바가 화면에 그려졌다 (조각 %d개)" % bars_drawn[0],
        bars_drawn[0] > 0)
    chk("상대가 걷는 도트로 나왔다 (%d/%d)" % (walked, len(foe_pets)),
        len(foe_pets) > 0 and walked == len(foe_pets),
        [p.walking_sprite for p in foe_pets])
    chk("내 도트도 걷는 도트다",
        all(p.walking_sprite for p in ov.pets.values()),
        [p.walking_sprite for p in ov.pets.values()])
    ax1, ay1, ax2, ay2 = ov.area()
    # 무대는 활동 범위에서 조금만 넓어진 것이어야 한다. 화면 한가운데로
    # 옮겨 가거나, 화면을 통째로 차지하면 안 된다.
    sw_, sh_ = ax2 - ax1, ay2 - ay1
    gw = stage_rect[2] - stage_rect[0]
    gh = stage_rect[3] - stage_rect[1]
    chk("무대가 활동 범위 근처에 있다",
        stage_rect[2] >= ax2 - 40 and stage_rect[3] >= ay2 - 40,
        (stage_rect, ov.area()))
    chk("무대가 지나치게 넓지 않다 (%dx%d -> %dx%d)"
        % (sw_, sh_, gw, gh), gw <= sw_ * 1.5 and gh <= sh_ * 1.5)

    print("\n=== 강제 중단 매트릭스 ===")
    # 재생 도중 끝나는 길이 여럿이다. 그 전부에서 원래대로 돌아와야 한다.
    cases = [
        ("한창일 때 cleanup", 3.0, lambda ar: ar.cleanup()),
        ("소집 중에 cleanup", 0.6, lambda ar: ar.cleanup()),
        ("입장 중에 cleanup", 2.2, lambda ar: ar.cleanup()),
        ("cleanup 을 두 번", 3.0, lambda ar: (ar.cleanup(), ar.cleanup())),
        ("재생 중 예외가 나도", 3.0, lambda ar: _boom(ar)),
    ]
    for name, when, kill in cases:
        ov = desktop(root, dex, NUMS)
        want = len(ov.pets)
        app = FakeApp(root, dex)
        app.overlay = ov
        ar = A.Arena(app, make_match(dex, rng, NUMS))
        ar.start()
        run_until(root, when)
        try:
            kill(ar)
        except Exception as e:                              # noqa: BLE001
            chk("%s — 정리가 터지지 않는다" % name, False, e)
            continue
        run_until(root, 1.2)
        st = state_of(ov)
        chk("%s → 유령 창 없음" % name, st["extra"] == 0, st)
        chk("%s → 잠금 풀림" % name, not st["locked"], st)
        chk("%s → 내 도트 %d마리 그대로" % (name, want),
            st["pets"] == want, st)
        chk("%s → 다시 걸어다닌다" % name,
            all(not p.battling for p in ov.pets.values()))
        chk("%s → 예약된 일이 안 남는다" % name, not ar.jobs, len(ar.jobs))
        ov.clear()

    print("\n=== 한 마리씩만 있을 때 ===")
    ov = desktop(root, dex, NUMS[:1])
    app = FakeApp(root, dex)
    app.overlay = ov
    ar = A.Arena(app, make_match(dex, rng, NUMS[:1]))
    ar.start()
    run_until(root, 120, stop=lambda: ar.closed)
    chk("1:1 도 끝까지 간다", ar.closed)
    chk("1:1 정리도 깨끗하다", len(ov.extra) == 0 and not ov.locked,
        state_of(ov))
    ov.clear()

    print("\n=== 명단 없는 로그 ===")
    ov = desktop(root, dex, NUMS)
    app = FakeApp(root, dex)
    app.overlay = ov
    bad = make_match(dex, rng, NUMS)
    bad["events"] = [e for e in bad["events"] if e.get("t") != "teams"]
    ar = A.Arena(app, bad)
    ar.start()
    run_until(root, 1.0)
    chk("깨진 로그는 조용히 접는다", ar.closed)
    chk("그때도 잠금은 풀려 있다", not ov.locked, state_of(ov))
    ov.clear()

    try:
        root.destroy()
    except Exception:                                       # noqa: BLE001
        pass
    print("\n======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


def _boom(ar):
    """재생 중에 예외가 나는 상황. 그래도 화면은 돌아와야 한다."""
    ar.queue.insert(0, {"t": "move", "who": "me", "move": None})
    ar.roster = None            # _render 가 참조하다 터진다
    ar.cleanup()


if __name__ == "__main__":
    sys.exit(main())
