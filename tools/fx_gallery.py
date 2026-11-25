# -*- coding: utf-8 -*-
"""기술 연출 미리보기 창 — 타입 · 기술을 골라 연출만 틀어 본다.

    .venv/bin/python tools/fx_gallery.py

  · 왼쪽 위   타입 × (물리 접촉 · 물리 원거리 · 특수 · 변화) 표. 칸을 누르면 그 조합의 기본 연출이 나온다.
  · 왼쪽 아래 대표 기술 목록 / 이름으로 찾기 (도감의 기술 전부). 고르면 바로 튼다.
  · 위 줄      누가 쓰나 · 배치(배틀 창 / 바탕화면) · 급소 · 효과 · Z기술 · 빗나감 · 느리게 · 배경
  · '차례로'  지금 목록을 위에서부터 이어서 튼다 (타입 표를 보고 있으면 표 전체). Space = 다시, Esc = 멈춤.

진짜 배틀 화면과 같은 코드를 탄다: 배틀 창 배치는 관장 · 실시간 · 레이드 · 더블 창처럼 2배 캔버스
(ui_gym_battle._ScaledCanvas) 위에, 바탕화면 배치는 야생 배틀처럼 1배로 그린다. 도트는 자리 표시용 그림이고,
맞으면 밀리고(fx_shift) 접촉기에는 달려든다(lunge).

창을 띄우지 않고 그림(GIF · 이어 붙인 PNG)으로 뽑으려면 tools/fx_preview.py 를 쓴다.
"""
import json
import os
import sys
import time
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "client"))

from PIL import Image, ImageDraw, ImageTk                       # noqa: E402

from poketdesktop import battle_fx as FX                        # noqa: E402
from poketdesktop import fx_kit as K                            # noqa: E402
from poketdesktop import ui_gym_battle as GB                    # noqa: E402

W, H = 860, 300
TYPES = list(K.PAL)
TYPE_KR = {"NORMAL": "노말", "FIRE": "불꽃", "WATER": "물", "ELECTRIC": "전기", "GRASS": "풀", "ICE": "얼음",
           "FIGHTING": "격투", "POISON": "독", "GROUND": "땅", "FLYING": "비행", "PSYCHIC": "에스퍼", "BUG": "벌레",
           "ROCK": "바위", "GHOST": "고스트", "DRAGON": "드래곤", "DARK": "악", "STEEL": "강철", "FAIRY": "페어리"}
KINDS = [("접촉", {"cat": "physical", "flags": ["contact"], "power": 80}),
         ("원거리", {"cat": "physical", "flags": ["protect"], "power": 80, "en": "x"}),
         ("특수", {"cat": "special", "flags": ["protect"], "power": 90, "en": "x"}),
         ("변화", {"cat": "status", "flags": [], "power": 0, "ail": "curse"})]
SHOWCASE = ("파괴광선 지진 번개 10만볼트 불대문자 화염방사 눈보라 냉동빔 사이코키네시스 섀도볼 용성군 하이드로펌프 "
            "파도타기 문포스 스톤에지 스톤샤워 대지의힘 솔라빔 리프스톰 폭풍 오물폭탄 대폭발 용의파동 파워젬 매지컬샤인 "
            "인파이트 깨물어부수기 불꽃펀치 드래곤클로 리프블레이드 아이언헤드 치근거리기 고스트다이브 전광석화 "
            "플레어드라이브 에어슬래시 거대해머 덩굴채찍 독찌르기 물수리검 기가드레인 "
            "칼춤 HP회복 방어 리플렉터 도깨비불 전기자석파 맹독 수면가루 이상한빛 울음소리 스텔스록 쾌청 비바라기 날개쉬기").split()
BGS = {"어두운": ((44, 50, 72), (26, 30, 44)), "풀밭": ((196, 226, 240), (150, 196, 132)),
       "흰": ((246, 246, 248), (226, 228, 232))}


