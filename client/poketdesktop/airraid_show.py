# -*- coding: utf-8 -*-
"""공습 장면 (2.3.0) — 서버가 계산해 둔 공습(common/airraid.py)을 바탕화면에서 재생한다.

**아무것도 물어보지 않는다.** 판은 서버에서 이미 끝났다 (투기장 arena.py 와 같은 원칙) - 재생 도중 앱을 꺼도
결과 · 보상은 그대로다.

    경보    내 포켓몬들 머리 위에 '!' , 가운데 '공습이다!'
    낙하    공습 포켓몬이 화면 위에서 한 마리씩 낙하산(airraid_art)을 타고 흔들리며 내려온다. 첫 상대는 맡을 내
            포켓몬 옆에, 남는 것은 무대 양 끝에 내려 기다린다. 땅에 닿으면 낙하산이 접혀 사라진다.
    전투    짝(Lane)마다 동시에 - 서버의 전역 턴 하나에 모든 짝이 한 턴씩 (각자 야생 배틀 연출: 돌진 · 체력 막대 ·
            떠오르는 글씨 · 기술 연출 · 쓰러짐). 턴이 끝나면 새 짝(pair)이 생기는 대로 이긴 쪽이 다음 상대에게
            걸어간다.
    결과    '공습을 막았다!' / '공습에 밀렸다…', 남은 공습 포켓몬은 화면 끝으로 걸어 나간다.
    정리    **무엇이 터져도 반드시** (cleanup - 몇 번 불러도 안전). 내 포켓몬은 제자리로, 공습 포켓몬 · 낙하산 창 ·
            레이어는 없앤다, 이름표를 되살리고 바탕화면을 돌려준다.

내 포켓몬은 **지금 바탕화면에 선 그 도트**가 싸운다 (평소 걸어다니던 자리 그대로). 명단(ids)의 포켓몬이 바탕화면에
없으면(그새 파티를 바꿨다) 대신 도트를 세웠다가 치운다.
"""
import math
import random
import time
import traceback

from common.korean import natural

from . import airraid_art as ART
from . import arena_layout as L
from . import battle_fx as FX
from . import config
from . import fx_layer as FL
from . import platform_os as PLAT
from .arena import ArenaPet, SKIP_TEXT, _short
from .overlay import work_area

SPEED = 1.0                  # 검사가 빠르게 돌린다
ALERT_MS = 1500
DROP_MS = 3600               # 화면 위에서 땅까지
DROP_GAP = 280               # 한 마리씩 차례로 뛰어내린다
FOLD_MS = 560
WALK_MS = 900                # 다음 상대에게 걸어가기 (가장 짧게)
WALK_SPEED = 260             # px/초 - 멀리서 기다리던 적은 그만큼 오래 걷는다
WALK_MAX_MS = 2600
FACE_GAP = 92                # 마주 선 둘의 발 사이 (px)
EV_GAP = 240
TURN_GAP = 260               # 전역 턴 사이
TARGET_SECONDS = 40          # 싸움이 길면 간격을 줄인다 (arena._pace 와 같은 틀)
STALL_MS = 20000             # 장면의 예약이 이만큼(실제 ms) 하나도 안 돌면 멈춘 것으로 보고 정리 (멈춤 감시)
MIN_SCALE = 0.35
RESULT_MS = 2400
LEAVE_MS = 1300
CHUTE_K = 2                  # 낙하산 배율
CHUTE_KEY = (255, 0, 254)    # 낙하산 창의 투명색
SWAY = 12                    # 흔들림 (px)
WIN_TEXT = "공습을 막았다!"
LOSE_TEXT = "공습에 밀렸다…"


def ms(x):
    return max(1, int(x / float(SPEED)))


class Raider(object):
    """공습 포켓몬 하나: 도트(ArenaPet) + 낙하산 창(duel_scene.Sprite)."""

    def __init__(self, i, info):
        self.i, self.info = i, info
        self.pet = None
        self.chute = None
        self.land = None          # 발 자리 (x, y)
        self.down = False
        self.fought = False


class Lane(object):
    """짝 하나 (서버의 판 d). 기술 연출(battle_fx.Effect)이 무대로 쓴다: cv · root · lunge · fx_shift · fx_box · hiding."""

    def __init__(self, scene, d, me, foe):
        self.sc = scene
        self.d = d
        self.me, self.foe = me, foe
        self.root = scene.root
        self.active = True
        self.playing = False
        self.queue = []
        self.fx = None
        self.hiding = FX.Hiding(self._pet_show)

    @property
    def cv(self):
        return self.sc.layer.cv if self.sc.layer else None

    def pet(self, who):
        return self.me if who == "me" else self.foe if who == "foe" else None

    def other(self, who):
        return self.pet("foe" if who == "me" else "me")

    # ---- battle_fx 가 부르는 것 ----
    def lunge(self, who, done):
        pet, other = self.pet(who), self.other(who)
        if not pet or not other:
            return done()
        hx, hy = pet.x, pet.y
        dx = 24 if other.x > pet.x else -24
        n = 5

        def go(i):
            if self.sc.closed:
                return
            if i > n * 2:
                pet.x, pet.y = hx, hy
                pet.place()
                return self.sc.after(60, done)
            k = i if i <= n else n * 2 - i
            pet.x = hx + dx * k / float(n)
            pet.place()
            self.sc.after(22, lambda: go(i + 1))
        go(1)

    def fx_shift(self, who, dx, dy):
        p = self.pet(who)
        if p is not None:
            p.x += dx
            p.y += dy
            p.place()

    def fx_box(self, who):
        p = self.pet(who)
        if p is None:
            return None
        x0, y0 = self.sc.to_local(p.x, p.y)
        return (x0, y0, x0 + p.fw, y0 + p.fh)

    def _pet_show(self, who, on):
        p = self.pet(who)
        if p is None:
            return
        try:
            if on:
                PLAT.show_again(p.win)
                if self.sc.layer:
                    self.sc.layer.raise_above()
            else:
                p.win.withdraw()
        except Exception:                                   # noqa: BLE001
            pass

    # ---- 재생 ----
    def play(self, events, done):
        """이 짝의 이번 턴 사건들을 차례로. 다 그리면 done."""
        self.queue = FX.annotate(list(events))
        self.playing = True

        def step():
            if self.sc.closed:
                return
            if not self.queue:
                self.playing = False
                return done()
            ev = self.queue.pop(0)
            try:
                self.render(ev, lambda: self.sc.after(self.sc.gap, step))
            except Exception as e:                          # noqa: BLE001
                config.log("공습 재생 오류(%s): %s\n%s" % (ev.get("t"), e, traceback.format_exc()))
                self.sc.fail()
        step()

    def render(self, ev, done):
        sc = self.sc
        t = ev.get("t")
        who = ev.get("who")
        self._apply_hp(ev)
        if t == "end":
            return self._on_end(ev, done)
        src, dst = self.pet(who), self.other(who)
        if t == "move" and src is not None:
            sc.float_over(src, ev.get("move") or "", "#ffffff")
        if t == "move" and src and dst and sc.layer:
            move = sc.find_move(ev)
            self.fx = FX.Effect(self, move, sc.center(src), sc.center(dst),
                                lambda: sc.after(int(140 * sc.scale), done), who=who, ev=ev)
            return self.fx.play()
        if t == "hit":
            side = self.pet(ev.get("target"))
            if side:
                if ev.get("crit"):
                    sc.float_over(side, "급소!", "#ffd447")
                eff = ev.get("eff", 1)
                if eff and eff > 1:
                    sc.float_over(side, "효과가 굉장하다!", "#7bffa0")
                elif eff and eff < 1:
                    sc.float_over(side, "효과가 별로...", "#b0b0c0")
                return sc.shake(side, done)
        if t in ("chip", "recoil") and src:
            sc.float_over(src, "-%d" % (ev.get("damage") or ev.get("amount") or 0), "#ff8a8a")
        if t == "heal" and src:
            sc.float_over(src, "+%d" % (ev.get("amount") or 0), "#7bffa0")
        if t in ("status", "msg") and src:
            sc.float_over(src, SKIP_TEXT.get(ev.get("status")) or _short(ev.get("text")), "#c9a0ff")
        if t == "ailment" and src:
            sc.float_over(src, (ev.get("text") or "").split(" 은(는) ")[-1].replace(" 상태가 되었다!", ""), "#ff9d55")
        if t == "ability" and src:
            sc.float_over(src, ev.get("abilityKr") or _short(ev.get("text")), "#ffd66b")
        if t == "immune" and src:
            sc.float_over(src, "효과가 없다...", "#9a9ab0")
        if t == "faint":
            p = self.pet(who)
            self.hiding.forget(who)
            if p is not None and not getattr(p, "down", False):
                return sc.faint(p, done)
        return sc.after(max(60, int(sc.gap * 0.7)), done)

    def _apply_hp(self, ev):
        if "hp" not in ev:
            return
        side = ev.get("target") if ev.get("t") == "hit" else ev.get("who")
        p = self.pet(side)
        if p is not None:
            bar = self.sc.bar_for(p)
            if bar:
                bar.set(ev["hp"], ev.get("maxhp") or 1)

    def _on_end(self, ev, done):
        """판이 끝났다. 서버가 짝 턴 상한으로 물린 쪽은 쓰러지는 사건이 없다 - 여기서 쓰러뜨린다."""
        self.active = False
        win = ev.get("win")
        losers = [self.me, self.foe] if win == "both" else [self.foe] if win == "me" else [self.me]
        left = [p for p in losers if p is not None and not getattr(p, "down", False)]
        if not left:
            return self.sc.after(int(self.sc.gap * 0.5), done)
        n = [len(left)]

        def one():
            n[0] -= 1
            if n[0] <= 0:
                done()
        for p in left:
            self.sc.faint(p, one)


