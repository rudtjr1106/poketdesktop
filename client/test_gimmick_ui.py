# -*- coding: utf-8 -*-
"""배틀 창의 테라스탈 (2.5.0) · Z기술 (시즌 4) 단추 검사.

    python client/test_gimmick_ui.py
    python client/run_as_windows.py client/test_gimmick_ui.py

**창을 진짜로 띄운다.** 가짜 api 는 관장·실시간·레이드 검사의 것을 빌려 쓴다 (테라스탈·Z기술
값을 엔진에 넘기는 것만 얹었다) - 판은 서버와 같은 엔진이 이 프로세스에서 돈다.

## 무엇을 못 박나

  1. Z링·테라오브가 있을 때만 단추가 뜬다. 없으면 아예 안 보이고, 보내는 요청도 예전과 같다.
  2. 단추는 메시지 막대에 메가진화 단추와 나란히 선다. 막대 안에 들어오고 눌린 위젯이 없다.
  3. 테라스탈 단추에는 될 타입이 적힌다.
  4. Z기술을 켜면 기술 칸이 바뀐다 - 되는 기술은 Z기술의 이름·위력으로 보인다.
  5. 켜고 기술을 쓰면 그 값이 **그 기술과 함께** 간다. 한 번 보내면 꺼진다.
     Z기술을 켜고 안 되는 기술을 고르면 그 기술이 보통으로 나간다 (Z파워는 안 닳는다).
  6. 사건이 오면 타입 표시가 테라 타입으로 바뀌고 이름표에 '테라 ○○' 가 붙는다. 쓰고 나면 단추가 다시 안 뜬다.
  7. 실시간·레이드 창도 같다.
"""
import json
import os
import random
import sys
import tempfile

os.environ.setdefault("POKET_HOME", os.path.join(tempfile.gettempdir(), "poket-test-gimmick"))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

import test_gym_ui as TG                                    # noqa: E402
import test_live_ui as TL                                   # noqa: E402
import test_raid_ui as TR                                   # noqa: E402
from common import live_battle as LB                        # noqa: E402
from common import pokelogic as P                           # noqa: E402
from common import raid_battle as RB                        # noqa: E402
from common import trainer_battle as TB                     # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_gimmick                         # noqa: E402
from poketdesktop import ui_gym_battle as GB                # noqa: E402
from poketdesktop import ui_live_battle as LUI              # noqa: E402
from poketdesktop import ui_raid_battle as RUI              # noqa: E402
from test_learn_dialog import squeezed                      # noqa: E402
from common import battle as BATTLE                         # noqa: E402

# 2.5.1: 테라 타입 = 지닌 테라피스 (지니는 도구) 라 한 마리가 Z크리스탈과 테라피스를 같이 못 지닌다. 이 검사는 단추
# 막대(두 단추가 겹치지 않나 · 순서 · 함께 보내기)를 보려고, 시험용 포켓몬에 적어 둔 tera 를 테라 타입으로 쓰게 한다.
# 엔진의 규칙(지닌 테라피스만)은 common/test_tera · test_live_battle · server/test_gimmick 이 본다.
_REAL_TERA_TYPE = BATTLE.Fighter.tera_type


def _test_tera_type(self):
    return _REAL_TERA_TYPE(self) or (None if self.item_gone else self.mon.get("tera"))


BATTLE.Fighter.tera_type = _test_tera_type

OK = FAIL = 0
DATA = os.path.join(ROOT, "server", "data")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class GymApi(TG.FakeApi):
    """관장 검사의 가짜 api + 테라스탈·Z기술. 받은 요청을 그대로 적어 둔다."""

    def gym_act(self, bid, kind, move="", slot=-1, mega=False, **kw):
        self.megas.append(bool(mega))
        self.sent = getattr(self, "sent", []) + [dict(kw, move=move)]
        if kind == "move":
            ev = self.tb.act("move", move, mega=mega, tera=bool(kw.get("tera")), z=bool(kw.get("z")))
        else:
            ev = self.tb.act(kind, slot) if kind != "forfeit" else self.tb.act("forfeit")
        return self._out(ev, {})


class LiveApi(TL.FakeApi):
    def live_act(self, kind, move="", slot=-1, mega=False, **kw):
        self.sent = getattr(self, "sent", []) + [dict(kw, move=move)]
        value = move if kind == "move" else (slot if kind == "switch" else None)
        self.lb.choose("a", kind, value, mega=mega, tera=bool(kw.get("tera")), z=bool(kw.get("z")))
        if self.auto_foe and self.lb.can_act("b"):
            self.lb.choose("b", *self.lb.auto_choice("b"))
        if self.lb.ready():
            self.events = self.lb.resolve()
            self.turn = self.lb.turn
            if self.lb.over:
                self.state = "done"
        return self.match()


class RaidApi(TR.FakeApi):
    def raid_act(self, kind, move="", slot=-1, mega=False, **kw):
        self.sent = getattr(self, "sent", []) + [dict(kw, move=move)]
        self.rb.choose(0, kind, move if kind == "move" else slot, mega=mega,
                       tera=bool(kw.get("tera")), z=bool(kw.get("z")))
        for i in range(1, len(self.rb.players)):
            if self.rb.players[i].playing():
                self.rb.choose(i, *self.rb.auto_choice(i))
        self.events = self.rb.resolve()
        self.round = self.rb.round
        if self.rb.over:
            self.state = "done"
        return self.room()


def in_bar(toggle):
    """단추가 보이고, 메시지 막대 안에 온전히 들어와 있나."""
    h = toggle.btn.holder
    if not (toggle.shown and h.winfo_ismapped()):
        return False, "안 보임"
    bar = h.master
    x, w = h.winfo_x(), h.winfo_width()
    return (x >= 0 and x + w <= bar.winfo_width() and h.winfo_height() <= bar.winfo_height()
            and w >= h.winfo_reqwidth()), (x, w, bar.winfo_width(), h.winfo_reqwidth())


def cell_names(win):
    """기술 칸에 적힌 굵은 이름들 (왼쪽 위부터)."""
    out = []

    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Label):
                f = str(c.cget("font"))
                if "bold" in f and c.master.master.master is not None and c.cget("anchor") == "w":
                    out.append(c.cget("text"))
            walk(c)
    walk(win.left)
    return out


def apart(a, b):
    """두 단추가 겹치지 않나."""
    ha, hb = a.btn.holder, b.btn.holder
    return (ha.winfo_x() + ha.winfo_width() <= hb.winfo_x()
            or hb.winfo_x() + hb.winfo_width() <= ha.winfo_x())


