# -*- coding: utf-8 -*-
"""길드 깃발 - 이름 옆 표시 (2.5.0, design-notes/2026-11-14-guild-flag.md '앱'). 진짜 Tk 로 본다. 서버 없이 돈다.

    python3 client/test_flag_names_ui.py              # 기본 화면을 본 뒤 DP 테마로 한 번 더 (자식 프로세스)
    POKET_SKIN=dp python3 client/test_flag_names_ui.py

서버는 줄마다 `"flag": 문자열|null` 을 싣는다 (랭킹 ranking[] · 친구 목록 friends[] · 길드전 match 의 own · target · from ·
matches[].guilds[]). 화면은
  · flag 가 있으면 이름 바로 앞에 깃발 그림(1배 = 24px)이 붙고, 없거나 틀린 꼴이면 안 붙는다 (자리도 안 비운다)
  · 깃발이 붙어도 이름 글꼴은 깃발 없는 줄과 같다 (글자를 줄이지 않는다) · 깃발 없는 줄은 예전 높이 그대로
  · DP 테마(캔버스 목록 - 보이는 줄만 그린다)는 create_image 로, 깃발이 아래 줄 글과 겹치지 않게 그 줄만 높인다
  · 길드전 1:1 판: 우리 · 상대 길드 이름 앞 (삼각형은 '우리가 칠 길드' · '우리를 치는 길드' 줄), 이번 시즌 맞대결 목록
가짜 서버는 기존 검사(test_held_rank_ui · test_skin_dp_friends · test_guild_war_match_ui)의 것을 물려받는다.
"""
import os
import subprocess
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-flag-names-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

import test_guild_war_match_ui as GM                        # noqa: E402
import test_held_rank_ui as HR                              # noqa: E402
import test_skin_dp_friends as DF                           # noqa: E402
from common import flag as F                                # noqa: E402
from poketdesktop import flag_art, skins                    # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_box, ui_friends, ui_guild, ui_guild_war, ui_rank  # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

GT, TG = GM.GT, GM.TG
OK = FAIL = 0
ERRORS = []


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def make_flag(color, hole=None):
    """한 빛깔로 채운 깃발 (hole 이면 가운데 한 칸을 그 빛깔로)."""
    px = F.fill(F.BLANK, 0, 0, color)
    if hole is not None:
        px = F.put(px, 12, 12, hole)
    return px


FLAG_A = make_flag(27, 21)          # 빨강 + 흰 점
FLAG_B = make_flag(17)              # 파랑
FLAG_C = F.put(F.BLANK, 3, 3, 9)    # 거의 투명 (한 칸만)
BAD = "이건 깃발이 아니다"            # 틀린 꼴 - 안 붙어야 한다


def pump(root, cond, sec=5.0):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def flag_names():
    """지금까지 만든 깃발 그림들의 Tk 이름."""
    return {str(img) for img in flag_art._CACHE.values()}


def is_flag_label(w):
    try:
        return w.winfo_class() == "Label" and str(w.cget("image")) in flag_names()
    except tk.TclError:
        return False


def find_labels(w, text):
    out = []
    for c in w.winfo_children():
        out.extend(find_labels(c, text))
        if c.winfo_class() == "Label" and str(c.cget("text")) == text:
            out.append(c)
    return out


def flags_in(w):
    n = 0
    for c in w.winfo_children():
        n += flags_in(c)
        if is_flag_label(c):
            n += 1
    return n


def flag_before(lb):
    """그 이름 라벨 바로 앞(pack 차례)에 깃발 라벨이 있나. 있으면 그 라벨."""
    slaves = lb.master.pack_slaves()
    i = slaves.index(lb)
    return slaves[i - 1] if i > 0 and is_flag_label(slaves[i - 1]) else None


def show(root, win, geo):
    top = win.winfo_toplevel()
    try:
        top.deiconify()
        top.geometry(geo)
    except tk.TclError:
        pass
    root.update()


