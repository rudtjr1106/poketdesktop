# -*- coding: utf-8 -*-
"""기술 연출 검사.

    .venv/bin/python client/test_move_fx.py

**창을 띄우지 않는다.** 캔버스와 시계를 흉내 낸 것(tools/fx_preview 의 FakeCanvas /
FakeRoot)에 연출을 그대로 돌려서 센다. 눈으로 보려면 tools/fx_gallery.py (창) · tools/fx_preview.py (그림).

못 박는 것.

  1. 연출 고르기 - 파괴광선은 광선, 지진은 갈라진 땅, 사이코키네시스는 염력 ... 그리고 이름표(EXACT)에 적은
     영문 이름이 도감에 실제로 있다. 고른 연출은 전부 구현돼 있다. 변화기는 무기 모양(광선 · 칼 · 발톱)을 안 쓴다.
     타입 18 x (접촉 · 원거리 · 특수 · 변화) 가 저마다 연출을 갖는다.
  2. 도감의 기술 전부(900여 종), 양쪽 방향으로: 예외 없이 **끝까지 가고**(2초 안), 끝나면 캔버스에
     **찌꺼기가 없고**, 끝났다는 신호(on_done)는 **한 번만** 오고, 연출이 밀어 둔 **도트는 제자리로** 돌아온다.
     한때 떠 있는 도형 수도 넘치지 않는다 (바탕화면 레이어가 느려진다).
  2-1. 급소 · 효과 · 컷인 · 빗나감: 가장 무겁게 돌려도 같다. 빗나간 기술은 맞는 쪽 도트를 안 민다.
  2-2. **느린 PC**: 한 장이 0.2초씩 걸려도 연출은 길어지지 않는다 (실제 시각으로 굴린다 - 장을 건너뛴다).
  3. 중간에 멈춰도(stop) 찌꺼기가 없고 on_done 은 안 오고 도트는 제자리다 - 배틀 창을 닫을 때다.
  4. 관장 배틀 창의 2배 캔버스(_ScaledCanvas)에서도 그대로 돈다. itemconfigure 로
     굵기·글꼴을 바꾸지 않는다 (그 창에서만 크기가 어긋난다).
  5. 진짜 Tk 캔버스가 우리가 쓰는 옵션을 전부 받는다 (숨긴 창, 화면에는 안 뜬다).
"""
import json
import os
import random
import sys
import tempfile

os.environ.setdefault("POKET_HOME", os.path.join(tempfile.gettempdir(), "poket-test-movefx"))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fx_preview as PV                                       # noqa: E402
from poketdesktop import battle_fx as FX                      # noqa: E402
from poketdesktop import move_fx as MF                        # noqa: E402

FX.DEBUG = True                 # 연출 중의 예외를 삼키지 않는다
OK = FAIL = 0
LIMIT_MS = 2000                 # 관장 배틀 창은 2600ms 에 다음으로 넘어간다
PEAK_MAX = 120                  # 한때 떠 있는 도형 수
TK_WAIT = int(os.environ.get("POKET_TK_WAIT") or 90)      # 진짜 Tk 확인을 기다리는 초


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


class StrictCanvas(PV.FakeCanvas):
    """itemconfigure 로 굵기·글꼴을 바꾸면 적어 둔다 (2배 캔버스에서 어긋난다)."""

    def __init__(self, *a, **kw):
        PV.FakeCanvas.__init__(self, *a, **kw)
        self.bad = []

    def itemconfigure(self, item, **kw):
        if "width" in kw or "font" in kw:
            self.bad.append(sorted(kw))
        PV.FakeCanvas.itemconfigure(self, item, **kw)

    itemconfig = itemconfigure


def run(move, flip=False, flat=False, cv=None, wrap=None, stop_at=None, more_ms=0, ev=None, step=None):
    """연출 하나를 돌린다. (stage, fx, 끝난 횟수, 걸린 ms) 를 돌려준다. step: 한 장에 걸리는 ms (느린 PC)."""
    me, foe = (PV.FLAT_ME, PV.FLAT_FOE) if flat else (PV.ME, PV.FOE)
    stage = PV.FakeStage(cv=cv or StrictCanvas(), me=me, foe=foe)
    raw = stage.cv
    if wrap:
        stage.cv = wrap(raw)
    src, dst = (foe, me) if flip else (me, foe)
    k = getattr(stage.cv, "k", 1.0)
    done = []
    fx = FX.Effect(stage, move, (src[0] / k, src[1] / k), (dst[0] / k, dst[1] / k),
                   lambda: done.append(stage.root.now), who="foe" if flip else "me", ev=ev)
    fx.play()
    stage.stopped = False
    while stage.root.now < LIMIT_MS + 600 and not done:
        if stop_at is not None and stage.root.now >= stop_at:
            fx.stop()
            stage.stopped = True
            break
        stage.root.advance(step or PV.FRAME_MS)
    if more_ms:
        stage.root.advance(more_ms)
    stage.raw = raw
    return stage, fx, len(done), (done[0] if done else None)


