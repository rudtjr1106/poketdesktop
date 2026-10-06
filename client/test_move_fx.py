# -*- coding: utf-8 -*-
"""기술 연출 검사 (1.10.0).

    python client/test_move_fx.py

**창을 띄우지 않는다.** 캔버스와 시계를 흉내 낸 것(tools/fx_preview 의 FakeCanvas /
FakeRoot)에 연출을 그대로 돌려서 센다. 눈으로 보려면 tools/fx_preview.py 를 쓴다.

못 박는 것.

  1. 연출 고르기 - 문포스는 달, 화염방사는 불길, 지진은 갈라진 땅 ... 그리고
     이름표(EXACT)에 적은 영문 이름이 도감에 실제로 있다. 고른 연출은 전부 구현돼 있다.
  2. 919종 전부, 양쪽 방향으로: 예외 없이 **끝까지 가고**(2초 안), 끝나면 캔버스에
     **찌꺼기가 없고**, 끝났다는 신호(on_done)는 **한 번만** 온다.
     한때 떠 있는 도형 수도 넘치지 않는다 (바탕화면 레이어가 느려진다).
  3. 중간에 멈춰도(stop) 찌꺼기가 없고 on_done 은 안 온다 - 배틀 창을 닫을 때다.
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
PEAK_MAX = 90                   # 한때 떠 있는 도형 수
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


def run(move, flip=False, flat=False, cv=None, wrap=None, stop_at=None, more_ms=0):
    """연출 하나를 돌린다. (stage, fx, 끝난 횟수, 걸린 ms) 를 돌려준다."""
    me, foe = (PV.FLAT_ME, PV.FLAT_FOE) if flat else (PV.ME, PV.FOE)
    stage = PV.FakeStage(cv=cv or StrictCanvas(), me=me, foe=foe)
    raw = stage.cv
    if wrap:
        stage.cv = wrap(raw)
    src, dst = (foe, me) if flip else (me, foe)
    k = getattr(stage.cv, "k", 1.0)
    done = []
    fx = FX.Effect(stage, move, (src[0] / k, src[1] / k), (dst[0] / k, dst[1] / k),
                   lambda: done.append(stage.root.now), who="foe" if flip else "me")
    fx.play()
    stage.stopped = False
    while stage.root.now < LIMIT_MS + 600 and not done:
        if stop_at is not None and stage.root.now >= stop_at:
            fx.stop()
            stage.stopped = True
            break
        stage.root.advance(PV.FRAME_MS)
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
    unused = sorted(s for s in MF.STYLES if s not in styles)
    chk("안 쓰이는 연출이 없다", not unused, unused)
    want = {"문포스": "moon", "화염방사": "flame", "불꽃세례": "ember", "불대문자": "daimonji",
            "하이드로펌프": "jet", "파도타기": "surf", "거품광선": "bubble", "지진": "quake",
            "스톤에지": "pillars", "스톤샤워": "rockfall", "사우전드애로": "arrows", "용성군": "meteor",
            "골드러시": "coins", "번개": "thunder", "10만볼트": "thunder", "방전": "zap",
            "사이코키네시스": "psy", "섀도볼": "ball", "용의파동": "pulse", "매지컬리프": "leaf",
            "덩굴채찍": "whip", "폭풍": "tornado", "대지의힘": "erupt", "파워젬": "gem",
            "냉동빔": "laser", "솔라빔": "laser", "파괴광선": "laser", "눈보라": "blizzard",
            "요정의바람": "sparkle", "매지컬샤인": "flash", "오물폭탄": "sludge", "독침": "needles",
            "거대해머": "hammer", "방어": "shield", "리플렉터": "wall",
            "치근거리기": "hit", "몸통박치기": "hit", "아이언헤드": "hit", "인파이트": "flurry",
            "역린": "flurry", "전광석화": "dash", "불릿펀치": "dash", "고스트다이브": "phantom",
            "에어슬래시": "blades", "깜짝베기": "slash", "드래곤클로": "claw", "물수리검": "multi",
            "플레어드라이브": "recoil", "냉동펀치": "punch", "블레이즈킥": "kick", "독찌르기": "stab",
            "드레인키스": "drain",
            # 예전 그대로인 것
            "깨물어부수기": "bite", "칼춤": "dance", "울음소리": "sound", "수면가루": "powder"}
    wrong = dict((n, FX.style_of(kr(n))) for n, s in want.items() if kr(n) and FX.style_of(kr(n)) != s)
    chk("기술마다 제 연출 (%d개)" % len(want), not wrong and all(kr(n) for n in want),
        wrong or [n for n in want if not kr(n)])
    attack_only = set(MF.STYLES) - {"shield", "wall", "tornado", "drain", "blizzard", "sludge", "boom"}
    leak = sorted((m["kr"], FX.style_of(m)) for m in moves
                  if (m.get("cat") or "status") == "status" and FX.style_of(m) in attack_only
                  and MF.key_of(m) not in MF.EXACT and FX._base_style(m) != FX.style_of(m))
    chk("변화기를 공격 연출로 바꾸지 않는다", not leak, leak[:8])
    big = FX.Effect(PV.FakeStage(), kr("파괴광선"), PV.ME, PV.FOE, None).big
    small = FX.Effect(PV.FakeStage(), kr("불꽃세례"), PV.ME, PV.FOE, None).big
    plain = FX.Effect(PV.FakeStage(), kr("칼춤"), PV.ME, PV.FOE, None).big
    chk("센 기술은 크게, 약한 기술은 작게, 변화기는 그대로", big > 1.2 and small < 1.0 and plain == 1.0,
        (big, small, plain))

    print("\n=== 2. 전부 돌려 본다 (%d종 x 양쪽) ===" % len(moves))
    random.seed(20261006)
    errs, slow, left, twice, peaks, bad_cfg = [], [], [], [], [], []
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
    chk("예외가 없다", not errs, errs[:5])
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
        for cat in ("physical", "special", "status"):
            try:
                st, fx, n, took = run({"type": typ, "cat": cat, "flags": []}, flat=True, more_ms=400)
                if n != 1 or st.raw.items:
                    bare.append((typ, cat, fx.style, n, len(st.raw.items)))
            except Exception as e:                           # noqa: BLE001
                bare.append((typ, cat, "%s: %s" % (type(e).__name__, e)))
    chk("타입과 분류만 아는 기술도 끝까지 간다", not bare, bare[:5])
    st, fx, n, took = run(kr("치근거리기"))
    chk("접촉기는 달려든다 (한 번)", st.lunges == 1, st.lunges)
    st, fx, n, took = run(kr("문포스"))
    chk("닿지 않는 기술은 안 달려든다", st.lunges == 0, st.lunges)

    print("\n=== 3. 중간에 멈춘다 ===")
    bad, cut = [], 0
    for s, m in sorted(styles.items()):
        for at in (60, 240, 520):
            st, fx, n, took = run(m, stop_at=at, more_ms=1500)
            if not st.stopped:                          # 그 전에 끝난 짧은 연출
                continue
            cut += 1
            if n or st.raw.items or not fx.dead:
                bad.append((s, at, n, len(st.raw.items)))
    chk("멈추면 찌꺼기가 없고 끝났다는 신호도 안 온다 (%d번)" % cut, not bad and cut > len(styles) * 2, bad[:5])

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
    near = [p for p in seen[-30:] if abs(p[0] - PV.FOE[0]) < 60 and abs(p[1] - PV.FOE[1]) < 60]
    chk("그리는 자리는 제자리 (과녁 둘레)", len(near) >= 10, (len(near), seen[-3:]))

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