def gym_part(root, dex, gyms, kmap):
    print("=== 관장 배틀 창 ===")
    liz = TG.mon(dex, "CHARIZARD", 100, ["FLAMETHROWER", "DRAGONCLAW", "AIRSLASH", "SUNNYDAY"], "BLAZE", 21)
    liz["held"] = "FIRIUMZ"
    liz["tera"] = "GRASS"
    party = [liz, TG.mon(dex, "GARCHOMP", 100, ["EARTHQUAKE"], "ROUGHSKIN", 22)]
    api = GymApi(dex, gyms, kmap, party)
    app = TG.FakeApp(root, api, dex)
    low = min((t for t in gyms["trainers"] if t["level"] < 60), key=lambda t: t["level"])

    def open_battle(have):
        api.region = low["region"]
        api.tb = TB.TrainerBattle(dex, [dict(m) for m in party], api.by_region[low["region"]],
                                  random.Random(7))
        api.tb.zring["me"] = api.tb.tera_orb["me"] = have
        b = GB.GymBattleWindow(app, api._out(api.tb.start()))
        TG.pump(root, lambda: not b.busy, 30)
        root.update()
        return b

    b = open_battle(False)
    chk("Z링·테라오브가 없으면 단추가 안 뜬다", not b.gim.tera.shown and not b.gim.z.shown
        and not b.gim.tera.btn.holder.winfo_ismapped() and not b.gim.z.btn.holder.winfo_ismapped())
    b.use_move("FLAMETHROWER")
    TG.pump(root, lambda: not b.busy, 30)
    chk("  그때 보내는 요청에는 테라·Z 칸이 아예 없다 (예전과 같다)",
        api.sent[-1] == {"move": "FLAMETHROWER"}, api.sent[-1])
    b.close()
    root.update()

    b = open_battle(True)
    for name, tg in (("테라스탈", b.gim.tera), ("Z기술", b.gim.z)):
        ok, got = in_bar(tg)
        chk("%s 단추가 메시지 막대 안에 뜬다" % name, ok, got)
    chk("  두 단추가 겹치지 않는다", apart(b.gim.tera, b.gim.z))
    chk("  메시지 글이 함께 보인다", "무엇을 할까" in b.msg.cget("text"), b.msg.cget("text"))
    chk("  눌린 위젯이 없다", not squeezed(b.win), squeezed(b.win)[:3])
    chk("테라스탈 단추에 될 타입이 적힌다", b.gim.tera.text == "테라스탈 · 풀", b.gim.tera.text)
    chk("기본은 둘 다 꺼짐", not b.gim.tera.on and not b.gim.z.on)
    before = cell_names(b)
    chk("끄면 기술 칸은 원래 이름", "화염방사" in before and "다이내믹풀플레임" not in before, before)

    b.gim.z.toggle()
    root.update()
    after = cell_names(b)
    chk("Z기술을 켜면 되는 기술이 Z기술 이름으로 바뀐다", "다이내믹풀플레임" in after and "화염방사" not in after,
        after)
    chk("  변화기는 Z + 원래 이름", "Z쾌청" in after, after)
    chk("  안 되는 기술은 그대로다", "드래곤클로" in after and "에어슬래시" in after, after)
    chk("  켠 색으로 바뀐다", b.gim.z.on and b.gim.z.btn.box.cget("bg") == ui_gimmick.Z_ON[0],
        b.gim.z.btn.box.cget("bg"))
    z = b.gim.decorate({"key": "FLAMETHROWER", "kr": "화염방사", "power": 90, "acc": 100})
    chk("  칸에 그릴 값: 위력 175, 반드시 명중", z["power"] == 175 and z["acc"] == 0 and z.get("z"), z)
    chk("  눌린 위젯이 없다 (다시 그린 뒤)", not squeezed(b.win), squeezed(b.win)[:3])
    b.gim.z.toggle()
    root.update()
    chk("다시 끄면 원래 이름으로 돌아온다", "화염방사" in cell_names(b), cell_names(b))

    b.gim.tera.toggle()
    b.gim.z.toggle()
    b.open_switch()
    root.update()
    chk("교체 화면에서는 숨고 꺼진다", not b.gim.tera.shown and not b.gim.z.shown
        and not b.gim.tera.on and not b.gim.z.on)
    b.show_commands()
    root.update()
    chk("기술 화면으로 돌아오면 다시 뜬다 (꺼진 채)", b.gim.tera.shown and b.gim.z.shown
        and not b.gim.tera.on and not b.gim.z.on)

    # Z기술을 켜고 안 되는 기술을 고르면 그 기술이 보통으로 나간다
    b.gim.z.toggle()
    b.use_move("DRAGONCLAW")
    TG.pump(root, lambda: not b.busy, 30)
    root.update()
    chk("Z를 켜고 안 되는 기술을 고르면 Z를 안 싣는다", api.sent[-1] == {"move": "DRAGONCLAW"}, api.sent[-1])
    chk("  Z파워가 안 닳아 단추가 다시 뜬다", b.gim.z.shown and not b.view["gimmick"]["zUsed"])

    seen = []
    orig = b._apply
    b._apply = lambda ev: (seen.append(ev.get("t")), orig(ev))[1]
    b.gim.tera.toggle()
    b.gim.z.toggle()
    b.use_move("FLAMETHROWER")
    chk("보내면 단추가 바로 꺼진다", not b.gim.tera.on and not b.gim.z.on)
    TG.pump(root, lambda: not b.busy, 40)
    root.update()
    chk("켜고 쓰면 tera·z 가 기술과 함께 간다",
        api.sent[-1] == {"move": "FLAMETHROWER", "tera": True, "z": True}, api.sent[-1])
    chk("테라스탈·Z파워 사건을 재생한다 (테라스탈이 먼저)", "tera" in seen and "zpower" in seen
        and seen.index("tera") < seen.index("zpower"), seen)
    me = b.shown.get("me") or {}
    chk("타입 표시가 테라 타입 하나로 바뀐다", me.get("tera") == "GRASS" and me.get("typeIds") == ["GRASS"],
        (me.get("tera"), me.get("typeIds")))
    st = b.cv.itemcget(b.box["me"]["status"], "text")
    chk("이름표 상태 줄에 '테라 풀' 이 붙는다", st.startswith("테라 풀"), st)
    chk("쓰고 나면 단추가 다시 안 뜬다", not b.gim.tera.shown and not b.gim.z.shown
        and b.view["gimmick"]["teraUsed"] and b.view["gimmick"]["zUsed"], b.view.get("gimmick"))
    # 연출은 판이 끝난 뒤에도 잠깐 돈다 - 느린 PC(CI 윈도우)에서는 그 끝을 기다린다
    TG.pump(root, lambda: all(e.dead for e in b.effects), 5)
    chk("연출이 남기고 간 것이 없다", all(e.dead for e in b.effects), [type(e).__name__ for e in b.effects])
    b.close()
    root.update()


