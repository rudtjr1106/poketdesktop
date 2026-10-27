# -*- coding: utf-8 -*-
"""숨는 기술 연출 검사 (2.0) — 공중날기·구멍파기·다이빙·고스트다이브 ... 와 모으는 기술.

    python client/test_vanish_fx.py

**창을 띄우지 않는다** (마지막 5번만 숨긴 Tk 창을 하나 쓴다). test_move_fx 와 같은 흉내 캔버스·시계
(tools/fx_preview)에 도트를 숨기고 옮기는 무대를 붙여 돌린다.

못 박는 것.

  1. 첫 턴(charge): 공격 연출은 안 틀고 숨는 연출만 - 끝나면 도트가 안 보이고 제자리에 있다.
     찌꺼기가 없고, 끝났다는 신호는 한 번만 온다.
  2. 둘째 턴: 다시 나타난 뒤에 공격한다 - 끝나면 보이고 제자리다. 고스트다이브는 안 보이는 채로 때리고
     끝날 때 나타난다. 다시 나오는 시간을 더해도 배틀 창이 기다려 주는 한도 안에 끝난다.
  3. 프리폴: 상대도 데리고 올라가고, 떨어뜨릴 때 같이 나타난다.
  4. 도중에 멈춰도(stop - 창 크기를 바꿀 때·건너뛸 때) 도트는 제자리고, 보임은 숨김 기록대로다.
  5. 모으는 기술(솔라빔 ...)은 숨지 않고 공격 연출도 안 튼다. 숨길 수 없는 무대에서도 터지지 않는다.
  6. Hiding: 쓰러지거나 바뀌면 바로 보이고, 데려간 상대도 놓인다. 바뀔 때만 화면을 부른다.
  7. 진짜 Tk 캔버스: 관장 배틀 창의 숨기기 · 옮기기 · 테두리 (숨긴 도트는 bbox 가 비어도 크기를 잰다).
"""
import json
import os
import sys
import tempfile

os.environ.setdefault("POKET_HOME", os.path.join(tempfile.gettempdir(), "poket-test-vanishfx"))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fx_preview as PV                                       # noqa: E402
from poketdesktop import battle_fx as FX                      # noqa: E402

FX.DEBUG = True                 # 연출 중의 예외를 삼키지 않는다
OK = FAIL = 0
HIDE_MS = 700                   # 숨는 연출의 한도
LIMIT_MS = 2400                 # 다시 나와서 때리기까지 (레이드 창이 2400ms 에 넘어간다)


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


class Stage(PV.FakeStage):
    """도트를 숨기고 옮길 수 있는 무대 (배틀 화면이 주는 것을 흉내 낸다)."""

    def __init__(self, hiding=True, **kw):
        PV.FakeStage.__init__(self, **kw)
        self.vis = {"me": True, "foe": True}
        self.calls = 0
        if hiding:
            self.hiding = FX.Hiding(self._show)

    def _show(self, who, on):
        self.calls += 1
        self.vis[who] = on

    def fx_shift(self, who, dx, dy):
        ox, oy = self.off[who]
        self.off[who] = (ox + dx, oy + dy)

    def fx_box(self, who):
        x, y = self.pos[who]
        ox, oy = self.off[who]
        z = 1.18 if who == "me" else 0.96
        return (x + ox - 17 * z, y + oy - 26 * z, x + ox + 17 * z, y + oy + 30 * z)


