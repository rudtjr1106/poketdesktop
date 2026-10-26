# -*- coding: utf-8 -*-
"""DP 테마의 바탕화면 알림 창들 - 선물 · 진화 · 부화 · 탐험 전리품 · 메가스톤 (v2: 단순 · 잘 보임).

DP 에서 무엇을 받거나 진화할 때처럼 **글상자 하나와 그 위의 무대**로 짠다. 무늬 · 겹친 테 · 테두리 글씨는 걷고,
창 크기는 기본 알림 창보다 크지 않게 줄였다 (그림은 도트 · 도구 그림만 - 그 밖의 아이콘은 쓰지 않는다).

    선물      글상자('선물이 도착했습니다!' · 보낸 제목 · 메시지) → 도구 목록 판(그림 · 이름, 흰 판)
              → 안내 글 → 빨간 '고맙습니다'
    진화      옅은 하늘색 무대에 진화 전 · 후 도트(발밑 그림자 · 이름 꼬리표)와 빨간 ▶ → 글상자
              '축하합니다! ○○는 ○○로 진화했다!' (배운 기술은 글상자 안 둘째 줄) → 빨간 '좋아!'
    부화      같은 무대에 태어난 도트(알 이름 꼬리표) → 글상자 '알이 부화했다! ○○이 태어났다!'
              → Lv · 색이 다른 개체 · 파티/박스 꼬리표 → 빨간 '반가워!'
    전리품    글상자 → 카드들이 굴러가는 칸 (카드 한 장 = 위에 보라 띠: 누가 어디서 몇 시간, 성공도 꼬리표 /
              아래 흰 판: 데려온 포켓몬 · 물건 줄 · 성장) → 안내 · 빨간 '확인'. 길면 창을 키우지 않고 안쪽이 굴러간다.
    메가스톤  글상자 → 흰 판(줄마다 글) → 안내 글 → 빨간 '확인'

무엇을 적을지 · 닫을 때 부르는 것 · 그림을 받아 오는 일은 기본 함수의 도우미를 그대로 쓴다
(ui_bag.gift_notes · evolve_lines · evolve_images, eggs_ui.hatch_facts · hatch_photo,
expedition_ui.loot_lines · loot_summary, bond_stone.got_texts) - 여기는 짓는 것만 한다.
받는 것 · 돌려주는 것은 기본 함수와 같다 (모달인 것은 닫힐 때까지 기다리고, 부화 · 스톤은 창을 돌려준다).
"""
import tkinter as tk

from PIL import ImageTk

from common.korean import natural

from ... import bond_stone as BS
from ... import eggs_ui as E
from ... import expedition_ui as XU
from ... import ui_bag as BAG
from ... import ui_box as B
from ... import ui_common as U
from . import CYAN1, DIM, INK, INK2, LINE, PURPLE, SEP, WHITE, font, poke_icons, tone
from . import kit as K
from .dialogs import BODY, PAD

MUTED = INK2                         # 둘째 줄 글 (INK 보다 옅게)
GROUND = "#b3c4d4"                   # 무대의 발밑 그림자
SLOT = 30                            # 도구 · 도트 그림 자리 (한 변, 기본 화면과 같다)
ROW = 34                             # 도구 한 줄 (기본 화면과 같은 높이)

# 꼬리표 빛깔 (옅은 바탕 + 같은 빛의 진한 글씨로 칠한다)
TIER_CHIP = {"common": "#8a8e96", "uncommon": "#3f9a3f", "rare": "#3a70d0", "epic": "#8a58c8",
             "held": "#e08a20", "tm": "#d0742a"}
GRADE_CHIP = {"great": "#e07a28", "good": "#3f9a3f", "normal": "#7c8494"}
EGG_CHIP = {"legendary": "#e0a020", "mythical": "#9a68d8"}
LEVEL_CHIP, SHINY_CHIP, ON_CHIP, BOX_CHIP = "#3a72cc", "#d8a020", "#4ca83a", "#e07a28"


# ---------------------------------------------------------------- 도우미
def _mix(a, b, t):
    """a 에 b 를 t 만큼 섞은 빛깔."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(ca, cb))


def chip_w(cv, text, spec=None):
    return K.tkfont_of(cv, spec or font(9)).measure(text) + U.h(14)


def chip(cv, x, y, text, col, spec=None, tags=()):
    """꼬리표 (x 에서 오른쪽으로, y 가 세로 가운데) - 옅은 바탕에 같은 빛의 진한 글씨. 그린 폭."""
    spec = spec or font(9)
    w = chip_w(cv, text, spec)
    h = K.tkfont_of(cv, spec).metrics("linespace") + U.h(4)
    K.rrect(cv, x, y - h // 2, x + w, y - h // 2 + h, U.h(4), fill=_mix(col, "#ffffff", 0.8),
            outline=_mix(col, "#ffffff", 0.45), width=1, tags=tags)
    cv.create_text(x + w // 2, y, text=text, fill=_mix(col, "#000000", 0.42), font=spec, anchor="center", tags=tags)
    return w


def _canvas(parent, width, height=10, **pack):
    cv = tk.Canvas(parent, bg=BODY, highlightthickness=0, bd=0, width=width, height=height)
    cv.pack(**(pack or {"fill": "x"}))
    return cv


def _msg(cv, x1, y1, x2, parts):
    """DP 글상자 (흰 판 · 진한 테 한 겹). parts = [(글, 글꼴, 빛깔)] 를 줄 사이를 띄워 쌓는다. 그린 바닥의 y."""
    s = U.h
    tw = x2 - x1 - s(28)
    hs = [K.text_height(cv, t, sp, tw) for t, sp, _c in parts]
    gap = s(3)
    y2 = y1 + s(10) + sum(hs) + gap * (len(parts) - 1) + s(10)
    K.panel(cv, x1 + 1, y1 + 1, x2 - 1, y2, strong=True)       # 캔버스 가장자리에서 테가 잘리지 않게 한 칸 안으로
    y = y1 + s(10)
    for (t, sp, col), h in zip(parts, hs):
        K.text(cv, x1 + s(14), y, t, sp, fill=col, anchor="nw", width=tw)
        y += h + gap
    return y2


def _ellipsis(cv, text, spec, width):
    """한 줄에 안 들어가면 끝을 …로 줄인다 (글꼴은 그대로)."""
    f = K.tkfont_of(cv, spec)
    if f.measure(text) <= width:
        return text
    while text and f.measure(text + "…") > width:
        text = text[:-1]
    return text + "…"


class _Slot(object):
    """캔버스 위의 그림 자리. 기본 화면의 그림 넣는 함수(ui_bag._gift_icon · expedition_ui._mon_thumb)가
    Label 에 하듯 configure(image=) 로 부르면 그 자리에 그림을 놓는다."""

    def __init__(self, cv, x, y, anchor="center"):
        self.cv, self.x, self.y, self.anchor = cv, x, y, anchor

    def configure(self, image=None, **_kw):
        if image is None:
            return
        try:
            self.cv.create_image(self.x, self.y, image=image, anchor=self.anchor)
        except tk.TclError:
            pass                              # 그사이 창을 닫았다

    config = configure


def _button(cv, text, command, right, y, h=None, kind="red"):
    """오른쪽 끝이 right 인 단추. (단추, 폭)."""
    s = U.h
    b = K.CButton(cv, text, command, kind, font(11))
    w = max(b.want_width(s(36)), s(110))
    b.layout(right - w - 1, y, right - 1, y + (h or s(36)))
    return b, w


def _keys(win, close):
    win.bind("<Return>", lambda _e: close())
    win.bind("<Escape>", lambda _e: close())


def _wait(parent, win):
    B.fit(win)
    win.grab_set()
    win.focus_force()
    parent.wait_window(win)


def _plate(cv, x1, y1, x2, y2):
    """목록 판 - 흰 바탕에 가는 테 한 겹."""
    K.panel(cv, x1 + 1, y1, x2 - 1, y2)


def _icon(cv, name, cx, cy, keep=None):
    """본가 도구 그림(poke_icons) 한 개 - 도구 그림이 없는 선물(돈 · 명패) 자리."""
    ph = poke_icons.photo(name)
    if ph is not None:
        cv.create_image(cx, cy, image=ph)
        if keep is not None:
            keep["ico_" + name] = ph


def _stage(cv, x1, y1, x2, h):
    """옅은 하늘색 무대 (무늬 없이). 그린 바닥의 y."""
    K.panel(cv, x1 + 1, y1 + 1, x2 - 1, y1 + h, fill=CYAN1)
    return y1 + h


def _ground(cv, cx, y):
    s = U.h
    cv.create_oval(cx - s(38), y - s(6), cx + s(38), y + s(6), fill=GROUND, outline="")


def _tag(cv, cx, y, text):
    """가운데 맞춘 이름표 (파란 꼬리표). (x1 이 cx 에서 왼쪽으로 반 폭, y 가 위). 높이."""
    spec = font(10)
    w = K.tkfont_of(cv, spec).measure(text) + U.h(16)
    return K.tag(cv, cx - w // 2, y, text, spec=spec)[1]


def _tag_h(cv):
    return K.tkfont_of(cv, font(10)).metrics("linespace") + U.h(6)


# ---------------------------------------------------------------- 선물
FALLBACK_ICON = {"money": "amulet-coin", "frame": "member-card"}      # 칭호는 맞는 그림이 없어 글만


def announce_gifts(parent, app, gifts):
    if not gifts:
        return
    s = U.h
    head, msg, footer = BAG.gift_notes(gifts)
    keep = {}
    win, f = B._shell(parent, "선물", 420, 300)
    win.keep = keep
    width = 420 - 2 * PAD
    cv = _canvas(f, width)
    parts = [("선물이 도착했습니다!", font(11), INK)]
    if head:
        parts.append((head, font(11), INK))
    if msg:
        parts.append((natural(msg), font(9), DIM))
    y = _msg(cv, 0, 0, width, parts) + s(10)

    # 도구 목록 판 - 줄마다 그림 자리(30) · 이름. 이름이 길면 접고 줄이 늘어난다.
    shown = gifts[:8]
    tx = s(14) + s(SLOT) + s(10)
    tw = width - tx - s(16)
    rows = [max(s(ROW), K.text_height(cv, BAG.gift_line(g), font(11), tw) + s(10)) for g in shown]
    more = s(24) if len(gifts) > 8 else 0
    top = y
    h = s(4) + sum(rows) + more + s(4)
    _plate(cv, 0, top, width, top + h)
    cy0 = top + s(4)
    for i, (g, rh) in enumerate(zip(shown, rows)):
        cy = cy0 + rh // 2
        if i:
            cv.create_line(s(12), cy0, width - s(12), cy0, fill=SEP)
        cx = s(14) + s(SLOT) // 2
        icon_id = BAG.gift_icon_id(g)
        if not icon_id and g.get("kind") == "balls":
            icon_id = "POKEBALL"                         # 몬스터볼은 앱의 도구 그림으로
        if icon_id:
            BAG._gift_icon(parent, app, _Slot(cv, cx, cy), icon_id, keep, i)
        elif g.get("kind") in FALLBACK_ICON:
            _icon(cv, FALLBACK_ICON[g["kind"]], cx, cy, keep)
        K.text(cv, tx, cy, BAG.gift_line(g), font(11), anchor="w", width=tw)
        cy0 += rh
    if more:
        K.text(cv, s(14), cy0 + more // 2, "그 밖 %d개" % (len(gifts) - 8), font(9), fill=DIM, anchor="w")
    y = top + h + s(10)
    K.text(cv, 0, y, footer, font(10), fill=MUTED, anchor="nw", width=width)
    y += K.text_height(cv, footer, font(10), width) + s(12)
    b, _w = _button(cv, "고맙습니다", win.destroy, width, y)
    win.buttons = (b,)
    cv.configure(height=y + s(36))
    _keys(win, win.destroy)
    _wait(parent, win)


# ---------------------------------------------------------------- 진화
def announce_evolve(parent, app, info):
    s = U.h
    win, f = B._shell(parent, "진화!", 420, 316)
    keep = {}
    win.keep = keep
    width = 420 - 2 * PAD
    cv = _canvas(f, width)

    # 무대: 진화 전 → 후. 발밑 그림자 위에 도트를 세운다 (도트는 아직 못 받았으면 '...' 부터).
    gy = s(10) + 84                                   # 도트 발밑 (도트는 84 칸)
    sh = gy + s(8) + _tag_h(cv) + s(10)
    _stage(cv, 0, 0, width, sh)
    ay = gy - 42
    slots = {}
    for tag, cx, name in (("b", width * 27 // 100, info.get("fromKr") or "?"),
                          ("a", width * 73 // 100, info.get("toKr") or "?")):
        _ground(cv, cx, gy)
        slots[tag] = (cx, cv.create_text(cx, ay, text="...", fill=DIM, font=font(11), tags=("ph_" + tag,)))
        _tag(cv, cx, gy + s(8), name)
    mx = width // 2
    K.cursor(cv, mx - s(8), ay, size=s(11))

    head, learn = BAG.evolve_lines(info)
    parts = [("축하합니다!", font(11), INK), (head, font(11), INK)]
    if learn:
        parts.append((learn, font(10), tone(U.ACCENT_TEXT)))
    y = _msg(cv, 0, sh + s(10), width, parts)

    def work():
        return BAG.evolve_images(app, info, 84)

    def done(imgs, err):
        if err or not imgs:
            return
        for img, tag in zip(imgs, ("b", "a")):
            if img is None:
                continue
            try:
                keep[tag] = ImageTk.PhotoImage(img)
                cv.delete("ph_" + tag)
                cv.create_image(slots[tag][0], gy, image=keep[tag], anchor="s")
            except tk.TclError:
                return
    U.run_async(parent, work, done)

    y += s(12)
    b, _w = _button(cv, "좋아!", win.destroy, width, y)
    win.buttons = (b,)
    cv.configure(height=y + s(36))
    _keys(win, win.destroy)
    _wait(parent, win)


# ---------------------------------------------------------------- 부화
def _chips(cv, x, y, width, items):
    """꼬리표를 왼쪽부터 늘어놓고 폭이 모자라면 다음 줄로. 그린 바닥의 y."""
    s = U.h
    cx, cy = x, y
    step = K.tkfont_of(cv, font(9)).metrics("linespace") + s(10)
    for text, col in items:
        w = chip_w(cv, text)
        if cx > x and cx + w > x + width:
            cx, cy = x, cy + step
        chip(cv, cx, cy + step // 2, text, col)
        cx += w + s(8)
    return cy + step


def announce_hatch(parent, app, egg, on_close=None):
    s = U.h
    name, mon, bits = E.hatch_facts(egg)
    win, f = B._shell(parent, "알이 부화했다", 400, s(360))
    keep = {}
    win.keep = keep
    width = 400 - 2 * PAD

    def close():
        try:
            win.destroy()
        except tk.TclError:
            pass
        if on_close:
            on_close()
    win.protocol("WM_DELETE_WINDOW", close)
    cv = _canvas(f, width)

    gy = s(10) + 96                                   # 도트 발밑 (도트는 96 칸)
    sh = gy + s(16)
    _stage(cv, 0, 0, width, sh)
    cx = width // 2
    _ground(cv, cx, gy)
    egg_name = egg.get("name") or ""
    if egg_name:
        chip(cv, s(10), s(18), egg_name, EGG_CHIP.get(egg.get("kind"), PURPLE))

    def show(ph):
        keep["mon"] = ph
        cv.create_image(cx, gy, image=ph, anchor="s")
    E.hatch_photo(app, mon, 96, show, parent)

    y = _msg(cv, 0, sh + s(10), width,
             [("알이 부화했다!", font(11), INK), (natural("%s이(가) 태어났다!" % name), font(11), INK)])
    chips = []
    for text, kind in bits:
        col = {"level": LEVEL_CHIP, "shiny": SHINY_CHIP}.get(kind)
        if kind == "party":
            col = ON_CHIP if mon.get("onDesktop") else BOX_CHIP
        chips.append((text, col))
    if chips:
        y = _chips(cv, 0, y + s(4), width, chips)
    y += s(8)
    b, _w = _button(cv, "반가워!", close, width, y)
    win.buttons = (b,)
    cv.configure(height=y + s(36))
    _keys(win, close)
    B.fit(win)
    return win


# ---------------------------------------------------------------- 탐험 전리품
def _loot_cards(cv, w, lines, claimed, live, win, app, keep):
    """받은 것 카드들을 cv 에 그린다. 그린 높이. live 가 아니면 그림은 안 받고 크기만 잰다 (재기용).

    카드 한 장 = 위에 보라 띠(누가 어디서 몇 시간 · 성공도 꼬리표) + 아래 흰 판 (한 겹으로 이어 붙였다)."""
    s = U.h
    pad = s(14)
    y = 0
    tag = 0
    spec, small = font(11), font(9)
    for (head, grade, grade_kr, rows), one in zip(lines, claimed):
        bh = s(28)

        # 판 안에 넣을 덩어리들: (높이, 그리는 함수(y))
        blocks = []
        if not rows:
            blocks.append((s(28), lambda yy: K.text(cv, pad, yy + s(14), "아무것도 못 찾았다...", font(10),
                                                    fill=DIM, anchor="w")))
        came = XU.friend_line(one)
        if came:
            text, badge = came
            bw = (chip_w(cv, badge) + s(10)) if badge else 0
            tw = w - 2 * pad - ((s(SLOT) + s(10)) if badge else 0) - bw
            fh = max(s(ROW), K.text_height(cv, text, spec if badge else small, tw) + s(10))

            def friend(yy, text=text, badge=badge, tw=tw, fh=fh, one=one):
                x = pad
                if badge:
                    nonlocal tag
                    if live:
                        XU._mon_thumb(win, app, _Slot(cv, x + s(SLOT) // 2, yy + fh // 2), one["friend"], keep,
                                      "friend%d" % tag)
                    tag += 1
                    x += s(SLOT) + s(10)
                    chip(cv, w - pad - chip_w(cv, badge), yy + fh // 2, badge, SHINY_CHIP)
                K.text(cv, x, yy + fh // 2, text, spec if badge else small, fill=tone(U.ACCENT_TEXT) if badge else DIM,
                       anchor="w", width=tw)
            blocks.append((fh, friend))
        for item_id, text, n, tier in rows:
            note = "새 기술머신" if tier == "tm" else XU.TIER_KR.get(tier, "")
            label = "%s%s" % (text, " × %d" % n if n > 1 else "")
            cw = (chip_w(cv, note) + s(10)) if note else 0
            tw = w - 2 * pad - s(SLOT) - s(10) - cw
            ih = max(s(ROW), K.text_height(cv, label, spec, tw) + s(10))

            def item(yy, item_id=item_id, label=label, note=note, tier=tier, tw=tw, ih=ih):
                nonlocal tag
                if item_id and live:
                    BAG._gift_icon(win, app, _Slot(cv, pad + s(SLOT) // 2, yy + ih // 2), item_id, keep, tag)
                if item_id:
                    tag += 1
                K.text(cv, pad + s(SLOT) + s(10), yy + ih // 2, label, spec,
                       fill=tone(U.ACCENT_TEXT) if tier == "tm" else INK, anchor="w", width=tw)
                if note:
                    chip(cv, w - pad - chip_w(cv, note), yy + ih // 2, note, TIER_CHIP.get(tier, TIER_CHIP["common"]))
            blocks.append((ih, item))
        grown = XU.growth_note(one)
        if grown:
            tw = w - 2 * pad
            texts = [(t, c) for t, c in ((grown[0], tone(U.SHINY) if grown[2] else MUTED), (grown[1], DIM)) if t]
            gh = s(8) + sum(K.text_height(cv, t, small, tw) + s(2) for t, _c in texts) + s(2)

            def growth(yy, texts=texts, tw=tw):
                cv.create_line(s(12), yy + s(1), w - s(12), yy + s(1), fill=SEP)
                ty = yy + s(6)
                for t, c in texts:
                    K.text(cv, pad, ty, t, small, fill=c, anchor="nw", width=tw)
                    ty += K.text_height(cv, t, small, tw) + s(2)
            blocks.append((gh, growth))

        total = bh + sum(h for h, _fn in blocks) + s(8)
        K.rrect(cv, 1, y, w - 1, y + total, s(6), fill=WHITE, outline=LINE, width=1)
        K.rrect(cv, 1, y, w - 1, y + bh, s(6), fill=PURPLE)
        cv.create_rectangle(2, y + bh // 2, w - 2, y + bh, fill=PURPLE, outline="")
        # 보라 띠: 누가 어디서 몇 시간 - 오른쪽에 성공도 꼬리표 (흰 글씨)
        room = w - 2 * s(14) - ((chip_w(cv, grade_kr) + s(10)) if grade_kr else 0)
        K.text(cv, s(14), y + bh // 2, _ellipsis(cv, head, font(10), room), font(10), fill=WHITE, anchor="w")
        if grade_kr:
            chip(cv, w - s(10) - chip_w(cv, grade_kr), y + bh // 2, grade_kr,
                 GRADE_CHIP.get(grade, TIER_CHIP["common"]))
        yy = y + bh + s(4)
        for h, fn in blocks:
            fn(yy)
            yy += h
        y += total + s(8)
    return y - s(8)


def show_loot(parent, app, claimed):
    s = U.h
    lines = XU.loot_lines(claimed)
    if not lines:
        return
    keep = {}
    win, f = B._shell(parent, "탐험", XU.LOOT_W, s(260))
    win.keep = keep
    width = XU.LOOT_W - 2 * PAD
    top = _canvas(f, width)
    top.configure(height=_msg(top, 0, 0, width, [("탐험에서 돌아왔습니다!", font(11), INK),
                                                (XU.loot_summary(lines, claimed), font(10), MUTED)]))

    # 바닥 줄(안내 + 확인)을 먼저 잡는다 - 굴러가는 칸이 높이를 다 먹어 단추가 밀려나지 않게
    foot = _canvas(f, width, s(36), side="bottom", fill="x", pady=(s(10), 0))
    foot.create_text(0, s(18), text="가방에 넣어 두었습니다.", fill=MUTED, font=font(10), anchor="w")
    b, _w = _button(foot, "확인", win.destroy, width, s(1))
    win.buttons = (b,)

    wrap = tk.Frame(f, bg=BODY)
    wrap.pack(fill="both", expand=True, pady=(s(10), 0))
    cv = tk.Canvas(wrap, bg=BODY, highlightthickness=0, bd=0, width=width, height=1, yscrollincrement=1)
    cv.pack(side="left", fill="both", expand=True)
    sb = K.Scroll(wrap, cv, BODY)
    cv.configure(yscrollcommand=sb.set)

    # 창 높이는 화면의 2/3 까지. 먼저 재서(그림 없이) 넘치는지 보고, 넘치면 굴림 막대 몫을 빼고 그린다.
    win.update_idletasks()
    hi = XU.loot_max_height(win)
    avail = max(s(160), hi - win.winfo_reqheight() + 1) if hi else None
    probe = tk.Canvas(win)
    try:
        need = _loot_cards(probe, width, lines, claimed, False, win, app, {})
    finally:
        probe.destroy()
    scroll = avail is not None and need > avail
    w = width - s(16) if scroll else width
    h = _loot_cards(cv, w, lines, claimed, True, win, app, keep)
    if scroll:
        sb.pack(side="right", fill="y", before=cv)
        cv.configure(width=w, height=avail, scrollregion=(0, 0, w, h))
        U.scrollable(cv, 3)
        U.install_wheel(win)
    else:
        cv.configure(height=h, scrollregion=(0, 0, w, h))
    win.loot_scroll = (cv, scroll, h, avail)
    _keys(win, win.destroy)
    _wait(parent, win)


# ---------------------------------------------------------------- 메가스톤
def announce_got(parent, got):
    if not got:
        return
    s = U.h
    title, head, lines, note = BS.got_texts(got)
    win, f = B._shell(parent, title, 440, s(250))
    win.keep = keep = {}
    width = 440 - 2 * PAD
    cv = _canvas(f, width)

    # 글상자 한 장 안에 첫 줄(받았다) + 줄마다 글 (유대 미션을 마치고 받은 돌)
    tx = s(14)
    tw = width - tx - s(16)
    hh = K.text_height(cv, head, font(11), width - s(28))
    rows = [max(s(30), K.text_height(cv, t, font(10), tw) + s(8)) for t in lines]
    y2 = s(10) + hh + s(6) + sum(rows) + s(6)
    K.panel(cv, 1, 1, width - 1, y2, strong=True)
    K.text(cv, s(14), s(10), head, font(11), anchor="nw", width=width - s(28))
    yy = s(10) + hh + s(6)
    for i, (t, rh) in enumerate(zip(lines, rows)):
        cv.create_line(s(12), yy, width - s(12), yy, fill=SEP)
        K.text(cv, tx, yy + rh // 2, t, font(10), anchor="w", width=tw)
        yy += rh
    y = y2 + s(10)
    nh = K.text_height(cv, note, font(10), width)
    K.text(cv, 0, y, note, font(10), fill=MUTED, anchor="nw", width=width)
    y += nh + s(12)
    b, _w = _button(cv, "확인", win.destroy, width, y)
    win.buttons = (b,)
    cv.configure(height=y + s(36))
    _keys(win, win.destroy)
    B.fit(win)
    return win