def close(root, w):
    # 맥 Tk: 화면 밖에서 안 그려진 창을 바로 없애면 update() 가 돌아오지 않는다 - 화면 안에서 없앤다
    try:
        w.win.winfo_toplevel().geometry("+40+40")
        root.update()
    except tk.TclError:
        pass
    w.close()
    root.update()


# ---------------------------------------------------------------- DP 캔버스 목록 (보이는 줄만 그린다)
def canvas_row(root, vl, i):
    """i 번째 줄이 보이게 굴린 뒤 그 줄의 ([(깃발 그림 이름, bbox)], {글: (bbox, 글꼴)}, 줄 위 y, 줄 높이).
    항목 번호가 아니라 값을 돌려준다 - 다른 줄을 보러 굴리면 목록이 다시 그려져 번호가 없어진다."""
    vl.see(i)
    vl.refresh()
    root.update()
    cv = vl.cv
    items = cv.find_withtag("row%d" % i)
    imgs = [(cv.itemcget(it, "image"), cv.bbox(it)) for it in items if cv.type(it) == "image"
            and "flag" in cv.gettags(it) and cv.itemcget(it, "image") in flag_names()]
    texts = {}
    for it in items:
        if cv.type(it) == "text":
            texts.setdefault(cv.itemcget(it, "text"), (cv.bbox(it), cv.itemcget(it, "font")))
    return imgs, texts, vl.tops[i], vl.rows[i][0]


def drawn_rows(vl):
    """캔버스에 그려 둔 줄 번호들."""
    out = set()
    for it in vl.cv.find_withtag("row"):
        for t in vl.cv.gettags(it):
            if t.startswith("row") and t[3:].isdigit():
                out.add(int(t[3:]))
    return out


def visible_rows(vl):
    top = vl.cv.canvasy(0)
    bottom = top + vl.cv.winfo_height()
    return {i for i, t in enumerate(vl.tops) if t < bottom and t + vl.rows[i][0] > top}


# ================================================================ 랭킹
RANK_ROWS = [
    {"rank": 1, "name": "깃발있음", "rp": 1500, "tier": "master", "tierKr": "마스터볼", "games": 10, "wins": 8,
     "losses": 2, "flag": FLAG_A},
    {"rank": 2, "name": "깃발없음", "rp": 1300, "tier": "master", "tierKr": "마스터볼", "games": 9, "wins": 6,
     "losses": 3, "flag": None},
    {"rank": 3, "name": "나의이름", "me": True, "rp": 900, "tier": "hyper", "tierKr": "하이퍼볼", "games": 7, "wins": 4,
     "losses": 3, "flag": FLAG_B, "title": "칭호하나"},
    {"rank": 4, "name": "틀린깃발", "rp": 800, "tier": "hyper", "tierKr": "하이퍼볼", "games": 5, "wins": 2,
     "losses": 3, "flag": BAD},
    {"rank": 5, "name": "옛서버줄", "rp": 700, "tier": "super", "tierKr": "슈퍼볼", "games": 5, "wins": 1,
     "losses": 4},
]
RANK_FLAG = {"깃발있음": FLAG_A, "나의이름": FLAG_B}


class RankApi(HR.FakeApi):
    def pvp_ranking(self, limit=50):
        r = HR.FakeApi.pvp_ranking(self, limit)
        r["ranking"] = [dict(x) for x in RANK_ROWS]
        r["me"]["flag"] = FLAG_B
        return r


def rank_checks(root):
    print("-- 랭킹")
    app = HR.FakeApp(root)
    app.api = RankApi()
    rw = ui_rank.RankWindow(app)
    show(root, rw.win, "%dx%d+60+40" % (U.h(ui_rank.W), U.h(ui_rank.H)))
    pump(root, lambda: not rw.busy and rw.rows)
    if hasattr(rw, "vl"):
        rank_dp(root, rw)
    else:
        rank_basic(root, rw)
    close(root, rw)


