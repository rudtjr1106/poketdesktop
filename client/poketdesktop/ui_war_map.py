# -*- coding: utf-8 -*-
"""길드전 지도 (시즌 4) — **원형 지도**의 칸을 주인 길드의 색으로 칠한 캔버스.

고리 모양 판을 길드마다 같은 부채꼴 15칸으로 나눈 것이다 (서버 guild_war.layout). 도형(geo)은 서버가
`/api/guild/war/map` 에 실어 준다 (ring_geo - 칸마다 부채꼴 한 개, 판의 크기 box, 부채꼴 바깥에 적을 길드
이름 labels). 누가 어느 칸을 가졌는지도 같은 응답이다 (ui_guild_war 가 받아서 넘긴다).

  · 칸 도형은 테두리를 칠과 같은 색으로 그리고, 칸과 칸 사이의 경계와 바깥 둘레를 선으로 따로 긋는다
    (_borders) - 길드끼리 맞닿은 곳은 굵게, 우리 길드의 둘레는 흰색으로.
  · 칸을 **한 번만 그리고**, 주인이 바뀌면 그 칸의 색과 둘레의 선만 고친다 (recolor).
  · 휠로 키우고 끌어서 옮긴다 (canvas.scale - 관장 지도와 같은 방식).
  · 내가 지키는 칸에는 흰 점, 우리 길드가 승수를 쌓은 칸에는 '2/3', 넘어간 칸에는 '점령' 을 적는다.
"""
import tkinter as tk
import tkinter.font as tkfont

from . import skins
from . import ui_common as U

SEA = "#0f141d"
BLANK = "#262d3d"            # 주인이 없는 칸 (지도를 받기 전)
LINE = "#0b0e14"
MINE_LINE = "#f2f4fb"        # 우리 길드의 둘레
PICK_LINE = "#ffffff"
PAD = 10
WEIGHT_FLOOR = 250.0         # 칸의 한가운데를 셀 때 시·군·구 넓이의 바닥값 (서버와 같다)
# 길드마다의 색. 서버가 준 색 번호(신청한 차례)로 고른다 - 전쟁 내내 안 바뀐다.
PALETTE = ("#e5484d", "#3e8ed0", "#46a758", "#f5a524", "#9b6cd6", "#22b8cf", "#e879a6", "#8fbf3f",
           "#d9703f", "#5b6ee1", "#2fa98c", "#c2a04a", "#b0607a", "#6fa8dc", "#a1887f", "#7f8ea3")



def color_of(index):
    """색 번호 -> 색. 길드가 색 수보다 많으면 돌려 쓴다."""
    try:
        return PALETTE[int(index) % len(PALETTE)]
    except (TypeError, ValueError):
        return BLANK


def lighten(hexcolor, k=0.35):
    """흰색 쪽으로 k 만큼 (고른 칸)."""
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(int(v + (255 - v) * k) for v in (r, g, b))


def _edge_key(a, b):
    p = (round(a[0], 4), round(a[1], 4))
    q = (round(b[0], 4), round(b[1], 4))
    return (p, q) if p <= q else (q, p)


