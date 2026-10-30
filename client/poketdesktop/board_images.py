# -*- coding: utf-8 -*-
"""게시판 이미지 (버전 2) - 글쓰기 첨부 · 글 보기 · 크게 보기. 기본 게시판과 테마(skins/dp/board)가 같이 쓴다.

규칙(장수 · 크기 · 누가 보는가)은 서버 board.py 의 '이미지' 가 정한다. 여기는 그리기와 고르기만 한다.

  · 그림 바이트는 api.board_image 가 이 PC 에 담아 둔다 (번호마다 그림이 안 바뀐다).
  · 글 안에서는 칸 폭에 맞춰 줄인다. 작은 도트 그림은 정수배로 키운다 (흐려지지 않게).
  · 누르면 크게 보기 창 - 움직이는 GIF 는 거기서 움직인다.
"""
import io
import os
import tkinter as tk

from PIL import Image, ImageTk

from . import ui_common as U

FILETYPES = (("이미지", "*.png *.jpg *.jpeg *.gif *.webp *.bmp"), ("모든 파일", "*.*"))
BYTES_MAX = 8 * 1024 * 1024          # 서버의 board.IMG_BYTES_MAX 와 같다 (서버가 limits.imageBytes 로도 알려 준다)


def open_first(raw):
    """바이트 -> 첫 장 (RGBA). 못 열면 None."""
    try:
        im = Image.open(io.BytesIO(raw))
        im.seek(0)
        return im.convert("RGBA")
    except Exception:                                       # noqa: BLE001
        return None


def fit_size(w, h, max_w, max_h):
    """칸에 맞춘 크기 (폭, 높이, 정수배로 키웠나). 작은 그림은 2~3배까지 정수배로 키운다."""
    w, h = max(1, int(w)), max(1, int(h))
    k = min(max_w / float(w), max_h / float(h))
    if k >= 2:
        k = float(min(3, int(k)))
        return int(w * k), int(h * k), True
    if k >= 1:
        return w, h, False
    return max(1, int(w * k)), max(1, int(h * k)), False


def scaled(im, size, sharp):
    if im.size == size:
        return im
    return im.resize(size, Image.NEAREST if sharp else Image.LANCZOS)


def photo(raw, max_w, max_h, bg=None):
    """글 안에 넣을 PhotoImage. 투명한 데는 bg 로 채운다 (Tk 라벨은 반투명을 못 그린다)."""
    im = open_first(raw)
    if im is None:
        return None
    w, h, sharp = fit_size(im.width, im.height, max_w, max_h)
    im = scaled(im, (w, h), sharp)
    if bg:
        base = Image.new("RGBA", im.size, bg)
        base.alpha_composite(im)
        im = base
    return ImageTk.PhotoImage(im)


def thumb(raw, side, bg=None):
    """첨부 줄의 작은 그림 (side x side 안)."""
    return photo(raw, side, side, bg)


def read_file(path, limit=BYTES_MAX):
    """파일 바이트. 너무 크거나 못 읽으면 ValueError (화면에 그대로 적는다)."""
    try:
        size = os.path.getsize(path)
    except OSError:
        raise ValueError("파일을 열 수 없습니다.")
    if size > limit:
        raise ValueError("%s 은(는) 너무 큽니다 (%dMB 까지)." % (os.path.basename(path), limit // (1024 * 1024)))
    with open(path, "rb") as f:
        return f.read()


def pick_files(parent):
    """파일 고르기 창. 고른 경로들 (취소면 빈 것)."""
    from tkinter import filedialog
    try:
        got = filedialog.askopenfilenames(parent=parent, title="붙일 이미지 고르기", filetypes=FILETYPES)
    except tk.TclError:
        return []
    return list(got or [])


def clipboard_image():
    """클립보드에 든 그림을 PNG 바이트로 (없으면 None). 캡처 도구로 찍은 화면을 바로 붙여 넣을 수 있다."""
    try:
        from PIL import ImageGrab
        got = ImageGrab.grabclipboard()
    except Exception:                                       # noqa: BLE001 - 운영체제마다 못 하는 경우가 있다
        return None
    if isinstance(got, list):                               # 탐색기에서 복사한 그림 파일
        for p in got:
            if isinstance(p, str) and p.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
                try:
                    return read_file(p)
                except ValueError:
                    return None
        return None
    if got is None or not hasattr(got, "save"):
        return None
    out = io.BytesIO()
    try:
        got.save(out, "PNG")
    except Exception:                                       # noqa: BLE001
        return None
    return out.getvalue()


ANIM_VIEW_PIXELS = 24000000          # 크게 보기에서 움직이는 그림의 프레임 전부 칸 합 (넘으면 덜 키운다)


class Viewer(object):
    """크게 보기 - 화면의 85% 안에 맞춘다. 움직이는 GIF 는 움직인다. 누르거나 Esc 로 닫는다.

    움직이는 그림은 프레임을 **보일 때** 하나씩 만든다 (열자마자 다 만들면 긴 GIF 에서 화면이 멈춘다).
    키우는 배수도 프레임 수만큼 줄인다 - 프레임 전부의 칸이 ANIM_VIEW_PIXELS 를 넘지 않게.
    """

    def __init__(self, root, raw, title="이미지"):
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.title(title)
        self.win.configure(bg=U.INK)
        self.frames, self.durs, self.i, self.job = [], [], 0, None
        self.src, self.size, self.sharp = None, None, False
        try:
            self.src = Image.open(io.BytesIO(raw))
            n = min(200, int(getattr(self.src, "n_frames", 1) or 1))
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            w0, h0 = self.src.size
            w, h, sharp = fit_size(w0, h0, int(sw * 0.85), int(sh * 0.85))
            while n > 1 and w * h * n > ANIM_VIEW_PIXELS and (w > w0 or w * h > 200 * 200):
                w, h, sharp = max(1, int(w * 0.8)), max(1, int(h * 0.8)), False
            self.size, self.sharp = (w, h), sharp
            self.frames = [None] * n
            self.durs = [100] * n
            self._frame(0)
        except Exception:                                   # noqa: BLE001
            self.frames = []
        if not self.frames:
            tk.Label(self.win, text="이미지를 열 수 없습니다.", bg=U.INK, fg=U.FG, font=U.FONT,
                     padx=30, pady=30).pack()
        else:
            self.label = tk.Label(self.win, image=self._frame(0), bg=U.INK, bd=0, cursor="hand2")
            self.label.pack()
            self.label.bind("<Button-1>", lambda _e: self.close())
            if len(self.frames) > 1:
                self.job = self.win.after(self.durs[0], self._next)
        self.win.bind("<Escape>", lambda _e: self.close())
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        try:
            self.win.focus_force()
        except tk.TclError:
            pass

    def _frame(self, i):
        """i 번째 프레임 PhotoImage (처음 볼 때 만든다)."""
        if self.frames[i] is None:
            self.src.seek(i)
            im = self.src.convert("RGBA")
            base = Image.new("RGBA", self.size, (20, 22, 30, 255))
            base.alpha_composite(scaled(im, self.size, self.sharp))
            self.frames[i] = ImageTk.PhotoImage(base)
            self.durs[i] = max(30, int(self.src.info.get("duration", 100) or 100))
        return self.frames[i]

    def _next(self):
        self.job = None
        if not self.frames:
            return
        self.i = (self.i + 1) % len(self.frames)
        try:
            self.label.configure(image=self._frame(self.i))
            self.job = self.win.after(self.durs[self.i], self._next)
        except (tk.TclError, EOFError, OSError):
            pass

    def close(self):
        if self.job:
            try:
                self.win.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass
