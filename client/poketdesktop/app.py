# -*- coding: utf-8 -*-
"""프로그램 본체 — 로그인, 도감, 오버레이, 트레이, 야생 조우를 이어 붙인다."""
import os
import random
import sys
import tkinter as tk

from common import pokelogic as P              # noqa: E402
from common.korean import natural              # noqa: E402
from common.version import VERSION             # noqa: E402

from . import api as apimod                    # noqa: E402
from . import config, single, sprite_cache, updater, walk_cache  # noqa: E402
from . import ui_common as U                   # noqa: E402
from .overlay import Overlay                   # noqa: E402
from .tray import Tray                         # noqa: E402
from .desktop_battle import DesktopBattle       # noqa: E402
from .ui_bag import BagWindow                  # noqa: E402
from .ui_box import BoxWindow, confirm         # noqa: E402
from .ui_dex import DexWindow                  # noqa: E402
from .ui_friends import FriendsWindow          # noqa: E402
from .ui_settings import SettingsWindow        # noqa: E402
from .arena import Arena                       # noqa: E402
from .ui_shop import ShopWindow                # noqa: E402
from .ui_common import apply_theme, run_async  # noqa: E402
from .ui_login import LoginWindow, ask_password  # noqa: E402
from .ui_update import UpdateWindow             # noqa: E402
from .wild_ui import WildController            # noqa: E402