def blob_sprite(h, col):
    """자리 표시용 도트 (머리 + 몸 + 그림자)."""
    s = 3
    w = int(h * 0.8)
    im = Image.new("RGBA", (w * s, (h + 8) * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([w * s * 0.08, h * s * 0.9, w * s * 0.92, (h + 6) * s], fill=(10, 12, 20, 110))
    d.ellipse([w * s * 0.14, h * s * 0.36, w * s * 0.86, h * s * 0.98], fill=col)
    d.ellipse([w * s * 0.24, 0, w * s * 0.76, h * s * 0.5], fill=col)
    d.ellipse([w * s * 0.36, h * s * 0.16, w * s * 0.46, h * s * 0.26], fill=(255, 255, 255, 230))
    d.ellipse([w * s * 0.56, h * s * 0.16, w * s * 0.66, h * s * 0.26], fill=(255, 255, 255, 230))
    return im.resize((w, h + 8), Image.LANCZOS)


class Stage(object):
    """battle_fx.Effect 가 바라는 무대 (배틀 화면들이 주는 것과 같다)."""

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.raw = app.cv
        self.k = 1.0
        self.cv = self.raw
        self.hiding = FX.Hiding(self._show)
        self.speed = 1.0
        self._t0 = time.monotonic()
        self._base = 0.0

    def set_scale(self, k):
        self.k = k
        self.cv = GB._ScaledCanvas(self.raw, k) if k != 1.0 else self.raw

    # 느리게 틀 수 있게 시계를 준다 (연출은 실제 시각으로 굴러간다)
    def fx_clock(self):
        return self._base + (time.monotonic() - self._t0) * 1000.0 * self.speed

    def set_speed(self, v):
        self._base = self.fx_clock()
        self._t0 = time.monotonic()
        self.speed = v

    def _show(self, key, on):
        self.raw.itemconfigure(self.app.sprite[key], state="normal" if on else "hidden")

    def lunge(self, who, done):
        item = self.app.sprite[who]
        (ax, ay), (bx, by) = self.app.pos[who], self.app.pos["foe" if who == "me" else "me"]
        d = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5 or 1.0
        ux, uy = (bx - ax) / d, (by - ay) / d
        reach = 18 * self.k
        seq = [0.35, 0.7, 1.0, 1.0, 0.6, 0.25, 0.0]
        state = {"at": 0.0}

        def step(i):
            if i >= len(seq):
                return
            dv = (seq[i] - state["at"]) * reach
            state["at"] = seq[i]
            self.raw.move(item, ux * dv, uy * dv)
            self.root.after(int(28 / max(0.05, self.speed)), lambda: step(i + 1))
        step(0)
        self.root.after(int(190 / max(0.05, self.speed)), done)

    def fx_shift(self, key, dx, dy):
        if key in self.app.sprite:
            self.raw.move(self.app.sprite[key], dx * self.k, dy * self.k)

    def fx_box(self, key):
        bb = self.raw.bbox(self.app.sprite[key]) if key in self.app.sprite else None
        return tuple(v / self.k for v in bb) if bb else None


class App(object):
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("기술 연출 미리보기")
        self.root.configure(bg="#14161f")
        raw = json.load(open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8"))["moves"]
        self.moves = {}
        for m in raw.values():
            self.moves.setdefault(m.get("kr"), m)
        self.fx = None
        self.queue = []
        self.last = None
        self.v = {"who": tk.StringVar(value="내가"), "lay": tk.StringVar(value="배틀 창"),
                  "eff": tk.StringVar(value="보통"), "spd": tk.StringVar(value="1x"),
                  "bg": tk.StringVar(value="어두운"), "crit": tk.BooleanVar(), "z": tk.BooleanVar(),
                  "miss": tk.BooleanVar()}
        self._build()
        self.stage = Stage(self)
        self.pos = {}
        self.sprite = {}
        self.photos = {}
        self.redraw()
        self.root.bind("<space>", lambda _e: self.replay())
        self.root.bind("<Escape>", lambda _e: self.halt())

    # ---------------- 화면 ----------------
    def _build(self):
        fg, bg, f = "#dfe4f5", "#14161f", ("", 11)
        top = tk.Frame(self.root, bg=bg)
        top.pack(side="top", fill="x", padx=8, pady=(8, 4))

        def menu(label, key, choices):
            tk.Label(top, text=label, fg="#8f98b8", bg=bg, font=f).pack(side="left", padx=(8, 2))
            om = tk.OptionMenu(top, self.v[key], *choices, command=lambda _v: self.changed(key))
            om.configure(bg="#232737", fg=fg, highlightthickness=0, font=f, width=6)
            om.pack(side="left")
        menu("쓰는 쪽", "who", ("내가", "상대가"))
        menu("배치", "lay", ("배틀 창", "바탕화면"))
        menu("효과", "eff", ("보통", "굉장", "별로"))
        menu("속도", "spd", ("1x", "0.5x", "0.25x"))
        menu("배경", "bg", tuple(BGS))
        for label, key in (("급소", "crit"), ("Z기술", "z"), ("빗나감", "miss")):
            tk.Checkbutton(top, text=label, variable=self.v[key], fg=fg, bg=bg, selectcolor="#232737",
                           activebackground=bg, activeforeground=fg, font=f).pack(side="left", padx=4)
        tk.Button(top, text="다시 (Space)", command=self.replay, font=f).pack(side="left", padx=(10, 2))
        tk.Button(top, text="차례로", command=self.play_all, font=f).pack(side="left", padx=2)
        tk.Button(top, text="멈춤 (Esc)", command=self.halt, font=f).pack(side="left", padx=2)

        body = tk.Frame(self.root, bg=bg)
        body.pack(side="top", fill="both", expand=True, padx=8, pady=4)
        left = tk.Frame(body, bg=bg)
        left.pack(side="left", fill="y")
        grid = tk.Frame(left, bg=bg)
        grid.pack(side="top")
        for j, (name, _spec) in enumerate(KINDS):
            tk.Label(grid, text=name, fg="#8f98b8", bg=bg, font=("", 10)).grid(row=0, column=j + 1)
        for i, t in enumerate(TYPES):
            c = K.tone(t)
            tk.Label(grid, text=TYPE_KR[t], fg=c.light, bg=bg, font=("", 10, "bold"), width=6,
                     anchor="e").grid(row=i + 1, column=0, padx=(0, 4))
            for j, (name, _spec) in enumerate(KINDS):
                b = tk.Label(grid, text="▶", fg=c.deep, bg=c.base, width=4, font=("", 9), cursor="hand2")
                b.grid(row=i + 1, column=j + 1, padx=1, pady=1)
                b.bind("<Button-1>", lambda _e, t=t, j=j: self.play_cell(t, j))
        find = tk.Frame(left, bg=bg)
        find.pack(side="top", fill="x", pady=(8, 2))
        tk.Label(find, text="찾기", fg="#8f98b8", bg=bg, font=f).pack(side="left")
        self.q = tk.StringVar()
        e = tk.Entry(find, textvariable=self.q, font=f, width=14)
        e.pack(side="left", padx=4)
        self.q.trace_add("write", lambda *_a: self.fill())
        self.lb = tk.Listbox(left, height=14, font=f, bg="#1b1e2b", fg=fg, selectbackground="#3a4466",
                             highlightthickness=0, exportselection=False)
        self.lb.pack(side="top", fill="both", expand=True)
        self.lb.bind("<<ListboxSelect>>", lambda _e: self.play_selected())
        self.fill()

        right = tk.Frame(body, bg=bg)
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.cv = tk.Canvas(right, width=W, height=H, highlightthickness=0, bd=0, bg="#1a1e2c")
        self.cv.pack(side="top")
        self.info = tk.Label(right, text="칸이나 기술을 고르세요", fg=fg, bg=bg, font=("", 12), anchor="w",
                             justify="left")
        self.info.pack(side="top", fill="x", pady=6)

    def fill(self):
        q = self.q.get().strip()
        names = [n for n in self.moves if q in n][:400] if q else [n for n in SHOWCASE if n in self.moves]
        self.names = names
        self.lb.delete(0, "end")
        for n in names:
            m = self.moves[n]
            self.lb.insert("end", "%s   %s · %s" % (n, TYPE_KR.get(m.get("type"), "?"), FX.style_of(m)))

    def redraw(self):
        """배경과 도트를 다시 놓는다 (배치 · 배경을 바꿨을 때)."""
        self.halt()
        cv = self.cv
        cv.delete("all")
        top, bot = BGS[self.v["bg"].get()]
        im = Image.new("RGB", (W, H))
        d = ImageDraw.Draw(im)
        for y in range(H):
            t = y / float(H)
            d.line([(0, y), (W, y)], fill=tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(3)))
        self.photos["bg"] = ImageTk.PhotoImage(im)
        cv.create_image(0, 0, image=self.photos["bg"], anchor="nw")
        battle = self.v["lay"].get() == "배틀 창"
        self.stage.set_scale(GB.FX_SCALE if battle else 1.0)
        if battle:                                          # 관장 · 실시간 배틀 창: 나는 왼쪽 아래, 상대는 오른쪽 위
            feet = {"me": (236, 268), "foe": (604, 150)}
            size = {"me": 128, "foe": 104}
        else:                                               # 바탕화면 배틀: 작은 도트가 나란히
            feet = {"me": (300, 196), "foe": (560, 196)}
            size = {"me": 52, "foe": 52}
        for who, col in (("foe", (104, 114, 152, 255)), ("me", (124, 136, 176, 255))):
            self.photos[who] = ImageTk.PhotoImage(blob_sprite(size[who], col))
            x, y = feet[who]
            self.sprite[who] = cv.create_image(x, y + 6, image=self.photos[who], anchor="s")
            self.pos[who] = (x, y - size[who] / 2.0)
        self.stage.hiding = FX.Hiding(self.stage._show)

    # ---------------- 틀기 ----------------
    def changed(self, key):
        if key == "spd":
            self.stage.set_speed({"1x": 1.0, "0.5x": 0.5, "0.25x": 0.25}[self.v["spd"].get()])
            return
        if key in ("lay", "bg"):
            self.redraw()
        self.replay()

    def play_cell(self, typ, j):
        name, spec = KINDS[j]
        m = dict(spec, type=typ, kr="%s %s" % (TYPE_KR[typ], name))
        self.queue = []
        self.play(m)

    def play_selected(self):
        sel = self.lb.curselection()
        if sel:
            self.queue = []
            self.play(self.moves[self.names[sel[0]]])

    def play_all(self):
        if self.q.get().strip() or self.lb.curselection():
            self.queue = [self.moves[n] for n in self.names]
        else:
            self.queue = [dict(spec, type=t, kr="%s %s" % (TYPE_KR[t], name)) for t in TYPES for name, spec in KINDS]
        self.next()

    def next(self):
        if self.queue:
            self.play(self.queue.pop(0))

    def replay(self):
        if self.last:
            self.play(self.last)

    def halt(self):
        self.queue = []
        if self.fx is not None:
            self.fx.stop()
            self.fx = None

    def play(self, move):
        if self.fx is not None:
            self.fx.stop()
        self.last = move
        who = "me" if self.v["who"].get() == "내가" else "foe"
        other = "foe" if who == "me" else "me"
        k = self.stage.k
        (sx, sy), (tx, ty) = self.pos[who], self.pos[other]
        eff = {"보통": 1.0, "굉장": 2.0, "별로": 0.5}[self.v["eff"].get()]
        ev = {"t": "move", "move": move.get("kr"), "z": bool(self.v["z"].get())}
        if self.v["miss"].get():
            ev["_miss"] = True
        elif (move.get("cat") or "status") != "status":
            ev["_hit"] = {"crit": bool(self.v["crit"].get()), "eff": eff}
        t0 = time.monotonic()

        def done():
            self.fx = None
            self.info.configure(text="%s   [%s · %s · 위력 %s]   %d ms" % (
                move.get("kr"), fx.style, TYPE_KR.get(move.get("type"), move.get("type")), move.get("power") or "-",
                (time.monotonic() - t0) * 1000))
            if self.queue:
                self.root.after(260, self.next)
        fx = self.fx = FX.Effect(self.stage, move, (sx / k, sy / k), (tx / k, ty / k), done, who=who, ev=ev)
        self.info.configure(text="%s   [%s]" % (move.get("kr"), fx.style))
        fx.play()


def main():
    FX.DEBUG = "--debug" in sys.argv
    app = App()
    if "--selftest" in sys.argv:            # 창이 뜨고 한 편이 끝까지 도는지만 본다 (검사 · CI 용)
        state = {"n": 0}
        names = ["파괴광선", "지진", "칼춤"]

        def one():
            if state["n"] >= len(names):
                print("GALLERY OK %d" % state["n"])
                return app.root.destroy()
            app.play(app.moves[names[state["n"]]])
            state["n"] += 1
            wait()

        def wait():
            if app.fx is None:
                return app.root.after(50, one)
            app.root.after(50, wait)
        app.root.after(100, one)
    app.root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
