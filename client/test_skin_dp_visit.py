# -*- coding: utf-8 -*-
"""화면 테마 '디아루가·펄기아'(skins/dp) 검사 - 묶음 visit: 놀러 가기 · 여기에 두기 도구 창, 업적 · 칭호 칸, 업적 알림.

    python client/test_skin_dp_visit.py

**창을 진짜로 띄운다** (가짜 서버). 테마는 칠하기만 새로 하고 동작은 기본 화면의 것을 그대로 쓰므로, 여기서는
'DP 로 칠한 자리가 기본 동작과 맞물리나' 를 본다.

  1. POKET_SKIN=dp 면 ItemPicker · AchievementPanel · TitlePanel 이 DP 클래스로 뜬다 (기본 클래스의 자식).
  2. 놀러 가기 (carry): 볼 · 지닌 도구 중 귀함까지만 보이고, 줄을 누르면 하나씩 담기고, 볼 5 · 지닌 도구 1 · 가진 수가
     한도다. 한도 액정 · 누가 가는지 · 도트가 뜨고, ▲ ▼ 빼기가 담은 수를 바꾼다. '놀러 가기' 는 담은 것을 넘긴다.
  3. 여기에 두기 (drop): 들고 온 것만, 담기 전에는 단추가 죽어 있고, 두면 서버에 가고 가방을 새로 받는다.
     친구가 오늘 받았으면 '이미 받음' · 담기지 않고 단추가 죽는다.
  4. 업적 칸: 갈래 띠 · 이룬 것은 금메달 + 날짜, 못 이룬 것은 회색 메달 + 진행 막대, 숨은 업적은 ?, 해금 안내.
     창 폭이 바뀌면 줄 높이를 다시 잡는다. 예순 줄이어도 끝까지 굴러간다.
  5. 칭호 칸: 가진 수 · 얻는 조건 · '가지고 있음' · '지금은 얻을 수 없음'. 도감 탭의 '업적' · '칭호' 단추로 번갈아 본다.
  6. 업적 알림 창: 하나면 '업적 달성!', 여럿이면 '지금까지의 기록으로' + 여덟 줄 넘게는 '그 밖 N개', 확인으로 닫힌다.
  모든 창에서 그리는 중에 난 예외가 없다.
"""
import io
import os
import sys
import tempfile

os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-test-skin-dp-visit-"))
os.environ.setdefault("POKET_SKIN", "dp")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from PIL import Image, ImageDraw                            # noqa: E402

import test_big_lists as TBL                                # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins                              # noqa: E402
from poketdesktop import sprite_cache                       # noqa: E402
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


# ---------------------------------------------------------------- 가짜 서버 · 앱
def icon_png(item_id):
    """도구 그림 대신 쓰는 색 동그라미 (이름마다 색이 다르다)."""
    h = sum(ord(c) for c in item_id)
    col = ((h * 53) % 200 + 40, (h * 97) % 200 + 40, (h * 29) % 200 + 40, 255)
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((3, 3, 28, 28), fill=col, outline=(40, 40, 50, 255), width=2)
    d.rectangle((3, 14, 28, 17), fill=(40, 40, 50, 255))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def sprite_png(path):
    im = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((8, 10, 40, 42), fill=(240, 120, 40, 255), outline=(60, 30, 10, 255), width=2)
    d.ellipse((17, 20, 23, 26), fill=(255, 255, 255, 255))
    d.ellipse((27, 20, 33, 26), fill=(255, 255, 255, 255))
    im.save(path)
    return path