def rank_basic(root, rw):
    pump(root, lambda: all(find_labels(rw.list, r["name"]) for r in RANK_ROWS))
    names = {r["name"]: find_labels(rw.list, r["name"])[0] for r in RANK_ROWS}
    for name, lb in names.items():
        fl = flag_before(lb)
        if name in RANK_FLAG:
            chk("'%s' 이름 바로 앞에 깃발" % name, fl is not None
                and str(fl.cget("image")) == str(flag_art.image(rw.win, RANK_FLAG[name])), fl)
            chk("  깃발은 1배 (24 x 24)", fl is not None and fl.winfo_reqwidth() == F.SIZE
                and fl.winfo_reqheight() == F.SIZE, fl and (fl.winfo_reqwidth(), fl.winfo_reqheight()))
        else:
            chk("'%s' 는 깃발 없음 (flag 없음 · null · 틀린 꼴)" % name, fl is None and flags_in(lb.master) == 0)
    fa, fb = str(names["깃발있음"].cget("font")), str(names["깃발없음"].cget("font"))
    chk("깃발 붙은 이름도 글꼴 그대로", fa and fa == fb, (fa, fb))
    chk("내 줄도 '나' 꼬리표 · 칭호 그대로", find_labels(names["나의이름"].master, "나")
        and find_labels(names["나의이름"].master, "칭호하나"))


def rank_dp(root, rw):
    vl = rw.vl
    pump(root, lambda: any(k == "rank" for _h, (k, _d) in vl.rows))
    rows = [(i, d) for i, (_h, (k, d)) in enumerate(vl.rows) if k == "rank"]
    chk("순위 줄 다섯 (가상 목록)", len(rows) == len(RANK_ROWS), len(rows))
    cv = vl.cv
    seen = {d["name"]: (d,) + canvas_row(root, vl, i) for i, d in rows}
    chk("보이는 줄만 그린다 (그려 둔 줄 = 보이는 줄)", drawn_rows(vl) <= visible_rows(vl),
        (sorted(drawn_rows(vl)), sorted(visible_rows(vl))))
    base_font = seen["깃발없음"][2].get("깃발없음", (None, None))[1]
    for name, (d, imgs, texts, top, hgt) in seen.items():
        if name not in RANK_FLAG:
            chk("'%s' 줄에는 깃발 없음" % name, not imgs, len(imgs))
            chk("  줄 높이 예전 그대로 (52)", hgt == U.h(52), hgt)
            continue
        ok = len(imgs) == 1 and imgs[0][0] == str(flag_art.image(cv, RANK_FLAG[name]))
        chk("'%s' 줄에 깃발 그림 하나 (create_image)" % name, ok, len(imgs))
        if not ok:
            continue
        fb = imgs[0][1]
        nb = texts.get(name, (None,))[0]
        bits = texts.get(d["bits"], (None,))[0]
        chk("  1배 (24 x 24)", fb[2] - fb[0] == F.SIZE and fb[3] - fb[1] == F.SIZE, fb)
        chk("  이름 바로 앞 (깃발 오른쪽에 이름)", nb is not None and fb[2] <= nb[0] <= fb[2] + U.h(12), (fb, nb))
        chk("  아래 줄 글과 안 겹치고 줄 안에 든다", bits is not None and fb[3] <= bits[1]
            and fb[1] >= top and fb[3] <= top + hgt, (fb, bits, top, hgt))
        chk("  줄은 예전(52)보다 낮지 않다", hgt >= U.h(52), hgt)
        chk("  이름 글꼴 그대로", base_font and texts.get(name, (None, None))[1] == base_font,
            (texts.get(name), base_font))


# ================================================================ 친구
FRIENDS = [
    dict(DF.FRIENDS[0], flag=FLAG_A),                       # 지우 - 깃발
    dict(DF.FRIENDS[1], flag=None),                         # 웅이 - 없음
    dict(DF.FRIENDS[2], flag=FLAG_C, wins=1, losses=2),     # 이슬 - 거의 투명한 깃발도 그림은 붙는다
    dict(DF.FRIENDS[3], flag=BAD),                          # 알망드 - 틀린 꼴
]
FRIEND_FLAG = {"지우": FLAG_A, "이슬": FLAG_C}


