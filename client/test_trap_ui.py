# -*- coding: utf-8 -*-
"""붙잡혀 있으면 교체를 잠그고 까닭을 보인다 (게시판 #664 뒤, 11/19) - 관장 · 실시간 배틀 창. 진짜 Tk 로 본다.

    python client/test_trap_ui.py

회오리불꽃에 묶여도 화면에는 아무 표시가 없고 교체 단추도 켜져 있어서, 묶기가 걸렸는지 실패했는지 알 수 없었다.
누르면 서버가 거절했는데, 그 문구도 다시 불러오며 '무엇을 할까?' 로 곧바로 덮였다.

서버(common/test_trap_view.py)가 view 에 싣는 것:
  side["noSwitch"]   지금 스스로 바꿀 수 없는 까닭. 있으면 교체 단추를 잠그고 글상자에 그 문구 + '무엇을 할까?'.
  mon["bound"]       조이기류 {move, moveKr, turns} - 이름표에 '회오리불꽃에 붙잡힘' 꼬리표 (내가 건 것은 남은 턴까지).
  (실시간은 붙잡혀 있으면 me["switches"] 도 빈 목록이다 - 옛 앱도 단추를 잠근다.)

  1. 붙잡히면 교체 단추가 잠기고, 눌러도(잠긴 채 교체 칸을 열려 해도) 서버로 안 간다.
  2. 글상자에 까닭이 뜬다. 이름표에 꼬리표 - 내 것은 턴 수 없이, 상대 것(내가 건 것)은 남은 턴까지.
  3. 풀리면 단추가 다시 켜지고 꼬리표가 사라진다.
  4. 옛 서버(칸 없음): 예전처럼 단추가 켜지고 꼬리표가 없다 (깨지지 않는다).
  5. 서버가 거절한 문구가 글상자에 남는다 (다시 불러온 뒤에도).

기본 화면을 본 뒤 같은 검사를 DP 계열 테마로 한 번씩 더 돈다 (자식 프로세스). 이름표를 그리는 곳은
DPDuel._paint_box (dp · pt · bw · emerald · swsh) 와 gs 의 것 둘이다.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-test-trap-"))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins                              # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

OK = FAIL = 0
ERRORS = []
SKINS = ("dp", "pt", "bw", "emerald", "swsh", "gs")
DATA = os.path.join(ROOT, "server", "data")

ME_BIND = {"turns": 3, "by": "foe", "move": "FIRESPIN"}
FOE_BIND = {"turns": 4, "by": "me", "move": "WHIRLPOOL"}
WHY = "회오리불꽃에 붙잡혀 있어 교체할 수 없다"
ME_TAG = "회오리불꽃에 붙잡힘"
FOE_TAG = "바다회오리에 붙잡힘 4턴"


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Refused(Exception):
    """서버가 409 로 거절한 것 (api 의 ApiError 와 같은 칸)."""
    status = 409

    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message


def pump(root, cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return False


def rest(root, sec=0.3):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def said(w):
    """글상자의 말 (DP 계열은 _said, 기본은 msg 라벨)."""
    if hasattr(w, "_said"):
        from common.korean import natural
        return natural(w._said or "")
    return w.msg.cget("text")


def state(btn):
    """교체 단추 (기본: ui_common.PushButton, DP 계열: Touch) - 둘 다 enabled 를 든다."""
    return "normal" if btn.enabled else "disabled"


def press(btn):
    """단추를 누른 것처럼 (둘 다 켜져 있을 때만 command 를 부른다)."""
    if btn.enabled and btn.command:
        btn.command()


def plate_texts(w, who):
    """그 이름표의 상태 줄 글 (DP 계열은 st_<who> 꼬리표들, 기본은 status 글 하나)."""
    cv = w.cv
    ids = list(cv.find_withtag("st_" + who))
    if not ids and "status" in w.box[who]:
        ids = [w.box[who]["status"]]
    return [cv.itemcget(i, "text") for i in ids if cv.type(i) == "text" and cv.itemcget(i, "text")]


def has_tag(w, who, tag, exact=False):
    for t in plate_texts(w, who):
        parts = [p for p in t.split("  ") if p] if not exact else [t]
        if tag in parts:
            return True
    return False


def inside_canvas(w, who):
    """그 이름표의 꼬리표 글이 장면 밖으로 안 나간다."""
    cv = w.cv
    width = cv.winfo_width() if cv.winfo_width() > 1 else int(cv["width"])
    for i in cv.find_withtag("st_" + who) or [w.box[who].get("status")]:
        bb = cv.bbox(i) if i else None
        if bb and (bb[0] < -1 or bb[2] > width + 1):
            return False, bb
    return True, None


def strip_new(view):
    """옛 서버의 view - noSwitch · trapped · bound 칸이 없다."""
    view = json.loads(json.dumps(view))
    for side in ("me", "foe"):
        s = view.get(side) or {}
        s.pop("noSwitch", None)
        s.pop("trapped", None)
        for m in s.get("team") or []:
            m.pop("bound", None)
    return view


# ---------------------------------------------------------------- 관장
def gym_checks(root, dex):
    import test_gym_ui as TG
    from poketdesktop import ui_gym_battle as GB
    print("\n=== 관장 배틀 (%s) ===" % skins.active())
    orig_later = GB.GymBattleWindow.later
    GB.GymBattleWindow.later = lambda self, ms, fn: orig_later(self, max(1, ms // 10), fn)
    gyms = json.load(open(os.path.join(DATA, "gyms.json"), encoding="utf-8"))
    party = [TG.mon(dex, "CHARIZARD", 50, ["FLAMETHROWER", "DRAGONCLAW", "AIRSLASH", "ROOST"], "BLAZE", 11),
             TG.mon(dex, "GARCHOMP", 62, ["EARTHQUAKE", "DRAGONCLAW", "STONEEDGE", "SWORDSDANCE"], "ROUGHSKIN", 12)]
    api = TG.FakeApi(dex, gyms, {"sido": [], "sgg": []}, party)
    acts = []
    loads = []
    real_act, real_battle = api.gym_act, api.gym_battle
    refuse = []

    def gym_act(bid, kind, move="", slot=-1, **kw):
        acts.append(kind)
        if refuse:
            raise Refused(refuse.pop())
        return real_act(bid, kind, move, slot, **kw)

    def gym_battle():
        loads.append(1)
        return real_battle()
    api.gym_act, api.gym_battle = gym_act, gym_battle
    app = TG.FakeApp(root, api, dex)
    region = next(t["region"] for t in gyms["trainers"] if t["name"] == "난천")
    b = GB.GymBattleWindow(app, api.gym_start(region))
    pump(root, lambda: not b.busy, 30)
    root.update()
    chk("처음: 교체 단추가 켜져 있다", state(b.switch_btn) == "normal", state(b.switch_btn))
    chk("  꼬리표 없음", not has_tag(b, "me", ME_TAG) and not has_tag(b, "foe", FOE_TAG),
        (plate_texts(b, "me"), plate_texts(b, "foe")))

    def reload(cond):
        n = len(loads)
        b._reload()
        pump(root, lambda: len(loads) > n and not b.busy and cond(), 10)
        rest(root, 0.15)

    print("1 · 2. 회오리불꽃에 붙잡혔다")
    api.tb.me.cond["bound"] = dict(ME_BIND)
    api.tb.foe.cond["bound"] = dict(FOE_BIND)
    reload(lambda: (b.view.get("me") or {}).get("noSwitch"))
    chk("교체 단추가 잠긴다", state(b.switch_btn) == "disabled", state(b.switch_btn))
    msg = said(b)
    chk("글상자에 까닭 + 무엇을 할까?", WHY in msg and "무엇을 할까" in msg, msg)
    chk("내 이름표에 '%s' (턴 수 없음)" % ME_TAG, has_tag(b, "me", ME_TAG) and not any(
        "턴" in t and "회오리불꽃" in t for t in plate_texts(b, "me")), plate_texts(b, "me"))
    chk("상대 이름표에 '%s' (내가 건 것)" % FOE_TAG, has_tag(b, "foe", FOE_TAG), plate_texts(b, "foe"))
    for who in ("me", "foe"):
        ok, bb = inside_canvas(b, who)
        chk("  %s 꼬리표가 장면 안" % who, ok, bb)
    n = len(acts)
    press(b.switch_btn)
    root.update()
    b.open_switch()
    root.update()
    chk("눌러도 · 교체 칸을 열려 해도 기술 화면에 남고 서버로 안 간다",
        b.mode == "moves" and len(acts) == n and state(b.switch_btn) == "disabled", (b.mode, acts[n:]))
    chk("  글상자도 그대로", WHY in said(b), said(b))

    print("5. 서버가 거절한 문구가 남는다")
    refuse.append("검사: 지금은 그 기술을 쓸 수 없습니다.")
    n = len(loads)
    b.use_move((b.view["me"]["team"][b.view["me"]["slot"]]["moves"] or [{}])[0].get("key"))
    pump(root, lambda: len(loads) > n and not b.busy, 10)
    rest(root, 0.3)
    chk("다시 불러온 뒤에도 거절 문구가 글상자에 있다", "그 기술을 쓸 수 없습니다" in said(b), said(b))
    chk("  기술 화면으로 돌아와 있다", b.mode == "moves" and not b.busy, (b.mode, b.busy))

    print("3. 풀렸다")
    api.tb.me.cond.pop("bound", None)
    api.tb.foe.cond.pop("bound", None)
    reload(lambda: not (b.view.get("me") or {}).get("noSwitch"))
    chk("교체 단추가 다시 켜진다", state(b.switch_btn) == "normal", state(b.switch_btn))
    chk("  글상자는 평소대로", WHY not in said(b) and "무엇을 할까" in said(b), said(b))
    chk("  꼬리표가 사라진다", not has_tag(b, "me", ME_TAG) and not has_tag(b, "foe", FOE_TAG),
        (plate_texts(b, "me"), plate_texts(b, "foe")))

    print("4. 옛 서버 (칸 없음)")
    api.tb.me.cond["bound"] = dict(ME_BIND)
    real_view = api.tb.view
    api.tb.view = lambda: strip_new(real_view())
    reload(lambda: True)
    chk("옛 서버: 단추는 예전처럼 켜져 있다 · 꼬리표 없음",
        state(b.switch_btn) == "normal" and not has_tag(b, "me", ME_TAG), (state(b.switch_btn), plate_texts(b, "me")))
    api.tb.view = real_view
    api.tb.me.cond.pop("bound", None)
    b.close()
    root.update()


# ---------------------------------------------------------------- 실시간
def live_checks(root, dex):
    import test_live_ui as TL
    from poketdesktop import ui_live_battle as LUI
    print("\n=== 실시간 배틀 (%s) ===" % skins.active())
    orig_later = LUI.LiveBattleWindow.later
    LUI.LiveBattleWindow.later = lambda self, ms, fn: orig_later(self, max(1, ms // 10), fn)
    api = TL.FakeApi(dex)
    sent = []
    refuse = []
    real_act = api.live_act

    def live_act(kind, move="", slot=-1, **kw):
        sent.append(kind)
        if refuse:
            raise Refused(refuse.pop())
        return real_act(kind, move, slot, **kw)
    api.live_act = live_act
    app = TL.FakeApp(root, api, dex)
    w = LUI.LiveBattleWindow(app, api.match())
    pump(root, lambda: not w.busy, 25)
    rest(root, 0.3)
    chk("처음: 교체 단추가 켜져 있다", state(w.switch_btn) == "normal", state(w.switch_btn))

    def poll(m=None):
        """폴링 한 번 (ui_live_battle._poll 의 done 과 같은 길)."""
        w.sync(m or api.match())
        w._refresh()
        root.update()

    print("1 · 2. 회오리불꽃에 붙잡혔다 (폴링으로 알게 된다)")
    api.lb.a.mon.cond["bound"] = dict(ME_BIND)
    api.lb.b.mon.cond["bound"] = dict(FOE_BIND)
    poll()
    chk("교체 단추가 잠긴다", state(w.switch_btn) == "disabled", state(w.switch_btn))
    chk("글상자에 까닭 + 무엇을 할까?", WHY in said(w) and "무엇을 할까" in said(w), said(w))
    chk("내 이름표에 '%s'" % ME_TAG, has_tag(w, "me", ME_TAG), plate_texts(w, "me"))
    chk("상대 이름표에 '%s'" % FOE_TAG, has_tag(w, "foe", FOE_TAG), plate_texts(w, "foe"))
    for who in ("me", "foe"):
        ok, bb = inside_canvas(w, who)
        chk("  %s 꼬리표가 장면 안" % who, ok, bb)
    n = len(sent)
    press(w.switch_btn)
    root.update()
    chk("눌러도 서버로 안 간다", len(sent) == n, sent[n:])

    print("5. 서버가 거절한 문구가 남는다")
    refuse.append("검사: 지금은 그 기술을 쓸 수 없습니다.")
    w.use_move((w.view["me"].get("moves") or [{}])[0].get("key"))
    pump(root, lambda: not w.sent, 10)
    rest(root, 0.2)
    chk("거절 문구가 글상자에 있다 ('무엇을 할까?' 로 안 덮인다)", "그 기술을 쓸 수 없습니다" in said(w), said(w))

    print("3. 풀렸다")
    api.lb.a.mon.cond.pop("bound", None)
    api.lb.b.mon.cond.pop("bound", None)
    poll()
    chk("교체 단추가 다시 켜진다", state(w.switch_btn) == "normal", state(w.switch_btn))
    chk("  꼬리표가 사라진다", not has_tag(w, "me", ME_TAG) and not has_tag(w, "foe", FOE_TAG),
        (plate_texts(w, "me"), plate_texts(w, "foe")))

    print("4. 옛 서버 (칸 없음, switches 는 있다)")
    api.lb.a.mon.cond["bound"] = dict(ME_BIND)
    real_match = api.match

    def old_match():
        m = real_match()
        m["battle"] = strip_new(m["battle"])
        m["battle"]["me"]["switches"] = [1]      # 옛 서버는 붙잡혀 있어도 자리를 줬다
        return m
    api.match = old_match                        # (창이 스스로 도는 폴링도 이것을 받는다)
    poll()
    w.show_commands()
    root.update()
    chk("옛 서버: 단추는 예전처럼 켜져 있다 · 꼬리표 없음",
        state(w.switch_btn) == "normal" and not has_tag(w, "me", ME_TAG), (state(w.switch_btn), plate_texts(w, "me")))
    api.match = real_match
    api.lb.a.mon.cond.pop("bound", None)
    w.close()
    root.update()


def main():
    print("=== 테마: %s ===" % skins.active())
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()

    def on_err(exc, val, tb):
        import traceback
        ERRORS.append("".join(traceback.format_exception(exc, val, tb))[-400:])
    root.report_callback_exception = on_err
    U.init_fonts(root)
    U.apply_theme(root)
    gym_checks(root, dex)
    live_checks(root, dex)
    rest(root, 0.3)
    chk("화면 콜백 오류 없음", not ERRORS, ERRORS[:2])
    root.destroy()
    print("\n[%s] %d개 통과, %d개 실패" % (skins.active(), OK, FAIL))
    bad = 1 if FAIL else 0
    if not os.environ.get("POKET_SKIN"):
        for key in SKINS:
            env = dict(os.environ, POKET_SKIN=key, POKET_HOME=tempfile.mkdtemp(prefix="poket-test-trap-%s-" % key))
            bad |= subprocess.call([sys.executable, os.path.abspath(__file__)], env=env)
    return bad


if __name__ == "__main__":
    sys.exit(main())
