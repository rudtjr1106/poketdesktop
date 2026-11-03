# -*- coding: utf-8 -*-
"""상점 맨 위의 '랜덤 기술머신 뽑기' 띠 (2.1.1) - 기본 · DP 테마가 같이 쓴다 (ui_gacha.Banner 와 같은 틀).

    [뽑기권 그림] 랜덤 기술머신 뽑기                         [ 1회 · 10,000원 ] [ 10회 · 100,000원 ]
                  아직 없는 기술머신만 나와요 · 남은 357개

한 번 = 랜덤 기술머신 뽑기권 한 장 값 (서버 /api/shop 의 tmDraw.price), 10번 = 열 장 값 (사용자 결정 11/04).
무엇이 나오는지는 서버가 정한다 - 아직 없는 기술머신만, 열 번 안에서도 겹치지 않는다. 뽑으면 결과 창이 뜨고
상점(돈) · 기술머신의 노란 점을 새로 읽는다. 옛 서버라 tmDraw 가 없으면 띠를 깔지 않는다.

상점 창(shop)에서 쓰는 것: shop.win · shop.app · shop.money · shop.tm_draw · shop.say · shop.reload.
"""
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from common.korean import natural

from . import item_icons
from . import ui_box
from . import ui_common as U
from . import ui_gacha as G

COUNTS = (1, 10)
HEIGHT = 66
PILL_W, PILL_H, PILL_GAP = 156, 38, 10
TOP, BOT = (34, 120, 196), (40, 54, 150)              # 띠 빛깔 (캡슐 띠의 자홍과 갈리게 파랑)
PILL = {"on": ((92, 214, 255), (24, 128, 214)), "hover": ((128, 226, 255), (40, 150, 232)),
        "off": ((132, 140, 160), (82, 88, 108))}


def won(n):
    return "%s원" % format(int(n), ",")


def _rgb(hexcol):
    return tuple(int(hexcol[i:i + 2], 16) for i in (1, 3, 5))


