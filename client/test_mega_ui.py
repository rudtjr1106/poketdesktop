# -*- coding: utf-8 -*-
"""배틀 창의 메가진화 단추 검사 (시즌 3).

    python client/test_mega_ui.py
    python client/run_as_windows.py client/test_mega_ui.py

**창을 진짜로 띄운다.** 가짜 api 는 관장·실시간·레이드 검사의 것을 그대로
빌려 쓴다 - 판은 서버와 같은 엔진이 이 프로세스에서 돈다.

## 무엇을 못 박나

  1. 키스톤과 맞는 스톤이 있을 때만 단추가 뜬다. 없으면 아예 안 보인다.
  2. **단추는 메시지 막대에 붙는다.** 명령 칸 오른쪽 기둥(기술 설명 자리)을
     줄이지 않는다. 막대 안에 들어오고, 눌린 위젯이 없다.
  3. 기본은 꺼짐. 켜고 기술을 쓰면 mega=True 가 **그 기술과 함께** 간다.
     안 켜면 False.
  4. 교체 화면으로 가면 숨고 꺼진다.
  5. 메가진화 사건이 오면 도트(번호)와 이름이 메가 폼으로 바뀐다.
  6. 한 번 쓰면 단추가 다시 안 뜬다 (한 판 한 번).
  7. 실시간·레이드 창도 같다.
"""
import json
import os
import random
import sys
import tempfile

os.environ.setdefault("POKET_HOME", os.path.join(tempfile.gettempdir(), "poket-test-mega"))

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
from poketdesktop import ui_gym_battle as GB                # noqa: E402
from poketdesktop import ui_live_battle as LUI              # noqa: E402
from poketdesktop import ui_mega                            # noqa: E402
from poketdesktop import ui_raid_battle as RUI              # noqa: E402
from test_learn_dialog import squeezed                      # noqa: E402

OK = FAIL = 0
DATA = os.path.join(ROOT, "server", "data")
MEGA_X = 10034                  # 메가리자몽X


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def btn_ok(win, mega):
    """단추가 보이고, 메시지 막대 안에 온전히 들어와 있나."""
    h = mega.btn.holder
    if not (mega.shown and h.winfo_ismapped()):
        return False, "안 보임"
    bar = h.master
    x, w = h.winfo_x(), h.winfo_width()
    return (x >= 0 and x + w <= bar.winfo_width() and h.winfo_height() <= bar.winfo_height()
            and w >= h.winfo_reqwidth()), (x, w, bar.winfo_width(), h.winfo_reqwidth())


