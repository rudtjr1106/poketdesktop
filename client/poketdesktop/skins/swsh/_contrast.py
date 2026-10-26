# -*- coding: utf-8 -*-
"""소드·실드 테마 - 남색 바탕 위의 진한 글자를 그 자리에서 밝게 바꾼다.

DP 틀은 밝은 바탕(옅은 푸른 회색) 위에 진한 글자를 놓았다. 이 테마는 시안대로 창 바탕을 남색으로 바꾸므로
바탕에 **바로** 놓인 글자(판 밖의 제목 · 안내 · 개수 …)가 남색 위의 남색이 되어 안 보인다. 판 안의 글자는
판이 흰 판이라 그대로 둔다.

그래서 글자를 놓는 두 자리만 본다 (이 테마일 때만 건다 - 다른 테마 · 기본 테마는 이 파일을 읽지 않는다):

    캔버스 글 (create_text · itemconfigure(fill=))   그 글이 놓이는 점 밑의 도형(가장 위의 칠한 네모 · 다각형 ·
                                                     원) 빛깔, 없으면 캔버스 바탕을 본다
    위젯 (Label · 단추 · 입력칸 …)                    그 위젯의 바탕 빛깔을 본다

캔버스 글은 한가할 때 한 번 더 본다 (글을 먼저 쓰고 판을 나중에 까는 화면 - 그때는 원래 빛깔로 되돌린다).

바탕이 어둡고 글자도 어두우면 글자만 밝힌다: 무채색이면 흰 글자 (흐린 글이면 옅은 남빛 회색), 빛깔이 있으면
(초록 · 주황 같은 뜻 빛깔) 같은 빛깔을 밝게. 배치 · 크기는 건드리지 않는다.
뜨는 메뉴(U.PopupMenu)는 기본 테마의 어두운 바탕에 밝은 글자라 걸리지 않는다.
"""
import colorsys
import tkinter as tk

WHITE = "#ffffff"
SOFT = "#b8bde0"             # 남색 위 흐린 글자 (시안 .hpk small)

_DARK_BG = 0.36              # 이보다 어두운 바탕이면 본다
_DARK_FG = 0.50              # 이보다 어두운 글자면 밝힌다
_SHAPES = ("rectangle", "polygon", "oval", "arc")

_installed = False
_names = {}


def _rgb(c, widget=None):
    """빛깔 -> (r, g, b) 0~1. 이름 빛깔은 Tk 에 묻는다. 모르면 None."""
    if not isinstance(c, str) or not c:
        return None
    if c[0] == "#" and len(c) == 7:
        try:
            return tuple(int(c[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
        except ValueError:
            return None
    if c[0] == "#" and len(c) == 4:
        try:
            return tuple(int(ch * 2, 16) / 255.0 for ch in c[1:])
        except ValueError:
            return None
    got = _names.get(c)
    if got is None and widget is not None:
        try:
            r, g, b = widget.winfo_rgb(c)
            got = (r / 65535.0, g / 65535.0, b / 65535.0)
        except (tk.TclError, ValueError):
            return None
        _names[c] = got
    return got


def _lum(rgb):
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v * 255)))) for v in rgb)


def lighter(fg_rgb):
    """어두운 글자 -> 남색 위에서 읽히는 글자."""
    h, s, v = colorsys.rgb_to_hsv(*fg_rgb)
    if s >= 0.35 and v >= 0.25:                       # 뜻 빛깔 (초록 · 주황 · 파랑 글) - 같은 빛깔을 밝게
        r, g, b = colorsys.hsv_to_rgb(h, min(s, 0.55), 1.0)
        return _hex((r * 0.55 + 0.45, g * 0.55 + 0.45, b * 0.55 + 0.45))
    if _lum(fg_rgb) >= 0.33:                          # 흐린 글 (회색 · 설명)
        return SOFT
    return WHITE


def _recolor():
    """DP 빛깔 -> 이 테마 빛깔 (derive 가 tkinter 에 건 것과 같은 표). 아직 안 걸렸으면 그대로."""
    from .. import derive
    return derive._installed or (lambda c: c)


def need(fg, bg, widget=None):
    """(fg, bg) 가 어두운 바탕 위의 어두운 글자면 바꿀 글자 빛깔, 아니면 None."""
    b = _rgb(bg, widget)
    f = _rgb(fg, widget)
    if b is None or f is None:
        return None
    if _lum(b) < _DARK_BG and _lum(f) < _DARK_FG:
        return lighter(f)
    return None


# ---------------------------------------------------------------- 캔버스 글
def _bg_at(cv, x, y):
    """(x, y) 밑의 바탕 빛깔 - 가장 위의 칠한 도형, 없으면 캔버스 바탕."""
    try:
        ids = cv.find_overlapping(x - 1, y - 1, x + 1, y + 1)
        for i in reversed(ids):
            if cv.type(i) not in _SHAPES:
                continue
            if cv.itemcget(i, "state") == "hidden":
                continue
            fill = cv.itemcget(i, "fill")
            if fill:
                return fill
        return cv.cget("background")
    except tk.TclError:
        return None


_NUDGE = {"n": (0, 4), "s": (0, -4), "e": (-4, 0), "w": (4, 0), "nw": (4, 4), "ne": (-4, 4), "sw": (4, -4),
          "se": (-4, -4), "center": (0, 0)}


def _text_fill(cv, x, y, anchor, fill):
    if fill is None or fill == "":
        fill = "#000000"
    fill = _recolor()(fill)
    dx, dy = _NUDGE.get(str(anchor or "center"), (0, 0))
    bg = _bg_at(cv, x + dx, y + dy)
    return need(fill, bg, cv)