class Banner(object):
    def __init__(self, parent, shop, bg, before=None):
        self.shop = shop
        self.before = before                               # 띠를 다시 깔 때 이 위젯 앞에 (상점 몸통)
        self.s = U.h(100) / 100.0
        self.cv = tk.Canvas(parent, bg=bg, highlightthickness=0, bd=0, height=int(HEIGHT * self.s))
        self.cv.bind("<Configure>", lambda e: self._paint(e.width))
        self.cv.bind("<Motion>", self._motion)
        self.cv.bind("<Leave>", lambda _e: self._hover(None))
        self.cv.bind("<Button-1>", self._click)
        self.ph = None
        self.pills = {}                                    # n -> (x0, y0, x1, y1) 캔버스 자리
        self.hot = None
        self.busy = False
        self.shown = False
        self.result_win = None

    # ---------------- 깔기
    def update(self):
        """상점을 다시 받은 뒤: tmDraw 가 있으면 깔고 다시 칠한다 (없으면 걷는다)."""
        info = getattr(self.shop, "tm_draw", None)
        if not info:
            if self.shown:
                self.cv.pack_forget()
                self.shown = False
            return
        if not self.shown:
            kw = dict(fill="x", padx=U.h(16), pady=(U.h(10), U.h(4)))
            if self.before is not None:
                kw["before"] = self.before
            self.cv.pack(**kw)
            self.shown = True
        self._paint(self.cv.winfo_width())

    def info(self):
        return getattr(self.shop, "tm_draw", None) or {}

    def can(self, n):
        """(누를 수 있나, 못 누르면 까닭)."""
        i = self.info()
        price, left = int(i.get("price") or 0), int(i.get("left") or 0)
        if price <= 0:
            return False, "지금은 뽑을 수 없습니다."
        if left <= 0:
            return False, "기술머신을 이미 다 모아서 뽑을 것이 없습니다."
        if left < n:
            return False, "아직 없는 기술머신이 %d개뿐이라 %d번은 뽑을 수 없습니다." % (left, n)
        if int(getattr(self.shop, "money", 0) or 0) < price * n:
            return False, "돈이 모자랍니다. (%s 필요)" % won(price * n)
        return True, ""

    # ---------------- 칠하기
    def _paint(self, w):
        if w <= 2 or not self.shown:
            return
        s, SS = self.s, G.SS
        h = int(HEIGHT * s)
        i = self.info()
        price, left = int(i.get("price") or 0), int(i.get("left") or 0)
        W2, H2 = w * SS, h * SS
        im = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
        col = Image.new("RGBA", (W2, 1))
        for x in range(W2):
            t = x / float(max(1, W2 - 1))
            col.putpixel((x, 0), tuple(int(TOP[k] + (BOT[k] - TOP[k]) * t) for k in range(3)) + (255,))
        r = int(14 * s * SS)
        G._paste_round(im, col.resize((W2, H2), Image.NEAREST), (0, 0), r)
        G._comp_round(im, G._light(W2, H2 // 2, 70), (0, 0), r)
        ImageDraw.Draw(im).rounded_rectangle((0, 0, W2 - 1, H2 - 1), r, outline=(150, 220, 255, 255),
                                             width=max(2, int(1.5 * s * SS)))
        x = int(16 * s * SS)
        icon = item_icons.pil("RANKTICKETTM")
        if icon is not None:
            n = max(1, int(44 * s * SS) // max(icon.size))
            ic = icon.resize((icon.width * n, icon.height * n), Image.NEAREST)
            im.alpha_composite(ic, (x, (H2 - ic.height) // 2))
            x += ic.width + int(12 * s * SS)
        t1 = G._text("랜덤 기술머신 뽑기", 19 * s * SS, fill=(255, 255, 255))
        sub = ("아직 없는 기술머신만 나와요 · 남은 %d개" % left) if left else "기술머신을 다 모았어요!"
        t2 = G._text(sub, 12 * s * SS, fill=(214, 236, 255), black=False)
        ty = (H2 - t1.height - t2.height) // 2
        im.alpha_composite(t1, (x, ty))
        im.alpha_composite(t2, (x, ty + t1.height))
        # 알약 단추 둘 (오른쪽부터)
        self.pills = {}
        pw, ph, gap = int(PILL_W * s), int(PILL_H * s), int(PILL_GAP * s)
        right = w - int(14 * s)
        for n in reversed(COUNTS):
            x1, y0 = right, (h - ph) // 2
            x0 = x1 - pw
            self.pills[n] = (x0, y0, x1, y0 + ph)
            ok, _why = self.can(n)
            look = "off" if (not ok or self.busy) else ("hover" if self.hot == n else "on")
            a, b = PILL[look]
            pim = Image.new("RGBA", (pw * SS, ph * SS), (0, 0, 0, 0))
            G._paste_round(pim, G._vgrad(pw * SS, ph * SS, a, b), (0, 0), ph * SS // 2)
            G._comp_round(pim, G._light(pw * SS - 12 * SS, ph * SS // 2, 90), (6 * SS, 2 * SS), ph * SS // 4)
            label = "%d회 · %s" % (n, won(price * n))
            t = G._text(label, 14 * s * SS, fill=(255, 255, 255) if look != "off" else (214, 218, 230))
            pim.alpha_composite(t, ((pim.width - t.width) // 2, (pim.height - t.height) // 2))
            im.alpha_composite(pim, (x0 * SS, y0 * SS))
            right = x0 - gap
        self.ph = ImageTk.PhotoImage(im.resize((w, h), Image.LANCZOS))
        self.cv.delete("all")
        self.cv.create_image(0, 0, anchor="nw", image=self.ph)

    def _pill_at(self, x, y):
        for n, (x0, y0, x1, y1) in self.pills.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return n
        return None

    def _motion(self, e):
        self._hover(self._pill_at(e.x, e.y))

    def _hover(self, n):
        self.cv.configure(cursor="hand2" if n else "")
        if n != self.hot:
            self.hot = n
            self._paint(self.cv.winfo_width())

    # ---------------- 뽑기
    def _click(self, e):
        n = self._pill_at(e.x, e.y)
        if n:
            self.draw(n)

    def draw(self, n):
        if self.busy:
            return
        ok, why = self.can(n)
        if not ok:
            return self.shop.say(why, U.DANGER)
        price = int(self.info().get("price") or 0)
        if n > 1 and not ui_box.confirm(self.shop.win, "기술머신 %d번 뽑기" % n,
                                        "%s으로 아직 없는 기술머신 %d개를 뽑을까요?" % (won(price * n), n),
                                        danger=False, ok_text="뽑기"):
            return
        api = self.shop.app.api
        self.busy = True
        self._paint(self.cv.winfo_width())
        self.shop.say("기술머신을 뽑는 중...", U.FG_FAINT)
        U.run_async(self.shop.win, lambda: api.shop_tmdraw(n), self._done)

    def _done(self, r, err):
        self.busy = False
        app = self.shop.app
        if err:
            self._paint(self.cv.winfo_width())
            self.shop.say(getattr(err, "message", str(err)), U.DANGER)
            if getattr(err, "status", 0):                 # 거절됐다 (그사이 돈 · 남은 수가 바뀌었다) - 다시 받는다
                self.shop.reload()
            return
        r = r or {}
        note = getattr(app, "note_tms", None)
        if note is not None and r.get("tmNew") is not None:
            note(r["tmNew"])                               # [기술머신] 의 노란 점 · 떠 있는 기술머신 칸
        self.shop.reload()                                 # 돈 · 남은 수
        self.result_win = Result(self.shop.win, r.get("tms") or [], int(r.get("spent") or 0))
        self.shop.say(r.get("message") or "기술머신을 얻었다!", U.GOOD)


# ---------------------------------------------------------------- 결과 창
def card(s, tm):
    """기술머신 한 장: 타입 빛깔 띠 · 번호 · 기술 이름 · 타입."""
    from .ui_tms import TYPE_KR
    SS = G.SS
    w, h = int(168 * s) * SS, int(70 * s) * SS
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    rgb = _rgb(U.TYPE_COLOR.get(tm.get("type"), "#68a090"))
    r = int(12 * s) * SS
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=(30, 22, 58, 255),
                                         outline=rgb + (255,), width=max(2, int(2 * s)) * SS)
    ImageDraw.Draw(im).rounded_rectangle((0, 0, int(8 * s) * SS, h - 1), r, fill=rgb + (255,))
    x = int(16 * s) * SS
    t0 = G._text("기술머신%03d" % int(tm.get("no") or 0), 11 * s * SS, fill=(190, 186, 214), black=False)
    t1 = G._text(tm.get("kr") or "?", 16 * s * SS, fill=(255, 255, 255))
    im.alpha_composite(t0, (x, int(8 * s) * SS))
    im.alpha_composite(t1, (x, int(8 * s) * SS + t0.height + int(3 * s) * SS))    # (번호와 이름이 붙지 않게)
    chip_txt = G._text(TYPE_KR.get(tm.get("type"), tm.get("type") or ""), 11 * s * SS, fill=(255, 255, 255))
    cw, chh = chip_txt.width + int(10 * s) * SS, chip_txt.height + 2 * SS
    cx, cy = w - cw - int(8 * s) * SS, h - chh - int(7 * s) * SS
    ImageDraw.Draw(im).rounded_rectangle((cx, cy, cx + cw, cy + chh), chh // 2, fill=rgb + (255,))
    im.alpha_composite(chip_txt, (cx + (cw - chip_txt.width) // 2, cy + 1 * SS))
    return im.resize((w // SS, h // SS), Image.LANCZOS)


class Result(object):
    """뽑은 기술머신 목록 창 (어두운 판에 카드 다섯 장씩)."""

    def __init__(self, parent, tms, spent):
        self.s = G.fit_scale(parent)
        s = self.s
        cols = 5 if len(tms) > 1 else 1
        rows = max(1, (len(tms) + cols - 1) // cols)
        cw, chh, gap, pad = int(168 * s), int(70 * s), int(10 * s), int(20 * s)
        head = int(54 * s)
        foot = int(66 * s)
        W = max(int(360 * s), cols * cw + (cols - 1) * gap + pad * 2)
        H = head + rows * chh + (rows - 1) * gap + foot
        self.win = tk.Toplevel(parent)
        U.style_window(self.win, "기술머신 뽑기 결과", W, H)
        self.win.resizable(False, False)
        self.cv = tk.Canvas(self.win, width=W, height=H, bg=G._hex(G.BASE), highlightthickness=0, bd=0)
        self.cv.pack()
        self.ph = []
        t = G._text("기술머신 %d개를 얻었다!" % len(tms) if len(tms) > 1 else "기술머신을 얻었다!", 19 * s,
                    fill=(255, 236, 170), glow=((255, 190, 60), 6 * s))
        self._img(W // 2, int(28 * s), t)
        for i, tm in enumerate(tms):
            x = pad + (i % cols) * (cw + gap)
            y = head + (i // cols) * (chh + gap)
            if cols == 1:
                x = (W - cw) // 2
            self._img(x + cw // 2, y + chh // 2, card(s, tm))
        sub = "%s을(를) 썼다 · 기술머신 탭에서 가르칠 수 있어요" % won(spent) if spent else "기술머신 탭에서 가르칠 수 있어요"
        self._img(W // 2, H - foot + int(20 * s), G._text(natural(sub), 13 * s, fill=(200, 196, 230), black=False))
        btn = self.cv.create_text(W // 2, H - int(20 * s), text="닫기", fill="#cfc9ef", font=U.FONT_B)
        self.cv.tag_bind(btn, "<Button-1>", lambda _e: self.close())
        self.cv.tag_bind(btn, "<Enter>", lambda _e: self.cv.itemconfigure(btn, fill="#ffffff"))
        self.cv.tag_bind(btn, "<Leave>", lambda _e: self.cv.itemconfigure(btn, fill="#cfc9ef"))
        self.win.bind("<Escape>", lambda _e: self.close())
        self.win.bind("<Return>", lambda _e: self.close())
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        try:
            self.win.transient(parent.winfo_toplevel())
            self.win.lift()
            self.win.focus_force()
        except tk.TclError:
            pass

    def _img(self, x, y, im):
        p = ImageTk.PhotoImage(im)
        self.ph.append(p)
        return self.cv.create_image(x, y, image=p)

    def close(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass
