# -*- coding: utf-8 -*-
"""새 버전을 받는 동안 보여주는 창.

켜자마자 뜨는 화면이라 첫인상이다. 몬스터볼이 굴러가고 진행 막대가
차오른다. 받는 동안 뭘 하고 있는지 글로도 알려준다.

받기와 푸는 일은 반드시 작업 스레드에서 한다. tk 스레드에서 하면 화면이
멈춰서 '먹통이 됐다' 로 보인다.
"""
import tkinter as tk

from common.version import VERSION

from . import config
from . import ui_common as U
from . import updater

W, H = 420, 300


class UpdateWindow(object):
    """받는 동안 뜨는 창. show() 가 끝나면 결과를 돌려준다.

        "updated"   새 버전으로 갈아탐 (부르는 쪽은 종료해야 한다)
        "skip"      나중에 하기로 함
        "failed"    받다가 실패 (그냥 지금 버전으로 계속)
    """

    def __init__(self, root, info):
        self.root = root
        self.info = info
        self.result = "skip"
        self.new_exe = None
        self.spin = 0
        self.spin_job = None
        self.done_flag = False

        self.win = tk.Toplevel(root)
        U.style_window(self.win, "포스크탑 업데이트", W, H)
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.on_skip)

        self._head()
        self._body()

    # ---------------- 머리: 굴러가는 몬스터볼 ----------------
    def _head(self):
        head = tk.Frame(self.win, bg=U.RED, height=92)
        head.pack(fill="x")
        head.pack_propagate(False)
        self.cv = tk.Canvas(head, width=W, height=92, bg=U.RED,
                            highlightthickness=0, bd=0)
        self.cv.pack()
        self.cv.create_text(24, 32, text="새 버전이 있습니다", anchor="w",
                            fill="#ffffff", font=(U.FAMILY_BLACK, 16))
        self.cv.create_text(24, 58, anchor="w", fill="#ffd9d6",
                            font=U.FONT_S,
                            text="v%s  →  v%s" % (VERSION, self.info["version"]))
        self.ball = None
        self.roll()

    def roll(self):
        """몬스터볼이 오른쪽으로 굴러간다. 받는 동안 계속."""
        if self.done_flag:
            return
        r = 17
        x = W - 62
        y = 46
        self.spin = (self.spin + 9) % 360
        if self.ball:
            for i in self.ball:
                self.cv.delete(i)
        items = []
        items.append(self.cv.create_oval(x - r, y - r, x + r, y + r,
                                         fill="#f4f6fb", outline=U.INK, width=3))
        # 회전하는 반쪽
        items.append(self.cv.create_arc(x - r, y - r, x + r, y + r,
                                        start=self.spin, extent=180,
                                        fill=U.RED, outline=U.INK, width=3))
        items.append(self.cv.create_oval(x - 6, y - 6, x + 6, y + 6,
                                         fill="#f4f6fb", outline=U.INK, width=3))
        self.ball = items
        self.spin_job = self.root.after(40, self.roll)

    # ---------------- 몸통 ----------------
    def _body(self):
        p = tk.Frame(self.win, bg=U.BG)
        p.pack(fill="both", expand=True, padx=22, pady=(16, 0))

        self.msg = tk.Label(p, text="받을 준비를 하고 있습니다...", bg=U.BG,
                            fg=U.FG, font=U.FONT_S, anchor="w")
        self.msg.pack(fill="x")

        # 진행 막대 (ttk 대신 직접 그린다 — 테마를 그대로 쓰려고)
        bar = tk.Frame(p, bg=U.INK, height=12, highlightthickness=2,
                       highlightbackground=U.LINE)
        bar.pack(fill="x", pady=(10, 0))
        bar.pack_propagate(False)
        self.fill = tk.Frame(bar, bg=U.ACCENT)
        self.fill.place(x=0, y=0, relwidth=0.0, relheight=1.0)

        self.pct = tk.Label(p, text="", bg=U.BG, fg=U.FG_FAINT,
                            font=U.FONT_XS, anchor="e")
        self.pct.pack(fill="x", pady=(5, 0))

        row = tk.Frame(self.win, bg=U.BG)
        row.pack(fill="x", side="bottom", padx=22, pady=16)
        self.btn_skip = U.ghost_button(row, "나중에", self.on_skip, height=34)
        self.btn_skip.pack(side="right")

        note = tk.Label(self.win, text="받는 동안 잠시만 기다려 주세요",
                        bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS)
        note.pack(side="bottom", pady=(0, 2))

    # ---------------- 진행 ----------------
    def say(self, text):
        try:
            self.msg.configure(text=text)
        except Exception:                                   # noqa: BLE001
            pass

    def progress(self, ratio, label=""):
        try:
            self.fill.place_configure(relwidth=max(0.0, min(1.0, ratio)))
            self.pct.configure(text=label)
        except Exception:                                   # noqa: BLE001
            pass

    def on_skip(self):
        self.result = "skip"
        self.finish()

    def finish(self):
        self.done_flag = True
        if self.spin_job:
            try:
                self.root.after_cancel(self.spin_job)
            except Exception:                               # noqa: BLE001
                pass
            self.spin_job = None
        try:
            self.win.grab_release()
        except Exception:                                   # noqa: BLE001
            pass
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass

    # ---------------- 실제로 받기 ----------------
    def start(self):
        info = self.info
        size = info.get("size") or 0
        self.say("새 버전을 받고 있습니다")

        def on_bytes(got, total):
            total = total or size or 1
            self.root.after(0, self.progress, got / float(total) * 0.85,
                            "%.1f / %.1f MB" % (got / 1048576.0,
                                                total / 1048576.0))

        def on_files(i, total):
            self.root.after(0, self.progress, 0.85 + (i / float(total or 1)) * 0.15,
                            "파일 정리 중 %d/%d" % (i, total))
            self.root.after(0, self.say, "새 버전을 펼치고 있습니다")

        def work():
            zpath = updater.temp_zip(info["version"])
            updater.download(info["url"], zpath, on_bytes)
            return updater.extract(zpath, updater.parent_dir(),
                                   info["version"], on_files)

        def done(new_exe, err):
            if err:
                config.log("업데이트 실패: %s" % err)
                self.say("받지 못했습니다. 지금 버전으로 계속합니다.")
                self.progress(0, "")
                self.result = "failed"
                return self.root.after(1600, self.finish)
            self.new_exe = new_exe
            self.result = "updated"
            self.say("다 받았습니다. 새 버전으로 다시 시작합니다.")
            self.progress(1.0, "완료")
            self.root.after(900, self.finish)

        U.run_async(self.root, work, done)

    def show(self, quiet=False):
        """quiet 는 부팅으로 켜졌을 때. **포커스를 뺏지 않는다.**

        컴퓨터를 켜자마자 다른 일을 시작한 사람의 타이핑을 가로채면 안 된다.
        받는 것은 그대로 하고 창도 그대로 보이되, 앞으로 끌어내지 않는다.
        """
        self.win.transient(self.root)
        if not quiet:
            try:
                self.win.grab_set()
            except Exception:                               # noqa: BLE001
                pass
            self.win.lift()
            self.win.focus_force()
        self.root.after(400, self.start)
        self.root.wait_window(self.win)
        return self.result, self.new_exe
