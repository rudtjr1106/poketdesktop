# -*- coding: utf-8 -*-
"""관장 — 대한민국 지도에서 시·군·구의 트레이너에게 도전한다.

## 두 단계로 들어간다

전국 한 화면에 시·군·구 256곳을 다 그리면 **109곳이 10px 보다 작다**(부산
중구는 2px). 누를 수가 없다. 그래서 먼저 시·도 16곳을 보여 주고, 누르면
그 안의 시·군·구로 들어간다. 들어가서 가장 좁은 곳이 14px 쯤이다.

## 색

시·군·구는 **트레이너 레벨**로 칠한다. 초록(20)에서 빨강·자주(100)로
갈수록 세다. 이긴 곳은 금색 테두리에 체크를 단다. 전국 화면의 시·도는
그 안에서 몇 곳을 이겼는지로 칠한다.

이름은 칸이 넉넉할 때만 지도 위에 쓴다. 좁은 곳에 억지로 쓰면 글자가
겹쳐 읽을 수 없다 - 올려 두면 아래 줄과 오른쪽 카드에 나온다.

## 지도 자료

700KB 라 한 번 받으면 요약값 이름으로 이 PC 에 남긴다. 서버의 요약값이
바뀌었을 때만 다시 받는다.
"""
import io
import json
import math
import os
import tkinter as tk
import tkinter.font as tkfont

from PIL import Image, ImageDraw, ImageTk

from . import config, sprite_cache, sprites
from . import ui_common as U
from .ui_common import run_async

W, H = 1040, 700
SIDE_W = 340
PAD = 18

# 레벨 색: 쉬움(초록) -> 어려움(자주)
STOPS = [(20, (58, 161, 126)), (40, (140, 194, 74)), (60, (242, 193, 78)),
         (80, (240, 123, 63)), (100, (201, 64, 106))]
CLEAR = "#ffc043"


def level_color(lv):
    lv = max(20, min(100, lv))
    for (a, ca), (b, cb) in zip(STOPS, STOPS[1:]):
        if a <= lv <= b:
            t = (lv - a) / float(b - a)
            c = tuple(int(round(x + (y - x) * t)) for x, y in zip(ca, cb))
            return "#%02x%02x%02x" % c
    return "#888888"


def shade(hexcolor, k):
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v * k))) for v in (r, g, b))


def trainer_photo(api, key, scale=None):
    """트레이너 도트를 받아(이 PC 에 남겨) 키운 PhotoImage 재료를 돌려준다.

    scale 을 안 주면 그림 크기로 정한다. 쇼다운 트레이너 도트는 80x80 틀에
    키 74칸이라 두 배로 키운다. 이스터에그처럼 칸이 촘촘한 그림(키 134칸)은
    두 배면 카드를 넘치므로 그대로 쓴다.

    **작업 스레드에서 부른다.** PhotoImage 는 tk 스레드에서만 만들 수 있어서
    PIL 이미지까지만 만든다.
    """
    d = os.path.join(config.data_dir(), "trainers")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "%s.png" % key)
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        raw = api.gym_sprite(key)
        if not raw:
            return None
        with open(p + ".part", "wb") as f:
            f.write(raw)
        os.replace(p + ".part", p)
    im = Image.open(p).convert("RGBA")
    bb = im.getbbox()
    if bb:
        im = im.crop(bb)             # 80x80 틀의 빈 위아래를 뺀다 (옆 칸 높이를 아낀다)
    if scale is None:
        scale = 2 if im.height <= 90 else 1
    if scale == 1:
        return im
    return im.resize((im.width * scale, im.height * scale), Image.NEAREST)


def mon_thumb(api, num, size):
    """포켓몬 작은 그림 (PIL). 작업 스레드에서."""
    path = sprite_cache.ensure(api, num, False)
    if not path:
        return None
    anim = sprites.load_animation(path, size, 0.2, 2.0, max_frames=1)
    return sprites.to_rgba(anim.frames[sprites.RIGHT][0], anim.key)