class FriendsApi(DF.Api):
    def friends(self):
        d = DF.Api.friends(self)
        d["friends"] = [dict(f) for f in FRIENDS]
        return d


def friend_checks(root):
    print("-- 친구 목록")
    app = DF.App(root)
    app.api = FriendsApi()
    app.live_pending = None
    fw = ui_friends.FriendsWindow(app)
    show(root, fw.win, "%dx%d+60+40" % (U.h(ui_friends.W), U.h(ui_friends.H)))
    pump(root, lambda: not fw.busy and fw.data)
    if hasattr(fw, "vl"):
        friends_dp(root, fw)
    else:
        friends_basic(root, fw)
    close(root, fw)


def friends_basic(root, fw):
    pump(root, lambda: all(find_labels(fw.list, f["name"]) for f in FRIENDS))
    names = {f["name"]: find_labels(fw.list, f["name"])[0] for f in FRIENDS}
    for name, lb in names.items():
        fl = flag_before(lb)
        if name in FRIEND_FLAG:
            chk("'%s' 이름 바로 앞에 깃발" % name, fl is not None
                and str(fl.cget("image")) == str(flag_art.image(fw.win, FRIEND_FLAG[name])), fl)
            chk("  접속 점 다음 자리", fl is not None and lb.master.pack_slaves().index(fl) == 1,
                fl and lb.master.pack_slaves().index(fl))
        else:
            chk("'%s' 는 깃발 없음 (null · 틀린 꼴)" % name, fl is None and flags_in(lb.master) == 0)
            chk("  이름 자리 예전 그대로 (padx 8)", str(lb.pack_info().get("padx")) == "8", lb.pack_info().get("padx"))
    fa, fb = str(names["지우"].cget("font")), str(names["웅이"].cget("font"))
    chk("깃발 붙은 이름도 글꼴 그대로", fa == fb, (fa, fb))
    chk("받은 신청 · 보낸 신청 · 차단 줄에는 깃발 없음", all(
        flags_in(find_labels(fw.list, n)[0].master) == 0 for n in ("로켓단", "난천", "스팸")))


def friends_dp(root, fw):
    vl = fw.vl
    pump(root, lambda: any(k == "friend" for _h, (k, _d) in vl.rows))
    rows = [(i, d) for i, (_h, (k, d)) in enumerate(vl.rows) if k == "friend"]
    chk("친구 줄 넷 (가상 목록)", len(rows) == len(FRIENDS), len(rows))
    cv = vl.cv
    seen = {d["name"]: (d,) + canvas_row(root, vl, i) for i, d in rows}
    chk("보이는 줄만 그린다 (그려 둔 줄 = 보이는 줄)", drawn_rows(vl) <= visible_rows(vl),
        (sorted(drawn_rows(vl)), sorted(visible_rows(vl))))

    def name_of(name, texts):
        """이름 글 항목 (남은 폭이 모자라 '…' 로 줄었으면 그것)."""
        if name in texts:
            return texts[name]
        return next((v for k, v in texts.items() if k.endswith("…") and name.startswith(k[:-1])), (None, None))
    base_font = name_of("웅이", seen["웅이"][2])[1]
    for name, (d, imgs, texts, top, hgt) in seen.items():
        if name not in FRIEND_FLAG:
            chk("'%s' 줄에는 깃발 없음" % name, not imgs, len(imgs))
            chk("  줄 높이 예전 그대로 (48)", hgt == U.h(48), hgt)
            continue
        ok = len(imgs) == 1 and imgs[0][0] == str(flag_art.image(cv, FRIEND_FLAG[name]))
        chk("'%s' 줄에 깃발 그림 하나 (create_image)" % name, ok, len(imgs))
        if not ok:
            continue
        fb = imgs[0][1]
        nb, nfont = name_of(name, texts)
        low = texts.get("%d승 %d패" % (d.get("wins", 0), d.get("losses", 0)), (None,))[0]
        chk("  이름 바로 앞 (깃발 오른쪽에 이름)", nb is not None and fb[2] <= nb[0] <= fb[2] + U.h(12), (fb, nb))
        chk("  아래 줄(전적)과 안 겹치고 줄 안에 든다", low is not None and fb[3] <= low[1]
            and fb[1] >= top and fb[3] <= top + hgt, (fb, low, top, hgt))
        chk("  줄은 예전(48)보다 낮지 않다", hgt >= U.h(48), hgt)
        chk("  이름 글꼴 그대로", base_font and nfont == base_font, (nfont, base_font))
    others = [i for i, (_h, (k, _d)) in enumerate(vl.rows) if k in ("request", "pending", "blocked")]
    chk("받은 신청 · 보낸 신청 · 차단 줄에는 깃발 없음", others and all(not canvas_row(root, vl, i)[0] for i in others))