def live_part(root, dex):
    print("\n=== 실시간 배틀 창 ===")
    api = LiveApi(dex)
    liz = TL.mon(dex, "CHARIZARD", ["FLAMETHROWER", "DRAGONCLAW"], 1)
    liz["held"] = "FIRIUMZ"
    liz["tera"] = "GRASS"
    a = [liz, TL.mon(dex, "PIKACHU", ["THUNDERBOLT"], 2)]
    b = [TL.mon(dex, "SNORLAX", ["TACKLE"], 3), TL.mon(dex, "BLASTOISE", ["SURF"], 4)]
    api.lb = LB.LiveBattle(dex, (1, "나", a), (2, "상대", b), rng=random.Random(4))
    api.lb.zring["me"] = api.lb.tera_orb["me"] = True         # 자리 a 가 me
    api.events = api.lb.start()
    app = TL.FakeApp(root, api, dex)
    w = LUI.LiveBattleWindow(app, api.match())
    TL.pump(root, lambda: not w.busy, 25)
    TL.rest(root, 0.3)
    for name, tg in (("테라스탈", w.gim.tera), ("Z기술", w.gim.z)):
        ok, got = in_bar(tg)
        chk("%s 단추가 메시지 막대 안에 뜬다" % name, ok, got)
    chk("  눌린 위젯이 없다", not squeezed(w.win), squeezed(w.win)[:3])
    w.gim.z.toggle()
    root.update()
    chk("Z기술을 켜면 기술 칸이 바뀐다", "다이내믹풀플레임" in cell_names(w), cell_names(w))
    w.gim.tera.toggle()
    w.use_move("FLAMETHROWER")
    TL.pump(root, lambda: (w.shown.get("me") or {}).get("tera") == "GRASS" and not w.busy, 25)
    chk("tera·z 가 기술과 함께 간다", api.sent[-1] == {"move": "FLAMETHROWER", "tera": True, "z": True},
        api.sent[-1])
    me = w.shown.get("me") or {}
    chk("테라스탈하면 타입 표시가 바뀐다", me.get("tera") == "GRASS" and me.get("typeIds") == ["GRASS"],
        (me.get("tera"), me.get("typeIds")))
    TL.rest(root, 0.3)
    chk("쓰고 나면 단추가 다시 안 뜬다", not w.gim.tera.shown and not w.gim.z.shown)
    w.close()
    root.update()


