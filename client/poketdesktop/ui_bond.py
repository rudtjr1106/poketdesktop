# -*- coding: utf-8 -*-
"""포켓몬 관리 창의 '메가진화' 칸 — 유대 미션 (시즌 3).

메가진화할 수 있는 종을 고르면 상세 칸의 진화 칸 아래(능력치 위)에 뜬다.

  · 키스톤: 관장 8곳. 없으면 몇 곳 남았는지.
  · 스톤: 그 종의 메가스톤과 받았는지.
  · 시작 전: 친밀도 막대. 255 가 차면 바탕화면에 빛나는 돌이 뜬다 -
    여기서도 바로 시작할 수 있다(돌을 놓쳐도 되게).
  · 시작 뒤: 미션 셋과 진행. 다 채우면 '메가스톤 받기'. X/Y 로 갈리는
    종은 누를 때 고른다.

## 판정은 서버가 한다

여기서는 GET /api/bond/{id} 로 받은 카드를 그리기만 한다. 시작·받기도
서버가 다시 본다. 목록에서 빨리 넘기면 응답이 뒤섞이므로 고를 때마다
표(token)를 올리고, 옛 표의 응답은 버린다.

레쿠쟈는 스톤이 없다 - 화룡점정을 알면 된다고 한 줄만 적는다.

## 메가진화하면 어떻게 되나 (1.9.0)

미션 칸 아래에 **메가 폼의 타입·특성·능력치**를 미리 보여 준다. 메가진화하면
특성이 바뀌는데(가디안의 트레이스 -> 페어리스킨) 그걸 알 곳이 없었고,
능력치가 얼마나 오르는지도 배틀에 들어가 봐야 알았다 (제보).

능력치는 **이 개체의** 레벨·개체값·노력치·성격으로 센다 - 배틀 엔진이
메가진화할 때 하는 계산(Fighter.mega_evolve)과 같다. 체력은 안 바뀐다.
서버에 묻지 않고 도감으로 여기서 센다. 스톤이 없어도 보인다 - 무엇을 얻게
되는지 알아야 미션을 할 마음이 든다. 폼이 둘(X·Y)이면 둘 다 보여 준다.
"""
import tkinter as tk

from . import ui_common as U

CARD = "#101623"
BAR_BG = "#232b3d"
MEGA = "#b69cff"
STAT_ROWS = [("hp", "HP"), ("atk", "공격"), ("def", "방어"),
             ("spa", "특수공격"), ("spd", "특수방어"), ("spe", "스피드")]


def forms_for(dex, mon):
    """이 개체가 될 수 있는 메가 폼들. 암수가 갈리는 종(냐오닉스)은 제 성별 것만."""
    forms = ((getattr(dex, "mega_of", None) or {}).get((mon or {}).get("species")) or []) \
        if dex else []
    # 배틀 엔진(Fighter.mega_target)과 같은 차례: 제 성별의 폼이 있으면 그것,
    # 없으면 성별 표시가 없는 폼. 같은 스톤으로 되는 다른 성별의 폼은 뺀다.
    g = (mon or {}).get("gender")
    mine = [f for f in forms if f.get("megaGender") and f["megaGender"] == g]
    stones = set(f.get("megaStone") for f in mine)
    rest = [f for f in forms if not f.get("megaGender") and f.get("megaStone") not in stones]
    return mine + rest


