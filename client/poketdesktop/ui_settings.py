# -*- coding: utf-8 -*-
"""설정 창.

트레이 메뉴로 바꿀 수 있는 건 크기·활동범위·이름표 셋뿐이었다. 나머지는
설정 파일을 손으로 열어야 했는데, exe 만 받아 쓰는 사람에게는 사실상
바꿀 수 없는 값이었다.

**바꿔서 바로 보이는 것만 둔다.** 내부 사정에 가까운 값(minScale 같은
것)은 여기 올리지 않는다 - 뭘 하는지 모르는 손잡이가 많으면 오히려
아무것도 못 만지게 된다.
"""
import tkinter as tk

from . import autostart
from . import config
from . import ui_common as U

W, H = 460, 560


class Row(object):
    """미끄럼 손잡이 한 줄."""

    def __init__(self, parent, label, note, lo, hi, value, fmt, on_change,
                 step=1):
        self.fmt = fmt
        self.on_change = on_change
        box = tk.Frame(parent, bg=U.BG)
        box.pack(fill="x", pady=(12, 0))
        head = tk.Frame(box, bg=U.BG)
        head.pack(fill="x")
        tk.Label(head, text=label, bg=U.BG, fg=U.FG, font=U.FONT_B,
                 anchor="w").pack(side="left")
        self.val = tk.Label(head, text=fmt % value, bg=U.BG, fg=U.ACCENT,
                            font=U.FONT_S)
        self.val.pack(side="right")
        self.var = tk.DoubleVar(value=value)
        sc = tk.Scale(box, from_=lo, to=hi, resolution=step,
                      orient="horizontal", variable=self.var,
                      showvalue=False, bg=U.BG, fg=U.FG,
                      troughcolor=U.INK, highlightthickness=0, bd=0,
                      activebackground=U.ACCENT, sliderrelief="flat",
                      length=W - 60, command=self._moved)
        sc.pack(fill="x")
        tk.Label(box, text=note, bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS,
                 anchor="w", justify="left", wraplength=W - 60).pack(fill="x")

    def _moved(self, _v):
        v = self.var.get()
        self.val.configure(text=self.fmt % v)
        self.on_change(v)