def raid_part(root, dex):
    print("\n=== 레이드 배틀 창 ===")
    api = RaidApi(dex, n=3, revealed=True)
    players = []
    for i in range(3):
        lead = RB.leveled(TR.mon(dex, "CHARIZARD" if i == 0 else "SNORLAX", 50,
                                 ["FLAMETHROWER", "DRAGONCLAW"] if i == 0 else ["TACKLE"],
                                 100 + i), 50)
        if i == 0:
            lead["held"] = "FIRIUMZ"
            lead["tera"] = "GRASS"
        players.append((i + 1, "참가자%d" % (i + 1),
                        [lead, RB.leveled(TR.mon(dex, "PIKACHU", 50, ["THUNDERBOLT"], 200 + i), 50)]))
    boss = TR.mon(dex, "MEWTWO", 60, ["PSYCHIC", "SHADOWBALL", "AURASPHERE", "RECOVER"], 1)
    api.rb = RB.RaidBattle(dex, boss, players, hp_mult=40, max_rounds=15, rng=random.Random(5))
    p0 = api.rb.players[0]
    p0.zring["me"] = p0.tera_orb["me"] = True          # 서버(raid.begin)가 하는 것과 같다
    api.events = api.rb.start()
    api.round = 0
    api.state = "fighting"
    app = TR.FakeApp(root, api, dex)
    bw = RUI.RaidBattleWindow(app, api.room())
    TR.pump(root, lambda: not bw.busy, 25)
    TR.rest(root, 0.3)
    for name, tg in (("테라스탈", bw.gim.tera), ("Z기술", bw.gim.z)):
        ok, got = in_bar(tg)
        chk("%s 단추가 메시지 막대 안에 뜬다" % name, ok, got)
    chk("  눌린 위젯이 없다", not squeezed(bw.win), squeezed(bw.win)[:3])
    bw.gim.tera.toggle()
    bw.gim.z.toggle()
    root.update()
    chk("Z기술을 켜면 기술 칸이 바뀐다", "다이내믹풀플레임" in cell_names(bw), cell_names(bw))
    bw.use_move("FLAMETHROWER")
    TR.pump(root, lambda: (bw.shown.get(0) or {}).get("tera") == "GRASS" and not bw.busy, 25)
    chk("tera·z 가 기술과 함께 간다", api.sent[-1] == {"move": "FLAMETHROWER", "tera": True, "z": True},
        api.sent[-1])
    me = bw.shown.get(0) or {}
    chk("테라스탈하면 내 칸의 타입 표시가 바뀐다", me.get("tera") == "GRASS", me.get("tera"))
    TR.rest(root, 0.3)
    chk("쓰고 나면 단추가 다시 안 뜬다", not bw.gim.tera.shown and not bw.gim.z.shown)
    other = bw.shown.get(1) or {}
    chk("다른 사람 칸은 그대로", not other.get("tera"), other.get("tera"))
    bw.close()
    root.update()