class GymWindow(object):

    def __init__(self, root, app, parent=None):
        self.root = root
        self.app = app
        self.alive = True
        self.data = None
        self.map = None
        self.by_region = {}
        self.sido = None             # 들어가 있는 시·도 코드 (None 이면 전국)
        self.selected = None         # 고른 시·군·구 코드
        self.photos = {}
        self.items = {}              # 캔버스 도형 태그 -> 코드
        self._redraw_job = None
        self.battle = None
        self.zoom = 1.0              # 시·도 지도 확대 (휠)
        self.pan = [0.0, 0.0]        # 끌어 옮긴 만큼 (px)
        self._drag = None
        self._dragged = False
        self._layouts = {}           # 시·도 코드 -> 섬 당겨 그리기 결과

        self.win = U.panel(parent, root, "포스크탑 — 관장", W, H, 900, 600, self.close)
        self.win.configure(bg=U.BG, highlightthickness=2, highlightbackground=U.LINE2)
        if not U.is_embedded(self.win):
            U.install_wheel(self.win)

        self._header()
        body = tk.Frame(self.win, bg=U.BG)
        body.pack(fill="both", expand=True)
        self._side(body)
        self._canvas(body)
        self.reload()

    # ---------------- 틀 ----------------
    def _header(self):
        h = tk.Frame(self.win, bg=U.BG2, height=U.h(62))
        h.pack(fill="x")
        h.pack_propagate(False)
        inner = tk.Frame(h, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16)
        tk.Label(inner, text="관장", bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY_BLACK, U.pt(15))).pack(side="left", pady=17)
        self.sub = tk.Label(inner, text="불러오는 중...", bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S)
        self.sub.pack(side="left", padx=(12, 0))
        self.back_btn = U.ghost_button(inner, "전국 지도", self.to_nation, height=32)
        self.back_btn.pack(side="right", pady=12)
        tk.Frame(self.win, bg=U.LINE2, height=2).pack(fill="x")

    def _canvas(self, body):
        holder = tk.Frame(body, bg=U.INK)
        holder.pack(side="left", fill="both", expand=True)
        # 상태줄은 지도 밑에만 둔다. 창 전체 폭으로 깔면 옆 카드가 그만큼
        # 짧아져서, 허브 탭 안에서 에이스 줄이 굴려야 보이는 자리로 밀려났다.
        self._status(holder)
        # 범례는 **지도와 다른 캔버스**에 둔다. 한 캔버스에 두면 키운 지도나 마우스를
        # 올려 위로 올린 도형이 범례를 덮었다.
        self.legend_cv = tk.Canvas(holder, bg="#0f141d", highlightthickness=0, height=U.h(50))
        self.legend_cv.pack(side="bottom", fill="x")
        tk.Frame(holder, bg=U.LINE, height=1).pack(side="bottom", fill="x")
        self.cv = tk.Canvas(holder, bg="#0f141d", highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", self._on_resize)
        # 시·도 안에서는 휠로 키우고 끌어서 옮긴다. 경기·인천의 구는 작아서
        # 맞춤 크기로는 누르기 빡빡하다.
        self.cv.bind("<MouseWheel>", self._on_wheel)
        # 윈도우의 Tk 는 휠을 포커스 가진 위젯으로 보낸다. 창에 건 install_wheel 이
        # 포인터 밑을 찾아 이걸 불러 준다 (허브 탭 안에서도 같다).
        self.cv.wheel_handler = self._on_wheel
        self.cv.bind("<Button-4>", lambda e: self._on_wheel(e, 1))
        self.cv.bind("<Button-5>", lambda e: self._on_wheel(e, -1))
        self.cv.bind("<ButtonPress-1>", self._drag_start, add="+")
        self.cv.bind("<B1-Motion>", self._drag_move, add="+")
        self.cv.bind("<ButtonRelease-1>", self._drag_end, add="+")

    def _side(self, body):
        self.side = tk.Frame(body, bg=U.BG2, width=U.h(SIDE_W))
        self.side.pack(side="right", fill="y")
        self.side.pack_propagate(False)
        tk.Frame(body, bg=U.LINE, width=1).pack(side="right", fill="y")
        self.crumb = tk.Frame(self.side, bg=U.BG2)
        self.crumb.pack(fill="x", padx=16, pady=(12, 4))
        # 도전 단추는 바닥에 **먼저** 붙인다. 카드가 길면 창 높이 700 에서
        # 64px, 허브 탭 안에서는 90px 넘게 모자라 단추가 통째로 잘렸다.
        self.action = tk.Frame(self.side, bg=U.BG2)
        self.action.pack(side="bottom", fill="x", padx=16, pady=(0, 12))
        # 나머지는 넘치면 굴린다 (에이스가 맨 아래 줄이라 잘리면 안 된다)
        wrap = tk.Frame(self.side, bg=U.BG2)
        wrap.pack(fill="both", expand=True, padx=(16, 4), pady=(0, 8))
        self.card_cv = tk.Canvas(wrap, bg=U.BG2, highlightthickness=0, bd=0)
        self.card_sb = tk.Scrollbar(wrap, orient="vertical", command=self.card_cv.yview)
        self.card_cv.configure(yscrollcommand=self.card_sb.set)
        self.card_cv.pack(side="left", fill="both", expand=True)
        self.card = tk.Frame(self.card_cv, bg=U.BG2)
        self._card_id = self.card_cv.create_window((0, 0), window=self.card, anchor="nw")
        self.card.bind("<Configure>", lambda _e: self._fit_card())
        self.card_cv.bind("<Configure>", lambda e: (
            self.card_cv.itemconfigure(self._card_id, width=e.width - U.h(12)), self._fit_card()))
        U.scrollable(self.card_cv, 60)

    def _fit_card(self):
        """카드가 칸보다 짧으면 굴릴 것도 막대도 없다."""
        try:
            need = self.card.winfo_reqheight()
            view = self.card_cv.winfo_height()
            w = self.card_cv.winfo_width()
            if need <= view:
                self.card_cv.configure(scrollregion=(0, 0, w, view))
                self.card_cv.yview_moveto(0)
                if self.card_sb.winfo_ismapped():
                    self.card_sb.pack_forget()
            else:
                self.card_cv.configure(scrollregion=(0, 0, w, need))
                if not self.card_sb.winfo_ismapped():
                    self.card_sb.pack(side="right", fill="y")
        except tk.TclError:
            pass

    def _status(self, parent):
        bar = tk.Frame(parent, bg=U.INK, height=U.h(30))
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self.status = tk.Label(bar, text="", bg=U.INK, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w")
        self.status.pack(side="left", fill="x", expand=True, padx=12)
        self.source = tk.Label(bar, text="", bg=U.INK, fg=U.FG_FAINT, font=U.FONT_XS, anchor="e")
        self.source.pack(side="right", padx=12)

    def say(self, text, color=None):
        try:
            self.status.configure(text=text, fg=color or U.FG_FAINT)
        except tk.TclError:
            pass

    # ---------------- 불러오기 ----------------
    def reload(self):
        def work():
            data = self.app.api.gym()
            digest = data.get("mapDigest") or "x"
            path = os.path.join(config.data_dir(), "gym_map_%s.json" % digest)
            if os.path.exists(path):
                with io.open(path, encoding="utf-8") as f:
                    m = json.load(f)
            else:
                m = self.app.api.gym_map()
                tmp = path + ".part"
                with io.open(tmp, "w", encoding="utf-8") as f:
                    json.dump(m, f, ensure_ascii=False)
                os.replace(tmp, path)
            return data, m

        def done(r, err):
            if not self.alive:
                return
            if err:
                return self.say("불러오지 못했습니다. %s" % getattr(err, "message", err), U.RED)
            self.data, self.map = r
            self.by_region = {x["region"]: x for x in self.data["regions"]}
            self.sido_names = {s["code"]: s["name"] for s in self.map["sido"]}
            self.sub.configure(text="이긴 곳 %d / %d" % (self.data["cleared"], self.data["total"]))
            self.source.configure(text="지도: 통계청 SGIS · vuski/admdongkor")
            self.redraw()
            if self.selected:
                self.select(self.selected)
            else:
                self._summary()
            act = self.data.get("active")
            if act:
                t = self.by_region.get(act["region"]) or {}
                self.say("%s 과(와)의 승부가 진행 중입니다. 그 지역을 눌러 이어서 하세요."
                         % t.get("name", ""), U.ACCENT)

        run_async(self.root, work, done)

    # ---------------- 그리기 ----------------
    def _on_resize(self, _e=None):
        if self._redraw_job:
            try:
                self.root.after_cancel(self._redraw_job)
            except Exception:                              # noqa: BLE001
                pass
        self._redraw_job = self.root.after(80, self.redraw)

    def _fit(self, ringsets):
        cw = max(100, self.cv.winfo_width())
        ch = max(100, self.cv.winfo_height())
        pts = [p for rs in ringsets for r in rs for p in r]
        minx = min(p[0] for p in pts)
        maxx = max(p[0] for p in pts)
        miny = min(p[1] for p in pts)
        maxy = max(p[1] for p in pts)
        pad = U.h(PAD)
        bottom = 0                             # 범례는 따로 있는 캔버스다
        s = min((cw - 2 * pad) / (maxx - minx), (ch - 2 * pad - bottom) / (maxy - miny))
        ox = (cw - (maxx - minx) * s) / 2 - minx * s
        oy = (ch - bottom - (maxy - miny) * s) / 2 - miny * s
        if self.zoom == 1.0 and self.pan == [0.0, 0.0]:
            return lambda p: (p[0] * s + ox, p[1] * s + oy)
        z, (px, py) = self.zoom, self.pan
        cx, cy = cw / 2.0, (ch - bottom) / 2.0
        return lambda p: ((p[0] * s + ox - cx) * z + cx + px, (p[1] * s + oy - cy) * z + cy + py)

    # ---------------- 확대 / 옮기기 ----------------
    def _on_wheel(self, e, direction=None):
        """휠로 키우고 줄인다.

        **굴리는 순간에는 그려 둔 것을 늘리기만 한다**(canvas.scale). 다 지우고
        새로 그리는 것은 굴리기를 멈춘 뒤 한 번만 한다 - 칸마다 새로 그렸더니
        경기·전남처럼 점이 많은 곳에서 한 칸 굴릴 때마다 멈칫했다. 새로 그릴
        때 이름표가 크기에 맞게 다시 들어간다.

        트랙패드는 작은 값을 잘게 여러 번 보낸다. 한 번에 1.25배씩 키우면
        손가락을 조금만 움직여도 끝까지 가 버린다. 값의 크기만큼만 키운다.
        """
        if not self.map:
            return "break"
        if direction is not None:
            notches = float(direction)
        else:
            try:
                dlt = float(e.delta)
            except (TypeError, ValueError, AttributeError):
                return "break"
            notches = dlt / 120.0 if abs(dlt) >= 30 else dlt
        if not notches:
            return "break"
        notches = max(-3.0, min(3.0, notches))
        old = self.zoom
        new = max(1.0, min(8.0, old * (1.15 ** notches)))
        if new < 1.01:
            new = 1.0                     # 곱셈 오차로 1.0000000002 에 멈추면 '원래 크기' 가 안 된다
        if abs(new - old) < 1e-4:
            return "break"
        cw, ch = self.cv.winfo_width(), self.cv.winfo_height()
        cx, cy = cw / 2.0, ch / 2.0
        # 휠 아래 점이 그 자리에 머물게 pan 을 맞춘다. install_wheel 을 거쳐 오면
        # e.x/e.y 는 창 기준이라 화면 좌표에서 캔버스 좌표로 바꾼다.
        try:
            mx, my = e.x_root - self.cv.winfo_rootx(), e.y_root - self.cv.winfo_rooty()
        except (AttributeError, TypeError):
            mx, my = e.x, e.y
        f = new / old
        self.pan[0] = (mx - cx) - ((mx - cx) - self.pan[0]) * f
        self.pan[1] = (my - cy) - ((my - cy) - self.pan[1]) * f
        self.zoom = new
        want = list(self.pan)
        self._clamp_pan()
        try:
            self.cv.scale("map", mx, my, f, f)
            # 가장자리에 막혀 pan 이 깎였으면 그만큼 되돌려 놓는다
            self.cv.move("map", self.pan[0] - want[0], self.pan[1] - want[1])
        except tk.TclError:
            pass
        if self._redraw_job:
            try:
                self.root.after_cancel(self._redraw_job)
            except Exception:                              # noqa: BLE001
                pass
        self._redraw_job = self.root.after(180, self.redraw)
        return "break"

    def _clamp_pan(self):
        if self.zoom <= 1.0:
            self.pan = [0.0, 0.0]
            return
        cw, ch = self.cv.winfo_width(), self.cv.winfo_height()
        lim_x, lim_y = (self.zoom - 1) * cw / 2.0, (self.zoom - 1) * ch / 2.0
        self.pan = [max(-lim_x, min(lim_x, self.pan[0])), max(-lim_y, min(lim_y, self.pan[1]))]

    def _drag_start(self, e):
        self._drag = (e.x, e.y, list(self.pan))
        self._dragged = False

    def _drag_move(self, e):
        if not self._drag or self.zoom <= 1.0:
            return
        x0, y0, pan0 = self._drag
        if not self._dragged and abs(e.x - x0) + abs(e.y - y0) < 5:
            return
        self._dragged = True
        self.cv.configure(cursor="fleur")
        before = list(self.pan)
        self.pan = [pan0[0] + e.x - x0, pan0[1] + e.y - y0]
        self._clamp_pan()
        # 끄는 동안은 그려 둔 것을 옮기기만 하고, 놓으면 이름표까지 다시 그린다
        self.cv.move("map", self.pan[0] - before[0], self.pan[1] - before[1])

    def _drag_end(self, _e):
        self._drag = None
        if self._dragged:
            self.cv.configure(cursor="")
            self._on_resize()
            # 놓는 순간의 클릭(고르기)은 먹는다. 영역의 클릭은 놓을 때 처리한다.
            self.root.after(1, self._clear_dragged)

    def _clear_dragged(self):
        self._dragged = False

    def _click_region(self, code):
        if not self._dragged:
            self.select(code)

    def _click_sido(self, code):
        if not self._dragged:
            self.enter_sido(code)

    def _reset_view(self):
        self.zoom = 1.0
        self.pan = [0.0, 0.0]

    def redraw(self):
        self._redraw_job = None
        if not self.map or not self.alive:
            return
        cv = self.cv
        cv.delete("all")
        self.items = {}
        if self.sido is None:
            self._draw_nation()
        else:
            self._draw_sido(self.sido)
        self._legend()
        try:
            self.back_btn.configure(state="normal" if self.sido else "disabled")
        except Exception:                                  # noqa: BLE001
            pass

    def _draw_nation(self):
        cv = self.cv
        tf = self._fit([sd["rings"] for sd in self.map["sido"]])
        stats = self._sido_stats()
        # **넓은 곳부터 그린다.** 고리는 바깥선뿐이라 경기도 도형이 서울을 통째로
        # 덮는다. 목록 순서대로 그렸더니 서울 위에 경기가 올라가 서울을 누를 수가 없었다.
        order = sorted(self.map["sido"], key=lambda sd: -sd.get("area", 0))
        for sd in order:
            won, total, lo, hi = stats.get(sd["code"], (0, 0, 0, 0))
            frac = won / float(total or 1)
            fill = shade(CLEAR, 0.35 + 0.65 * frac) if won else "#2a3246"
            tag = "s%s" % sd["code"]
            for ring in sd["rings"]:
                cv.create_polygon([c for p in ring for c in tf(p)], fill=fill, outline="#0b0e14",
                                  width=1, tags=(tag, "region", "map"))
            self.items[tag] = ("sido", sd["code"])
            cv.tag_bind(tag, "<Enter>", lambda _e, c=sd["code"]: self._hover_sido(c, True))
            cv.tag_bind(tag, "<Leave>", lambda _e, c=sd["code"]: self._hover_sido(c, False))
            cv.tag_bind(tag, "<ButtonRelease-1>", lambda _e, c=sd["code"]: self._click_sido(c))
        # 이름표는 도형을 다 그린 뒤에. **좁은 곳부터** 자리를 잡는다 - 서울·세종은
        # 옮길 데가 없지만 경기·충남은 넓어서 비켜 앉을 수 있다. 가운데가 이미
        # 잡혀 있으면 자기 땅 안에서 위·아래·옆으로 옮겨 보고, 끝내 안 되면 뺀다.
        f1 = tkfont.Font(root=cv, family=U.FAMILY, size=U.pt(9), weight="bold")
        f2 = tkfont.Font(root=cv, family=U.FAMILY, size=U.pt(8))
        self._label_fonts = (f1, f2)
        taken = []
        for sd in reversed(order):
            won, total, lo, hi = stats.get(sd["code"], (0, 0, 0, 0))
            label = short_sido(sd["name"])
            sub = "%d/%d" % (won, total)
            c0 = sd.get("center") or sd["rings"][0][0]
            cx0, cy0 = tf(c0)
            r = abs(tf((c0[0] + sd.get("labelR", 0), c0[1]))[0] - cx0)
            w = max(f1.measure(label), f2.measure(sub)) + U.h(4)
            h = f1.metrics("linespace") + f2.metrics("linespace")
            flat_rings = [[v for p in ring for v in tf(p)] for ring in sd["rings"]]
            box = None
            for dx, dy in ((0, 0), (0, -0.7), (0, 0.7), (-0.7, 0), (0.7, 0), (0, -1.4), (0, 1.4)):
                cx, cy = cx0 + dx * max(r, h), cy0 + dy * max(r, h)
                cand = (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0)
                if (dx or dy) and not inside(flat_rings, cx, cy):
                    continue
                if not any(_overlap(cand, q) for q in taken):
                    box = cand
                    break
            if box is None:
                continue
            cx = (box[0] + box[2]) / 2.0
            taken.append(box)
            t1 = cv.create_text(cx, box[1] + f1.metrics("linespace") / 2.0, text=label, fill="#f2f4fb",
                                font=f1, tags=("label", "map"))
            t2 = cv.create_text(cx, box[3] - f2.metrics("linespace") / 2.0, text=sub, fill="#c9cfdf",
                                font=f2, tags=("label", "map"))
            for t in (t1, t2):
                cv.tag_bind(t, "<ButtonRelease-1>", lambda _e, c=sd["code"]: self._click_sido(c))
                cv.tag_bind(t, "<Enter>", lambda _e, c=sd["code"]: self._hover_sido(c, True))

    def _sido_stats(self):
        out = {}
        for d in self.map["sgg"]:
            t = self.by_region.get(d["code"])
            if not t:
                continue
            won, total, lo, hi = out.get(d["sido"], (0, 0, 999, 0))
            out[d["sido"]] = (won + (1 if t["cleared"] else 0), total + 1,
                              min(lo, t["level"]), max(hi, t["level"]))
        return out

    def _draw_sido(self, code):
        cv = self.cv
        # 넓은 곳부터 (완주군이 전주시를 감싸는 것처럼 둘러싼 곳이 작은 곳을 덮지 않게)
        regs = sorted((d for d in self.map["sgg"] if d["sido"] == code), key=lambda d: -d.get("area", 0))
        if code not in self._layouts:
            self._layouts[code] = island_layout(regs)
        shifts, boxes, hidden = self._layouts[code]
        moved = {d["code"]: [[(p[0] + shifts.get((d["code"], i), (0, 0))[0],
                               p[1] + shifts.get((d["code"], i), (0, 0))[1]) for p in ring]
                              for i, ring in enumerate(d["rings"]) if (d["code"], i) not in hidden]
                 for d in regs}
        box_pts = [[(b[0], b[1]), (b[2], b[3])] for b in boxes]
        tf = self._fit(list(moved.values()) + [box_pts])
        flat = {c: [[v for p in ring for v in tf(p)] for ring in rings] for c, rings in moved.items()}
        for b in boxes:
            # 멀리 떨어진 섬은 가까이 당겨 그렸다. 원래 자리가 아니라는 표시.
            (x0, y0), (x1, y1) = tf((b[0], b[1])), tf((b[2], b[3]))
            cv.create_rectangle(x0, y0, x1, y1, outline="#4a5475", dash=(4, 3), tags=("map",))
        for d in regs:
            t = self.by_region.get(d["code"]) or {}
            lv = t.get("level", 20)
            fill = level_color(lv)
            tag = "g%s" % d["code"]
            sel = d["code"] == self.selected
            for ring in flat[d["code"]]:
                cv.create_polygon(ring, fill=fill,
                                  outline=CLEAR if t.get("cleared") else "#0b0e14",
                                  width=3 if t.get("cleared") else 1, tags=(tag, "region", "map"))
            self.items[tag] = ("sgg", d["code"])
            cv.tag_bind(tag, "<Enter>", lambda _e, c=d["code"]: self._hover_sgg(c, True))
            cv.tag_bind(tag, "<Leave>", lambda _e, c=d["code"]: self._hover_sgg(c, False))
            cv.tag_bind(tag, "<ButtonRelease-1>", lambda _e, c=d["code"]: self._click_region(c))
            if sel:
                cv.itemconfigure(tag, outline="#ffffff", width=3)
        if self.selected:
            cv.tag_raise("g%s" % self.selected)
            self._restack("g%s" % self.selected)
        f_name = tkfont.Font(root=cv, family=U.FAMILY, size=U.pt(8), weight="bold")
        f_lv = tkfont.Font(root=cv, family=U.FAMILY, size=U.pt(7))
        for d in regs:
            t = self.by_region.get(d["code"]) or {}
            sx, sy = shifts.get((d["code"], ring_of(d, d["center"])), (0, 0))
            cx, cy = tf((d["center"][0] + sx, d["center"][1] + sy))
            rings = flat[d["code"]]
            name = map_label(d["name"])
            lv_text = "Lv.%d" % t.get("level", 0)
            nh, lh = f_name.metrics("linespace"), f_lv.metrics("linespace")
            ck = U.h(16) + U.h(2) if t.get("cleared") else 0
            # 넣어 볼 순서: 이름+레벨 -> 이름만 -> (이긴 곳이면) 체크만
            tries = [((name, lv_text), max(f_name.measure(name), f_lv.measure(lv_text)), nh + lh),
                     ((name,), f_name.measure(name), nh)]
            shown = ()
            top = cy
            for texts, bw, bh in tries:
                total = bh + ck
                if box_inside(rings, cx, cy, bw + U.h(6), total + U.h(2)):
                    shown, top = texts, cy - total / 2.0
                    break
            items = []
            if t.get("cleared"):
                r = U.h(8)
                oy = top + r if shown else cy
                items.append(cv.create_oval(cx - r, oy - r, cx + r, oy + r, fill=CLEAR,
                                            outline="#10131b", tags=("label", "map")))
                items.append(cv.create_text(cx, oy, text="✓", fill="#10131b",
                                            font=(U.FAMILY, U.pt(8), "bold"), tags=("label", "map")))
                top += ck
            if shown:
                items.append(cv.create_text(cx, top + nh / 2.0, text=shown[0], fill="#10131b",
                                            font=f_name, tags=("label", "map")))
            if len(shown) > 1:
                items.append(cv.create_text(cx, top + nh + lh / 2.0, text=shown[1], fill="#10131b",
                                            font=f_lv, tags=("label", "map")))
            for x in items:
                cv.tag_bind(x, "<ButtonRelease-1>", lambda _e, c=d["code"]: self._click_region(c))
        self._label_fonts = (f_name, f_lv)

    def _legend(self):
        cv = self.legend_cv
        cv.delete("all")
        x0, y0 = U.h(16), U.h(18)
        if self.sido is None:
            cv.create_text(x0, y0, anchor="w", fill=U.FG_DIM, font=U.FONT_XS,
                           text="시·도를 누르면 그 안의 시·군·구로 들어갑니다   (금색 = 이긴 곳이 많을수록 진하게)")
            self._zoom_hint()
            return
        cv.create_text(x0, y0, anchor="w", fill=U.FG_DIM, font=U.FONT_XS, text="트레이너 레벨")
        bx = x0 + U.h(92)
        for i, lv in enumerate(range(20, 101, 5)):
            cv.create_rectangle(bx + i * U.h(14), y0 - U.h(6), bx + (i + 1) * U.h(14), y0 + U.h(6),
                                fill=level_color(lv), outline="")
        for lv in (20, 60, 100):
            i = (lv - 20) // 5
            cv.create_text(bx + i * U.h(14) + U.h(7), y0 + U.h(16), text=str(lv),
                           fill=U.FG_FAINT, font=U.FONT_XS)
        ex = bx + 17 * U.h(14) + U.h(24)
        cv.create_rectangle(ex, y0 - U.h(7), ex + U.h(22), y0 + U.h(7), fill="#3a4258",
                            outline=CLEAR, width=3)
        cv.create_text(ex + U.h(30), y0, anchor="w", fill=U.FG_DIM, font=U.FONT_XS, text="이긴 곳")
        self._zoom_hint()

    def _zoom_hint(self):
        """오른쪽 위: 확대 안내, 키웠으면 배율과 '원래 크기'."""
        cv = self.cv
        x, y = cv.winfo_width() - U.h(12), U.h(16)
        cv.delete("hint")
        if self.zoom <= 1.0:
            t0 = cv.create_text(x, y, anchor="e", fill=U.FG_FAINT, font=U.FONT_XS, text="휠로 확대", tags=("hint",))
            x0, y0, _, y1 = cv.bbox(t0)
            bg = cv.create_rectangle(x0 - U.h(6), y0 - U.h(3), x + U.h(4), y1 + U.h(3), fill="#0f141d",
                                     outline="", tags=("hint",))
            cv.tag_lower(bg, t0)
            return
        rid = cv.create_text(x, y, anchor="e", fill=U.ACCENT, font=U.FONT_XS, text="원래 크기",
                             tags=("reset", "hint"))
        tid = cv.create_text(cv.bbox(rid)[0] - U.h(10), y, anchor="e", fill=U.FG_DIM, font=U.FONT_XS,
                             text="×%.1f · 끌어서 옮기기" % self.zoom, tags=("hint",))
        x0, y0, _, y1 = cv.bbox(tid)
        bg = cv.create_rectangle(x0 - U.h(8), y0 - U.h(4), x + U.h(6), y1 + U.h(4), fill="#0f141d",
                                 outline="#2c3650", tags=("hint",))
        cv.tag_lower(bg, rid)
        cv.tag_bind(rid, "<Button-1>", lambda _e: (self._reset_view(), self.redraw()))
        cv.tag_bind(rid, "<Enter>", lambda _e: cv.configure(cursor="hand2"))
        cv.tag_bind(rid, "<Leave>", lambda _e: cv.configure(cursor=""))

    # ---------------- 올리기 / 누르기 ----------------
    def _hover_sido(self, code, on):
        tag = "s%s" % code
        try:
            self.cv.itemconfigure(tag, outline="#ffffff" if on else "#0b0e14", width=2 if on else 1)
            if on:
                self.cv.tag_raise(tag)
                self._restack(tag)
        except tk.TclError:
            return
        if on:
            won, total, lo, hi = self._sido_stats().get(code, (0, 0, 0, 0))
            self.say("%s — %d곳 · Lv.%d~%d · 이긴 곳 %d" % (self.sido_names.get(code, ""),
                                                        total, lo, hi, won))

    def _hover_sgg(self, code, on):
        tag = "g%s" % code
        t = self.by_region.get(code) or {}
        sel = code == self.selected
        try:
            if on:
                self.cv.itemconfigure(tag, outline="#ffffff", width=3)
                self.cv.tag_raise(tag)
                self._restack(tag)
            else:
                self.cv.itemconfigure(tag, outline="#ffffff" if sel else (CLEAR if t.get("cleared") else "#0b0e14"),
                                      width=3 if (sel or t.get("cleared")) else 1)
        except tk.TclError:
            return
        if on:
            d = next((x for x in self.map["sgg"] if x["code"] == code), {})
            self.say("%s %s — %s (%s) Lv.%d%s" % (short_sido(d.get("sidonm", "")), sgg_name(d.get("name", "")),
                                                  t.get("name", ""), t.get("role", ""), t.get("level", 0),
                                                  "  ✓ 이긴 곳" if t.get("cleared") else ""))

    def _restack(self, raised):
        """올린 곳보다 **좁은 곳**을 다시 그 위로 올린다.

        테두리를 보이려고 올린 경기도가 서울을 다시 덮으면 서울을 못 누른다.
        """
        cv = self.cv
        if self.sido is None:
            rows = [("s%s" % sd["code"], sd.get("area", 0)) for sd in self.map["sido"]]
        else:
            rows = [("g%s" % d["code"], d.get("area", 0)) for d in self.map["sgg"] if d["sido"] == self.sido]
        area = dict(rows).get(raised, 0)
        for tag, a in sorted(rows, key=lambda r: -r[1]):
            if a < area:
                cv.tag_raise(tag)
        cv.tag_raise("label")
        cv.tag_raise("hint")

    def enter_sido(self, code):
        self.sido = code
        self.selected = None
        self._reset_view()
        self.redraw()
        self._summary()

    def to_nation(self):
        self.sido = None
        self.selected = None
        self._reset_view()
        self.redraw()
        self._summary()

    # ---------------- 오른쪽 ----------------
    def _crumbs(self, parts):
        for w in self.crumb.winfo_children():
            w.destroy()
        for i, (text, cb) in enumerate(parts):
            if i:
                tk.Label(self.crumb, text="›", bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_S).pack(side="left", padx=4)
            lab = tk.Label(self.crumb, text=text, bg=U.BG2, fg=U.ACCENT if cb else U.FG,
                           font=U.FONT_S, cursor="hand2" if cb else "")
            lab.pack(side="left")
            if cb:
                lab.bind("<Button-1>", lambda _e, f=cb: f())

    def _clear_card(self):
        for box in (self.card, self.action):
            for w in box.winfo_children():
                w.destroy()
        try:
            self.card_cv.yview_moveto(0)
        except tk.TclError:
            pass

    def _summary(self):
        """고른 곳이 없을 때 오른쪽에 보여 줄 요약."""
        self._clear_card()
        if not self.data:
            return
        if self.sido is None:
            self._crumbs([("대한민국", None)])
            tk.Label(self.card, text="대한민국", bg=U.BG2, fg=U.FG,
                     font=(U.FAMILY_BLACK, U.pt(16))).pack(anchor="w", pady=(6, 2))
            tk.Label(self.card, text="시·군·구 256곳마다 트레이너가 기다립니다.\n"
                                     "관장·사천왕·챔피언에 라이벌과 악의 조직까지.",
                     bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, justify="left").pack(anchor="w")
            regions = self.data["regions"]
        else:
            name = self.sido_names.get(self.sido, "")
            self._crumbs([("대한민국", self.to_nation), (short_sido(name), None)])
            tk.Label(self.card, text=name, bg=U.BG2, fg=U.FG,
                     font=(U.FAMILY_BLACK, U.pt(16)), wraplength=U.h(SIDE_W - 40),
                     justify="left").pack(anchor="w", pady=(6, 2))
            codes = {d["code"] for d in self.map["sgg"] if d["sido"] == self.sido}
            regions = [r for r in self.data["regions"] if r["region"] in codes]
            tk.Label(self.card, text="지도에서 시·군·구를 누르면 트레이너가 나옵니다.",
                     bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S).pack(anchor="w")
        won = sum(1 for r in regions if r["cleared"])
        box = U.framed(self.card, bg=U.BG3, border=U.LINE)
        box.pack(fill="x", pady=(14, 0))
        inner = tk.Frame(box, bg=U.BG3)
        inner.pack(fill="x", padx=12, pady=10)
        for k, v in (("지역", "%d곳" % len(regions)), ("이긴 곳", "%d곳" % won),
                     ("레벨", "Lv.%d ~ %d" % (min(r["level"] for r in regions),
                                             max(r["level"] for r in regions)))):
            row = tk.Frame(inner, bg=U.BG3)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=k, bg=U.BG3, fg=U.FG_DIM, font=U.FONT_S).pack(side="left")
            tk.Label(row, text=v, bg=U.BG3, fg=U.FG, font=U.FONT_B).pack(side="right")
        if self.sido is None:
            self._sido_buttons()

    def _sido_buttons(self):
        """시·도 열여섯 곳 바로 가기. 세종·대전·서울은 전국 지도에서 손톱만 하다."""
        U.marker_label(self.card, "시·도 바로 가기", bg=U.BG2).pack(anchor="w", pady=(16, 6))
        grid = tk.Frame(self.card, bg=U.BG2)
        grid.pack(fill="x")
        stats = self._sido_stats()
        order = sorted(self.map["sido"], key=lambda sd: sd["code"])
        for i, sd in enumerate(order):
            won, total, _lo, _hi = stats.get(sd["code"], (0, 0, 0, 0))
            done = total and won == total
            bg = shade(CLEAR, 0.45) if done else U.BG3
            cell = tk.Frame(grid, bg=bg, cursor="hand2", highlightthickness=1, highlightbackground=U.LINE)
            cell.grid(row=i // 4, column=i % 4, sticky="nsew", padx=2, pady=2)
            name = tk.Label(cell, text=short_sido(sd["name"]), bg=bg, fg=U.FG, font=U.FONT_S, cursor="hand2")
            name.pack(pady=(3, 0))
            cnt = tk.Label(cell, text="%d/%d" % (won, total), bg=bg, fg=U.FG_DIM if not done else U.FG,
                           font=U.FONT_XS, cursor="hand2")
            cnt.pack(pady=(0, 3))
            for w in (cell, name, cnt):
                w.bind("<Button-1>", lambda _e, c=sd["code"]: self.enter_sido(c))
                w.bind("<Enter>", lambda _e, ws=(cell, name, cnt): [x.configure(bg=U.BG4) for x in ws])
                w.bind("<Leave>", lambda _e, ws=(cell, name, cnt), b=bg: [x.configure(bg=b) for x in ws])
        for c in range(4):
            grid.grid_columnconfigure(c, weight=1, uniform="sido")

    def jump(self, code):
        d = next((x for x in self.map["sgg"] if x["code"] == code), None)
        if not d:
            return
        if self.sido != d["sido"]:
            self._reset_view()
        self.sido = d["sido"]
        self.selected = code
        self.redraw()
        self.select(code)

    def select(self, code):
        self.selected = code
        d = next((x for x in self.map["sgg"] if x["code"] == code), {})
        if self.sido != d.get("sido"):
            self._reset_view()
            self.sido = d.get("sido")
        self.redraw()
        self._crumbs([("대한민국", self.to_nation),
                      (short_sido(d.get("sidonm", "")), lambda s=d.get("sido"): self.enter_sido(s)),
                      (sgg_name(d.get("name", "")), None)])
        self._clear_card()
        tk.Label(self.card, text="트레이너를 불러오는 중...", bg=U.BG2, fg=U.FG_DIM,
                 font=U.FONT_S).pack(anchor="w", pady=10)

        def work():
            t = self.app.api.gym_trainer(code)
            img = trainer_photo(self.app.api, t["sprite"])
            thumbs = {}
            for m in t["team"]:
                try:
                    thumbs[m["num"]] = mon_thumb(self.app.api, m["num"], 28)
                except Exception:                          # noqa: BLE001
                    thumbs[m["num"]] = None
            return t, img, thumbs

        def done(r, err):
            if not self.alive or self.selected != code:
                return
            if err:
                self._clear_card()
                return self.say("불러오지 못했습니다. %s" % getattr(err, "message", err), U.RED)
            self._trainer_card(code, *r)

        run_async(self.root, work, done)

    def _trainer_card(self, code, t, img, thumbs):
        self._clear_card()
        top = tk.Frame(self.card, bg=U.BG2)
        top.pack(fill="x", pady=(4, 0))
        if img is not None:
            ph = ImageTk.PhotoImage(img)
            self.photos["trainer"] = ph
            tk.Label(top, image=ph, bg=U.BG2).pack(side="left")
        info = tk.Frame(top, bg=U.BG2)
        info.pack(side="left", fill="both", expand=True, padx=(10, 0))
        tk.Label(info, text=t["role"], bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w").pack(anchor="w")
        tk.Label(info, text=t["name"], bg=U.BG2, fg=U.FG, font=(U.FAMILY_BLACK, U.pt(17)),
                 anchor="w").pack(anchor="w")
        tk.Label(info, text=" Lv.%d " % t["level"], bg=level_color(t["level"]), fg="#10131b",
                 font=U.FONT_B).pack(anchor="w", pady=(4, 0))
        if t.get("typeKr"):
            tk.Label(info, text="%s 타입을 주로 쓴다" % t["typeKr"], bg=U.BG2, fg=U.FG_FAINT,
                     font=U.FONT_XS).pack(anchor="w", pady=(4, 0))
        # 이긴 기록과 상금은 도트 옆 빈칸에 둔다. 아래에 두 줄을 더 쌓으면
        # 창 높이 700 에서 에이스 줄이 굴려야 보이는 자리로 밀려났다.
        state = ("✓ 이긴 곳 · %d번 이김%s" % (t["wins"], (" · 최소 %d턴" % t["bestTurns"]) if t.get("bestTurns") else "")
                 if t["cleared"] else "아직 이기지 못했다")
        st = tk.Label(info, text=state, bg=U.BG2, fg=U.GOOD if t["cleared"] else U.FG_DIM,
                      font=U.FONT_S, anchor="w", justify="left")
        st.pack(fill="x", pady=(8, 0))
        U.wrap_to_width(st)
        prize = ("다시 이기면 하루 한 번 %s원" if t["cleared"] else "처음 이기면 상금 %s원") % format(t["prize"], ",")
        pz = tk.Label(info, text=prize, bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w", justify="left")
        pz.pack(fill="x")
        U.wrap_to_width(pz)
        if t.get("why"):
            why = tk.Label(self.card, text=t["why"], bg=U.BG2, fg=U.ACCENT, font=U.FONT_S,
                           justify="left", anchor="w")
            why.pack(fill="x", pady=(8, 0))
            U.wrap_to_width(why)

        U.marker_label(self.card, "데리고 있는 포켓몬", bg=U.BG2).pack(anchor="w", pady=(12, 4))
        team = tk.Frame(self.card, bg=U.BG2)
        team.pack(fill="x")
        for i, m in enumerate(t["team"]):
            row = tk.Frame(team, bg=U.BG3 if i == len(t["team"]) - 1 else U.BG2, height=U.h(30))
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            bg = row["bg"]
            slot = tk.Frame(row, bg=bg, width=U.h(34), height=U.h(30))
            slot.pack(side="left")
            slot.pack_propagate(False)
            th = thumbs.get(m["num"])
            if th is not None:
                ph = ImageTk.PhotoImage(th)
                self.photos["t%d" % i] = ph
                tk.Label(slot, image=ph, bg=bg).pack(expand=True)
            tk.Label(row, text=m["kr"] or m["species"], bg=bg, fg=U.FG, font=U.FONT_B,
                     anchor="w").pack(side="left", padx=(6, 0))
            if i == len(t["team"]) - 1:
                tk.Label(row, text="에이스", bg=bg, fg=U.ACCENT, font=U.FONT_XS).pack(side="left", padx=6)
            tk.Label(row, text="Lv.%d" % m["level"], bg=bg, fg=U.FG_DIM, font=U.FONT_S).pack(side="right", padx=8)
            tk.Label(row, text="/".join(m.get("types") or []), bg=bg, fg=U.FG_FAINT,
                     font=U.FONT_XS).pack(side="right")

        act = (self.data or {}).get("active")
        btn_row = tk.Frame(self.action, bg=U.BG2)
        btn_row.pack(fill="x", pady=(8, 0))
        if act and act["region"] == code:
            label = "승부 이어하기"
        elif act:
            label = "다른 승부가 진행 중"
        else:
            label = "도전하기"
        self.go_btn = U.PushButton(btn_row, label, lambda: self.challenge(code), height=40)
        self.go_btn.pack(fill="x")
        if act and act["region"] != code:
            self.go_btn.configure(state="disabled")
            other = self.by_region.get(act["region"], {})
            tk.Label(btn_row, text="%s 과(와)의 승부를 먼저 끝내세요." % other.get("name", ""),
                     bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_XS).pack(anchor="w", pady=(4, 0))

    # ---------------- 도전 ----------------
    def challenge(self, code):
        if self.battle and self.battle.alive:
            return self.battle.focus()
        try:
            self.go_btn.configure(state="disabled")
        except Exception:                                  # noqa: BLE001
            pass
        self.say("승부를 준비하는 중...")

        def done(r, err):
            if not self.alive:
                return
            if err:
                try:
                    self.go_btn.configure(state="normal")
                except Exception:                          # noqa: BLE001
                    pass
                return self.say(getattr(err, "message", str(err)), U.RED)
            from .ui_gym_battle import GymBattleWindow
            self.battle = GymBattleWindow(self.app, r, on_close=self._battle_closed)
            self.say("")

        run_async(self.root, lambda: self.app.api.gym_start(code), done)

    def _battle_closed(self):
        self.battle = None
        if self.alive:
            self.reload()

    def close(self):
        self.alive = False
        try:
            self.win.destroy()
        except Exception:                                  # noqa: BLE001
            pass


def short_sido(name):
    table = {"서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
             "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기",
             "강원특별자치도": "강원", "충청북도": "충북", "충청남도": "충남", "경상북도": "경북",
             "경상남도": "경남", "제주특별자치도": "제주", "전북특별자치도": "전북",
             "전남광주통합특별시": "전남광주"}
    return table.get(name, name)


def sgg_name(name):
    """수원시팔달구 -> 수원시 팔달구. 일반구는 원자료에 띄어쓰기가 없다."""
    i = name.find("시")
    if name.endswith("구") and 0 < i < len(name) - 2:
        return name[:i + 1] + " " + name[i + 1:]
    return name


def map_label(name):
    """지도 위에 쓸 짧은 이름. 수원시팔달구 -> 팔달구 (시 이름은 칸이 좁아 뺀다)."""
    i = name.find("시")
    if name.endswith("구") and 0 < i < len(name) - 2:
        return name[i + 1:]
    return name


def island_layout(regs):
    """멀리 떨어진 섬 무리를 가까이 당겨 그릴 자리.

    ({(시군구 코드, 고리 번호): (dx, dy)}, [상자 (x0, y0, x1, y1)], {안 그릴 고리}) - 지도 좌표.

    그대로 맞추면 본토가 작아진다. 경북은 울릉군 하나 때문에 폭이 두 배가
    되고, 인천은 백령도가 서북쪽 끝에 있어 도심 구 여덟 곳이 손톱만 해졌다.
    지도책처럼 먼 섬은 본토 테두리 안의 **빈 바다**로 옮기고 점선 상자를
    두른다. 빈 곳이 없으면 본토 바로 바깥, 원래 있던 쪽에 붙인다.

      1. 고리(섬 하나)끼리 가까우면(전체 크기의 2%) 한 무리 - 가장 넓은 무리가 본토
      2. 나머지를 5% 간격으로 다시 묶는다 - 백령·대청·소청이 한 상자에 들어가게
      3. 본토 테두리에서 본토 크기의 12% 넘게 떨어진 무리만 옮긴다
      4. 본토(와 가까운 섬)를 작은 그림으로 칠해, 겹치지 않는 자리 중
         원래 자리에 가장 가까운 곳을 고른다

    지금 자료에서 걸리는 곳: 인천(백령도·연평도), 전남(흑산도 쪽), 경북(울릉군),
    제주(추자도), 전북(어청도·위도). 한 번 계산해 시·도마다 남겨 둔다.
    """
    rings = []
    for d in regs:
        for i, r in enumerate(d["rings"]):
            if len(r) >= 3:
                rings.append({"key": (d["code"], i), "b": _bbox(r), "a": _area(r), "pts": r})
    if len(rings) < 2:
        return {}, [], set()
    allb = rings[0]["b"]
    for r in rings:
        allb = _union(allb, r["b"])
    size = max(allb[2] - allb[0], allb[3] - allb[1])
    groups = _clusters(rings, 0.02 * size)
    core = max(groups, key=lambda g: g["a"])
    cb = core["b"]
    cs = max(cb[2] - cb[0], cb[3] - cb[1])
    others = [rings[i] for g in groups if g is not core for i in g["idx"]]
    far = [g for g in _clusters(others, 0.05 * size) if _gap(g["b"], cb) > 0.12 * cs] if others else []
    # 너무 작아 상자 안에 점 하나로 보일 섬(전북 어청도, 신안 끝의 바위섬)은
    # 상자를 달면 빈 상자로 보인다. 그리지 않는다 - 그 시·군·구는 본섬으로 누른다.
    hidden = set()
    for g in [g for g in far if max(g["b"][2] - g["b"][0], g["b"][3] - g["b"][1]) < 0.025 * cs]:
        hidden.update(others[i]["key"] for i in g["idx"])
        far.remove(g)
    if not far:
        return {}, [], hidden
    far_keys = {others[i]["key"] for g in far for i in g["idx"]} | hidden
    nb = list(cb)
    for r in rings:
        if r["key"] not in far_keys:
            nb = _union(nb, r["b"])
    ncx, ncy = (nb[0] + nb[2]) / 2.0, (nb[1] + nb[3]) / 2.0
    nw, nh = nb[2] - nb[0], nb[3] - nb[1]
    k = 400.0 / max(nw, nh)
    gw, gh = int(nw * k) + 3, int(nh * k) + 3
    occ = Image.new("L", (gw, gh), 0)
    draw = ImageDraw.Draw(occ)
    for r in rings:
        if r["key"] not in far_keys:
            draw.polygon([((p[0] - nb[0]) * k, (p[1] - nb[1]) * k) for p in r["pts"]], fill=255)
    pad = 0.03 * cs
    shifts, boxes = {}, []
    for g in sorted(far, key=lambda g: -g["a"]):
        b = g["b"]
        w, h = b[2] - b[0], b[3] - b[1]
        ox, oy = (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0
        # 안쪽 빈 바다라도 **원래 있던 쪽**이어야 한다. 가장 가까운 빈 곳만 보면
        # 동해의 울릉군이 경북 서북쪽 구석에 들어갔다.
        want_x = 1 if ox > ncx + 0.2 * nw else (-1 if ox < ncx - 0.2 * nw else 0)
        want_y = 1 if oy > ncy + 0.2 * nh else (-1 if oy < ncy - 0.2 * nh else 0)
        best = None
        steps = 20
        for i in range(steps + 1):
            for j in range(steps + 1):
                x = nb[0] + pad + w / 2 + i / float(steps) * max(0.0, nw - 2 * pad - w)
                y = nb[1] + pad + h / 2 + j / float(steps) * max(0.0, nh - 2 * pad - h)
                if (want_x and (x - ncx) * want_x <= 0) or (want_y and (y - ncy) * want_y <= 0):
                    continue
                bx = (x - w / 2 - pad, y - h / 2 - pad, x + w / 2 + pad, y + h / 2 + pad)
                if any(_overlap(bx, q) for q in boxes):
                    continue
                px = (int((bx[0] - nb[0]) * k), int((bx[1] - nb[1]) * k),
                      int(math.ceil((bx[2] - nb[0]) * k)), int(math.ceil((bx[3] - nb[1]) * k)))
                if px[0] < 0 or px[1] < 0 or px[2] > gw or px[3] > gh:
                    continue
                if occ.crop(px).getbbox() is not None:
                    continue
                dist = (x - ox) ** 2 + (y - oy) ** 2
                if best is None or dist < best[0]:
                    best = (dist, x, y, bx)
        if best is None:
            gap = 2 * pad
            for _ in range(80):
                dx = (nb[2] + gap) - b[0] if b[0] > nb[2] else ((nb[0] - gap) - b[2] if b[2] < nb[0] else 0.0)
                dy = (nb[3] + gap) - b[1] if b[1] > nb[3] else ((nb[1] - gap) - b[3] if b[3] < nb[1] else 0.0)
                bx = (b[0] + dx - pad, b[1] + dy - pad, b[2] + dx + pad, b[3] + dy + pad)
                if not any(_overlap(bx, q) for q in boxes):
                    break
                gap += pad
            best = (0, ox + dx, oy + dy, bx)
        _, x, y, bx = best
        boxes.append(bx)
        for i in g["idx"]:
            shifts[others[i]["key"]] = (x - ox, y - oy)
    return shifts, boxes, hidden


def ring_of(d, pt):
    """이 점이 든 고리 번호 (이름표를 섬과 같이 옮기려고). 없으면 0."""
    for i, r in enumerate(d["rings"]):
        if inside([[v for p in r for v in p]], pt[0], pt[1]):
            return i
    return 0


def _bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _union(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _gap(a, b):
    return max(0.0, a[0] - b[2], b[0] - a[2], a[1] - b[3], b[1] - a[3])


def _overlap(a, b):
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def _area(pts):
    return abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))) / 2.0


def _clusters(items, t):
    """상자 사이가 t 이하면 한 무리. [{idx, b, a}]"""
    parent = list(range(len(items)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    order = sorted(range(len(items)), key=lambda i: items[i]["b"][0])
    for n, i in enumerate(order):
        for j in order[n + 1:]:
            if items[j]["b"][0] - items[i]["b"][2] > t:
                break
            if _gap(items[i]["b"], items[j]["b"]) <= t:
                parent[root(i)] = root(j)
    out = {}
    for i in range(len(items)):
        g = out.setdefault(root(i), {"idx": [], "b": items[i]["b"], "a": 0.0})
        g["idx"].append(i)
        g["b"] = _union(g["b"], items[i]["b"])
        g["a"] += items[i]["a"]
    return list(out.values())


def inside(rings, x, y):
    """점이 여러 고리 중 하나라도 안에 있나. 고리는 [x0, y0, x1, y1, ...]."""
    for ring in rings:
        n = len(ring) // 2
        hit = False
        j = n - 1
        for i in range(n):
            xi, yi = ring[2 * i], ring[2 * i + 1]
            xj, yj = ring[2 * j], ring[2 * j + 1]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi:
                hit = not hit
            j = i
        if hit:
            return True
    return False


def box_inside(rings, cx, cy, w, h):
    """가운데가 (cx, cy) 인 w x h 상자가 도형 안에 들어가나.

    모서리와 변의 가운데·사분점을 찍어 본다. 가늘고 긴 곳(울진군)에서
    글자가 이웃 칸을 덮는지 보려는 것이라 이 정도면 충분하다.
    """
    hw, hh = w / 2.0, h / 2.0
    for fx in (-1, -0.5, 0, 0.5, 1):
        for fy in (-1, 0, 1):
            if not inside(rings, cx + fx * hw, cy + fy * hh):
                return False
    return True
