# -*- coding: utf-8 -*-
"""바탕화면을 메가진화한 모습으로 걷기 + 메가진화 연출 검사 (1.8.0).

    python client/test_mega_walk.py
    python client/run_as_windows.py client/test_mega_walk.py

**창을 진짜로 띄운다.** 도트는 서버 없이 여기서 그린다. 메가 폼은 몸통을
넓게 그려서, 갈아 입으면 도트의 **너비**가 달라진다 (높이는 설정의 목표
높이로 맞춰지므로 같다).

## 무엇을 못 박나

  1. 도감: 지닌 것으로 될 수 있는 메가 폼 (Pokedex.mega_for) 이 배틀의
     규칙(Fighter.mega_target)과 **모든 폼에서** 같다.
  2. 우클릭 메뉴 줄: 메가진화와 상관없는 종에는 없다. 키스톤이 없거나
     스톤을 안 지녔으면 회색으로 까닭을 알려 준다. 되면 '메가진화한
     모습으로 걷기', 켜져 있으면 '원래 모습으로 걷기'.
  3. 켜 둔 포켓몬에만 lookNum 이 붙고, 도트를 못 받았으면 떼어 낸다.
  4. 오버레이: lookNum 이 있으면 그 폼의 도트로 선다. 없으면 원래 도트로라도
     선다. 동기화로 lookNum 이 생기거나 없어지면 갈아 입힌다.
     **그냥 진화(num 이 바뀜)는 건드리지 않는다** - 진화 연출의 몫이다.
     연출 중·배틀 중(look_hold)인 도트도 건드리지 않는다.
  5. 켜기: 연출이 돌고 메가 폼이 된다. 설정에 적힌다. 발밑 가운데가 그대로다.
     끄기: 원래 모습으로, 설정에서 빠진다. 도트를 못 받으면 켠 것을 무른다.
  6. 바탕화면 배틀의 메가진화: 그 판 동안 메가 폼, 끝나면 되돌린다.
     이미 메가 폼으로 걷던 도트는 그대로 둔다. 도트가 없어도 판은 흘러간다.
  7. 배틀 창의 연출(MegaFx): 도트는 한 번만 바뀌고, 그 뒤에 끝났다고 알린다.
     끝나면 캔버스에 아무것도 안 남는다. 도중에 멈추면 다음으로 안 넘긴다.
"""
import os
import random
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-megawalk-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from PIL import Image                                       # noqa: E402

from common import battle as B                              # noqa: E402
from common import pokelogic as P                           # noqa: E402
from poketdesktop import config, evolve_fx, fx_layer        # noqa: E402
from poketdesktop import mega_fx, overlay, sprites          # noqa: E402
from poketdesktop import sprite_cache, ui_mega, walk_cache  # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop.app import App                            # noqa: E402

OK = FAIL = 0
HOME = os.environ["POKET_HOME"]
DEX = P.Pokedex.load(os.path.join(ROOT, "server", "data", "pokedex.json"))
LIZ, MEGA_X, MEGA_Y = 6, 10034, 10035
RAY, MEGA_RAY = 384, 10079


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def wait(root, cond, sec=8.0):
    end = time.time() + sec
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.01)
    return cond()


def settle(root, sec=0.15):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