@skins.skinnable
class WarMap(object):
    """parent 안에 지도를 그린다. on_pick(칸) 은 칸을 눌렀을 때, on_hover(칸 또는 None) 는 올렸을 때."""

    def __init__(self, parent, on_pick=None, on_hover=None):
        self.root = parent.winfo_toplevel()
        self.on_pick = on_pick
        self.on_hover = on_hover
        self.geo = None
        self.cells = {}              # 칸 -> {"codes", "g", "name", "me", "ai", "taken", "wins"}
        self.cell_of = {}            # 시·군·구 -> 칸
        self.colors = {}             # 길드 -> 색
        self.my_gid = None
        self.need = 3
        self.selected = None
        self.zoom = 1.0
        self.pan = [0.0, 0.0]
        self.items = {}              # 칸 -> 그 칸의 도형 번호들
        self.runs = []               # (선 번호, 칸 a, 칸 b 또는 None=바닷가)
        self._look = {}              # 칸 -> 지금 칠해 둔 색
        self._line_look = {}         # 선 번호 -> (색, 굵기)
        self._order = []
        self._box = None
        self._shape = None           # 칸 나눔이 그대로면 선을 다시 셈하지 않는다
        self._drag = None
        self._dragged = False
        self._job = None
        self._size = None
        self.cv = tk.Canvas(parent, bg=SEA, highlightthickness=0)
        cv = self.cv
        cv.bind("<Configure>", self._on_resize)
        cv.bind("<MouseWheel>", self._on_wheel)
        cv.wheel_handler = self._on_wheel      # 창에 건 install_wheel 이 포인터 밑을 찾아 불러 준다
        cv.bind("<Button-4>", lambda e: self._on_wheel(e, 1))
        cv.bind("<Button-5>", lambda e: self._on_wheel(e, -1))
        cv.bind("<ButtonPress-1>", self._drag_start, add="+")
        cv.bind("<B1-Motion>", self._drag_move, add="+")
        cv.bind("<ButtonRelease-1>", self._drag_end, add="+")
        # 칸마다 따로 걸지 않는다. 'region' 이름표 하나에 걸고, 포인터 밑의 도형으로 칸을 찾는다.
        cv.tag_bind("region", "<Enter>", lambda _e: self._hover(self._under()))
        cv.tag_bind("region", "<Leave>", lambda _e: self._hover(None))
        cv.tag_bind("region", "<ButtonRelease-1>", self._click)
        self.font = tkfont.Font(root=cv, family=U.FAMILY, size=U.pt(8), weight="bold")
        self.label_font = tkfont.Font(root=cv, family=U.FAMILY, size=U.pt(9), weight="bold")

    # ---------------- 자료 ----------------
    def set_geo(self, geo):
        if geo is self.geo:
            return
        self.geo = geo
        # 넓은 곳부터 그린다 - 고리는 바깥선뿐이라, 넓은 곳을 나중에 그리면 안에 든 작은 곳을 덮는다
        self._order = sorted(geo.get("sgg") or [], key=lambda g: -float(g.get("area") or 0))
        pts = [p for g in self._order for r in g["rings"] for p in r]
        self._box = (tuple(geo["box"]) if geo.get("box") else       # 판 바깥의 길드 이름까지 들어가게 (서버가 준다)
                     (min(p[0] for p in pts), max(p[0] for p in pts),
                      min(p[1] for p in pts), max(p[1] for p in pts)) if pts else None)
        # 시·군·구 경계의 선분마다 어느 시·군·구가 쓰나 (칸 사이의 경계를 고를 때 쓴다)
        self._edges = {}
        for g in self._order:
            for ring in g["rings"]:
                for a, b in zip(ring, ring[1:] + ring[:1]):
                    self._edges.setdefault(_edge_key(a, b), set()).add(g["code"])
        self._shape = None
        self.redraw()

    def set_state(self, data):
        """서버의 지도 응답 (/api/guild/war/map). 칸 나눔이 같으면 색과 선만 고친다."""
        data = data or {}
        self.cells = dict(data.get("cells") or {})
        self.cell_of = dict((c, cid) for cid, x in self.cells.items() for c in x.get("codes") or [])
        self.colors = dict((g["guildId"], color_of(g.get("color"))) for g in data.get("guilds") or [])
        self.my_gid = data.get("myGuild")
        self.need = data.get("need") or 3
        shape = tuple(sorted((cid, tuple(x.get("codes") or [])) for cid, x in self.cells.items()))
        if self.items and shape == self._shape:
            self.recolor()
        else:
            self._shape = shape
            self.redraw()

    def owner(self, cid):
        x = self.cells.get(cid)
        return x.get("g") if x else None

    def fill(self, cid):
        gid = self.owner(cid)
        c = self.colors.get(gid, BLANK) if gid is not None else BLANK
        return lighten(c) if cid == self.selected else c

    def line_look(self, a, b):
        """칸 a 와 b 사이 경계의 (색, 굵기). b 가 None 이면 바닷가."""
        ga = self.owner(a)
        if b is None:
            return (MINE_LINE, 2) if ga == self.my_gid and ga is not None else (LINE, 1)
        gb = self.owner(b)
        if ga == gb:
            return LINE, 1                                   # 같은 길드 안의 칸 경계
        if self.my_gid is not None and self.my_gid in (ga, gb):
            return MINE_LINE, 2                              # 우리 길드의 둘레
        return LINE, 2                                       # 다른 길드끼리 맞닿은 곳

    # ---------------- 그리기 ----------------
    def _fit(self):
        cw = max(100, self.cv.winfo_width())
        ch = max(100, self.cv.winfo_height())
        minx, maxx, miny, maxy = self._box
        pad = U.h(PAD)
        s = min((cw - 2 * pad) / (maxx - minx), (ch - 2 * pad) / (maxy - miny))
        ox = (cw - (maxx - minx) * s) / 2 - minx * s
        oy = (ch - (maxy - miny) * s) / 2 - miny * s
        z, (px, py) = self.zoom, self.pan
        cx, cy = cw / 2.0, ch / 2.0
        return lambda p: ((p[0] * s + ox - cx) * z + cx + px, (p[1] * s + oy - cy) * z + cy + py)

    def redraw(self):
        """다 지우고 새로 그린다 (처음, 칸 나눔이 바뀌었을 때, 칸 크기가 바뀌었을 때)."""
        self._job = None
        cv = self.cv
        try:
            cv.delete("all")
        except tk.TclError:
            return
        self.items, self.runs, self._look, self._line_look = {}, [], {}, {}
        self._backdrop()
        if not self.geo or not self._order or not self._box or not self.cells:
            return
        self._size = (cv.winfo_width(), cv.winfo_height())
        tf = self._fit()
        for g in self._order:
            cid = self.cell_of.get(g["code"])
            if cid is None:
                continue
            fill = self.fill(cid)
            for ring in g["rings"]:
                i = cv.create_polygon([c for p in ring for c in tf(p)], fill=fill, outline=fill, width=1,
                                      tags=("map", "region", "c:" + cid))
                self.items.setdefault(cid, []).append(i)
            self._look[cid] = fill
        self._borders(tf)
        self._labels(tf)
        self._marks()

    def _backdrop(self):
        """지도 뒤의 바탕 (테마가 바다 무늬 같은 것을 그린다 - 'bg' 꼬리표, 확대해도 그대로). 기본은 캔버스 빛깔뿐."""

    def _label(self, px, py, text, color):
        """부채꼴 바깥의 길드 이름 한 개 (테마마다 글씨 모양)."""
        self.cv.create_text(px + 1, py + 1, text=text, fill=LINE, font=self.label_font, tags=("map", "label"))
        self.cv.create_text(px, py, text=text, fill=lighten(color, 0.55), font=self.label_font,
                            tags=("map", "label"))

    def _labels(self, tf):
        """부채꼴 바깥에 그 땅의 처음 주인 길드 이름 (서버 ring_geo 의 labels). 길드가 많으면 줄여 적는다."""
        labels = (self.geo or {}).get("labels") or []
        cut = 7 if len(labels) > 12 else 12
        for lb in labels:
            text = lb.get("text") or ""
            if len(text) > cut:
                text = text[:cut - 1] + "…"
            px, py = tf((lb["x"], lb["y"]))
            self._label(px, py, text, self.colors.get(lb.get("guildId"), "#ffffff"))

    def _borders(self, tf):
        """칸 사이의 경계와 바닷가를 선으로. 고리를 따라가며 같은 경계가 이어지는 동안 한 줄로 묶는다."""
        cv = self.cv
        for g in self._order:
            me = self.cell_of.get(g["code"])
            if me is None:
                continue
            for ring in g["rings"]:
                n = len(ring)
                run, key = [], None
                for k in range(n):
                    a, b = ring[k], ring[(k + 1) % n]
                    users = self._edges.get(_edge_key(a, b), set())
                    others = [self.cell_of.get(c) for c in users if c != g["code"]]
                    if not others:
                        other = None                         # 바닷가 (또는 섬)
                    else:
                        other = others[0]
                        if other == me:
                            other = "same"                   # 칸 안의 경계 - 긋지 않는다
                    k2 = None if other == "same" else (me, other)
                    # 같은 경계는 한쪽에서만 긋는다 (칸 번호가 작은 쪽)
                    if k2 is not None and k2[1] is not None and k2[1] < me:
                        k2 = None
                    if k2 != key:
                        self._flush(run, key, tf)
                        run, key = [], k2
                    if k2 is not None:
                        if not run:
                            run.append(a)
                        run.append(b)
                self._flush(run, key, tf)
        cv.tag_raise("line")

    def _flush(self, run, key, tf):
        if key is None or len(run) < 2:
            return
        color, width = self.line_look(key[0], key[1])
        i = self.cv.create_line([c for p in run for c in tf(p)], fill=color, width=width,
                                tags=("map", "line"))
        self.runs.append((i, key[0], key[1]))
        self._line_look[i] = (color, width)

    def recolor(self):
        """주인이 바뀐 칸의 색과 둘레의 선만 고친다. 고친 칸의 수를 돌려준다."""
        cv = self.cv
        n = 0
        for cid, ids in self.items.items():
            want = self.fill(cid)
            if self._look.get(cid) == want:
                continue
            for i in ids:
                cv.itemconfigure(i, fill=want, outline=want)
            self._look[cid] = want
            n += 1
        for i, a, b in self.runs:
            want = self.line_look(a, b)
            if self._line_look.get(i) != want:
                cv.itemconfigure(i, fill=want[0], width=want[1])
                self._line_look[i] = want
        cv.tag_raise("line")
        self._marks()
        return n

    def _center(self, cid):
        """칸의 한가운데 (넓이로 무게를 단 시·군·구 가운데들의 평균)."""
        sx = sy = sw = 0.0
        for g in self.geo.get("sgg") or []:
            if self.cell_of.get(g["code"]) != cid:
                continue
            w = max(WEIGHT_FLOOR, float(g.get("area") or 0))
            c = g.get("center") or g["rings"][0][0]
            sx, sy, sw = sx + c[0] * w, sy + c[1] * w, sw + w
        return (sx / sw, sy / sw) if sw else None

    def _marks(self):
        """내가 지키는 칸에 흰 점, 우리 길드가 쌓은 승수, 넘어간 칸 표시."""
        cv = self.cv
        cv.delete("mark")
        if not self.geo or not self.items:
            return
        tf = self._fit()
        r = U.h(3)
        for cid, x in self.cells.items():
            text = None
            if x.get("taken"):
                text = "점령"
            elif x.get("wins"):
                text = "%d/%d" % (x["wins"], self.need)
            if not (text or x.get("me")):
                continue
            c = self._center(cid)
            if not c:
                continue
            px, py = tf(c)
            tags = ("map", "mark", "region", "c:" + cid)    # 표시를 눌러도 그 칸을 누른 것으로 친다
            if x.get("me"):
                cv.create_oval(px - r, py - r, px + r, py + r, fill="#ffffff", outline=LINE, width=1, tags=tags)
                py += r + U.h(7)
            if text:
                cv.create_text(px + 1, py + 1, text=text, fill=LINE, font=self.font, tags=tags)
                cv.create_text(px, py, text=text, fill="#ffffff", font=self.font, tags=tags)

    def select(self, cid):
        """고른 칸을 밝게 칠한다 (None 이면 푼다)."""
        if cid == self.selected:
            return
        self.selected = cid
        if self.items:
            self.recolor()

    # ---------------- 누르기 / 올리기 ----------------
    def _under(self):
        """포인터 밑의 칸."""
        try:
            for i in self.cv.find_withtag("current"):
                for t in self.cv.gettags(i):
                    if t.startswith("c:"):
                        return t[2:]
        except tk.TclError:
            pass
        return None

    def _hover(self, cid):
        if self.on_hover and not self._dragged:
            self.on_hover(cid)

    def _click(self, _e):
        if self._dragged:
            return
        self.pick(self._under())

    def pick(self, cid):
        """그 칸을 고른다 (검사도 이것을 부른다)."""
        if not cid or cid not in self.items:
            return
        self.select(cid)
        if self.on_pick:
            self.on_pick(cid)

    # ---------------- 확대 / 옮기기 ----------------
    def _on_resize(self, _e=None):
        size = (self.cv.winfo_width(), self.cv.winfo_height())
        if size == self._size and self.items:
            return
        if self._job:
            try:
                self.root.after_cancel(self._job)
            except Exception:                              # noqa: BLE001
                pass
        self._job = self.root.after(80, self.redraw)

    def _on_wheel(self, e, direction=None):
        """휠로 키우고 줄인다. 그려 둔 것을 늘리기만 한다 (관장 지도와 같은 셈)."""
        if not self.items:
            return "break"
        if direction is not None:
            notches = float(direction)
        else:
            try:
                dlt = float(e.delta)
            except (TypeError, ValueError, AttributeError):
                return "break"
            notches = dlt / 120.0 if abs(dlt) >= 30 else dlt      # 트랙패드는 작은 값을 잘게 보낸다
        if not notches:
            return "break"
        notches = max(-3.0, min(3.0, notches))
        old = self.zoom
        new = max(1.0, min(8.0, old * (1.15 ** notches)))
        if new < 1.01:
            new = 1.0
        if abs(new - old) < 1e-4:
            return "break"
        cw, ch = self.cv.winfo_width(), self.cv.winfo_height()
        cx, cy = cw / 2.0, ch / 2.0
        try:
            mx, my = e.x_root - self.cv.winfo_rootx(), e.y_root - self.cv.winfo_rooty()
        except (AttributeError, TypeError):
            mx, my = cx, cy
        f = new / old
        self.pan[0] = (mx - cx) - ((mx - cx) - self.pan[0]) * f
        self.pan[1] = (my - cy) - ((my - cy) - self.pan[1]) * f
        self.zoom = new
        want = list(self.pan)
        self._clamp_pan()
        try:
            self.cv.scale("map", mx, my, f, f)
            self.cv.move("map", self.pan[0] - want[0], self.pan[1] - want[1])
        except tk.TclError:
            pass
        return "break"

    def _clamp_pan(self):
        if self.zoom <= 1.0:
            self.pan = [0.0, 0.0]
            return
        cw, ch = self.cv.winfo_width(), self.cv.winfo_height()
        lim_x, lim_y = (self.zoom - 1) * cw / 2.0, (self.zoom - 1) * ch / 2.0
        self.pan = [max(-lim_x, min(lim_x, self.pan[0])), max(-lim_y, min(lim_y, self.pan[1]))]

    def reset_view(self):
        """맞춤 크기로 되돌린다."""
        if self.zoom == 1.0 and self.pan == [0.0, 0.0]:
            return
        self.zoom, self.pan = 1.0, [0.0, 0.0]
        self.redraw()

    def view(self):
        """지금 보는 자리 (칸을 다시 만들 때 이어 가려고 들고 있는다)."""
        return {"zoom": self.zoom, "pan": list(self.pan), "selected": self.selected}

    def set_view(self, v):
        v = v or {}
        try:
            self.zoom = max(1.0, min(8.0, float(v.get("zoom") or 1.0)))
            self.pan = [float(x) for x in (v.get("pan") or [0.0, 0.0])][:2]
        except (TypeError, ValueError):
            self.zoom, self.pan = 1.0, [0.0, 0.0]
        self.selected = v.get("selected")

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
        self.cv.move("map", self.pan[0] - before[0], self.pan[1] - before[1])

    def _drag_end(self, _e):
        self._drag = None
        if self._dragged:
            self.cv.configure(cursor="")
            # 놓는 순간의 클릭(고르기)은 먹는다. 칸의 클릭은 놓을 때 처리한다.
            self.root.after(1, self._clear_dragged)

    def _clear_dragged(self):
        self._dragged = False
