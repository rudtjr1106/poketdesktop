# -*- coding: utf-8 -*-
"""에메랄드 테마 - 포켓몬 (PC 박스). GBA 3세대 '포켓몬 옮기기' 화면을 시안 A 의 언어로 그린다.

    청록 빗금 바탕 ┌ 요약 창 (GBA 창) ──────┐ [◀  박스 1   8/30 ▾  ▶] [이름 바꾸기] [새로고침]   ← 빨간 머리 띠
                   │ ┌ 무대 (큰 도트) ────┐ │ ┌ 거르기 창 ───────────────────────────────────────┐
                   │ │ No.0006 (남색 꼬리표) │ │ [타입: 전체 ▾]  찾기 [        ]  [도감][이름][Lv][종족값] │
                   │ └────────────────────┘ │ └──────────────────────────────────────────────────┘
                   │ [리자몽 ♂      Lv.60]  │ ┌ 데리고 다니는 ┐ ┌ 벽지 위 6 × 5 칸 (GBA 창) ─────┐
                   │ [불꽃][비행]           │ │ (빨간 띠)     │ │ 점무늬 벽지, 포켓몬이 든 칸만   │
                   │ [정보][능력][기술][메가]│ │ [파티 1 ▾]    │ │ 종이 판 - 도트가 먼저 보인다     │
                   │ 쪽 내용                 │ │ ▶ 리자몽 Lv.60│ │ 고른 칸 = 연노랑 + 빨간 ▶ · 테 │
                   └────────────────────────┘ └──────────────┘ └────────────────────────────────┘
                                              [데리고 다니기][별명 짓기][박스 옮기기][색 고르기][놓아주기]
                                              ┌ 글상자 (GBA 창) ─────────────────────────────────┐

    머리 띠      가방의 '◀ 지닌 도구 ▶' 띠 그대로 - 빨강 · 흰 글씨, 양 끝 흰 ◀ ▶ 가 박스 넘기기
                 (못 넘기면 흐린 ◀ ▶). 가운데를 누르면 박스 고르기 드롭다운
    파티 판      GBA 창 위에 빨간 띠 '데리고 다니는' (원작의 PARTY POKéMON 단추), 고른 자리는 연노랑 + 빨간 ▶
    벽지         연한 민트에 점무늬 (원작 박스 벽지처럼) - 글은 칸 · 판 위에만 둔다
    요약 쪽 탭   시안의 줄 세우기 칸 (흰 바탕 · 남색 테, 고른 것 = 남색 바탕 흰 글씨)

동작 · 정보량은 DP 박스(skins/dp/box.py) 그대로다 - 칠하는 메서드만 바꾼다. 아이콘은 포켓몬 도트 · 도구 그림뿐.
"""
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from common import legends as L
from common import movetext as MT

from ... import box_filter, item_icons
from ... import ui_common as U
from ..dp import DIM, INK, INK2, font, tone
from ..dp import box as DPB
from ..dp import kit as K
from ..dp.scene import T
from . import GREEN_OK, GRP, LIGHT, NAVY, PAPER, RED, RED_D, SELY
from . import gba

D = DPB.D
SORTS = DPB.SORTS

WALL = "#d6efe3"            # 벽지 바탕 (옅은 민트)
WALL_DOT = "#b4dcc9"        # 벽지 점
WALL_LINE = "#a8d4c0"       # 빈 칸 테 (벽지보다 조금 진하게 - 자리만 보인다)
CELL_LINE = "#9cc4e4"       # 포켓몬이 든 칸의 테 (창 안쪽 줄 빛)
HOVY = "#fbf6dc"            # 올린 칸 · 줄 (고른 줄보다 옅게)
CHK = "#e4f4d8"             # 여러 마리 고르기로 고른 칸
STAGE = "#e2f2ec"           # 요약 무대 바탕
STAGE_FLOOR = "#bfe0d0"     # 무대의 받침
BAR_BG = "#dce8f0"          # 막대 홈
BAR_EXP = "#4898e0"         # 경험치 막대 (GBA 의 파란 EXP)
SEP = "#e4e4da"             # 줄 사이 옅은 선
ARROW_OFF = "#f09a8c"       # 못 누르는 ◀ ▶ (빨간 띠 위)