def mega_preview(dex, mon, form):
    """이 개체가 그 폼으로 메가진화하면 어떻게 되는가. 못 세면 None.

    배틀 엔진(Fighter.mega_evolve)과 같은 계산이다: 종만 메가 폼으로 바꿔
    능력치를 다시 세고, **체력은 그대로** 둔다. 특성은 메가 폼의 첫 특성.
    """
    try:
        now = dex.stats_of(mon)
        after = dex.stats_of(dict(mon, species=form["internal"]))
    except Exception:                                       # noqa: BLE001
        return None
    if not now or not after:
        return None
    after["hp"] = now.get("hp", after.get("hp"))
    ab = "".join(c for c in str((form.get("abil") or [""])[0]).upper() if c.isalnum())
    base = dex.get(mon.get("species")) or {}
    return {
        "name": form.get("kr") or form.get("internal"),
        "types": list(form.get("types") or []),
        "typesChanged": list(form.get("types") or []) != list(base.get("types") or []),
        "ability": ab or None,
        "abilityKr": dex.ability_name(ab) if ab else None,
        "abilityNote": dex.ability_desc(ab) if ab else None,
        "abilityChanged": bool(ab) and ab != (mon.get("ability") or ""),
        "rows": [(k, label, int(now.get(k, 0)), int(after.get(k, 0)),
                  int(after.get(k, 0)) - int(now.get(k, 0))) for k, label in STAT_ROWS],
        "stoneKr": form.get("megaStoneKr"),
        "move": form.get("megaMove"),
    }


def delta_text(d):
    """능력치 변화 글. '+46', '-10', 안 바뀌면 '그대로'."""
    return "그대로" if not d else ("+%d" % d if d > 0 else "%d" % d)


