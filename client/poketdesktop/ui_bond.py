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
"""
import tkinter as tk

from . import ui_common as U

CARD = "#101623"
BAR_BG = "#232b3d"
MEGA = "#b69cff"


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