class AirRaidShow(object):

    def __init__(self, app, view, on_done=None):
        self.app = app
        self.root = app.root
        self.view = view or {}
        self.on_done = on_done
        self.closed = False
        self.phase = "new"
        self.jobs = []
        self.layer = None
        self.bars = {}
        self.texts = []
        self.mine = []              # 내 쪽 도트 (명단 차례)
        self.made = []              # 대신 세운 도트
        self.frozen = []            # 공습 동안 멈춰 세운 바탕화면 도트
        self.home = {}
        self.raiders = []
        self.lanes = {}
        self.steps = []
        self.pairs_done = 0
        self.gaps = []              # 다음 상대에게 간 자리와 가장 가까운 다른 도트의 발 사이 (검사가 본다)
        self.walkers = []           # 다음 짝마다 걸어온 쪽 ('foe' - 검사가 본다)
        self.gap = EV_GAP
        self.scale = 1.0
        self.stop_plate = None
        self.bar_job = None
        self._names_ov = None
        self.result_ev = None
        self.beat = time.monotonic()
        self.watch_job = None
        self.rng = random.Random(len(self.view.get("events") or []))

    # ---------------- 도구 ----------------
    def after(self, t, fn):
        if self.closed:
            return None

        def run():
            if self.closed:
                return
            self.beat = time.monotonic()             # 진행했다 (멈춤 감시)
            try:
                fn()
            except Exception as e:                          # noqa: BLE001
                config.log("공습 장면 오류: %s\n%s" % (e, traceback.format_exc()))
                self.fail()
        j = self.root.after(max(1, int(t)), run)
        self.jobs.append(j)
        if len(self.jobs) > 400:
            self.jobs = self.jobs[-200:]
        return j

    def to_local(self, x, y):
        return self.layer.to_local(x, y) if self.layer else (x, y)

    def center(self, pet):
        return self.to_local(pet.x + pet.fw / 2.0, pet.y + pet.fh / 2.0)

    def find_move(self, ev):
        name = ev.get("move")
        dex = getattr(self.app, "dex", None)
        if dex and name:
            for m in (getattr(dex, "moves", None) or {}).values():
                if m.get("kr") == name:
                    return m
        return {"type": ev.get("moveType") or "NORMAL", "cat": ev.get("cat") or "physical", "flags": []}

    def float_over(self, pet, text, color, ms_=900):
        if not self.layer or not text or not pet:
            return
        try:
            self.texts.append(FL.FloatText(self.layer, pet.x + pet.fw / 2.0, pet.y - 6, text, color, ms_))
        except Exception:                                   # noqa: BLE001
            pass

    def bar_for(self, pet):
        b = self.bars.get(id(pet))
        if b is None and self.layer:
            b = FL.HpBar(self.layer)
            self.bars[id(pet)] = b
        return b

    def feet(self, pet):
        return pet.x + pet.fw / 2.0, pet.y + pet.fh

    def place_feet(self, pet, fx, fy):
        pet.x, pet.y = L.feet_to_topleft(fx, fy, pet.fw, pet.fh)
        pet.place()

    def fail(self):
        """재생 중 무엇이 터졌다 - 그만 틀고 정리한다 (결과 · 보상은 서버에 이미 있다)."""
        self.cleanup()

    # ---------------- 시작 ----------------
    def start(self):
        try:
            self._setup()
        except Exception as e:                              # noqa: BLE001
            config.log("공습 준비 실패: %s\n%s" % (e, traceback.format_exc()))
            self.cleanup()

    def _setup(self):
        ov = self.app.overlay
        evs = list(self.view.get("events") or [])
        if not ov or not evs or evs[0].get("t") != "teams":
            return self.cleanup()
        self.teams = evs[0]
        ov.locked = True
        self._names_ov = ov
        ov.block_names()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        try:
            self.work = L.work_for(ov.area(), PLAT.screens(sw, sh), PLAT.screen_works(sw, sh))
        except Exception:                                   # noqa: BLE001
            self.work = None
        self.work = self.work or work_area(sw, sh)
        self.area = ov.area()
        self._my_side(ov)
        self._parse(evs[1:])
        self._pace()
        self._plan_landing()
        xs = [r.land[0] for r in self.raiders] + [self.feet(p)[0] for p in self.mine if p]
        ys = [r.land[1] for r in self.raiders] + [self.feet(p)[1] for p in self.mine if p]
        wl, wt, wr, wb = self.work
        rect = (max(wl, int(min(xs)) - 80), max(wt, int(min(ys)) - 160), min(wr, int(max(xs)) + 80),
                min(wb, int(max(ys)) + 10))
        self.layer = FL.open_layer(self.root, rect)
        # 그만 보기(×)는 두지 않는다 - 공습은 중간에 취소할 수 없다 (사용자 11/08). 끝나는 길은 끝 · 마감 · 로그아웃뿐
        self._tick()
        # 멈춤 감시 (독립 검토): 기술 연출 한 단계가 끝을 안 알리면 다음 턴을 영영 기다린다 - 그동안 바쁨이라 풀숲 ·
        # 집중 · 대전이 막힌다. **전체 길이가 아니라 진행이 멎은 시간**으로 본다 (예상 길이로 마감을 두었더니 기술
        # 연출이 예상보다 길거나 PC 가 느리면 멀쩡한 공습을 잘랐다). 장면의 예약(after)이 STALL_MS 동안 하나도 안
        # 돌면 정리한다 (결과 · 보상은 서버에 이미 있다)
        self.beat = time.monotonic()
        self._watch()
        self._alert()

    def _watch(self):
        if self.closed:
            return
        if (time.monotonic() - self.beat) * 1000.0 > STALL_MS:
            config.log("공습 장면이 %d초 동안 멈춰 정리합니다 (단계 %s)" % (STALL_MS // 1000, self.phase))
            return self.cleanup()
        self.watch_job = self.root.after(1000, self._watch)

    def _my_side(self, ov):
        """명단(ids) 차례로 내 쪽 도트. 바탕화면의 다른 도트는 공습 동안 멈춰 세운다."""
        ids = list(self.view.get("ids") or [])
        roster = self.teams.get("me") or []
        x1, y1, x2, y2 = self.area
        for pid, p in list(ov.pets.items()):
            p.battling = True
            p.state = "idle"
            self.frozen.append(p)
            self.home[id(p)] = (p.x, p.y)
        for i, info in enumerate(roster):
            pid = ids[i] if i < len(ids) else None
            p = ov.pets.get(pid) if pid is not None else None
            if p is None:
                p = self._stand_in(ov, info, i)
                if p is not None:
                    fx = x1 + 60 + i * (FACE_GAP + 40)
                    self.place_feet(p, min(fx, x2 - 40), y2 - 8)
            self.mine.append(p)              # 못 세웠으면 None - 자리를 비워야 서버의 번호(mi)가 안 밀린다 (독립 검토)

    def _stand_in(self, ov, info, i):
        try:
            p = ov.make({"id": -2000 - i, "num": info.get("num"), "shiny": bool(info.get("shiny")),
                         "tint": info.get("tint"),
                         "info": {"name": info.get("name"), "species": info.get("species"),
                                  "level": info.get("level"), "types": []}}, cls=ArenaPet)
        except Exception as e:                              # noqa: BLE001
            config.log("공습: 대신 세울 도트를 못 만들었습니다: %s" % e)
            return None
        if p is None:
            return None
        p.stand_in = True
        ov.extra.append(p)
        self.made.append(p)
        return p

    def _parse(self, evs):
        """서버 로그 -> 처음 짝 + 턴마다 {짝 d: 사건들} · 그 턴 뒤 새 짝들 · 결과."""
        self.first_pairs = []
        cur = None
        for e in evs:
            t = e.get("t")
            if t == "raid":
                self.result_ev = e
                continue
            if t == "turn":
                cur = {"lanes": {}, "pairs": [], "post": {}}
                self.steps.append(cur)
                continue
            if cur is None:
                if t == "pair":
                    self.first_pairs.append(e)
                continue                                    # 처음 짝의 등장 사건(압정 …)은 그리지 않는다
            if t == "pair":
                cur["pairs"].append(e)
                continue
            d = e.get("d")
            if d is None:
                continue
            if any(p["d"] == d for p in cur["pairs"]):
                cur["post"].setdefault(d, []).append(e)      # 새 짝의 등장 사건 - 걸어간 뒤에
            else:
                cur["lanes"].setdefault(d, []).append(e)

    def _pace(self):
        n = sum(max(len(v) for v in s["lanes"].values()) if s["lanes"] else 1 for s in self.steps) or 1
        want = TARGET_SECONDS * 1000.0
        raw = n * EV_GAP
        self.scale = max(MIN_SCALE, min(1.0, want / raw)) if raw > want else 1.0
        self.gap = ms(max(60, int(EV_GAP * self.scale)))

    def _plan_landing(self):
        """첫 상대는 맡을 내 포켓몬 옆에, 남는 공습 포켓몬은 무대 양 끝에."""
        foes = self.teams.get("foe") or []
        self.raiders = [Raider(i, info) for i, info in enumerate(foes)]
        x1, y1, x2, y2 = self.area
        wl, wt, wr, wb = self.work
        cx = (x1 + x2) / 2.0
        spots = [self.feet(p) for p in self.mine if p]      # 이미 선 자리 (겹치지 않게)

        def crowd(x, y):
            return sum(1 for (px, py) in spots if abs(px - x) < 56 and abs(py - y) < 40)

        def pick(cands, y):
            ok = [x for x in cands if wl + 30 < x < wr - 30]
            if not ok:
                return max(wl + 30, min(wr - 30, cands[0]))
            return min(ok, key=lambda x: (crowd(x, y), ok.index(x)))
        for e in self.first_pairs:
            mi, fi = e["mi"], e["fi"]
            if mi >= len(self.mine) or fi >= len(self.raiders) or self.mine[mi] is None:
                continue
            mx, my = self.feet(self.mine[mi])
            side = 1 if mx < cx else -1
            lx = pick([mx + sd * FACE_GAP * k for k in (1.0, 1.4, 1.8) for sd in (side, -side)], my)
            self.raiders[fi].land = (lx, my)
            spots.append((lx, my))
        ground = max([self.feet(p)[1] for p in self.mine if p] or [y2 - 8])
        k = 0
        for r in self.raiders:
            if r.land is not None:
                continue
            ly = min(wb - 4, ground - self.rng.randint(0, 14))
            # 기다리는 공습 포켓몬은 무대 밖 왼쪽부터 (오른쪽 아래가 무대라 왼쪽이 넓다), 그다음 오른쪽
            cands = ([x1 - 50 - j * 78 for j in range(8)] + [x2 + 50 + j * 78 for j in range(4)]
                     + [x1 + 50 + j * 78 for j in range(int((x2 - x1) // 78))])   # 영역이 화면 전체면 영역 안에
            lx = pick([x for x in cands if crowd(x, ly) == 0] or cands, ly)
            r.land = (lx, ly)
            spots.append((lx, ly))
            k += 1

    # ---------------- 경보 · 낙하 ----------------
    def _alert(self):
        self.phase = "alert"
        here = [p for p in self.mine if p]
        for p in here:
            self.float_over(p, "!", "#ff5a5a", ms(ALERT_MS))
        if here:
            mid = here[len(here) // 2]
            self.after(ms(260), lambda: self.float_over(mid, "공습이다!", "#ffd447", ms(ALERT_MS)))
        self.after(ms(ALERT_MS), self._drop)

    def _drop(self):
        self.phase = "drop"
        self.landed = 0
        if not self.raiders:
            return self._fight()
        for r in self.raiders:
            self.after(ms(r.i * DROP_GAP), lambda r=r: self._drop_one(r))

    def _drop_one(self, r):
        ov = self.app.overlay
        info = r.info
        try:
            pet = ov.make({"id": -1000 - r.i, "num": info.get("num"), "shiny": False, "tint": None,
                           "info": {"name": info.get("name"), "species": info.get("species"),
                                    "level": info.get("level"), "types": []}}, cls=ArenaPet)
        except Exception as e:                              # noqa: BLE001
            config.log("공습 포켓몬 도트 실패: %s" % e)
            pet = None
        if pet is None:
            r.down = True                                   # 도트가 없으면 이 공습 포켓몬은 그리지 않는다
            return self._landed(r)
        r.pet = pet
        ov.extra.append(pet)
        try:
            from .duel_scene import Sprite
            img = ART.scaled(ART.parachute(r.i), CHUTE_K)
            r.chute = Sprite(self.root, CHUTE_KEY, img.size)
            r.chute_img = r.chute.load([img])[0]
            r.chute.show(r.chute_img)
        except Exception as e:                              # noqa: BLE001
            config.log("낙하산 창 실패: %s" % e)
            r.chute = None
        lx, ly = r.land
        top = self.work[1] - pet.fh
        r.top = top                                         # 화면 위 끝에서 (검사가 본다)
        phase = self.rng.random() * math.pi * 2
        steps = max(1, int(ms(DROP_MS) / 33))
        self.place_feet(pet, lx, top)
        if self.layer:
            self.layer.raise_above()

        def go(i):
            if self.closed or r.pet is None:
                return
            k = min(1.0, i / float(steps))
            e = k * (2 - k) if k > 0.85 else k              # 마지막에 살짝 느려진다
            fy = top + (ly - top) * e
            sway = math.sin(phase + k * math.pi * 3) * SWAY * (1.0 - k)
            self.place_feet(pet, lx + sway, fy)
            if r.chute is not None:
                r.chute.move(lx + sway, pet.y + 8)
            if k >= 1.0:
                return self._fold(r)
            self.after(33, lambda: go(i + 1))
        go(0)

    def _fold(self, r):
        if r.chute is None:
            return self._landed(r)
        try:
            frames = [r.chute.load([ART.scaled(f, CHUTE_K)])[0] for f in ART.folding(r.i)]
        except Exception:                                   # noqa: BLE001
            frames = []
        n = len(frames)

        def go(i):
            if self.closed:
                return
            if i >= n:
                if r.chute is not None:
                    r.chute.destroy()
                    r.chute = None
                return self._landed(r)
            r.chute.show(frames[i])
            self.after(ms(FOLD_MS / max(1, n)), lambda: go(i + 1))
        go(0)

    def _landed(self, r):
        self.landed += 1
        if self.landed >= len(self.raiders):
            self.after(ms(300), self._fight)

    # ---------------- 전투 ----------------
    def _fight(self):
        self.phase = "fight"
        for e in self.first_pairs:
            self._make_lane(e)
            self.pairs_done += 1
        self.step_i = 0
        self.after(ms(500), self._next_step)

    def _make_lane(self, e):
        mi, fi = e["mi"], e["fi"]
        me = self.mine[mi] if mi < len(self.mine) else None
        r = self.raiders[fi] if fi < len(self.raiders) else None
        foe = r.pet if r else None
        if r:
            r.fought = True
        for p in (me, foe):                  # 숨는 기술(공중날기 · 구멍파기)로 숨은 채 이긴 도트 - 새 짝은 모른다
            if p is not None and not getattr(p, "down", False):
                try:
                    if p.win.state() == "withdrawn":
                        PLAT.show_again(p.win)
                except Exception:                           # noqa: BLE001
                    pass
        lane = Lane(self, e["d"], me, foe)
        self.lanes[e["d"]] = lane
        for p, side in ((me, "me"), (foe, "foe")):
            if p is None:
                continue
            b = self.bar_for(p)
            info = e.get(side) or {}
            if b:
                b.set(info.get("hp", 1), info.get("maxhp", 1))
                b.shown = b.ratio
        if me and foe:
            me.face_towards(foe.x)
            foe.face_towards(me.x)
        return lane

    def _next_step(self):
        if self.closed:
            return
        if self.step_i >= len(self.steps):
            return self._result()
        s = self.steps[self.step_i]
        self.step_i += 1
        lanes = [(self.lanes.get(d), evs) for d, evs in s["lanes"].items() if self.lanes.get(d)]
        left = [len(lanes)]

        def one():
            left[0] -= 1
            if left[0] <= 0:
                self.after(ms(TURN_GAP * self.scale), lambda: self._pairs(s))
        if not lanes:
            return self._pairs(s)
        for lane, evs in lanes:
            lane.play(evs, one)

    def _pairs(self, s):
        """이번 턴 뒤 새로 생긴 짝: 이긴 쪽이 다음 상대에게 걸어간다 (동시에)."""
        pairs = s.get("pairs") or []
        if not pairs:
            return self._next_step()
        left = [len(pairs)]

        def one():
            left[0] -= 1
            if left[0] <= 0:
                self._next_step()
        for e in pairs:
            lane = self._make_lane(e)
            self.pairs_done += 1
            post = (s.get("post") or {}).get(e["d"]) or []
            self._approach(lane, e, lambda lane=lane, post=post: lane.play(post, one) if post else one())

    def _approach(self, lane, e, done):
        """새 짝이 마주 선다. **늘 남은 적(공습 쪽)이 우리 포켓몬 쪽으로 걸어온다** - 우리 포켓몬은 제자리에서 맞는다
        (사용자 11/08 '우리 포켓몬이 잡으러 가지 말고 남은 적들이 우리 팀 쪽으로'). 멀리서 기다리던 적은 그만큼 오래 걷는다."""
        me, foe = lane.me, lane.foe
        if not me or not foe:
            return done()
        walker, stay = foe, me
        self.walkers.append("foe")
        sx, sy = self.feet(stay)
        side = 1 if self.feet(walker)[0] >= sx else -1
        tx = self._free_x(sx, sy, side, (walker, stay))
        others = self._standing((walker, stay))
        near = [abs(self.feet(p)[0] - tx) for p in others if abs(self.feet(p)[1] - sy) < 40]
        self.gaps.append(min(near) if near else 999)
        wx, wy = self.feet(walker)
        t = max(WALK_MS, min(WALK_MAX_MS, (abs(tx - wx) + abs(sy - wy)) * 1000.0 / WALK_SPEED))
        self.walk(walker, tx, sy, ms(t), lambda: (walker.face_towards(stay.x), stay.face_towards(walker.x),
                                                   done()))

    def _standing(self, skip=()):
        """지금 서 있는 도트 (쓰러지지 않은 내 쪽 · 공습 쪽)."""
        out = [p for p in self.mine if p and not getattr(p, "down", False)]
        out += [r.pet for r in self.raiders if r.pet is not None and not getattr(r.pet, "down", False)]
        return [p for p in out if p not in skip]

    def _free_x(self, sx, sy, side, skip=()):
        """(sx, sy) 의 상대 옆에 설 x - 다른 도트와 겹치지 않는 쪽 · 거리부터 (안 되면 가장 덜 붐비는 곳)."""
        wl, wt, wr, wb = self.work
        others = self._standing(skip)
        best = None
        for k in (1.0, 1.5, 2.0):
            for sd in (side, -side):
                tx = sx + sd * FACE_GAP * k
                if not (wl + 30 < tx < wr - 30):
                    continue
                crowd = sum(1 for p in others if abs(self.feet(p)[0] - tx) < 56 and abs(self.feet(p)[1] - sy) < 40)
                if crowd == 0:
                    return tx
                if best is None or crowd < best[0]:
                    best = (crowd, tx)
        return best[1] if best else sx + side * FACE_GAP

    def walk(self, pet, fx, fy, t, done=None):
        tx, ty = L.feet_to_topleft(fx, fy, pet.fw, pet.fh)
        x0, y0 = pet.x, pet.y
        steps = max(1, int(t / 33))
        pet.state = "walk"

        def go(i):
            if self.closed:
                return
            k = min(1.0, i / float(steps))
            nx, ny = x0 + (tx - x0) * k, y0 + (ty - y0) * k
            pet.walked = getattr(pet, "walked", 0) + abs(nx - pet.x) + abs(ny - pet.y)
            if i == 1 or (i % 4 == 0 and k < 1.0):
                pet.turn_to(tx - pet.x, ty - pet.y)
            pet.x, pet.y = nx, ny
            pet.place()
            if k >= 1.0:
                pet.state = "idle"
                return done() if done else None
            self.after(33, lambda: go(i + 1))
        go(1)

    # ---------------- 작은 연출 ----------------
    def shake(self, pet, done):
        hx = pet.x
        seq = [-7, 7, -5, 5, -3, 3, 0]

        def go(i):
            if self.closed:
                return
            if i >= len(seq):
                pet.x = hx
                pet.place()
                return done()
            pet.x = hx + seq[i]
            pet.place()
            self.after(max(14, int(30 * self.scale)), lambda: go(i + 1))
        go(0)

    def faint(self, pet, done):
        hy = pet.y

        def go(i):
            if self.closed:
                return
            if i > 10:
                pet.down = True
                try:
                    pet.win.withdraw()
                    if getattr(pet, "name_win", None):
                        pet.name_win.withdraw()
                except Exception:                           # noqa: BLE001
                    pass
                pet.y = hy
                return done()
            pet.y = hy + i * 4
            pet.place()
            self.after(28, lambda: go(i + 1))
        go(0)

    def _tick(self):
        """체력 막대가 짝의 도트 위를 따라다닌다 (싸우는 짝만)."""
        if self.closed or not self.layer:
            return
        self._n = getattr(self, "_n", 0) + 1
        if self._n % 15 == 1:
            try:
                self.layer.keep_alive()
            except Exception:                               # noqa: BLE001
                pass
        live = set()
        for lane in self.lanes.values():
            if lane.active:
                for p in (lane.me, lane.foe):
                    if p is not None and not getattr(p, "down", False):
                        live.add(id(p))
                        b = self.bar_for(p)
                        if b:
                            b.ease()
                            try:
                                b.draw(int(p.x) + p.fw // 2, int(p.y))
                            except Exception:               # noqa: BLE001
                                pass
        for k, b in self.bars.items():
            if k not in live:
                b.clear()
        self.bar_job = self.root.after(33, self._tick)

    # ---------------- 결과 · 정리 ----------------
    def _result(self):
        self.phase = "result"
        res = (self.result_ev or {}).get("result") or self.view.get("result")
        msg = WIN_TEXT if res == "win" else LOSE_TEXT
        here = [p for p in self.mine if p]
        standing = [p for p in here if not getattr(p, "down", False)]
        center = standing[len(standing) // 2] if standing else (here[0] if here else None)
        if center is not None and getattr(center, "down", False):
            PLAT.show_again(center.win)
        self.float_over(center, msg, "#7bffa0" if res == "win" else "#ff8a8a", ms(RESULT_MS))
        if res == "win":
            rw = self.view.get("reward") or {}
            if rw:
                self.after(ms(500), lambda: self.float_over(
                    center, "몬스터볼 +%d · %s원" % (rw.get("balls", 0), format(rw.get("money", 0), ",")),
                    "#ffd447", ms(RESULT_MS)))
        self.after(ms(RESULT_MS), self._leave)

    def _leave(self):
        """남은 공습 포켓몬은 가까운 화면 끝으로 걸어 나가고, 내 포켓몬은 제자리로."""
        self.phase = "leave"
        wl, wt, wr, wb = self.work
        for r in self.raiders:
            p = r.pet
            if p is None or getattr(p, "down", False):
                continue
            fx, fy = self.feet(p)
            edge = wl - p.fw if fx < (wl + wr) / 2.0 else wr + p.fw
            self.walk(p, edge, fy, ms(LEAVE_MS))
        for p in self.mine:
            if p is None or p in self.made:
                continue
            hx, hy = self.home.get(id(p), (p.x, p.y))
            if getattr(p, "down", False):
                continue
            self.walk(p, hx + p.fw / 2.0, hy + p.fh, ms(LEAVE_MS))
        self.after(ms(LEAVE_MS) + 120, self.cleanup)

    def cleanup(self):
        """원상 복귀. **몇 번을 불러도 안전하다** (끝 · 마감 · 예외 · 로그아웃 모두 여기로)."""
        if self.closed:
            return
        self.closed = True
        self.phase = "done"
        sp, self.stop_plate = self.stop_plate, None
        if sp is not None:
            try:
                sp.close()
            except Exception:                               # noqa: BLE001
                pass
        for lane in self.lanes.values():
            if lane.fx is not None:
                try:
                    lane.fx.stop()
                except Exception:                           # noqa: BLE001
                    pass
            lane.hiding.kind.clear()
            lane.hiding.held.clear()
            lane.active = lane.playing = False
        for job in (self.bar_job, self.watch_job):
            if job:
                try:
                    self.root.after_cancel(job)
                except Exception:                           # noqa: BLE001
                    pass
        self.bar_job = self.watch_job = None
        for j in self.jobs:
            try:
                self.root.after_cancel(j)
            except Exception:                               # noqa: BLE001
                pass
        self.jobs = []
        ov = self.app.overlay
        for r in self.raiders:
            if r.chute is not None:
                try:
                    r.chute.destroy()
                except Exception:                           # noqa: BLE001
                    pass
                r.chute = None
            if r.pet is not None:
                try:
                    if ov and r.pet in ov.extra:
                        ov.extra.remove(r.pet)
                    r.pet.destroy()
                except Exception:                           # noqa: BLE001
                    pass
                r.pet = None
        self.raiders = []
        for p in self.made:
            try:
                if ov and p in ov.extra:
                    ov.extra.remove(p)
                p.destroy()
            except Exception:                               # noqa: BLE001
                pass
        self.made = []
        for p in self.frozen:
            try:
                p.battling = False
                p.state = "idle"
                p.down = False
                hx, hy = self.home.get(id(p), (p.x, p.y))
                p.x, p.y = hx, hy
                if not getattr(ov, "hidden", False):
                    PLAT.show_again(p.win)
                p.place()
            except Exception:                               # noqa: BLE001
                pass
        self.frozen = []
        self.mine = []
        for b in self.bars.values():
            try:
                b.clear()
            except Exception:                               # noqa: BLE001
                pass
        self.bars = {}
        for t in self.texts:
            try:
                t.destroy()
            except Exception:                               # noqa: BLE001
                pass
        self.texts = []
        if self.layer:
            try:
                self.layer.destroy()
            except Exception:                               # noqa: BLE001
                pass
            self.layer = None
        ov2, self._names_ov = self._names_ov, None
        if ov2 is not None:
            try:
                ov2.release_names()
            except Exception as e:                          # noqa: BLE001
                config.log("공습 이름표를 되살리지 못했습니다: %s" % e)
        if ov:
            ov.locked = False
        if self.on_done:
            try:
                self.on_done()
            except Exception:                               # noqa: BLE001
                config.log("공습 끝 처리 실패: %s" % traceback.format_exc())


def result_text(view):
    """알림 한 줄: '공습을 막았다! (몬스터볼 +3 · 2,000원)'."""
    res = view.get("result")
    rw = view.get("reward") or {}
    head = "공습 — " + (WIN_TEXT if res == "win" else LOSE_TEXT)
    if res == "win" and rw:
        head += " (몬스터볼 +%d · %s원)" % (rw.get("balls", 0), format(rw.get("money", 0), ","))
    return natural(head)