def _wrap_canvas():
    base_create = tk.Canvas._create
    base_itemconf = tk.Canvas.itemconfigure

    def _settle(cv):
        """한가할 때 한 번 더 본다: 글을 먼저 쓰고 판을 나중에 깐 캔버스(마이페이지의 칸 등)는 글을 쓸 때
        밑이 아직 남색이라 밝혔는데, 판이 깔린 뒤에는 흰 판 위의 옅은 글이 된다 - 지금 밑을 보고 원래 빛깔로
        되돌리거나 밝힌다."""
        cv._sw_job = None
        todo, cv._sw_todo = getattr(cv, "_sw_todo", {}), {}
        for i, orig in todo.items():
            try:
                if cv.type(i) != "text":
                    continue
                xy = cv.coords(i)
                if len(xy) < 2:
                    continue
                dx, dy = _NUDGE.get(str(cv.itemcget(i, "anchor") or "center"), (0, 0))
                want = need(orig, _bg_at(cv, xy[0] + dx, xy[1] + dy), cv) or orig
                if cv.itemcget(i, "fill") != want:
                    base_itemconf(cv, i, fill=want)
            except (tk.TclError, ValueError, TypeError):
                continue

    def _later(cv, i, orig):
        try:
            todo = getattr(cv, "_sw_todo", None)
            if todo is None:
                todo = cv._sw_todo = {}
            todo[i] = orig
            if getattr(cv, "_sw_job", None) is None:
                cv._sw_job = cv.after_idle(_settle, cv)
        except (tk.TclError, AttributeError):
            pass

    def _create(self, itemType, args, kw):
        orig = None
        if itemType == "text":
            try:
                flat = tk._flatten(args)
                cnf = flat[-1] if flat and isinstance(flat[-1], (dict, tuple)) else {}
                if isinstance(cnf, tuple):
                    cnf = {}
                coords = [a for a in flat if isinstance(a, (int, float))]
                if len(coords) >= 2:
                    opts = dict(cnf or {})
                    opts.update(kw or {})
                    fill = opts.get("fill")
                    orig = _recolor()(fill if fill else "#000000")
                    new = _text_fill(self, coords[0], coords[1], opts.get("anchor"), fill)
                    if new:
                        kw = dict(kw or {})
                        kw["fill"] = new             # (kw 가 cnf 보다 앞선다 - tkinter._cnfmerge)
            except (tk.TclError, ValueError, TypeError):
                orig = None
        i = base_create(self, itemType, args, kw)
        if orig is not None and _rgb(orig) is not None and _lum(_rgb(orig)) < _DARK_FG:
            _later(self, i, orig)                    # 어두운 글만 - 밝은 글은 바꿀 일이 없다
        return i

    def itemconfigure(self, tagOrId, cnf=None, **kw):
        fill = kw.get("fill") if kw else None
        if fill is None and isinstance(cnf, dict):
            fill = cnf.get("fill")
        if fill:
            try:
                ids = self.find_withtag(tagOrId)
                if len(ids) == 1 and self.type(ids[0]) == "text":
                    xy = self.coords(ids[0])
                    if len(xy) >= 2:
                        orig = _recolor()(fill)
                        if _rgb(orig) is not None and _lum(_rgb(orig)) < _DARK_FG:
                            _later(self, ids[0], orig)
                        elif getattr(self, "_sw_todo", None):
                            self._sw_todo.pop(ids[0], None)
                        new = _text_fill(self, xy[0], xy[1], self.itemcget(ids[0], "anchor"), fill)
                        if new:
                            if "fill" in kw:
                                kw["fill"] = new
                            else:
                                cnf = dict(cnf, fill=new)
            except (tk.TclError, ValueError, TypeError):
                pass
        return base_itemconf(self, tagOrId, cnf, **kw)

    tk.Canvas._create = _create
    tk.Canvas.itemconfigure = itemconfigure
    tk.Canvas.itemconfig = itemconfigure


# ---------------------------------------------------------------- 위젯
_FG_OPTS = ("-foreground", "-insertbackground")


def fix_widget(w):
    """위젯의 바탕이 어둡고 글자도 어두우면 글자만 밝힌다."""
    try:
        bg = w.tk.call(w._w, "cget", "-background")
        fg = w.tk.call(w._w, "cget", "-foreground")
    except (tk.TclError, AttributeError):
        return
    new = need(str(fg), str(bg), w)
    if not new:
        return
    for opt in _FG_OPTS:
        try:
            w.tk.call(w._w, "configure", opt, new)
        except tk.TclError:
            pass


def _wrap_widgets():
    base_init = tk.BaseWidget.__init__
    base_configure = tk.Misc.configure

    def __init__(self, master, widgetName, cnf={}, kw={}, extra=()):      # noqa: B006 (tkinter 와 같은 꼴)
        base_init(self, master, widgetName, cnf, kw, extra)
        fix_widget(self)

    def configure(self, cnf=None, **kw):
        out = base_configure(self, cnf, **kw)
        if cnf or kw:
            keys = set(kw) | (set(cnf) if isinstance(cnf, dict) else set())
            if keys & {"bg", "background", "fg", "foreground"}:
                fix_widget(self)
        return out

    tk.BaseWidget.__init__ = __init__
    tk.Misc.configure = configure
    tk.Misc.config = configure


def install():
    global _installed
    if _installed:
        return
    _installed = True
    _wrap_canvas()
    _wrap_widgets()
