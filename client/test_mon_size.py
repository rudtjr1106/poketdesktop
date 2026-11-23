# -*- coding: utf-8 -*-
"""배틀 창 도트 키 = 도감의 키 (2.5.5, 11/23 게시판 #777 댕댕킴 '따라큐 같은 애들이 엄청 크게 보인다') - 화면 없이.

    python client/test_mon_size.py

  1. 몫: 0.3m 이하 0.45 · 3.5m 이상 1.0 · 사이는 커질수록 커진다 · 키를 모르면 1.0 (예전과 같다)
  2. 진짜 도감: 따라큐 < 피카츄 < 리자몽 < 그란돈 = 고래왕 (칸 다 씀)
  3. 메가 · 폼은 그 모습의 키 · 없으면 원래 종의 키
  4. 관장 · 실시간 배틀 창이 그 높이로 도트를 받아 온다 (따라큐는 칸의 절반 아래, 그란돈은 칸 그대로)
  5. 레이드: 우리 쪽은 키대로 · 보스는 늘 칸 그대로
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-mon-size-"))

from common import pokelogic as P                           # noqa: E402
from poketdesktop import mon_size as MS                     # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def dex():
    with open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8") as f:
        return P.Pokedex(json.load(f))


class _Stop(Exception):
    pass


def window_sizes(mod, cls, nums, who_or_key, **kw):
    """창을 띄우지 않고 set_mon 만 돌려, 도트를 받아 올 때 넘긴 높이를 모은다."""
    from poketdesktop import sprite_cache, sprites
    got = []
    w = cls.__new__(cls)
    w.app = type("A", (), {"dex": DEX, "api": None})()
    w.shown, w.anims, w.alive = {}, {}, True
    noop = lambda *a, **k: None                                         # noqa: E731
    w.zoom_use = w._paint_box = w._stop_anim = w._paint = noop
    w.sendout = type("S", (), {"cancel": noop, "forget": noop, "arrive": lambda *a: True})()
    w.hiding = type("H", (), {"apply": noop})()
    w.cv = type("C", (), {"itemconfigure": noop})()
    w.sprite = {who_or_key: 1}
    w.root = None
    w.dot_fit = lambda who, h, wd: h

    def load(path, size, *a, **k):
        got.append(size)
        raise _Stop()
    old = (mod.run_async, sprite_cache.ensure, sprites.load_animation)
    mod.run_async = lambda root, work, done: _run(work)
    sprite_cache.ensure = lambda api, num, shiny: "x.gif"
    sprites.load_animation = load
    try:
        for n in nums:
            w.set_mon(who_or_key, {"num": n}, **kw)
    finally:
        mod.run_async, sprite_cache.ensure, sprites.load_animation = old
    return got


def _run(work):
    try:
        work()
    except _Stop:
        pass


DEX = dex()
NUM = {"따라큐": 778, "피카츄": 25, "리자몽": 6, "그란돈": 383, "고래왕": 321, "파쪼옥": 595}


def main():
    print("=== 배틀 도트 키 (#777)")
    chk("1. 0.3m 이하는 0.45", MS.ratio(0.1) == MS.ratio(0.3) == 0.45, (MS.ratio(0.1), MS.ratio(0.3)))
    chk("   3.5m 이상은 1.0", MS.ratio(3.5) == MS.ratio(14.5) == 1.0, (MS.ratio(3.5), MS.ratio(14.5)))
    seq = [MS.ratio(h) for h in (0.3, 0.5, 0.9, 1.5, 2.5, 3.5)]
    chk("   사이는 커질수록 커진다", all(a < b for a, b in zip(seq, seq[1:])), seq)
    chk("   키를 모르면 1.0 (예전과 같다)", MS.ratio(None) == MS.ratio(0) == MS.ratio("?") == 1.0)
    chk("   도감이 없으면 칸 그대로", MS.fit(None, 778, 132) == 132)

    r = {k: MS.ratio(MS.height_of(DEX, n)) for k, n in NUM.items()}
    chk("2. 따라큐 < 피카츄 < 리자몽 < 그란돈", r["따라큐"] < r["피카츄"] < r["리자몽"] < r["그란돈"] == 1.0, r)
    chk("   고래왕도 칸을 다 쓴다 · 파쪼옥은 가장 작게", r["고래왕"] == 1.0 and r["파쪼옥"] == 0.45, r)
    chk("   내 쪽 칸(132px)에서 따라큐 59px · 리자몽 111px", MS.fit(DEX, 778, 132) == 59 and MS.fit(DEX, 6, 132) == 111,
        (MS.fit(DEX, 778, 132), MS.fit(DEX, 6, 132)))

    mega = next(m for m in DEX.megas if m.get("megaOf") == "CHARIZARD" and m.get("height"))
    chk("3. 메가는 그 모습의 키", MS.height_of(DEX, mega["num"]) == mega["height"], (mega["num"], mega.get("height")))
    form = next((f for f in DEX.forms if f.get("formOf")), None)
    if form is not None:
        saved = form.pop("height", None)
        try:
            base = DEX.get(form["formOf"])
            chk("   폼에 키가 없으면 원래 종의 키", MS.height_of(DEX, form["num"]) == base.get("height"),
                (form["num"], base.get("height")))
        finally:
            if saved is not None:
                form["height"] = saved
    chk("   모르는 번호는 None", MS.height_of(DEX, 99999) is None)

    from poketdesktop import ui_gym_battle as GB
    from poketdesktop import ui_live_battle as LB
    from poketdesktop import ui_raid_battle as RB
    full = 132
    gym = window_sizes(GB, GB.GymBattleWindow, [778, 383], "me")
    chk("4. 관장 배틀: 따라큐는 칸의 절반 아래 · 그란돈은 칸 그대로", len(gym) == 2 and gym[0] < full / 2 and gym[1] == full,
        gym)
    live_cls = next(getattr(LB, n) for n in dir(LB) if n.endswith("Window") and hasattr(getattr(LB, n), "set_mon"))
    live = window_sizes(LB, live_cls, [778, 383], "me")
    chk("   실시간 배틀도 같다", len(live) == 2 and live[0] < live[1] and live[1] == LB.U.h(LB.MON_H["me"]), live)
    raid_cls = next(getattr(RB, n) for n in dir(RB) if n.endswith("Window") and hasattr(getattr(RB, n), "set_mon"))
    raid = window_sizes(RB, raid_cls, [778, 383], 0)
    boss = window_sizes(RB, raid_cls, [778], 0, boss=True)
    chk("5. 레이드: 우리 쪽은 키대로", len(raid) == 2 and raid[0] < raid[1], raid)
    chk("   보스는 따라큐라도 칸 그대로", boss == [RB.U.h(RB.BOSS_H)], (boss, RB.U.h(RB.BOSS_H)))

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