def _wallpaper(w, h, step):
    """점무늬 벽지 그림 (크기마다 한 번 만든다)."""
    tile = Image.new("RGB", (step, step), WALL)
    dr = ImageDraw.Draw(tile)
    k = max(2, step // 7)
    for cx, cy in ((step // 4, step // 4), (step * 3 // 4, step * 3 // 4)):
        dr.rectangle((cx - k // 2, cy - k // 2, cx - k // 2 + k - 1, cy - k // 2 + k - 1), fill=WALL_DOT)
    img = Image.new("RGB", (max(1, w), max(1, h)), WALL)
    for y in range(0, h, step):
        for x in range(0, w, step):
            img.paste(tile, (x, y))
    return img


class BoxWindow(DPB.BoxWindow):

    DW_PX = 330            # 요약 창 폭 (DP 와 같다)
    PARTY_PX = 166         # 파티 판 폭 (빨간 띠 · 빨간 ▶ 자리만큼 DP 보다 조금 넓게)

    def _build(self):
        DPB.BoxWindow._build(self)
        self._wall = None                      # (w, h, PhotoImage)
        self.win.configure(bg=gba.BG1)
        self.cv.configure(bg=gba.BG1)
        self.dframe.configure(bg=PAPER, highlightthickness=0)
        self.dcv.configure(bg=PAPER)
        self.dcv.pack_configure(padx=(U.h(8), U.h(2)), pady=U.h(8))
        self.gframe.configure(bg=WALL)
        self.gcv.configure(bg=WALL)
        for sb, bg in ((self.dsb, PAPER), (self.gsb, WALL)):
            try:
                sb.configure(bg=bg)
            except tk.TclError:
                pass

    # ---------------- 판 전체 ----------------
    def _paint(self):
        self._job = None
        cv = self.cv
        try:
            W, H = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if W < 200 or H < 200:
            return
        cv.delete("scene")
        self._msg_ids = None
        s = U.h
        m = s(10)
        gba.stripes(cv, 0, 0, W, H, tags=T)
        DW = s(self.DW_PX)
        gba.frame(cv, m, m, m + DW, H - m, tags=T)
        ins = gba.inset()
        self._place("detail", self.dframe, m + ins, m + ins, DW - 2 * ins, H - 2 * m - 2 * ins)
        self._paint_right(cv, m + DW + s(10), W - m, H)

    def _box_header(self, cv, x1, y1, x2, y2):
        """빨간 머리 띠 '◀ 박스 이름 N/30 ▾ ▶' - ◀ ▶ 는 박스 넘기기, 가운데는 박스 고르기."""
        s = U.h
        gba.frame(cv, x1, y1, x2, y2, fill=RED, tags=T)
        prev, nxt, _ren = self._page_state
        cy = (y1 + y2) // 2
        aw = s(40)
        k = s(8)
        for d, on in ((-1, prev), (1, nxt)):
            tg = T + ("bpg", "bpg%s" % ("m" if d < 0 else "p"))
            ax = x1 + s(6) if d < 0 else x2 - s(6) - aw
            cv.create_rectangle(ax, y1, ax + aw, y2, fill="", outline="", tags=tg)        # 누를 자리
            mx = ax + aw // 2
            if d < 0:
                pts = (mx + k // 2 + 2, cy - k, mx - k, cy, mx + k // 2 + 2, cy + k)
            else:
                pts = (mx - k // 2 - 2, cy - k, mx + k, cy, mx - k // 2 - 2, cy + k)
            cv.create_polygon(pts, fill="#ffffff" if on else ARROW_OFF, outline="", tags=tg)
            cv.tag_bind("bpg%s" % ("m" if d < 0 else "p"), "<Button-1>",
                        lambda _e, dd=d, ok=on: self._page(dd) if ok else None)
        mx1, mx2 = x1 + s(6) + aw, x2 - s(6) - aw
        tg = T + ("page",)
        cv.create_rectangle(mx1, y1, mx2, y2, fill="", outline="", tags=tg)
        spec = font(13)
        text = DPB._clamp(cv, self._page_text, spec, mx2 - mx1 - s(8), 1)
        d = max(1, s(2))
        cv.create_text((mx1 + mx2) // 2 + d, cy + d, text=text, fill=RED_D, font=spec, anchor="center", tags=tg)
        cv.create_text((mx1 + mx2) // 2, cy, text=text, fill="#ffffff", font=spec, anchor="center", tags=tg)
        self._boxes["page"] = (mx1, y1, mx2, y2)
        cv.tag_bind("page", "<Button-1>", lambda _e: self.open_box_menu())
        self._hand("page", "bpg")

    def _paint_right(self, cv, x0, x2, H):
        s = U.h
        m = s(10)
        y = m
        ins = gba.inset()
        # 1) 빨간 머리 띠 (박스 넘기기 · 고르기) · 이름 바꾸기 · 새로고침
        bh = s(36)
        rw = self.btn_rename.want_width(s(20))
        bw = self.btn_reload.want_width(s(20))
        hx2 = x2 - bw - rw - s(14)
        self._box_header(cv, x0, y, hx2, y + bh)
        self.btn_prev.hide()
        self.btn_next.hide()
        self.btn_rename.layout(hx2 + s(8), y + s(2), hx2 + s(8) + rw, y + bh)
        self.btn_reload.layout(x2 - bw, y + s(2), x2, y + bh)
        # 2) 거르기 창: 타입 · 찾기 · 줄 세우기 (남색 2px 테의 종이 창 - 글이 빗금 위에 놓이지 않게)
        y += bh + s(6)
        th = s(28)
        lw = max(2, s(2))
        fh = th + 2 * lw + s(8)
        gba.frame(cv, x0, y, x2, y + fh, bw=lw, inner=False, tags=T)
        ry = y + lw + s(4)
        rx1, rx2 = x0 + lw + s(6), x2 - lw - s(6)
        f10 = K.tkfont_of(cv, font(10))
        tw = f10.measure(self.btn_type.text + " ▾") + s(24)
        gba.sort_box(cv, rx1, ry, rx1 + tw, ry + th, self.btn_type.text + " ▾", font(10), False, tags=T + ("tsel",))
        self._boxes["type"] = (rx1, ry, rx1 + tw, ry + th)
        cv.tag_bind("tsel", "<Button-1>", lambda _e: self._open_type_menu())
        self._hand("tsel")
        gap = s(4)
        sws = [f10.measure(lb) + s(18) for _k, lb in SORTS]
        sx = rx2 - sum(sws) - gap * (len(SORTS) - 1)
        left = sx
        for (key, lb), w in zip(SORTS, sws):
            tg = T + ("bsort", "bsort" + key)
            gba.sort_box(cv, sx, ry, sx + w, ry + th, lb, font(10), self.sort == key, tags=tg)
            cv.tag_bind("bsort" + key, "<Button-1>", lambda _e, k=key: self.set_sort(k))
            sx += w + gap
        self._hand("bsort")
        fx = rx1 + tw + s(12)
        cv.create_text(fx, ry + th // 2, text="찾기", fill=INK, font=font(10), anchor="w", tags=T)
        fx += f10.measure("찾기") + s(8)
        self._place("find", self.find_box, fx, ry, max(s(90), left - fx - s(12)), th)
        # 3) 데리고 다니는 포켓몬 + 벽지 위 박스 칸
        y += fh + s(6)
        BOT = s(92)
        gy2 = H - BOT
        PW = s(self.PARTY_PX)
        self._paint_party_slots(cv, x0, y, x0 + PW, gy2)
        gx1 = x0 + PW + s(8)
        gba.frame(cv, gx1, y, x2, gy2, fill=WALL, tags=T)
        self._place("grid", self.gframe, gx1 + ins, y + ins, x2 - gx1 - 2 * ins, gy2 - y - 2 * ins)
        # 4) 단추 줄 + 글상자
        by = gy2 + s(6)
        bh2 = s(36)
        if self.multi:
            btns = [self.btn_multi_move, self.btn_multi_all, self.btn_multi_clear, self.btn_multi_done]
            hide = [self.btn_party, self.btn_nick, self.btn_move, self.btn_tint, self.btn_release]
        else:
            btns = [self.btn_party, self.btn_nick, self.btn_move, self.btn_tint, self.btn_release]
            hide = [self.btn_multi_move, self.btn_multi_all, self.btn_multi_clear, self.btn_multi_done]
        for b in hide:
            b.hide()
        x = x0
        for b in btns:
            w = b.want_width(s(28))
            b.layout(x, by, x + w, by + bh2)
            x += w + s(6)
        text, color = self.msg
        shown = text or self._count_text
        tid = K.msgbox(cv, x0, by + bh2 + s(4), x2, H - m, shown,
                       (tone(color) if color else (INK if text else INK2)), tags=T)
        self._msg_ids = (None, tid)

    def _paint_party_slots(self, cv, x1, y1, x2, y2):
        """데리고 다니는 여섯 자리: GBA 창 + 빨간 띠 (원작의 PARTY POKéMON) + 파티 고르기 + 여섯 판."""
        s = U.h
        gba.frame(cv, x1, y1, x2, y2, tags=T)
        ins = gba.inset()
        ix1, ix2 = x1 + ins, x2 - ins
        hy1, hy2 = y1 + ins, y1 + ins + s(26)
        cv.create_rectangle(ix1, hy1, ix2, hy2, fill=RED, outline="", tags=T)
        cv.create_line(ix1, hy2, ix2, hy2, fill=NAVY, width=max(2, s(2)), tags=T)
        d = max(1, s(1))
        cx, cy = (ix1 + ix2) // 2, (hy1 + hy2) // 2
        cv.create_text(cx + d, cy + d, text="데리고 다니는", fill=RED_D, font=font(10), anchor="center", tags=T)
        cv.create_text(cx, cy, text="데리고 다니는", fill="#ffffff", font=font(10), anchor="center", tags=T)
        top = hy2 + s(4)
        rows = self.party_presets()
        if rows:
            name = next((p.get("name") or "파티 %d" % p.get("no") for p in rows if p.get("no") == self.party_active()),
                        "파티")
            px1, px2 = ix1 + s(4), ix2 - s(4)
            ph = s(26)
            gba.sort_box(cv, px1, top, px2, top + ph,
                         DPB._clamp(cv, name, font(10), px2 - px1 - s(30), 1) + " ▾", font(10), False,
                         tags=T + ("preset",))
            self._boxes["preset"] = (px1, top, px2, top + ph)
            cv.tag_bind("preset", "<Button-1>", lambda _e: self._open_preset_menu())
            self._hand("preset")
            top += ph + s(4)
        self.btn_party_name.hide()
        n = 6
        gap = s(4)
        sh = (y2 - ins - s(4) - top - gap * (n - 1)) / float(n)
        self._pslots = {}
        for i in range(n):
            sy1 = top + i * (sh + gap)
            sy2 = sy1 + sh
            sx1, sx2 = ix1 + s(4), ix2 - s(4)
            m = self._party_list[i] if i < len(self._party_list) else None
            mid = (sy1 + sy2) / 2
            if m is None:
                cv.create_rectangle(sx1, sy1, sx2, sy2, fill="#f0f0e8", outline=SEP, tags=T)
                cv.create_text((sx1 + sx2) / 2, mid, text="빈 자리", fill=DIM, font=font(9), tags=T)
                continue
            pid = m["id"]
            sel, tgt, chk = pid == self.sel, pid == self._target, pid in self.checked
            tg = T + ("pslot",)
            fill = SELY if sel else (CHK if chk else (HOVY if pid == self._hover or tgt else PAPER))
            if tgt:
                line, lw = NAVY, max(2, s(2))
            elif sel:
                line, lw = RED, max(2, s(2))
            else:
                line, lw = CELL_LINE, 1
            cv.create_rectangle(sx1, sy1, sx2, sy2, fill=fill, outline=line, width=lw, tags=tg)
            if sel:
                gba.cursor(cv, sx1 + s(4), mid, s(5), tags=tg)
            ph = self._fit_thumb(m, sh)
            if ph is not None:
                cv.create_image(sx1 + s(38), mid, image=ph, tags=tg)
            info = m.get("info") or {}
            name = "알" if m.get("isEgg") else info.get("name", m.get("species", "?"))
            if m.get("shiny"):
                name = "★" + name
            nx = sx1 + s(66)
            cv.create_text(nx, mid - s(8), text=DPB._clamp(cv, name, font(10), sx2 - nx - s(4), 1),
                           fill=INK, font=font(10), anchor="w", tags=tg)
            cv.create_text(nx, mid + s(9), anchor="w", font=font(9), fill=INK2, tags=tg,
                           text=("%d%%" % box_filter.egg_progress(m.get("egg") or {})[0]) if m.get("isEgg")
                           else "Lv.%d" % m.get("level", 0))
            if chk:
                cv.create_text(sx2 - s(4), sy2 - s(2), text="✓", fill=GREEN_OK, font=font(11), anchor="se", tags=tg)
            self._pslots[pid] = (sx1, sy1, sx2, sy2)
        self._hand("pslot")

    def _fit_thumb(self, m, room):
        """파티 판의 도트 - 판이 도트보다 낮으면 (작은 창) 3/4 · 2/3 · 1/2 로 줄인 것 (도트라 정수 배로 줄인다)."""
        ph = self._thumb(m)
        if ph is None or m.get("isEgg"):
            return ph
        try:
            h = ph.height()
        except tk.TclError:
            return ph
        if h <= room:
            return ph
        cache = self.__dict__.setdefault("_small", {})
        for z, sub in ((3, 4), (2, 3), (1, 2)):
            if h * z // sub <= room or sub == 2:
                key = (self._thumb_key(m), z, sub)
                got = cache.get(key)
                if got is None:
                    try:
                        img = ImageTk.getimage(ph)
                        got = ImageTk.PhotoImage(img.resize((max(1, img.width * z // sub),
                                                             max(1, img.height * z // sub)), Image.NEAREST))
                    except Exception:                       # noqa: BLE001
                        return ph
                    cache[key] = got
                return got
        return ph

    # ---------------- 박스 칸 (벽지 위 6 × 5) ----------------
    def _wall_photo(self, w, h):
        if self._wall and self._wall[0] == w and self._wall[1] == h:
            return self._wall[2]
        try:
            ph = ImageTk.PhotoImage(_wallpaper(w, h, max(10, U.h(16))))
        except Exception:                                   # noqa: BLE001
            return None
        self._wall = (w, h, ph)
        return ph

    def _paint_grid(self):
        cv = self.gcv
        try:
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w <= 1:
            return
        cv.delete("all")
        s = U.h
        cols = 6
        n = len(self._page_mons)
        rows = max(5, -(-n // cols))
        pad = s(6)
        cw = (w - pad) / float(cols)
        # 다섯 줄이 한 화면에 (칸이 도트 높이보다 낮아질 때만 굴러간다)
        ch = max(U.h(self.THUMB) + pad + s(2), (h - pad) / 5.0)
        total = max(h, int(ch * rows + pad))
        cv.configure(scrollregion=(0, 0, w, total))
        wall = self._wall_photo(int(w), int(total))
        if wall is not None:
            cv.create_image(0, 0, image=wall, anchor="nw")
        self._cells = {}
        for i in range(rows * cols):
            r, c = divmod(i, cols)
            x1, y1 = pad + c * cw, pad + r * ch
            x2, y2 = x1 + cw - pad, y1 + ch - pad
            if i >= n:
                cv.create_rectangle(x1, y1, x2, y2, fill="", outline=WALL_LINE)      # 빈 자리 - 벽지가 보인다
                continue
            m = self._page_mons[i]
            pid = m["id"]
            sel, tgt, chk, hov = pid == self.sel, pid == self._target, pid in self.checked, pid == self._hover
            fill = SELY if sel else (CHK if chk else (HOVY if (hov or tgt) else PAPER))
            if tgt:
                line, lw = NAVY, max(2, s(2))
            elif sel:
                line, lw = RED, max(2, s(2))
            else:
                line, lw = CELL_LINE, 1
            cv.create_rectangle(x1, y1, x2, y2, fill=fill, outline=line, width=lw)
            ph = self._thumb(m)
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            if ph is not None:
                cv.create_image(mx, my, image=ph)
            else:
                cv.create_oval(mx - 6, my - 6, mx + 6, my + 6, fill=PAPER, outline=LIGHT)
            if sel:
                gba.cursor(cv, x1 + s(4), my, s(5))
            if m.get("shiny"):
                cv.create_text(x1 + 5, y1 + 3, text="★", fill="#d0a000", font=font(9), anchor="nw")
            kind = None if m.get("isEgg") else L.kind_of(m.get("num"))
            if kind:
                cv.create_text(x2 - 4, y1 + 3, text="◆" if kind == "legendary" else "✦", fill="#a050c0",
                               font=font(8), anchor="ne")
            if m.get("away"):
                cv.create_text(mx, y2 - 3, text="탐험 중", fill="#2860c0", font=font(8), anchor="s")
            if chk:
                cv.create_text(x2 - 4, y2 - 2, text="✓", fill=GREEN_OK, font=font(12), anchor="se")
            self._cells[pid] = (x1, y1, x2, y2)
        # 마우스가 올라간 포켓몬의 이름 (종이 쪽지 · 남색 테)
        m = self._by_id.get(self._hover) if self._hover else None
        box = self._cells.get(self._hover) if m is not None else None
        if box:
            info = m.get("info") or {}
            name = "알" if m.get("isEgg") else info.get("name", m.get("species", "?"))
            tip = "%s  Lv.%s" % (name, "-" if m.get("isEgg") else m.get("level", "?"))
            f = K.tkfont_of(cv, font(9))
            tw = f.measure(tip) + s(18)
            tx = min(max(tw / 2 + 2, (box[0] + box[2]) / 2), w - tw / 2 - 2)
            ty = max(s(24), box[1] - 2)
            b = max(2, s(2))
            cv.create_rectangle(tx - tw / 2, ty - s(22), tx + tw / 2, ty, fill=NAVY, outline="")
            cv.create_rectangle(tx - tw / 2 + b, ty - s(22) + b, tx + tw / 2 - b, ty - b, fill=PAPER, outline="")
            cv.create_text(tx, ty - s(11), text=tip, fill=INK, font=font(9))

    # ---------------- 요약 창 ----------------
    def _paint_detail(self, top=False):
        """요약: 무대(큰 도트) · 이름 판 · 타입은 늘 위에, 그 아래 쪽 탭(줄 세우기 칸 모양)과 쪽 하나."""
        self._job_d = None
        cv = self.dcv
        try:
            w, vh = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w <= 1:
            return
        cv.delete("all")
        for b in (self.btn_hold, self.btn_unhold, self.btn_remember, self.btn_bond):
            b.hide()
        s = U.h
        d = self._d
        x1, x2 = 0, w - s(2)
        if not d:
            cv.create_text(w // 2, s(80), text="포켓몬을 고르세요", fill=INK2, font=font(12), anchor="n", tags=D)
            return
        y = 0
        lw = max(2, s(2))
        # 무대 - 남색 2px 테 안의 옅은 민트, 받침 위에 큰 도트
        sh = s(122)
        gba.frame(cv, x1, y, x2, y + sh, fill=STAGE, bw=lw, inner=False, tags=D)
        cv.create_oval(w // 2 - s(66), y + sh - s(32), w // 2 + s(66), y + sh - s(10), fill=STAGE_FLOOR,
                       outline="", tags=D)
        f9 = K.tkfont_of(cv, font(9))
        nw = f9.measure(d["num"]) + s(14)
        cv.create_rectangle(x1 + lw, y + lw, x1 + lw + nw, y + lw + s(20), fill=NAVY, outline="", tags=D)
        cv.create_text(x1 + lw + nw // 2, y + lw + s(10), text=d["num"], fill="#ffffff", font=font(9),
                       anchor="center", tags=D)
        a = cv.create_image(w // 2, y + sh // 2 + s(4), image=self.d_art.image or "", tags=D)
        b = cv.create_text(w // 2, y + sh // 2, text="" if self.d_art.image else self.d_art.text,
                           fill=tone(self.d_art.fg), font=font(11), tags=D)
        self.d_art.ids = (a, b)
        y += sh + s(6)
        # 이름 판 - 이름 · 성별 · Lv
        nh = s(36)
        gba.frame(cv, x1, y, x2, y + nh, fill=PAPER, bw=lw, inner=False, tags=D)
        my = y + nh // 2
        t = cv.create_text(x1 + s(10), my, text=d["name"], fill="#b07800" if d["m"].get("shiny") else INK,
                           font=font(14), anchor="w", tags=D)
        bb = cv.bbox(t)
        if d.get("gender") and bb:
            cv.create_text(bb[2] + s(6), my, text=d["gender"], fill=d.get("gender_fg", INK2), font=font(12),
                           anchor="w", tags=D)
        cv.create_text(x2 - s(10), my, text=d["lv"], fill=INK, font=font(12), anchor="e", tags=D)
        y += nh + s(6)
        if d.get("sub"):
            _a, t2 = K.text(cv, x1 + s(4), y, d["sub"], font(9), fill=INK2, tags=D, width=x2 - x1 - s(8))
            y = cv.bbox(t2)[3] + s(6)
        cx = x1 + s(4)
        for label, col in d.get("chips") or []:
            cw = f9.measure(label) + s(16)
            cv.create_rectangle(cx, y, cx + cw, y + s(22), fill=col, outline=NAVY, width=1, tags=D)
            cv.create_text(cx + cw // 2, y + s(11), text=label, fill=K.look_of(col)[3], font=font(9),
                           anchor="center", tags=D)
            cx += cw + s(5)
        if d.get("chips"):
            y += s(30)
        if d.get("egg"):
            y = self._d_egg(cv, d, x1, x2, y)
        else:
            pages = [("info", "정보"), ("stats", "능력"), ("moves", "기술")]
            if self.bond.visible:
                pages.append(("mega", "메가진화"))
            if self._dpage not in dict(pages):
                self._dpage = "info"
            gap = s(4)
            f11 = K.tkfont_of(cv, font(11))
            th = s(30)
            w0 = (x2 - x1 - gap * (len(pages) - 1)) / float(len(pages))
            tx = float(x1)
            for key, lb in pages:
                ww = max(w0, f11.measure(lb) + s(12))
                tg = D + ("dpg", "dpg" + key)
                gba.sort_box(cv, int(tx), y, int(tx + ww), y + th, lb, font(11), key == self._dpage, tags=tg)
                cv.tag_bind("dpg" + key, "<Button-1>", lambda _e, k=key: self._pick_dpage(k))
                tx += ww + gap
            cv.tag_bind("dpg", "<Enter>", lambda _e: cv.configure(cursor="hand2"))
            cv.tag_bind("dpg", "<Leave>", lambda _e: cv.configure(cursor=""))
            y += th + s(12)
            y = {"info": self._d_info, "stats": self._d_stats, "moves": self._d_moves,
                 "mega": self._d_bond}[self._dpage](cv, d, x1 + s(4), x2 - s(4), y)
        total = y + s(12)
        cv.configure(scrollregion=(0, 0, w, max(total, vh)))
        if top:
            cv.yview_moveto(0)
        for b in (self.btn_hold, self.btn_unhold, self.btn_remember, self.btn_bond):
            if b.box:
                b.draw()

    def _label(self, cv, x, y, text):
        """쪽 안의 머리 (시안의 단락 머리 - 회청색)."""
        cv.create_text(x, y, text=text, fill=GRP, font=font(9), anchor="nw", tags=D)

    def _bar(self, cv, x1, y, x2, h, ratio, col):
        """GBA 막대: 남색 1px 테 안의 옅은 홈 + 채움."""
        cv.create_rectangle(x1, y, x2, y + h, fill=BAR_BG, outline=NAVY, width=1, tags=D)
        fw = int((x2 - x1 - 2) * max(0.0, min(1.0, ratio)))
        if fw > 0:
            cv.create_rectangle(x1 + 1, y + 1, x1 + 1 + fw, y + h - 1, fill=col, outline="", tags=D)

    def _d_info(self, cv, d, x1, x2, y):
        s = U.h
        iw = x2 - x1
        for title, name, note in (("특성", d["ability"], d["ability_note"]), ("성격", d["nature"], d["nature_note"])):
            self._label(cv, x1, y, title)
            y = self._wrap(cv, x1 + s(40), y, name, font(10), width=iw - s(40))
            y = self._wrap(cv, x1 + s(40), y + 2, note, font(9), fill=INK2, width=iw - s(40)) + s(10)
        cv.create_line(x1, y - s(4), x2, y - s(4), fill=SEP, tags=D)
        y += s(4)
        # 지닌 도구
        self._label(cv, x1, y, "도구")
        bw1, bw2 = self.btn_hold.want_width(s(18)), self.btn_unhold.want_width(s(18))
        self.btn_unhold.layout(x2 - bw2, y - s(6), x2, y + s(22))
        self.btn_hold.layout(x2 - bw2 - s(6) - bw1, y - s(6), x2 - bw2 - s(6), y + s(22))
        y += s(28)
        tx = x1 + s(40)
        if d["held"]:
            ph = item_icons.photo(d["held"], 24)
            if ph is not None:
                cv.create_image(x1 + s(14), y + s(10), image=ph, tags=D)
        y = self._wrap(cv, tx, y, d["held_text"], font(9), fill=INK if d["held"] else INK2, width=iw - s(40)) + s(10)
        cv.create_line(x1, y - s(4), x2, y - s(4), fill=SEP, tags=D)
        y += s(4)
        # 경험치 (GBA 의 파란 EXP 막대)
        ratio, text = d["exp"]
        self._label(cv, x1, y, "경험치")
        cv.create_text(x2, y, text=text, fill=INK2, font=font(8), anchor="ne", tags=D)
        y += s(18)
        self._bar(cv, x1, y, x2, s(10), ratio, BAR_EXP)
        y += s(18)
        if d.get("friend"):
            hearts, num, msg = d["friend"]
            self._label(cv, x1, y, "친밀도")
            cv.create_text(x1 + s(48), y - 1, text=hearts, fill="#e04888", font=font(10), anchor="nw", tags=D)
            cv.create_text(x2, y, text=num, fill=INK2, font=font(9), anchor="ne", tags=D)
            y = self._wrap(cv, x1, y + s(18), msg, font(9), fill=INK2, width=iw) + s(10)
        if d.get("evo"):
            self._label(cv, x1, y, "진화")
            y += s(18)
            for line in d["evo"]:
                y = self._wrap(cv, x1, y, line, font(9), width=iw) + s(3)
        return y

    def _d_stats(self, cv, d, x1, x2, y):
        s = U.h
        iw = x2 - x1
        y = self._wrap(cv, x1, y, d["ivsum"], font(9), fill=GREEN_OK, width=iw) + s(8)
        for i, (label, v, iv, hy, mx) in enumerate(d["rows"]):
            if i % 2 == 0:
                cv.create_rectangle(x1 - s(2), y - s(3), x2 + s(2), y + s(18), fill="#f0f0e6", outline="", tags=D)
            cv.create_text(x1, y, text=label, fill=INK2, font=font(9), anchor="nw", tags=D)
            cv.create_text(x1 + s(84), y, text=str(v), fill=INK, font=font(10), anchor="ne", tags=D)
            col = "#3cb868" if iv == 31 else ("#f0a020" if iv >= 26 else "#9aa2b0")
            self._bar(cv, x1 + s(92), y + 3, x2 - s(66), s(10), v / float(mx or 1), col)
            cv.create_text(x2, y, text="개체 %d%s" % (iv, "✦" if hy else ""),
                           fill=GREEN_OK if iv == 31 else INK2, font=font(8), anchor="ne", tags=D)
            y += s(22)
        y = self._wrap(cv, x1, y + s(4), d["evsum"], font(9), fill=INK2, width=iw)
        return y

    def _d_moves(self, cv, d, x1, x2, y):
        """기술 넷 - 배틀 기술 창처럼 줄마다 타입 빛깔 띠, 고른 줄은 연노랑 + 빨간 ▶."""
        s = U.h
        iw = x2 - x1
        dex = self.app.dex
        mh = s(46)
        lw = max(2, s(2))
        n = len(d["moves"])
        if n:
            gba.frame(cv, x1, y, x2, y + n * mh + 2 * lw, bw=lw, inner=False, tags=D)
        ry = y + lw
        for i, (mv, md) in enumerate(d["moves"]):
            col = U.TYPE_COLOR.get((md or {}).get("type"), "#a0a0a8")
            tg = D + ("mv%d" % i,)
            picked = bool(self._move_pick and self._move_pick[0] == i)
            cv.create_rectangle(x1 + lw, ry, x2 - lw, ry + mh, fill=SELY if picked else PAPER, outline="", tags=tg)
            if i:
                cv.create_line(x1 + lw + s(4), ry, x2 - lw - s(4), ry, fill=SEP, tags=tg)
            cv.create_rectangle(x1 + lw + s(4), ry + s(8), x1 + lw + s(9), ry + mh - s(8), fill=col, outline="",
                                tags=tg)
            if picked:
                gba.cursor(cv, x1 + lw + s(13), ry + s(15), s(5), tags=tg)
            nx = x1 + lw + s(28)
            cv.create_text(nx, ry + s(15), text=mv, fill=INK, font=font(11), anchor="w", tags=tg)
            sub = "%s · %s" % (dex.type_name((md or {}).get("type")) if dex else "", MT.short_line(md))
            cv.create_text(nx, ry + mh - s(12), text=sub, fill=INK2, font=font(9), anchor="w", tags=tg)
            cv.tag_bind("mv%d" % i, "<Button-1>", lambda _e, k=i, dd=md, t=mv: self.pick_move(k, dd, t))
            cv.tag_bind("mv%d" % i, "<Enter>", lambda _e: cv.configure(cursor="hand2"))
            cv.tag_bind("mv%d" % i, "<Leave>", lambda _e: cv.configure(cursor=""))
            ry += mh
        y = (ry + lw + s(8)) if n else y
        if self._move_pick:
            _i, md, name = self._move_pick
            y = self._wrap(cv, x1, y + s(2), MT.stat_line(md, name or "?"), font(9), fill="#b05a10", width=iw)
            y = self._wrap(cv, x1, y + s(2), MT.desc(md), font(9), fill=INK2, width=iw) + s(6)
        if d.get("pending"):
            y = self._wrap(cv, x1, y + s(2), d["pending"], font(9), fill=GREEN_OK, width=iw) + s(6)
        rw = self.btn_remember.want_width(s(24))
        self.btn_remember.layout(x2 - rw, y + s(4), x2, y + s(36))
        return y + s(40)

    def _d_bond(self, cv, d, x1, x2, y):
        """메가진화 · 유대 미션 - DP 와 같은 줄들, 막대만 GBA 막대 · 메가 타입은 네모 꼬리표."""
        s = U.h
        iw = x2 - x1
        b = self.bond
        mega = "#7a4ad0"
        if b.btn_spec:
            self.btn_bond.configure(text=b.btn_spec[0], state="normal")
            bw = self.btn_bond.want_width(s(24))
            self.btn_bond.layout(x2 - bw, y, x2, y + s(32))
            y += s(40)
        for row in b.lines:
            if row[0] == "kv":
                _k, label, val, col = row
                self._label(cv, x1, y, label)
                y = self._wrap(cv, x1 + s(48), y, val, font(9), fill=tone(col) if col != DPB.BD.MEGA else mega,
                               width=iw - s(48)) + s(4)
            elif row[0] == "bar":
                _k, label, num, ratio, col = row
                y2 = self._wrap(cv, x1, y, label, font(9), width=iw - s(60))
                cv.create_text(x2, y, text=num, fill=INK2, font=font(8), anchor="ne", tags=D)
                self._bar(cv, x1, y2 + 3, x2, s(10), ratio, col)
                y = y2 + s(18)
            else:
                _k, text, col = row
                y = self._wrap(cv, x1, y, text, font(9), fill=mega if col == DPB.BD.MEGA else tone(col),
                               width=iw) + s(4)
        dex = self.app.dex
        for pv in b.previews:
            cv.create_line(x1, y + s(4), x2, y + s(4), fill=SEP, tags=D)
            y += s(12)
            t = cv.create_text(x1, y, text=pv["name"], fill=mega, font=font(11), anchor="nw", tags=D)
            bb = cv.bbox(t)
            cv.create_text((bb[2] if bb else x1) + s(8), y + 2, text="메가진화하면", fill=INK2, font=font(8),
                           anchor="nw", tags=D)
            y += s(22)
            cx = x1
            f8 = K.tkfont_of(cv, font(8))
            for tp in pv["types"]:
                label = dex.type_name(tp) if dex else tp
                cw = f8.measure(label) + s(14)
                col = U.TYPE_COLOR.get(tp, "#a0a0a8")
                cv.create_rectangle(cx, y, cx + cw, y + s(18), fill=col, outline=NAVY, width=1, tags=D)
                cv.create_text(cx + cw // 2, y + s(9), text=label, fill=K.look_of(col)[3], font=font(8),
                               anchor="center", tags=D)
                cx += cw + s(4)
            y += s(24)
            if pv.get("abilityKr"):
                y = self._wrap(cv, x1, y, "특성 %s (%s)" % (pv["abilityKr"], "바뀜" if pv["abilityChanged"] else "그대로"),
                               font(9), width=iw) + s(2)
            for i, (_k, label, now, after, dlt) in enumerate(pv["rows"]):
                if i % 2 == 0:
                    cv.create_rectangle(x1 - s(2), y - s(1), x2 + s(2), y + s(15), fill="#f0f0e6", outline="",
                                        tags=D)
                cv.create_text(x1, y, text=label, fill=INK2, font=font(8), anchor="nw", tags=D)
                cv.create_text(x1 + s(110), y, text="%d → %d" % (now, after), fill=INK if dlt else DIM,
                               font=font(8), anchor="ne", tags=D)
                cv.create_text(x2, y, text=DPB.BD.delta_text(dlt),
                               fill=GREEN_OK if dlt > 0 else (RED if dlt < 0 else DIM), font=font(8),
                               anchor="ne", tags=D)
                y += s(16)
        return y


# ---------------------------------------------------------------- 지닌 도구 고르기
# ui_box.HeldPicker 가 view("box") 에서 이 이름을 찾는다 - 없으면 기본 테마 것으로 떨어진다.
from ..dp.box import HeldPicker, _clamp  # noqa: E402,F401