def helper_part():
    print("\n=== 거들기 ===")
    chk("요청에는 켠 것만 싣는다", ui_gimmick.act_kwargs(False, False) == {"mega": False}
        and ui_gimmick.act_kwargs(True, False, True) == {"mega": True, "tera": True}
        and ui_gimmick.act_kwargs(False, True, True) == {"mega": False, "tera": True, "z": True})
    chk("이름표 글: 테라스탈했으면 '테라 ○○'", ui_gimmick.tera_tag({"teraKr": "풀"}) == "테라 풀"
        and ui_gimmick.tera_tag({}) == "" and ui_gimmick.tera_tag(None) == "")
    wide = lambda s: len(s) * 10                       # noqa: E731 - 글자 하나 10px 로 잰다
    chk("좁은 단추는 ' · ' 에서 줄을 바꾸고, 넉넉하면 그대로 (글자는 안 줄인다)",
        ui_gimmick.fit_lines("테라스탈 · 에스퍼", wide, 60) == "테라스탈\n에스퍼"
        and ui_gimmick.fit_lines("테라스탈 · 에스퍼", wide, 200) == "테라스탈 · 에스퍼"
        and ui_gimmick.fit_lines("메가진화", wide, 10) == "메가진화")

    print("\n=== 결정 모습 (테라스탈한 도트) ===")
    from PIL import Image, ImageDraw
    from poketdesktop import tera_fx
    frames = []
    for k in range(6):                                   # 가로 40 x 세로 60, 아래쪽에 몸 (발이 맨 아래 줄)
        im = Image.new("RGBA", (40, 60), (0, 0, 0, 0))
        ImageDraw.Draw(im).ellipse((8, 18 + (k % 2), 32, 59), fill=(220, 120, 40, 255))
        frames.append(im)
    out = ui_gimmick.tera_look(frames, "GRASS")
    room = out[0].height - 60
    chk("위쪽만 늘린다 (폭 그대로, 왕관 자리)", len(out) == 6 and out[0].width == 40 and room >= 12,
        (len(out), out[0].size))
    a_out, a_in = out[0].getchannel("A"), frames[0].getchannel("A")
    chk("  발 자리(맨 아래 줄)가 그대로 - 창의 도트는 발에 맞춰 선다",
        a_out.getbbox()[3] == out[0].height and a_in.getbbox()[3] == 60
        and a_out.getpixel((20, out[0].height - 1)) == 255 and a_in.getpixel((20, 59)) == 255,
        (a_out.getbbox(), a_in.getbbox()))
    top = out[0].getchannel("A").crop((0, 0, 40, room + 17)).getbbox()
    chk("  몸 위에 왕관이 있다", top is not None and top[3] <= room + 17, top)
    px = out[0].convert("RGB").getpixel((20, room + 45))
    chk("  몸은 그 타입 빛깔로 (풀: 초록이 빨강보다 짙다)", px[1] > px[0], px)
    chk("  테라스탈 안 했으면 그대로", ui_gimmick.tera_look(frames, None) is frames)
    chk("  그림이 이상하면 원래 프레임 그대로 (판을 막지 않는다)", tera_fx.crystal_frames(["x"], "#00ff00") == ["x"])
    sweeps = [tera_fx._sweep(40, 60, k, 10) is not None for k in range(10)]
    chk("  빛줄기는 한 바퀴의 앞쪽에만 스친다 (나머지는 쉰다)", any(sweeps) and not all(sweeps) and sweeps[0]
        and not sweeps[-1], sweeps)

    print("\n=== 가방 · 상점 · 상자: 테라피스 (2.5.1 - 지니는 도구) ===")
    from poketdesktop import ui_bag, ui_box, ui_shop
    from common import held as HELD
    shard = {"id": "WATERTERASHARD", "kr": "테라피스 물", "cat": "held", "teraType": "WATER",
             "desc": "테라스탈의 힘이 깃든 결정 조각. 지니게 하면 테라스탈할 때 물 타입이 된다.",
             "effect": {"kind": "held"}, "holdable": True, "heldNote": HELD.effect_note("WATERTERASHARD")}
    chk("지닌 도구로 다룬다 (따로 쓰는 길 'tera' 는 없다)", "held" in ui_bag.USABLE and "tera" not in ui_bag.USABLE)
    chk("  가방 설명에 하는 일이 붙는다", "테라스탈" in ui_bag.item_desc(shard), ui_bag.item_desc(shard))
    chk("  대상 안내는 지니게 하기", ui_bag.target_hint(shard) == ui_bag.target_hint({"effect": {"kind": "held"}}),
        ui_bag.target_hint(shard))
    chk("  지닌 도구 묶음 '테라피스'", HELD.group("WATERTERASHARD") == "tera" and HELD.group_kr("tera") == "테라피스")
    chk("상자 '테라' 칸 설명: 지닌 것 / 안 지닌 것 / 옛 서버",
        "지닌 테라피스" in ui_box.tera_note({"teraKr": "물", "teraSet": True})
        and "테라스탈하지 못한다" in ui_box.tera_note({"teraKr": "없음", "teraSet": False})
        and "새 판" in ui_box.tera_note({}))
    chk("상자 '테라' 칸 값: 지닌 것 '물 타입' / 안 지닌 것 '없음' / 옛 서버 '?'",
        ui_box.tera_label({"teraKr": "물", "teraSet": True}) == "물 타입"
        and ui_box.tera_label({"teraKr": "없음", "teraSet": False}) == "없음" and ui_box.tera_label({}) == "?")


def main():
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    with open(os.path.join(DATA, "gyms.json"), encoding="utf-8") as f:
        gyms = json.load(f)
    with open(os.path.join(DATA, "korea_map.json"), encoding="utf-8") as f:
        kmap = json.load(f)

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
    print("글꼴 %s / 본문 %dpt (BASE_PT=%d)" % (U.FAMILY, U.FONT[1], U.BASE_PT))
    # 연출 대기를 1/10 로
    orig_later = GB.GymBattleWindow.later
    GB.GymBattleWindow.later = lambda self, ms, fn: orig_later(self, max(1, ms // 10), fn)

    helper_part()
    gym_part(root, dex, gyms, kmap)
    live_part(root, dex)
    raid_part(root, dex)

    TG.pump(root, lambda: False, 1.0)
    chk("Tk 콜백에서 난 오류가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