SHOP = {"money": 0,
        "bag": {"GREATBALL": 7, "ULTRABALL": 2, "BLACKBELT": 2, "FOCUSSASH": 1, "MASTERBALL": 1, "FIRESTONE": 3,
                "POKEBALL": 12},
        "items": [{"id": "POKEBALL", "kr": "몬스터볼", "cat": "ball", "rarity": "common"},
                  {"id": "GREATBALL", "kr": "슈퍼볼", "cat": "ball", "rarity": "uncommon"},
                  {"id": "ULTRABALL", "kr": "하이퍼볼", "cat": "ball", "rarity": "rare"},
                  {"id": "BLACKBELT", "kr": "검은띠", "cat": "held", "rarity": "uncommon"},
                  {"id": "FOCUSSASH", "kr": "기합의띠", "cat": "held", "rarity": "epic"},
                  {"id": "MASTERBALL", "kr": "마스터볼", "cat": "ball", "rarity": "legendary"},
                  {"id": "FIRESTONE", "kr": "불꽃의돌", "cat": "stone", "rarity": "common"}]}


class Api(object):
    def __init__(self):
        self.calls = []
        self.state_visit = None

    def shop(self):
        return SHOP

    def item_sprite(self, item_id):
        return icon_png(item_id)

    def visit_state(self):
        return {"visit": self.state_visit, "receivedToday": 0, "receivePerDay": 1, "ballMax": 5, "heldMax": 1,
                "rarities": ["common", "uncommon", "rare"]}

    def visit_drop(self, items):
        self.calls.append(("drop", items))
        return {"bundle": {"id": 70, "items": items, "count": 1}}

    def achievements(self):
        return PUBLIC

    def titles(self):
        return TITLES

    def dexbook(self):
        return {"seen": [], "caught": [], "gens": {}, "total": 0}


class Lead(object):
    mon = {"num": 4, "info": {"name": "파이리", "level": 30}}
    look = None


class Visit(object):
    def __init__(self):
        self.v = {"partner": "집주인", "host": 2}
        self.went = []

    def my_lead_pet(self):
        return Lead()

    def go(self, friend_id, items, done=None):
        self.went.append((friend_id, items))
        if done:
            done({}, None)


class App(object):
    def __init__(self, root):
        self.root = root
        self.api = Api()
        self.visit = Visit()
        self.syncs = 0
        self.dex = None
        self.notes = []

    def request_sync(self):
        self.syncs += 1

    def notify(self, message):
        self.notes.append(message)


def ach(key, name, group="도감 수집", title=None, balls=0, got=False, value=0, target=50, hidden=False, desc=None):
    a = {"key": key, "group": group, "name": name, "desc": desc or "%s 설명" % name, "target": target,
         "title": title, "balls": balls, "hidden": hidden}
    if got:
        a["gotAt"] = "2026-10-02T00:10:00+00:00"
    else:
        a["value"] = value
    return a


PUBLIC = {
    "done": 2, "total": 5,
    "unlocks": {"unlock_7": True, "unlock_9": False},
    "achievements": [
        ach("dex_50", "50종", balls=5, got=True, desc="도감에 50종을 올린다."),
        ach("dex_400", "400종", title="도감 조사원", value=120, target=400,
            desc="포켓몬 400종을 잡아 도감에 올린다. 전설과 환상의 포켓몬도 센다."),
        ach("region_1", "관동 도감 완성", group="지방 도감", title="관동 도감 완성", value=100, target=146,
            desc="관동 지방의 포켓몬을 모두 잡는다."),
        ach("unlock_ultra", "울트라홀 개척자", group="해금", title="울트라홀 개척자", got=True, target=49,
            desc="울트라홀 해금 업적."),
        {"key": "hidden_nick", "group": "숨은 업적", "name": "???", "desc": "숨은 업적",
         "target": 1, "title": None, "balls": 0, "hidden": True, "value": 0},
    ],
}
TITLES = {"owned": 1, "total": 5, "season": 3, "seasonEnds": "2026-10-16", "titles": [
    {"id": "ach_dex_400", "name": "도감 조사원", "group": "도감 수집",
     "how": "포켓몬 400종을 잡아 도감에 올리기", "owned": False, "open": True, "value": 120, "target": 400},
    {"id": "ach_region_1", "name": "관동 도감 완성", "group": "지방 도감",
     "how": "관동 지방 포켓몬을 모두 잡기 (전설·환상 제외)", "owned": True, "open": True},
    {"id": "ach_hidden_midnight", "name": "???", "group": "숨은 업적",
     "how": "숨은 업적 - 달성하면 알 수 있다", "owned": False, "open": True},
    {"id": "s3_master", "name": "시즌 3 마스터볼", "group": "랭킹전 시즌 3",
     "how": "시즌 3 에서 마스터볼 티어(RP 600)에 오르기 - 시즌이 끝날 때 받는다", "owned": False, "open": True},
    {"id": "s2_super", "name": "시즌 2 슈퍼볼", "group": "지난 시즌 (다시 얻을 수 없음)",
     "how": "시즌 2 에서 슈퍼볼 티어(RP 150)에 오르기 - 시즌이 끝날 때 받는다", "owned": False, "open": False}]}


