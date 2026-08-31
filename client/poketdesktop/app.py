# -*- coding: utf-8 -*-
"""프로그램 본체 — 로그인, 도감, 오버레이, 트레이, 야생 조우를 이어 붙인다."""
import os
import random
import sys
import tkinter as tk

from common import pokelogic as P              # noqa: E402
from common.version import VERSION             # noqa: E402

from . import api as apimod                    # noqa: E402
from . import config, sprite_cache             # noqa: E402
from . import ui_common as U                   # noqa: E402
from .overlay import Overlay                   # noqa: E402
from .tray import Tray                         # noqa: E402
from .ui_box import BoxWindow, confirm         # noqa: E402
from .ui_common import apply_theme, run_async  # noqa: E402
from .ui_login import LoginWindow, ask_password  # noqa: E402
from .wild_ui import WildController            # noqa: E402


class App(object):
    def __init__(self):
        self.settings = config.load_settings()
        self.api = None
        self.dex = None
        self.username = None
        self.balls = 0
        self.overlay = None
        self.tray = None
        self.wild = None
        self.box_window = None
        self._quitting = False
        self._relogin = False

        self.root = tk.Tk()
        self.root.withdraw()
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        U.init_fonts(self.root)
        apply_theme(self.root)

    # ---------------------------------------------------------------- 시작
    def boot(self):
        session = config.load_session()
        token = session.get("token")
        if not token:
            return self.show_login()
        api = apimod.Api(self.settings["server"], token)

        def done(r, err):
            if err:
                config.log("자동 로그인 실패: %s" % err)
                return self.show_login()
            self.api = api
            self.username = r["user"]["username"]
            config.save_session({"token": r["token"], "username": self.username,
                                 "expiresAt": r.get("expiresAt")})
            config.log("자동 로그인 성공: %s" % self.username)
            self.after_login()
        run_async(self.root, lambda: api.auto_login(token), done)

    def show_login(self):
        res = LoginWindow(self.root, self.settings).show()
        if not res:
            return self.quit()
        self.api = res["api"]
        self.username = res["user"]["username"]
        self.balls = res.get("balls") or 0
        self.after_login()

    def after_login(self):
        def done(r, err):
            if err:
                return self._fatal("도감을 불러오지 못했습니다.\n%s"
                                   % getattr(err, "message", err))
            data, how = r
            self.dex = P.Pokedex(data)
            config.log("도감 %s (%d종)" % (how, len(self.dex.species)))
            self.start_ui()
        run_async(self.root, lambda: apimod.load_pokedex(self.api), done)

    def start_ui(self):
        if self.overlay is None:
            self.overlay = Overlay(self.root, self.settings,
                                   on_pet_menu=self.pet_menu,
                                   on_pet_open=self.pet_open)
            self.overlay.start()
        if self.tray is None:
            self.tray = Tray(self)
            self.tray.start()
        if self.wild is None:
            self.wild = WildController(self)
        self.sync()
        self.wild.start()
        self._schedule_sync()
        self.notify("%s 님, 포켓 데스크톱을 시작했습니다." % self.username)

    def _fatal(self, msg):
        try:
            import tkinter.messagebox as mb
            mb.showerror("포켓 데스크톱", msg)
        except Exception:
            pass
        self.quit()

    # ---------------------------------------------------------------- 알림
    def notify(self, message):
        config.log(message)
        if self.tray:
            self.tray.notify(message)

    def refresh_tray(self):
        if self.tray:
            self.tray.refresh()

    # ---------------------------------------------------------------- 동기화
    def _schedule_sync(self):
        if self._quitting:
            return
        self.root.after(max(15, self.settings["syncSeconds"]) * 1000, self._tick)

    def _tick(self):
        self.sync()
        self._schedule_sync()

    def request_sync(self):
        self.root.after(250, self.sync)

    def sync(self):
        """바탕화면에 있어야 할 목록을 서버에서 받아 화면을 맞춘다.

        도트 내려받기는 작업 스레드에서 미리 끝내둔다. tk 스레드에서 받으면
        받는 동안 포켓몬들이 얼어붙는다.
        """
        if not self.api:
            return

        def work():
            mons = self.api.desktop()
            paths = sprite_cache.ensure_many(
                self.api, [(m.get("num"), m.get("shiny")) for m in mons])
            me = None
            try:
                me = self.api.me()
            except Exception:
                pass
            return mons, paths, me

        def done(r, err):
            if err:
                config.log("동기화 실패: %s" % err)
                # 세션이 끊긴 거라면 조용히 실패만 하고 있으면 안 된다.
                # 포켓몬이 사라진 채로 계속 돌아가서 사용자는 이유를 모른다.
                if getattr(err, "status", 0) == 401:
                    self.on_session_lost()
                return
            mons, paths, me = r
            if me:
                self.balls = me.get("balls", self.balls)
            if self.overlay:
                self.overlay.sync(mons or [], paths or {})
            self.refresh_tray()
        run_async(self.root, work, done)

    def on_session_lost(self):
        """세션이 만료되거나 계정이 사라졌을 때 다시 로그인 받는다."""
        if self._quitting or self._relogin:
            return
        self._relogin = True
        config.log("세션이 끊겨서 다시 로그인을 요청합니다")
        self.notify("로그인이 만료되었습니다. 다시 로그인해 주세요.")
        config.clear_session()
        if self.wild:
            self.wild.stop()
        if self.overlay:
            self.overlay.clear()
        if self.box_window:
            self.box_window.close()
        self.api = None
        self.username = None
        self.balls = 0
        self.refresh_tray()
        try:
            self.show_login()
        finally:
            self._relogin = False

    # ---------------------------------------------------------------- 메뉴 동작
    def open_box(self):
        if self.box_window:
            return self.box_window.focus()
        self.box_window = BoxWindow(self.root, self)

    def pet_open(self, pet):
        self.open_box()
        if self.box_window and self.box_window.tree.exists(str(pet.id)):
            self.box_window.tree.selection_set(str(pet.id))

    def pet_menu(self, pet, event):
        info = pet.mon.get("info", {})
        m = tk.Menu(self.root, tearoff=0, bg=U.BG2, fg=U.FG,
                    activebackground=U.BG4, activeforeground=U.FG,
                    bd=0, font=U.FONT_S)
        m.add_command(label="%s   Lv.%s" % (info.get("name", "?"),
                                            info.get("level", "?")),
                      state="disabled")
        m.add_separator()
        m.add_command(label="정보 보기", command=lambda: self.pet_open(pet))
        m.add_command(label="박스로 거두기", command=lambda: self._recall(pet.id))
        m.add_separator()
        m.add_command(label="포켓몬 관리...", command=self.open_box)
        m.add_command(label="풀숲 찾아보기", command=self.encounter_now)
        m.add_separator()
        m.add_command(label="종료", command=self.quit)
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _recall(self, pid):
        run_async(self.root, lambda: self.api.set_desktop(pid, False),
                  lambda r, e: self.request_sync())

    def recall_all(self):
        if not self.overlay:
            return
        ids = list(self.overlay.pets)

        def work():
            for pid in ids:
                try:
                    self.api.set_desktop(pid, False)
                except Exception:
                    pass
        run_async(self.root, work, lambda r, e: self.request_sync())

    def send_random(self):
        """박스에 있는 포켓몬 중에서 빈 자리만큼 무작위로 내보낸다."""
        def work():
            mons = self.api.pokemon()
            free = [m for m in mons if not m.get("onDesktop")]
            used = sum(1 for m in mons if m.get("onDesktop"))
            room = max(0, 6 - used)
            random.shuffle(free)
            picked = free[:room]
            for m in picked:
                try:
                    self.api.set_desktop(m["id"], True)
                except Exception:
                    break
            sprite_cache.ensure_many(
                self.api, [(m.get("num"), m.get("shiny")) for m in picked])
        run_async(self.root, work, lambda r, e: self.request_sync())

    def encounter_now(self):
        """지금 바로 풀숲을 돋운다."""
        if self.wild:
            self.wild.check(force=True)

    def check_server(self):
        def done(r, err):
            if err:
                self.notify(getattr(err, "message", str(err)))
            else:
                self.notify("서버 정상 · 도감 %d종 · 야생 등장 %d종"
                            % (r.get("species", 0), r.get("spawnable", 0)))
        run_async(self.root, self.api.health, done)

    # ---- 설정 ----
    def set_size(self, px):
        self.settings["targetHeight"] = int(px)
        config.save_settings(self.settings)
        if self.overlay:
            self.overlay.refresh_visuals()
        self.refresh_tray()

    def set_area(self, w, h):
        if w == 0:                       # 화면 전체
            self.settings["areaW"] = 100000
            self.settings["areaH"] = 100000
        else:
            self.settings["areaW"] = w
            self.settings["areaH"] = h
        config.save_settings(self.settings)
        if self.overlay:
            for p in self.overlay.pets.values():
                p.clamp()
                p.place()
        self.refresh_tray()

    def toggle_names(self):
        self.settings["showNames"] = not self.settings.get("showNames")
        config.save_settings(self.settings)
        if self.overlay:
            self.overlay.refresh_visuals()
        self.refresh_tray()

    # ---- 계정 ----
    def logout(self):
        if not confirm(self.root, "로그아웃",
                       "로그아웃하면 이 기기의 저장된 로그인이 지워집니다.\n계속할까요?"):
            return

        def work():
            try:
                self.api.logout()
            except Exception:
                pass
            config.clear_session()
        run_async(self.root, work, lambda r, e: self._restart_login())

    def _restart_login(self):
        if self.wild:
            self.wild.stop()
        if self.overlay:
            self.overlay.clear()
        if self.box_window:
            self.box_window.close()
        self.api = None
        self.username = None
        self.balls = 0
        self.refresh_tray()
        self.show_login()
        if self.api:
            self.after_login()

    def delete_account(self):
        if not confirm(self.root, "회원탈퇴",
                       "계정과 보유한 포켓몬이 전부 삭제됩니다.\n"
                       "되돌릴 수 없습니다. 정말 진행할까요?"):
            return
        pw = ask_password(self.root, "회원탈퇴",
                          "확인을 위해 비밀번호를 입력해 주세요.")
        if not pw:
            return

        def done(r, err):
            if err:
                return self.notify(getattr(err, "message", str(err)))
            config.clear_session()
            self.notify(r.get("message", "탈퇴가 완료되었습니다."))
            self.root.after(1500, self.quit)
        run_async(self.root, lambda: self.api.delete_account(pw), done)

    # ---------------------------------------------------------------- 종료
    def quit(self):
        if self._quitting:
            return
        self._quitting = True
        if self.wild:
            self.wild.stop()
        if self.overlay:
            self.overlay.stop()
            self.overlay.clear()
        if self.tray:
            self.tray.stop()
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.after(120, self.boot)
        self.root.mainloop()


def main():
    config.log("=== 시작 ===")
    try:
        App().run()
    except Exception as e:                     # noqa: BLE001
        import traceback
        config.log("치명적 오류: %s\n%s" % (e, traceback.format_exc()))
        raise
