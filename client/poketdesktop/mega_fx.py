# -*- coding: utf-8 -*-
"""바탕화면의 메가진화 연출 (1.8.0).

두 군데서 쓴다.

## 1. 걸어다니는 모습을 메가 폼으로 (play)

도트를 오른쪽 클릭해 '메가진화한 모습으로' 를 고르면 그 자리에서 변한다.
진화 연출(evolve_fx.Evolution)을 그대로 물려받고 다음만 바꾼다.

  · 빛이 금빛 하나가 아니라 **무지갯빛**이다 (tint).
  · 깜빡이는 동안 여러 색 기운이 **몸으로 모여든다** (gather). 본가의
    메가진화가 그렇다 - 진화는 몸에서 빛이 나오고, 메가진화는 빛이 모인다.
  · 종이 바뀌는 게 아니다. num·이름은 그대로 두고 **lookNum 만** 바꾼다.
  · OS 알림을 안 띄운다. 눈앞에서 벌어진 일이라 따로 알릴 것이 없다.

되돌릴 때('원래 모습으로')는 뜸 들이지 않고 빛 한 번에 돌아온다 (revert).

## 2. 바탕화면 배틀 중의 메가진화 (battle)

야생 배틀·투기장에서 서버가 mega 사건을 보내면 그 도트 둘레에서 같은
빛을 터뜨리고, **그 판이 끝날 때까지** 메가 폼의 도트로 싸운다. 판이
끝나면 release 가 원래 입던 모습으로 되돌린다.

메가 폼의 도트가 없는 종(26폼)은 빛과 글씨만 나온다 - 그동안처럼.

도트는 연출 도중에 받는다. 기운이 모이는 동안(0.5초 남짓) 뒤에서 받고,
그때까지 못 받으면 조금 더 기다렸다가 도트는 그대로 둔 채 넘어간다.
배틀을 도트 하나 때문에 세워 둘 수는 없다.
"""
import math
import random

from . import config
from . import sprite_cache, walk_cache
from . import ui_common as U
from . import evolve_fx
from .fx_layer import FloatText

RAINBOW = ("#ff6b9d", "#ffb347", "#ffe66d", "#7bffa0", "#6fd3ff", "#b69cff")
TEXT_COLOR = "#c9b3ff"
TEXT = "메가진화!"
FAIL_TEXT = "메가 폼의 도트를 받지 못했다..."

BLINK_STEPS = 10         # 진화(16)보다 짧다 - 자주 켜고 끌 수 있는 것이라
BLINK_SLOW = 120
BLINK_FAST = 40
GATHER_STEPS = 16
GATHER_MS = 46

# 배틀 중
B_GATHER_STEPS = 12
B_GATHER_MS = 42
B_WAIT_MS = 900          # 기운이 다 모였는데 도트를 아직 못 받았을 때 더 기다리는 시간
B_AFTER_MS = 620         # 새 모습을 보여 주고 다음 사건으로


def rainbow(i=None):
    if i is None:
        return random.choice(RAINBOW)
    return RAINBOW[int(i) % len(RAINBOW)]


