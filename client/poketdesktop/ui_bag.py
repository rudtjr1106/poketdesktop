# -*- coding: utf-8 -*-
"""가방 창 — 가진 도구를 보고 포켓몬에게 쓴다.

왜 이렇게 만들었는지.

* 도구 목록만 보여주면 "이걸 누구한테 쓰지?" 에서 막힌다. 그래서 도구를
  고르는 순간 오른쪽에 **쓸 대상 목록**이 같이 뜬다. 창을 두 번 열 일이 없다.
* 진화의 돌만 38종이라 대부분은 지금 가진 포켓몬과 상관이 없다. 최종 판단은
  서버가 하지만(낮/밤 같은 조건이 있다), 화면에서도 도구의 evolves(한국어 종
  이름)와 포켓몬의 info.species 를 맞춰보고 **될 만한 대상을 밝게** 칠한다.
  아무 일도 안 일어나는 클릭을 줄이려는 것이다.
* 은색병뚜껑은 능력을 하나 골라야 한다. 그래서 대상을 고른 뒤에 능력 칸이
  열리고, 이미 31 이거나 이미 단련된 능력은 아예 눌리지 않는다. 서버도 같은
  것을 막지만, 눌러보고 거절당하는 것보다 미리 못 누르게 하는 편이 낫다.
* 목록에 놓는 도트는 **작업 스레드에서 그림까지 다 만들어 둔다.** 도트 한 장을
  만드는 데 픽셀을 파이썬으로 훑기 때문에(sprites.flatten_rgba) 마릿수만큼
  tk 스레드에서 돌리면 창이 눈에 띄게 멈춘다. tk 스레드에서는 PhotoImage 로
  감싸는 일만 한다.
* 휠은 창 하나가 받아서 포인터 밑의 목록으로 보낸다(U.install_wheel).
  이 창은 목록이 둘이라 어느 쪽을 굴릴지 그때그때 정해야 한다.
"""
import datetime
import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from common import deco as DECO
from common import held as H
from common import pokelogic as P
from common import tint as T
from common.korean import natural

from . import sprite_cache, sprites
from . import ui_box
from . import item_icons
from . import skins
from . import ui_common as U
from . import ui_loading
from . import ui_monfind

LIST_W = 292            # 왼쪽 도구 목록 폭
# 도구 목록 줄 세우기 (1.13.4, 게시판 #323 '도구가 많아져 정렬이 마구잡이 - 이름순 / 특성순'). 분류 머리줄은 그대로 두고
# 그 안을 이 순서로 세운다. 종류순은 지닌 도구를 하는 일(held.GROUPS)마다 머리줄로 나눈다.
ITEM_SORTS = (("name", "이름"), ("kind", "종류"), ("rarity", "등급"), ("count", "개수"))
RARITY_RANK = {"common": 1, "uncommon": 2, "rare": 3, "epic": 4, "legendary": 5}
ITEM_H = U.h(28)        # 도구 한 줄 높이 (글꼴 따라 늘어난다)
MON_H = U.h(34)         # 포켓몬 한 줄 높이
THUMB = 22              # 목록에 놓는 도트 높이 (다른 창과 겹치지 않는 값)

EV_STAT_MAX = 252       # 서버 config 와 같은 값 (스탯 하나당)
EV_TOTAL_MAX = 510      # 서버 config 와 같은 값 (여섯 개 합계)
HYPER_MIN_LEVEL = 50    # 병뚜껑을 받을 수 있는 최소 레벨

STAT_ROWS = [("hp", "HP"), ("atk", "공격"), ("def", "방어"),
             ("spa", "특수공격"), ("spd", "특수방어"), ("spe", "스피드")]
STAT_KR = dict(STAT_ROWS)

# 분류 — 실제로 쓸 수 있는 것부터 위로 올린다
CAT_ORDER = ["megastone", "zcrystal", "form", "held", "stone", "ev", "iv", "misc", "ball", "deco"]
CAT_KR = {"megastone": "메가스톤", "zcrystal": "Z크리스탈", "form": "폼 도구", "held": "지닌 도구",
          "stone": "진화의 돌", "ev": "노력치", "iv": "단련", "misc": "기타", "ball": "볼", "deco": "꾸미기"}
CAT_COLOR = {"megastone": "#a98bff", "zcrystal": "#ffd23c", "form": "#5fd3c6", "held": U.ACCENT,
             "stone": U.PINK, "ev": U.GOOD, "iv": U.SHINY, "misc": U.INFO, "ball": U.RED, "deco": "#ff8fc8"}

# /api/bag/use 가 받아주는 효과. 나머지(볼, 파는 물건)는 여기서 쓸 수 없다.
# "held" 는 use 가 아니라 /api/pokemon/{id}/hold 로 간다 - 대상을 고르는
# 흐름은 같아서 여기서 같이 다룬다.
# "form" (1.13) 은 폼 도구 - 고르는 도구(로토무카탈로그·운석)는 쓰기 전에 모습을 한 번 더 묻는다.
# "tmticket" (1.13.1) 은 랭크 시즌 보상인 기술머신 뽑기권 - 타입 확정은 쓰기 전에 타입을 묻는다.
# "deco" (버전 2) 는 꾸미기 - /api/deco/equip 으로 씌우고 뺀다. "decopick" 은 참가 묶음 선택권 (묶음을 고른다).
USABLE = ("ev", "iv", "level", "stone", "noevolve", "held", "shiny", "ticket", "form", "tmticket", "deco", "decopick")
# **대상 포켓몬이 없는 도구.** 고를 것이 없으니 목록을 띄우지 않고 바로 쓴다.
NO_TARGET = ("ticket", "tmticket", "decopick")

ROW_BG = "#10131c"      # 목록 한 줄 바탕
SEL_BG = "#2b2417"      # 고른 줄
GOOD_BG = "#14211a"     # 진화의 돌이 통하는 줄
PANEL = "#101623"       # 액자 안쪽


# ---------------------------------------------------------------- 서버 호출
def _takes(fn, name):
    try:
        import inspect
        return name in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def fetch_shop(api):
    """도구 설명 · 가방 · 지갑을 한 번에 받는다.

    /api/bag 은 개수만 주고 이름도 효과도 없다. 화면에는 설명이 필요하므로
    도구 명세가 같이 오는 /api/shop 을 쓴다.
    """
    fn = getattr(api, "shop", None)
    if fn is not None:
        return fn()
    return api._call("GET", "/api/shop")


def use_item(api, item_id, pid, stat, hour, form="", tm_type=""):
    """도구를 쓴다. 시각(hour)은 **이 PC 기준**으로 반드시 같이 보낸다.

    서버는 도커 안에서 UTC 로 돌기 때문에 사용자의 밤낮을 스스로 알 수 없다.
    (이브이의 밤 진화처럼 시각을 보는 조건이 있다.)
    form 은 폼 도구(1.13)에서만 - 고른 모습. tm_type 은 타입 확정 기술머신 뽑기권(1.13.1)에서만.
    """
    fn = getattr(api, "use_item", None)
    if fn is not None and _takes(fn, "hour") and (_takes(fn, "form") or not form) \
            and (_takes(fn, "tm_type") or not tm_type):
        kw = {"hour": hour}
        if form:
            kw["form"] = form
        if tm_type:
            kw["tm_type"] = tm_type
        return fn(item_id, pid, stat or "", **kw)
    body = {"item": item_id, "pokemon": pid, "stat": stat or "", "hour": hour}
    if form:
        body["form"] = form
    if tm_type:
        body["type"] = tm_type
    return api._call("POST", "/api/bag/use", body)


def form_targets(item, mon):
    """이 폼 도구가 이 포켓몬에게 해 줄 수 있는 모습들 (서버가 도구마다 실어 보낸 forms 중 그 종의 것)."""
    return [t for t in (item.get("forms") or []) if t.get("of") == (mon or {}).get("species")]


def mega_fits(dex, item, mon):
    """이 포켓몬이 이 메가스톤으로 메가진화하나. 메가스톤이 아니거나 도감이 없으면 True (서버가 본다)."""
    if (item or {}).get("cat") != "megastone" or dex is None:
        return True
    forms = (getattr(dex, "mega_of", None) or {}).get((mon or {}).get("species")) or []
    return any(f.get("megaStone") == item["id"] for f in forms)


# ---------------------------------------------------------------- 설명 만들기
# ---------------------------------------------------------------- 꾸미기 (버전 2)
# 꾸미기는 서버의 가방(/api/shop 의 bag)이 아니라 /api/deco 에 있다. 가방은 그것을 '꾸미기' 분류의 도구로
# 섞어 보여 준다 (이름 'deco:<열쇠>', 그림은 deco_art - item_icons 가 서버에 안 묻는다). 팔 수 없다 (sell 0).
def fetch_deco(api):
    """꾸미기 목록 (/api/deco). 옛 서버거나 실패하면 None - 가방은 꾸미기 없이 연다."""
    fn = getattr(api, "deco_state", None)
    if fn is None:
        return None
    try:
        return fn()
    except Exception:                                       # noqa: BLE001
        return None


def deco_items(state, names=None):
    """/api/deco 의 답 -> (도구 명세 목록, {도구ID: 개수}, {포켓몬id: {칸: 열쇠}}). 가진 것만.

    names 는 {포켓몬id: 이름} - '쓰는 포켓몬' 을 설명에 적는다."""
    from .deco_art import ITEM_PREFIX
    if not state:
        return [], {}, {}
    names = names or {}
    worn = {}
    for pid, d in (state.get("worn") or {}).items():
        try:
            worn[int(pid)] = DECO.clean(d)
        except (TypeError, ValueError):
            pass
    items, bag = [], {}
    for it in state.get("items") or []:
        key = it.get("key")
        if not it.get("owned") or key not in DECO.DECOS:
            continue
        slot = DECO.slot_of(key)
        by = it.get("wornBy")
        who = names.get(by) if by else None
        desc = "%s (%s 칸) %s" % (DECO.name(key), DECO.SLOT_KR.get(slot, slot), DECO.DECOS[key].get("desc", ""))
        if by:
            desc += "\n지금 %s 이(가) 쓰고 있다." % (who or "다른 포켓몬")
        iid = ITEM_PREFIX + key
        items.append({"id": iid, "kr": DECO.name(key), "en": key, "cat": "deco", "sell": 0, "note": desc,
                      "effect": {"kind": "deco", "deco": key, "slot": slot, "wornBy": by}})
        bag[iid] = 1
    picks = int(state.get("picks") or 0)
    if picks > 0:
        iid = ITEM_PREFIX + DECO.PICK
        items.append({"id": iid, "kr": DECO.PICK_KR, "en": DECO.PICK, "cat": "deco", "sell": 0,
                      "note": "길드전 참가 보상. 참가 묶음 (%s) 가운데 하나를 고른다. 고른 뒤에는 바꿀 수 없다."
                      % " · ".join(DECO.BUNDLE_KR[b] for b in DECO.JOIN_CHOICES),
                      "effect": {"kind": "decopick", "choices": state.get("choices") or []}})
        bag[iid] = picks
    return items, bag, worn