def canvas_texts(cv):
    out = []
    for i in cv.find_all():
        if cv.type(i) == "text":
            t = cv.itemcget(i, "text")
            if t:
                out.append(t)
    return out


def setup_sprite():
    path = sprite_png(os.path.join(os.environ["POKET_HOME"], "lead.png"))
    sprite_cache.ensure = lambda api, num, shiny=False: path


def main():
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errs = []
    root.report_callback_exception = lambda e, v, tb: errs.append("".join(__import__("traceback").format_exception(
        e, v, tb)))
    setup_sprite()
    from poketdesktop import ui_achievements as UA
    from poketdesktop import ui_visit
    from poketdesktop.skins.dp import achievements as DA
    from poketdesktop.skins.dp import visit as DV

    # ---------------- 1. 놀러 가기 ----------------
    print("=== 놀러 가기 (carry) ===")
    app = App(root)
    d = ui_visit.SendDialog(app, {"id": 2, "name": "집주인"})
    TBL.wait(root, lambda: d.items, 5)
    TBL.settle(root, 0.4)
    chk("DP 클래스로 뜬다 (기본 클래스의 자식)", type(d) is DV.ItemPicker and isinstance(d, ui_visit.ItemPicker),
        type(d))
    chk("들고 갈 수 있는 것만: 볼 · 지닌 도구 중 귀함까지 (몬스터볼은 흔함이라 들어간다, 돌 · 마스터볼 · 기합의띠는 빠진다)",
        set(d.bag) == {"POKEBALL", "GREATBALL", "ULTRABALL", "BLACKBELT"}, sorted(d.bag))
    chk("한도 액정", d.limit_text == "볼 0/5 · 지닌 도구 0/1", d.limit_text)
    chk("누가 가는지 (파티 맨 앞) · 도트", d.who_title.startswith("파이리") and d._thumb is not None,
        (d.who_title, d._thumb))
    chk("목록: 머리줄 + 도구 줄", [k for _h, (k, _v) in d.items_vl.rows].count("head") == 2
        and [k for _h, (k, _v) in d.items_vl.rows].count("item") == 4, d.items_vl.rows[:3])
    chk("  담은 것이 없으면 담은 판은 비어 있다", d.picked_vl.rows == [] and not d.plan)
    # 진짜 눌림: 목록의 하이퍼볼 줄
    idx = next(i for i, (_h, (k, v)) in enumerate(d.items_vl.rows) if k == "item" and v["id"] == "ULTRABALL")
    vc = d.items_vl.cv
    for _ in range(3):
        vc.event_generate("<Button-1>", x=30, y=d.items_vl.tops[idx] + 8)
        TBL.settle(root, 0.05)
    chk("줄을 누르면 하나씩 담기고 가진 것(2)보다 많이는 못 담는다", d.plan == {"ULTRABALL": 2}
        and "가진 만큼" in d.msg[0], (d.plan, d.msg))
    chk("  담은 판에 한 줄", len(d.picked_vl.rows) == 1)
    for _ in range(5):
        d.pick_item("GREATBALL")
    chk("볼은 합쳐서 5개까지", d.plan == {"ULTRABALL": 2, "GREATBALL": 3} and "볼은 5개까지" in d.msg[0]
        and d.msg[1] == U.DANGER, (d.plan, d.msg))
    d.pick_item("BLACKBELT")
    d.pick_item("BLACKBELT")
    TBL.settle(root, 0.1)
    chk("지닌 도구는 1개까지", d.plan.get("BLACKBELT") == 1 and "지닌 도구는 1개까지" in d.msg[0]
        and d.limit_text == "볼 5/5 · 지닌 도구 1/1", (d.plan, d.limit_text))
    # 담은 줄의 ▼ · 빼기 (진짜 눌림)
    pc = d.picked_vl.cv
    TBL.settle(root, 0.2)
    pi = d.order.index("GREATBALL")
    w = pc.winfo_width()
    from poketdesktop.skins.dp.visit import _geo
    dn, cnt, up, rm = _geo(w)
    pc.event_generate("<Button-1>", x=(dn[0] + dn[1]) // 2, y=d.picked_vl.tops[pi] + U.h(25))
    TBL.settle(root, 0.1)
    chk("  ▼ 를 누르면 하나 줄어든다", d.plan.get("GREATBALL") == 2 and d.limit_text == "볼 4/5 · 지닌 도구 1/1",
        (d.plan, d.limit_text))
    pc.event_generate("<Button-1>", x=(up[0] + up[1]) // 2, y=d.picked_vl.tops[pi] + U.h(25))
    TBL.settle(root, 0.1)
    chk("  ▲ 를 누르면 하나 는다", d.plan.get("GREATBALL") == 3, d.plan)
    bi = d.order.index("BLACKBELT")
    pc.event_generate("<Button-1>", x=(rm[0] + rm[1]) // 2, y=d.picked_vl.tops[bi] + U.h(25))
    TBL.settle(root, 0.1)
    chk("  빼기를 누르면 그 줄이 빠진다", "BLACKBELT" not in d.plan and len(d.picked_vl.rows) == 2
        and d.limit_text == "볼 5/5 · 지닌 도구 0/1", (d.plan, d.limit_text))
    texts = canvas_texts(d.cv)
    chk("  판에 안내글 · 담은 도구 제목이 있다", "들고 갈 도구" in texts and any("보따리" in t for t in texts), texts[:8])
    d.go()
    TBL.settle(root, 0.3)
    chk("'놀러 가기' 는 담은 것을 넘기고 창을 닫는다", app.visit.went == [(2, [{"id": "ULTRABALL", "count": 2},
                                                                              {"id": "GREATBALL", "count": 3}])]
        and not d.alive, app.visit.went)

    # ---------------- 2. 여기에 두기 ----------------
    print("\n=== 여기에 두기 (drop) ===")
    app.api.state_visit = {"partner": "집주인", "canGive": True,
                           "carry": [{"id": "GREATBALL", "kr": "슈퍼볼", "count": 2},
                                     {"id": "BLACKBELT", "kr": "검은띠", "count": 1}]}
    d2 = ui_visit.DropDialog(app)
    TBL.wait(root, lambda: d2.items, 5)
    TBL.settle(root, 0.4)
    chk("DP 클래스 · 들고 온 것만, 오늘 받을 수 있다", type(d2) is DV.ItemPicker and d2.bag == {"GREATBALL": 2, "BLACKBELT": 1}
        and d2.limit_text == "받을 수 있음", (d2.bag, d2.limit_text))
    chk("  담기 전에는 단추가 죽어 있다", not d2.go_btn.enabled)
    for _ in range(3):
        d2.pick_item("GREATBALL")
    chk("  들고 온 것(2)보다 많이는 못 담고, 담으면 단추가 산다", d2.plan == {"GREATBALL": 2} and d2.go_btn.enabled
        and "가진 만큼" in d2.msg[0], (d2.plan, d2.msg))
    chk("  보라 띠: 보따리 몇 개", d2.who_title == "보따리 2개", d2.who_title)
    d2.go()
    TBL.wait(root, lambda: not d2.alive, 5)
    chk("  두면 서버에 가고 가방을 새로 받는다", app.api.calls[-1] == ("drop", [{"id": "GREATBALL", "count": 2}])
        and app.syncs >= 1, app.api.calls)
    app.api.state_visit = {"partner": "집주인", "canGive": False,
                           "carry": [{"id": "BLACKBELT", "kr": "검은띠", "count": 1}]}
    d3 = ui_visit.DropDialog(app)
    TBL.wait(root, lambda: d3.items, 5)
    TBL.settle(root, 0.3)
    d3.pick_item("BLACKBELT")
    chk("친구가 오늘 받았으면 '이미 받음' · 담기지 않고 단추가 죽는다 · 알림", d3.limit_text == "이미 받음"
        and d3.limit_fg == U.DANGER and not d3.plan and not d3.go_btn.enabled and "오늘 이미" in d3.msg[0],
        (d3.limit_text, d3.plan, d3.msg))
    d3.close()
    app.api.state_visit = {"partner": "집주인", "canGive": True, "carry": []}
    d4 = ui_visit.DropDialog(app)
    TBL.wait(root, lambda: d4._empty_note != "불러오는 중...", 5)
    TBL.settle(root, 0.3)
    chk("들고 온 것이 없으면 목록 자리에 안내", d4._empty and "들고 온 도구가 없다" in d4._empty_note
        and any("들고 온 도구가 없다" in t for t in canvas_texts(d4.cv)), d4._empty_note)
    d4.close()
    chk("그리는 중에 난 예외가 없다 (도구 창)", not errs, errs[:1])

    # ---------------- 3. 업적 칸 ----------------
    print("\n=== 업적 칸 ===")
    host = tk.Toplevel(root)
    host.title("visit_host")
    host.geometry("900x640+40+40")
    U.install_wheel(host)
    p = UA.AchievementPanel(host, app)
    p.pack(fill="both", expand=True)
    chk("DP 클래스로 뜬다", type(p) is DA.AchievementPanel and isinstance(p, UA.AchievementPanel), type(p))
    p.reload()
    TBL.wait(root, lambda: p.data is not None, 5)
    TBL.settle(root, 0.4)
    secs = [v for _h, (k, v) in p.vl.rows if k == "sec"]
    cards = [v for _h, (k, v) in p.vl.rows if k == "card"]
    chk("갈래 띠 넷 · 카드 다섯", secs == ["도감 수집  1/2", "지방 도감  0/1", "해금  1/1", "숨은 업적  0/1"] and len(cards) == 5,
        (secs, len(cards)))
    chk("달성 수 액정", p.sum_text == "달성 2 / 5" and "달성 2 / 5" in canvas_texts(p.cv), p.sum_text)
    chk("  열린 해금 안내", "열림: 울트라홀" in canvas_texts(p.cv), canvas_texts(p.cv)[:6])
    chk("이룬 것은 날짜, 못 이룬 것은 진행 막대", [c["foot"] for c in cards if c["got"]] ==
        ["2026-10-02 달성", "2026-10-02 달성"] and [c["bar"] for c in cards if c["bar"]] == [(120, 400), (100, 146), (0, 1)],
        [(c["got"], c["foot"], c["bar"]) for c in cards])
    chk("숨은 업적은 ? 메달", [c["hidden"] for c in cards] == [False, False, False, False, True])
    drawn = canvas_texts(p.vl.cv)
    chk("그려진 글: 이름 · 설명 · 진행 수 · 보상", "50종" in drawn and "120 / 400" in drawn and any("칭호 「도감 조사원」" in t
                                                                                         for t in drawn), drawn[:14])
    # 창 폭을 줄이면 줄 높이를 다시 잡는다
    before = [h for h, (k, _v) in p.vl.rows if k == "card"]
    host.geometry("420x640+40+40")   # (v2 업적 카드가 촘촘해 420 이어야 설명이 접힌다)
    TBL.settle(root, 0.5)
    after = [h for h, (k, _v) in p.vl.rows if k == "card"]
    chk("창을 좁히면 줄 높이를 다시 잡는다 (글이 더 접힌다)", sum(after) > sum(before) and p._built_w == p.vl.cv.winfo_width(),
        (sum(before), sum(after)))
    host.geometry("900x640+40+40")
    TBL.settle(root, 0.4)
    chk("그리는 중에 난 예외가 없다 (업적 칸)", not errs, errs[:1])
    # 많을 때: 끝까지 굴러간다
    big = dict(PUBLIC)
    big["achievements"] = [ach("k%d" % i, "업적 %02d" % i, group="갈래 %d" % (i // 20), got=(i % 3 == 0), value=i,
                               target=100) for i in range(60)]
    big["total"] = 60
    big["done"] = 20
    app.api.achievements = lambda: big
    p.reload()
    TBL.wait(root, lambda: p.data is big or p.data.get("total") == 60, 5)
    TBL.settle(root, 0.4)
    vc = p.vl.cv
    chk("예순 줄 · 내용이 창보다 길다", p.vl.total > vc.winfo_height() * 2, (p.vl.total, vc.winfo_height()))
    lo, hi = vc.yview()
    chk("  처음엔 맨 위", lo == 0.0 and hi < 0.5, (lo, hi))
    x = vc.winfo_rootx() + 60
    y = vc.winfo_rooty() + 60
    for _ in range(6):
        host.event_generate("<MouseWheel>", delta=-120, rootx=x, rooty=y)
        root.update()
    chk("  휠을 내리면 굴러간다", vc.yview()[0] > 0.0, vc.yview())
    vc.yview_moveto(1.0)
    TBL.settle(root, 0.3)
    last_i = len(p.vl.rows) - 1
    bottom = p.vl.tops[last_i] + p.vl.rows[last_i][0]
    chk("  끝까지 굴리면 마지막 카드가 통째로 보인다", vc.yview()[1] >= 0.999 and "업적 59" in canvas_texts(vc)
        and bottom <= vc.canvasy(vc.winfo_height()) + 1, (vc.yview(), bottom, vc.canvasy(vc.winfo_height())))
    app.api.achievements = lambda: PUBLIC
    p.alive = False
    p.pack_forget()

    # ---------------- 4. 칭호 칸 ----------------
    print("\n=== 칭호 칸 ===")
    t = UA.TitlePanel(host, app)
    t.pack(fill="both", expand=True)
    chk("DP 클래스로 뜬다", type(t) is DA.TitlePanel and isinstance(t, UA.TitlePanel), type(t))
    t.reload()
    TBL.wait(root, lambda: t.data is not None, 5)
    TBL.settle(root, 0.4)
    cards = [v for _h, (k, v) in t.vl.rows if k == "card"]
    chk("가진 수 액정 · 안내", t.sum_text == "가진 칭호 1 / 5" and any("마이페이지" in s for s in canvas_texts(t.cv)),
        (t.sum_text, canvas_texts(t.cv)[:6]))
    chk("칭호 이름과 얻는 조건", [c["name"] for c in cards] == ["「도감 조사원」", "「관동 도감 완성」", "「???」", "「시즌 3 마스터볼」",
                                                       "「시즌 2 슈퍼볼」"]
        and any("400종" in c["desc"] for c in cards) and any("마스터볼 티어(RP 600)" in c["desc"] for c in cards),
        [c["name"] for c in cards])
    chk("  가진 칭호는 '가지고 있음', 지난 시즌은 '지금은 얻을 수 없음', 못 얻은 것은 진행 막대",
        [c["chip"][0] for c in cards if c["chip"]] == ["가지고 있음", "지금은 얻을 수 없음"]
        and [c["bar"] for c in cards if c["bar"]] == [(120, 400)], [(c["chip"], c["bar"]) for c in cards])
    chk("그리는 중에 난 예외가 없다 (칭호 칸)", not errs, errs[:1])
    t.alive = False
    host.destroy()

    # ---------------- 5. 도감 탭 ----------------
    print("\n=== 도감 탭에서 번갈아 보기 ===")
    from poketdesktop import ui_dex
    app2 = App(root)
    dw = ui_dex.DexWindow(app2)
    root.update()
    dw.toggle_achievements()
    TBL.wait(root, lambda: dw.ach is not None and dw.ach.data is not None, 5)
    TBL.settle(root, 0.3)
    chk("업적 단추를 누르면 DP 업적 칸이 격자 자리에 들어간다", type(dw.ach) is DA.AchievementPanel
        and dw.ach.f.winfo_manager() and not dw.dex_body.winfo_manager() and dw.ach_btn.text == "도감으로",
        (type(dw.ach), dw.ach_btn.text))
    dw.toggle_titles()
    TBL.wait(root, lambda: dw.titles is not None and dw.titles.data is not None, 5)
    TBL.settle(root, 0.3)
    chk("칭호 단추를 누르면 칭호 칸 · 업적 칸은 숨는다", type(dw.titles) is DA.TitlePanel and dw.titles.f.winfo_manager()
        and not dw.ach.f.winfo_manager() and dw.title_btn.text == "도감으로" and dw.ach_btn.text == "업적 2/5",
        (dw.title_btn.text, dw.ach_btn.text))
    dw.toggle_titles()
    TBL.settle(root, 0.2)
    chk("다시 누르면 격자", dw.dex_body.winfo_manager() and not dw.titles.f.winfo_manager())
    chk("그리는 중에 난 예외가 없다 (도감)", not errs, errs[:1])
    dw.close()

    # ---------------- 6. 업적 알림 ----------------
    print("\n=== 업적 알림 창 ===")
    shot = {}
    orig_wait = root.wait_window

    def spy_wait(win):
        root.update()
        win.update_idletasks()
        cvs = [w for w in win.winfo_children()[-1].winfo_children() if isinstance(w, tk.Canvas)]
        shot["t"] = " ".join(canvas_texts(cvs[0])) if cvs else ""
        shot["win"] = win
        shot["h"] = win.winfo_height()
        win.ok_btn.invoke() if hasattr(win, "ok_btn") else win.destroy()
    root.wait_window = spy_wait
    UA.announce(root, app, [ach("dex_400", "400종", title="도감 조사원", got=True)])
    chk("하나면 '업적 달성!' · 칭호 보상 · 마이페이지 안내", "업적 달성!" in shot["t"] and "도감 조사원" in shot["t"]
        and "마이페이지" in shot["t"], shot["t"][:120])
    chk("  확인 단추로 닫힌다", not shot["win"].winfo_exists())
    many = [ach("k%d" % i, "업적%d" % i, balls=5 if i % 2 else 0, title=None if i % 2 else "칭호%d" % i, got=True)
            for i in range(12)]
    UA.announce(root, app, many)
    chk("여럿이면 '지금까지의 기록으로 업적 12개' · '그 밖 4개' · 볼 보상", "지금까지의 기록으로 업적 12개" in shot["t"]
        and "그 밖 4개" in shot["t"] and "몬스터볼 5개" in shot["t"], shot["t"][:160])
    root.wait_window = orig_wait
    chk("그리는 중에 난 예외가 없다 (알림)", not errs, errs[:1])

    for w in root.winfo_children():
        if isinstance(w, tk.Toplevel):
            try:
                w.destroy()
            except tk.TclError:
                pass
    root.destroy()
    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
