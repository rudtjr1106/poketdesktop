# -*- coding: utf-8 -*-
"""배틀 창의 포켓몬 도트 - 화면 없이.

    python client/test_mon_size.py

2.5.5 (게시판 #777 댕댕킴 '따라큐 같은 애들이 엄청 크게 보인다'): 도트 키 = 도감의 키
2.5.8 (게시판 #850 댕댕킴의 뒤이은 피드백): 전체적으로 덜 줄인다 · 떠 있는 포켓몬은 띄운다 · 내 포켓몬은 뒷모습

  1. 몫: 0.3m 이하 0.55 · 2.0m 이상 1.0 · 사이는 커질수록 커진다 · 키를 모르면 1.0 (예전과 같다)
  2. 진짜 도감: 따라큐 < 피카츄 < 리자몽 < 잠만보 = 그란돈 = 고래왕 (칸 다 씀)
  3. 메가 · 폼은 그 모습의 키 · 없으면 원래 종의 키
  4. 떠 있는 종: 비행 타입 · 부유 특성 (숨겨진 특성도) - 칸의 12% 를 띄우고 그만큼 도트를 줄여 칸을 안 넘는다
  5. 띄운 그림: 아래에 띄운 만큼 띠가 붙고 그 바닥에 그림자 · 몸은 위에 그대로 · 0 이면 받은 그대로
  6. 관장 · 실시간 배틀 창: 키대로 받아 온다 · 비행은 띄운다 · 레이드 우리 쪽도 (보스는 늘 칸 그대로)
  7. 뒷모습: 내 쪽만 뒷모습 도트(그대로) · 없으면 앞모습을 뒤집어 · 상대는 늘 앞모습 · 설정을 끄면 앞모습
  8. 내 포켓몬을 누르면 앞뒤가 바뀐다 (설정에 적고 다시 세운다) · 쓰러진 포켓몬은 다시 세우지 않는다
  9. 도트 보관: 뒷모습은 이름에 b · 없다는 답은 기억한다 (다시 안 묻는다) · 옛 서버(머리말 없음)의 답은 버린다
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-mon-size-")

from PIL import Image                                       # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import config                             # noqa: E402
from poketdesktop import mon_size as MS                     # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def dex():
    with open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8") as f:
        return P.Pokedex(json.load(f))


DEX = dex()
NUM = {"따라큐": 778, "피카츄": 25, "리자몽": 6, "잠만보": 143, "그란돈": 383, "고래왕": 321, "파쪼옥": 595}


class _Anim(object):
    """load_animation 이 돌려주는 것처럼: frames[RIGHT] 는 원본, frames[LEFT] 는 뒤집은 것."""
    key, durations = None, [100]

    def __init__(self, size):
        self.frames = [["원본"], ["뒤집음"]]
        self.size = size


def run_window(mod, cls, mons, key, settings=None, back_have=(), **kw):
    """창을 띄우지 않고 set_mon 만 돌린다. 포켓몬마다 {size, path, facing, lift, frames} 를 모은다."""
    from poketdesktop import sprite_cache, sprites, ui_gimmick
    got = []
    w = cls.__new__(cls)
    w.app = type("A", (), {"dex": DEX, "api": None, "settings": dict(config.DEFAULTS, **(settings or {}))})()
    w.shown, w.anims, w.alive = {}, {}, True
    noop = lambda *a, **k: None                                         # noqa: E731
    w.zoom_use = w._paint_box = w._stop_anim = w._paint = noop
    w.sendout = type("S", (), {"cancel": noop, "forget": noop, "arrive": lambda *a: True})()
    w.hiding = type("H", (), {"apply": noop})()
    binds = []
    w.cv = type("C", (), {"itemconfigure": noop, "tag_bind": lambda self, *a: binds.append(a[:2])})()
    w.sprite = {key: 1, "me": 1}
    w.root = None
    w.dot_fit = lambda who, h, wd: h
    cur = {}

    def ensure(api, num, shiny, back=False):
        if back and num not in back_have:
            return None
        return "%d%s.gif" % (num, "b" if back else "")

    def load(path, size, *a, **k):
        cur.update(size=size, path=path)
        return _Anim(size)

    def to_rgba(f, _key):
        cur["facing"] = f
        return Image.new("RGBA", (10, 20), (255, 0, 0, 255))

    def run(root, work, done):
        cur.clear()
        res = work()
        if res is not None:
            cur["frames"] = res[1]
            got.append(dict(cur))
    old = (mod.run_async, sprite_cache.ensure, sprites.load_animation, sprites.to_rgba, ui_gimmick.tera_look)
    mod.run_async, sprite_cache.ensure, sprites.load_animation = run, ensure, load
    sprites.to_rgba, ui_gimmick.tera_look = to_rgba, (lambda frames, tera: frames)
    try:
        for n in mons:
            w.set_mon(key, {"num": n}, **kw)
    finally:
        mod.run_async, sprite_cache.ensure, sprites.load_animation, sprites.to_rgba, ui_gimmick.tera_look = old
    for g in got:
        g["lift"] = g["frames"][0].size[1] - 20
    return got, w, binds


def main():
    print("=== 배틀 도트 키 (#777 · #850)")
    chk("1. 0.3m 이하는 0.55", MS.ratio(0.1) == MS.ratio(0.3) == 0.55, (MS.ratio(0.1), MS.ratio(0.3)))
    chk("   2.0m 이상은 1.0", MS.ratio(2.0) == MS.ratio(14.5) == 1.0, (MS.ratio(2.0), MS.ratio(14.5)))
    seq = [MS.ratio(h) for h in (0.3, 0.5, 0.9, 1.2, 1.6, 2.0)]
    chk("   사이는 커질수록 커진다", all(a < b for a, b in zip(seq, seq[1:])), seq)
    chk("   키를 모르면 1.0 (예전과 같다)", MS.ratio(None) == MS.ratio(0) == MS.ratio("?") == 1.0)
    chk("   도감이 없으면 칸 그대로", MS.fit(None, 778, 132) == 132 and MS.place(None, 778, 132) == (132, 0))

    r = {k: MS.ratio(MS.height_of(DEX, n)) for k, n in NUM.items()}
    chk("2. 따라큐 < 피카츄 < 리자몽 < 잠만보", r["따라큐"] < r["피카츄"] < r["리자몽"] < r["잠만보"] == 1.0, r)
    chk("   그란돈 · 고래왕도 칸을 다 쓴다 · 파쪼옥은 가장 작게", r["그란돈"] == r["고래왕"] == 1.0 and r["파쪼옥"] == 0.55, r)
    chk("   내 쪽 칸(132px)에서 따라큐 73px · 피카츄 82px · 리자몽 127px",
        (MS.fit(DEX, 778, 132), MS.fit(DEX, 25, 132), MS.fit(DEX, 6, 132)) == (73, 82, 127),
        (MS.fit(DEX, 778, 132), MS.fit(DEX, 25, 132), MS.fit(DEX, 6, 132)))

    mega = next(m for m in DEX.megas if m.get("megaOf") == "CHARIZARD" and m.get("height"))
    chk("3. 메가는 그 모습의 키", MS.height_of(DEX, mega["num"]) == mega["height"], (mega["num"], mega.get("height")))
    form = next((f for f in DEX.forms if f.get("formOf")), None)
    if form is not None:
        saved = form.pop("height", None)
        try:
            base = DEX.get(form["formOf"])
            chk("   폼에 키가 없으면 원래 종의 키", MS.height_of(DEX, form["num"]) == base.get("height"),
                (form["num"], base.get("height")))
        finally:
            if saved is not None:
                form["height"] = saved
    chk("   모르는 번호는 None", MS.height_of(DEX, 99999) is None)

    # 구구(비행) · 또가스(부유) · 리자몽(비행) 은 뜨고, 피카츄 · 그란돈 · 메가리자몽X(불꽃/드래곤) 는 안 뜬다
    megax = next(m for m in DEX.megas if m.get("megaOf") == "CHARIZARD" and "FLYING" not in (m.get("types") or ()))
    hidden = next((s for s in DEX.species if s.get("hidden") == "LEVITATE"
                   and "LEVITATE" not in (s.get("abil") or ()) and "FLYING" not in (s.get("types") or ())), None)
    chk("4. 비행 타입 · 부유 특성은 떠 있는 종", MS.floats(DEX, 16) and MS.floats(DEX, 109) and MS.floats(DEX, 6))
    chk("   아닌 종 · 모르는 번호 · 도감 없음은 아니다", not MS.floats(DEX, 25) and not MS.floats(DEX, 383)
        and not MS.floats(DEX, megax["num"]) and not MS.floats(DEX, 99999) and not MS.floats(None, 16))
    if hidden is not None:
        chk("   숨겨진 특성이 부유인 종도", MS.floats(DEX, hidden["num"]), hidden.get("kr"))
    chk("   칸(132)의 12퍼센트 = 16px 띄운다 · 안 뜨는 종은 0", MS.place(DEX, 16, 132) == (73, 16) and MS.place(DEX, 25, 132) == (82, 0),
        (MS.place(DEX, 16, 132), MS.place(DEX, 25, 132)))
    size, lift = MS.place(DEX, 384, 132)                    # 레쿠쟈 7m - 칸을 다 쓰는 비행
    chk("   큰 비행 포켓몬은 띄운 만큼 줄여 칸을 안 넘는다", size + lift == 132 and lift == 16, (size, lift))

    red = Image.new("RGBA", (40, 30), (255, 0, 0, 255))
    up = MS.lifted([red, red], 10)
    chk("5. 띄운 그림: 높이가 띄운 만큼 는다 (장마다)", [im.size for im in up] == [(40, 40), (40, 40)], [im.size for im in up])
    chk("   몸은 위에 그대로", up[0].getpixel((20, 0)) == (255, 0, 0, 255) and up[0].getpixel((20, 29)) == (255, 0, 0, 255))
    chk("   바닥 가운데에 옅은 그림자 · 구석은 투명", up[0].getpixel((20, 38))[3] == MS.SHADOW[3] and up[0].getpixel((0, 39))[3] == 0
        and up[0].getpixel((0, 32))[3] == 0, (up[0].getpixel((20, 38)), up[0].getpixel((0, 39))))
    chk("   0 이면 받은 그대로", MS.lifted([red], 0)[0] is red and MS.lifted([], 5) == [])

    from poketdesktop import ui_gym_battle as GB
    from poketdesktop import ui_live_battle as LB
    from poketdesktop import ui_raid_battle as RB
    full = 132
    gym, _w, _b = run_window(GB, GB.GymBattleWindow, [778, 383, 16], "foe")
    chk("6. 관장 배틀: 따라큐는 칸보다 작게 · 그란돈은 칸 그대로 · 구구는 띄운다",
        [(g["size"], g["lift"]) for g in gym] == [(MS.fit(DEX, 778, 108), 0), (108, 0), MS.place(DEX, 16, 108)],
        [(g["size"], g["lift"]) for g in gym])
    live_cls = next(getattr(LB, n) for n in dir(LB) if n.endswith("Window") and hasattr(getattr(LB, n), "set_mon"))
    live, _w, _b = run_window(LB, live_cls, [778, 383, 16], "me")
    box = LB.U.h(LB.MON_H["me"])
    chk("   실시간 배틀도 같다", [(g["size"], g["lift"]) for g in live] == [(MS.fit(DEX, 778, box), 0), (box, 0),
                                                              MS.place(DEX, 16, box)], live)
    raid_cls = next(getattr(RB, n) for n in dir(RB) if n.endswith("Window") and hasattr(getattr(RB, n), "set_mon"))
    raid, _w, _b = run_window(RB, raid_cls, [778, 16], 0)
    boss, _w, _b = run_window(RB, raid_cls, [16], 0, boss=True)
    chk("   레이드: 우리 쪽은 키대로 · 비행은 띄운다", raid[0]["size"] < RB.U.h(RB.MON_H) and raid[0]["lift"] == 0
        and raid[1]["lift"] > 0, raid)
    chk("   보스는 구구라도 칸 그대로 · 안 띄운다", boss[0]["size"] == RB.U.h(RB.BOSS_H) and boss[0]["lift"] == 0, boss)

    me, w, binds = run_window(GB, GB.GymBattleWindow, [25, 778], "me", back_have=(25,))
    chk("7. 내 쪽: 뒷모습 도트가 있으면 그것을 그대로 (상대 쪽을 본다)", me[0]["path"] == "25b.gif" and me[0]["facing"] == "원본", me[0])
    chk("   뒷모습이 없는 종은 앞모습을 뒤집어 (예전과 같다)", me[1]["path"] == "778.gif" and me[1]["facing"] == "뒤집음", me[1])
    chk("   키는 앞뒤가 같다", me[0]["size"] == MS.fit(DEX, 25, full), me[0])
    foe, _w, _b = run_window(GB, GB.GymBattleWindow, [25], "foe", back_have=(25,))
    chk("   상대는 늘 앞모습 그대로", foe[0]["path"] == "25.gif" and foe[0]["facing"] == "원본", foe[0])
    off, _w, _b = run_window(GB, GB.GymBattleWindow, [25], "me", settings={"battleBack": False}, back_have=(25,))
    chk("   설정을 끄면 내 쪽도 앞모습을 뒤집어", off[0]["path"] == "25.gif" and off[0]["facing"] == "뒤집음", off[0])
    lme, _w, _b = run_window(LB, live_cls, [25], "me", back_have=(25,))
    chk("   실시간 배틀도 내 쪽은 뒷모습", lme[0]["path"] == "25b.gif" and lme[0]["facing"] == "원본", lme[0])
    chk("   기본 설정은 뒷모습", config.DEFAULTS.get("battleBack") is True and MS.back_view(w.app))

    chk("8. 내 포켓몬 그림에 누르기가 걸린다 (하나만 - 세울 때마다 갈아 끼운다)",
        binds and all(b == (1, "<Button-1>") for b in binds), binds)
    calls, saved = [], []
    w.set_mon = lambda who, mon, **k: calls.append((who, mon.get("num")))
    w.shown = {"me": {"num": 25}}
    real_save = config.save_settings
    config.save_settings = lambda s: saved.append(s.get("battleBack"))
    try:
        MS.flip_me(w)
        chk("   누르면 앞모습으로: 설정에 적고 저장 · 지금 포켓몬을 다시 세운다",
            w.app.settings["battleBack"] is False and saved == [False] and calls == [("me", 25)], (saved, calls))
        MS.flip_me(w)
        chk("   또 누르면 뒷모습으로", w.app.settings["battleBack"] is True and calls == [("me", 25), ("me", 25)], calls)
        w.shown = {"me": {"num": 25, "fainted": True}}
        MS.flip_me(w)
        chk("   쓰러진 포켓몬은 다시 세우지 않는다 (설정만 바뀐다)", len(calls) == 2 and w.app.settings["battleBack"] is False,
            (calls, w.app.settings["battleBack"]))
    finally:
        config.save_settings = real_save

    from poketdesktop import sprite_cache as SC
    asked = []

    class Api(object):
        have = {(25, False, True): b"BACK", (25, False, False): b"FRONT"}

        def sprite(self, num, shiny=False, back=False):
            asked.append((num, bool(shiny), bool(back)))
            data = self.have.get((num, bool(shiny), bool(back)))
            return (data, ".gif") if data else (None, None)
    api = Api()
    pb = SC.ensure(api, 25, False, True)
    pf = SC.ensure(api, 25, False)
    chk("9. 뒷모습은 이름에 b 가 붙어 따로 보관된다", os.path.basename(pb) == "0025b.gif" and os.path.basename(pf) == "0025.gif"
        and open(pb, "rb").read() == b"BACK" and open(pf, "rb").read() == b"FRONT", (pb, pf))
    chk("   다음에는 받아 둔 것을 쓴다 (다시 안 묻는다)", SC.ensure(api, 25, False, True) == pb and len(asked) == 2, asked)
    chk("   뒷모습이 없으면 None (앞모습으로 대신하지 않는다)", SC.ensure(api, 778, False, True) is None)
    n = len(asked)
    SC.ensure(api, 778, False, True)
    chk("   없다는 답은 기억한다 (다시 안 묻는다)", len(asked) == n, asked[n:])
    chk("   앞모습은 그 뒤에도 그대로 묻는다", SC.ensure(api, 778, False) is None and asked[-1] == (778, False, False), asked[-1])

    from poketdesktop import api as APIM
    client = APIM.Api.__new__(APIM.Api)
    client.base = "http://x"
    urls = []

    class Resp(object):
        status_code, content = 200, b"IMG"

        def __init__(self, headers):
            self.headers = headers
    client.session = type("S", (), {"get": lambda self, url, timeout=0: (urls.append(url), Resp(HEAD[0]))[1]})()
    HEAD = [{"X-Sprite-Ext": ".gif"}]
    chk("   옛 서버(X-Sprite-Back 없음)가 준 그림은 뒷모습으로 받지 않는다", client.sprite(25, False, True) == (None, None)
        and urls[-1] == "http://x/api/sprite/25?back=true", urls)
    HEAD[0] = {"X-Sprite-Ext": ".gif", "X-Sprite-Back": "1"}
    chk("   새 서버의 뒷모습은 받는다 · 이로치는 shiny 와 같이", client.sprite(25, True, True) == (b"IMG", ".gif")
        and urls[-1] == "http://x/api/sprite/25?shiny=true&back=true", urls[-1])
    HEAD[0] = {"X-Sprite-Ext": ".gif"}
    chk("   앞모습 요청은 예전과 같은 주소", client.sprite(25) == (b"IMG", ".gif") and urls[-1] == "http://x/api/sprite/25"
        and client.sprite(25, True)[0] == b"IMG" and urls[-1] == "http://x/api/sprite/25?shiny=true", urls[-2:])

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