def item_desc(item):
    """도구 설명 한 줄. items.json 에 설명 문구가 없어서 effect 로 만든다.

    볼은 서버가 만들어 보낸 note 를 그대로 쓴다. 조건(밤인지, 무게가 얼마인지,
    이미 잡아본 종인지)을 아는 쪽은 서버뿐이라, 여기서 다시 만들면 화면에
    쓰인 말과 실제 판정이 어긋난다.
    """
    if item.get("note"):
        return item["note"]
    eff = item.get("effect") or {}
    kind = eff.get("kind")
    if kind == "ev":
        stat = STAT_KR.get(eff.get("stat"), "?")
        n = int(eff.get("amount", 0))
        if n >= 0:
            return ("%s 노력치가 %d 오른다. 스탯 하나당 %d, 여섯 개 합쳐 %d 까지."
                    % (stat, n, EV_STAT_MAX, EV_TOTAL_MAX))
        return "%s 노력치가 %d 내려간다." % (stat, abs(n))
    if kind == "iv":
        if int(eff.get("count", 1)) >= 6:
            return ("여섯 능력을 한꺼번에 최고까지 단련한다. Lv.%d 부터 받을 수 있다."
                    % HYPER_MIN_LEVEL)
        return ("고른 능력 하나를 최고(%d)까지 단련한다. Lv.%d 부터 받을 수 있다."
                % (P.IV_MAX, HYPER_MIN_LEVEL))
    if kind == "level":
        return ("레벨이 %d 오른다. 조건이 맞으면 그 자리에서 진화한다."
                % int(eff.get("amount", 1)))
    if kind == "stone":
        who = item.get("evolves") or []
        if not who:
            out = "특정 포켓몬을 진화시키는 돌이다."
        elif len(who) > 6:
            out = "%s 외 %d종이(가) 진화한다." % (", ".join(who[:6]),
                                            len(who) - 6)
        else:
            out = "%s이(가) 진화한다." % ", ".join(who)
        # **지닐 수도 있는 돌이 넷 있다** (예리한손톱·예리한이빨·
        # 왕의징표석·금속코트). 진화 얘기만 적어 두면 배틀에서
        # 무슨 일을 하는지 가방에서는 알 길이 없다.
        if item.get("holdable") and item.get("desc"):
            out += "\n\n지니게 하면: " + item["desc"]
            if item.get("heldNote"):
                out += "\n" + item["heldNote"]
        return out
    if kind == "noevolve":
        return "진화를 막는다. 한 번 더 쓰면 다시 진화할 수 있게 된다."
    if kind == "shiny":
        return (item.get("desc") or "먹이면 이로치가 된다.") + \
            "\n\n랭크 시즌 보상으로만 받는다. 한 번 먹이면 되돌릴 수 없다."
    if kind == "held":
        # 본가 설명 그대로 (서버가 items.json 에서 실어 보낸다)
        out = item.get("desc") or "포켓몬에게 지니게 하는 도구다. 배틀에서 효과가 난다."
        # 본가 문장은 "위력이 올라간다" 까지만 있다. 몇 배인지는 서버가 붙여 보낸다.
        if item.get("heldNote"):
            out += "\n\n" + item["heldNote"]
        return out
    if kind == "form":
        return form_desc(item)
    if kind == "ticket":
        out = item.get("desc") or "쓰면 확률로 알을 받는다."
        pct = int(round(float(eff.get("chance") or 0) * 100))
        if pct:
            out += "\n\n당첨 확률 %d%%. 꽝이어도 표는 없어진다." % pct
        return out
    if kind == "tmticket":
        out = item.get("desc") or "아직 없는 기술머신 하나가 나온다."
        return out + ("\n\n랭크 시즌 보상으로만 받는다. 가진 기술머신은 나오지 않는다 - "
                      "뽑을 것이 없으면 쓸 수 없고 표는 남는다.")
    if kind == "ball":
        return "야생 포켓몬을 만났을 때 던지는 볼이다. 가방에서는 쓸 수 없다."
    if kind == "sell":
        return "쓸 데는 없지만 상점에 팔면 값을 쳐준다."
    return "아직 쓸 수 없는 도구다."


def form_desc(item):
    """폼 도구 설명: 본가 설명 + 누가 어떤 모습이 되는지 + 쓰면 어떻게 되는지."""
    return (item.get("desc") or "포켓몬에게 쓰면 모습이 바뀐다.") + "\n\n" + form_note(item)


def form_note(item):
    """폼 도구의 덧말: 누가 어떤 모습이 되는지 + 쓰면 어떻게 되는지 (상점도 이것을 쓴다)."""
    eff = item.get("effect") or {}
    out = ""
    tg = item.get("forms") or []
    by = {}
    for t in tg:
        by.setdefault(t.get("ofKr"), []).append(t.get("formKr"))
    lines = ["%s → %s" % (who, " · ".join(fk)) for who, fk in by.items()]
    if lines:
        out += "\n".join(lines) + "\n\n"
    if eff.get("consume"):
        out += "쓰면 없어진다."
    elif len(tg) > 1 and len(set(t.get("of") for t in tg)) == 1:
        out += "쓸 때 모습을 고른다. '원래 모습'을 고르면 되돌아온다. 도구는 없어지지 않는다."
    else:
        out += "한 번 더 쓰면 원래 모습으로 돌아온다. 도구는 없어지지 않는다."
    return out


def target_hint(item):
    """대상 목록 위에 붙일 한 줄 안내."""
    kind = (item.get("effect") or {}).get("kind")
    if kind == "stone":
        return "이 돌이 통하는 포켓몬을 밝게 표시했다"
    if kind == "iv":
        return "Lv.%d 부터 단련할 수 있다" % HYPER_MIN_LEVEL
    if kind == "ev":
        return "스탯당 %d · 합계 %d 까지" % (EV_STAT_MAX, EV_TOTAL_MAX)
    if kind == "level":
        return "레벨이 오르면서 기술도 배운다"
    if kind == "noevolve":
        return "한 마리씩 껐다 켰다 한다"
    if kind == "shiny":
        return "이미 이로치인 포켓몬에게는 못 쓴다"
    if kind == "held":
        return "한 마리에 하나. 이미 지닌 것은 가방으로 돌아온다"
    if kind == "form":
        return "이 도구가 통하는 포켓몬을 밝게 표시했다"
    if kind == "deco":
        return "한 마리에 칸마다 하나. 다른 포켓몬이 쓰던 것이면 옮겨 온다"
    return ""


def unusable_note(item):
    """여기서는 못 쓰는 도구에게 해줄 말."""
    eff = item.get("effect") or {}
    if eff.get("kind") == "ball":
        return "볼은 야생 포켓몬을 만났을 때 던진다.\n가방에서는 쓸 수 없다."
    if eff.get("kind") == "sell":
        return ("포켓몬에게 쓸 수 있는 도구가 아니다.\n"
                "상점에 팔면 한 개에 %d원을 받는다." % int(item.get("sell", 0)))
    return "이 도구는 아직 쓸 수 없다."


def _scrollable(cv):
    """이 캔버스가 실제로 굴러갈 데가 있나."""
    try:
        lo, hi = cv.yview()
        return (hi - lo) < 0.999
    except Exception:                                       # noqa: BLE001
        return False


# ---------------------------------------------------------------- 조각 위젯
def _scroller(parent, bg):
    """세로로 굴러가는 빈 영역을 만든다. (canvas, inner) 를 돌려준다.

    내용이 화면보다 짧으면 **스크롤할 게 없어야 한다.** bbox 를 그대로
    넣으면, 도구가 두 개뿐인데도 스크롤바가 움직이고 빈 화면이 보인다.
    포켓몬 관리 창에서 이미 같은 것을 고쳤다.

    맞추는 일은 U.scroll_fitter 가 **몰아서 한 번** 한다. 예전에는 여기서
    <Configure> 마다 update_idletasks 로 배치를 억지로 끝내고 쟀는데, 그게
    또 <Configure> 를 불러 제 발로 되돌아왔다. 기술머신 358줄을 그리는
    2.6초 중 2.3초가 이 한 줄이었다. 줄을 담자마자 굴려야 하면
    canvas.scroll_fit.fit_now() 를 부른다.
    """
    holder = tk.Frame(parent, bg=bg)
    holder.pack(fill="both", expand=True)
    cv = tk.Canvas(holder, bg=bg, highlightthickness=0, bd=0)
    sb = ttk.Scrollbar(holder, orient="vertical", command=cv.yview)
    cv.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    cv.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(cv, bg=bg)
    wid = cv.create_window((0, 0), window=inner, anchor="nw")
    cv.scroll_fit = U.scroll_fitter(cv, inner, wid)
    return cv, inner


SEP = "#161a24"          # 줄 사이의 금
HEAD_H = U.h(26)


class HeadRow(object):
    """도구 목록의 분류 머리줄 ('지닌 도구 · 12종'). 아래에 금 하나."""

    def __init__(self, parent):
        self.f = tk.Frame(parent, bg=U.LINE)
        self.body = tk.Frame(self.f, bg=U.INK)
        self.body.place(x=0, y=0, relwidth=1.0, height=HEAD_H)
        self.mark = tk.Frame(self.body, bg=U.ACCENT, width=3, height=U.h(11))
        self.mark.place(x=12, rely=0.5, anchor="w")
        self.label = tk.Label(self.body, text="", bg=U.INK, fg=U.FG_DIM, font=U.FONT_LABEL)
        self.label.place(x=21, rely=0.5, anchor="w")

    def bind(self, data):
        """data = (분류, 종 수) 또는 (분류, 종 수, 종류) - 종류순에서 지닌 도구를 나눈 머리줄."""
        cat, n = data[0], data[1]
        sub = data[2] if len(data) > 2 else None
        self.mark.configure(bg=CAT_COLOR.get(cat, U.ACCENT))
        self.label.configure(text=("%s · %s · %d종" % (CAT_KR.get(cat, cat), sub, n)) if sub
                             else "%s · %d종" % (CAT_KR.get(cat, cat), n))


class ItemRow(object):
    """왼쪽 도구 목록 한 줄 — 그림(없으면 분류 색점) · 이름 · 개수. 아래에 금 하나.

    **줄 하나가 여러 도구를 돌아가며 보여 준다** (U.VirtualList - 화면에 보이는 만큼만 만든다).
    무엇을 보여 줄지는 bind 가 정하고, 개수와 고름은 가방 창(win)의 값을 읽는다.
    """

    def __init__(self, parent, win):
        self.win = win
        self.item = None
        self.selected = False
        self.usable = False
        self.f = tk.Frame(parent, bg=SEP)                # 아래 한 줄이 금으로 남는다
        self.body = tk.Frame(self.f, bg=ROW_BG, cursor="hand2")
        self.body.place(x=0, y=0, relwidth=1.0, height=ITEM_H)
        self.mark = tk.Frame(self.body, bg=ROW_BG, width=3)
        self.mark.place(x=0, y=0, relheight=1.0)
        # 도구 그림. 아직 못 받았으면 분류 색점으로 대신한다 (bind 가 둘 중 하나를 놓는다).
        self.icon = tk.Label(self.body, bg=ROW_BG, bd=0)
        self.dot = tk.Frame(self.body, bg=U.BG3, width=5, height=U.h(5))
        self.name = tk.Label(self.body, text="", bg=ROW_BG, fg=U.FG, font=U.FONT_S, anchor="w")
        self.name.place(x=32, rely=0.5, anchor="w")
        self.count = tk.Label(self.body, text="", bg=ROW_BG, fg=U.FG_DIM, font=U.FONT_XS, anchor="e")
        self.count.place(relx=1.0, x=-12, rely=0.5, anchor="e")
        self._art = None                                 # 지금 놓인 것: "icon" | "dot"
        for w in (self.body, self.icon, self.dot, self.name, self.count):
            w.bind("<Button-1>", self._click)
            w.bind("<Enter>", self._in)
            w.bind("<Leave>", self._out)

    def bind(self, item):
        self.item = item
        self.usable = (item.get("effect") or {}).get("kind") in USABLE
        ph = item_icons.photo(item["id"], 20)
        if ph is not None:
            self.icon.configure(image=ph)
            self.icon.image = ph
            if self._art != "icon":
                self.dot.place_forget()
                self.icon.place(x=8, rely=0.5, anchor="w")
                self._art = "icon"
        else:
            self.dot.configure(bg=CAT_COLOR.get(item.get("cat"), U.BG3))
            if self._art != "dot":
                self.icon.place_forget()
                self.dot.place(x=13, rely=0.5, anchor="w")
                self._art = "dot"
        self.name.configure(text=item["kr"])
        self.count.configure(text="%d개" % self.win.bag.get(item["id"], 0),
                             fg=U.FG_DIM if self.usable else U.FG_FAINT)
        self.selected = (item["id"] == self.win.item_id)
        self._look()

    def _click(self, _e):
        if self.item is not None:
            self.win.pick_item(self.item["id"])

    def _paint(self, bg, mark):
        self.body.configure(bg=bg)
        self.mark.configure(bg=mark)
        for w in (self.name, self.count, self.icon):
            w.configure(bg=bg)

    def _look(self):
        if self.selected:
            self._paint(SEL_BG, U.ACCENT)
            self.name.configure(fg=U.ACCENT_TEXT, font=U.FONT_B)
        else:
            self._paint(ROW_BG, ROW_BG)
            self.name.configure(fg=U.FG if self.usable else U.FG_FAINT, font=U.FONT_S)

    def _in(self, _e):
        if not self.selected:
            self._paint(U.BG2, U.LINE)

    def _out(self, _e):
        if not self.selected:
            self._paint(ROW_BG, ROW_BG)