def main():
    moves_all = json.load(open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8"))["moves"]
    by_key, moves = {}, []
    for m in moves_all.values():                 # 같은 기술이 두 이름으로 실린 것은 한 번만
        if m.get("kr") not in by_key:
            by_key[m.get("kr")] = m
            moves.append(m)
    kr = by_key.get

    print("=== 1. 연출 고르기 ===")
    en = set(MF.key_of(m) for m in moves_all.values())
    missing = sorted(k for k in MF.EXACT if k not in en)
    chk("이름표에 적은 기술이 도감에 다 있다", not missing, missing)
    styles = {}
    for m in moves:
        styles.setdefault(FX.style_of(m), m)
    unimpl = sorted(s for s in styles if s not in MF.STYLES and not hasattr(FX.Effect, "_" + s))
    chk("고른 연출이 전부 구현돼 있다 (%d가지)" % len(styles), not unimpl, unimpl)
    unused = sorted(s for s in MF.STYLES if s not in styles and s not in ("selfdown",))
    chk("안 쓰이는 연출이 없다", not unused, unused)
    want = {"파괴광선": "laser", "솔라빔": "laser", "냉동빔": "laser", "지진": "quake", "번개": "thunder",
            "10만볼트": "thunder", "방전": "zap", "불대문자": "daimonji", "화염방사": "flame", "불꽃세례": "ember",
            "눈보라": "blizzard", "사이코키네시스": "psy", "섀도볼": "ball", "용성군": "meteor", "문포스": "moon",
            "하이드로펌프": "jet", "파도타기": "surf", "거품광선": "bubble", "스톤에지": "pillars",
            "스톤샤워": "rockfall", "사우전드애로": "arrows", "골드러시": "coins", "용의파동": "pulse",
            "매지컬리프": "leafstorm", "리프스톰": "leafstorm", "덩굴채찍": "whip", "폭풍": "tornado",
            "대지의힘": "erupt", "파워젬": "gem", "요정의바람": "sparkle", "오물폭탄": "sludge", "독침": "needles",
            "거대해머": "hammer", "대폭발": "boom",
            "치근거리기": "hit", "몸통박치기": "hit", "아이언헤드": "hit", "인파이트": "flurry", "역린": "flurry",
            "전광석화": "dash", "불릿펀치": "dash", "고스트다이브": "phantom", "에어슬래시": "blades",
            "깜짝베기": "slash", "드래곤클로": "claw", "깨물어부수기": "bite", "물수리검": "multi",
            "플레어드라이브": "recoil", "냉동펀치": "punch", "블레이즈킥": "kick", "독찌르기": "stab",
            "드레인키스": "drain",
            # 변화기
            "방어": "shield", "리플렉터": "wall", "칼춤": "dance", "울음소리": "sound", "수면가루": "powder",
            "HP회복": "heal", "날개쉬기": "roost", "도깨비불": "wisp", "전기자석파": "hex", "맹독": "hex",
            "이상한빛": "hex", "스텔스록": "hazard", "쾌청": "weather", "비바라기": "weather", "잠자기": "sleepz",
            "고속이동": "buff", "손톱갈기": "buff"}
    wrong = dict((n, FX.style_of(kr(n))) for n, s in want.items() if kr(n) and FX.style_of(kr(n)) != s)
    chk("기술마다 제 연출 (%d개)" % len(want), not wrong and all(kr(n) for n in want),
        wrong or [n for n in want if not kr(n)])
    # 변화기는 때리지 않는다 - 무기 모양(광선 · 칼 · 발톱 · 지진 ...)은 공격기만 쓴다 (이상한빛이 파괴광선처럼 나갔다)
    from poketdesktop import fx_melee as ME
    weapon = set(ME.STYLES) | {"laser", "quake", "boom", "thunder", "meteor", "pillars", "erupt", "daimonji",
                               "needles", "icicles", "rockfall", "arrows", "nova", "shot", "stream"}
    leak = sorted((m["kr"], FX.style_of(m)) for m in moves
                  if (m.get("cat") or "status") == "status" and FX.style_of(m) in weapon)
    chk("변화기는 무기 모양을 안 쓴다", not leak, leak[:8])
    # 타입 18 x (접촉 · 원거리 · 특수 · 변화): 저마다 연출이 있고, 접촉은 타입마다 한 수가 다르다
    cells = {}
    for typ in FX.TYPE_FX:
        cells[typ] = (FX.style_of({"type": typ, "cat": "physical", "flags": ["contact"]}),
                      FX.style_of({"type": typ, "cat": "physical", "flags": ["protect"], "en": "x"}),
                      FX.style_of({"type": typ, "cat": "special", "flags": ["protect"], "en": "x"}),
                      FX.style_of({"type": typ, "cat": "status", "flags": []}))
    bad = dict((t, c) for t, c in cells.items() if c[0] != "hit" or c[1] != "shot" or c[2] != MF.STREAM.get(t)
               or c[3] != "hex" or any(x not in MF.STYLES for x in c))
    chk("타입 18 x 분류 4 가 다 연출을 갖는다", len(cells) == 18 and not bad, bad)
    chk("  접촉기의 한 수는 타입마다 따로 (%d가지)" % len(set(ME.FLOURISH.values())),
        set(ME.FLOURISH) == set(FX.TYPE_FX) and len(set(ME.FLOURISH.values())) == 18)
    chk("  특수기의 줄기도 타입마다 (%d가지 모양)" % len(set(MF.STREAM.values())),
        set(MF.STREAM) == set(FX.TYPE_FX) and len(set(MF.STREAM.values())) >= 14, sorted(set(MF.STREAM.values())))
    from poketdesktop import fx_kit as K
    chk("  타입마다 색 다섯 단 · 조각 · 맞은 자리의 모습", set(K.PAL) == set(FX.TYPE_FX) and set(K.MOTE) == set(FX.TYPE_FX)
        and all(len(v) == 6 for v in K.PAL.values()) and not any("#fe01fe" in v for v in K.PAL.values()))
    big = FX.Effect(PV.FakeStage(), kr("파괴광선"), PV.ME, PV.FOE, None).big
    small = FX.Effect(PV.FakeStage(), kr("불꽃세례"), PV.ME, PV.FOE, None).big
    plain = FX.Effect(PV.FakeStage(), kr("칼춤"), PV.ME, PV.FOE, None).big
    chk("센 기술은 크게, 약한 기술은 작게, 변화기는 그대로", big > 1.2 and small < 1.0 and plain == 1.0,
        (big, small, plain))

    print("\n=== 2. 전부 돌려 본다 (%d종 x 양쪽) ===" % len(moves))
    random.seed(20261006)
    errs, slow, left, twice, peaks, bad_cfg, astray = [], [], [], [], [], [], []
    longest = (0, "")
    for m in moves:
        for flip in (False, True):
            try:
                st, fx, n, took = run(m, flip=flip, more_ms=400)
            except Exception as e:                           # noqa: BLE001
                errs.append((m["kr"], flip, "%s: %s" % (type(e).__name__, e)))
                continue
            if n == 0 or took > LIMIT_MS:
                slow.append((m["kr"], fx.style, took))
            elif took > longest[0]:
                longest = (took, "%s(%s)" % (m["kr"], fx.style))
            if n > 1:
                twice.append((m["kr"], fx.style, n))
            if st.raw.items:
                left.append((m["kr"], fx.style, len(st.raw.items)))
            if st.raw.peak > PEAK_MAX:
                peaks.append((m["kr"], fx.style, st.raw.peak))
            if st.raw.bad:
                bad_cfg.append((m["kr"], fx.style, st.raw.bad[0]))
            if any(abs(v) > 1e-6 for xy in st.shift.values() for v in xy):
                astray.append((m["kr"], fx.style, st.shift))
    chk("예외가 없다", not errs, errs[:5])
    chk("연출이 밀어 둔 도트는 제자리로 돌아온다", not astray, astray[:5])
    chk("모두 %dms 안에 끝난다 (가장 긴 것 %dms %s)" % (LIMIT_MS, longest[0], longest[1]), not slow, slow[:5])
    chk("끝났다는 신호는 한 번만", not twice, twice[:5])
    chk("끝나면 캔버스에 찌꺼기가 없다", not left, left[:5])
    chk("한때 떠 있는 도형이 %d개를 안 넘는다" % PEAK_MAX, not peaks, sorted(peaks, key=lambda x: -x[2])[:5])
    chk("itemconfigure 로 굵기·글꼴을 바꾸지 않는다", not bad_cfg, bad_cfg[:5])
    flat = []
    for s, m in sorted(styles.items()):
        for flip in (False, True):
            try:
                st, fx, n, took = run(m, flip=flip, flat=True, more_ms=400)
                if n != 1 or st.raw.items:
                    flat.append((s, flip, n, len(st.raw.items)))
            except Exception as e:                           # noqa: BLE001
                flat.append((s, flip, "%s: %s" % (type(e).__name__, e)))
    chk("나란히 선 배치(바탕화면 배틀)에서도 끝까지 간다", not flat, flat[:5])
    # 도감에 없는 기술(몸부림, 옛 기록의 기술)은 화면들이 타입과 분류만 넘긴다
    bare = []
    for typ in list(FX.TYPE_FX) + ["???"]:
        for cat, flags in (("physical", []), ("physical", ["contact"]), ("physical", ["protect"]), ("special", []),
                           ("status", [])):
            try:
                st, fx, n, took = run({"type": typ, "cat": cat, "flags": flags}, flat=True, more_ms=400)
                if n != 1 or st.raw.items:
                    bare.append((typ, cat, fx.style, n, len(st.raw.items)))
            except Exception as e:                           # noqa: BLE001
                bare.append((typ, cat, "%s: %s" % (type(e).__name__, e)))
    chk("타입과 분류만 아는 기술도 끝까지 간다", not bare, bare[:5])
    st, fx, n, took = run(kr("치근거리기"))
    chk("접촉기는 달려든다 (한 번)", st.lunges == 1, st.lunges)
    st, fx, n, took = run(kr("문포스"))
    chk("닿지 않는 기술은 안 달려든다", st.lunges == 0, st.lunges)
    st, fx, n, took = run(kr("파괴광선"), ev={"t": "move", "_hit": {"crit": False, "eff": 1.0}})
    chk("맞으면 맞는 쪽 도트가 밀린다 · 쏘는 쪽은 반동으로 밀린다",
        st.pushed.get("foe", 0) > 4 and st.pushed.get("me", 0) > 2, st.pushed)
    st, fx, n, took = run(kr("칼춤"))
    chk("변화기는 도트를 밀지 않는다", not st.pushed, st.pushed)

    # 더블배틀 · 레이드는 자리 열쇠로 부른다: keys=(쓰는 자리, 맞는 자리). 그 자리의 도트만 밀고, 끝나면 제자리다.
    class Slots(PV.FakeStage):
        def __init__(self):
            PV.FakeStage.__init__(self)
            self.shift = dict((k_, [0.0, 0.0]) for k_ in ("a0", "a1", "b0", "b1"))

        def fx_box(self, key):
            return None
    slot_bad = []
    for name in ("파괴광선", "지진", "사이코키네시스", "인파이트", "깨물어부수기", "대폭발", "칼춤", "울음소리"):
        stg, got = Slots(), []
        fx = FX.Effect(stg, kr(name), PV.ME, PV.FOE, lambda: got.append(1), who="me",
                       ev={"t": "move", "_hit": {"crit": True, "eff": 2.0}}, keys=("a1", "b0"))
        fx.play()
        while stg.root.now < LIMIT_MS + 600 and not got:
            stg.root.advance(PV.FRAME_MS)
        stg.root.advance(400)
        status = (kr(name).get("cat") or "status") == "status"
        if (got != [1] or stg.cv.items or any(abs(v) > 1e-6 for xy in stg.shift.values() for v in xy)
                or not set(stg.pushed) <= {"a1", "b0"} or (not status and not stg.pushed.get("b0"))):
            slot_bad.append((name, got, len(stg.cv.items), stg.pushed))
    chk("자리 열쇠(keys=)로 불러도 그 자리의 도트만 밀고 제자리로 돌린다 (더블배틀 · 레이드)", not slot_bad, slot_bad[:4])

    print("\n=== 2-1. 맞는 순간의 세기 · 컷인 · 빗나감 ===")
    evs = [{"t": "move", "move": "10만볼트"}, {"t": "hit", "eff": 2.0, "crit": False},
           {"t": "move", "move": "물대포"}, {"t": "hit", "eff": 0.5}, {"t": "hit", "eff": 1.0, "crit": True},
           {"t": "move", "move": "칼춤"}, {"t": "msg"}]
    FX.annotate(evs)
    chk("annotate: 기술마다 다음 '맞음' 의 효과 · 급소 (여러 번이면 가장 센 것 · 한 번이라도 급소)",
        evs[0]["_hit"] == {"crit": False, "eff": 2.0} and evs[2]["_hit"] == {"crit": True, "eff": 1.0}
        and "_hit" not in evs[5], [e.get("_hit") for e in evs])
    evs2 = [{"t": "move", "move": "파괴광선"}, {"t": "miss"}, {"t": "move", "move": "지진"}, {"t": "immune"},
            {"t": "move", "move": "번개"}, {"t": "hit", "eff": 1.0}, {"t": "immune"}]
    FX.annotate(evs2)
    chk("annotate: 빗나감 · 효과 없음도 달아 둔다 (맞은 뒤의 것은 아니다)",
        evs2[0].get("_miss") and evs2[2].get("_immune") and not evs2[4].get("_immune") and "_hit" not in evs2[0],
        [dict((k, v) for k, v in e.items() if k.startswith("_")) for e in evs2])
    miss_bad = []
    for name in ("파괴광선", "지진", "번개", "사이코키네시스", "인파이트", "깨물어부수기", "폭풍", "섀도볼"):
        for ev in (evs2[0], evs2[2]):
            st, fx, n, took = run(kr(name), ev=dict(ev), more_ms=400)
            if n != 1 or st.raw.items or st.pushed.get("foe"):
                miss_bad.append((name, n, len(st.raw.items), st.pushed))
    chk("빗나가거나 효과가 없으면 맞는 쪽 도트를 안 민다 (끝까지는 간다)", not miss_bad, miss_bad[:4])
    fx = FX.Effect(PV.FakeStage(), kr("파괴광선"), PV.ME, PV.FOE, None, ev=evs2[0])
    chk("  빗나간 연출은 과녁을 비켜 떨어진다", fx.miss and fx.dst != PV.FOE and abs(fx.dst[1] - PV.FOE[1]) > 20, fx.dst)
    fx = FX.Effect(PV.FakeStage(), kr("10만볼트"), PV.ME, PV.FOE, None, ev=evs[0])
    chk("  연출이 그걸 받는다", fx.eff == 2.0 and not fx.crit and not fx.zmove, (fx.eff, fx.crit, fx.zmove))
    plain = FX.Effect(PV.FakeStage(), kr("10만볼트"), PV.ME, PV.FOE, None)
    chk("  모르면 보통 (효과 1 · 급소 아님)", plain.eff == 1.0 and not plain.crit)
    cut = lambda name, **kw: MF.wants_cutin(FX.Effect(PV.FakeStage(), kr(name), PV.ME, PV.FOE, None, **kw))  # noqa: E731
    chk("컷인: 위력 %d 이상 공격기 (파괴광선 · 오버히트)" % MF.CUTIN_POWER, cut("파괴광선") and cut("오버히트"))
    chk("  인파이트(120) · 10만볼트(90) · 변화기는 안 띄운다", not cut("인파이트") and not cut("10만볼트") and not cut("칼춤"))
    chk("  Z기술은 늘", cut("전광석화", ev={"t": "move", "move": "울트라대시어택", "z": True}))
    seen = set()
    PV.play(kr("파괴광선"), flat=True,
            on_frame=lambda stg: seen.update(o[2].get("text") for o in stg.cv.items.values() if o[0] == "text"))
    chk("  컷인 띠에 기술 이름이 뜬다", "파괴광선" in seen, seen)
    st, fx, n, took = run(kr("파괴광선"), flat=True, more_ms=400)
    chk("  컷인이 있어도 끝까지 가고 찌꺼기가 없다", n == 1 and not st.raw.items, (n, len(st.raw.items)))
    heavy, slow2 = [], []
    for m in moves:
        hint = {"t": "move", "move": m.get("kr"), "z": True, "_hit": {"crit": True, "eff": 2.0}}
        try:
            st, fx, n, took = run(m, ev=hint, more_ms=400)
        except Exception as e:                               # noqa: BLE001
            heavy.append((m["kr"], "%s: %s" % (type(e).__name__, e)))
            continue
        if n != 1 or st.raw.items or st.raw.peak > PEAK_MAX:
            heavy.append((m["kr"], fx.style, n, len(st.raw.items), st.raw.peak))
        if took > LIMIT_MS:
            slow2.append((m["kr"], fx.style, took))
    chk("가장 무겁게 (효과가 굉장하다 + 급소 + 컷인) 돌려도 끝까지 · 찌꺼기 없이 · 도형 %d개 안" % PEAK_MAX,
        not heavy, heavy[:5])
    chk("  %dms 안에 끝난다" % LIMIT_MS, not slow2, slow2[:5])

    print("\n=== 2-2. 느린 PC (한 장에 0.2초) ===")
    # 장 수를 세어 굴리면 느린 PC 에서는 연출이 몇 배로 길어져, 배틀 창이 2.4초에 다음으로 넘긴 뒤에도 돌고 있다.
    # 실제 시각으로 굴리므로 장을 건너뛸 뿐 길이는 같다.
    lag = []
    for s_, m in sorted(styles.items()):
        st0, fx0, n0, took0 = run(m, more_ms=400)
        st, fx, n, took = run(m, step=200, more_ms=600)
        if n != 1 or st.raw.items or took > took0 + 420 or any(abs(v) > 1e-6 for xy in st.shift.values() for v in xy):
            lag.append((s_, n, took0, took, len(st.raw.items)))
    chk("느려도 길어지지 않고 (두 장 안쪽) 끝까지 · 찌꺼기 없이 · 도트 제자리", not lag, lag[:5])

    print("\n=== 3. 중간에 멈춘다 ===")
    bad, cut = [], 0
    for s, m in sorted(styles.items()):
        for at in (60, 240, 520):
            st, fx, n, took = run(m, stop_at=at, more_ms=1500)
            if not st.stopped:                          # 그 전에 끝난 짧은 연출
                continue
            cut += 1
            if n or st.raw.items or not fx.dead or any(abs(v) > 1e-6 for xy in st.shift.values() for v in xy):
                bad.append((s, at, n, len(st.raw.items), st.shift))
    chk("멈추면 찌꺼기가 없고 끝났다는 신호도 안 오고 도트는 제자리다 (%d번)" % cut,
        not bad and cut > len(styles) * 2, bad[:5])
    # 물기: 다 닫힌 순간(마무리 충격 바로 앞)에 연출이 쥔 다각형은 이빨 일곱 개뿐이다 (test_gym_ui 가 진짜 창에서 찍는다)
    shot = {}
    orig = FX.Effect.burst

    def spy(self):
        if self.style == "bite" and "n" not in shot:
            polys = [self.cv.items[i] for i in self.items if self.cv.items[i][0] == "polygon"]
            shot["n"] = len(polys)
            shot["tri"] = all(len(p_[1]) == 6 for p_ in polys)
            shot["x"] = sum(v for p_ in polys for v in p_[1][0::2]) / max(1, 3 * len(polys))
            shot["pushed"] = dict(getattr(self.st, "pushed", {}))
        return orig(self)
    FX.Effect.burst = spy
    try:
        run(kr("깨물어부수기"))
    finally:
        FX.Effect.burst = orig
    chk("물기: 다 닫힌 순간 이빨(세모) 일곱 개가 과녁 가운데에", shot.get("n") == 7 and shot.get("tri")
        and abs(shot.get("x", 0) - PV.FOE[0]) < 3, shot)
    # (물린 동안 도트를 밀면 이빨이 도트 가운데에서 어긋난다 - 관장 배틀 창 검사가 진짜 캔버스에서 그걸 잰다)
    chk("  물린 채 머무는 동안에는 맞는 쪽 도트를 안 민다", not shot.get("pushed", {}).get("foe"), shot.get("pushed"))

    print("\n=== 4. 관장 배틀 창의 2배 캔버스 ===")
    from poketdesktop import ui_gym_battle as GB
    bad = []
    for s, m in sorted(styles.items()):
        try:
            st, fx, n, took = run(m, wrap=lambda c: GB._ScaledCanvas(c, GB.FX_SCALE), more_ms=400)
        except Exception as e:                               # noqa: BLE001
            bad.append((s, "%s: %s" % (type(e).__name__, e)))
            continue
        if n != 1 or st.raw.items or st.raw.bad:
            bad.append((s, n, len(st.raw.items), st.raw.bad[:1]))
    chk("2배 캔버스에서도 끝까지 가고 찌꺼기가 없다", not bad, bad[:5])
    # 좌표가 정말 2배로 그려지는지: 문포스의 마지막 타격은 과녁(무대 좌표) 둘레에 그려진다
    seen = []

    class Spy(StrictCanvas):
        def _make(self, kind, args, kw):
            i = StrictCanvas._make(self, kind, args, kw)
            pts = self.items[i][1]
            seen.append((sum(pts[0::2]) / (len(pts) / 2), sum(pts[1::2]) / (len(pts) / 2)))
            return i
    run(kr("문포스"), cv=Spy(), wrap=lambda c: GB._ScaledCanvas(c, GB.FX_SCALE))
    # (맞는 순간의 도형 - 마지막 200개쯤 - 은 과녁 둘레에 있고, 2배로 밀려난 자리(과녁 좌표 x 2)에는 없다)
    last = seen[-200:]
    near = [p for p in last if abs(p[0] - PV.FOE[0]) < 80 and abs(p[1] - PV.FOE[1]) < 80]
    off = [p for p in last if abs(p[0] - PV.FOE[0] * 2) < 80 and abs(p[1] - PV.FOE[1] * 2) < 80]
    chk("그리는 자리는 제자리 (과녁 둘레)", len(near) >= 60 and not off, (len(near), len(off), seen[-3:]))

    print("\n=== 5. 진짜 Tk 캔버스 ===")
    # 따로 띄워서 시간 제한을 둔다. 화면이 꺼진 맥에서는 Tk() 가 돌아오지 않는 일이 있어서,
    # 같은 프로세스에서 열면 검사 전체가 멈춘다.
    import subprocess
    try:
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "--tk"], capture_output=True,
                           text=True, timeout=TK_WAIT, encoding="utf-8", errors="replace")
        out = (r.stdout or "").strip().splitlines()
        tail = out[-1] if out else (r.stderr or "").strip()[-300:]
        if tail.startswith("SKIP"):
            print("  (건너뜀: %s)" % tail[5:])
        else:
            chk("Tk 가 옵션을 다 받고 찌꺼기가 없다 (1배·2배)", r.returncode == 0 and tail.startswith("TKOK"), tail)
    except subprocess.TimeoutExpired:
        if os.environ.get("CI"):
            chk("Tk 가 %d초 안에 응답한다" % TK_WAIT, False, "응답 없음")
        else:
            print("  (건너뜀: Tk 가 %d초 동안 응답하지 않는다 - 화면이 꺼져 있으면 그렇다)" % TK_WAIT)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