def gym_part(root, dex, gyms, kmap):
    print("=== 관장 배틀 창 ===")
    moves = ["FLAMETHROWER", "DRAGONCLAW", "AIRSLASH", "ROOST"]
    liz = TG.mon(dex, "CHARIZARD", 100, moves, "BLAZE", 21)
    liz["held"] = "CHARIZARDITEX"
    party = [liz, TG.mon(dex, "GARCHOMP", 100, ["EARTHQUAKE"], "ROUGHSKIN", 22)]
    api = TG.FakeApi(dex, gyms, kmap, party)
    app = TG.FakeApp(root, api, dex)
    low = min((t for t in gyms["trainers"] if t["level"] < 60), key=lambda t: t["level"])

    def open_battle(keystone):
        api.region = low["region"]
        api.tb = TB.TrainerBattle(dex, [dict(m) for m in party], api.by_region[low["region"]],
                                  random.Random(7))
        api.tb.keystone["me"] = keystone
        b = GB.GymBattleWindow(app, api._out(api.tb.start()))
        TG.pump(root, lambda: not b.busy, 30)
        root.update()
        return b

    b = open_battle(False)
    chk("키스톤이 없으면 단추가 안 뜬다", not b.mega.shown and not b.mega.btn.holder.winfo_ismapped())
    b.use_move("FLAMETHROWER")
    TG.pump(root, lambda: not b.busy, 30)
    chk("  그때 보내는 값은 False", api.megas[-1:] == [False], api.megas)
    b.close()
    root.update()

    b = open_battle(True)
    ok, got = btn_ok(b.win, b.mega)
    chk("키스톤 + 리자몽나이트X -> 단추가 메시지 막대 안에 뜬다", ok, got)
    chk("  명령 칸 오른쪽 기둥에는 안 붙는다 (기술 설명 자리)",
        b.mega.btn.holder.master is b.msg.master, b.mega.btn.holder.master)
    chk("  메시지 글이 함께 보인다", "무엇을 할까" in b.msg.cget("text"), b.msg.cget("text"))
    chk("  눌린 위젯이 없다", not squeezed(b.win), squeezed(b.win)[:3])
    chk("기본은 꺼짐", not b.mega.on)
    b.mega.toggle()
    chk("누르면 켜지고 색이 바뀐다", b.mega.on and b.mega.btn.box.cget("bg") == ui_mega.ON_FILL,
        b.mega.btn.box.cget("bg"))
    b.open_switch()
    root.update()
    chk("교체 화면에서는 숨고 꺼진다", not b.mega.shown and not b.mega.on
        and not b.mega.btn.holder.winfo_ismapped())
    b.show_commands()
    root.update()
    chk("기술 화면으로 돌아오면 다시 뜬다 (꺼진 채)", b.mega.shown and not b.mega.on)

    seen = []
    orig = b._mega
    b._mega = lambda ev: (seen.append(dict(ev)), orig(ev))
    b.mega.toggle()
    b.use_move("FLAMETHROWER")
    chk("보내면 단추가 바로 꺼진다", not b.mega.on)
    TG.pump(root, lambda: not b.busy, 30)
    root.update()
    chk("켜고 쓰면 mega=True 가 기술과 함께 간다", api.megas[-1:] == [True], api.megas)
    chk("메가진화 사건을 재생한다", seen and seen[0].get("who") == "me"
        and seen[0].get("num") == MEGA_X, seen[:1])
    me = b.shown.get("me") or {}
    chk("도트 번호가 메가 폼", me.get("num") == MEGA_X, me.get("num"))
    chk("이름이 메가리자몽X", me.get("name") == "메가리자몽X", me.get("name"))
    # 1.9.0: 메가진화하면 특성도 바뀐다 (맹화 -> 단단한발톱). 제보: 가디안이
    # 트레이스로 베낀 특성이 메가진화 뒤에도 칸에 그대로 남아 있었다.
    claws = dex.ability_name("TOUGHCLAWS")
    chk("메가 사건에 새 특성이 실려 온다", seen[0].get("abilityKr") == claws, seen[0].get("abilityKr"))
    chk("특성 칸이 메가 폼의 특성으로 바뀐다", me.get("abilityKr") == claws
        and b.cv.itemcget(b.box["me"]["ability"], "text") == claws,
        (me.get("abilityKr"), b.cv.itemcget(b.box["me"]["ability"], "text")))
    chk("한 번 쓰면 단추가 다시 안 뜬다", not b.mega.shown and b.view.get("megaUsed"),
        (b.mega.shown, b.view.get("megaUsed")))
    b.close()
    root.update()