# ---------------------------------------------------------------- 재료
def make_sheet(name, cell, color, wide=False):
    """걷는 도트 시트. 8방향 x 2칸. wide 면 몸통이 넓다 (메가 폼)."""
    path = os.path.join(HOME, name)
    im = Image.new("RGBA", (cell * 2, cell * 8), (0, 0, 0, 0))
    bw = cell - 6 if wide else cell // 3
    for row in range(8):
        for col in range(2):
            box = Image.new("RGBA", (bw, cell - 10), color)
            im.paste(box, (col * cell + (cell - bw) // 2, row * cell + 5))
    im.save(path)
    return path, {"ok": True, "frameW": cell, "frameH": cell, "durations": [8, 8]}


def make_dot(name, color):
    path = os.path.join(HOME, name)
    im = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    im.paste(Image.new("RGBA", (18, 24), color), (11, 8))
    im.save(path)
    return path


def mon(pid, species, held=None, moves=("TACKLE",), gender="M", name=None):
    sp = DEX.get(species)
    return {"id": pid, "num": sp["num"], "species": species, "shiny": False,
            "held": held, "moves": list(moves), "gender": gender, "level": 50,
            "info": {"name": name or sp["kr"], "species": sp["kr"], "level": 50,
                     "types": []}}


class MiniApp(object):
    """App 에서 메가 걷기에 얽힌 메서드만 빌려 쓴다 (진짜 코드를 그대로 돌린다)."""
    mega_ids = App.mega_ids
    mega_form = App.mega_form
    dress_megas = App.dress_megas
    undress_missing = staticmethod(App.undress_missing)
    mega_menu_row = App.mega_menu_row
    toggle_mega_walk = App.toggle_mega_walk
    float_over_pet = App.float_over_pet

    def __init__(self, root, ov):
        self.root = root
        self.overlay = ov
        self.api = object()
        self.dex = DEX
        self.settings = ov.settings if ov is not None else dict(config.DEFAULTS)
        self.keystone = True
        self.arena = None
        self.battle = None
        self.notes = []
        self.fetched = []

    def notify(self, m):
        self.notes.append(m)

    def _prefetch_anims(self, mons):
        self.fetched.append([overlay.look_num(m) for m in mons])


class Host(object):
    """바탕화면 배틀 한 판의 껍데기 (mega_fx.battle 이 만지는 것만)."""

    def __init__(self, app, layer):
        self.app = app
        self.root = app.root
        self.layer = layer
        self.closed = False
        self.said = []

    def after(self, ms, fn):
        return self.root.after(ms, fn)

    def float_over(self, pet, text, color):
        self.said.append(text)


# ---------------------------------------------------------------- 1. 도감
def dex_part():
    print("=== 도감: 될 수 있는 메가 폼 ===")
    bad = []
    for form in DEX.megas:
        base = DEX.get(form["megaOf"])
        m = P.make_pokemon(base, 50, random.Random(1), shiny_rate=10 ** 9)
        m["held"] = form.get("megaStone")
        m["moves"] = [form["megaMove"]] if form.get("megaMove") else ["TACKLE"]
        # 냐오닉스는 암수 메가가 다르다. 성별이 안 적힌 폼은 수컷 것이다.
        m["gender"] = form.get("megaGender") or "M"
        mine = DEX.mega_for(m)
        theirs = B.Fighter(DEX, m).mega_target()
        if mine is not form or theirs is not form:
            bad.append((form["internal"], mine and mine["internal"],
                        theirs and theirs["internal"]))
    chk("모든 폼(%d)에서 배틀의 규칙과 같다" % len(DEX.megas), not bad, bad[:3])
    chk("스톤이 없으면 None", DEX.mega_for(mon(1, "CHARIZARD")) is None)
    chk("남의 스톤이면 None", DEX.mega_for(mon(1, "CHARIZARD", "VENUSAURITE")) is None)
    chk("메가진화가 없는 종은 None", DEX.mega_for(mon(1, "PIKACHU", "CHARIZARDITEX")) is None)
    chk("리자몽나이트X -> 메가리자몽X",
        (DEX.mega_for(mon(1, "CHARIZARD", "CHARIZARDITEX")) or {}).get("num") == MEGA_X)
    chk("레쿠쟈는 화룡점정을 알면 된다",
        (DEX.mega_for(mon(1, "RAYQUAZA", None, ["DRAGONASCENT"])) or {}).get("num") == MEGA_RAY)
    walk = [m for m in DEX.megas if m.get("walk")]
    dot = [m for m in DEX.megas if m.get("dot")]
    # 1.9.0: 세 번째 출처(GBA 풍)로 19폼이 더 걷는다 (메가보만다·메가메타그로스 …)
    ow = [m for m in walk if str(m["walk"]).startswith("ow:")]
    # 1.9.1: 레전드 Z-A 의 메가 22폼은 쇼다운 사이트의 배틀 도트로 선다 (걷는 도트는 없다)
    chk("걷는 도트가 있는 폼 60 (그중 세 번째 출처 19), 배틀 도트가 있는 폼 79",
        (len(walk), len(ow), len(dot)) == (60, 19, 79), (len(walk), len(ow), len(dot)))
    neither = [m["internal"] for m in DEX.megas if not m.get("walk") and not m.get("dot")]
    chk("둘 다 없는 폼은 넷뿐 (히드런·냐오닉스 암수·마기아나)", sorted(neither) == sorted(
        ["HEATRAN_MEGA", "MEOWSTIC_MEGA", "MEOWSTIC_MEGA_F", "MAGEARNA_MEGA"]), neither)
    chk("메가 폼의 번호는 모두 10000 이상 (오버레이가 이걸로 가른다)",
        all(m["num"] >= overlay.MEGA_FROM for m in DEX.megas))


# ---------------------------------------------------------------- 2·3. 메뉴와 lookNum
class StubPet(object):
    def __init__(self, m, look=None):
        self.mon = m
        self.id = m["id"]
        self.look = look or m["num"]
        self.evolving = False


def menu_part(root):
    print("\n=== 우클릭 메뉴 줄 ===")
    app = MiniApp(root, None)
    app.settings = dict(config.DEFAULTS)
    liz = mon(1, "CHARIZARD", "CHARIZARDITEX")
    chk("메가진화가 없는 종에는 줄이 없다",
        app.mega_menu_row(StubPet(mon(2, "PIKACHU"))) is None)
    nodot = next(m for m in DEX.megas if not m.get("walk") and not m.get("dot"))
    chk("메가 폼의 도트가 없는 종에도 줄이 없다 (%s)" % nodot["megaOf"],
        app.mega_menu_row(StubPet(mon(3, nodot["megaOf"], nodot.get("megaStone")))) is None)
    app.keystone = False
    row = app.mega_menu_row(StubPet(liz))
    chk("키스톤이 없으면 회색으로 까닭을 알린다",
        row and row.get("enabled") is False and "키스톤" in row["text"], row)
    chk("  그때는 될 수 있는 폼도 없다", app.mega_form(liz) is None)
    app.keystone = True
    row = app.mega_menu_row(StubPet(mon(4, "CHARIZARD")))
    chk("스톤을 안 지녔으면 회색으로 까닭을 알린다",
        row and row.get("enabled") is False and "메가스톤" in row["text"], row)
    row = app.mega_menu_row(StubPet(liz))
    chk("되면 '메가진화한 모습으로 걷기'",
        row and row.get("enabled", True) and row["text"] == "메가진화한 모습으로 걷기"
        and callable(row.get("command")), row)
    app.settings["megaWalk"] = [1]
    row = app.mega_menu_row(StubPet(liz, MEGA_X))
    chk("켜져 있으면 '원래 모습으로 걷기'", row and row["text"] == "원래 모습으로 걷기", row)
    chk("배틀 도트만 있는 폼(메가리자몽Y)도 된다",
        (app.mega_form(mon(5, "CHARIZARD", "CHARIZARDITEY")) or {}).get("num") == MEGA_Y)

    print("\n=== 켜 둔 포켓몬에만 lookNum ===")
    app.settings["megaWalk"] = [1, "7", "이상한값"]
    chk("설정의 엉뚱한 값은 버린다", app.mega_ids() == [1, 7], app.mega_ids())
    a, b, c = liz, mon(2, "CHARIZARD", "CHARIZARDITEX"), mon(7, "CHARIZARD")
    c["lookNum"] = MEGA_X                       # 스톤을 뗀 뒤의 옛 값
    want = app.dress_megas([a, b, c])
    chk("켠 것에만 붙는다", a.get("lookNum") == MEGA_X and "lookNum" not in b, (a, b))
    chk("스톤을 떼면 켜져 있어도 안 붙는다 (옛 값도 지운다)", "lookNum" not in c, c)
    chk("받을 도트 목록을 준다", want == [(MEGA_X, False)], want)
    chk("num 은 그대로다 (겉모습만)", a["num"] == LIZ)
    chk("키스톤이 없으면 안 붙는다", app.dress_megas([dict(a)], False) == [])
    a["lookNum"] = MEGA_X
    app.undress_missing([a], {(MEGA_X, False): None}, {MEGA_X: (None, None)})
    chk("도트를 못 받았으면 떼어 낸다", "lookNum" not in a, a)
    a["lookNum"] = MEGA_X
    app.undress_missing([a], {(MEGA_X, False): "x.gif"}, {})
    chk("배틀 도트만 받아도 둔다", a.get("lookNum") == MEGA_X)
    app.undress_missing([a], {}, {MEGA_X: ("s.png", {"ok": True})})
    chk("걷는 도트만 받아도 둔다", a.get("lookNum") == MEGA_X)


# ---------------------------------------------------------------- 4. 오버레이
def feet(pet):
    return (round(pet.x + pet.fw / 2.0), round(pet.y + pet.fh))


def overlay_part(root, ov, paths, walks):
    print("\n=== 오버레이: 어떤 도트로 서나 ===")
    a = mon(1, "CHARIZARD", "CHARIZARDITEX")
    b = dict(mon(2, "CHARIZARD", "CHARIZARDITEX"), lookNum=MEGA_X)
    c = dict(mon(3, "CHARIZARD", "CHARIZARDITEY"), lookNum=MEGA_Y)
    d = dict(mon(4, "RAYQUAZA", None, ["DRAGONASCENT"]), lookNum=MEGA_RAY)   # 도트를 안 준다
    ov.sync([a, b, c, d], paths, walks)
    settle(root)
    pa, pb, pc, pd = (ov.pets[i] for i in (1, 2, 3, 4))
    chk("lookNum 이 없으면 원래 도트", pa.look == LIZ
        and isinstance(pa.anim, sprites.WalkAnimation), pa.look)
    chk("lookNum 이 있으면 메가 폼의 걷는 도트", pb.look == MEGA_X
        and isinstance(pb.anim, sprites.WalkAnimation) and pb.fw > pa.fw, (pb.look, pb.fw, pa.fw))
    chk("걷는 도트가 없는 폼은 배틀 도트로 선다", pc.look == MEGA_Y
        and not isinstance(pc.anim, sprites.WalkAnimation), (pc.look, type(pc.anim)))
    chk("메가 폼의 도트를 못 구하면 원래 모습으로라도 선다", pd.look == RAY, pd.look)
    chk("다른 동작(Idle)도 지금 입은 번호로 찾는다",
        walk_cache.sheet_key(pb.look, "Idle", False) == (MEGA_X, "Idle"))

    print("\n=== 동기화로 갈아 입기 ===")
    w_base = pa.fw
    x1, y1, x2, y2 = ov.area()
    pa.x, pa.y = (x1 + x2) // 2, (y1 + y2) // 2
    pa.place()
    before = feet(pa)
    ov.sync([dict(a, lookNum=MEGA_X), b, c, d], {})
    settle(root)
    chk("lookNum 이 생기면 메가 폼으로", pa.look == MEGA_X and pa.fw > w_base, (pa.look, pa.fw))
    chk("  발밑 가운데가 그대로다", abs(feet(pa)[0] - before[0]) <= 1
        and abs(feet(pa)[1] - before[1]) <= 1, (before, feet(pa)))
    chk("  같은 창을 그대로 쓴다 (새로 만들지 않는다)", ov.pets[1] is pa)
    ov.sync([a, b, c, d], {})
    settle(root)
    chk("lookNum 이 없어지면 원래 모습으로", pa.look == LIZ and pa.fw == w_base, (pa.look, pa.fw))

    pa.evolving = True
    ov.sync([dict(a, lookNum=MEGA_X), b, c, d], {})
    chk("연출 중인 도트는 건드리지 않는다", pa.look == LIZ)
    pa.evolving = False
    pb.look_hold = True
    ov.sync([a, dict(b, lookNum=None), c, d], {})
    chk("배틀에서 잠깐 변한 도트(look_hold)도 건드리지 않는다", pb.look == MEGA_X)
    pb.look_hold = False
    ov.sync([a, b, c, d], {})

    # 그냥 진화: num 이 바뀐다. 진화 연출이 갈아 끼우므로 sync 는 손대지 않는다.
    evolved = dict(a, num=RAY)
    ov.sync([evolved, b, c, d], {})
    chk("그냥 진화(num 이 바뀜)는 sync 가 갈아 입히지 않는다", pa.look == LIZ, pa.look)
    ov.sync([a, b, c, d], {})

    print("\n=== 크기를 바꿔도 (도트를 전부 다시 만든다) ===")
    ov.refresh_visuals()
    settle(root)
    chk("메가 폼으로 걷던 도트는 메가 폼으로 다시 선다", ov.pets[2].look == MEGA_X
        and ov.pets[1].look == LIZ, (ov.pets[2].look, ov.pets[1].look))
    return a


# ---------------------------------------------------------------- 5. 켜고 끄기
def toggle_part(root, ov, app, files, sheets):
    print("\n=== 켜기 (연출과 함께) ===")
    pet = ov.pets[1]
    x1, y1, x2, y2 = ov.area()
    pet.x, pet.y = (x1 + x2) // 2, (y1 + y2) // 2
    pet.place()
    pet.battling = False
    before, w_base = feet(pet), pet.fw
    app.settings["megaWalk"] = []
    row = app.mega_menu_row(pet)
    chk("메뉴에 '메가진화한 모습으로 걷기'", row and row["text"] == "메가진화한 모습으로 걷기", row)
    row["command"]()
    chk("바로 설정에 적힌다", app.mega_ids() == [1], app.mega_ids())
    chk("  파일에도 남는다", config.load_settings().get("megaWalk") == [1],
        config.load_settings().get("megaWalk"))
    chk("연출이 돈다 (그동안 다시 못 누른다)", pet.evolving is True)
    app.toggle_mega_walk(pet)
    chk("  겹쳐 눌러도 설정이 뒤집히지 않는다", app.mega_ids() == [1])
    chk("메가 폼이 된다", wait(root, lambda: pet.look == MEGA_X), pet.look)
    chk("  도트가 넓어졌다 (메가 폼의 몸통)", pet.fw > w_base, (pet.fw, w_base))
    chk("  발밑 가운데가 그대로다", abs(feet(pet)[0] - before[0]) <= 1
        and abs(feet(pet)[1] - before[1]) <= 1, (before, feet(pet)))
    chk("  lookNum 이 붙고 num·이름은 그대로", pet.mon.get("lookNum") == MEGA_X
        and pet.mon["num"] == LIZ and pet.mon["info"]["name"] == "리자몽", pet.mon)
    chk("연출이 끝난다", wait(root, lambda: not pet.evolving))
    settle(root, 0.3)
    chk("  다시 걷는다 (멈춰 세운 것을 푼다)", not pet.battling and "advance" not in pet.__dict__)
    chk("  메가 폼의 다른 동작을 받으러 간다", app.fetched[-1:] == [[MEGA_X]], app.fetched)
    chk("  걷는 도트를 오버레이가 기억한다 (크기를 바꿔도 남게)",
        bool(ov.walks.get(MEGA_X)), list(ov.walks))
    ov.sync([dict(pet.mon)] + [p.mon for i, p in ov.pets.items() if i != 1], {})
    chk("  다음 동기화에서 그대로다", pet.look == MEGA_X and ov.pets[1] is pet)

    print("\n=== 끄기 ===")
    row = app.mega_menu_row(pet)
    chk("메뉴가 '원래 모습으로 걷기' 로 바뀐다", row and row["text"] == "원래 모습으로 걷기", row)
    before = feet(pet)
    row["command"]()
    chk("설정에서 빠진다", app.mega_ids() == [] and config.load_settings().get("megaWalk") == [])
    chk("원래 모습으로 돌아온다", wait(root, lambda: pet.look == LIZ and not pet.evolving), pet.look)
    chk("  크기도 돌아온다", pet.fw == w_base, (pet.fw, w_base))
    chk("  발밑 가운데가 그대로다", abs(feet(pet)[0] - before[0]) <= 1
        and abs(feet(pet)[1] - before[1]) <= 1, (before, feet(pet)))
    chk("  lookNum 이 없어진다", "lookNum" not in pet.mon, pet.mon)

    print("\n=== 도트를 못 받으면 ===")
    saved = dict(files), dict(sheets)
    files.pop(MEGA_X, None)
    sheets.pop(MEGA_X, None)
    ov.paths.pop((MEGA_X, False), None)
    ov.walks.pop(MEGA_X, None)
    app.toggle_mega_walk(pet)
    chk("일단 켜진다", app.mega_ids() == [1])
    chk("끝나면 켠 것을 무른다", wait(root, lambda: not pet.evolving and app.mega_ids() == []),
        app.mega_ids())
    chk("  모습은 그대로", pet.look == LIZ and pet.fw == w_base)
    chk("  기록에 남긴다", any("받지 못했" in n for n in app.notes), app.notes)
    files.update(saved[0])
    sheets.update(saved[1])

    print("\n=== 막아야 할 때 ===")
    app.battle = object()
    app.toggle_mega_walk(pet)
    chk("배틀 중에는 안 바뀐다", app.mega_ids() == [] and not pet.evolving)
    app.battle = None
    app.arena = object()
    app.toggle_mega_walk(pet)
    chk("투기장 중에도 안 바뀐다", app.mega_ids() == [] and not pet.evolving)
    app.arena = None


# ---------------------------------------------------------------- 6. 배틀 중
def battle_part(root, ov, app):
    print("\n=== 바탕화면 배틀의 메가진화 ===")
    pet = ov.pets[1]
    w_base = pet.fw
    layer = fx_layer.open_layer(root, ov.area())
    host = Host(app, layer)
    done = []
    mega_fx.battle(host, pet, MEGA_X, lambda: done.append(1))
    chk("끝나면 다음 사건으로 넘긴다 (한 번만)", wait(root, lambda: done) and done == [1], done)
    chk("그 판 동안 메가 폼의 도트", pet.look == MEGA_X and pet.fw > w_base, (pet.look, pet.fw))
    chk("  '메가진화!' 가 뜬다", host.said == ["메가진화!"], host.said)
    chk("  판이 끝날 때까지 sync 가 못 되돌린다", pet.look_hold is True)
    ov.sync([p.mon for p in ov.pets.values()], {})
    chk("    동기화가 와도 메가 폼", pet.look == MEGA_X)
    settle(root, 0.5)
    left = layer.cv.find_all() if layer else ()
    chk("  빛 조각이 남지 않는다", len(left) == 0, len(left))
    mega_fx.release(ov, [pet, None])
    chk("판이 끝나면 원래 모습으로", pet.look == LIZ and pet.fw == w_base and not pet.look_hold,
        (pet.look, pet.fw))

    print("\n=== 이미 메가 폼으로 걷던 도트 ===")
    walker = ov.pets[2]
    done = []
    mega_fx.battle(host, walker, MEGA_X, lambda: done.append(1))
    chk("연출만 돌고 넘어간다", wait(root, lambda: done) and walker.look == MEGA_X)
    chk("  붙잡아 두지 않는다 (되돌릴 것이 없다)", walker.look_hold is False)
    mega_fx.release(ov, [walker])
    chk("  끝나도 메가 폼 그대로", walker.look == MEGA_X)

    print("\n=== 메가 폼의 도트가 없을 때 ===")
    done = []
    host.said = []
    t0 = time.time()
    mega_fx.battle(host, pet, 10288, lambda: done.append(1))        # 메가펜드라: 도트 없음
    chk("판은 흘러간다", wait(root, lambda: done), done)
    chk("  3초 안에", time.time() - t0 < 3.0, time.time() - t0)
    chk("  도트는 그대로, 글씨는 뜬다", pet.look == LIZ and host.said == ["메가진화!"],
        (pet.look, host.said))
    chk("  붙잡아 두지 않는다", pet.look_hold is False)

    print("\n=== 판이 도중에 닫히면 ===")
    done = []
    mega_fx.battle(host, pet, MEGA_X, lambda: done.append(1))
    settle(root, 0.1)
    host.closed = True
    settle(root, 1.2)
    chk("다음으로 넘기지 않는다", done == [], done)
    mega_fx.release(ov, [pet])
    chk("도트는 원래 모습", pet.look == LIZ, pet.look)
    left = layer.cv.find_all() if layer else ()
    chk("빛 조각이 남지 않는다", len(left) == 0, len(left))

    print("\n=== 레이어를 못 열었을 때 (클릭 통과가 안 되는 환경) ===")
    bare = Host(app, None)
    done = []
    mega_fx.battle(bare, pet, MEGA_X, lambda: done.append(1))
    chk("연출 없이도 도트는 바뀌고 넘어간다", wait(root, lambda: done) and pet.look == MEGA_X,
        (done, pet.look))
    mega_fx.release(ov, [pet])
    if layer:
        layer.destroy()


# ---------------------------------------------------------------- 7. 배틀 창
def canvas_part(root):
    print("\n=== 배틀 창의 연출 (MegaFx) ===")
    top = tk.Toplevel(root)
    cv = tk.Canvas(top, width=400, height=300, bg="#202030", highlightthickness=0)
    cv.pack()
    root.update()
    log = []

    def later(ms, fn):
        return root.after(ms, fn)

    fx = ui_mega.MegaFx(cv, (200, 150), later, on_swap=lambda: log.append("swap"),
                        on_done=lambda: log.append("done"))
    fx.play()
    chk("시작하면 기운이 그려진다", len(cv.find_all()) > 0)
    chk("끝난다", wait(root, lambda: fx.dead, 5.0))
    chk("도트는 한 번만 바뀌고, 그 뒤에 끝났다고 알린다", log == ["swap", "done"], log)
    settle(root, 0.3)
    chk("캔버스에 아무것도 안 남는다", len(cv.find_all()) == 0, len(cv.find_all()))

    log[:] = []
    fx = ui_mega.MegaFx(cv, (200, 150), later, on_swap=lambda: log.append("swap"),
                        on_done=lambda: log.append("done"))
    fx.play()
    settle(root, 0.2)
    fx.stop()
    settle(root, 0.4)
    chk("도중에 멈추면 다음으로 안 넘긴다", log == [] and fx.dead, log)
    chk("  그린 것도 치운다", len(cv.find_all()) == 0, len(cv.find_all()))

    log[:] = []
    fx = ui_mega.MegaFx(cv, (200, 150), later, on_swap=lambda: log.append("swap"),
                        on_done=lambda: log.append("done"))
    fx.play()
    settle(root, 0.2)
    top.destroy()
    settle(root, 0.4)
    chk("창이 닫혀도 도트는 바뀐 것으로 치고 끝낸다", log == ["swap", "done"], log)


def main():
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

    dex_part()
    menu_part(root)

    # 도트: 메가 폼은 몸통이 넓다
    sheets = {LIZ: make_sheet("liz.png", 32, (220, 120, 60, 255)),
              RAY: make_sheet("ray.png", 32, (60, 160, 90, 255)),
              MEGA_X: make_sheet("megax.png", 48, (40, 40, 60, 255), wide=True)}
    files = {LIZ: make_dot("liz.gif.png", (220, 120, 60, 255)),
             RAY: make_dot("ray.gif.png", (60, 160, 90, 255)),
             MEGA_X: make_dot("megax.gif.png", (40, 40, 60, 255)),
             MEGA_Y: make_dot("megay.gif.png", (240, 90, 40, 255))}
    # 연출이 도트를 받는 자리 (서버 대신)
    sprite_cache.ensure = lambda api, num, shiny=False: files.get(num)
    walk_cache.ensure = lambda api, num, name="Walk", shiny=False: (
        sheets.get(num) if name == "Walk" and sheets.get(num) else (None, None))

    settings = dict(config.DEFAULTS)
    settings["megaWalk"] = []
    ov = overlay.Overlay(root, settings)
    paths = dict(((n, False), p) for n, p in files.items())
    walks = dict((n, s) for n, s in sheets.items())
    overlay_part(root, ov, paths, walks)
    app = MiniApp(root, ov)
    toggle_part(root, ov, app, files, sheets)
    battle_part(root, ov, app)

    # 배틀 밖에서 도트 위에 글씨 띄우기 (싸우지 않고 잡아서 받은 경험치, 1.8.1)
    print("\n=== 도트 위에 잠깐 뜨는 글씨 ===")
    before = set(root.winfo_children())
    ok = app.float_over_pet(1, "+120 exp", ms=300)
    root.update()
    made = [w for w in root.winfo_children() if w not in before]
    if fx_layer.open_layer(root, ov.area()) is None:
        chk("이펙트 층을 못 여는 환경에서는 조용히 넘어간다", ok is False and not made)
    else:
        for w in [w for w in root.winfo_children() if w not in before and w not in made]:
            w.destroy()                                  # 방금 확인용으로 연 층
        chk("글씨를 띄울 층이 생긴다", ok is True and len(made) == 1, (ok, made))
        settle(root, 1.2)
        chk("  시간이 지나면 층까지 치운다", not any(w.winfo_exists() for w in made))
    chk("바탕화면에 없는 포켓몬이면 아무 일도 없다", app.float_over_pet(999, "+1 exp") is False)

    canvas_part(root)

    ov.clear()
    settle(root, 0.3)
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
