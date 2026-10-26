# -*- coding: utf-8 -*-
"""에메랄드 테마 - 가방 (도구 칸). 시안 A 의 가방 그림을 옮긴다.

청록 빗금 바탕 위에 GBA 창(남색 테 · 안쪽 옅은 줄 · 종이 바탕)을 놓는다. 칸은 DP 와 같은 셋이다:

    ┌ 빨간 머리 띠 ─────────┐┌ 목록 창 ─────────────────┐┌ 설명 창 ────────────────┐
    │ ◀  지닌 도구  ▶        ││ 찾기 [                 ]  ││ [그림] 이름 [등급]       │
    ├ 소지금 창 ────────────┤│ [이름][종류][등급][개수]  ││        가진 수 3개 · 분류│
    │ 소지금      500,000원  ││ 열매 · 3종                ││ 설명 …                   │
    ├ 주머니 창 ────────────┤│ ▶ 그림 이름   등급   ×5   │├ 누구에게 창 ────────────┤
    │ ▶ 전체   (연노랑 띠)   ││   …                       ││ 누구에게 쓸까? 안내  N마리│
    │   지닌 도구        227 ││                           ││ 찾기 [     ] [기본][..]  │
    │   …                    ││                           ││ ▶ 그림 리자몽     빈손   │
    │ 460종 · 1380개 [새로고침]│                           ││   …                      │
    └───────────────────────┘│                           ││            [ ○○ 쓰기 ]   │
     [팔기] [여러 개 팔기]     └───────────────────────────┘└──────────────────────────┘

    머리 띠    시안의 '◀ 지닌 도구 ▶' - 빨강 · 흰 글씨. ◀ ▶ 는 앞 · 뒤 주머니
    고른 줄    연노랑 띠 + 빨간 ▶ (도구 · 주머니 · 포켓몬 모두)
    줄 세우기  흰 칸 · 남색 2px 테, 고른 것은 남색 바탕 흰 글씨 (칸 폭을 고르게 나눈다)
    설명 창    왼쪽에 도구 그림 칸(옅은 초록 · 남색 3px 테), 이름 · 등급 꼬리표 · 가진 수, 아래에 설명
               (작은 창에서 '누구에게' 칸이 모자라면 그림 칸을 빼고 글만 - 설명은 자르지 않는다)
    큰 단추    빨강 · 남색 4px 테 · 그늘 ('○○ 쓰기') - 누구에게 창 오른쪽 아래

시안은 머리 띠 · 소지금을 맨 위 한 줄에 두지만, 그러면 목록이 기본 가방보다 짧아져서 (목록 정보량을 줄이지
않는다 - 사용자) 왼쪽 칸 위에 쌓았다. 포켓몬 줄은 시안의 40px 보다 조금 낮은 36px.

동작은 DP 가방(skins/dp/bag.py) · 기본 가방 그대로다. 알릴 말은 설명 창 위에 잠깐 (_toast).
기술머신 칸(tms.py)도 같은 틀(GBABag)을 쓴다. 아이콘은 직접 그리지 않는다 - 도구 그림은 item_icons.
"""
import tkinter as tk

from common.korean import natural

from ... import box_filter
from ... import item_icons
from ... import ui_bag as B
from ... import ui_common as U
from ..dp import DIM, INK, INK2, font, tone
from ..dp import bag as DPB
from ..dp import kit as K
from ..dp.scene import POCKET_NAME, POCKETS, T
from . import GREEN_OK, GRP, NAVY, PAPER, SELY
from . import gba

ART_BG = "#e8f0e8"          # 도구 그림 칸 (시안 .info .art)
HOV = "#fbf6dc"             # 마우스를 올린 줄 (고른 줄보다 옅게)


