# -*- coding: utf-8 -*-
"""화면 테마 'dp' - 배틀 창(skins/dp/battle.py) v2 다듬기 검사.

    python client/test_skin_dp_battle.py

창을 진짜로 띄운다 (가짜 서버는 test_gym_ui · test_live_ui 의 것). 동작 흐름(기술 · 교체 · 기권 → 결과)은
test_skin_dp.py 11 · 12 · 13 이 본다. 여기서는 v2 에서 바꾼 그림만 본다:
  1. 위 화면 하늘에 흰 가로줄이 없다 (번지는 빛깔 띠만). 글상자는 테 한 겹 + 흰 바탕 (오른쪽 빗금 없음).
  2. 아래 화면에 몬스터볼 무늬(굵은 테의 큰 고리)가 없다. 단추 글씨는 테두리 없이 한 번만 그린다.
  3. 관장 창은 상대 이름표에도 체력 숫자가 있다 (기본 창과 같다). 실시간 창은 상대 체력 숫자를 숨긴다.
  4. 기술 단추: 글씨에 테두리가 없다. 올린 기술의 빨간 꺾쇠가 아랫줄('포켓몬' · '기권')을 덮지 않는다.
     아랫줄 단추는 글씨가 들어가는 폭이고 서로 · 알약과 겹치지 않는다. 작은 창 · 큰 창에서도.
"""
import json
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-skin-dp-battle-")
os.environ["POKET_SKIN"] = "dp"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins                              # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def texts_at(cv, tag=None):
    """캔버스의 글자 항목 [(id, 글)] - tag 를 주면 그 태그만."""
    ids = cv.find_withtag(tag) if tag else cv.find_all()
    return [(i, cv.itemcget(i, "text")) for i in ids if cv.type(i) == "text" and cv.itemcget(i, "text")]


def doubled(cv, tag=None):
    """같은 글을 여러 번 겹쳐 그린 것 (테두리 글씨는 9번 · 그림자 글씨는 2번) - 한 단추 안에서 같은 글이 두 번 넘게면 테두리."""
    seen = {}
    for _i, t in texts_at(cv, tag):
        seen[t] = seen.get(t, 0) + 1
    return sorted(t for t, n in seen.items() if n > 2)