class MonRow(object):
    """'누구에게 쓸까?' 목록 한 줄 — 왼쪽에 **실제 도트**를 작게 놓는다. 아래에 금 하나.

    도트 자리는 그림이 없어도 폭이 흔들리지 않게 고정 크기 액자에 넣는다.

    **줄 하나가 여러 포켓몬을 돌아가며 보여 준다** (U.VirtualList). bind 가 그 포켓몬의 이름·레벨·
    도트와, 가방 창(win)이 들고 있는 것 - 고른 도구 기준의 상태(_states), 고름(mon_id) - 을 칠한다.
    """

    def __init__(self, parent, win):
        self.win = win
        self.mon = None
        self.selected = False
        self.good = False
        self.blocked = False
        self.note_text = ""
        self.photo = None
        self.f = tk.Frame(parent, bg=SEP)                # 아래 한 줄이 금으로 남는다
        self.body = tk.Frame(self.f, bg=ROW_BG, cursor="hand2")
        self.body.place(x=0, y=0, relwidth=1.0, height=MON_H)
        self.body.pack_propagate(False)
        self.mark = tk.Frame(self.body, bg=ROW_BG, width=3)
        self.mark.place(x=0, y=0, relheight=1.0)

        self.frame_art = tk.Frame(self.body, bg=ROW_BG, width=30, height=MON_H)
        self.frame_art.pack_propagate(False)
        self.frame_art.pack(side="left", padx=(9, 0))
        self.art = tk.Label(self.frame_art, bg=ROW_BG)
        self.art.pack(expand=True)
        self.name = tk.Label(self.body, text="", bg=ROW_BG, fg=U.FG, font=U.FONT_S, anchor="w", width=13)
        self.name.pack(side="left", padx=(7, 0))
        self.lv = tk.Label(self.body, text="", bg=ROW_BG, fg=U.FG_DIM, font=U.FONT_XS, anchor="w", width=6)
        self.lv.pack(side="left")
        self.sub = tk.Label(self.body, text="", bg=ROW_BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w")
        self.sub.pack(side="left", padx=(4, 0))
        self.note = tk.Label(self.body, text="", bg=ROW_BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="e")
        self.note.pack(side="right", padx=(6, 12))

        self.cells = [self.frame_art, self.art, self.name, self.lv, self.sub, self.note]
        for w in [self.body] + self.cells:
            w.bind("<Button-1>", self._click)
            w.bind("<Enter>", self._in)
            w.bind("<Leave>", self._out)

    def bind(self, mon):
        self.mon = mon
        info = mon.get("info") or {}
        name = info.get("name", mon.get("species", "?"))
        if mon.get("shiny"):
            name = "★ " + name
        self.name.configure(text=name)
        self.lv.configure(text="Lv.%d" % mon.get("level", 0))
        sub = info.get("species", "") if info.get("name") != info.get("species") else ""
        if mon.get("onDesktop"):
            sub = (sub + " · 따라다님").strip(" ·")
        self.sub.configure(text=sub)
        # 도트. 참조를 들고 있지 않으면 그림이 사라진다. 없으면 지난 포켓몬의 것을 걷는다.
        self.photo = self.win.photos.get(mon["id"])
        self.art.configure(image=self.photo if self.photo is not None else "")
        good, blocked, note, color = self.win._states.get(mon["id"]) or (False, False, "", U.FG_FAINT)
        self.good, self.blocked, self.note_text = good, blocked, note
        self.note.configure(text=note, fg=color)
        self.body.configure(cursor="" if blocked else "hand2")
        self.selected = (mon["id"] == self.win.mon_id)
        self.repaint()

    def _click(self, _e):
        if self.mon is not None:
            self.win.pick_mon(self.mon["id"])

    def _bg(self):
        if self.selected:
            return SEL_BG, U.ACCENT
        if self.good:
            return GOOD_BG, U.GOOD
        return ROW_BG, ROW_BG

    def _fill(self, bg):
        self.body.configure(bg=bg)
        for w in self.cells:
            w.configure(bg=bg)

    def repaint(self):
        bg, mark = self._bg()
        self._fill(bg)
        self.mark.configure(bg=mark)
        if self.blocked:
            fg = U.FG_FAINT
        elif self.selected:
            fg = U.ACCENT_TEXT
        elif self.mon is not None and self.mon.get("shiny"):
            fg = U.SHINY
        else:
            fg = U.FG
        self.name.configure(fg=fg, font=U.FONT_B if self.selected else U.FONT_S)

    def _in(self, _e):
        if not self.selected:
            self._fill(U.BG2 if not self.good else "#1b2b21")

    def _out(self, _e):
        if not self.selected:
            self.repaint()


# ---------------------------------------------------------------- 가방 창
def bag_title(inner, switch=None):
    """가방 탭의 머리 왼쪽 — 가방 그림, '가방', 그리고 [도구 | 기술머신] 고르기.

    도구 칸과 기술머신 칸(ui_tms)이 같은 것을 같은 자리에 그린다. 그래야 칸을
    오갈 때 고르는 단추가 제자리에 있다 (1.8.0 에서 두 탭을 하나로 합쳤다).
    switch 는 단추를 만들어 주는 함수다 (ui_bag_tabs). 없으면 그리지 않는다.
    """
    # 가방 아이콘 — 몬스터볼 대신 여기서만 쓰는 그림이라 직접 그린다
    cv = tk.Canvas(inner, width=28, height=28, bg=U.BG2,
                   highlightthickness=0, bd=0)
    cv.pack(side="left", pady=17)
    cv.create_arc(9, 2, 19, 14, start=0, extent=180, style="arc",
                  outline=U.INK, width=3)
    cv.create_rectangle(3, 9, 25, 25, fill=U.ACCENT, outline=U.INK, width=2)
    cv.create_rectangle(3, 14, 25, 18, fill=U.RED, outline="")
    cv.create_rectangle(11, 13, 17, 19, fill="#f4f6fb", outline=U.INK,
                        width=1)
    tk.Label(inner, text="가방", bg=U.BG2, fg=U.FG,
             font=(U.FAMILY_BLACK, U.pt(15))).pack(side="left", padx=(12, 12))
    if switch:
        switch(inner).pack(side="left", padx=(0, 12))


@skins.skinnable
class BagWindow(object):
    def __init__(self, root, app, parent=None, switch=None):
        self.root = root
        self.app = app
        self.alive = True
        self._switch = switch    # 가방 탭 안의 [도구 | 기술머신] (ui_bag_tabs)

        self.items = []          # /api/shop 이 준 도구 명세
        self.bag = {}            # {도구ID: 개수}
        self.money = 0
        self.mons = []
        self.photos = {}         # {포켓몬id: PhotoImage} — 한 번 만들면 계속 쓴다
        self.item_id = None
        self.mon_id = None
        self.stat = None         # 병뚜껑으로 단련할 능력
        self.stat_needed = False
        self._pending = None     # 다시 불러온 뒤에 띄울 말
        self._wait = None        # 여는 중 표시
        self._states = {}        # {포켓몬id: (good, blocked, note, color)} — 고른 도구 기준
        self._mon_ids = set()
        self._view = []          # 오른쪽 목록에 보이는 포켓몬 - 찾는 말로 거르고 줄 세운 것 (1.13.1)
        self.tm_left = None      # {타입: 아직 없는 기술머신 수} - 타입 확정 뽑기권이 있을 때만 온다 (1.13.1)
        self.deco_worn = {}      # {포켓몬id: {칸: 열쇠}} - 꾸미기 (버전 2, deco_items)
        self.item_sort = "name"  # 도구 목록 순서 (ITEM_SORTS). 다시 불러와도 그대로다 (1.13.4)

        # parent 가 있으면 탭 안의 한 칸으로, 없으면 지금까지처럼 창으로.
        self.win = U.panel(parent, root, "포스크탑 — 가방",
                           1000, 664, 950, 600, self.close)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        if not U.is_embedded(self.win):
            # 탭으로 들어갈 때는 허브가 이미 걸어 두었다.
            U.install_wheel(self.win)

        self._build()
        self.reload()

    # ---------------- 그리기 ----------------
    # 화면 테마(skins/)는 이 아래 _build 와 _paint_* · _show_* · _repaint_* 만 갈아 끼운다 - 서버 호출과
    # 판정(어느 도구를 누구에게 쓸 수 있나, 단추를 켤까)은 이 창의 것을 그대로 쓴다.
    def _build(self):
        self._header()
        self._bottom()
        body = tk.Frame(self.win, bg=U.BG)
        body.pack(fill="both", expand=True)
        self._items_pane(body)
        self._detail_pane(body)

    # ---------------- 머리 ----------------
    def _header(self):
        h = tk.Frame(self.win, bg=U.BG2, height=U.h(62))
        h.pack(fill="x")
        h.pack_propagate(False)
        inner = tk.Frame(h, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16)

        bag_title(inner, self._switch)
        self.count_label = tk.Label(inner, text="", bg=U.BG2, fg=U.FG_FAINT,
                                    font=U.FONT_S)
        self.count_label.pack(side="left")

        # **pady 를 주지 않는다.** 머리줄 62 에 단추(32+그림자 4)+30 이면 윈도우에서
        # 4px 눌린다 (레이드·도감 머리줄에서 겪었다). 여백 없이도 세로 가운데에 놓인다.
        U.ghost_button(inner, "새로고침", self.reload,
                       height=32).pack(side="right")
        purse = tk.Frame(inner, bg=U.INK, highlightthickness=2,
                         highlightbackground=U.LINE)
        purse.pack(side="right", padx=(0, 10))
        tk.Label(purse, text="소지금", bg=U.INK, fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(side="left", padx=(10, 6), pady=4)
        self.money_label = tk.Label(purse, text="0원", bg=U.INK, fg=U.ACCENT,
                                    font=U.FONT_B)
        self.money_label.pack(side="left", padx=(0, 10))
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x")

    # ---------------- 왼쪽: 가진 도구 ----------------
    def _items_pane(self, parent):
        wrap = tk.Frame(parent, bg=U.BG, width=LIST_W)
        wrap.pack(side="left", fill="y")
        wrap.pack_propagate(False)

        head = tk.Frame(wrap, bg=U.INK, height=U.h(26))
        head.pack(fill="x")
        head.pack_propagate(False)
        U.marker_label(head, "가진 도구", bg=U.INK).pack(side="left", padx=12,
                                                     pady=6)
        tk.Frame(wrap, bg=U.LINE, height=U.h(2)).pack(fill="x")
        # 찾기 · 줄 세우기 (1.13.4, 게시판 #323). 찾는 말은 trace 로 듣는다 - 한글 조합 중인 글자를 놓치지 않게.
        tools = tk.Frame(wrap, bg=U.BG)
        tools.pack(fill="x", padx=10, pady=(8, 6))
        self.item_findrow = tk.Frame(tools, bg=U.BG)
        self.item_findrow.pack(fill="x")
        tk.Label(self.item_findrow, text="찾기", bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS).pack(side="left")
        self.item_q = tk.StringVar()
        self.item_find = U.entry(self.item_findrow, self.item_q, width=10)
        self.item_find.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.item_sortrow = tk.Frame(tools, bg=U.BG)
        self.item_sortrow.pack(fill="x", pady=(6, 0))
        self.item_seg = U.Segmented(self.item_sortrow, ITEM_SORTS, self.item_sort, self.set_item_sort)
        self.item_seg.frame.pack(side="left")
        self.item_q.trace_add("write", lambda *_a: self._items_changed())
        tk.Frame(wrap, bg=U.LINE, height=U.h(1)).pack(fill="x")
        # **보이는 줄만 만든다** (U.VirtualList). 도구가 300종이어도 위젯은 화면만큼이다 -
        # 예전에는 줄을 전부 만들어서 열 때와 도구를 쓸 때마다 몇 초씩 끊겼다.
        self.item_vl = U.VirtualList(wrap, {
            "head": (HEAD_H + U.h(1), HeadRow),
            "item": (ITEM_H + U.h(1), lambda p: ItemRow(p, self))}, bg=U.BG)
        self.item_vl.pack(fill="both", expand=True)
        self.item_canvas = self.item_vl.canvas
        self.item_empty = tk.Frame(wrap, bg=U.BG)        # 가방이 비었을 때 목록 대신
        tk.Label(self.item_empty, text="가방이 비어 있다.", bg=U.BG,
                 fg=U.FG_DIM, font=U.FONT_S).pack(pady=(34, 4))
        tk.Label(self.item_empty, text="야생 포켓몬을 잡거나 배틀에서\n도구를 주울 수 있다.",
                 bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, justify="center").pack()
        # 찾는 말에 맞는 도구가 없을 때 목록 대신 (1.13.4)
        self.item_nomatch = tk.Label(wrap, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S,
                                     wraplength=LIST_W - 40, justify="center")

    # ---------------- 오른쪽: 설명과 대상 ----------------
    def _detail_pane(self, parent):
        d = tk.Frame(parent, bg=U.BG2)
        d.pack(side="right", fill="both", expand=True)
        tk.Frame(d, bg=U.LINE2, width=2).place(x=0, y=0, relheight=1.0)
        p = tk.Frame(d, bg=U.BG2)
        p.pack(fill="both", expand=True, padx=(18, 16), pady=13)

        head = tk.Frame(p, bg=U.BG2)
        head.pack(fill="x")
        self.i_name = tk.Label(head, text="도구를 고르세요", bg=U.BG2,
                               fg=U.ACCENT_TEXT, font=(U.FAMILY_BLACK, U.pt(16)))
        self.i_name.pack(side="left")
        self.i_cat = U.chip(head, "", U.BG3, fg=U.FG_DIM)
        self.i_cat.pack(side="left", padx=(10, 0), pady=5)
        self.i_count = tk.Label(head, text="", bg=U.BG3, fg=U.FG, font=U.FONT_B,
                                padx=9, pady=2, highlightthickness=2,
                                highlightbackground=U.LINE2)
        self.i_count.pack(side="right")

        self.i_desc = tk.Label(p, text="왼쪽에서 도구를 고르면 여기에 설명이 뜬다.",
                               bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w",
                               justify="left", wraplength=580)
        self.i_desc.pack(fill="x", pady=(7, 0))

        self._stat_box(p)

        # 대상 목록
        lhead = tk.Frame(p, bg=U.BG2)
        lhead.pack(fill="x", pady=(12, 5))
        U.marker_label(lhead, "누구에게 쓸까?", bg=U.BG2).pack(side="left")
        self.t_hint = tk.Label(lhead, text="", bg=U.BG2, fg=U.FG_FAINT,
                               font=U.FONT_XS)
        self.t_hint.pack(side="right")
        # 찾기·줄 세우기 (1.13.1). 도구를 바꿔도 찾는 말과 순서는 그대로다.
        self.find = ui_monfind.FindBar(p, U.BG2, self._find_changed)
        self.find.frame.pack(fill="x", pady=(0, 6))

        frame = U.framed(p, bg=ROW_BG, border=U.LINE)
        frame.pack(fill="both", expand=True)
        # 여기도 보이는 줄만 만든다. 포켓몬이 수백 마리면 줄을 다 만든 목록은 굴릴 때마다 끊겼다.
        self.mon_vl = U.VirtualList(frame, {"mon": (MON_H + U.h(1), lambda p: MonRow(p, self))},
                                    bg=ROW_BG)
        self.mon_vl.pack(fill="both", expand=True)
        self.mon_canvas = self.mon_vl.canvas
        self._mon_list_on = True                         # 목록이 담겨 있나 (아니면 안내 글이 그 자리에)
        self.mon_note = tk.Label(frame, text="", bg=ROW_BG,
                                 fg=U.FG_FAINT, font=U.FONT_S, justify="center",
                                 pady=34)

        self._ev_box(p)

    def _stat_box(self, parent):
        """은색병뚜껑 전용 — 어느 능력을 단련할지 고르는 칸."""
        self.statbox = tk.Frame(parent, bg=PANEL, highlightthickness=2,
                                highlightbackground=U.LINE)
        top = tk.Frame(self.statbox, bg=PANEL)
        top.pack(fill="x", padx=11, pady=(9, 4))
        U.marker_label(top, "어느 능력을 단련할까?", bg=PANEL).pack(side="left")
        self.stat_hint = tk.Label(top, text="", bg=PANEL, fg=U.FG_FAINT,
                                  font=U.FONT_XS)
        self.stat_hint.pack(side="right")
        row = tk.Frame(self.statbox, bg=PANEL)
        row.pack(fill="x", padx=11, pady=(0, 10))
        self.stat_chips = {}
        for key, label in STAT_ROWS:
            lb = tk.Label(row, text=label, bg=U.BG3, fg=U.FG_DIM, font=U.FONT_XS,
                          padx=8, pady=5, highlightthickness=2,
                          highlightbackground=U.LINE)
            lb.pack(side="left", padx=(0, 5))
            lb.bind("<Button-1>", lambda e, k=key: self.pick_stat(k))
            self.stat_chips[key] = lb

    def _ev_box(self, parent):
        """노력치 도구 전용 — 고른 포켓몬의 지금 노력치를 막대로 보여준다."""
        self.evbox = tk.Frame(parent, bg=PANEL, highlightthickness=2,
                              highlightbackground=U.LINE)
        top = tk.Frame(self.evbox, bg=PANEL)
        top.pack(fill="x", padx=11, pady=(9, 5))
        U.marker_label(top, "지금 노력치", bg=PANEL).pack(side="left")
        self.ev_total = tk.Label(top, text="", bg=PANEL, fg=U.FG_DIM,
                                 font=U.FONT_XS)
        self.ev_total.pack(side="right")
        grid = tk.Frame(self.evbox, bg=PANEL)
        grid.pack(fill="x", padx=11, pady=(0, 10))
        self.ev_bars = {}
        for i, (key, label) in enumerate(STAT_ROWS):
            r, c = i % 3, i // 3
            cell = tk.Frame(grid, bg=PANEL)
            cell.grid(row=r, column=c, sticky="w", padx=(0, 18), pady=1)
            name = tk.Label(cell, text=label, bg=PANEL, fg=U.FG_DIM,
                            font=U.FONT_XS, anchor="w", width=7)
            name.pack(side="left")
            cv = tk.Canvas(cell, width=118, height=7, bg="#232b3d",
                           highlightthickness=0, bd=0)
            cv.pack(side="left", padx=(2, 7))
            val = tk.Label(cell, text="0", bg=PANEL, fg=U.FG, font=U.FONT_XS,
                           anchor="e", width=4)
            val.pack(side="left")
            self.ev_bars[key] = (name, cv, val)

    # ---------------- 바닥 ----------------
    def _bottom(self):
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x", side="bottom")
        bar = tk.Frame(self.win, bg=U.INK, height=U.h(58))
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        inner = tk.Frame(bar, bg=U.INK)
        inner.pack(fill="both", expand=True, padx=16)

        self.use_btn = U.PushButton(inner, "쓰기", self.do_use, height=34)
        self.use_btn.pack(side="right", pady=11)
        self.use_btn.configure(state="disabled")
        # **가방에서도 판다.** 팔려고 상점 탭으로 건너갔다가 목록에서 그
        # 도구를 다시 찾아야 하는 게 번거로웠다. 파는 곳은 서버가 같다
        # (/api/shop/sell) - 여기서는 부르기만 한다.
        self.sell_btn = U.ghost_button(inner, "팔기", self.do_sell, height=34)
        self.sell_btn.pack(side="right", padx=(0, 8), pady=11)
        self.sell_btn.configure(state="disabled")
        # 별가루가 서른 개 쌓이면 '팔기' 를 서른 번 눌러야 했다. 여러 가지를
        # 골라 한 번에 판다 (ui_sell).
        self.sell_many_btn = U.ghost_button(inner, "여러 개 팔기",
                                            self.do_sell_many, height=34)
        self.sell_many_btn.pack(side="right", padx=(0, 8), pady=11)
        U.ghost_button(inner, "닫기", self.close,
                       height=34).pack(side="right", padx=(0, 8), pady=11)
        self.status = U.status_line(inner, "", bg=U.INK)
        self.status.pack(side="left", fill="x", expand=True, pady=11)

    # ---------------- 칠하기 (화면 테마가 갈아 끼운다) ----------------
    def _paint_money(self, kinds, total):
        self.money_label.configure(text="{:,}원".format(self.money))
        self.count_label.configure(text="%d종 · 모두 %d개" % (kinds, total))

    def _paint_sort(self):
        self.item_seg.set(self.item_sort)

    def _show_mons(self, keep):
        self.mon_vl.set([("mon", m) for m in self._view], keep=keep)

    def _repaint_items(self):
        self.item_vl.refresh()

    def _repaint_mons(self):
        self.mon_vl.refresh()

    def _paint_item(self, it):
        """오른쪽 위 - 고른 도구의 이름 · 분류 · 개수 · 설명, 그리고 능력 칸 · 노력치 칸을 열고 닫는다."""
        if not it:
            self.i_name.configure(text="도구를 고르세요")
            self.i_cat.configure(text="", bg=U.BG2)
            self.i_count.configure(text="")
            self.i_desc.configure(text="왼쪽에서 도구를 고르면 여기에 설명이 뜬다.")
            self.t_hint.configure(text="")
            self.statbox.pack_forget()
            self.evbox.pack_forget()
            return
        kind = (it.get("effect") or {}).get("kind")
        self.i_name.configure(text=it["kr"])
        self.i_cat.configure(text=CAT_KR.get(it["cat"], it["cat"]),
                             bg=CAT_COLOR.get(it["cat"], U.BG3), fg="#14141a")
        self.i_count.configure(text="%d개" % self.bag.get(it["id"], 0))
        self.i_desc.configure(text=natural(item_desc(it)))
        self.t_hint.configure(text=target_hint(it))
        if self.stat_needed:
            self.statbox.pack(fill="x", pady=(11, 0), after=self.i_desc)
        else:
            self.statbox.pack_forget()
        if kind == "ev":
            self.evbox.pack(fill="x", pady=(11, 0))
        else:
            self.evbox.pack_forget()

    # ---------------- 거들기 ----------------
    def say(self, text, color=U.GOOD, fg=None):
        try:
            U.set_status(self.status, natural(text or ""), color, fg)
        except tk.TclError:
            pass

    def current_item(self):
        return next((i for i in self.items if i["id"] == self.item_id), None)

    def current_mon(self):
        return next((m for m in self.mons if m["id"] == self.mon_id), None)

    # ---------------- 데이터 ----------------
    def reload(self):
        if not self.app.api:
            return self.say("로그인이 필요합니다.", U.DANGER, U.DANGER)
        # 여는 중 표시가 이미 떠 있으면 하나 더 띄우지 않는다. 겹쳐 띄우면
        # 먼저 온 답이 나중 것만 걷고, 먼저 띄운 것은 창을 덮은 채 남는다.
        if not self._pending and self._wait is None:
            self.say("가방을 여는 중...", U.FG_FAINT)
            self._wait = ui_loading.Overlay(self.win, "가방을 여는 중")
        api = self.app.api

        def work():
            shop = fetch_shop(api)
            deco = fetch_deco(api)
            mons = api.pokemon()
            # 도트는 여기서 그림까지 다 만들어 둔다. tk 스레드에서 만들면
            # 마릿수만큼 창이 멈춘다. PhotoImage 만 tk 쪽에서 씌운다.
            #
            # 칸(frame_art) 을 넘지 않게 max_size 로 줄인다. 옆으로 긴 종은
            # 높이만 맞추면 30px 칸 밖으로 나가 잘렸다(캐시된 312종 중 40종).
            # 칸을 넓히지는 않는다 - 이름과 레벨 자리가 옮겨 간다.
            thumbs = {}
            for m in mons:
                # 폼(1.13)이면 그 폼의 그림. 못 받으면 원래 모습으로.
                path = (m.get("formNum") and sprite_cache.ensure(api, m["formNum"], T.skin(m))) \
                    or sprite_cache.ensure(api, m.get("num"), T.skin(m))
                if not path:
                    continue
                try:
                    anim = sprites.load_animation(path, target_height=THUMB,
                                                  min_scale=0.2, max_scale=3.0,
                                                  max_frames=1,
                                                  max_size=(26, MON_H - 4))
                    thumbs[m["id"]] = sprites.to_rgba(
                        anim.frames[sprites.RIGHT][0], anim.key)
                except Exception:                       # noqa: BLE001
                    pass
            # 도구 그림도 같이 받아 둔다 (가진 것만). 목록 크기(20)로
            # 풀어 두기까지 해서 tk 스레드는 감싸기만 한다.
            try:
                bag = (shop or {}).get("bag") or {}
                item_icons.prefetch(api, list(bag), sizes=(20,))
            except Exception:                           # noqa: BLE001
                pass
            return shop, mons, thumbs, deco
        U.run_async(self.root, work, self._loaded)

    def _loaded(self, r, err):
        w, self._wait = self._wait, None
        if not self.alive:
            if w:
                w.close()
            return
        if err:
            if w:
                w.close()
            return self.say(getattr(err, "message", str(err)), U.DANGER,
                            U.DANGER)
        shop, mons, thumbs, deco = r
        self.items = list(shop.get("items") or [])
        self.bag = dict(shop.get("bag") or {})
        names = dict((m["id"], (m.get("info") or {}).get("name") or m.get("nickname") or "?") for m in mons or [])
        d_items, d_bag, self.deco_worn = deco_items(deco, names)
        self.items += d_items
        self.bag.update(d_bag)
        self.money = int(shop.get("money") or 0)
        self.tm_left = shop.get("tmLeft")
        self.mons = mons or []
        self._mon_ids = set(m["id"] for m in self.mons)
        self.photos = {}
        for pid, img in thumbs.items():
            try:
                self.photos[pid] = ImageTk.PhotoImage(img)
            except Exception:                           # noqa: BLE001
                pass

        kinds = sum(1 for v in self.bag.values() if v > 0)
        total = sum(v for v in self.bag.values() if v > 0)
        self._paint_money(kinds, total)

        # 고를 도구를 먼저 정해 둔다. 줄을 만들면서 고른 줄을 바로 칠한다.
        keep_item = self.item_id
        if keep_item and self.bag.get(keep_item, 0) > 0:
            target = keep_item
        else:
            target = self._first_item()
        self.item_id = target
        self._fill_items()
        self._fill_mons()

        self.item_id = None
        self.pick_item(target)

        if self._pending:
            text, color = self._pending
            self._pending = None
            self.say(text, color)
        else:
            self.say("")

        if w:
            # **다 그리고 나서 걷는다.** 맨 앞에서 걷으면 줄을 만드는 동안
            # 아무 표시 없이 창이 멈춘 것처럼 보였다(4초). 첫 화면만큼은
            # 이미 만들었으니, 그것이 그려진 뒤(idle)에 걷는다.
            try:
                self.root.after_idle(w.close)
            except tk.TclError:
                w.close()

    def _first_item(self):
        """처음에 골라 둘 도구 — 쓸 수 있는 것 중 맨 위."""
        rows = self._owned()
        for it in rows:
            if (it.get("effect") or {}).get("kind") in USABLE:
                return it["id"]
        return rows[0]["id"] if rows else None

    def _owned(self):
        """가진 도구만 분류 순서대로."""
        owned = [i for i in self.items if self.bag.get(i["id"], 0) > 0]
        owned.sort(key=lambda i: (CAT_ORDER.index(i["cat"])
                                  if i["cat"] in CAT_ORDER else 99,
                                  i["kr"]))
        return owned

    def _fill_items(self, keep=True):
        """왼쪽 도구 목록을 새로 채운다: 분류마다 머리줄 하나, 그 아래 가진 도구들.

        줄을 만들지 않는다 - 무엇이 몇 번째 줄인지만 넘긴다 (U.VirtualList). 보던 자리는 그대로다.
        """
        owned = self._owned()
        if not owned:
            return self._show_item_entries("empty")
        entries = self._item_entries(owned)
        if not entries:
            # 찾는 말에 맞는 도구가 없다
            return self._show_item_entries(
                "nomatch", note=natural("'%s' 에 맞는 도구가 없다." % self.item_q.get().strip()))
        self._show_item_entries("list", entries, keep=keep)

    def _show_item_entries(self, state, entries=(), keep=True, note=""):
        """도구 목록 자리: state 가 "list" 면 entries 를 담고, "empty"(가방이 비었다) ·
        "nomatch"(찾는 말에 맞는 것이 없다 - note) 면 목록 대신 안내를 놓는다."""
        self.item_nomatch.pack_forget()
        if state == "empty":
            self.item_vl.set([])
            self.item_vl.holder.pack_forget()
            self.item_empty.pack(fill="both", expand=True)
            return
        self.item_empty.pack_forget()
        if state == "nomatch":
            self.item_vl.set([])
            self.item_vl.holder.pack_forget()
            self.item_nomatch.configure(text=note)
            self.item_nomatch.pack(fill="x", pady=(34, 0))
            return
        self.item_vl.pack(fill="both", expand=True)
        self.item_vl.set(list(entries), keep=keep)

    def _item_entries(self, owned):
        """목록에 담을 줄: 분류마다 머리줄 하나와 그 아래 도구들 - 찾는 말로 거르고 고른 순서로 (1.13.4).

        종류순이면 지닌 도구는 하는 일(held.GROUPS)마다 머리줄을 따로 둔다.
        """
        q = self.item_q.get().strip().lower()
        if q:
            owned = [i for i in owned if q in (i.get("kr") or "").lower() or q in (i.get("en") or "").lower()]
        sort = self.item_sort
        cats, by_cat = [], {}
        for it in owned:                            # _owned() 가 이미 분류 순서다
            if it["cat"] not in by_cat:
                cats.append(it["cat"])
                by_cat[it["cat"]] = []
            by_cat[it["cat"]].append(it)
        entries = []
        for cat in cats:
            rows = sorted(by_cat[cat], key=self._item_key)
            if sort == "kind" and cat == "held":
                for key, label in H.GROUPS:
                    part = [i for i in rows if H.group(i["id"]) == key]
                    if part:
                        entries.append(("head", (cat, len(part), label)))
                        entries.extend(("item", i) for i in part)
                continue
            entries.append(("head", (cat, len(rows))))
            entries.extend(("item", i) for i in rows)
        return entries

    def _item_key(self, it):
        """분류 안의 순서. 같으면 가나다 (이름순은 가나다만)."""
        name = (it.get("kr") or "", it.get("id") or "")
        if self.item_sort == "rarity":
            return (-RARITY_RANK.get(it.get("rarity"), 0),) + name
        if self.item_sort == "count":
            return (-int(self.bag.get(it.get("id"), 0) or 0),) + name
        return name

    def set_item_sort(self, key):
        """줄 세우기 단추를 눌렀다. 고른 도구는 그대로, 목록은 맨 위부터."""
        self.item_sort = key if key in dict(ITEM_SORTS) else "name"
        self._paint_sort()
        self._items_changed()
        self.say("도구를 %s순으로 봅니다." % dict(ITEM_SORTS)[self.item_sort]
                 + (" 지닌 도구는 하는 일마다 묶었습니다." if self.item_sort == "kind" else ""), U.INFO, U.FG_DIM)

    def _items_changed(self):
        """찾는 말이나 순서가 바뀌었다 - 목록만 다시 담는다 (고른 도구 · 오른쪽 칸은 그대로)."""
        if not self.alive:
            return
        self._fill_items(keep=False)

    def _fill_mons(self, keep=True):
        """'누구에게 쓸까?' 목록을 새로 채운다. 줄은 화면에 걸칠 때 그 시점의 상태로 칠해진다.

        보이는 것은 찾는 말로 거르고 고른 순서로 줄 세운 것이다 (self.find, 1.13.1).
        """
        self._view = self.find.view(self.mons, getattr(self.app, "dex", None))
        self._show_mons(keep)
        if not self.mons:
            self._mon_list(False, "가진 포켓몬이 없다.")

    def _find_changed(self):
        """찾는 말·순서가 바뀌었다. 목록을 다시 채우고(맨 위부터), 고른 포켓몬이 가려졌으면
        보이는 것 중에서 다시 고른다."""
        if not self.alive:
            return
        stat, mon = self.stat, self.mon_id
        self._fill_mons(keep=False)
        self._show_targets(self.current_item())
        if stat and self.mon_id == mon:
            self.pick_stat(stat)             # 병뚜껑으로 고른 능력은 그대로 (pick_mon 이 지운다)

    def _mon_list(self, on, note=""):
        """대상 목록을 보이거나, 그 자리에 안내 글을 놓는다."""
        if on:
            self.mon_note.pack_forget()
            if not self._mon_list_on:
                self.mon_vl.pack(fill="both", expand=True)
                self._mon_list_on = True
            return
        if self._mon_list_on:
            self.mon_vl.holder.pack_forget()
            self._mon_list_on = False
        self.mon_note.configure(text=note)
        self.mon_note.pack(fill="both", expand=True)

    def shown_items(self):
        """화면에 걸친 도구 줄들 [(도구 id, 줄)] (검사용)."""
        return [(row.item["id"], row) for _i, row in self.item_vl.shown() if isinstance(row, ItemRow)]

    def shown_mons(self):
        """화면에 걸친 포켓몬 줄들 [(포켓몬 id, 줄)] (검사용)."""
        return [(row.mon["id"], row) for _i, row in self.mon_vl.shown()]

    # ---------------- 고르기 ----------------
    def pick_item(self, item_id):
        prev = self.item_id
        self.item_id = item_id
        self.stat = None
        if prev != item_id:
            self._repaint_items()            # 보이는 줄만 다시 칠한다 (고름은 줄이 self.item_id 를 본다)
        it = self.current_item()
        if not it:
            self.stat_needed = False
            self._paint_item(None)
            self._show_targets(None)
            return self._refresh_button()

        eff = it.get("effect") or {}
        kind = eff.get("kind")
        # 병뚜껑처럼 능력을 골라야 하는 것만 능력 칸을 연다.
        # 금색병뚜껑(count 6)은 서버가 알아서 여섯 개를 다 단련한다.
        self.stat_needed = (kind == "iv" and int(eff.get("count", 1)) < 6)
        self._paint_item(it)

        self._show_targets(it)
        self._refresh_stats()
        self._refresh_evs()
        self._refresh_button()

    def _show_targets(self, it):
        """도구에 맞춰 대상 목록을 칠하거나, 못 쓰는 도구면 안내로 바꾼다."""
        kind = (it.get("effect") or {}).get("kind") if it else None
        usable = bool(it) and kind in USABLE
        if usable and kind in NO_TARGET:
            # 대상이 없다. 목록 자리에 무엇을 하는 도구인지만 적는다.
            self._mon_list(False, natural(item_desc(it)))
            self.mon_id = None
            return
        if not usable:
            self._mon_list(False, natural(unusable_note(it)) if it else
                           "도구를 고르면 쓸 수 있는 포켓몬을 보여준다.")
            self.mon_id = None
            return
        if not self.mons:
            return self._mon_list(False, "가진 포켓몬이 없다.")

        # 판정은 **줄이 아니라 데이터로** 한다. 줄은 화면에 보이는 것만 있다 -
        # 나머지는 굴러서 화면에 걸칠 때 이 상태로 칠해진다.
        self._states = {}
        for m in self.mons:
            self._states[m["id"]] = self._target_state(it, m)
        if not self._view:
            # 찾는 말에 맞는 포켓몬이 없다. 안 보이는 포켓몬에게 쓰게 두지 않는다.
            self._mon_list(False, self.find.empty_note())
            return self.pick_mon(None, quiet=True)
        self._mon_list(True)
        # 처음 골라 줄 것은 **보이는 것 중에서** 찾는다 - 찾아서 좁혔으면 그 안에서.
        first_ok = None
        for m in self._view:
            if not self._states[m["id"]][1] and (
                    first_ok is None or (self._is_good(m["id"]) and not self._is_good(first_ok))):
                first_ok = m["id"]
        self._repaint_mons()
        # 고르고 있던 포켓몬이 이 도구로는 못 쓰는 대상이거나 찾기에 가려졌으면 옮겨 준다
        cur = self._states.get(self.mon_id)
        if cur is None or cur[1] or not any(m["id"] == self.mon_id for m in self._view):
            self.pick_mon(first_ok, quiet=True)
        else:
            self.pick_mon(self.mon_id, quiet=True)

    def _is_good(self, pid):
        st = self._states.get(pid)
        return bool(st and st[0])

    def _target_state(self, it, mon):
        """이 도구를 이 포켓몬에게 쓸 수 있는지.

        (밝게 칠할까, 막을까, 줄 끝에 붙일 말, 그 말의 색) 을 돌려준다.
        진화의 돌은 **막지 않는다.** 낮/밤 같은 조건은 서버가 보기 때문에
        여기서는 될 만한 대상을 밝게 알려주는 데까지만 한다.
        """
        eff = it.get("effect") or {}
        kind = eff.get("kind")
        info = mon.get("info") or {}
        level = int(mon.get("level", 0))

        if kind == "held":
            cur = mon.get("heldKr")
            if mon.get("held") == it["id"]:
                return False, True, "이미 지님", U.FG_FAINT
            if not mega_fits(getattr(self.app, "dex", None), it, mon):
                # 그 스톤으로 메가진화하는 종만 지닌다 (서버도 막는다). 막아 두어야 파티 맨 앞의 빈손
                # 포켓몬이 먼저 골라지지 않는다 - 10/22 오이쉬에의 망나뇽나이트가 그렇게 치엔파오에게 갔다.
                return False, True, "메가진화 안 함", U.FG_FAINT
            if it.get("cat") == "megastone" and mon.get("bonded") is False:
                # 유대 미션을 마친 개체만 메가진화한다 (10/22, 서버도 막는다). 옛 서버는 bonded 를 안 보낸다.
                return False, True, "유대 미션 전", U.FG_FAINT
            if cur:
                return False, False, "지님: %s" % cur, U.FG_DIM
            return True, False, "빈손", U.GOOD

        if kind == "stone":
            if info.get("species") in (it.get("evolves") or []):
                return True, False, "진화할 수 있다", U.GOOD
            return False, False, "", U.FG_FAINT

        if kind == "iv":
            if level < HYPER_MIN_LEVEL:
                return False, True, "Lv.%d 부터" % HYPER_MIN_LEVEL, U.FG_FAINT
            ivs = info.get("ivs") or {}
            hyper = info.get("hyper") or {}
            left = [s for s, _l in STAT_ROWS
                    if int(ivs.get(s, 0)) < P.IV_MAX and not hyper.get(s)]
            if not left:
                return False, True, "이미 다 단련됨", U.FG_FAINT
            return False, False, "%d곳 남음" % len(left), U.SHINY

        if kind == "ev":
            stat = eff.get("stat")
            amount = int(eff.get("amount", 0))
            evs = info.get("evs") or {}
            cur = int(evs.get(stat, 0))
            total = int(info.get("evTotal", sum(int(v) for v in evs.values())))
            label = STAT_KR.get(stat, stat)
            if amount >= 0:
                if cur >= EV_STAT_MAX:
                    return False, True, "%s 이미 최대" % label, U.FG_FAINT
                if total >= EV_TOTAL_MAX:
                    return False, True, "합계가 꽉 참", U.FG_FAINT
                return False, False, "%s %d" % (label, cur), U.GOOD
            if cur <= 0:
                return False, True, "%s 내릴 것 없음" % label, U.FG_FAINT
            return False, False, "%s %d" % (label, cur), U.INFO

        if kind == "level":
            if level >= P.LEVEL_MAX:
                # 레벨은 못 올려도 진화 조건이 되면 진화한다 (서버가 본다)
                return False, False, "최고 레벨 · 진화할 수 있으면 진화", U.FG_DIM
            # 양쪽에 다 'Lv.' 를 붙인다. 'Lv.5 → 6' 은 56 레벨로 읽혔다.
            return False, False, "Lv.%d → Lv.%d" % (
                level, min(P.LEVEL_MAX, level + int(eff.get("amount", 1)))), U.INFO

        if kind == "noevolve":
            if mon.get("noEvolve"):
                return True, False, "진화 잠금 중 · 풀기", U.PINK
            return False, False, "진화를 막는다", U.FG_DIM

        if kind == "shiny":
            if mon.get("shiny"):
                return False, True, "이미 이로치", U.FG_FAINT
            return False, False, "이로치로 바꾸기", U.SHINY

        if kind == "form":
            return self._form_state(it, mon)

        if kind == "deco":
            return self._deco_state(it, mon)

        return False, True, "쓸 수 없다", U.FG_FAINT

    def _deco_state(self, it, mon):
        """꾸미기 (버전 2): 쓰고 있으면 '빼기', 그 칸에 다른 것을 쓰고 있으면 '바꿔 씀', 바탕화면에 있으면 밝게."""
        eff = it.get("effect") or {}
        key, slot = eff.get("deco"), eff.get("slot")
        mine = self.deco_worn.get(mon.get("id")) or {}
        if mine.get(slot) == key:
            return True, False, "쓰는 중 · 빼기", U.PINK
        if mine.get(slot):
            return False, False, "%s 대신" % DECO.name(mine[slot]), U.FG_DIM
        if mon.get("onDesktop"):
            return True, False, "", U.GOOD          # 밝게만 ('따라다님' 이 이미 줄에 있다)
        return False, False, "", U.FG_FAINT

    def _deco_on(self, it, mon):
        """이 포켓몬에 끼우나(True) 빼나(False)."""
        eff = it.get("effect") or {}
        return (self.deco_worn.get((mon or {}).get("id")) or {}).get(eff.get("slot")) != eff.get("deco")

    @staticmethod
    def _form_state(it, mon):
        """폼 도구 (1.13). 통하는 종만 밝히고, 지금 모습을 줄 끝에 적는다. 나머지는 막는다."""
        tg = form_targets(it, mon)
        if not tg:
            return False, True, "", U.FG_FAINT
        cur = mon.get("form")
        if (it.get("effect") or {}).get("consume"):
            # 꽃꿀: 그 모습으로만 바꾼다 (다홍꿀은 원래 모습으로)
            if (tg[0].get("form") or None) == (cur or None):
                return False, True, "이미 그 모습", U.FG_FAINT
            return True, False, "→ %s" % tg[0].get("formKr"), U.GOOD
        if len(tg) == 1:
            if cur == tg[0].get("form"):
                return True, False, "%s · 원래 모습으로" % tg[0].get("formKr"), U.PINK
            return True, False, "→ %s" % tg[0].get("formKr"), U.GOOD
        now = next((t.get("formKr") for t in tg if t.get("form") == cur), None) if cur else None
        return True, False, "지금: %s" % (now or "원래 모습"), U.GOOD

    def pick_mon(self, pid, quiet=False):
        # 줄이 아직 안 만들어졌을 수 있어서 데이터(self._states)로 본다.
        st = self._states.get(pid)
        if st is not None and st[1]:
            if not quiet:
                self.say(st[2] or "이 포켓몬에게는 쓸 수 없다.", U.ACCENT,
                         U.FG_DIM)
            return
        prev = self.mon_id
        self.mon_id = pid if pid in self._mon_ids else None
        if prev != self.mon_id:
            self._repaint_mons()             # 보이는 줄만 다시 칠한다
        self.stat = None
        self._refresh_stats()
        self._refresh_evs()
        self._refresh_button()

    def pick_stat(self, key):
        mon = self.current_mon()
        if not self.stat_needed or not mon:
            return
        info = mon.get("info") or {}
        if int((info.get("ivs") or {}).get(key, 0)) >= P.IV_MAX \
                or (info.get("hyper") or {}).get(key):
            return self.say("%s은(는) 이미 최고치다." % STAT_KR[key], U.ACCENT,
                            U.FG_DIM)
        self.stat = key
        self._refresh_stats()
        self._refresh_button()

    # ---------------- 오른쪽 칸 새로 칠하기 ----------------
    def _refresh_stats(self):
        if not self.stat_needed:
            return
        mon = self.current_mon()
        info = (mon or {}).get("info") or {}
        ivs = info.get("ivs") or {}
        hyper = info.get("hyper") or {}
        if not mon:
            hint = "먼저 포켓몬을 고르세요"
        elif int(mon.get("level", 0)) < HYPER_MIN_LEVEL:
            hint = "Lv.%d 부터 단련할 수 있다" % HYPER_MIN_LEVEL
        else:
            hint = "회색은 이미 최고치"
        cells = []                            # (능력, 글, "off" | "done" | "on" | "free")
        for key, label in STAT_ROWS:
            if not mon:
                cells.append((key, label, "off"))
                continue
            iv = int(ivs.get(key, 0))
            done = hyper.get(key) or iv >= P.IV_MAX
            text = "%s %d" % (label, P.IV_MAX if done else iv)
            cells.append((key, text, "done" if done else "on" if self.stat == key else "free"))
        self._paint_stats(hint, cells)

    def _paint_stats(self, hint, cells):
        self.stat_hint.configure(text=hint)
        for key, text, state in cells:
            lb = self.stat_chips[key]
            if state in ("off", "done"):
                lb.configure(text=text, bg=U.BG2, fg="#5a6076",
                             highlightbackground=U.LINE, cursor="")
            elif state == "on":
                lb.configure(text=text, bg=U.ACCENT, fg=U.ACCENT_DARK,
                             highlightbackground=U.INK, cursor="hand2")
            else:
                lb.configure(text=text, bg=U.BG3, fg=U.FG,
                             highlightbackground=U.LINE2, cursor="hand2")

    def _refresh_evs(self):
        it = self.current_item()
        if not it or (it.get("effect") or {}).get("kind") != "ev":
            return
        mon = self.current_mon()
        info = (mon or {}).get("info") or {}
        evs = info.get("evs") or {}
        total = int(info.get("evTotal", 0))
        want = (it.get("effect") or {}).get("stat")
        rows = []                             # (능력, 이름, 값 - 포켓몬을 안 골랐으면 None, 이 도구의 능력인가)
        for key, label in STAT_ROWS:
            rows.append((key, label, int(evs.get(key, 0)) if mon else None, key == want))
        if mon:
            total_text = "합계 %d / %d" % (total, EV_TOTAL_MAX)
            total_full = total >= EV_TOTAL_MAX
        else:
            total_text, total_full = "포켓몬을 고르세요", None
        self._paint_evs(rows, total_text, total_full)

    def _paint_evs(self, rows, total_text, total_full):
        """total_full: 합계가 꽉 찼나 (True/False), 포켓몬을 안 골랐으면 None."""
        for key, label, v, on in rows:
            name, cv, val = self.ev_bars[key]
            name.configure(fg=U.ACCENT_TEXT if on else U.FG_DIM)
            val.configure(text=str(v) if v is not None else "-",
                          fg=U.ACCENT if on else U.FG_DIM)
            cv.delete("all")
            w = int(118 * min(v or 0, EV_STAT_MAX) / float(EV_STAT_MAX))
            if w:
                cv.create_rectangle(0, 0, w, 7,
                                    fill=U.ACCENT if on else "#4a5878",
                                    outline="")
        if total_full is None:
            self.ev_total.configure(text=total_text, fg=U.FG_FAINT)
        else:
            self.ev_total.configure(text=total_text, fg=U.DANGER if total_full else U.FG_DIM)

    def _refresh_button(self):
        it = self.current_item()
        mon = self.current_mon()
        kind = (it.get("effect") or {}).get("kind") if it else None
        usable = bool(it) and kind in USABLE
        free = usable and kind in NO_TARGET          # 대상을 안 고르는 도구
        ok = bool(usable and (free or (mon and (not self.stat_needed or self.stat))))
        use_text = "%s 쓰기" % it["kr"] if (it and usable and (mon or free)) else "쓰기"
        if kind == "deco":
            use_text = ("씌우기" if self._deco_on(it, mon) else "빼기") if mon else "씌우기"
        elif kind == "decopick":
            use_text = "묶음 고르기"

        # 팔기는 포켓몬을 안 골라도 된다. 값이 붙어 있고 실제로 갖고
        # 있으면 팔 수 있다. 몬스터볼은 게임이 안 돌아가므로 뺀다.
        have = int(self.bag.get((it or {}).get("id"), 0)) if it else 0
        price = int((it or {}).get("sell") or 0)
        can_sell = bool(it) and price > 0 and have > 0 and it["id"] != "POKEBALL"
        self._paint_buttons(ok, use_text, can_sell, "%d원에 팔기" % price if can_sell else "팔기")

    def _paint_buttons(self, use_ok, use_text, sell_ok, sell_text):
        self.use_btn.configure(state="normal" if use_ok else "disabled")
        self.use_btn.configure(text=use_text)
        self.sell_btn.configure(state="normal" if sell_ok else "disabled")
        self.sell_btn.configure(text=sell_text)

    # ---------------- 팔기 ----------------
    def do_sell(self):
        """가방에서 바로 판다. 값과 재고 판정은 서버가 한다.

        **되돌릴 수 없으니 한 번 묻는다.** 진화의 돌처럼 아껴 둔 것을
        잘못 누르면 그대로 사라진다.
        """
        it = self.current_item()
        if not it:
            return
        have = int(self.bag.get(it["id"], 0))
        price = int(it.get("sell") or 0)
        if have <= 0 or price <= 0:
            return
        n = 1
        if not ui_box.confirm(
                self.win, "팔기",
                "%s 을(를) 한 개 팔아 %d원을 받습니다. 되돌릴 수 없습니다."
                % (it["kr"], price),
                danger=True, ok_text="판다"):
            return

        api = self.app.api
        item_id = it["id"]
        self.sell_btn.configure(state="disabled")
        self.say("%s을(를) 파는 중..." % it["kr"], U.FG_FAINT)

        def work():
            fn = getattr(api, "sell", None)
            if fn is not None:
                return fn(item_id, n)
            return api._call("POST", "/api/shop/sell",
                             body={"item": item_id, "count": n})

        def done(r, err):
            if not self.alive:
                return
            if err:
                self.say(getattr(err, "message", str(err)), U.DANGER, U.DANGER)
                return self._refresh_button()
            r = r or {}
            self._pending = (r.get("message") or "팔았다.", U.GOOD)
            self.reload()

        U.run_async(self.root, work, done)

    # ---------------- 여러 개 팔기 ----------------
    def do_sell_many(self):
        """여러 도구를 골라 한 번에 판다. 판정과 계산은 서버가 한다."""
        from .ui_sell import ask_sell_many, summary

        if not self.items:
            return self.say("가방을 아직 불러오지 못했습니다.", U.DANGER, U.DANGER)
        lines = ask_sell_many(self.win, self.root, self.items, self.bag, self.money)
        if not lines:
            return
        if not ui_box.confirm(self.win, "여러 개 팔기",
                              summary(lines, self.items),
                              danger=True, ok_text="판다"):
            return

        api = self.app.api
        wait = ui_loading.Overlay(self.win, "파는 중")
        self.say("파는 중...", U.FG_FAINT)

        def done(r, err):
            wait.close()
            if not self.alive:
                return
            if err:
                return self.say(getattr(err, "message", str(err)), U.DANGER, U.DANGER)
            r = r or {}
            self._pending = (r.get("message") or "팔았다.", U.GOOD)
            self.reload()

        U.run_async(self.root, lambda: api.sell_many(lines), done)

    # ---------------- 쓰기 ----------------
    def do_use(self):
        it = self.current_item()
        mon = self.current_mon()
        if it and (it.get("effect") or {}).get("kind") in NO_TARGET:
            return self._use_no_target(it)
        if not it or not mon:
            return
        if self.stat_needed and not self.stat:
            return self.say("어느 능력을 단련할지 골라 주세요.", U.ACCENT, U.FG_DIM)
        if (it.get("effect") or {}).get("kind") == "deco":
            return self._use_deco(it, mon)
        # 이로치사탕은 시즌 보상이라 다시 구할 길이 없다. 한 번 묻는다.
        if (it.get("effect") or {}).get("kind") == "shiny":
            name = (mon.get("info") or {}).get("name") or "이 포켓몬"
            if not ui_box.confirm(
                    self.win, "이로치사탕",
                    "%s에게 이로치사탕을 먹입니다. 몸 색이 이로치로 바뀌고 "
                    "되돌릴 수 없습니다." % name, danger=False, ok_text="먹이기"):
                return

        form = ""
        if (it.get("effect") or {}).get("kind") == "form":
            form = self._ask_form(it, mon)
            if form is None:
                return

        api = self.app.api
        item_id, pid, stat = it["id"], mon["id"], self.stat or ""
        # 낮/밤을 보는 조건이 있어서 이 PC 의 시각을 같이 보낸다.
        hour = datetime.datetime.now().hour
        self.use_btn.configure(state="disabled")
        self.say("%s을(를) 쓰는 중..." % it["kr"], U.FG_FAINT)

        held = (it.get("effect") or {}).get("kind") == "held"

        def work():
            if held:
                # 지니는 건 '쓰는' 게 아니다. 가방에서 빠져 포켓몬에게 간다.
                return api.hold(pid, item_id)
            return use_item(api, item_id, pid, stat, hour, form=form)

        def done(r, err):
            if not self.alive:
                return
            if err:
                self.say(getattr(err, "message", str(err)), U.DANGER, U.DANGER)
                return self._refresh_button()
            r = r or {}
            self.mon_id = pid
            self._pending = (r.get("message") or "도구를 썼다.", U.GOOD)
            self.reload()
            self.app.request_sync()          # 바탕화면 도트도 바뀔 수 있다
            if not r.get("evolve"):
                ask_new_learns(self.app, mon, r)     # 로토무카탈로그 · 이상한사탕 … (게시판 #279)
            if r.get("evolve"):
                info = dict(r["evolve"], pokemonId=pid)
                show = getattr(self.app, "show_evolutions", None)
                if show is not None:
                    show([info], self.win)     # 바탕화면에 있으면 진화 연출
                else:
                    announce_evolve(self.win, self.app, info)
        U.run_async(self.root, work, done)

    def _ask_form(self, it, mon):
        """폼 도구를 쓰기 전에 물을 것. 고른 모습의 열쇠('' = 원래 모습), 그만두면 None.

        · 고르는 도구 (로토무카탈로그·운석): 바뀔 모습을 고른다. '원래 모습' 도 있다.
        · 나머지 (켜고 끄기·꽃꿀): 묻지 않는다.
        """
        tg = form_targets(it, mon)
        if len(tg) < 2:
            return ""                           # 묻지 않는다 (못 쓰는 대상이면 서버가 왜인지 말해 준다)
        name = (mon.get("info") or {}).get("name") or "이 포켓몬"
        cur = mon.get("form") or ""
        opts = [(t["form"], t.get("formKr") or t["form"], None) for t in tg if t.get("form") != cur]
        if cur:
            opts.append(("", "원래 모습", None))
        now = next((t.get("formKr") for t in tg if t.get("form") == cur), None) if cur else None
        return ui_box.ask_choice(self.win, it["kr"],
                                 "%s의 모습을 고르세요. (지금: %s)" % (name, now or "원래 모습"), opts)

    def _ask_tm_type(self, it):
        """타입 확정 기술머신 뽑기권: 어느 타입에서 뽑을지 (1.13.1). 고른 타입, 그만두면 None.

        다 모은 타입은 빼고, 타입마다 아직 없는 기술머신 수를 적는다 (서버가 실어 보낸 tmLeft).
        옛 서버라 그 수가 없으면 타입만 늘어놓는다 - 다 모은 타입이면 서버가 표를 빼기 전에 거절한다.
        """
        from .ui_tms import TYPE_KR            # ui_tms 가 이 모듈을 부르므로 여기서 늦게 부른다
        left = self.tm_left
        opts = []
        for t, kr in TYPE_KR.items():
            if left is None:
                if t != "STELLAR":
                    opts.append((t, kr, None))
            elif int(left.get(t) or 0) > 0:
                opts.append((t, kr, "아직 없는 것 %d개" % int(left[t])))
        if not opts:
            self.say("기술머신을 이미 다 모아서 뽑을 것이 없다.", U.ACCENT, U.FG_DIM)
            return None
        return ui_box.ask_choice(self.win, it["kr"],
                                 "어느 타입을 뽑을까요? 고른 타입의 기술머신 가운데 아직 없는 것 "
                                 "하나가 무작위로 나옵니다.", opts)

    def _use_deco(self, it, mon):
        """꾸미기를 씌우거나 뺀다 (/api/deco/equip). 바탕화면 도트도 바로 갈아 입힌다."""
        api = self.app.api
        key = (it.get("effect") or {}).get("deco")
        pid = mon["id"]
        on = self._deco_on(it, mon)
        name = (mon.get("info") or {}).get("name") or "이 포켓몬"
        self.use_btn.configure(state="disabled")
        self.say("씌우는 중..." if on else "빼는 중...", U.FG_FAINT)

        def done(r, err):
            if not self.alive:
                return
            if err:
                self.say(getattr(err, "message", str(err)), U.DANGER, U.DANGER)
                return self._refresh_button()
            self.mon_id = pid
            text = ("%s 에게 %s 을(를) 씌웠다." if on else "%s 의 %s 을(를) 뺐다.") % (name, it["kr"])
            self._pending = (natural(text), U.GOOD)
            changed = getattr(self.app, "deco_changed", None)
            if changed is not None:
                changed(pid, (r or {}).get("deco") or {})
            else:
                self.app.request_sync()
            self.reload()
        U.run_async(self.root, lambda: api.deco_equip(pid, key, on), done)

    def _use_deco_pick(self, it):
        """참가 묶음 선택권: 묶음 셋 가운데 하나를 고른다 (되돌릴 수 없다 - 고르는 창이 그렇게 말한다)."""
        choices = (it.get("effect") or {}).get("choices") or [
            {"key": b, "kr": DECO.BUNDLE_KR[b]} for b in DECO.JOIN_CHOICES]
        opts = [(c["key"], c.get("kr") or DECO.name(c["key"]), None) for c in choices]
        bundle = ui_box.ask_choice(self.win, DECO.PICK_KR,
                                   "참가 묶음 하나를 고르세요. 고른 뒤에는 바꿀 수 없습니다.", opts)
        if not bundle:
            return
        api = self.app.api
        self.use_btn.configure(state="disabled")
        self.say("고르는 중...", U.FG_FAINT)

        def done(r, err):
            if not self.alive:
                return
            if err:
                self.say(getattr(err, "message", str(err)), U.DANGER, U.DANGER)
                return self._refresh_button()
            got = (r or {}).get("got") or [DECO.name(bundle)]
            self._pending = ("받았다: %s - 꾸미기 주머니에서 포켓몬에게 씌울 수 있다." % " · ".join(got), U.GOOD)
            self.item_id = None
            self.reload()
        U.run_async(self.root, lambda: api.deco_pick(bundle), done)

    def _use_no_target(self, it):
        """대상이 없는 도구(뽑기권). 포켓몬을 안 고르고 바로 쓴다."""
        if (it.get("effect") or {}).get("kind") == "decopick":
            return self._use_deco_pick(it)
        api = self.app.api
        item_id = it["id"]
        eff = it.get("effect") or {}
        tm_type = ""
        if eff.get("kind") == "tmticket" and eff.get("pickType"):
            tm_type = self._ask_tm_type(it)
            if not tm_type:
                return                              # 창을 닫았다
        hour = datetime.datetime.now().hour
        self.use_btn.configure(state="disabled")
        self.say("%s을(를) 쓰는 중..." % it["kr"], U.FG_FAINT)

        def done(r, err):
            if not self.alive:
                return
            if err:
                msg = getattr(err, "message", str(err))
                if tm_type and getattr(err, "status", 0):
                    # 거절됐다 (그사이 드랍으로 그 타입을 다 모았다 등). 가방을 다시 읽어야 고르는 창의
                    # '아직 없는 것 N개' 가 맞는 수가 된다 - 안 그러면 다 모은 타입이 계속 뜬다.
                    self._pending = (msg, U.DANGER)
                    return self.reload()
                self.say(msg, U.DANGER, U.DANGER)
                return self._refresh_button()
            r = r or {}
            color = U.GOOD if r.get("won") else U.FG_DIM
            self._pending = (r.get("message") or "도구를 썼다.", color)
            self.reload()
            self.app.request_sync()          # 알 칸이 바뀐다
            if r.get("tmNew") is not None:   # 기술머신 뽑기권 - [기술머신] 의 노란 점과 목록
                note = getattr(self.app, "note_tms", None)
                if note is not None:
                    note(r["tmNew"])

        U.run_async(self.root,
                    lambda: use_item(api, item_id, 0, "", hour, tm_type=tm_type), done)

    # ---------------- 끝내기 ----------------
    def close(self):
        self.alive = False
        if getattr(self.app, "bag_window", None) is self:
            self.app.bag_window = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def focus(self):
        if U.is_embedded(self.win):
            return          # 탭이면 허브가 앞으로 꺼내 준다
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()


# ---------------------------------------------------------------- 진화 알림
def _gift_icon(parent, app, label, item_id, keep, tag):
    """선물 상자에 도구 그림을 넣는다. 안 받아 뒀으면 받아서 넣는다.

    **처음 받는 도구는 이 PC 에 그림이 없다.** 선물이 바로 그런 경우다 -
    이벤트 볼처럼 상점에 없는 물건은 가방을 열어 본 적이 없으면 그림도
    없다. 그대로 두면 이름만 뜨고 자리가 비어 보인다.

    창을 늦게 띄우지는 않는다. 먼저 글로 띄우고, 그림이 오면 채운다.
    """
    got = item_icons.photo(item_id, 26)
    if got is not None:
        keep[tag] = got
        return label.configure(image=got)

    def work():
        item_icons.raw(app.api, item_id)     # 받아서 이 PC 에 남긴다
        return True

    def done(_r, err):
        if err:
            return
        try:
            ph = item_icons.photo(item_id, 26)
            if ph is not None:
                keep[tag] = ph
                label.configure(image=ph)
        except Exception:                                  # noqa: BLE001
            pass

    U.run_async(parent, work, done)


def gift_line(g):
    """선물 한 줄에 적을 말.

    돈은 개수가 아니다. "돈 ×5000" 이라고 적으면 5000개를 받은 것처럼
    읽힌다. 화면 어디서나 돈은 "5,000원" 이라 여기서도 그렇게 적는다.
    """
    n = int(g.get("count", 1) or 0)
    if g.get("kind") == "money":
        return "%s원" % format(n, ",")
    # 칭호·명패는 개수가 없다 (시즌 보상)
    if g.get("kind") == "title":
        return "칭호 · %s" % (g.get("name") or "?")
    if g.get("kind") == "frame":
        return "명패 · %s" % (g.get("name") or "?")
    if g.get("kind") == "egg":
        return g.get("name") or "포켓몬 알"
    if g.get("kind") == "deco":
        return "꾸미기 · %s" % (g.get("name") or "?")     # 묶음은 여러 개를 한 줄에 (개수가 없다)
    return "%s ×%d" % (g.get("name") or "?", n)


def gift_notes(gifts):
    """선물 알림의 글 셋: (제목, 메시지, 맨 아래 안내). 화면(기본 · 테마)이 같이 쓴다.

    제목과 메시지는 운영자가 적은 것이다. 첫 선물의 것을 쓴다 - 한 번에 여러 개를 보낼 때는 보통 같은
    이유로 보낸다. 안내는 선물 종류에 따라 다르다 (가방 · 알 · 칭호/명패).
    """
    head = gifts[0].get("title") or ""
    msg = gifts[0].get("message") or ""
    # 칭호·명패는 가방이 아니라 마이페이지에서 단다 (시즌 보상, 1.12.0 까지는 랭킹 탭)
    kinds = set(g.get("kind") for g in gifts)
    bits = []
    if kinds & {"item", "money", "balls"}:
        bits.append("가방에 넣어 두었습니다.")
    if "egg" in kinds:
        # 1.4.1 부터 알도 파티 한 자리를 차지한다. 꽉 차 있으면 박스로 간다.
        bits.append("알은 데리고 다니는 동안 게임을 켜 둔 시간만큼 자라서 부화합니다. "
                    "자리가 없으면 박스에 들어가니 포켓몬 관리에서 데리고 다니세요.")
    if kinds & {"title", "frame"}:
        bits.append("칭호·명패는 마이페이지에서 바꿀 수 있습니다.")
    if "deco" in kinds:
        bits.append("꾸미기는 가방의 '꾸미기' 주머니에 들어갑니다 - 거기서 고르거나, 바탕화면 포켓몬을 우클릭해 "
                    "'꾸미기...' 로 씌울 수 있습니다.")
    return head, msg, " ".join(bits) or "가방에 넣어 두었습니다."


def gift_icon_id(g):
    """선물 한 줄에 그릴 도구 그림의 id (없으면 None - 돈 · 칭호처럼 그림이 없는 줄)."""
    if g.get("kind") == "item" and g.get("item"):
        return g["item"]
    if g.get("kind") == "egg" and g.get("item"):
        from . import eggs_ui
        return eggs_ui.EGG_ITEM.get(g["item"])
    return None


@skins.skinnable_fn("announce")
def announce_gifts(parent, app, gifts):
    """운영자가 보낸 선물이 도착했다고 알린다.

    **여럿이면 한 창에 모아 보여준다.** 하나씩 띄우면 창이 줄줄이 뜬다.

    껍데기는 진화 알림과 같은 것을 쓴다(ui_box._shell). 창마다 다시
    그리면 미묘하게 달라진다.

    도구 그림은 이미 받아 둔 것만 쓴다. 없으면 글로만 보여준다 - 선물이
    왔다는 사실이 그림보다 중요하고, 그림 받다 창이 늦게 뜨면 안 된다.
    """
    if not gifts:
        return
    keep = {}
    n = len(gifts)
    # 창 높이는 줄 수에 따라 잡고, 글꼴이 커지면 같이 커진다.
    # **넉넉하게 잡는다.** 모자라면 아래에서부터 조용히 눌린다 - 실제로
    # 18px 이 모자라 단추 글씨('고맙습니다')까지 잘렸다.
    height = U.h(250) + min(n, 8) * U.h(38)
    win, f = ui_box._shell(parent, "선물", 420, height)

    tk.Label(f, text="선물이 도착했습니다", bg=U.BG, fg=U.ACCENT_TEXT,
             font=(U.FAMILY_BLACK, U.pt(20))).pack(anchor="w")
    head, msg, footer = gift_notes(gifts)
    if head:
        tk.Label(f, text=head, bg=U.BG, fg=U.FG, font=U.FONT_H,
                 wraplength=360, justify="left").pack(anchor="w", pady=(6, 0))
    if msg:
        tk.Label(f, text=natural(msg), bg=U.BG, fg=U.FG_DIM, font=U.FONT_S,
                 wraplength=360, justify="left").pack(anchor="w", pady=(4, 0))

    box = tk.Frame(f, bg=PANEL, highlightthickness=2,
                   highlightbackground=U.LINE)
    box.pack(fill="x", pady=(14, 0))
    inner = tk.Frame(box, bg=PANEL)
    inner.pack(fill="x", padx=14, pady=10)
    for i, g in enumerate(gifts[:8]):
        row = tk.Frame(inner, bg=PANEL, height=U.h(34))
        row.pack(fill="x")
        row.pack_propagate(False)
        # **그림 자리를 픽셀로 잡는다.** Label 의 width 는 글자일 때는
        # 글자 수인데 그림일 때는 픽셀이라, width=3 을 주면 그림이 3px
        # 로 눌린다. 게다가 돈처럼 그림이 없는 줄과 들여쓰기가 어긋난다.
        # 칸(Frame)으로 자리를 잡으면 있든 없든 줄이 맞는다.
        slot = tk.Frame(row, bg=PANEL, width=U.h(30), height=U.h(30))
        slot.pack(side="left", padx=(0, 8))
        slot.pack_propagate(False)
        icon = tk.Label(slot, bg=PANEL)
        icon.pack(expand=True)
        icon_id = gift_icon_id(g)
        if icon_id:
            _gift_icon(parent, app, icon, icon_id, keep, i)
        tk.Label(row, text=gift_line(g), bg=PANEL, fg=U.FG, font=U.FONT_B,
                 anchor="w").pack(side="left")
    if n > 8:
        tk.Label(inner, text="그 밖 %d개" % (n - 8), bg=PANEL,
                 fg=U.FG_FAINT, font=U.FONT_XS).pack(anchor="w", pady=(4, 0))

    tk.Label(f, text=footer, bg=U.BG, fg=U.FG_DIM,
             font=U.FONT_S, wraplength=360,
             justify="left").pack(anchor="w", pady=(10, 0))

    row = tk.Frame(f, bg=U.BG)
    row.pack(fill="x", pady=(14, 0))
    U.PushButton(row, "고맙습니다", win.destroy, height=34,
                 font=U.FONT_B).pack(side="right")

    # **다 담고 나서 창을 내용에 맞춘다.**
    #
    # 줄 수만 세서 높이를 잡으면 모자란다. 제목과 설명이 길면 여러 줄로
    # 접히는데 그 줄 수는 글꼴에 달렸고, 글꼴은 OS 마다 다르다. 맥에서
    # 맞춰 둔 숫자가 윈도우(맑은 고딕)에서 맞으리라는 보장이 없다.
    #
    # 글자를 줄이지 않는다. 칸을 늘린다.
    try:
        win.update_idletasks()
        need = win.winfo_reqheight()
        if need > win.winfo_height():
            win.geometry("%dx%d" % (win.winfo_width() or 420, need))
    except Exception:                                      # noqa: BLE001
        pass

    win.grab_set()
    parent.wait_window(win)


def ask_new_learns(app, mon, r):
    """도구를 쓴 뒤 '배우려고 기다리는 기술' 이 새로 생겼으면 바로 묻는다. 물었으면 True (1.13.3).

    게시판 #279 (주호): 로토무카탈로그로 워시로토무가 되면 기술이 넷이라 하이드로펌프가 기다리는 기술이 되는데,
    가방은 진화만 챙기고 이것을 안 봐서 '배우겠습니까' 가 안 떴다 - 레벨업을 해야 그제야 물었다. 이상한사탕으로
    레벨이 올라 생긴 것도 같다. **원래 있던 기다리는 기술로는 다시 묻지 않는다** (쓰기 전의 mon 과 견준다).
    진화하면 진화 연출이 따로 묻는다 - 부르는 쪽이 그때는 안 부른다.
    """
    before = set((mon or {}).get("pending") or [])
    after = set(((r or {}).get("pokemon") or {}).get("pending") or [])
    want = getattr(app, "want_learn", None)
    if not (after - before) or want is None:
        return False
    want((mon or {}).get("id"), ((mon or {}).get("info") or {}).get("name") or "")
    return True


def evolve_lines(info):
    """진화 알림의 글 둘: (진화했다는 말, 배운 기술 줄 또는 ''). 화면(기본 · 테마)이 같이 쓴다.

    '(으)로' 는 natural() 이 못 고치는 표기다. '로(으로)' 로 적어야 앞말의 받침을 보고 '로 / 으로' 가
    제대로 골라진다. 진화하면서 배우는 기술이 있으면 같이 적고, 자리가 없어 못 배운 것도 적는다 -
    잠시 뒤에 무엇을 잊을지 묻는 창이 뜬다.
    """
    head = natural("%s은(는) %s로(으로) 진화했다!" % (info.get("fromKr", "?"), info.get("toKr", "?")))
    learned = info.get("learned") or []
    pending = info.get("pending") or []
    line = ""
    if learned or pending:
        bits = []
        if learned:
            bits.append("%s 을(를) 배웠다!" % ", ".join(learned))
        if pending:
            bits.append("%s 을(를) 배우려 한다." % ", ".join(pending))
        line = natural("  ".join(bits))
    return head, line


def evolve_images(app, info, height=72):
    """작업 스레드에서. 진화 전 · 후의 도트 (PIL 그림 또는 None) 둘."""
    out = []
    for num in (info.get("fromNum"), info.get("toNum")):
        path = sprite_cache.ensure(app.api, num, False)
        img = None
        if path:
            try:
                anim = sprites.load_animation(path, target_height=height,
                                              min_scale=0.2, max_scale=3.0,
                                              max_frames=1)
                img = sprites.to_rgba(anim.frames[sprites.RIGHT][0],
                                      anim.key)
            except Exception:                           # noqa: BLE001
                img = None
        out.append(img)
    return out


@skins.skinnable_fn("announce")
def announce_evolve(parent, app, info):
    """진화했다고 크게 알린다.

    바탕화면 연출은 다른 파일이 맡는다. 여기서는 글로 알리는 것과, 전/후
    **실제 도트**를 나란히 보여주는 것까지만 한다. 대화상자 껍데기는
    ui_box 의 것을 그대로 쓴다. 창마다 다시 그리면 미묘하게 달라진다.
    """
    win, f = ui_box._shell(parent, "진화!", 420, 316)
    keep = {}

    tk.Label(f, text="축하합니다!", bg=U.BG, fg=U.ACCENT_TEXT,
             font=(U.FAMILY_BLACK, U.pt(20))).pack(anchor="w")
    head, learn_line = evolve_lines(info)
    tk.Label(f, text=head, bg=U.BG, fg=U.FG, font=U.FONT_H, wraplength=360,
             justify="left").pack(anchor="w", pady=(6, 0))
    if learn_line:
        tk.Label(f, text=learn_line, bg=U.BG, fg=U.ACCENT_TEXT,
                 font=U.FONT_S, wraplength=360,
                 justify="left").pack(anchor="w", pady=(2, 0))

    art = tk.Frame(f, bg=PANEL, highlightthickness=2, highlightbackground=U.LINE,
                   height=U.h(110))
    art.pack(fill="x", pady=(14, 0))
    art.pack_propagate(False)
    before = tk.Label(art, bg=PANEL, text="...", fg=U.FG_FAINT, font=U.FONT_S)
    before.pack(side="left", expand=True)
    tk.Label(art, text="→", bg=PANEL, fg=U.ACCENT, font=U.FONT_T).pack(side="left")
    after = tk.Label(art, bg=PANEL, text="...", fg=U.FG_FAINT, font=U.FONT_S)
    after.pack(side="left", expand=True)

    def work():
        return evolve_images(app, info)

    def done(imgs, err):
        if err or not imgs:
            return
        for lb, img, tag in ((before, imgs[0], "b"), (after, imgs[1], "a")):
            if img is None:
                continue
            try:
                keep[tag] = ImageTk.PhotoImage(img)
                lb.configure(image=keep[tag], text="")
            except tk.TclError:
                return
    U.run_async(parent, work, done)

    row = tk.Frame(f, bg=U.BG)
    row.pack(fill="x", pady=(14, 0))
    U.PushButton(row, "좋아!", win.destroy, height=34,
                 font=U.FONT_B).pack(side="right")
    # 맥은 줄이 높아서 316 으로는 '좋아!' 단추가 아래에서 눌렸다. 모자라면 늘린다.
    ui_box.grow(win)
    win.grab_set()
    parent.wait_window(win)