class SettingsWindow(object):

    def __init__(self, app, parent=None):
        self.app = app
        self.root = app.root
        s = app.settings

        # parent 가 있으면 탭 안의 한 칸으로, 없으면 지금까지처럼 창으로.
        self.win = U.panel(parent, self.root, "포스크탑 — 설정",
                           W, H, None, None, self.close)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        if not U.is_embedded(self.win):
            # 탭으로 들어갈 때는 허브가 이미 걸어 두었다.
            U.install_wheel(self.win)

        head = tk.Frame(self.win, bg=U.BG2, height=56)
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text="설정", bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY_BLACK, 15)).pack(side="left", padx=16, pady=15)
        tk.Frame(self.win, bg=U.LINE2, height=2).pack(fill="x")

        p = tk.Frame(self.win, bg=U.BG)
        p.pack(fill="both", expand=True, padx=20, pady=(4, 0))

        Row(p, "포켓몬 크기", "도트를 이 높이에 맞춰 통일합니다.",
            24, 120, s["targetHeight"], "%.0f px",
            lambda v: self._set_size(int(v)), step=4)
        Row(p, "걷는 속도", "느리게 두면 더 느긋하게 돌아다닙니다.",
            0.3, 3.0, s["walkSpeed"], "x%.1f",
            lambda v: self._set("walkSpeed", round(v, 1)), step=0.1)
        Row(p, "부드러움", "높을수록 부드럽지만 그만큼 더 자주 그립니다.",
            10, 60, s["fps"], "%.0f fps",
            lambda v: self._set("fps", int(v)), step=5)
        Row(p, "서버와 맞추는 주기",
            "짧게 두면 다른 기기에서 바꾼 것이 빨리 반영됩니다. "
            "짧을수록 서버를 자주 두드립니다.",
            30, 300, s["syncSeconds"], "%.0f초",
            lambda v: self._set("syncSeconds", int(v)), step=10)

        self._checks(p, s)

        foot = tk.Frame(self.win, bg=U.BG)
        foot.pack(fill="x", side="bottom", padx=20, pady=16)
        U.ghost_button(foot, "기본값으로", self.reset, height=32).pack(
            side="left")
        U.ghost_button(foot, "닫기", self.close, height=32).pack(side="right")
        self.status = U.status_line(self.win, "바꾸면 바로 적용됩니다.")
        self.status.pack(fill="x", side="bottom", padx=20)

    def _checks(self, p, s):
        box = tk.Frame(p, bg=U.BG)
        box.pack(fill="x", pady=(16, 0))
        self.names = tk.BooleanVar(value=bool(s.get("showNames")))
        # 윈도우 알림은 아예 안 띄운다. 켜 두고 잊어버리는 프로그램이라
        # 무슨 일이 있을 때마다 튀어나오면 하던 일을 방해한다. 그래서
        # 알림 관련 손잡이도 없앴다.
        for var, label, key, note in (
                (self.names, "이름표 보이기", "showNames",
                 "포켓몬 위에 이름과 레벨을 띄웁니다."),):
            c = tk.Checkbutton(
                box, text=label, variable=var, bg=U.BG, fg=U.FG,
                selectcolor=U.INK, activebackground=U.BG,
                activeforeground=U.FG, font=U.FONT_S, anchor="w",
                highlightthickness=0, bd=0,
                command=(lambda k=key, v=var: self._toggle(k, v)))
            c.pack(fill="x")
            tk.Label(box, text=note, bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS,
                     anchor="w").pack(fill="x", padx=(22, 0), pady=(0, 6))
        self._autostart_row(box)

    def _autostart_row(self, box):
        """컴퓨터 켤 때 같이 시작.

        다른 손잡이와 다르게 이건 **설정 파일 밖(레지스트리)** 을 건드린다.
        그래서 실패할 수도 있고, 우리가 켜 둔 것을 사용자가 작업 관리자에서
        꺼 버릴 수도 있다. 켜고 끄는 표시만 두면 "켰는데 왜 안 되지" 로
        끝나므로, **지금 진짜 어떤 상태인지**를 한 줄로 같이 보여준다.
        """
        st, msg = autostart.state()
        self.boot_var = tk.BooleanVar(value=st in ("on", "blocked"))
        tk.Checkbutton(
            box, text="컴퓨터 켤 때 같이 시작", variable=self.boot_var,
            bg=U.BG, fg=U.FG, selectcolor=U.INK, activebackground=U.BG,
            activeforeground=U.FG, font=U.FONT_S, anchor="w",
            highlightthickness=0, bd=0,
            state=("normal" if autostart.supported() else "disabled"),
            command=self._toggle_autostart).pack(fill="x")
        self.boot_note = tk.Label(box, text="", bg=U.BG, fg=U.FG_FAINT,
                                  font=U.FONT_XS, anchor="w", justify="left",
                                  wraplength=W - 60)
        self.boot_note.pack(fill="x", padx=(22, 0), pady=(0, 6))
        self._paint_autostart(st, msg)

    def show_autostart(self):
        """지금 상태를 다시 읽어 화면에 맞춘다.

        트레이에서 껐다 켰을 때 app 이 불러 준다. 이게 없으면 설정 탭이
        옛 표시를 그대로 들고 있다가, 거기서 누를 때 정반대로 동작한다.
        """
        st, msg = autostart.state()
        self.boot_var.set(st in ("on", "blocked"))
        self._paint_autostart(st, msg)

    def _paint_autostart(self, st, msg):
        # 막힌 것은 눈에 띄어야 한다. 나머지는 조용한 설명이면 된다.
        self.boot_note.configure(
            text=msg, fg=(U.DANGER if st == "blocked" else U.FG_FAINT))

    def _toggle_autostart(self):
        ok, msg = self.app.set_autostart(self.boot_var.get())
        # 실패했으면 표시를 되돌린다. 화면과 실제가 어긋나면 안 된다.
        self.show_autostart()
        U.set_status(self.status, msg.replace(chr(10), " "),
                     U.GOOD if ok else U.DANGER)

    # ---------------- 적용 ----------------
    def _save(self):
        config.save_settings(self.app.settings)

    def _set(self, key, value):
        self.app.settings[key] = value
        self._save()

    def _set_size(self, px):
        # 크기는 도트를 다시 만들어야 해서 앱 쪽 경로를 그대로 쓴다.
        self.app.set_size(px)

    def _toggle(self, key, var):
        self.app.settings[key] = bool(var.get())
        self._save()
        if self.app.overlay:
            self.app.overlay.refresh_visuals()
        self.app.refresh_tray()

    def reset(self):
        # autostart 는 화면 취향이 아니라 **윈도우에 걸어 둔 등록**이다.
        # "기본값으로" 를 눌렀다고 부팅 목록에서 조용히 빠지면(혹은 조용히
        # 끼어들면) 어리둥절하다. 여기서는 건드리지 않는다.
        keep = {k: self.app.settings[k]
                for k in ("server", "lastBall", "autostart")
                if k in self.app.settings}
        self.app.settings.clear()
        self.app.settings.update(dict(config.DEFAULTS))
        self.app.settings.update(keep)
        self._save()
        U.set_status(self.status, "기본값으로 되돌렸습니다. 창을 다시 열면"
                                  " 값이 보입니다.")
        self.app.set_size(self.app.settings["targetHeight"])
        self.app.refresh_tray()

    # ---------------- 끝 ----------------
    def focus(self):
        if U.is_embedded(self.win):
            return          # 탭이면 허브가 앞으로 꺼내 준다
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except Exception:                                   # noqa: BLE001
            pass

    def close(self):
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        if getattr(self.app, "settings_win", None) is self:
            self.app.settings_win = None
