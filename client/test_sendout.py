# -*- coding: utf-8 -*-
"""실시간 배틀: 들어갈 때의 연출과, 포켓몬이 몬스터볼에서 나오고 들어가는 연출 (1.10.4).

    python client/test_sendout.py

**창을 진짜로 띄운다.** 서버는 안 띄운다 (test_live_ui 의 가짜 api - 같은 엔진을 이 프로세스에서 돌린다).

제보 둘:
  * "실시간 배틀에서도 몬스터볼 던지는 애니메이션, 들어오는 애니메이션이 있으면 좋겠음"
  * "실시간 배틀 진입 시 애니메이션 효과가 너무 빨라서 크게 못 다가옴"

  1. 새 판을 열면 닫힌 띠 위에 **'나 VS 상대'** 가 한 박자 뜬다. 그동안 첫 장면은 안 튼다 (가려져서 못 본다).
  2. 띠가 걷히기 시작하면 첫 장면을 튼다: **볼이 날아와 열리고, 흰 윤곽이 단계로 커져 포켓몬이 된다.**
  3. 불러들일 때는 흰 윤곽으로 줄어들고 붉은 줄기가 돌아간다. 다음 포켓몬은 또 볼에서 나온다.
  4. 연출이 끝나면 그리던 것(볼·빛·줄기·이름)이 남지 않는다. 포켓몬은 평소처럼 움직인다.
  5. 연출 도중에 창 크기를 바꿔도 포켓몬이 제대로 선다.
  6. 관장 배틀에도 같은 연출이 있다. 관장의 볼은 관장의 손에서 나온다.
"""
import json
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-sendout-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from PIL import Image                                       # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import enter_fx as EF                     # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import sendout_fx as SO                   # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_live_battle as LUI              # noqa: E402
import test_live_ui as TL                                   # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def image_of(w, who):
    try:
        return str(w.cv.itemcget(w.sprite[who], "image"))
    except tk.TclError:
        return ""


def tagged(w, tag):
    try:
        return list(w.cv.find_withtag(tag))
    except tk.TclError:
        return []


def texts_on(w):
    out = {}
    for i in w.cv.find_all():
        if w.cv.type(i) == "text":
            out[w.cv.itemcget(i, "text")] = i
    return out


def covered(w):
    dark = [i for i in w.cv.find_all() if w.cv.type(i) == "rectangle" and w.cv.itemcget(i, "fill") == EF.BLACK
            and w.cv.itemcget(i, "state") != "hidden"]
    return sum((c[2] - c[0]) * (c[3] - c[1]) for c in (w.cv.coords(i) for i in dark)) / float(w.sw * w.sh)


def watch(root, w, until, sec=20.0):
    """until() 이 참이 될 때까지 돌리며 그동안 보인 것을 적는다."""
    seen = {"me": [], "foe": [], "ball_me": 0, "ball_foe": 0, "lines": 0, "samples": 0}
    end = time.time() + sec
    while time.time() < end:
        root.update()
        seen["samples"] += 1
        for who in ("me", "foe"):
            im = image_of(w, who)
            if not seen[who] or seen[who][-1] != im:
                seen[who].append(im)
            if tagged(w, "sendout_" + who):
                seen["ball_" + who] += 1
        seen["lines"] += any(w.cv.type(i) == "line" for i in tagged(w, "sendout"))
        if until():
            break
        time.sleep(0.004)
    return seen


def main():
    with open(os.path.join(TL.DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))

    print("=== 계산 (창 없이) ===")
    first = Image.new("RGBA", (80, 60), (0, 0, 0, 0))
    first.paste((200, 60, 60, 255), (20, 10, 60, 60))
    wf = SO.white_frames(first)
    chk("흰 윤곽은 다섯 단계로 커지고 마지막이 제 크기다", [f.size for f in wf] == [(16, 12), (32, 24), (48, 36), (64, 48), (80, 60)],
        [f.size for f in wf])
    px = wf[-1].getpixel((40, 40))
    chk("  포켓몬의 모양대로 희게 칠한다 (빈 곳은 비어 있다)", px == (255, 255, 255, 255) and wf[-1].getpixel((2, 2))[3] == 0, px)
    p0, p1 = (0.0, 100.0), (200.0, 100.0)
    chk("볼은 포물선으로 난다 (양 끝은 그대로, 가운데가 떠오른다)", SO.arc(p0, p1, 0, 40) == p0 and SO.arc(p0, p1, 1, 40) == p1
        and SO.arc(p0, p1, 0.5, 40) == (100.0, 60.0), SO.arc(p0, p1, 0.5, 40))
    chk("볼은 화면 밖(트레이너 쪽)에서 온다: 내 쪽은 왼쪽 아래, 상대는 오른쪽 위", SO.hand("me", 880, 336, 28)[0] < 0
        and SO.hand("foe", 880, 336, 28)[0] > 880 and SO.hand("me", 880, 336, 28)[1] > SO.hand("foe", 880, 336, 28)[1])
    chk("내보내는 연출은 1초 남짓, 불러들이는 것은 그 절반쯤", 0.8 <= SO.SEND_S <= 1.3 and 0.3 <= SO.BACK_S <= 0.6
        and LUI.SEND_MS >= SO.SEND_S * 1000 and LUI.RECALL_MS >= SO.BACK_S * 1000, (SO.SEND_S, SO.BACK_S))
    chk("**들어갈 때 천천히**: 이름을 한 박자 띄우고(1초쯤), 띠는 0.8초쯤 걸려 걷힌다 (예전 0.42초)",
        0.9 <= EF.HOLD_S <= 1.6 and 0.7 <= EF.OPEN_S <= 1.2, (EF.HOLD_S, EF.OPEN_S))
    w_, h_ = 880, 336
    a, b, c = EF.versus_spots(w_, h_, 0.0), EF.versus_spots(w_, h_, EF.SLIDE_S), EF.versus_spots(w_, h_, 9.0, 0.4)
    chk("이름은 양쪽 밖에서 들어와 가운데 좌우에 선다", a["me"][0] < 0 and a["foe"][0] > w_ and 0 < b["me"][0] < w_ / 2 < b["foe"][0] < w_
        and abs((w_ / 2 - b["me"][0]) - (b["foe"][0] - w_ / 2)) < 1 and b["vs"] == (w_ / 2.0, h_ / 2.0), (a, b))
    chk("  띠가 걷히면 다시 양쪽으로 물러난다 (VS 는 위로)", c["me"][0] < 0 and c["foe"][0] > w_ and c["vs"][1] < 0, c)

    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-400:])
    root.report_callback_exception = on_err

    print("\n=== 새 판을 연다 ===")
    api = TL.FakeApi(dex)
    app = TL.FakeApp(root, api, dex)
    t0 = time.time()
    w = LUI.LiveBattleWindow(app, api.match())
    root.update()
    tx = texts_on(w)
    chk("닫힌 띠 위에 '나 VS 상대' 를 준비한다", "VS" in tx and "나" in tx and "상대" in tx and covered(w) >= 0.99,
        (sorted(tx), covered(w)))
    chk("  첫 장면은 아직 안 틀었다 (가려져 있다) - 명령 칸도 비어 있다", w.busy and w.shown == {"me": None, "foe": None}
        and not w.left.winfo_children(), w.shown)
    # 이름이 다 들어와 선 모습을 그 자리에서 그려 본다 (시간을 기다려 찍으면 느린 컴퓨터에서 흔들린다)
    w._vs.draw(w.sw, w.sh, EF.SLIDE_S, 1.0)
    root.update_idletasks()
    tx = texts_on(w)
    boxes = dict((k, w.cv.bbox(tx[k])) for k in ("나", "상대", "VS"))
    chk("**한 박자**: 이름이 양쪽에 서고 가운데에 VS (화면 안, 서로 안 겹친다)",
        all(w.cv.itemcget(tx[k], "state") == "normal" for k in boxes)
        and boxes["나"][0] >= 0 and boxes["상대"][2] <= w.sw and boxes["나"][2] < boxes["VS"][0] and boxes["VS"][2] < boxes["상대"][0],
        boxes)
    top = [w.cv.find_all().index(tx[k]) for k in ("나", "상대", "VS")]
    darks = [i for i, it in enumerate(w.cv.find_all()) if w.cv.type(it) == "rectangle" and w.cv.itemcget(it, "fill") == EF.BLACK]
    chk("  이름은 띠보다 위에 그려진다", min(top) > max(darks), (top, darks[-3:]))
    watch(root, w, lambda: w.intro.get("start") is not None, 8.0)   # 첫 장면을 틀기 시작했다
    chk("**띠가 걷히기 시작할 때** 첫 장면을 튼다 (%.2f초 - 예전에는 창이 뜨자마자였다)" % (w.intro.get("start") or 0),
        w.intro.get("start") is not None and w.intro["start"] >= w.intro["open"] - 0.02
        and w.intro["open"] >= EF.HOLD_S, w.intro)
    chk("  그 전에 이름이 다 들어와 선 채로 닫혀 있었다", w.intro["names"] is True, w.intro)
    watch(root, w, lambda: w.shown["me"] is not None, 6.0)
    chk("  첫 포켓몬의 볼은 띠가 다 걷힌 뒤에 날아온다 (가려지지 않는다)", covered(w) < 0.05, covered(w))

    print("\n=== 볼에서 나온다 ===")
    seen = watch(root, w, lambda: not w.busy, 25.0)
    total = time.time() - t0
    # (연출은 시간으로 굴러가서 느린 컴퓨터에서는 그림을 건너뛴다. 화면을 찍어 센 수는 흔들리므로
    #  일이 일어난 차례는 sendout.trace 로 보고, 화면으로는 '보였다' 만 본다.)
    for who, kr in (("me", "내 포켓몬"), ("foe", "상대 포켓몬")):
        photos = [str(p) for p in (w.anims[who] or ([], []))[0]]
        ims = seen[who]
        chk("%s: 볼이 날아온다 (그동안 포켓몬 자리는 비어 있다)" % kr, seen["ball_" + who] > 0 and "" in ims, (seen["ball_" + who], ims[:3]))
        chk("  **볼이 떨어지고 -> 흰 윤곽이 커지고 -> 포켓몬이 선다** (이 차례로)",
            w.sendout.trace[who] == ["throw", "landed", "grow", "standing"] and ims[-1] in photos,
            (w.sendout.trace[who], ims[-1] in photos))
        chk("  다 나온 뒤에는 평소처럼 움직인다", w.anims[who] is not None and w.anim_jobs[who] is not None and not w.sendout.busy(who))
    chk("볼이 열릴 때 빛이 터진다 (여섯 갈래)", seen["lines"] > 0, seen["lines"])
    TL.rest(root, 0.3)
    chk("**그리던 것이 남지 않는다** (볼·빛·이름·띠)", not tagged(w, "sendout") and "VS" not in texts_on(w) and covered(w) == 0.0
        and float(w.win.attributes("-alpha")) == 1.0, (tagged(w, "sendout"), sorted(texts_on(w))[:4], covered(w)))
    chk("  들어가는 데 걸린 시간 %.1f초 (이름 한 박자 + 띠 + 볼 둘)" % total, 3.0 <= total <= 14.0, total)
    chk("  이제 기술을 고른다", bool(w.left.winfo_children()) and w.shown["me"]["name"] and w.shown["foe"]["name"])

    print("\n=== 불러들이고 다시 내보낸다 ===")
    before = w.shown["me"]["name"]
    w.do_switch(1)
    seen = watch(root, w, lambda: w.shown["me"] is not None and w.shown["me"]["name"] != before, 12.0)
    chk("불러들인다: 흰 윤곽으로 줄어들고 -> 붉은 줄기가 돌아가고 -> 사라진다",
        w.sendout.trace["me"][4:7] == ["recall", "beam", "gone"] and "" in seen["me"], (w.sendout.trace["me"][4:], seen["me"][:6]))
    seen = watch(root, w, lambda: not w.busy, 25.0)
    photos = [str(p) for p in (w.anims["me"] or ([], []))[0]]
    chk("다음 포켓몬도 볼에서 나온다 (%s -> %s)" % (before, w.shown["me"]["name"]),
        w.sendout.trace["me"][7:] == ["throw", "landed", "grow", "standing"] and seen["me"][-1] in photos,
        (w.sendout.trace["me"][7:], seen["ball_me"]))
    TL.rest(root, 0.3)
    chk("  끝나면 남는 것이 없고 포켓몬은 움직인다", not tagged(w, "sendout") and w.anim_jobs["me"] is not None and image_of(w, "me") in photos)

    print("\n=== 연출 도중에 창 크기를 바꾼다 ===")
    w.do_switch(0)
    watch(root, w, lambda: bool(tagged(w, "sendout_me")) and w.sendout.busy("me"), 12.0)
    chk("(볼이 날아가는 중이다)", w.sendout.busy("me"))
    w._scene()                                              # 창 크기를 바꾸면 장면을 통째로 다시 그린다 (battle_zoom)
    w._restore()
    watch(root, w, lambda: not w.busy, 25.0)
    TL.rest(root, 0.4)
    photos = [str(p) for p in (w.anims["me"] or ([], []))[0]]
    chk("**포켓몬이 제대로 서 있다** (연출은 그만두고 그대로 세운다)", image_of(w, "me") in photos and bool(photos)
        and not w.sendout.busy("me") and not tagged(w, "sendout") and w.shown["me"]["name"] == before,
        (image_of(w, "me"), w.shown["me"]["name"]))

    print("\n=== 하던 판을 다시 연다 ===")
    w.close()
    root.update()
    t0 = time.time()
    w = LUI.LiveBattleWindow(app, api.match())
    root.update()
    chk("이름은 안 띄운다 - 띠만 걷힌다 (바로 고를 수 있다)", "VS" not in texts_on(w) and not w.busy and covered(w) >= 0.99
        and bool(w.left.winfo_children()), sorted(texts_on(w))[:3])
    watch(root, w, lambda: covered(w) == 0.0 and float(w.win.attributes("-alpha")) == 1.0, 5.0)
    quick = time.time() - t0
    chk("  %.1f초 만에 다 걷힌다" % quick, quick <= EF.FADE_S + EF.OPEN_S + 0.8 and covered(w) == 0.0, quick)
    pump_ok = TL.pump(root, lambda: w.anims["me"] is not None and w.anims["foe"] is not None, 6.0)
    chk("  포켓몬은 볼 없이 그대로 서 있다", pump_ok and not tagged(w, "sendout"))
    w.close()
    root.update()

    print("\n=== 유턴: 쓰자마자 교체할 포켓몬을 고른다 (1.10.4) ===")
    import random
    from common import live_battle as LB
    api2 = TL.FakeApi(dex)
    mine = [TL.mon(dex, "NINJASK", ["UTURN", "XSCISSOR"], 11), TL.mon(dex, "SNORLAX", ["TACKLE"], 12)]
    foes = [TL.mon(dex, "BLISSEY", ["SEISMICTOSS"], 13), TL.mon(dex, "SNORLAX", ["TACKLE"], 14)]
    api2.lb = LB.LiveBattle(dex, (1, "나", mine), (2, "상대", foes), rng=random.Random(4))
    api2.events = api2.lb.start()
    app2 = TL.FakeApp(root, api2, dex)
    w = LUI.LiveBattleWindow(app2, api2.match())
    watch(root, w, lambda: not w.busy, 25.0)
    TL.rest(root, 0.3)
    ninja, lax = api2.lb.a.team[0], api2.lb.a.team[1]
    w.use_move("UTURN")
    watch(root, w, lambda: not w.busy and w.view.get("phase") == "switch", 25.0)
    TL.rest(root, 0.4)
    from test_learn_dialog import texts
    tx = " ".join(texts(w.win))
    chk("유턴을 쓰면 **턴 도중에** 교체 칸이 뜬다 (상대는 아직 안 움직였다)", w.view.get("phase") == "switch" and w.view.get("canAct")
        and "교체할 포켓몬을 고르세요" in tx and "PP" not in tx and ninja.hp == ninja.maxhp and api2.lb.turn == 1
        and api2.lb.mid is not None, (w.view.get("phase"), tx[:120], ninja.hp, ninja.maxhp))
    chk("  '돌아가기' 는 없다 (꼭 골라야 한다)", "돌아가기" not in tx, tx[:160])
    w.do_switch(1)
    seen = watch(root, w, lambda: not w.busy and w.view.get("phase") == "choose", 25.0)
    TL.rest(root, 0.4)
    photos = [str(p_) for p_ in (w.anims["me"] or ([], []))[0]]
    chk("고르면 턴이 이어진다: 나온 포켓몬이 상대의 기술을 맞는다 (유턴을 쓴 포켓몬은 멀쩡하다)",
        api2.lb.a.slot == 1 and lax.hp == lax.maxhp - 50 and ninja.hp == ninja.maxhp and api2.lb.turn == 1
        and w.shown["me"]["name"] == "잠만보" and w.shown["me"]["hp"] == lax.hp, (api2.lb.a.slot, lax.maxhp - lax.hp, w.shown["me"]))
    chk("  물러날 때 붉은 줄기, 나올 때 볼 (연출도 그대로 탄다)",
        w.sendout.trace["me"][-7:] == ["recall", "beam", "gone", "throw", "landed", "grow", "standing"]
        and image_of(w, "me") in photos, w.sendout.trace["me"][-8:])
    chk("  이제 다시 기술을 고른다", "PP" in " ".join(texts(w.win)) and not w.sent)
    w.close()
    root.update()

    print("\n=== 관장 배틀에도 같은 연출 ===")
    import test_gym_ui as TG
    from poketdesktop import ui_gym_battle as GB
    with open(os.path.join(TL.DATA, "gyms.json"), encoding="utf-8") as f:
        gyms = json.load(f)
    with open(os.path.join(TL.DATA, "korea_map.json"), encoding="utf-8") as f:
        kmap = json.load(f)
    party = [TG.mon(dex, "NINJASK", 60, ["UTURN", "XSCISSOR"], "SPEEDBOOST", 21),
             TG.mon(dex, "SNORLAX", 60, ["TACKLE"], "THICKFAT", 22)]
    gapi = TG.FakeApi(dex, gyms, kmap, party)
    gapp = TG.FakeApp(root, gapi, dex)
    # 포켓몬이 둘 이상인 가장 약한 관장 (내 아이스크가 먼저 움직이고, 유턴 뒤에도 상대가 남는다)
    region = min((r for r in gapi.by_region if len(gapi.by_region[r]["team"]) >= 2),
                 key=lambda r: gapi.by_region[r]["level"])
    g = GB.GymBattleWindow(gapp, gapi.gym_start(region))
    seen = watch(root, g, lambda: not g.busy, 25.0)
    TL.rest(root, 0.3)
    for who, kr in (("me", "내 포켓몬"), ("foe", "관장의 포켓몬")):
        photos = [str(p_) for p_ in (g.anims[who] or ([], []))[0]]
        chk("%s도 볼에서 나온다 (떨어지고 -> 커지고 -> 선다)" % kr, g.sendout.trace[who] == ["throw", "landed", "grow", "standing"]
            and image_of(g, who) in photos and g.anim_jobs[who] is not None, g.sendout.trace[who])
    hx, hy = g.sendout_hand("foe")
    fx, fy = g.sendout.spot("foe")
    chk("**관장의 볼은 관장의 손에서 나온다** (장면 안, 상대 자리의 오른쪽)", fx < hx < g.sw and 0 < hy < g.sh
        and g.sendout.hand_of("foe") == (hx, hy), ((hx, hy), (fx, fy), g.sw))
    chk("  내 볼은 화면 밖(왼쪽 아래)에서 날아온다", g.sendout_hand("me") is None and g.sendout.hand_of("me")[0] < 0)
    chk("  끝나면 그리던 것이 남지 않는다", not tagged(g, "sendout") and not g.sendout.busy("me") and not g.sendout.busy("foe"))
    g.use_move("UTURN")
    watch(root, g, lambda: not g.busy and g.view.get("needSwitch"), 25.0)
    TL.rest(root, 0.3)
    tx = " ".join(texts(g.win))
    chk("관장 배틀의 유턴도 쓰자마자 교체 칸이 뜬다 (상대는 아직 안 움직였다)", g.view.get("needSwitch")
        and "교체할 포켓몬을 고르세요" in tx and gapi.tb.mid is not None and gapi.tb.me.hp == gapi.tb.me.maxhp
        and gapi.tb.turn == 1, (tx[:100], gapi.tb.turn))
    g.do_switch(1)
    watch(root, g, lambda: not g.busy and not g.view.get("needSwitch"), 25.0)
    TL.rest(root, 0.3)
    chk("  물러날 때 붉은 줄기, 나올 때 볼", g.sendout.trace["me"][-7:] == ["recall", "beam", "gone", "throw", "landed", "grow", "standing"]
        and g.shown["me"]["name"] == "잠만보", g.sendout.trace["me"][-8:])
    g.close()
    root.update()
    chk("닫으면 쥐고 있던 그림을 놓는다", g.sendout._balls == {} and g.sendout.keep == {"me": [], "foe": []})
    chk("도는 동안 오류 없음", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