def live_part(root, dex):
    print("\n=== 실시간 배틀 창 ===")
    api = TL.FakeApi(dex)
    liz = TL.mon(dex, "CHARIZARD", ["FLAMETHROWER", "DRAGONCLAW"], 1)
    liz["held"] = "CHARIZARDITEX"
    a = [liz, TL.mon(dex, "PIKACHU", ["THUNDERBOLT"], 2)]
    b = [TL.mon(dex, "SNORLAX", ["TACKLE"], 3), TL.mon(dex, "BLASTOISE", ["SURF"], 4)]
    api.lb = LB.LiveBattle(dex, (1, "나", a), (2, "상대", b), rng=random.Random(4))
    api.lb.keystone["me"] = True                    # 자리 a 가 me
    api.events = api.lb.start()
    app = TL.FakeApp(root, api, dex)
    w = LUI.LiveBattleWindow(app, api.match())
    TL.pump(root, lambda: not w.busy, 25)
    TL.rest(root, 0.3)
    ok, got = btn_ok(w.win, w.mega)
    chk("단추가 메시지 막대 안에 뜬다", ok, got)
    chk("  눌린 위젯이 없다", not squeezed(w.win), squeezed(w.win)[:3])
    w.mega.toggle()
    w.use_move("FLAMETHROWER")
    TL.pump(root, lambda: (w.shown.get("me") or {}).get("num") == MEGA_X and not w.busy, 25)
    me = w.shown.get("me") or {}
    chk("메가진화하면 도트·이름이 바뀐다", me.get("num") == MEGA_X
        and me.get("name") == "메가리자몽X", (me.get("num"), me.get("name")))
    TL.rest(root, 0.3)
    chk("한 번 쓰면 단추가 다시 안 뜬다", not w.mega.shown)
    w.close()
    root.update()


def raid_part(root, dex):
    print("\n=== 레이드 배틀 창 ===")
    api = TR.FakeApi(dex, n=3, revealed=True)
    players = []
    for i in range(3):
        lead = RB.leveled(TR.mon(dex, "CHARIZARD" if i == 0 else "SNORLAX", 50,
                                 ["FLAMETHROWER", "DRAGONCLAW"] if i == 0 else ["TACKLE"],
                                 100 + i), 50)
        if i == 0:
            lead["held"] = "CHARIZARDITEX"
        players.append((i + 1, "참가자%d" % (i + 1),
                        [lead, RB.leveled(TR.mon(dex, "PIKACHU", 50, ["THUNDERBOLT"], 200 + i), 50)]))
    boss = TR.mon(dex, "MEWTWO", 60, ["PSYCHIC", "SHADOWBALL", "AURASPHERE", "RECOVER"], 1)
    api.rb = RB.RaidBattle(dex, boss, players, hp_mult=40, max_rounds=15, rng=random.Random(5))
    p0 = api.rb.players[0]
    p0.keystone = True                               # 서버(raid.begin)가 하는 것과 같다
    p0.bt.keystone["me"] = True
    api.events = api.rb.start()
    api.round = 0
    api.state = "fighting"
    app = TR.FakeApp(root, api, dex)
    bw = RUI.RaidBattleWindow(app, api.room())
    TR.pump(root, lambda: not bw.busy, 25)
    TR.rest(root, 0.3)
    ok, got = btn_ok(bw.win, bw.mega)
    chk("단추가 메시지 막대 안에 뜬다", ok, got)
    chk("  눌린 위젯이 없다", not squeezed(bw.win), squeezed(bw.win)[:3])
    bw.mega.toggle()
    bw.use_move("FLAMETHROWER")
    TR.pump(root, lambda: (bw.shown.get(0) or {}).get("num") == MEGA_X and not bw.busy, 25)
    me = bw.shown.get(0) or {}
    chk("메가진화하면 내 칸의 도트·이름이 바뀐다", me.get("num") == MEGA_X
        and me.get("name") == "메가리자몽X", (me.get("num"), me.get("name")))
    TR.rest(root, 0.3)
    chk("한 번 쓰면 단추가 다시 안 뜬다", not bw.mega.shown)
    other = bw.shown.get(1) or {}
    chk("다른 사람 칸은 그대로", other.get("num") == 143, other.get("num"))
    bw.close()
    root.update()


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
        errors.append("".join(traceback.format_exception(exc, val, tb))[-300:])
    root.report_callback_exception = on_err
    print("글꼴 %s / 본문 %dpt (BASE_PT=%d)" % (U.FAMILY, U.FONT[1], U.BASE_PT))
    # 연출 대기를 1/10 로
    orig_later = GB.GymBattleWindow.later
    GB.GymBattleWindow.later = lambda self, ms, fn: orig_later(self, max(1, ms // 10), fn)

    gym_part(root, dex, gyms, kmap)
    live_part(root, dex)
    raid_part(root, dex)

    TG.pump(root, lambda: False, 1.0)
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