class BondPanel(object):
    def __init__(self, box, parent, width):
        self.box = box
        self.width = width
        self.before = None                 # 능력치 칸 (그 앞에 담는다)
        self.token = 0
        self.card = None
        self.pid = None
        f = self.frame = tk.Frame(parent, bg=CARD, highlightthickness=2,
                                  highlightbackground=U.LINE)
        self.head = tk.Frame(f, bg=CARD)
        self.head.pack(fill="x", padx=11, pady=(8, 4))
        U.marker_label(self.head, "메가진화", bg=CARD).pack(side="left")
        self.btn = None
        self.body = tk.Frame(f, bg=CARD)
        self.body.pack(fill="x", padx=11, pady=(0, 8))
        # 메가진화하면 어떻게 되나 (1.9.0). 미션 칸(body)은 서버 답이 오면 다시
        # 그리므로, 여기에 섞지 않고 따로 둔다.
        self.preview = tk.Frame(f, bg=CARD)
        self.previews = []                 # 지금 보여 주는 미리보기들 (검사가 본다)

    # ---------------- 보이기 ----------------
    def show(self, m):
        """이 포켓몬을 골랐다. 메가가 없는 종이면 칸째 뺀다."""
        self.token += 1
        self.card = None
        self.pid = m.get("id")
        dex = self.box.app.dex
        forms = ((getattr(dex, "mega_of", None) or {}).get(m.get("species")) or []) if dex else []
        # 늘 뺐다가 능력치 앞에 다시 담는다. 진화 칸도 같은 자리에 담으므로
        # 그대로 두면 고를 때마다 둘의 순서가 뒤바뀐다.
        self.frame.pack_forget()
        if m.get("isEgg") or not forms:
            return
        kw = {"fill": "x", "pady": (10, 0)}
        if self.before is not None:
            kw["before"] = self.before
        self.frame.pack(**kw)
        self._button(None)
        self._preview(m)
        if not any(f.get("megaStone") for f in forms):
            self._lines([("화룡점정을 알고 있으면 스톤 없이 메가진화합니다. "
                          "키스톤은 있어야 합니다.", U.FG_DIM)])
            return
        self._lines([("불러오는 중...", U.FG_FAINT)])
        tok, pid = self.token, self.pid
        api = self.box.app.api
        U.run_async(self.box.root, lambda: api.bond(pid),
                    lambda r, err: self._got(tok, r, err))

    def _got(self, tok, r, err):
        if tok != self.token:
            return                         # 그사이 다른 포켓몬을 골랐다
        try:
            if err or not r:
                self._button(None)
                self._lines([("미션을 불러오지 못했습니다.", U.FG_FAINT)])
                return
            self.render(r)
        except tk.TclError:
            pass                           # 그사이 창을 닫았다

    # ---------------- 메가진화하면 ----------------
    def _preview(self, m):
        """메가 폼의 타입·특성·능력치 변화. 도감으로 여기서 센다."""
        for w in self.preview.winfo_children():
            w.destroy()
        self.preview.pack_forget()
        self.previews = []
        dex = self.box.app.dex
        for form in forms_for(dex, m):
            pv = mega_preview(dex, m, form)
            if pv:
                self.previews.append(pv)
        if not self.previews:
            return
        self.preview.pack(fill="x", padx=11, pady=(0, 9))
        for pv in self.previews:
            self._preview_block(pv, dex)

    def _preview_block(self, pv, dex):
        f = self.preview
        tk.Frame(f, bg=U.LINE, height=1).pack(fill="x", pady=(2, 7))
        head = tk.Frame(f, bg=CARD)
        head.pack(fill="x")
        tk.Label(head, text=pv["name"], bg=CARD, fg=MEGA, font=U.FONT_B,
                 anchor="w").pack(side="left")
        tk.Label(head, text="메가진화하면", bg=CARD, fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(side="left", padx=(6, 0))
        types = tk.Frame(f, bg=CARD)
        types.pack(fill="x", pady=(5, 0))
        tk.Label(types, text="타입", bg=CARD, fg=U.FG_FAINT, font=U.FONT_XS,
                 width=5, anchor="w").pack(side="left")
        for t in pv["types"]:
            U.chip(types, dex.type_name(t), U.TYPE_COLOR.get(t, U.BG3),
                   font=U.FONT_XS, padx=7).pack(side="left", padx=(0, 4))
        if not pv["typesChanged"]:
            tk.Label(types, text="그대로", bg=CARD, fg=U.FG_FAINT,
                     font=U.FONT_XS).pack(side="left", padx=(2, 0))
        if pv.get("abilityKr"):
            ab = tk.Frame(f, bg=CARD)
            ab.pack(fill="x", pady=(5, 0))
            tk.Label(ab, text="특성", bg=CARD, fg=U.FG_FAINT, font=U.FONT_XS,
                     width=5, anchor="w").pack(side="left", anchor="n")
            col = tk.Frame(ab, bg=CARD)
            col.pack(side="left", fill="x", expand=True)
            line = tk.Frame(col, bg=CARD)
            line.pack(fill="x")
            tk.Label(line, text=pv["abilityKr"], bg=CARD, fg=U.FG, font=U.FONT_B,
                     anchor="w").pack(side="left")
            tk.Label(line, text="바뀜" if pv["abilityChanged"] else "그대로", bg=CARD,
                     fg=U.ACCENT if pv["abilityChanged"] else U.FG_FAINT,
                     font=U.FONT_XS).pack(side="left", padx=(6, 0))
            if pv.get("abilityNote"):
                self._label(col, pv["abilityNote"], U.FG_DIM).pack(fill="x")
        grid = tk.Frame(f, bg=CARD)
        grid.pack(fill="x", pady=(6, 0))
        grid.columnconfigure(3, weight=1)
        for i, (_k, label, now, after, d) in enumerate(pv["rows"]):
            tk.Label(grid, text=label, bg=CARD, fg=U.FG_DIM, font=U.FONT_XS,
                     anchor="w", width=7).grid(row=i, column=0, sticky="w", pady=1)
            tk.Label(grid, text=str(now), bg=CARD, fg=U.FG_DIM, font=U.FONT_S,
                     anchor="e").grid(row=i, column=1, sticky="e")
            tk.Label(grid, text="→  %d" % after, bg=CARD, fg=U.FG if d else U.FG_DIM,
                     font=U.FONT_NUM if d else U.FONT_S,
                     anchor="w").grid(row=i, column=2, sticky="w", padx=(8, 0))
            tk.Label(grid, text=delta_text(d), bg=CARD,
                     fg=U.GOOD if d > 0 else (U.DANGER if d < 0 else U.FG_FAINT),
                     font=U.FONT_S, anchor="e").grid(row=i, column=3, sticky="e")
        how = ("화룡점정을 알고 있으면" if pv.get("move")
               else "%s 을(를) 지니면" % pv["stoneKr"] if pv.get("stoneKr") else None)
        note = "지금 레벨·개체값·노력치·성격으로 센 값입니다. 체력은 안 바뀝니다."
        if how:
            note = "%s 배틀에서 메가진화할 수 있습니다. %s" % (how, note)
        from common.korean import natural
        self._label(f, natural(note), U.FG_FAINT).pack(fill="x", pady=(6, 0))

    # ---------------- 그리기 ----------------
    def _clear(self):
        for w in self.body.winfo_children():
            w.destroy()

    def _label(self, parent, text, fg, font=None):
        lb = tk.Label(parent, text=text, bg=CARD, fg=fg, font=font or U.FONT_XS,
                      anchor="w", justify="left")
        U.wrap_to_width(lb)
        return lb

    def _lines(self, rows):
        self._clear()
        for text, fg in rows:
            self._label(self.body, text, fg).pack(fill="x", pady=(0, 2))

    def _button(self, spec):
        """머리줄 오른쪽 단추. spec = (글, 할 일) 또는 None."""
        if self.btn is not None:
            self.btn.holder.destroy()
            self.btn = None
        if spec:
            text, cmd = spec
            self.btn = U.PushButton(self.head, text, cmd, height=24, font=U.FONT_S)
            self.btn.pack(side="right")

    def _bar(self, parent, ratio, color):
        cv = tk.Canvas(parent, height=U.h(6), bg=BAR_BG, highlightthickness=0, bd=0)

        def draw(_e=None):
            try:
                cv.delete("all")
                w = cv.winfo_width()
                if w > 1 and ratio > 0:
                    cv.create_rectangle(0, 0, int(w * min(1.0, ratio)), U.h(6),
                                        fill=color, outline="")
            except tk.TclError:
                pass
        cv.bind("<Configure>", draw)
        return cv

    def render(self, c):
        self.card = c
        self._clear()
        key = c.get("keystone") or {}
        has_key = bool(key.get("has"))
        missing = set(c.get("missing") or [])

        # 키스톤 · 스톤
        top = tk.Frame(self.body, bg=CARD)
        top.pack(fill="x")
        tk.Label(top, text="키스톤", bg=CARD, fg=U.FG_FAINT, font=U.FONT_XS,
                 width=5, anchor="w").pack(side="left")
        tk.Label(top, text="있음" if has_key else "관장 %d / %d곳"
                 % (key.get("gyms", 0), key.get("need", 8)),
                 bg=CARD, fg=U.GOOD if has_key else U.FG_DIM,
                 font=U.FONT_XS).pack(side="left")
        st = tk.Frame(self.body, bg=CARD)
        st.pack(fill="x", pady=(2, 0))
        tk.Label(st, text="스톤", bg=CARD, fg=U.FG_FAINT, font=U.FONT_XS,
                 width=5, anchor="w").pack(side="left", anchor="n")
        names = []
        for s in c.get("stones") or []:
            got = s["id"] not in missing
            names.append("%s%s" % (s.get("kr") or s["id"], " (받음)" if got else ""))
        self._label(st, "  ·  ".join(names), MEGA if not missing else U.GOOD) \
            .pack(side="left", fill="x", expand=True)

        if not c.get("started"):
            return self._before_start(c, has_key, missing)
        return self._missions(c, missing)

    def _before_start(self, c, has_key, missing):
        now, need = int(c.get("happiness") or 0), int(c.get("need") or 255)
        fr = tk.Frame(self.body, bg=CARD)
        fr.pack(fill="x", pady=(8, 0))
        line = tk.Frame(fr, bg=CARD)
        line.pack(fill="x")
        tk.Label(line, text="유대", bg=CARD, fg=U.FG_DIM, font=U.FONT_XS).pack(side="left")
        tk.Label(line, text="%d / %d" % (now, need), bg=CARD,
                 fg=U.PINK if now >= need else U.FG_FAINT,
                 font=U.FONT_XS).pack(side="right")
        self._bar(fr, now / float(need or 1), U.PINK).pack(fill="x", pady=(3, 0))
        if not missing:
            msg, fg, btn = "이 종의 메가스톤을 모두 가지고 있습니다.", U.GOOD, None
        elif not has_key:
            msg, fg, btn = ("관장 8곳을 이기면 키스톤을 받습니다. 키스톤이 있어야 "
                            "메가진화할 수 있어요."), U.FG_DIM, None
        elif now < need:
            msg, fg, btn = ("데리고 다니며 유대를 끝까지 채우면 바탕화면에 빛나는 돌이 "
                            "나타납니다. 누르면 유대 미션이 시작돼요."), U.FG_DIM, None
        else:
            msg, fg, btn = ("유대가 가득 찼습니다! 미션 셋을 마치면 메가스톤을 받습니다."
                            ), MEGA, ("미션 시작", self.do_start)
        self._label(self.body, msg, fg).pack(fill="x", pady=(6, 0))
        self._button(btn)

    def _missions(self, c, missing):
        for i, ms in enumerate(c.get("missions") or []):
            v, t = int(ms.get("value") or 0), int(ms.get("target") or 1)
            done = v >= t
            row = tk.Frame(self.body, bg=CARD)
            row.pack(fill="x", pady=(8 if i == 0 else 5, 0))
            line = tk.Frame(row, bg=CARD)
            line.pack(fill="x")
            tk.Label(line, text="%d / %d" % (v, t), bg=CARD,
                     fg=U.GOOD if done else U.FG_FAINT,
                     font=U.FONT_XS).pack(side="right", anchor="n", padx=(8, 0))
            self._label(line, "%s %s" % ("①②③"[i] if i < 3 else "·", ms.get("text") or ""),
                        U.GOOD if done else U.FG).pack(side="left", fill="x", expand=True)
            self._bar(row, v / float(t or 1), U.GOOD if done else MEGA) \
                .pack(fill="x", pady=(2, 0))
        if c.get("claimable"):
            msg, fg, btn = "미션을 다 채웠습니다! 메가스톤을 받으세요.", MEGA, \
                ("메가스톤 받기", self.do_claim)
        elif c.get("stone"):
            kr = next((s.get("kr") for s in c.get("stones") or []
                       if s["id"] == c["stone"]), c["stone"])
            msg, fg, btn = ("%s 을(를) 받았습니다. 지니게 하고 배틀에서 메가진화를 "
                            "켜 보세요." % kr), U.GOOD, None
        elif c.get("done"):
            msg, fg, btn = "미션을 마쳤습니다.", U.GOOD, None
        else:
            msg, fg, btn = "세 가지를 다 채우면 메가스톤을 받습니다.", U.FG_DIM, None
        self._label(self.body, msg, fg).pack(fill="x", pady=(8, 0))
        self._button(btn)

    # ---------------- 하기 ----------------
    def _send(self, work, ok_msg):
        tok = self.token
        box = self.box
        if self.btn is not None:
            self.btn.configure(state="disabled")

        def done(r, err):
            if err:
                box.say(getattr(err, "message", str(err)), U.DANGER)
                if tok == self.token and self.btn is not None:
                    self.btn.configure(state="normal")
                return
            if tok == self.token and r:
                r.setdefault("keystone", (self.card or {}).get("keystone"))
                try:
                    self.render(r)
                except tk.TclError:
                    return
            box.say(ok_msg(r) if callable(ok_msg) else ok_msg, U.GOOD)
            box.app.request_sync()          # 바탕화면의 빛나는 돌을 치운다
        U.run_async(box.root, work, done)

    def do_start(self):
        pid, api = self.pid, self.box.app.api
        self._send(lambda: api.bond_start(pid), "유대 미션을 시작했습니다!")

    def do_claim(self):
        c = self.card or {}
        miss = [s for s in c.get("stones") or [] if s["id"] in (c.get("missing") or [])]
        if len(miss) == 1:
            return self._claim(miss[0])
        if not miss:
            return
        rows = [{"text": s.get("kr") or s["id"], "command": (lambda s=s: self._claim(s))}
                for s in miss]
        self.box._menu(self.btn, rows)

    def _claim(self, stone):
        pid, api = self.pid, self.box.app.api
        self._send(lambda: api.bond_claim(pid, stone["id"]),
                   "%s 을(를) 받았습니다! 가방에서 지니게 하세요." % (stone.get("kr") or stone["id"]))