# ---------------------------------------------------------------- 1. 걸어다니는 모습
class MegaEvolution(evolve_fx.Evolution):
    """그 자리에서 메가 폼으로 (또는 원래 모습으로) 바뀐다."""

    @property
    def revert(self):
        return bool(self.info.get("revert"))

    def tint(self, i=None):
        return rainbow(i)

    # ---- 깜빡임 + 모여드는 기운 ----
    def blink(self, i):
        if not self.alive():
            return self.finish()
        if self.revert or self.anim_new is None:
            # 돌아올 때는 빛 한 번이면 된다. 도트를 못 받았을 때도 뜸 들이지 않는다.
            return self.reveal()
        if i == 0:
            self.gather()
        if i >= BLINK_STEPS or not self.sil_old:
            return self.morph(0)
        t = i / float(max(1, BLINK_STEPS - 1))
        gap = int(BLINK_SLOW + (BLINK_FAST - BLINK_SLOW) * t)
        if i % 2 == 0:
            self.show(self.sil_old[0])
        else:
            self.show_normal()
        if i % 3 == 0:
            self.spark()
        self.after(gap, lambda: self.blink(i + 1))

    def gather(self):
        """여러 색 기운이 둘레에서 돌며 몸으로 빨려 든다."""
        if not self.layer:
            return
        cv = self.layer.cv
        cx, cy = self.at(self.cx, self.cy)
        far = max(self.w0, self.h0) * 1.5 + 30
        orbs = []
        n = 12
        for k in range(n):
            r = 3 + (k % 3)
            it = cv.create_oval(0, 0, 0, 0, fill=rainbow(k), outline="")
            self.items.append(it)
            orbs.append((it, 2 * math.pi * k / n, r))

        def step(i):
            if not self.alive() or not self.layer:
                return
            if i >= GATHER_STEPS:
                for it, _a, _r in orbs:
                    self.kill(it)
                return
            t = i / float(GATHER_STEPS)
            dist = far * (1.0 - t) ** 1.4 + 6
            spin = t * math.pi * 2.2
            for it, a, r in orbs:
                x = cx + math.cos(a + spin) * dist
                y = cy + math.sin(a + spin) * dist * 0.8
                try:
                    cv.coords(it, x - r, y - r, x + r, y + r)
                except Exception:                           # noqa: BLE001
                    return
            self.after(GATHER_MS, lambda: step(i + 1))
        step(0)

    # ---- 겉모습만 바뀐다 ----
    def update_mon(self):
        mon = self.pet.mon
        if self.revert:
            mon.pop("lookNum", None)
        elif self.info.get("toNum"):
            mon["lookNum"] = self.info["toNum"]

    def congrats(self):
        changed = self.anim_new is not None
        if changed and not self.revert:
            try:
                self.pet.play("Hop", once=True)
            except Exception:                               # noqa: BLE001
                pass
            if self.layer and self.alive():
                try:
                    self.texts.append(
                        FloatText(self.layer, self.cx, self.pet.y - 10, TEXT,
                                  TEXT_COLOR, ms=evolve_fx.TEXT_MS))
                except Exception:                           # noqa: BLE001
                    pass
        elif not changed and not self.revert:
            # 도트를 못 받았다. 아무 일도 안 일어난 것처럼 보이면 안 되니 한 줄 띄운다.
            try:
                if not self.layer:
                    self.open_layer()
                if self.layer:
                    self.texts.append(
                        FloatText(self.layer, self.cx, self.pet.y - 10, FAIL_TEXT,
                                  "#b0b0c0", ms=evolve_fx.TEXT_MS))
            except Exception:                               # noqa: BLE001
                pass
        self.notify_done()
        self.after(260 if (changed and self.revert) else evolve_fx.TEXT_MS,
                   self.finish)


def play(app, pet, num, revert=False, on_done=None):
    """바탕화면의 그 도트를 num 의 모습으로 바꾼다 (연출과 함께).

    num 은 메가 폼의 번호, revert 면 원래 번호다. 끝나면 on_done() -
    pet.look == num 인지로 정말 바뀌었는지 알 수 있다 (도트를 못 받았으면
    안 바뀐다).
    """
    if pet is None or not num or getattr(pet, "evolving", False):
        if on_done:
            on_done()
        return None
    pet.evolving = True
    fx = MegaEvolution(app, pet, {"toNum": num, "revert": bool(revert)}, on_done)
    try:
        fx.start()
    except Exception as e:                                  # noqa: BLE001
        config.log("메가진화 연출 실패: %s" % e)
        fx.finish()
    return fx


# ---------------------------------------------------------------- 2. 배틀 중
def battle(host, pet, num, done):
    """바탕화면 배틀에서 pet 이 메가진화한다. 끝나면 done().

    host 는 그 판 (desktop_battle.DesktopBattle / arena.Arena) - layer, after,
    float_over, closed, app 을 가진다. num 은 메가 폼의 번호.
    """
    app = host.app
    ov = getattr(app, "overlay", None)
    layer = getattr(host, "layer", None)
    state = {"gathered": False, "loaded": False, "fired": False}
    shiny = bool((pet.mon or {}).get("shiny"))
    need = bool(num) and ov is not None and getattr(pet, "look", None) != num

    def closed():
        return bool(getattr(host, "closed", False))

    # ---- 도트는 뒤에서 받는다 ----
    def work():
        path = sprite_cache.ensure(app.api, num, shiny)
        sheet, meta = walk_cache.ensure(app.api, num, shiny=shiny)
        return path, (sheet, meta) if sheet and meta else None

    def got(r, err):
        if r and not err and ov is not None:
            path, walk = r
            if path:
                ov.paths[(num, shiny)] = path
            if walk:
                ov.walks[walk_cache.key(num, shiny)] = walk
        state["loaded"] = True
        fire()

    # ---- 빛이 터지며 모습이 바뀐다 ----
    def fire(force=False):
        if state["fired"] or closed():
            return
        if not state["gathered"] or not (state["loaded"] or force):
            return
        state["fired"] = True
        if need and state["loaded"]:
            try:
                if ov.reskin(pet, num):
                    pet.look_hold = True        # 판이 끝날 때까지 이 모습으로
            except Exception as e:                          # noqa: BLE001
                config.log("배틀 메가 폼 도트 실패: %s" % e)
        _burst(host, pet)
        try:
            host.float_over(pet, TEXT, TEXT_COLOR)
        except Exception:                                   # noqa: BLE001
            pass
        host.after(B_AFTER_MS, done)

    def gathered():
        state["gathered"] = True
        fire()
        if not state["fired"]:
            host.after(B_WAIT_MS, lambda: fire(force=True))

    if need:
        try:
            U.run_async(app.root, work, got)
        except Exception:                                   # noqa: BLE001
            state["loaded"] = True
    else:
        state["loaded"] = True

    if not layer:
        return gathered()
    _gather(host, pet, gathered)


