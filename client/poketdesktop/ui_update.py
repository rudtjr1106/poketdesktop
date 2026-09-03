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


# ---------------------------------------------------------------- 물어보는 창
ASK_W, ASK_H = 460, 340


def highlights(notes_md, limit=6):
    """릴리스 본문에서 '바뀐 것' 대목만 뽑아 사람이 읽을 줄로 만든다.

    본문 앞쪽 절반은 받는 법 안내다. 이미 받아서 쓰고 있는 사람에게 그걸
    다시 보여줄 이유가 없다. 마크다운 표시는 창에서 글자 그대로 보이기만
    하므로 떼어낸다.

    못 알아보겠으면 빈 목록을 준다. 그때는 창이 줄거리 없이 버전만
    보여준다 - 틀린 것을 보여주는 것보다 낫다.
    """
    if not notes_md:
        return []
    out = []
    started = False
    open_item = False          # 지금 항목이 여러 줄로 이어지는 중인가
    for raw in notes_md.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if line.startswith("#"):
            # 제목 줄. '바뀐 것' 부터가 우리가 찾는 대목이다.
            level = len(line) - len(line.lstrip("#"))
            # **하위 제목은 대목을 끊지 않는다.** '## 바뀐 것' 밑에 '###'
            # 로 한 줄 요약을 두는 꼴이라, 그걸 새 대목으로 보면 바로
            # 다음 항목부터 전부 놓친다.
            if started and level >= 3:
                open_item = False
                continue
            started = ("바뀐 것" in line or "새로운" in line)
            open_item = False
            continue
        if not started:
            continue
        if not line:
            open_item = False          # 빈 줄에서 항목이 끝난다
            continue
        bullet = line[:2] in ("- ", "* ")
        if bullet:
            line = line[2:]
        line = line.replace("**", "").replace("`", "").strip()
        if not line:
            continue
        # **이어지는 줄은 앞 항목에 붙인다.** 릴리스 본문은 한 항목을
        # 여러 줄로 접어 쓴다. 줄마다 세면 한 항목이 넷으로 보이고,
        # 창에는 문장 중간이 잘린 조각만 늘어선다.
        if not bullet and open_item and out:
            out[-1] = out[-1] + " " + line
            continue
        if len(out) >= limit:
            break
        out.append(line)
        open_item = True
    return out