def gym(root, dex):
    import test_gym_ui as TG
    from poketdesktop import ui_gym_battle as GB
    gyms = json.load(open(os.path.join(TG.DATA, "gyms.json"), encoding="utf-8"))
    party = [TG.mon(dex, "CHARIZARD", 50, ["FLAMETHROWER", "DRAGONCLAW", "AIRSLASH", "ROOST"], "BLAZE", 11),
             TG.mon(dex, "GARCHOMP", 62, ["EARTHQUAKE", "DRAGONCLAW", "STONEEDGE", "SWORDSDANCE"], "ROUGHSKIN", 12)]
    api = TG.FakeApi(dex, gyms, {"sido": [], "sgg": []}, party)
    app = TG.FakeApp(root, api, dex)
    app.settings = {}
    region = next(t["region"] for t in gyms["trainers"] if t["name"] == "난천")
    b = GB.GymBattleWindow(app, api.gym_start(region))
    TG.pump(root, lambda: not b.busy, 30)
    root.update()
    chk("관장 배틀은 DP", type(b).__module__.endswith("skins.dp.gym_battle"), type(b).__module__)

    print("1. 위 화면 · 글상자")
    sw = b.sw
    # 하늘의 흰 가로줄은 창 너비만큼의 얇은 띠였다 - 띠 높이가 번지는 빛깔 띠(4px)보다 얇은 것이 없어야 한다
    thin = [i for i in b.cv.find_all() if b.cv.type(i) == "rectangle"
            and (lambda c: c[2] - c[0] >= sw - 1 and c[3] - c[1] < 3)(b.cv.coords(i))]
    chk("하늘에 흰 가로줄이 없다", not thin, len(thin))
    shapes = [i for i in b.mcv.find_all() if b.mcv.type(i) in ("rectangle", "polygon")]
    chk("글상자는 테 한 겹 + 흰 바탕 (빗금 없음)", len(shapes) == 2, len(shapes))

    print("2. 아래 화면")
    rings = [i for i in b.bcv.find_all() if b.bcv.type(i) == "oval" and float(b.bcv.itemcget(i, "width")) > 4]
    chk("몬스터볼 무늬가 없다", not rings, len(rings))
    twice = doubled(b.bcv, "tomon") + doubled(b.bcv, "torun")
    chk("포켓몬 · 기권 단추 글씨에 테두리가 없다", not twice, twice)

    print("3. 체력 숫자")
    foe_hp = b.box["foe"].get("hp")
    got = b.cv.itemcget(foe_hp[1], "text") if foe_hp else ""
    chk("관장 창: 상대 이름표에 체력 숫자", "/" in got, got)
    # 상대 이름표가 커졌다 (80 → 96). 가장 낮은 장면에서도 내 도트 머리(0.93 x 장면 + 10 - 도트 높이) 위에서 끝나야 한다
    from poketdesktop import battle_zoom as Z
    plate_bottom = U.h(14) + b._plate_h(False)
    head = int(U.h(b.ZOOM_MIN_SCENE) * 0.93) + U.h(10) - Z.px(GB.MON_H["me"])
    chk("상대 이름표가 내 포켓몬 머리를 덮지 않는다 (가장 낮은 장면에서도)", plate_bottom <= head,
        (plate_bottom, head))

    print("4. 기술 단추")
    chk("내 차례면 바로 기술 화면 (싸운다 단계 없음)", b._page == "moves" and len(b._move_btns) == 4, b._page)
    twice = [t for m in b._move_btns for t in doubled(b.bcv, m.tag)]
    chk("기술 단추 글씨에 테두리가 없다", not twice, twice)
    mv = b._move_btns[2]
    b.lower._motion(type("E", (), {"x": (mv.box[0] + mv.box[2]) // 2, "y": (mv.box[1] + mv.box[3]) // 2})())
    root.update()
    corner_bottom = b.bcv.bbox(mv.tag)[3] - 1                  # (꺾쇠까지 든 그 단추의 그림 전체)
    row_top = min(b.switch_btn.box[1], b.forfeit_btn.box[1])
    chk("올린 기술의 꺾쇠가 아랫줄을 덮지 않는다", corner_bottom <= row_top, (corner_bottom, row_top))
    b.lower._leave(None)
    # 아랫줄 - 메가진화 · Z기술 알약이 있을 때도, 작은 창 · 큰 창에서도
    b.close()
    for k in (None, str(Z.MIN_K), "1.6"):
        if k:
            os.environ["POKET_BATTLE_ZOOM"] = k            # (기본 크기의 몇 배로 띄운다 - 끌어서 바꾼 창과 같다)
        try:
            b = GB.GymBattleWindow(app, api.gym_start(region))
            TG.pump(root, lambda: not b.busy, 30)
            b.view["canMega"] = True
            b.view["gimmick"] = {"zMoves": [{"key": "FLAMETHROWER", "name": "다이내믹풀플레임", "power": 175}]}
            b.show_commands()
            root.update()
            bottom_row(b, "창 %dpx" % b.ww)
            b.close()
        finally:
            os.environ.pop("POKET_BATTLE_ZOOM", None)


def bottom_row(b, name):
    """기술 화면 맨 아랫줄: 알약 · '포켓몬' · '기권' 이 겹치지 않고, 단추 글씨가 단추 안에 든다."""
    from poketdesktop.skins.dp import kit
    w, h = b._lower_wh()
    sw, fw = b.switch_btn.box, b.forfeit_btn.box
    tbar_right = b.tbar.winfo_x() + b.tbar.winfo_reqwidth() if (b.mega.shown or b.gim.z.shown) else 0
    chk("%s: 알약 · 포켓몬 · 기권 이 겹치지 않는다" % name, tbar_right < sw[0] < sw[2] < fw[0] < fw[2] <= w,
        (tbar_right, sw, fw, w))
    for bt in (b.switch_btn, b.forfeit_btn):
        tw = kit.tkfont_of(b.bcv, bt.spec).measure(bt.text)
        th = kit.tkfont_of(b.bcv, bt.spec).metrics("linespace")
        chk("%s: '%s' 글씨가 단추 안에 든다" % (name, bt.text), tw + 16 <= bt.box[2] - bt.box[0]
            and th <= bt.box[3] - bt.box[1], (tw, th, bt.box))
    mv = b._move_btns[3]
    b.lower._motion(type("E", (), {"x": (mv.box[0] + mv.box[2]) // 2, "y": (mv.box[1] + mv.box[3]) // 2})())
    b.bcv.update_idletasks()
    corner = b.bcv.bbox(mv.tag)
    chk("%s: 올린 기술의 꺾쇠가 아랫줄 · 창 밖으로 안 나간다" % name, corner[3] - 1 <= sw[1] and corner[2] <= w + 1,
        (corner, sw, w))
    b.lower._leave(None)


def live(root, dex):
    import test_live_ui as TL
    from poketdesktop import ui_live_battle as LUI
    api = TL.FakeApi(dex)
    app = TL.FakeApp(root, api, dex)
    w = LUI.LiveBattleWindow(app, api.match())
    TL.pump(root, lambda: not w.busy and w._page == "moves", 30)
    chk("실시간 배틀은 DP", type(w).__module__.endswith("skins.dp.live_battle"), type(w).__module__)
    chk("실시간 창: 상대 체력 숫자는 숨긴다 (기본 창과 같다)", w.box["foe"].get("hp") is None
        and w.box["me"].get("hp") is not None)
    w.close()


def main():
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda e, v, tb: errors.append("%s: %s" % (e.__name__, v))
    root_dir = os.path.dirname(HERE)
    dex = P.Pokedex(json.load(open(os.path.join(root_dir, "server", "data", "pokedex.json"), encoding="utf-8")))
    gym(root, dex)
    live(root, dex)
    chk("그리는 중 예외가 없다", not errors, errors[:3])
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    try:
        root.destroy()
    except tk.TclError:
        pass
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