class App(object):
    def __init__(self):
        self.settings = config.load_settings()
        self.api = None
        self.dex = None
        self.username = None
        self.balls = 0
        self.money = 0
        self.overlay = None
        self.tray = None
        self.wild = None
        self._syncing = False
        self.box_window = None
        self.shop_window = None
        self.bag_window = None
        self.friends_win = None
        self.dex_window = None
        self.settings_win = None
        # 마지막으로 있었던 일. 트레이 메뉴에서 보여준다.
        self.last_message = ""
        # 상대가 걸어온, 아직 안 본 대전 수. 트레이에 표시한다.
        self.pvp_unseen = 0
        self.arena = None
        self.battle = None
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
    def check_update(self):
        """새 버전이 있으면 받아서 갈아탄다.

        갈아탔으면 True 를 돌려준다. 부르는 쪽은 그때 바로 끝내야 한다 —
        새 exe 가 이미 떠 있는데 이쪽도 살아 있으면 두 개가 같이 돈다.

        exe 로 묶여 있을 때만 한다. 개발 중(파이썬)에는 건드리지 않는다.
        """
        if not updater.is_frozen():
            return False
        # 지난 버전 폴더를 치운다. 새 버전으로 갈아탄 직후라면 여기서 지워진다.
        try:
            updater.cleanup_old()
        except Exception:                                   # noqa: BLE001
            pass
        try:
            info = updater.check()
        except Exception as e:                              # noqa: BLE001
            config.log("업데이트 확인 실패: %s" % e)
            return False
        if not info:
            return False
        config.log("새 버전 %s 발견" % info["version"])
        try:
            result, new_exe = UpdateWindow(self.root, info).show()
        except Exception as e:                              # noqa: BLE001
            config.log("업데이트 창 오류: %s" % e)
            return False
        if result == "updated" and new_exe:
            try:
                updater.relaunch(new_exe)
                return True
            except Exception as e:                          # noqa: BLE001
                config.log("새 버전 실행 실패: %s" % e)
        return False

    def boot(self):
        if self.check_update():
            return self.quit()
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
        self.money = res.get("money") or 0
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
        # 첫 동기화가 실패하거나(서버가 깨는 중이라 느릴 수 있다) 도트를
        # 아직 못 받았으면 바탕화면이 비어 보인다. 잠시 뒤 한 번 더 맞춘다.
        self.root.after(2500, self._first_sync_retry)
        self.root.after(7000, self._first_sync_retry)
        self.wild.start()
        self.resume_battle()
        self._schedule_sync()
        self.notify("%s 님, 포켓 데스크톱을 시작했습니다." % self.username)

    def _first_sync_retry(self):
        """바탕화면이 아직 비어 있으면 다시 맞춘다.

        가입 직후에는 서버가 자다 깨는 중이라 첫 요청이 느리거나 실패할 수
        있다. 그러면 포켓몬이 안 뜬 채로 다음 주기(90초)까지 기다리게 된다.
        """
        if self._quitting or not self.api or not self.overlay:
            return
        if self.overlay.pets or self._syncing:
            return          # 이미 받아오는 중이면 그대로 둔다
        config.log("바탕화면이 비어 있어 다시 맞춥니다")
        self.sync()

    def _fatal(self, msg):
        try:
            import tkinter.messagebox as mb
            mb.showerror("포켓 데스크톱", msg)
        except Exception:
            pass
        self.quit()

    # ---------------------------------------------------------------- 알림
    def notify(self, message):
        """무슨 일이 있었는지 한 줄.

        **윈도우 알림은 띄우지 않는다.** 이건 켜 두고 잊어버리는
        프로그램이다. 포켓몬을 잡을 때마다, 레벨이 오를 때마다 화면
        구석에서 알림이 튀어나오면 하던 일을 방해한다. 게임 안에서
        일어나는 일은 바탕화면에서 눈으로 보이는 것으로 충분하다 -
        풀숲이 흔들리고, 도트가 싸우고, 진화 연출이 돈다.

        대신 기록에는 남긴다. 나중에 "왜 그랬지" 를 따져볼 수 있어야 한다.
        그리고 놓치면 안 되는 것(상대가 걸어온 대전 같은 것)은 트레이
        메뉴에 표시로 남는다.

        조사는 여기서 한 번에 자연스럽게 고친다.
        """
        message = natural(message)
        config.log(message)
        self.last_message = message

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
        self._syncing = True

        def work():
            mons = self.api.desktop()
            paths = sprite_cache.ensure_many(
                self.api, [(m.get("num"), m.get("shiny")) for m in mons])
            # 걷는 도트도 같이 받아 둔다. 없는 종은 알아서 건너뛴다.
            walks = walk_cache.ensure_many(
                self.api, [m.get("num") for m in mons])
            me = None
            try:
                me = self.api.me()
            except Exception:
                pass
            return mons, paths, me, walks

        def done(r, err):
            self._syncing = False
            if err:
                config.log("동기화 실패: %s" % err)
                # 세션이 끊긴 거라면 조용히 실패만 하고 있으면 안 된다.
                # 포켓몬이 사라진 채로 계속 돌아가서 사용자는 이유를 모른다.
                if getattr(err, "status", 0) == 401:
                    self.on_session_lost()
                return
            mons, paths, me, walks = r
            if me:
                self.balls = me.get("balls", self.balls)
                self.money = me.get("money", self.money)
                # 상대가 걸어온 대전은 서버가 이 응답에 개수로 실어 준다.
                # 이걸 위해 폴링을 새로 두지 않는다.
                self.announce_pvp(me.get("pvpUnseen", 0))
            if self.overlay:
                self.overlay.sync(mons or [], paths or {}, walks or {})
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
        # 투기장을 먼저 접는다. overlay.clear() 만 하면 locked 가 남아서
        # 다시 로그인해도 바탕화면이 영영 빈 채로 있는다.
        self.close_arena()
        if self.wild:
            self.wild.stop()
        if self.overlay:
            self.overlay.clear()
        self.close_windows()
        if self.battle:
            self.battle.close()
        self.api = None
        self.username = None
        self.balls = 0
        self.money = 0
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

    def open_credits(self):
        """쓰인 자료의 출처. 걷는 도트가 CC BY-NC 라 표기가 필요하다."""
        import webbrowser
        webbrowser.open("https://github.com/rudtjr1106/poketdesktop/blob/main/CREDITS.md")

    def open_shop(self):
        if self.shop_window:
            return self.shop_window.focus()
        self.shop_window = ShopWindow(self.root, self)

    def open_bag(self):
        if self.bag_window:
            return self.bag_window.focus()
        self.bag_window = BagWindow(self.root, self)

    def open_friends(self):
        if self.friends_win:
            return self.friends_win.focus()
        self.friends_win = FriendsWindow(self)

    def open_dex(self):
        if self.dex_window:
            return self.dex_window.focus()
        self.dex_window = DexWindow(self)

    def open_settings(self):
        if self.settings_win:
            return self.settings_win.focus()
        self.settings_win = SettingsWindow(self)

    # ---------------- 유저 배틀 ----------------
    # 대전은 비동기다. 상대가 켜져 있지 않아도 그 사람의 지금 파티를
    # 가져와 붙인다. 그래서 누르면 그 자리에서 끝나고, 상대는 다음에
    # 켤 때 결과를 받는다.
    def pvp_random(self):
        self._pvp(lambda: self.api.pvp_random())

    def pvp_challenge(self, uid):
        self._pvp(lambda: self.api.pvp_challenge(uid))

    def _pvp(self, fn):
        if getattr(self, "_pvp_busy", False) or self.arena:
            return
        if self.battle:
            return self.notify("야생 배틀이 끝난 뒤에 해주세요.")
        self._pvp_busy = True
        self.notify("상대를 찾고 있습니다...")

        def done(r, err):
            self._pvp_busy = False
            if err:
                return self.notify(getattr(err, "message", str(err)))
            self.show_pvp_result(r)
        run_async(self.root, fn, done)

    def watch_match(self, mid):
        """대전 한 판을 투기장에서 재생한다.

        로그는 이미 서버에 있어서 언제 재생하든 같은 판이 나온다.
        재생 중에 꺼도 승패와 보상은 이미 확정되어 있다.
        """
        if self.arena or not self.api:
            return
        def work():
            view = self.api.pvp_match(mid)
            # 상대 팀 도트를 여기서 받아 둔다. overlay.walks 에는 내 팀
            # 것만 들어 있어서(sync 가 내 목록으로만 채운다), 이걸 안 하면
            # 상대만 걷지 않는 옛날 배틀 도트로 나온다.
            nums = []
            for e in view.get("events") or []:
                if e.get("t") == "teams":
                    nums = [x.get("num") for x in
                            (e.get("me") or []) + (e.get("foe") or [])]
                    break
            paths = sprite_cache.ensure_many(
                self.api, [(n, False) for n in nums if n])
            walks = walk_cache.ensure_many(self.api, [n for n in nums if n])
            return view, paths, walks

        def done(r, err):
            if err or not r:
                return self.notify(
                    getattr(err, "message", "대전을 불러오지 못했습니다."))
            if self.arena:
                return
            view, paths, walks = r
            if self.overlay:
                self.overlay.paths.update(paths or {})
                self.overlay.walks.update(walks or {})
            self.wild.stop()
            self.arena = Arena(self, view, on_done=self.close_arena)
            self.arena.start()
            # 다 봤다고 표시. 재생을 끝까지 안 봐도 결과는 이미 정해져 있다.
            run_async(self.root, lambda: self.api.pvp_seen(mid),
                      lambda _r, _e: None)
        run_async(self.root, work, done)

    def close_arena(self):
        """투기장을 끝내고 바탕화면을 원래대로.

        **몇 번을 불러도 안전해야 한다.** 로그아웃·종료·세션만료·정상
        종료가 전부 여기로 온다. 하나라도 빠지면 바탕화면이 잠긴 채
        남고, 사용자는 재시작 말고는 푸는 방법이 없다.
        """
        ar, self.arena = self.arena, None
        if ar:
            try:
                ar.cleanup()
            except Exception:                               # noqa: BLE001
                pass
        if self.overlay:
            self.overlay.locked = False
        # 종료·로그아웃 중이면 되살리지 않는다. 그 길로도 여기를 지나는데,
        # 그때 폴링을 다시 켜면 죽은 세션으로 서버를 두드리게 된다.
        if self._quitting or self._relogin or not self.api:
            return
        if self.wild:
            self.wild.start()
        self.sync()

    def show_pvp_result(self, r):
        """대전이 끝났다. 투기장에서 보여준다."""
        mid = (r or {}).get("matchId")
        if mid:
            return self.watch_match(mid)
        mine = (r or {}).get("a") or {}
        res = mine.get("result")
        head = {"win": "이겼습니다!", "lose": "졌습니다...",
                "draw": "비겼습니다."}.get(res, "대전이 끝났습니다.")
        bits = []
        if mine.get("reward"):
            bits.append("%s원" % format(mine["reward"], ","))
        if mine.get("delta"):
            bits.append("%+d점" % mine["delta"])
        if mine.get("myLeft") is not None:
            bits.append("%d대 %d 남음"
                        % (mine.get("myLeft", 0), mine.get("foeLeft", 0)))
        self.notify(head + ("  (" + " · ".join(bits) + ")" if bits else ""))
        self.sync()

    def announce_pvp(self, n):
        """상대가 걸어온 대전이 몇 개인지. sync 응답에 실려 온다.

        알림을 띄우지 않으므로 트레이 메뉴에 숫자로 남긴다. 대전은
        화면에 아무 자국도 남기지 않아서, 여기 없으면 상대가 걸어온
        것을 알 길이 없다.
        """
        n = int(n or 0)
        if n == self.pvp_unseen:
            return
        self.pvp_unseen = n
        if n:
            config.log("확인하지 않은 대전 %d개" % n)
        self.refresh_tray()

    def watch_pending(self):
        """상대가 걸어온 대전 중 가장 최근 것을 본다."""
        if self.arena:
            return
        if not self.api:
            return self.notify("로그인이 필요합니다.")

        def done(r, err):
            if err:
                return self.notify(getattr(err, "message", str(err)))
            got = [m for m in (r or {}).get("matches") or []
                   if not m.get("attacked")]
            if not got:
                return self.notify("새로 받은 대전이 없습니다.")
            self.watch_match(got[0]["id"])
        run_async(self.root, lambda: self.api.pvp_pending(), done)

    def close_windows(self):
        """열려 있는 창을 전부 닫는다. 로그아웃·탈퇴·종료 때 부른다."""
        self.close_arena()
        for name in ("box_window", "shop_window", "bag_window",
                     "friends_win", "dex_window", "settings_win"):
            w = getattr(self, name, None)
            if w:
                try:
                    w.close()
                except Exception:
                    pass
            setattr(self, name, None)

    def open_battle(self, battle, intro=None):
        """바탕화면에서 배틀을 시작한다. 창은 안 뜬다."""
        if not battle or self.battle or self.arena:
            return
        self.battle = DesktopBattle(self, battle, intro)

    def resume_battle(self):
        """프로그램을 껐다 켰는데 배틀이 진행 중이었다면 이어서 연다."""
        if not self.api or self.battle:
            return

        def done(r, err):
            if err:
                return
            b = (r or {}).get("battle")
            if b and not b.get("over"):
                # 프로그램을 껐다 켠 사이에 남아 있던 배틀은 그냥 정리한다.
                # 야생 도트가 이미 사라졌을 수 있어서 이어붙이기 어렵다.
                run_async(self.root,
                          lambda: self.api.battle_run(b["id"]), lambda x, e: None)
        run_async(self.root, self.api.battle_current, done)

    def pet_open(self, pet):
        """도트를 두 번 누르면 관리 창에서 그 포켓몬을 보여준다.

        예전에는 BoxWindow.tree 를 찾았는데 그런 게 없다(목록을 직접
        그린다). 예외가 나서 선택이 안 옮겨졌고, tkinter 가 예외를
        삼켜서 '창은 뜨는데 엉뚱한 애가 골라져 있다' 로만 보였다.
        """
        self.open_box()
        w = self.box_window
        if not w:
            return
        # 목록을 아직 못 받았을 수 있다. 받은 뒤에 고른다.
        def pick():
            try:
                w.select(pet.id)
            except Exception:                               # noqa: BLE001
                pass
        pick()
        self.root.after(400, pick)

    def pet_menu(self, pet, event):
        # 투기장 중에는 우클릭 메뉴를 아예 안 연다. 트레이만 막으면
        # 이 경로가 열려 있어서, 싸우는 도중에 파티를 바꾸거나 풀숲을
        # 돋울 수 있다.
        if self.arena:
            return
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
        """지금 풀숲이 돋았는지 본다."""
        if self.arena:
            return self.notify("배틀이 끝난 뒤에 해주세요.")
        if self.wild:
            self.wild.check(force=True)

    def check_server(self):
        # 로그아웃 상태에서는 self.api 가 None 이다. 그대로 두면
        # self.api.health 를 꺼내다 터지는데, tkinter 가 after 콜백
        # 예외를 삼켜서 눌러도 아무 반응이 없는 것으로만 보인다.
        if not self.api:
            return self.notify("로그인한 뒤에 확인할 수 있습니다.")

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
                       "로그아웃하면 이 기기의 저장된 로그인이 지워집니다.\n계속할까요?", danger=False, ok_text="로그아웃"):
            return

        def work():
            try:
                self.api.logout()
            except Exception:
                pass
            config.clear_session()
        run_async(self.root, work, lambda r, e: self._restart_login())

    def _restart_login(self):
        self.close_arena()
        if self.wild:
            self.wild.stop()
        if self.overlay:
            self.overlay.clear()
        self.close_windows()
        if self.battle:
            self.battle.close()
        self.api = None
        self.username = None
        self.balls = 0
        self.money = 0
        self.refresh_tray()
        # show_login() 이 로그인에 성공하면 그 안에서 after_login() 까지
        # 부른다. 여기서 한 번 더 부르면 폴링 예약과 컨트롤러가 두 벌씩
        # 생긴다. 지금은 각 컨트롤러에 'is None' 가드가 있어 증상이 안
        # 보이지만, 가드 없는 것을 하나라도 추가하는 순간 드러난다.
        self.show_login()

    def delete_account(self):
        if not confirm(self.root, "회원탈퇴",
                       "계정과 보유한 포켓몬이 전부 삭제됩니다.\n"
                       "되돌릴 수 없습니다. 정말 진행할까요?",
                       ok_text="회원탈퇴"):
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
        self.close_windows()
        if self.wild:
            self.wild.stop()
        if self.overlay:
            self.overlay.stop()
            self.overlay.clear()
        if self.battle:
            self.battle.close()
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
    # 두 개가 같이 돌면 포켓몬이 겹쳐 그려지고 서버도 두 번씩 두드린다.
    # 트레이 아이콘이 '숨겨진 아이콘' 안에 들어가 있어서, 이미 켜져
    # 있는 걸 못 보고 다시 누르기가 아주 쉽다.
    _lock, running = single.acquire(config.data_dir())
    if running:
        config.log("이미 실행 중이라 새로 켜지 않습니다")
        single.tell_user()
        return
    try:
        App().run()
    except Exception as e:                     # noqa: BLE001
        import traceback
        config.log("치명적 오류: %s\n%s"
                   % (e, traceback.format_exc()))
        raise
    finally:
        single.release()
