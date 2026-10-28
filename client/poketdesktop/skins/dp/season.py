# -*- coding: utf-8 -*-
"""DP 테마의 랭크 팀 (길드전 방어팀 · 공격팀도 같은 창) 과 칭호 · 명패 달기.

v2 (2026-10-25): 기본 창과 같은 크기(560x660)에 한 단으로 다시 짰다. 무늬 · 겹친 테 · 테두리 글씨를 걷고,
DP 의 모서리 깎은 하늘색 판 · 보라 설명 띠 · 빨간 커서는 남겼다.

랭크 팀:

    [등록됨] 4 / 6마리                       [바탕화면 파티로 채우기] [비우기] [등록 풀기]
    ▓ 보라 띠: 이 팀의 규칙 ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    [모서리를 깎은 하늘색 판 3 x 2: 차례 · 이름 · 레벨 · 도트]  (판을 누르면 뺀다 - 주황 테)
    포켓몬 찾기 [      ]                                       12마리
    ┌ 흰 목록: 도트 · 이름 · 레벨 · 데리고 다님 · 전설·환상, 고른 줄은 크림빛에 빨간 차례 공 ┐
    ├ 글상자 (알림) ─────────────────────────────────────────────── [등록] ┤

칭호 · 명패는 위에 이름 미리 보기 (이름이 명패 빛깔, 그 옆에 칭호), 그 아래 파란 꼬리표와 흰 상자에 고를 것들
(고른 줄은 빨간 화살표 · 크림빛), 아래에 글상자와 '닫기 · 달기'.

받기 · 고르기 규칙 · 저장 · 알릴 말은 기본 창(ui_season.TeamWindow · RewardsWindow) 그대로다 - 짓는 고리만 바꾼다.
"""
import tkinter as tk

from PIL import ImageTk

from common import tint as Tn

from ... import item_icons, sprite_cache, sprites
from ... import ui_common as U
from ... import ui_season as S
from . import (CUR, DIM, HOV, INK, INK2, LINE, LINE_D, PLATE_HOVER_TOP, PLATE_LINE, PLATE_SEL, PLATE_TOP, PURPLE,
               SEL, SEP, WHITE, WIN_BG, font, tone)
from . import poke_icons
from . import kit as K
from .dialogs import BODY, PAD, clamp_lines, dialog_bar, heading
from .scene import T, Scene

LEGEND = "#b8860b"
DESK = "#3a72cc"
EMPTY_FILL = "#f2f5f8"


def one_line(cv, text, spec, width):
    """한 줄에 넣는다 - 넘치면 글자를 덜고 끝에 '…'. (clamp_lines 는 띄어쓰기에서 먼저 접어서 '★ 긴별명' 이
    '★…' 이 된다)"""
    f = K.tkfont_of(cv, spec)
    text = (text or "").replace("\n", " ")
    if f.measure(text) <= width:
        return text
    while text and f.measure(text + "…") > width:
        text = text[:-1]
    return text.rstrip() + "…"


def chip_w(cv, text, spec=None):
    return K.tkfont_of(cv, spec or font(9)).measure(text) + U.h(12)


def chip(cv, x, y, text, col, spec=None, tags=()):
    """빛깔 꼬리표 (x 에서 오른쪽으로, y 가 가운데). 그 폭. 흰 글씨 (테두리 없음)."""
    spec = spec or font(9)
    w = chip_w(cv, text, spec)
    h = K.tkfont_of(cv, spec).metrics("linespace") + U.h(4)
    K.rrect(cv, x, y - h // 2, x + w, y + h // 2, U.h(4), fill=col, tags=tags)
    cv.create_text(x + w // 2, y, text=text, fill="#ffffff", font=spec, anchor="center", tags=tags)
    return w


def mark(cv, cx, cy, r, tags=(), keep=None):
    """도트가 아직 없을 때 그 자리에 놓는 몬스터볼 (앱의 도구 그림 - 직접 그리지 않는다)."""
    ph = item_icons.photo("POKEBALL", r * 2) or poke_icons.photo("poke-ball")
    if ph is None:
        return
    if keep is not None:
        keep.append(ph)
    cv.create_image(cx, cy, image=ph, tags=tags)


# ---------------------------------------------------------------- 랭크 팀
class TeamWindow(Scene, S.TeamWindow):
    SIZE = (560, 660, 460, 520)          # 기본 창과 같다
    RH_PX = 38              # 목록 한 줄
    THUMB = 30              # 도트 높이
    PH_PX = 46              # 파티 판

    # ---------------- 짓기 ----------------
    def _build(self, title):
        self.RH = U.h(self.RH_PX)
        self.photos = {}                 # (도감 번호, skin, 판의 것인가) -> PhotoImage
        self._thumb_busy = set()
        self._thumb_miss = set()         # 못 받은 도트 - 이 창에서는 다시 묻지 않는다 (몬스터볼로 둔다)
        self._by = {}                    # 포켓몬 id -> 포켓몬
        self._note = ""
        self._found = ""
        self._nomatch = ""
        self._unreg_on = False
        self._phover = None              # 마우스가 올라간 파티 판 (자리 번호)
        self._pboxes = {}                # 자리 번호 -> 판 (x1, y1, x2, y2)
        self._pitems = {}                # 자리 번호 -> (테, 바탕) - 올림은 빛깔만 바꾼다 (지우지 않는다)
        self._keep = []                  # 그린 그림 (파이썬이 놓으면 Tk 가 지운다)
        dialog_bar(self.win, title)
        self._scene_init()
        self.find_box = K.entry(self.cv, self.q, width=10)
        self.vl = K.VList(self.cv, WHITE, self._draw_row)
        self.vl.on_click = lambda pid, _x, _y, _w: self.toggle(pid)
        self.vl.on_scroll = self._thumbs_visible
        self.fill_btn = K.CButton(self.cv, "바탕화면 파티로 채우기", self.fill_party, "blue", font(10))
        self.clear_btn = K.CButton(self.cv, "비우기", self.clear, "gray", font(10))
        self.unreg_btn = K.CButton(self.cv, "등록 풀기", self.unregister, "gray", font(10))
        self.save_btn = K.CButton(self.cv, "등록", self.save, "red", font(13))
        self.cv.bind("<Motion>", self._motion, add="+")
        self.cv.bind("<Leave>", lambda _e: self._set_phover(None), add="+")
        self.cv.bind("<Button-1>", self._press, add="+")

    def _soon(self):
        # Scene 의 것은 _paint 를 부른다 - 이 창의 _paint 는 '고른 것이 바뀌었다' (기본 창)라서 판은 _draw 로 그린다
        if self._job is None:
            try:
                self._job = self.cv.after_idle(self._draw)
            except tk.TclError:
                pass

    # ---------------- 기본 창이 부르는 고리 ----------------
    def say(self, text, color=U.GOOD):
        # Scene._say 는 글만 바꿔 끼워 줄을 다시 접지 않는다 - 서버 오류처럼 긴 말이 상자 밖으로 나가므로 판을 다시 그린다
        self.msg = (text or "", color)
        self._soon()

    def _paint_note(self, text):
        self._note = text
        self._soon()

    def _show_unreg(self, on):
        self._unreg_on = bool(on)
        self._soon()

    def _row(self, m):
        self._by[m["id"]] = m
        self.rows[m["id"]] = self.row_info(m)

    def _repack(self, old, want):
        self._list_rows(top=True)

    def _paint_found(self, q, want):
        self._found = self.found_text(q, want)
        self._nomatch = self.nomatch_text(q) if (self.mons and not want) else ""
        self._soon()

    def _paint_rows(self):
        self._list_rows()
        try:
            self.vl.refresh()
        except tk.TclError:
            pass

    def _paint_slots(self):
        self._soon()                     # 판의 도트는 판을 그리며 받는다 (_paint_party)

    def _paint_state(self, _text):
        self._soon()                     # 머리는 state_parts() 로 판이 그린다

    # ---------------- 목록 ----------------
    def _list_rows(self, top=False):
        """목록에 담을 줄 = 찾기에 맞은 것 (self.visible - 기본 창이 정한다)."""
        rows = [(self.RH, pid) for pid in self.visible]
        if top or rows != self.vl.rows:
            self.vl.set(rows, keep=not top)
            self._thumbs_visible()

    def _draw_row(self, cv, pid, x, y, w, h, tags, hover=None):
        s = U.h
        r, m = self.rows.get(pid), self._by.get(pid)
        if r is None:
            return
        on = pid in self.picked
        if on or hover is not None:
            cv.create_rectangle(x + 2, y + 1, x + w - 2, y + h - 1, fill=SEL if on else HOV, outline="", tags=tags)
        mid = y + h // 2
        # 고른 차례 (빨간 공) - 안 고른 줄은 빈 동그라미
        cx, rr = x + s(16), s(9)
        if on:
            cv.create_oval(cx - rr, mid - rr, cx + rr, mid + rr, fill=CUR, outline="", tags=tags)
            cv.create_text(cx, mid, text=str(self.picked.index(pid) + 1), fill="#ffffff", font=font(9),
                           anchor="center", tags=tags)
        else:
            cv.create_oval(cx - rr + 2, mid - rr + 2, cx + rr - 2, mid + rr - 2, outline="#c4cad2", width=2,
                           tags=tags)
        ph = self._thumb(m)
        if ph is not None:
            cv.create_image(x + s(48), mid, image=ph, tags=tags)
        else:
            mark(cv, x + s(48), mid, s(9), tags, self._keep)
        # 오른쪽 꼬리표 (오른쪽부터)
        ny = mid - s(8)
        rx = x + w - s(10)
        for label, col, want in (("데리고 다님", DESK, r["desk"]), ("전설·환상", LEGEND, r["restricted"])):
            if want:
                cw = chip_w(cv, label, font(8))
                chip(cv, rx - cw, ny, label, col, font(8), tags=tags)
                rx -= cw + s(6)
        tx = x + s(80)
        name = ("★ " if r["shiny"] else "") + r["name"]
        K.text(cv, tx, ny, one_line(cv, name, font(11), max(s(40), rx - tx - s(8))), font(11),
               fill=tone(U.SHINY) if r["shiny"] else INK, anchor="w", tags=tags)
        sub = r["lv"] + (("  ·  " + r["species"]) if r["species"] else "")
        cv.create_text(tx, mid + s(10), text=one_line(cv, sub, font(9), max(s(40), x + w - s(10) - tx)),
                       fill=INK2, font=font(9), anchor="w", tags=tags)
        cv.create_line(x + s(8), y + h - 1, x + w - s(8), y + h - 1, fill=SEP, tags=tags)

    # ---------------- 도트 ----------------
    @staticmethod
    def _thumb_key(m, big=False):
        return (m.get("formNum") or m.get("num"), Tn.skin(m), big)

    def _thumb(self, m, big=False):
        return self.photos.get(self._thumb_key(m, big)) if m else None

    def _thumbs_visible(self):
        try:
            self._thumbs([self._by[p] for p in self.vl.visible() if p in self._by])
        except tk.TclError:
            pass

    def _thumbs(self, mons, big=False):
        """판 · 보이는 줄의 도트를 받아 둔다 (포켓몬 관리 칸과 같은 길). 못 받으면 몬스터볼을 그린다."""
        want = []
        for m in mons:
            k = self._thumb_key(m, big)
            if k[0] and k not in self.photos and k not in self._thumb_busy and k not in self._thumb_miss \
                    and k not in want:
                want.append(k)
        if not want:
            return
        self._thumb_busy.update(want)
        api = self.app.api
        size = U.h(self.THUMB)

        def work():
            out = {}
            for num, skin, _big in want:
                try:
                    path = sprite_cache.ensure(api, num, skin)
                    if not path:
                        continue
                    anim = sprites.load_animation(path, target_height=size, min_scale=0.2, max_scale=3.0,
                                                  max_frames=1, max_size=(int(size * 1.3), size))
                    out[(num, skin, big)] = sprites.to_rgba(anim.frames[sprites.RIGHT][0], anim.key)
                except Exception:                           # noqa: BLE001
                    pass
            return out

        def done(imgs, err):
            self._thumb_busy.difference_update(want)
            self._thumb_miss.update(k for k in want if not imgs or k not in imgs)
            if err or not imgs:
                return
            for k, img in imgs.items():
                try:
                    self.photos[k] = ImageTk.PhotoImage(img)
                except Exception:                           # noqa: BLE001
                    pass
            self._soon()
            try:
                self.vl.refresh()
            except tk.TclError:
                pass
        U.run_async(self.root, work, done)

    # ---------------- 판 전체 ----------------
    def _draw(self):
        self._job = None
        cv, s = self.cv, U.h
        try:
            W, H = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if W < s(300) or H < s(200):
            return
        cv.delete("scene")
        self._msg_ids = None
        self._keep = []
        BOT = s(56)
        top = H - BOT
        cv.create_rectangle(0, 0, W, top, fill=WIN_BG, outline="", tags=T)
        pad = s(14)
        y = s(10)

        # 머리: 등록 상태 꼬리표 · n / 6마리 · 단추들 (모자라면 단추는 다음 줄로)
        head, count = self.state_parts()
        done = self.registered
        btns = [self.fill_btn, self.clear_btn] + ([self.unreg_btn] if self._unreg_on else [])
        if not self._unreg_on:
            self.unreg_btn.hide()
        ws = [b.want_width(s(24)) for b in btns]
        bgap = s(8)
        btn_total = sum(ws) + bgap * (len(btns) - 1)
        cnt_w = K.tkfont_of(cv, font(12)).measure(count)
        room = W - 2 * pad
        label = one_line(cv, head, font(9), max(s(60), room - cnt_w - s(24)))
        lab_w = chip_w(cv, label, font(9))
        rowh = s(30)
        chip(cv, pad, y + rowh // 2, label, "#2c9a4c" if done else "#8a8e96", font(9), tags=T)
        cv.create_text(pad + lab_w + s(10), y + rowh // 2, text=count, fill=INK, font=font(12), anchor="w", tags=T)
        one_row = lab_w + s(10) + cnt_w + s(16) + btn_total <= room
        by1 = y if one_row else y + rowh + s(6)
        x = W - pad - btn_total if one_row else pad
        for b, w in zip(btns, ws):
            b.layout(x, by1, x + w, by1 + rowh)
            x += w + bgap
        y = by1 + rowh + s(8)

        # 보라 설명 띠
        if self._note:
            y = self._paint_band(cv, pad, y, W - pad, max(s(40), (top - y) - s(300))) + s(8)

        # 아래: 왼쪽에 판 여섯 (한 줄에 한 판), 오른쪽에 찾기 + 목록
        gap = s(10)
        bot = top - s(8)
        LW = int(max(s(150), min(s(200), (W - 2 * pad) * 0.36)))
        n = max(1, self.max)
        pg = s(6)
        PH = int(max(s(40), min(s(52), (bot - y - pg * (n - 1)) / float(n))))
        self._pboxes, self._pitems = {}, {}
        mons = self.slot_mons()
        self._thumbs([m for m in mons if m])
        for i, m in enumerate(mons):
            py1 = y + i * (PH + pg)
            self._plate(cv, i, m, pad, py1, pad + LW, py1 + PH)

        rx1 = pad + LW + gap
        K.panel(cv, rx1, y, W - pad, bot, tags=T)
        th = s(26)
        ix1, ix2 = rx1 + s(10), W - pad - s(10)
        K.text(cv, ix1, y + s(8) + th // 2, "포켓몬 찾기", font(10), anchor="w", tags=T)
        ex = ix1 + K.tkfont_of(cv, font(10)).measure("포켓몬 찾기") + s(8)
        fw = K.tkfont_of(cv, font(9)).measure(self._found) if self._found else 0
        if self._found:
            cv.create_text(ix2, y + s(8) + th // 2, text=self._found, fill=INK2, font=font(9), anchor="e", tags=T)
        self._place("find", self.find_box, ex, y + s(8), max(s(60), ix2 - fw - s(8) - ex), th)
        ly = y + s(8) + th + s(6)
        cv.create_line(rx1 + s(6), ly, W - pad - s(6), ly, fill=SEP, width=2, tags=T)
        ly += s(2)
        if self._nomatch:
            self._hide("list")
            K.text(cv, (rx1 + W - pad) // 2, ly + s(30), self._nomatch, font(11), anchor="n", justify="center",
                   width=W - pad - rx1 - s(30), tags=T)
        else:
            self._place("list", self.vl.frame, rx1 + 2, ly, W - pad - rx1 - 4, max(s(40), bot - ly - 3))
        self._paint_bottom(cv, 0, W, top, H, [(self.save_btn, s(100), s(160))])

    def _plate(self, cv, i, m, x1, y1, x2, y2):
        """파티 판 하나 (모서리를 깎은 하늘색 판). 빈 자리는 옅은 판에 '빈 자리'."""
        s = U.h
        c = s(8)
        mid = (y1 + y2) // 2
        if m is None:
            K.clipped(cv, x1, y1, x2, y2, c, LINE, T)
            K.clipped(cv, x1 + 1, y1 + 1, x2 - 1, y2 - 1, c - 1, EMPTY_FILL, T)
            cv.create_text(x1 + s(14), mid, text=str(i + 1), fill=DIM, font=font(11), anchor="w", tags=T)
            cv.create_text(x1 + s(36), mid, text="빈 자리", fill=DIM, font=font(10), anchor="w", tags=T)
            return
        r = self.rows.get(m["id"]) or self.row_info(m)
        hov = i == self._phover
        tg = T + ("plate",)
        a = K.clipped(cv, x1, y1, x2, y2, c, PLATE_SEL if hov else PLATE_LINE, tg)
        b = K.clipped(cv, x1 + 2, y1 + 2, x2 - 2, y2 - 2, c - 1, PLATE_HOVER_TOP if hov else PLATE_TOP, tg)
        self._pboxes[i] = (x1, y1, x2, y2)
        self._pitems[i] = (a, b)
        ph = self._thumb(m)
        sx = x1 + s(30)
        if ph is not None:
            cv.create_image(sx, mid + s(2), image=ph, tags=tg)
        else:
            mark(cv, sx, mid + s(2), s(11), tg, self._keep)
        # 차례 표 (짧은 꼬리표 - 흰 글씨, 왼쪽 위 모서리)
        K.rrect(cv, x1 + s(5), y1 + s(5), x1 + s(19), y1 + s(19), s(4), fill="#34485e", tags=tg)
        cv.create_text(x1 + s(12), y1 + s(12), text=str(i + 1), fill="#ffffff", font=font(8), anchor="center",
                       tags=tg)
        nx = x1 + s(56)
        right = x2 - s(8)
        name_y, lv_y = mid - s(9), mid + s(11)
        name_right = right
        if r["restricted"]:
            cw = chip_w(cv, "전설", font(8))
            chip(cv, right - cw, name_y, "전설", LEGEND, font(8), tags=tg)
            name_right = right - cw - s(4)
        name = ("★" if r["shiny"] else "") + r["name"]
        K.text(cv, nx, name_y, one_line(cv, name, font(10), max(s(30), name_right - nx)), font(10),
               fill=tone(U.SHINY) if r["shiny"] else INK, anchor="w", tags=tg)
        cv.create_text(nx, lv_y, text=one_line(cv, r["lv"], font(9), max(s(30), right - nx)), fill=INK2,
                       font=font(9), anchor="w", tags=tg)

    def _paint_band(self, cv, x1, y, x2, max_h):
        """보라 띠 (DP 가방의 설명 띠) 에 이 팀의 규칙. 띠 밑의 y."""
        s = U.h
        tw = x2 - x1 - s(24)
        text = self._note
        h = K.text_height(cv, text, font(9), tw) + s(14)
        if h > max_h:                    # 창이 아주 작을 때만 - 목록 자리를 남긴다
            line = K.tkfont_of(cv, font(9)).metrics("linespace")
            text = clamp_lines(cv, text, font(9), tw, max(1, (max_h - s(14)) // max(1, line)))
            h = K.text_height(cv, text, font(9), tw) + s(14)
        K.rrect(cv, x1, y, x2, y + h, s(8), fill=PURPLE, tags=T)
        K.text(cv, x1 + s(12), y + s(7), text, font(9), fill=WHITE, width=tw, tags=T)
        return y + h

    # ---------------- 파티 판 올리기 · 누르기 ----------------
    def _plate_at(self, x, y):
        for i, (x1, y1, x2, y2) in self._pboxes.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return i
        return None

    def _motion(self, e):
        self._set_phover(self._plate_at(e.x, e.y))

    def _set_phover(self, i):
        if i == self._phover:
            return
        old, self._phover = self._phover, i
        for k, on in ((old, False), (i, True)):
            ids = self._pitems.get(k)
            if not ids:
                continue
            a, b = ids
            try:
                self.cv.itemconfigure(a, fill=PLATE_SEL if on else PLATE_LINE)
                self.cv.itemconfigure(b, fill=PLATE_HOVER_TOP if on else PLATE_TOP)
            except tk.TclError:
                pass
        try:
            self.cv.configure(cursor="hand2" if i is not None else "")
        except tk.TclError:
            pass

    def _press(self, e):
        i = self._plate_at(e.x, e.y)
        if i is None:
            return
        ms = self.slot_mons()
        if i < len(ms) and ms[i] is not None:
            self.toggle(ms[i]["id"])         # 판을 누르면 팀에서 뺀다 (목록의 줄을 다시 누른 것과 같다)


# ---------------------------------------------------------------- 칭호 · 명패
class RewardsWindow(S.RewardsWindow):
    W = 440                 # 기본 창과 같다
    MAX_LIST = 270          # 목록 칸이 이보다 길면 창을 키우지 않고 안쪽을 굴린다
    ROW_PX = 27

    def _build(self):
        s = U.h
        self._titles, self._frames = [], []
        self._msg = ("", None)
        self._msg_id = None
        self._msg_w = 0
        self._hits = []                  # [(y1, y2, 변수, 값, 줄 바탕 id, 골랐나)]
        self._hover = None
        self._full = 0
        win = tk.Toplevel(self.root)
        U.style_window(win, "칭호 · 명패", U.wide(self.W), 520)
        U.apply_theme(win)
        win.configure(bg=BODY, highlightthickness=0)
        dialog_bar(win, "칭호 · 명패")
        self.win = win
        # 미리 보기: 랭킹 · 친구 목록에서 내 이름이 어떻게 보이나
        self.pcv = tk.Canvas(win, bg=BODY, highlightthickness=0, bd=0, height=s(50))
        self.pcv.pack(fill="x", padx=PAD, pady=(s(10), 0))
        self.pcv.bind("<Configure>", lambda _e: self._paint_preview())
        # 아래 줄: 글상자 + 닫기 · 달기 (목록보다 먼저 담는다 - 목록이 길어도 늘 보인다)
        self.bcv = tk.Canvas(win, bg=BODY, highlightthickness=0, bd=0, height=s(42))
        self.bcv.pack(side="bottom", fill="x", padx=PAD, pady=(0, s(8)))
        self.bcv.bind("<Configure>", lambda _e: self._paint_foot())
        self.save_btn = K.CButton(self.bcv, "달기", self.save, "red", font(11))
        self.close_btn = K.CButton(self.bcv, "닫기", self.close, "gray", font(11))
        self.body = tk.Frame(win, bg=BODY)
        self.body.pack(fill="both", expand=True, padx=PAD, pady=s(6))
        self.title_var.trace_add("write", lambda *_a: self._repaint())
        self.frame_var.trace_add("write", lambda *_a: self._repaint())

    def say(self, text, color=U.GOOD):
        self._msg = (text or "", color)
        if self._msg_id is not None:
            try:
                self.bcv.itemconfigure(self._msg_id[1], text=self._msg_text(),
                                       fill=tone(color) if color else INK)
                return
            except tk.TclError:
                pass
        self._paint_foot()

    # ---------------- 목록 ----------------
    def _fill(self, titles, frames):
        self._titles, self._frames = list(titles), list(frames)
        wrap = tk.Frame(self.body, bg=BODY)
        wrap.pack(fill="both", expand=True)
        self.cv = tk.Canvas(wrap, bg=BODY, highlightthickness=0, bd=0, yscrollincrement=1, height=1)
        sb = K.Scroll(wrap, self.cv, BODY)
        sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.cv.configure(yscrollcommand=sb.set)
        U.scrollable(self.cv, 3)
        self.cv.bind("<Configure>", lambda _e: self._repaint(preview=False))
        self.cv.bind("<Button-1>", self._click)
        self.cv.bind("<Motion>", self._motion)
        self.cv.bind("<Leave>", lambda _e: self._set_hover(None))
        # 창 높이를 목록에 맞춘다 - 넘치면 창을 키우지 않고 목록을 굴린다
        try:
            self.win.update_idletasks()
            w = self.cv.winfo_width()
        except tk.TclError:
            return
        if w <= 1:
            w = U.wide(self.W) - 2 * PAD - U.h(14)
        full = self._draw_list(w)
        self.cv.configure(height=max(U.h(80), min(full, U.h(self.MAX_LIST))))
        U.fit_window(self.win, U.wide(self.W), keep_pos=True)
        self._paint_preview()
        self._show_equipped()

    def _show_equipped(self):
        """달고 있는 칭호가 목록 아래쪽에 있으면 거기까지 굴려 둔다."""
        key = self.title_var.get()
        hit = [h for h in self._hits if h[2] is self.title_var and h[3] == key]
        if not hit or self.cv is None:
            return
        y1, y2 = hit[0][0], hit[0][1]
        try:
            self.win.update_idletasks()
            view = self.cv.winfo_height()
            if self._full > view and y2 > view:
                self.cv.yview_moveto(max(0.0, (y1 - view // 3) / float(self._full)))
        except tk.TclError:
            pass

    def _repaint(self, preview=True):
        if self.cv is not None:
            try:
                top = self.cv.yview()[0]
                self._draw_list()
                self.cv.yview_moveto(top)
            except tk.TclError:
                pass
        if preview:
            self._paint_preview()

    def _draw_list(self, w=None):
        """칭호 · 명패 상자. 그린 높이."""
        cv, s = self.cv, U.h
        try:
            w = w or cv.winfo_width()
        except tk.TclError:
            return 0
        if w <= 1:
            return 0
        cv.delete("all")
        self._hits = []
        self._hover = None
        y = heading(cv, 0, w, 0, "칭호", "랭킹·친구 목록·투기장에서 이름 옆에 붙습니다.")
        rows = [(S.NONE, "달지 않기", None)] + [(t["id"], t["name"], None) for t in self._titles]
        y = self._box(cv, w, y, self.title_var, rows,
                      "" if self._titles else "아직 받은 칭호가 없습니다. 시즌 보상이나 도감 업적으로 받습니다.")
        y = heading(cv, 0, w, y + s(12), "명패", "이름이 명패 색으로 바뀝니다.")
        rows = [(S.NONE, "달지 않기", "")] + [(f["id"], f["name"], f.get("color") or INK) for f in self._frames]
        y = self._box(cv, w, y, self.frame_var, rows, "" if self._frames else "아직 받은 명패가 없습니다.")
        self._full = y + s(4)
        cv.configure(scrollregion=(0, 0, w, self._full))
        return self._full

    def _box(self, cv, w, y, var, rows, empty):
        """흰 고르기 상자 (DP 의 고르기 창처럼 고른 줄 왼쪽에 빨간 화살표). 상자 밑의 y."""
        s = U.h
        rh = s(self.ROW_PX)
        tw = w - s(48)
        extra = (K.text_height(cv, empty, font(9), tw) + s(8)) if empty else 0
        y2 = y + s(6) + len(rows) * rh + extra + s(6)
        K.panel(cv, 0, y, w, y2, strong=True)
        cur = var.get()
        yy = y + s(6)
        for key, label, color in rows:
            on = key == cur
            bg = cv.create_rectangle(s(5), yy + 1, w - s(5), yy + rh - 1, fill=SEL if on else WHITE, outline="")
            mid = yy + rh // 2
            if on:
                K.cursor(cv, s(12), mid, size=s(6))
            tx = s(30)
            if color is not None:        # 명패: 그 빛깔의 작은 칸 ('달지 않기' 는 빈 흰 칸)
                K.rrect(cv, tx, mid - s(8), tx + s(24), mid + s(8), s(4), fill=color or WHITE,
                        outline=LINE_D if color else LINE, width=1)
                tx += s(34)
            K.text(cv, tx, mid, one_line(cv, label, font(11), w - tx - s(14)), font(11),
                   fill="#a02020" if on else INK, anchor="w")
            self._hits.append((yy, yy + rh, var, key, bg, on))
            yy += rh
        if empty:
            K.text(cv, s(30), yy + s(2), empty, font(9), fill=DIM, anchor="nw", width=tw)
        return y2

    def _hit_at(self, e):
        try:
            y = self.cv.canvasy(e.y)
        except tk.TclError:
            return None
        for i, h in enumerate(self._hits):
            if h[0] <= y < h[1]:
                return i
        return None

    def _click(self, e):
        i = self._hit_at(e)
        if i is not None:
            _y1, _y2, var, key, _bg, _on = self._hits[i]
            var.set(key)                 # (변수가 바뀌면 다시 그린다)

    def _motion(self, e):
        self._set_hover(self._hit_at(e))

    def _set_hover(self, i):
        """올린 줄은 옅은 빛 (빛깔만 바꾼다 - 지우고 다시 그리지 않는다)."""
        if i == self._hover:
            return
        for k, on in ((self._hover, False), (i, True)):
            if k is None or k >= len(self._hits):
                continue
            _y1, _y2, _v, _key, bg, picked = self._hits[k]
            if not picked:
                try:
                    self.cv.itemconfigure(bg, fill=HOV if on else WHITE)
                except tk.TclError:
                    pass
        self._hover = i
        try:
            self.cv.configure(cursor="hand2" if i is not None else "")
        except tk.TclError:
            pass

    # ---------------- 미리 보기 · 아래 줄 ----------------
    def _chosen(self, rows, var):
        key = var.get()
        for r in rows:
            if r.get("id") == key:
                return r
        return None

    def _paint_preview(self):
        cv, s = self.pcv, U.h
        try:
            w, h = cv.winfo_width(), cv.winfo_height()
            cv.delete("all")
        except tk.TclError:
            return
        if w <= 1:
            return
        K.panel(cv, 0, 0, w, h, strong=True)
        mid = h // 2
        tw_, th_ = K.tag(cv, s(10), mid - s(10), "미리 보기", spec=font(9))
        fr = self._chosen(self._frames, self.frame_var)
        t = self._chosen(self._titles, self.title_var)
        name = getattr(self.app, "username", None) or "트레이너"
        # 이름은 어두운 판 위에 명패 빛깔로 (앱 안의 랭킹 · 친구 목록과 같은 모습)
        spec = font(12)
        x = s(10) + tw_ + s(10)
        nm = one_line(cv, name, spec, max(s(60), (w - x) // 2 - s(24)))
        pw = K.tkfont_of(cv, spec).measure(nm) + s(20)
        py1, py2 = s(7), h - s(7)
        K.rrect(cv, x, py1, x + pw, py2, s(6), fill="#2c3038")
        cv.create_text(x + pw // 2, mid, text=nm, fill=(fr or {}).get("color") or "#ffffff", font=spec,
                       anchor="center")
        tx = x + pw + s(12)
        if t:
            cv.create_text(tx, mid, text=one_line(cv, "칭호  %s" % t["name"], font(10), w - tx - s(12)),
                           fill="#c06810", font=font(10), anchor="w")
        else:
            cv.create_text(tx, mid, text="칭호 없음", fill=DIM, font=font(10), anchor="w")

    def _msg_text(self):
        return clamp_lines(self.bcv, self._msg[0], font(10), max(U.h(60), self._msg_w), 2)

    def _paint_foot(self):
        cv, s = self.bcv, U.h
        try:
            w, h = cv.winfo_width(), cv.winfo_height()
            cv.delete("foot")
        except tk.TclError:
            return
        if w <= 1:
            return
        bh = s(34)
        by = (h - bh) // 2
        w1, w2 = self.save_btn.want_width(s(36)), self.close_btn.want_width(s(36))
        self.save_btn.layout(w - w1, by, w, by + bh)
        self.close_btn.layout(w - w1 - s(8) - w2, by, w - w1 - s(8), by + bh)
        mx2 = w - w1 - w2 - s(20)
        K.panel(cv, 0, 1, mx2, h - 1, strong=True, tags=("foot",))
        self._msg_w = mx2 - s(24)
        text, color = self._msg
        self._msg_id = K.text(cv, s(12), h // 2, self._msg_text(), font(10), fill=tone(color) if color else INK,
                              anchor="w", tags=("foot",))