class NewVersionAsk(object):
    """켜 둔 동안 새 버전을 찾았을 때 물어보는 창.

    **켤 때와 다르게 반드시 물어본다.** 켤 때라면 바로 받아도 된다 -
    사용자는 아직 아무것도 시작하지 않았다. 그런데 켜 둔 동안에 받으면
    프로그램이 그 자리에서 다시 시작한다. 배틀 중일 수도, 상점에서 뭘
    고르는 중일 수도 있다. 그걸 말없이 끊으면 안 된다.

    show() 는 "now" 또는 "later" 를 돌려준다.
    """

    def __init__(self, root, info):
        self.root = root
        self.info = info
        self.result = "later"

        self.win = tk.Toplevel(root)
        U.style_window(self.win, "포스크탑 — 새 버전", ASK_W, ASK_H)
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.on_later)

        head = tk.Frame(self.win, bg=U.RED, height=76)
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text="새 버전이 나왔습니다", bg=U.RED, fg="#ffffff",
                 font=(U.FAMILY_BLACK, 15), anchor="w").pack(
                     fill="x", padx=20, pady=(16, 0))
        sub = "v%s  →  v%s" % (VERSION, info["version"])
        size = info.get("size") or 0
        if size:
            sub += "   ·   %.1f MB" % (size / 1048576.0)
        tk.Label(head, text=sub, bg=U.RED, fg="#ffd9d6", font=U.FONT_S,
                 anchor="w").pack(fill="x", padx=20)

        p = tk.Frame(self.win, bg=U.BG)
        p.pack(fill="both", expand=True, padx=20, pady=(14, 0))
        bits = highlights(info.get("notes"))
        if bits:
            tk.Label(p, text="바뀐 것", bg=U.BG, fg=U.FG_DIM, font=U.FONT_B,
                     anchor="w").pack(fill="x")
            for line in bits[:3]:
                # **길면 자른다.** 릴리스 본문의 한 항목은 서너 줄까지
                # 가는데, 그걸 그대로 담으면 창이 화면을 넘긴다. 자세한
                # 것은 받은 뒤 '새로운 기능' 창에서 읽는다.
                if len(line) > 96:
                    line = line[:95].rstrip() + "..."
                tk.Label(p, text="· " + line, bg=U.BG, fg=U.FG,
                         font=U.FONT_S, anchor="w", justify="left",
                         wraplength=ASK_W - 56).pack(fill="x", pady=(4, 0))
        else:
            tk.Label(p, text="새 판으로 갈아탈 수 있습니다.", bg=U.BG,
                     fg=U.FG, font=U.FONT_S, anchor="w").pack(fill="x")

        tk.Label(self.win, text="받으면 프로그램이 새 판으로 다시 시작합니다.",
                 bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w",
                 justify="left", wraplength=ASK_W - 44).pack(
                     fill="x", side="bottom", padx=20, pady=(0, 12))
        row = tk.Frame(self.win, bg=U.BG)
        row.pack(fill="x", side="bottom", padx=20, pady=(0, 4))
        U.PushButton(row, "지금 받기", self.on_now, height=36).pack(side="right")
        U.ghost_button(row, "나중에", self.on_later, height=36).pack(
            side="right", padx=(0, 8))
        self._fit()

    def _fit(self):
        """내용에 맞춰 창 높이를 정한다.

        **정해 둔 높이로는 늘 틀린다.** 줄거리는 릴리스마다 길이가 달라서,
        짧은 판에서는 아래가 텅 비고 긴 판에서는 단추가 잘려 나간다.
        단추가 안 보이면 사용자는 창을 닫는 수밖에 없다.
        """
        try:
            self.win.update_idletasks()
            h = max(ASK_H, self.win.winfo_reqheight())
            sh = self.win.winfo_screenheight()
            h = min(h, max(320, sh - 120))
            sw = self.win.winfo_screenwidth()
            self.win.geometry("%dx%d+%d+%d" % (
                ASK_W, h, (sw - ASK_W) // 2, max(0, (sh - h) // 3)))
        except Exception:                                   # noqa: BLE001
            pass

    def on_now(self):
        self.result = "now"
        self.finish()

    def on_later(self):
        self.result = "later"
        self.finish()

    def finish(self):
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass

    def show(self):
        self.win.transient(self.root)
        # **화면을 잠그지 않는다(grab_set 안 함).** 배틀 중일 수도 있는데,
        # 물어보는 창 하나가 다른 창을 전부 못 쓰게 만들 이유가 없다.
        self.win.lift()
        try:
            self.win.focus_force()
        except Exception:                                   # noqa: BLE001
            pass
        self.root.wait_window(self.win)
        return self.result


# ---------------------------------------------------------------- 패치노트
NOTE_W, NOTE_H = 480, 520


class PatchNotes(object):
    """이번 판에 무엇이 들어왔는지 보여주는 창.

    갈아탄 뒤 처음 켰을 때 한 번 저절로 뜨고, 그 뒤에는 트레이 메뉴의
    '이번 버전 새로운 기능' 으로 언제든 다시 열 수 있다.

    **Text 위젯에 담는다.** Label 을 줄마다 쌓으면 항목이 늘 때마다 창
    높이를 다시 재야 하고, 넘치면 아래가 잘려서 안 보인다. Text 는 스크롤이
    딸려 있어서 내용이 얼마든 늘어도 그대로 읽힌다.
    """

    def __init__(self, root, entry, greet=False):
        self.root = root
        self.win = tk.Toplevel(root)
        U.style_window(self.win, "포스크탑 — 새로운 기능", NOTE_W, NOTE_H)
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        head = tk.Frame(self.win, bg=U.BG2, height=84)
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text=("새 버전으로 갈아탔습니다" if greet
                             else "이번 버전 새로운 기능"),
                 bg=U.BG2, fg=U.FG, font=(U.FAMILY_BLACK, 15),
                 anchor="w").pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(head, text="v%s   ·   %s" % (entry["version"],
                                              entry.get("headline") or ""),
                 bg=U.BG2, fg=U.ACCENT, font=U.FONT_S, anchor="w",
                 justify="left", wraplength=NOTE_W - 44).pack(fill="x", padx=20)
        tk.Frame(self.win, bg=U.LINE2, height=2).pack(fill="x")

        wrap = tk.Frame(self.win, bg=U.BG)
        wrap.pack(fill="both", expand=True, padx=18, pady=(14, 0))
        sb = tk.Scrollbar(wrap, orient="vertical", bg=U.BG2,
                          troughcolor=U.INK, bd=0, highlightthickness=0)
        sb.pack(side="right", fill="y")
        txt = tk.Text(wrap, bg=U.BG, fg=U.FG, font=U.FONT_S, bd=0,
                      height=8,
                      highlightthickness=0, wrap="word", spacing1=2,
                      spacing3=8, padx=4, pady=0, cursor="arrow",
                      yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.configure(command=txt.yview)
        txt.tag_configure("head", font=U.FONT_B, foreground=U.ACCENT,
                          spacing1=10, spacing3=3)
        txt.tag_configure("body", foreground=U.FG_DIM, lmargin1=12, lmargin2=12)
        for title, body in entry["items"]:
            txt.insert("end", title + "\n", "head")
            if body:
                txt.insert("end", body + "\n", "body")
        # 읽기만 하는 창이다. 그렇다고 state="disabled" 로 두면 휠 스크롤까지
        # 막히는 판이 있어서, 글자를 넣는 키만 막는다.
        txt.bind("<Key>", lambda e: "break")
        self.txt = txt

        row = tk.Frame(self.win, bg=U.BG)
        row.pack(fill="x", side="bottom", padx=20, pady=14)
        U.PushButton(row, "좋아요", self.close, height=36).pack(side="right")

    def close(self):
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass

    def show(self, modal=False):
        self.win.transient(self.root)
        self.win.lift()
        try:
            self.win.focus_force()
        except Exception:                                   # noqa: BLE001
            pass
        if modal:
            self.root.wait_window(self.win)