class GBABag(object):
    """가방 · 기술머신 칸이 같이 쓰는 시안 A 의 틀. 부르는 창이 정하는 것은 DP PocketDial 과 같다:
    _lcd_text · _line_text · _pocket_now · _pocket_label · _pocket_count · _pocket_click · _dial_buttons · _tm_badge,
    그리고 _money_label() (오른쪽 위 창의 이름)."""

    LW_PX = 236
    TOP_PX = 46
    PLATE_PX = 36            # 포켓몬 줄 높이 (시안 .mon 40px 보다 조금 낮게 - 한 화면에 기본 가방만큼은 보이게)
    MID_SHARE = 0.42         # 가운데 목록 칸 몫 (시안처럼 오른쪽 '누구에게' 칸을 넓게)
    MID_MIN = 270            # 가운데 목록 칸의 가장 좁은 폭 (DP 는 290 - 작은 창에서 오른쪽 칸에 조금 더 준다)

    def _money_label(self):
        return "소지금"

    def _pocket_count_text(self, key):
        """주머니 줄 오른쪽 글 (든 종류 수). 전체 · 기술머신은 비운다."""
        if key in ("all", "tms"):
            return ""
        return str(self._pocket_count(key))

    def _em_reload_button(self):
        btn = getattr(self, "_em_refresh", None)
        if btn is None:
            btn = self._em_refresh = K.CButton(self.cv, "새로고침", self.reload, "gray", font(9))
        return btn

    def _step_pocket(self, d):
        keys = [k for k, _l in POCKETS]
        now = self._pocket_now()
        i = keys.index(now) if now in keys else 0
        self._pocket_click(keys[(i + d) % len(keys)])

    # ---------------- 칸 나누기
    def _em_layout(self, W, H):
        """(세 칸의 x 경계 c1 · c2, 가운데 · 오른쪽 창이 시작하는 y - s(8)). 칸 사이 · 가장자리 여백은 s(10).

        시안은 위에 머리 띠 · 소지금 줄을 따로 두지만, 그러면 목록이 기본 가방보다 짧아진다 (사용자: 목록 정보량을
        줄이지 말 것). 그래서 머리 띠 · 소지금은 왼쪽 칸 맨 위에 쌓고, 가운데 · 오른쪽 창은 맨 위부터 쓴다."""
        s = U.h
        c1 = s(self.LW_PX)
        c2 = c1 + max(s(self.MID_MIN), min(s(440), int((W - c1) * self.MID_SHARE)))
        return c1, c2, s(2)

    def _paint_back(self, cv, W, H):
        gba.stripes(cv, 0, 0, W, H, tags=T)

    def _paint_top(self, cv, W, c1, c2, top):
        """(왼쪽 칸이 머리 띠 · 소지금을 그린다 - 여기는 할 일이 없다)"""

    # ---------------- 왼쪽: 머리 띠 · 소지금 · 주머니 창 · 아래 단추
    def _paint_left(self, cv, H):
        s = U.h
        W = cv.winfo_width()
        c1, _c2, _top = self._em_layout(W, H)
        m, g = s(10), s(4)
        x1, x2 = m, c1 - g
        ins = gba.inset()
        # 빨간 머리 띠 '◀ 주머니 ▶' (시안 .pocket)
        hy1, hy2 = m, m + s(self.TOP_PX)
        gba.header(cv, x1, hy1, x2, hy2, self._pocket_label(), font(13), tags=T,
                   arrow_tags=lambda d: ("earrow", "earrow%d" % d))
        for d in (-1, 1):
            cv.tag_bind("earrow%d" % d, "<Button-1>", lambda _e, dd=d: self._step_pocket(dd))
        # 소지금 창 (시안 .money)
        my1, my2 = hy2 + s(8), hy2 + s(8) + s(self.TOP_PX)
        gba.frame(cv, x1, my1, x2, my2, tags=T)
        cv.create_text(x1 + ins + s(10), (my1 + my2) // 2, text=self._money_label(), fill=INK, font=font(10),
                       anchor="w", tags=T)
        cv.create_text(x2 - ins - s(10), (my1 + my2) // 2, text=self._lcd_text(), fill=INK, font=font(13),
                       anchor="e", tags=T)
        # 아래 단추: 팔기 · 여러 개 팔기 (기술머신: 새 기술머신) - 칸 폭에 안 들면 두 줄로
        btns = [b for b in self._dial_buttons() if b is not None]
        bh, gap = s(40), s(6)
        ws = [b.want_width(s(22)) for b in btns]
        rows = [[]]
        for bt, w in zip(btns, ws):
            used = sum(ww for _b, ww in rows[-1]) + gap * len(rows[-1])
            if rows[-1] and used + w > x2 - x1:
                rows.append([])
            rows[-1].append((bt, min(w, x2 - x1)))
        rows = [r for r in rows if r]
        bot = (H - m - len(rows) * bh - (len(rows) - 1) * s(6) - s(8)) if rows else H - m
        by = bot + s(8)
        for r in rows:
            tw = sum(w for _b, w in r) + gap * (len(r) - 1)
            bx = (x1 + x2 - tw) // 2
            for bt, w in r:
                bt.layout(bx, by, bx + w, by + bh)
                bx += w + gap
            by += bh + s(6)
        # 주머니 창: 주머니 줄 (고른 주머니는 연노랑 띠 + 빨간 ▶) + 맨 아래 한 줄 (몇 종 · 몇 개 + [새로고침])
        py1, py2 = my2 + s(8), bot
        gba.frame(cv, x1, py1, x2, py2, tags=T)
        rb = self._em_reload_button()
        rw = rb.want_width(s(16))
        rbh = s(28)
        rb.layout(x2 - ins - s(6) - rw, py2 - ins - s(4) - rbh, x2 - ins - s(6), py2 - ins - s(4))
        line = self._line_text()
        lw = x2 - x1 - 2 * ins - s(22) - rw
        lh = max(rbh, K.text_height(cv, line, font(9), lw))
        K.text(cv, x1 + ins + s(8), py2 - ins - s(4) - lh // 2 - s(1), line, font(9), fill=INK2, width=lw,
               anchor="w", tags=T)
        cv.create_line(x1 + ins + s(4), py2 - ins - s(12) - lh, x2 - ins - s(4), py2 - ins - s(12) - lh,
                       fill="#e4e4da", tags=T)
        n = len(POCKETS)
        inner = py2 - py1 - 2 * ins - s(20) - lh
        rh = max(s(22), min(s(34), inner // n))
        y = py1 + ins + s(4)
        now = self._pocket_now()
        f11 = font(11)
        for key, _l in POCKETS:
            if y + rh > py2 - ins - s(12) - lh:
                break
            on = key == now
            tg = T + ("epk", "epk_" + key)
            cv.create_rectangle(x1 + ins + s(2), y, x2 - ins - s(2), y + rh, fill=SELY if on else "",
                                outline="", tags=tg)
            mid = y + rh // 2
            if on:
                gba.cursor(cv, x1 + ins + s(6), mid, s(6), tags=tg)
            empty = key not in ("all", "tms") and self._pocket_count(key) == 0
            name = POCKET_NAME.get(key, key).replace("\n", " ")
            nx = x1 + ins + s(24)
            cv.create_text(nx, mid, text=name, fill=DIM if empty else INK, font=f11, anchor="w", tags=tg)
            cnt = self._pocket_count_text(key)
            if cnt:
                cv.create_text(x2 - ins - s(10), mid, text=cnt, fill=GRP, font=font(10), anchor="e", tags=tg)
            if key == "tms" and getattr(self, "_tm_badge", False):
                d = s(4)
                fx = nx + K.tkfont_of(cv, f11).measure(name) + s(10)
                cv.create_oval(fx - d, mid - d, fx + d, mid + d, fill="#ff4040", outline=PAPER, width=2, tags=tg)
            cv.tag_bind("epk_" + key, "<Button-1>", lambda _e, kk=key: self._pocket_click(kk))
            y += rh
        self._hand("epk", "earrow")
        return c1

    # ---------------- 가운데 목록 창 (찾기 · 줄 세우기 · 목록) - 안쪽 사각형을 돌려준다
    def _list_frame(self, cv, c1, c2, top, H):
        s = U.h
        g, m = s(4), s(10)
        x1, y1, x2, y2 = c1 + g, top + s(8), c2 - g, H - m
        gba.frame(cv, x1, y1, x2, y2, tags=T)
        ins = gba.inset()
        return x1 + ins + s(8), y1 + ins + s(5), x2 - ins - s(6), y2 - ins - s(4)

    def _tabs(self, cv, x, y, h, items, current, tag, on_pick, spec=None, align="left", fill_off=None,
              line_off=None, span=None):
        """줄 세우기 칸 줄 (시안 .sorts). span 을 주면 x ~ span 을 고르게 나눈다. 그린 칸들 [(열쇠, 상자)]."""
        spec = spec or font(10)
        f = K.tkfont_of(cv, spec)
        gap = U.h(4)
        if span:
            n = max(1, len(items))
            w0 = (span - x - gap * (n - 1)) / float(n)
            ws = [max(w0, f.measure(lb) + U.h(14)) for _k, lb in items]
        else:
            ws = [f.measure(lb) + U.h(20) for _k, lb in items]
        if align == "right":
            x -= sum(ws) + gap * (len(items) - 1)
        out = []
        for (key, lb), w in zip(items, ws):
            tg = T + (tag, "%s_%s" % (tag, key or "_"))
            gba.sort_box(cv, int(x), y, int(x + w), y + h, lb, spec, key == current and current is not None, tags=tg)
            cv.tag_bind("%s_%s" % (tag, key or "_"), "<Button-1>", lambda _e, k=key: on_pick(k))
            out.append((key, (int(x), y, int(x + w), y + h)))
            x += w + gap
        self._hand(tag)
        return out

    # ---------------- 오른쪽 위: 설명 창
    def _em_info(self):
        """설명 창의 내용 {name, chip: (글, 빛깔) 또는 None, sub, body, art(cv, x, y, s)}. 기본은 _band_content."""
        title, body, art = self._band_content()
        return {"name": title, "chip": None, "sub": "", "body": body, "art": art}

    ART_PX = 56

    def _info_height(self, cv, x1, x2, H, compact=False):
        """설명 창에 다 드는 높이. compact = 그림 칸 없이 (작은 창 - 설명 글이 먼저다)."""
        s = U.h
        info = self._em_info()
        ins = gba.inset()
        tw = x2 - x1 - 2 * ins - s(28)
        art = 0 if compact else s(self.ART_PX)
        head_w = tw - (art + s(14) if art else 0)
        nh = K.text_height(cv, info["name"], font(13), head_w)
        sh = K.text_height(cv, info["sub"], font(10), head_w) + s(4) if info["sub"] else 0
        head = max(art, nh + sh)
        bh = K.text_height(cv, info["body"], font(11), tw) if info["body"] else 0
        return min(int(H * 0.42), 2 * ins + s(18) + head + (s(8) + bh if bh else 0))

    def _info_fit(self, cv, x1, x2, H, room):
        """설명 창 높이: room(누구에게 창이 포켓몬 두 줄을 지키고 남는 높이)에 다 들면 그대로, 안 들면 그림 칸
        없는 모양의 높이 (설명 글은 자르지 않고, 남는 자리는 포켓몬 줄에 준다)."""
        full = self._info_height(cv, x1, x2, H)
        return full if full <= room else self._info_height(cv, x1, x2, H, compact=True)

    def _paint_info(self, cv, x1, y1, x2, y2):
        s = U.h
        info = self._em_info()
        gba.frame(cv, x1, y1, x2, y2, tags=T)
        ins = gba.inset()
        H = cv.winfo_height()
        compact = (y2 - y1) < self._info_height(cv, x1, x2, H)
        ix, iy = x1 + ins + s(12), y1 + ins + s(10)
        tw = x2 - x1 - 2 * ins - s(28)
        art = 0 if compact else s(self.ART_PX)
        if art:
            b = max(2, s(3))
            cv.create_rectangle(ix, iy, ix + art, iy + art, fill=NAVY, outline="", tags=T)
            cv.create_rectangle(ix + b, iy + b, ix + art - b, iy + art - b, fill=ART_BG, outline="", tags=T)
            if info.get("art") is not None:
                info["art"](cv, ix + b, iy + b, art - 2 * b)
        hx = ix + (art + s(14) if art else 0)
        head_w = tw - (art + s(14) if art else 0)
        _a, nid = K.text(cv, hx, iy, info["name"], font(13), width=head_w, tags=T)
        bb = cv.bbox(nid)
        ny2 = bb[3] if bb else iy + s(22)
        chip = info.get("chip")
        if chip and bb:
            ctext, ccol = chip
            f9 = K.tkfont_of(cv, font(9))
            cw = f9.measure(ctext) + s(12)
            ch = f9.metrics("linespace") + s(2)
            cx = bb[2] + s(8)
            if cx + cw > x2 - ins - s(8):          # 이름 옆에 안 들면 이름 아래 줄로
                cx, cy = hx, ny2 + s(4) + ch // 2
                ny2 += ch + s(4)
            else:
                cy = (bb[1] + bb[3]) // 2
            cv.create_rectangle(cx, cy - ch // 2, cx + cw, cy + ch // 2, fill=ccol, outline="", tags=T)
            cv.create_text(cx + cw // 2, cy, text=ctext, fill="#ffffff", font=font(9), anchor="center", tags=T)
        if info.get("sub"):
            _a, sid = K.text(cv, hx, ny2 + s(4), info["sub"], font(10), fill=INK2, width=head_w, tags=T)
            sb = cv.bbox(sid)
            ny2 = sb[3] if sb else ny2 + s(20)
        by = max(iy + art, ny2) + s(8)
        if info.get("body"):
            # 창에 다 안 들면 (아주 작은 창) 들어가는 줄까지만 + '…'
            lines = K.wrap(cv, info["body"], font(11), tw).split("\n")
            ls = K.tkfont_of(cv, font(11)).metrics("linespace")
            fit = max(1, (y2 - ins - s(4) - by) // max(1, ls))
            if len(lines) > fit:
                lines = lines[:fit]
                lines[-1] = lines[-1].rstrip() + "…"
            cv.create_text(ix, by, text="\n".join(lines), fill=INK, font=font(11), anchor="nw", tags=T)

    # ---------------- 오른쪽 아래: 누구에게 창
    def _who_rows(self, cv, x0, W, title, hint):
        """누구에게 창 머리의 줄 짜기 - 줄이 가장 적게 드는 것을 고른다 (포켓몬 줄을 한 화면에 더 많이).

            "A"  [제목 · 안내 · N마리] [찾기 칸 · 줄 세우기]
            "B"  [제목 · 줄 세우기] [안내] [찾기 칸 · N마리]
            "C"  [제목 · 안내 · N마리] [찾기 칸] [줄 세우기]
            "D"  [제목] [안내] [찾기 칸 · N마리] [줄 세우기]

        'N마리'(찾는 중의 수) 자리는 늘 남긴다 - 찾을 때마다 줄이 오르내리지 않게."""
        s = U.h
        f9 = K.tkfont_of(cv, font(9))
        sorts = box_filter.PICK_SORTS
        tabs_w = sum(f9.measure(lb) + s(20) for _k, lb in sorts) + s(4) * (len(sorts) - 1)
        tw = K.tkfont_of(cv, font(11)).measure(title)
        beside = (not hint) or x0 + s(4) + tw + s(14) + f9.measure(hint) + s(12) + s(56) <= W
        inline = W - tabs_w - s(10) - (x0 + s(44)) >= s(96)
        up = x0 + s(4) + tw + s(16) + tabs_w <= W
        if beside and inline:
            return "A"
        if up:
            return "B"
        return "C" if beside else "D"

    def _who_need(self, cv, x1, x2, title, hint, note, boxes):
        """누구에게 창이 포켓몬 두 줄은 보이려면 필요한 높이 (설명 창을 줄이는 기준)."""
        s = U.h
        ins = gba.inset()
        x0, W = x1 + ins + s(10), x2 - ins - s(8)
        mode = self._who_rows(cv, x0, W, title, hint)
        need = 2 * ins + s(12) + s(32) + s(40) + s(12)
        if hint and mode in ("B", "D"):
            need += K.text_height(cv, hint, font(9), W - x0 - s(8)) + s(6)
        if note is None or self.find.searching():
            need += s(34) + 2 * self.PLATE_H + (s(32) if mode in ("C", "D") else 0)
        else:
            need += s(80)
        need += sum(h + s(6) for h, _d in boxes)
        return need

    def _paint_who(self, cv, x1, y1, x2, y2, title, hint, note, boxes, btn):
        """누구에게 창: 머리 · 안내, 찾기 · 줄 세우기, (끼우는 칸), 포켓몬 줄 목록, 오른쪽 아래 큰 단추."""
        s = U.h
        gba.frame(cv, x1, y1, x2, y2, tags=T)
        ins = gba.inset()
        ix1, ix2 = x1 + ins + s(10), x2 - ins - s(8)
        # 큰 단추 (오른쪽 아래)
        bh = s(40)
        bw = max(btn.want_width(s(44)), int((ix2 - ix1) * 0.55))
        bw = min(bw, ix2 - ix1)
        by2 = y2 - ins - s(6)
        btn.kind = "cta"
        btn.layout(ix2 - bw, by2 - bh, ix2, by2)
        self._paint_plates_area(cv, ix1, ix2, y1 + ins + s(6), by2 - bh - s(6), title, hint, note, boxes)

    def _paint_plates_area(self, cv, x0, W, y1, y2, title, hint, note, boxes=()):
        """누구에게 창 안쪽 (DP scene.Plates 의 같은 이름 - 빛깔 · 칸만 시안대로). x0 ~ W 가 안쪽 폭.
        머리의 줄 짜기는 _who_rows (줄이 가장 적게 드는 것)."""
        s = U.h
        fh = s(26)
        mode = self._who_rows(cv, x0, W, title, hint)
        listing = note is None or self.find.searching()
        sorts = box_filter.PICK_SORTS
        cv.create_text(x0 + s(4), y1 + fh // 2, text=title, fill=GRP, font=font(11), anchor="w", tags=T)
        count_at_top = mode in ("A", "C")
        if hint and count_at_top:
            tw = K.tkfont_of(cv, font(11)).measure(title)
            cv.create_text(x0 + s(4) + tw + s(14), y1 + fh // 2, text=hint, fill=INK2, font=font(9), anchor="w",
                           tags=T)
        if count_at_top and self.find.count:
            cv.create_text(W, y1 + fh // 2, text=self.find.count, fill=INK2, font=font(9), anchor="e", tags=T)
        if mode == "B" and listing:
            self._tabs(cv, W, y1, fh, sorts, self.find.sort, "msrt", self.find.pick_sort, spec=font(9),
                       align="right")
        fy = y1 + fh + s(6)
        if hint and not count_at_top:
            _a, hid = K.text(cv, x0 + s(4), fy - s(2), hint, font(9), fill=INK2, width=W - x0 - s(8), tags=T)
            b = cv.bbox(hid)
            fy = (b[3] if b else fy + s(16)) + s(6)
        if not listing:
            self._hide("mfind")
            self._paint_plates_rest(cv, x0, W, fy, y2, note, boxes)
            return
        cv.create_text(x0 + s(4), fy + fh // 2, text="찾기", fill=INK, font=font(10), anchor="w", tags=T)
        ex = x0 + s(44)
        ex2 = W
        y = fy + fh + s(8)
        if mode == "A":
            tabs = self._tabs(cv, W, fy, fh, sorts, self.find.sort, "msrt", self.find.pick_sort, spec=font(9),
                              align="right")
            ex2 = (tabs[0][1][0] if tabs else W) - s(10)
        elif mode in ("B", "D"):
            ex2 = W - s(56)
            if self.find.count:
                cv.create_text(W, fy + fh // 2, text=self.find.count, fill=INK2, font=font(9), anchor="e", tags=T)
        if mode in ("C", "D"):
            self._tabs(cv, x0 + s(4), y - s(2), fh, sorts, self.find.sort, "msrt", self.find.pick_sort,
                       spec=font(9), span=W)
            y += fh + s(6)
        self._place("mfind", self.find.box, ex, fy, max(s(80), ex2 - ex), fh)
        self._paint_plates_rest(cv, x0, W, y, y2, note, boxes)

    def _paint_plates_rest(self, cv, x0, W, y, y2, note, boxes):
        s = U.h
        for h, draw in boxes:
            draw(cv, x0, y, W)
            y += h + s(6)
        if note is None:
            cols = 2 if (W - x0) >= s(440) else 1
            if cols != self._plate_cols:
                self._plate_cols = cols
                self._plates_set(self._plate_rows_src, keep=True)
            self._place("mons", self.mons_vl.frame, x0, y, W - x0, max(s(40), y2 - y))
        else:
            self._hide("mons")
            K.text(cv, (x0 + W) // 2, y + s(18), note, font(11), anchor="n", justify="center",
                   width=W - x0 - s(24), tags=T)

    # ---- 포켓몬 줄 (시안 .mon: 고른 줄은 연노랑 + 빨간 ▶, 상태는 오른쪽 - 좋음은 초록)
    def _plate_box(self, x, y, w, h, k):
        cols = max(1, self._plate_cols)
        pw = w // cols
        return x + k * pw, y, x + (k + 1) * pw - (U.h(6) if k < cols - 1 else 0), y + h

    def _draw_plate(self, cv, m, x1, y1, x2, y2, tags, hov):
        s = U.h
        info = self._plate_info(m)
        blocked, good = info.get("blocked"), info.get("good")
        sel = m.get("id") == self.mon_id
        if sel:
            cv.create_rectangle(x1, y1 + 1, x2, y2 - 1, fill=SELY, outline="", tags=tags)
        elif hov and not blocked:
            cv.create_rectangle(x1, y1 + 1, x2, y2 - 1, fill=HOV, outline="", tags=tags)
        cv.create_line(x1 + s(4), y2 - 1, x2 - s(4), y2 - 1, fill="#e4e4da", tags=tags)
        mid = (y1 + y2) // 2
        if sel:
            gba.cursor(cv, x1 + s(4), mid, s(6), tags=tags)
        ph = info.get("photo")
        if ph is not None:
            cv.create_image(x1 + s(42), mid, image=ph, tags=tags)
        name = info.get("name") or "?"
        if info.get("shiny"):
            name = "★ " + name
        tx = x1 + s(70)
        ink = DIM if blocked else INK
        cv.create_text(tx, y1 + s(3), text=name, fill="#8a5a00" if info.get("shiny") else ink, font=font(11),
                       anchor="nw", tags=tags)
        cv.create_text(tx, y2 - s(3), text=info.get("sub") or "", fill=DIM if blocked else GRP, font=font(9),
                       anchor="sw", tags=tags)
        if info.get("note"):
            f9 = K.tkfont_of(cv, font(9))
            nw = f9.measure(info["note"])
            low = tx + f9.measure(info.get("sub") or "") + s(10) <= x2 - s(10) - nw
            col = GREEN_OK if good else tone(info.get("color") or U.FG_DIM)
            cv.create_text(x2 - s(10), (y2 - s(3)) if low else (y1 + s(5)), text=info["note"], fill=col,
                           font=font(9), anchor="se" if low else "ne", tags=tags)


class BagWindow(GBABag, DPB.BagWindow):

    def _build(self):
        DPB.BagWindow._build(self)
        self.items_vl.cv.configure(bg=PAPER)
        self.items_vl.frame.configure(bg=PAPER)
        self.mons_vl.cv.configure(bg=PAPER)
        self.mons_vl.frame.configure(bg=PAPER)
        self.use_btn.kind = "cta"

    def _em_info(self):
        it = self._item
        if not it:
            title, body, art = self._band_content()
            return {"name": title, "chip": None, "sub": "", "body": body, "art": art}
        rk = it.get("rarity")
        chip = (DPB.RARITY_KR[rk], DPB.RARE[rk]) if rk in DPB.RARITY_KR else None

        def art(cv, x, y, sz):
            ph = item_icons.photo(it["id"], max(32, sz - U.h(4)))
            if ph is not None:
                cv.create_image(x + sz // 2, y + sz // 2, image=ph, tags=T)
        sub = "가진 수 %d개 · %s" % (self.bag.get(it["id"], 0), B.CAT_KR.get(it["cat"], it["cat"]))
        return {"name": it["kr"], "chip": chip, "sub": sub, "body": natural(B.item_desc(it)), "art": art}

    def _paint(self):
        self._job = None
        if not self.alive:
            return
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
        c1, c2, top = self._em_layout(W, H)
        self._paint_back(cv, W, H)
        self._paint_top(cv, W, c1, c2, top)
        self._paint_left(cv, H)
        self._paint_list(cv, c1, c2, H)
        g, m = s(4), s(10)
        rx1, rx2 = c2 + g, W - m
        iy1 = top + s(8)
        it = self._item
        hint = B.target_hint(it) if it else ""
        boxes = self._boxes(cv, rx2 - rx1 - 2 * gba.inset() - s(18))
        need = self._who_need(cv, rx1, rx2, "누구에게 쓸까?", hint, self._mon_note, boxes)
        ih = self._info_fit(cv, rx1, rx2, H, H - m - iy1 - s(8) - need)
        self._paint_info(cv, rx1, iy1, rx2, iy1 + ih)
        self.close_btn.hide()
        self._paint_who(cv, rx1, iy1 + ih + s(8), rx2, H - m, "누구에게 쓸까?", hint, self._mon_note, boxes,
                        self.use_btn)
        self._toast_box = (rx1, iy1, rx2, iy1 + ih)
        self._paint_toast()

    def _paint_list(self, cv, x0, x1, H):
        """가운데 목록 창: 찾기 줄 · 줄 세우기 줄(칸을 고르게) · 도구 목록."""
        s = U.h
        _c1, _c2, top = self._em_layout(cv.winfo_width(), H)
        ix1, iy1, ix2, iy2 = self._list_frame(cv, x0, x1, top, H)
        th = s(26)
        cv.create_text(ix1, iy1 + th // 2, text="찾기", fill=INK, font=font(10), anchor="w", tags=T)
        ex = ix1 + s(40)
        self._place("ifind", self.item_find, ex, iy1, ix2 - ex, th)
        iy1b = iy1 + th + s(6)
        self._tabs(cv, ix1, iy1b, th, B.ITEM_SORTS, self.item_sort, "srt", self.set_item_sort, span=ix2)
        ly1 = iy1b + th + s(6)
        if self._items_state == "list":
            self._place("items", self.items_vl.frame, ix1 - s(4), ly1, ix2 - ix1 + s(4), iy2 - ly1)
        else:
            self._hide("items")
            note = self._items_note if self._items_state == "nomatch" else \
                "가방이 비어 있다.\n야생 포켓몬을 잡거나 배틀에서 도구를 주울 수 있다."
            K.text(cv, (ix1 + ix2) // 2, ly1 + s(40), note, font(11), anchor="n", justify="center",
                   width=ix2 - ix1 - 20, tags=T)

    def _draw_item_row(self, cv, data, x, y, w, h, tags, hover=None):
        """목록 한 줄 (시안 .row): 고른 줄은 연노랑 띠 + 빨간 ▶. 단락 머리는 회청색 글씨 ('열매 · 3종')."""
        s = U.h
        kind, val = data
        if kind == "head":
            cat, n = val[0], val[1]
            sub = val[2] if len(val) > 2 else None
            label = ("%s · %s · %d종" % (B.CAT_KR.get(cat, cat), sub, n)) if sub else \
                "%s · %d종" % (B.CAT_KR.get(cat, cat), n)
            gba.group_head(cv, x + s(6), y + h // 2 + s(2), label, font(9), tags=tags)
            return
        it = val
        usable = (it.get("effect") or {}).get("kind") in B.USABLE
        sel = it["id"] == self.item_id
        if sel:
            cv.create_rectangle(x, y, x + w, y + h, fill=SELY, outline="", tags=tags)
        elif hover is not None:
            cv.create_rectangle(x, y, x + w, y + h, fill=HOV, outline="", tags=tags)
        m = y + h // 2
        if sel:
            gba.cursor(cv, x + s(4), m, s(6), tags=tags)
        icon = item_icons.photo(it["id"], 24) or item_icons.photo(it["id"], 20)
        ix = x + s(18) + s(13)
        if icon is not None:
            cv.create_image(ix, m, image=icon, tags=tags)
        else:
            cv.create_rectangle(ix - 3, m - 3, ix + 3, m + 3, fill=B.CAT_COLOR.get(it.get("cat"), DIM), outline="",
                                tags=tags)
        fg = INK if usable else DIM
        nid = cv.create_text(x + s(52), m, text=it["kr"], fill=fg, font=font(11), anchor="w", tags=tags)
        cx = x + w - s(10)
        cv.create_text(cx, m, text="×%d" % self.bag.get(it["id"], 0), fill=fg, font=font(11), anchor="e", tags=tags)
        rk = it.get("rarity")
        if rk in DPB.RARITY_KR:
            rx = cx - s(46)
            f = K.tkfont_of(cv, font(9))
            b = cv.bbox(nid)
            if not b or b[2] + s(10) <= rx - f.measure(DPB.RARITY_KR[rk]):
                cv.create_text(rx, m, text=DPB.RARITY_KR[rk], fill=DPB.RARE[rk] if usable else DIM, font=font(9),
                               anchor="e", tags=tags)