# ================================================================ 길드전 1:1
class FlagWar(GM.MatchWar):
    """1:1 맞대결 서버 흉내 + 길드 깃발 (우리 피카단 = A, 상대 로켓단 = B, 삼각형의 '우리를 치는 길드' = C)."""

    FLAGS = {1: FLAG_A, 9: FLAG_B, 8: FLAG_C, 4: BAD}

    def match(self):
        m = GM.MatchWar.match(self)
        for key in ("target", "from", "own"):
            side = dict(m[key])
            side["flag"] = self.FLAGS.get(side.get("guildId"))
            m[key] = side
        return m

    def matches(self):
        out = []
        for mt in GM.MatchWar.matches(self):
            mt = dict(mt)
            mt["guilds"] = [dict(g, flag=self.FLAGS.get(g.get("guildId"))) for g in mt["guilds"]]
            out.append(mt)
        return out


def war_checks(root):
    print("-- 길드전 1:1")
    ui_guild.CHAT_MS = 150
    ui_box.confirm = lambda *a, **k: True
    ui_guild_war.POLL_MS = 600000            # 검사 도중 판을 다시 그리지 않게
    ui_guild_war.WarTab._open_battle = lambda self, data: None
    srv = TG.FakeServer()
    srv.names.update(GM.NAMES)
    srv.g = {"name": "피카단", "intro": "", "mode": "open", "master": 1, "points": 0}
    srv.roles = {1: "master", 2: "member", 3: "member"}
    app = GT.App(root, GM.Api(srv, 1))
    srv.war = FlagWar()
    w = ui_guild.GuildWindow(app)
    top = w.win.winfo_toplevel()
    top.deiconify()
    top.geometry("1000x680+60+40")
    TG.wait(root, lambda: w.data is not None and w.mode == "guild")
    war = GT.open_war(root, w)
    TG.wait(root, lambda: war._board_on and len(war.foe_rows) == 5)
    TG.settle(root, 0.3)

    sb = war.score_box
    us, them = find_labels(sb, "우리 [피카단]"), find_labels(sb, "[로켓단]")
    chk("1:1 별 판: 우리 이름 앞에 우리 깃발", us and flag_before(us[0]) is not None
        and str(flag_before(us[0]).cget("image")) == str(flag_art.image(sb, FLAG_A)), us)
    chk("  상대 이름 앞에 상대 깃발", them and flag_before(them[0]) is not None
        and str(flag_before(them[0]).cget("image")) == str(flag_art.image(sb, FLAG_B)), them)
    chk("  별 판의 깃발은 둘뿐", flags_in(sb) == 2, flags_in(sb))
    font_us = str(us[0].cget("font")) if us else None
    rk = war.rank_box
    blocks = rk.winfo_children()
    pika = find_labels(blocks[0], "[피카단]  우리")
    rocket = find_labels(blocks[0], "[로켓단]")
    kkobugi = find_labels(blocks[1], "[꼬부기단]")
    longg = find_labels(blocks[1], "[아주아주긴이름의길드]")
    chk("이번 시즌 맞대결: 우리 판의 두 길드 이름 앞에 깃발", pika and rocket and flag_before(pika[0]) is not None
        and flag_before(rocket[0]) is not None
        and str(flag_before(rocket[0]).cget("image")) == str(flag_art.image(rk, FLAG_B)), (pika, rocket))
    chk("  틀린 꼴(꼬부기단) · 없음은 깃발 없음", kkobugi and flag_before(kkobugi[0]) is None
        and flags_in(blocks[2]) == 0, kkobugi)
    chk("  남의 짝의 깃발(긴 이름 길드)은 그 길드 것", longg and flag_before(longg[0]) is not None
        and str(flag_before(longg[0]).cget("image")) == str(flag_art.image(rk, FLAG_C)), longg)
    chk("  목록 이름 글꼴 그대로 (깃발 있는 줄 = 없는 줄)", rocket and kkobugi
        and str(rocket[0].cget("font")) == str(kkobugi[0].cget("font")))
    ok, bad = GM.no_clip(war, top)
    chk("글이 잘리지 않는다 (판 · 오른쪽 칸)", ok, bad)

    print("-- 길드전 삼각형")
    srv.war.kind = "tri"
    chk("삼각형으로 다시 받는다", GM.reload(root, war, lambda: (war.st.get("match") or {}).get("kind") == "tri"))
    sb = war.score_box
    to = find_labels(sb, "우리가 칠 길드 [로켓단] · 출전 5명")
    fr = find_labels(sb, "우리를 치는 길드 [아주아주긴이름의길드] · 출전 7명")
    chk("'우리가 칠 길드' 줄 앞에 그 길드 깃발", to and flag_before(to[0]) is not None
        and str(flag_before(to[0]).cget("image")) == str(flag_art.image(sb, FLAG_B)), to)
    chk("'우리를 치는 길드' 줄 앞에 그 길드 깃발", fr and flag_before(fr[0]) is not None
        and str(flag_before(fr[0]).cget("image")) == str(flag_art.image(sb, FLAG_C)), fr)
    chk("  제목 글꼴 그대로", to and font_us and str(to[0].cget("font")) == font_us, to and to[0].cget("font"))
    ok, bad = GM.no_clip(war, top)
    chk("  글이 잘리지 않는다", ok, bad)

    print("-- 길드전 깃발 없음 (예전 그대로)")
    srv.war = GM.MatchWar()
    chk("깃발 없는 판으로 다시 받는다", GM.reload(root, war, lambda: "flag" not in ((war.st.get("match") or {})
                                                                         .get("own") or {})))
    TG.wait(root, lambda: war._board_on and len(war.foe_rows) == 5)
    sb, rk = war.score_box, war.rank_box
    us = find_labels(sb, "우리 [피카단]")
    chk("별 판 · 맞대결 목록에 깃발 없음", flags_in(sb) == 0 and flags_in(rk) == 0, (flags_in(sb), flags_in(rk)))
    chk("  이름 라벨은 예전처럼 칸에 바로 (깃발 틀 없음 - 같은 칸에 '출전 N명')",
        us and find_labels(us[0].master, "출전 3명"), us and us[0].master)
    w.close()
    root.update()


def main():
    print("=== 테마: %s ===" % skins.active())
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    root.report_callback_exception = lambda *a: ERRORS.append(a)
    U.init_fonts(root)
    U.apply_theme(root)
    rank_checks(root)
    friend_checks(root)
    war_checks(root)
    chk("화면 콜백 오류 없음", not ERRORS, ERRORS[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    bad = 1 if FAIL else 0
    if not os.environ.get("POKET_SKIN"):
        env = dict(os.environ, POKET_SKIN="dp")
        bad |= subprocess.call([sys.executable, os.path.abspath(__file__)], env=env)
    return bad


if __name__ == "__main__":
    sys.exit(main())