def tk_part():
    """진짜 Tk 캔버스(숨긴 창)에 연출마다 한 번씩. 마지막 줄에 TKOK / SKIP / 틀린 것을 적는다."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()                                     # 화면에는 안 뜬다
        real = tk.Canvas(root, width=PV.STAGE_W, height=PV.STAGE_H)
    except Exception as e:                                   # noqa: BLE001
        print("SKIP Tk 를 못 연다 - %s" % e)
        return 0
    from poketdesktop import ui_gym_battle as GB

    class RealCanvas(object):
        """진짜 캔버스에 검사가 보는 칸만 얹는다."""
        def __init__(self, cv):
            self._cv = cv
            self.w, self.h, self.bad, self.peak = PV.STAGE_W, PV.STAGE_H, [], 0

        @property
        def items(self):
            return self._cv.find_all()

        def __getattr__(self, name):
            return getattr(self._cv, name)

    moves_all = json.load(open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8"))["moves"]
    styles = {}
    for m in moves_all.values():
        styles.setdefault(FX.style_of(m), m)
    bad = []
    for s, m in sorted(styles.items()):
        for wrap in (None, lambda c: GB._ScaledCanvas(c, GB.FX_SCALE)):
            try:
                st, fx, n, took = run(m, cv=RealCanvas(real), wrap=wrap, more_ms=400)
                if n != 1 or real.find_all():
                    bad.append((s, n, len(real.find_all())))
            except Exception as e:                           # noqa: BLE001
                bad.append((s, "%s: %s" % (type(e).__name__, e)))
            real.delete("all")
    root.destroy()
    print(("TKOK %d가지" % len(styles)) if not bad else "틀림 %r" % (bad[:5],))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(tk_part() if "--tk" in sys.argv else main())