def _center(pet):
    return pet.x + pet.fw / 2.0, pet.y + pet.fh / 2.0


def _gather(host, pet, then):
    layer = host.layer
    cv = layer.cv
    sx, sy = _center(pet)
    cx, cy = layer.to_local(sx, sy)
    far = max(pet.fw, pet.fh) * 1.5 + 30
    orbs = []
    n = 10
    try:
        for k in range(n):
            it = cv.create_oval(0, 0, 0, 0, fill=rainbow(k), outline="")
            orbs.append((it, 2 * math.pi * k / n, 3 + (k % 3)))
    except Exception:                                       # noqa: BLE001
        return then()

    def clear():
        for it, _a, _r in orbs:
            try:
                cv.delete(it)
            except Exception:                               # noqa: BLE001
                pass

    def step(i):
        if getattr(host, "closed", False) or not host.layer:
            return clear()
        if i >= B_GATHER_STEPS:
            clear()
            return then()
        t = i / float(B_GATHER_STEPS)
        dist = far * (1.0 - t) ** 1.4 + 6
        spin = t * math.pi * 2.0
        try:
            for it, a, r in orbs:
                x = cx + math.cos(a + spin) * dist
                y = cy + math.sin(a + spin) * dist * 0.8
                cv.coords(it, x - r, y - r, x + r, y + r)
        except Exception:                                   # noqa: BLE001
            clear()
            return then()
        host.after(B_GATHER_MS, lambda: step(i + 1))
    step(0)


def _burst(host, pet):
    """무지갯빛 고리와 알갱이가 퍼진다. 스스로 치운다."""
    layer = getattr(host, "layer", None)
    if not layer:
        return
    cv = layer.cv
    sx, sy = _center(pet)
    cx, cy = layer.to_local(sx, sy)
    size = max(pet.fw, pet.fh)

    def kill(it):
        try:
            cv.delete(it)
        except Exception:                                   # noqa: BLE001
            pass

    bits = []
    try:
        for k in range(14):
            a = random.uniform(0, 2 * math.pi)
            sp = random.uniform(4.0, 9.0)
            r = random.uniform(2, 4)
            it = cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=rainbow(k), outline="")
            bits.append((it, math.cos(a) * sp, math.sin(a) * sp * 0.8))
    except Exception:                                       # noqa: BLE001
        pass

    def step(i):
        if getattr(host, "closed", False) or not host.layer or i >= 9:
            for it, _vx, _vy in bits:
                kill(it)
            return
        try:
            # 처음 몇 박자는 흰 빛이 몸을 덮었다 걷힌다 (도트가 바뀌는 순간을 가린다)
            if i < 4:
                r = size * (0.85 - i * 0.2) + 6
                glow = cv.create_oval(cx - r, cy - r * 1.05, cx + r, cy + r * 1.05,
                                      fill="#ffffff", outline="")
                host.after(44, lambda it=glow: kill(it))
            rr = 14 + i * 15
            ring = cv.create_oval(cx - rr, cy - rr * 0.92, cx + rr, cy + rr * 0.92,
                                  outline=rainbow(i), width=max(1, 6 - i // 2))
            host.after(160, lambda it=ring: kill(it))
            for it, vx, vy in bits:
                cv.move(it, vx, vy + i * 0.35)
        except Exception:                                   # noqa: BLE001
            for it, _vx, _vy in bits:
                kill(it)
            return
        host.after(40, lambda: step(i + 1))
    step(0)


def release(ov, pets):
    """배틀이 끝났다. 잠깐 메가 폼이 됐던 도트를 원래 입던 모습으로 되돌린다."""
    from .overlay import look_num
    for pet in pets or []:
        if pet is None or not getattr(pet, "look_hold", False):
            continue
        pet.look_hold = False
        try:
            if ov is not None and pet.look != look_num(pet.mon):
                ov.reskin(pet)
        except Exception as e:                              # noqa: BLE001
            config.log("메가 폼을 되돌리지 못했습니다: %s" % e)