MOVES = dict((m.get("kr"), m) for m in json.load(
    open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8"))["moves"].values())


def play(stage, name, ev=None, who="me", stop_at=None, limit=LIMIT_MS + 600):
    """기술 사건 하나를 튼다. (끝난 횟수, 끝난 때, 공격 연출을 튼 횟수) 를 돌려준다."""
    other = "foe" if who == "me" else "me"
    ev = dict(ev or {}, t="move", who=who, move=name)
    done, attacks = [], []
    fx = FX.Effect(stage, MOVES[name], stage.pos[who], stage.pos[other],
                   lambda: done.append(stage.root.now), who=who, ev=ev)
    real = fx._play_move

    def attack():
        attacks.append(1)
        return real()
    fx._play_move = attack
    start = stage.root.now
    fx.play()
    while stage.root.now - start < limit and not done:
        if stop_at is not None and stage.root.now - start >= stop_at:
            fx.stop()
            break
        stage.root.advance(PV.FRAME_MS)
    stage.root.advance(400)                      # 남은 조각이 다 지워질 틈
    return len(done), (done[0] - start if done else None), len(attacks)


def home(stage, who):
    return abs(stage.off[who][0]) < 1e-6 and abs(stage.off[who][1]) < 1e-6


def t_two_turns():
    print("=== 1·2. 첫 턴에 숨고, 둘째 턴에 나와서 때린다 ===")
    for name, kind in (("공중날기", "fly"), ("뛰어오르기", "fly"), ("구멍파기", "dig"), ("다이빙", "dive"),
                       ("고스트다이브", "vanish"), ("섀도다이브", "vanish")):
        for who in ("me", "foe"):
            st = Stage()
            n, ms, att = play(st, name, {"charge": kind}, who=who)
            chk("%s(%s) 첫 턴: 숨는 연출만 %sms, 안 보이고 제자리, 찌꺼기 없음" % (name, who, ms),
                n == 1 and att == 0 and ms is not None and ms <= HIDE_MS and not st.vis[who]
                and home(st, who) and not st.cv.items and st.hiding.hidden(who) == kind and st.lunges == 0,
                (n, att, ms, st.vis, st.off, len(st.cv.items), st.hiding.kind))
            other = "foe" if who == "me" else "me"
            chk("  맞은편은 그대로 보인다", st.vis[other] and home(st, other), (st.vis, st.off))
            n, ms, att = play(st, name, {}, who=who)
            chk("%s(%s) 둘째 턴: 나와서 때린다 %sms, 보이고 제자리" % (name, who, ms),
                n == 1 and att == 1 and ms is not None and ms <= LIMIT_MS and st.vis[who] and home(st, who)
                and not st.cv.items and not st.hiding.hidden(who),
                (n, att, ms, st.vis, st.off, len(st.cv.items), st.hiding.kind))
    st = Stage()
    play(st, "고스트다이브", {"charge": "vanish"})
    seen = []
    real = st._show
    st._show = lambda who, on: (seen.append((st.root.now, who, on)), real(who, on))
    st.hiding.show = st._show
    play(st, "고스트다이브", {})
    chk("고스트다이브 둘째 턴: 공격이 끝날 때 나타난다 (그 전에는 안 보인다)",
        len(seen) == 1 and seen[0][1:] == ("me", True) and seen[0][0] > 300, seen)
    st = Stage()
    play(st, "공중날기", {"charge": "fly"})
    n, ms, att = play(st, "몸통박치기", {})
    chk("숨은 채로 다른 기술을 쓰면(잠금이 풀렸다) 그래도 나와서 쓴다", att == 1 and st.vis["me"] and home(st, "me"),
        (att, st.vis, st.off))


def t_sky_drop():
    print("=== 3. 프리폴: 상대도 데리고 올라간다 ===")
    st = Stage()
    n, ms, att = play(st, "프리폴", {"charge": "fly", "carry": True})
    chk("첫 턴: 둘 다 안 보이고 제자리", n == 1 and att == 0 and not st.vis["me"] and not st.vis["foe"]
        and home(st, "me") and home(st, "foe") and st.hiding.held == {"me": "foe"}, (st.vis, st.off, st.hiding.held))
    n, ms, att = play(st, "프리폴", {})
    chk("둘째 턴: 둘 다 내려와 보이고, 그다음에 때린다", n == 1 and att == 1 and st.vis["me"] and st.vis["foe"]
        and home(st, "me") and home(st, "foe") and not st.hiding.kind and not st.hiding.held,
        (st.vis, st.off, st.hiding.kind, st.hiding.held))
    st = Stage()
    play(st, "프리폴", {"charge": "fly", "carry": True})
    st.hiding.forget("me")
    chk("데려간 쪽이 쓰러지면 끌려간 상대도 놓인다", st.vis["me"] and st.vis["foe"] and not st.hiding.held, st.vis)


def t_stop():
    print("=== 4. 도중에 멈춰도 어긋나지 않는다 ===")
    for name, kind in (("공중날기", "fly"), ("구멍파기", "dig"), ("다이빙", "dive"), ("고스트다이브", "vanish")):
        for at in (60, 150, 240):
            st = Stage()
            n, _ms, _att = play(st, name, {"charge": kind}, stop_at=at)
            chk("%s 첫 턴 %dms 에 멈춤: 제자리, 숨김 기록대로 안 보인다, 찌꺼기 없음" % (name, at),
                n == 0 and home(st, "me") and not st.vis["me"] and st.hiding.hidden("me") == kind
                and not st.cv.items, (n, st.off, st.vis, len(st.cv.items)))
            n, _ms, _att = play(st, name, {}, stop_at=at // 2)
            chk("  둘째 턴 %dms 에 멈춤: 제자리, 보인다" % (at // 2),
                n == 0 and home(st, "me") and st.vis["me"] and not st.hiding.hidden("me") and not st.cv.items,
                (n, st.off, st.vis, len(st.cv.items)))


def t_power():
    print("=== 5. 모으는 기술 · 숨길 수 없는 무대 ===")
    for name, mt in (("솔라빔", None), ("솔라블레이드", None), ("불새", None), ("칼바람", None),
                     ("로켓박치기", None), ("메테오빔", None), ("일렉트로빔", None), ("프리즈볼트", None),
                     ("콜드플레어", None), ("지오컨트롤", None)):
        if name not in MOVES:
            chk("%s 이(가) 도감에 있다" % name, False)
            continue
        st = Stage()
        n, ms, att = play(st, name, {"charge": "power"})
        chk("%s 첫 턴: 모으기만 (%sms), 숨지 않는다" % (name, ms),
            n == 1 and att == 0 and ms <= HIDE_MS and st.vis["me"] and home(st, "me")
            and not st.cv.items and not st.hiding.kind, (n, att, ms, st.vis, st.hiding.kind))
        n, ms, att = play(st, name, {})
        chk("  둘째 턴: 그냥 공격", n == 1 and att == 1, (n, att))
    for kind in ("fly", "dig", "dive", "vanish"):
        st = Stage(hiding=False)
        n, ms, att = play(st, "공중날기", {"charge": kind})
        chk("숨길 수 없는 무대(%s): 터지지 않고 끝난다, 도트는 안 움직인다" % kind,
            n == 1 and att == 0 and home(st, "me") and not st.cv.items, (n, att, st.off))
    st = Stage()
    n, ms, att = play(st, "몸통박치기", {})
    chk("숨은 쪽이 없으면 예전 그대로", n == 1 and att == 1 and st.calls == 0, (n, att, st.calls))


def t_hiding():
    print("=== 6. Hiding ===")
    shown = []
    hd = FX.Hiding(lambda k, on: shown.append((k, on)))
    hd.forget("me")
    hd.sync("me")
    chk("숨은 적 없는 쪽은 화면을 안 부른다 (바탕화면 도트는 다시 띄우면 창이 다시 뜬다)", not shown, shown)
    hd.hide("me", "dig")
    hd.hide("me", "dig")
    chk("숨긴다 - 같은 일은 한 번만", shown == [("me", False)], shown)
    hd.apply("me")
    chk("다시 그린 도트에는 숨김을 다시 건다 (창 크기·폼)", shown[-1] == ("me", False) and len(shown) == 2, shown)
    hd.forget("me")
    chk("쓰러지거나 바뀌면 바로 보인다", shown[-1] == ("me", True) and not hd.hidden("me"), shown)
    hd.hide("a", "fly")
    hd.hide("b", "vanish")
    hd.forget_all()
    chk("판이 끝나면 전부 보인다", shown[-2:] in ([("a", True), ("b", True)], [("b", True), ("a", True)])
        and not hd.kind, shown)
    hd = FX.Hiding(lambda k, on: 1 / 0)
    FX.DEBUG = False                        # 여기서만 예외를 삼키는지 본다
    try:
        hd.hide("me", "fly")
    finally:
        FX.DEBUG = True
    chk("화면이 실패해도 기록은 남는다", hd.hidden("me") == "fly")


def t_edges():
    print("=== 6-2. 드문 경우 (독립 리뷰가 찾은 것) ===")
    st = Stage()
    play(st, "공중날기", {"charge": "fly"})
    n, ms, att = play(st, "칼춤", {"stay": True})
    chk("숨은 채로 춤을 따라 추면(stay) 숨은 채로 둔다", att == 1 and not st.vis["me"] and st.hiding.hidden("me") == "fly"
        and home(st, "me"), (att, st.vis, st.hiding.kind))
    st = Stage()
    play(st, "공중날기", {"charge": "fly"})
    shown = []
    real = st.hiding.show
    st.hiding.show = lambda k, on: (shown.append((k, on)), real(k, on))
    n, ms, att = play(st, "구멍파기", {"charge": "dig"})
    chk("숨어 있다가 새 두 턴 기술: 먼저 보이고 다시 숨는다 (잠금이 풀려 내려와 있었다)",
        shown[:1] == [("me", True)] and not st.vis["me"] and st.hiding.hidden("me") == "dig" and att == 0, shown)

    from poketdesktop import duel_scene as DS
    sc = DS.FightScene.__new__(DS.FightScene)
    sc.sides = {"a": DS._Side(), "b": DS._Side()}
    sc.pane = None
    sc.hiding = FX.Hiding(lambda s, on: setattr(sc.sides[s], "gone", not on))
    real_load = DS.load_art
    DS.load_art = lambda *a, **k: None
    try:
        m = {"num": 746, "name": "약어리", "hp": 10, "maxhp": 100}
        sc.hiding.hide("a", "dive")
        sc._enter("a", m, keep=True)
        chk("구경: 숨은 채 폼이 바뀌면(메가·폼) 숨긴 채로", sc.sides["a"].gone and sc.hiding.hidden("a") == "dive")
        sc._enter("a", m)
        chk("구경: 다른 포켓몬이 나오면 보인다", not sc.sides["a"].gone and not sc.hiding.hidden("a"))
    finally:
        DS.load_art = real_load

    from poketdesktop import arena as AR
    cls = [c for c in vars(AR).values() if isinstance(c, type) and "_on_ko" in vars(c)][0]
    ar = cls.__new__(cls)
    calls = []
    ar.hiding = FX.Hiding(lambda s, on: calls.append((s, on)))
    ar.active = {"me": object(), "foe": object()}
    ar.down, ar.slot, ar.scale = {"me": set(), "foe": set()}, {"me": 0, "foe": 0}, 1.0
    ar.after = lambda ms, fn: fn()
    ar.hiding.hide("me", "fly")
    type(ar)._on_ko(ar, {"side": "both"}, lambda: None)
    chk("투기장: 턴 제한으로 같이 끝나면 링을 비우기 전에 보이게 한다", calls[-1] == ("me", True)
        and not ar.hiding.hidden("me"), calls)

    from poketdesktop import desktop_battle as DB

    class Win(object):
        def __init__(self):
            self.log = []

        def withdraw(self):
            self.log.append("withdraw")

        def deiconify(self):
            self.log.append("show")

        def update_idletasks(self):
            pass

        def attributes(self, *a):
            pass

    class Pet(object):
        pass
    pet = Pet()
    pet.win, pet.badge_win = Win(), Win()
    d = DB.DesktopBattle.__new__(DB.DesktopBattle)
    d.mine, d.foe, d.layer, d.closed = None, pet, None, False
    d.hiding = FX.Hiding(d._pet_show)
    d.hiding.hide("foe", "fly")
    chk("야생 배틀: 숨으면 야생 표식도 같이 숨는다", pet.win.log == ["withdraw"] and pet.badge_win.log == ["withdraw"],
        (pet.win.log, pet.badge_win.log))
    pet.win.log, pet.badge_win.log = ["show"], ["show"]         # 놓친 볼이 도로 띄웠다 (show_wild_sprite)
    d.app = Pet()
    d.app.notify = lambda *a: None
    d.play = lambda *a: None
    d.after_ball({"caught": False, "events": []})
    chk("야생 배틀: 볼을 놓친 뒤에도 숨은 자리면 다시 감춘다", pet.win.log[-1] == "withdraw"
        and pet.badge_win.log[-1] == "withdraw" and d.hiding.hidden("foe") == "fly", (pet.win.log, pet.badge_win.log))


def t_tk():
    print("=== 7. 진짜 Tk 캔버스 (관장 배틀 창의 숨기기 · 옮기기 · 테두리) ===")
    try:
        import tkinter as tk
        from poketdesktop import platform_os as PLAT
        PLAT.before_tk()
        root = tk.Tk()
        root.withdraw()
    except Exception as e:                                  # noqa: BLE001
        chk("Tk 를 열 수 있다", False, e)
        return
    try:
        from poketdesktop import ui_gym_battle as GB
        from poketdesktop import ui_raid_battle as RB

        class Win(object):
            pass
        w = Win()
        w.cv = tk.Canvas(root, width=300, height=200)
        ph = tk.PhotoImage(width=40, height=50)
        w.sprite = {"me": w.cv.create_image(100, 150, anchor="s", image=ph)}
        w.anims = {"me": ([ph], [100])}
        box = GB.GymBattleWindow.fx_box(w, "me")
        chk("테두리: 아래 가운데에 붙은 40x50", box == (80.0, 100.0, 120.0, 150.0), box)
        GB.GymBattleWindow._sprite_show(w, "me", False)
        chk("숨기면 Tk 의 bbox 는 빈다", not w.cv.bbox(w.sprite["me"]), w.cv.bbox(w.sprite["me"]))
        chk("  그래도 테두리는 잰다", GB.GymBattleWindow.fx_box(w, "me") == box)
        GB.GymBattleWindow.fx_shift(w, "me", 0, -30)
        chk("옮긴다", w.cv.coords(w.sprite["me"]) == [100.0, 120.0], w.cv.coords(w.sprite["me"]))
        GB.GymBattleWindow._sprite_show(w, "me", True)
        chk("다시 보인다", w.cv.itemcget(w.sprite["me"], "state") == "normal")
        w.root = root
        w.fx_shift = lambda *a: GB.GymBattleWindow.fx_shift(w, *a)
        w.fx_box = lambda *a: GB.GymBattleWindow.fx_box(w, *a)
        st = GB._FxStage(w, 2.0)
        st.fx_shift("me", 0, 15)
        chk("2배 무대: 연출 좌표 15 = 창 30", w.cv.coords(w.sprite["me"]) == [100.0, 150.0], w.cv.coords(w.sprite["me"]))
        chk("2배 무대: 테두리는 연출 좌표로", st.fx_box("me") == (40.0, 50.0, 60.0, 75.0), st.fx_box("me"))
        w.sprite = {"boss": w.sprite["me"]}
        w.anims = {"boss": ([ph], [100])}
        RB.RaidBattleWindow._sprite_show(w, "boss", False)
        RB.RaidBattleWindow._sprite_show(w, 3, False)          # 없는 자리는 조용히 넘어간다
        chk("레이드: 자리로 숨긴다", w.cv.itemcget(w.sprite["boss"], "state") == "hidden")
        chk("레이드: 없는 자리의 테두리는 None", RB.RaidBattleWindow.fx_box(w, 3) is None)
    finally:
        root.destroy()


def main():
    t_two_turns()
    t_sky_drop()
    t_stop()
    t_power()
    t_hiding()
    t_edges()
    t_tk()
    print("")
    print("=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
