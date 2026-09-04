# -*- coding: utf-8 -*-
"""프로그램 본체 — 로그인, 도감, 오버레이, 트레이, 야생 조우를 이어 붙인다."""
import os
import random
import sys
import tkinter as tk

from common import patchnotes                  # noqa: E402
from common import pokelogic as P              # noqa: E402
from common.korean import natural              # noqa: E402
from common.version import VERSION             # noqa: E402

from . import api as apimod                    # noqa: E402
from . import autostart                     # noqa: E402
from . import config, single, sprite_cache, ui_loading, updater, walk_cache  # noqa: E402
from . import platform_os as PLAT              # noqa: E402
from . import ui_common as U                   # noqa: E402
from .overlay import Overlay                   # noqa: E402
from .tray import Tray                         # noqa: E402
if sys.platform == "darwin" and PLAT.gui_ready():   # noqa: E402
    # 맥은 pystray 를 못 쓴다 (tray_mac 의 첫 주석을 보라).
    # pyobjc 가 없으면 여기서 ImportError 가 나서 앱이 아예 안 뜬다.
    # 그래서 먼저 물어보고, 없으면 main() 이 사람에게 말해 준다.
    from .tray_mac import Tray                 # noqa: E402,F811
from .desktop_battle import DesktopBattle       # noqa: E402
from .ui_bag import BagWindow                  # noqa: E402
from .ui_box import BoxWindow, confirm         # noqa: E402
from .ui_dex import DexWindow                  # noqa: E402
from .ui_friends import FriendsWindow          # noqa: E402
from .ui_settings import SettingsWindow        # noqa: E402
from .arena import Arena                       # noqa: E402
from .ui_shop import ShopWindow                # noqa: E402
from .ui_hub import HubWindow                  # noqa: E402
from .ui_common import apply_theme, run_async  # noqa: E402
from .ui_login import LoginWindow, ask_password  # noqa: E402
from .ui_update import NewVersionAsk, PatchNotes, UpdateWindow  # noqa: E402
from .wild_ui import WildController            # noqa: E402


# 켜 둔 동안 새 버전을 몇 시간마다 살펴볼지.
#
# 이 프로그램은 한 번 켜면 몇 주씩 그대로 돈다(부팅 때 저절로 켜지고,
# 트레이에만 있다). 켤 때 한 번만 보면 새 판이 나와도 컴퓨터를 다시 켤
# 때까지 모른다.
#
# 처음엔 6시간으로 뒀는데, 막상 판을 하나 올려 두고 기다려 보니 너무
# 늦게 알아챈다 - 컴퓨터를 오전에 켜 두고 낮에 판을 올리면 저녁까지도
# 모른다. 1시간으로 줄였다. 깃허브 API 는 로그인 없이 시간당 60번인데,
# 한 사람이 한 시간에 부르는 건 많아야 한두 번(켤 때 한 번 + 이 주기로
# 한 번)이라 훨씬 자주 봐도 넉넉하다.
UPDATE_EVERY_HOURS = 1

# 손으로 켰다면 사람이 화면을 보고 있다. 한 번만 더 해 보고 로그인 창을 준다.
MANUAL_LOGIN_TRIES = 1
# 부팅으로 켜졌으면 **포기하지 않는다.** 3·6·12·24·48초로 물러났다가
# 그 뒤로는 1분마다 조용히 다시 해 본다.
#
# 포기하고 로그인 창을 띄우면 최악이다. 컴퓨터를 켠 지 한참 지나 다른
# 일을 하고 있는데 창이 튀어나와 포커스를 뺏고, 그걸 닫으면 프로그램이
# 그냥 죽는다. 노트북은 뚜껑을 열고 몇 분 뒤에야 와이파이가 붙는 일이
# 흔하다. 그때까지 조용히 기다리는 편이 낫다.
RETRY_MAX_WAIT = 60


class _FakeEvent(object):
    """감시자가 받은 오른쪽 클릭을 tk 이벤트인 척 넘긴다."""

    __slots__ = ("x_root", "y_root", "num")

    def __init__(self, x, y):
        self.x_root, self.y_root, self.num = x, y, 2


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
        self.hub = None            # 탭 창 하나
        self.box_window = None
        self.shop_window = None
        self.bag_window = None
        self.friends_win = None
        self.dex_window = None
        self.settings_win = None
        self.pvp_window = None
        # 마지막으로 있었던 일. 트레이 메뉴에서 보여준다.
        self.last_message = ""
        # 상대가 걸어온, 아직 안 본 대전 수. 트레이에 표시한다.
        self.pvp_unseen = 0
        # 받아 놓고 아직 안 받아준 친구 요청 수. 대전과 같은 이유로
        # 트레이에 숫자로 남긴다 - 화면에 아무 자국이 없다.
        self.friend_unseen = 0
        # 이미 알린 요청. 폴링마다 같은 것을 또 띄우지 않기 위해서다.
        self._friend_seen = set()
        self._friend_first = True
        # 켜 둔 동안의 새 버전 확인.
        self._update_job = None
        self._update_asking = False
        self.notes_win = None
        self.arena = None
        self.battle = None
        self._quitting = False
        self._relogin = False
        self._sync_job = None
        # 부팅 때 켜진 것인지 손으로 켠 것인지. 인터넷이 아직 안 붙었을
        # 때 얼마나 기다려 줄지가 달라진다 (_retry_login).
        self.autostarted = autostart.started_by_autostart()
        self._login_try = 0

        # tk.Tk() 보다 **먼저** 해야 하는 것이 있다 (맥의 창 복구 대화상자).
        PLAT.before_tk()
        self.root = tk.Tk()
        self.root.withdraw()
        # Dock/작업표시줄에는 안 뜨고 트레이 아이콘만 남는다.
        # tk.Tk() **뒤에** 불러야 한다 (Tk 이 정책을 되돌려 놓는다).
        PLAT.hide_from_dock()
        PLAT.dpi_aware()
        U.init_fonts(self.root)
        apply_theme(self.root)

    # ---------------------------------------------------------------- 시작
    def check_update(self):
        """새 버전이 있으면 받아서 갈아탄다.

        갈아탔으면 True 를 돌려준다. 부르는 쪽은 그때 바로 끝내야 한다 —
        새 exe 가 이미 떠 있는데 이쪽도 살아 있으면 두 개가 같이 돈다.

        exe 로 묶여 있을 때만 한다. 개발 중(파이썬)에는 건드리지 않는다.
        맥에서는 아예 안 한다 - 릴리스에 올라간 것이 윈도우 zip 뿐이라
        받아 봐야 못 쓴다 (updater.supported 를 보라).
        """
        if not updater.is_frozen() or not updater.supported():
            return False
        # **옛 폴더를 지우기 전에** 등록해 둔 경로부터 지금 파일로 맞춘다.
        #
        # 바로 아래 cleanup_old() 가 지난 버전 폴더를 지우는데, 갈아탄 직후
        # 첫 실행에서는 Run 키가 아직 그 폴더의 exe 를 가리키고 있다. 지운
        # 다음에 고치려다 그 사이에 프로세스가 죽으면(백신 격리, 강제 종료,
        # 노트북 덮개) Run 키는 없는 파일을 가리킨 채 남는다. 윈도우는 그때
        # 아무 소리 없이 넘어가므로 다음 부팅부터 아무것도 안 뜨고, 안 뜨니
        # 스스로 고칠 기회도 영영 없다.
        #
        # **이미 등록돼 있을 때만** 손댄다. 여기서 새로 등록하면 아직
        # 로그인도 안 한 사람이 부팅 목록에 들어간다.
        if autostart.registered() is not None:
            autostart.sync(self.settings.get("autostart"))
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
            result, new_exe = UpdateWindow(self.root, info).show(
                quiet=self.autostarted)
        except Exception as e:                              # noqa: BLE001
            config.log("업데이트 창 오류: %s" % e)
            return False
        if result == "updated" and new_exe:
            try:
                # 부팅으로 켜진 것이었다면 새 프로세스도 그렇게 알아야
                # 한다. 안 넘기면 갓 갈아탄 판이 '손으로 켠 것' 이 되어
                # 인터넷이 늦게 붙을 때 로그인 창을 띄워 버린다.
                updater.relaunch(new_exe,
                                 [autostart.FLAG] if self.autostarted else [])
                return True
            except Exception as e:                          # noqa: BLE001
                config.log("새 버전 실행 실패: %s" % e)
        return False

    def boot(self):
        if self.check_update():
            return self.quit()
        if self.autostarted:
            self._early_tray()
        self._login_try = 0
        self._auto_login()

    def _early_tray(self):
        """로그인 전이라도 트레이 아이콘은 띄운다 (부팅으로 켜졌을 때).

        인터넷이 늦게 붙는 PC 에서는 여기서부터 몇 분 동안 화면에 아무것도
        없다 - 창도, 트레이 아이콘도. 사용자에게는 "자동 시작이 안 됐다" 와
        구분이 안 된다. 게다가 그때 바탕화면 아이콘을 다시 누르면 "이미
        실행 중입니다, 숨겨진 아이콘에서 몬스터볼을 찾으세요" 가 뜨는데,
        찾으라는 그 아이콘이 없다.
        """
        if self._quitting:
            return
        if self.tray is None:
            self.tray = Tray(self)
            self.tray.start()

    def _auto_login(self):
        if self._quitting:
            return
        session = config.load_session()
        token = session.get("token")
        if not token:
            return self.show_login()
        api = apimod.Api(self.settings["server"], token)

        def done(r, err):
            if err:
                if self._retry_login(err):
                    return
                config.log("자동 로그인 실패: %s" % err)
                return self.show_login()
            self.api = api
            self.username = r["user"]["username"]
            config.save_session({"token": r["token"], "username": self.username,
                                 "expiresAt": r.get("expiresAt")})
            config.log("자동 로그인 성공: %s" % self.username)
            self.after_login()
        run_async(self.root, lambda: api.auto_login(token), done)

    def _retry_login(self, err):
        """서버가 아예 답을 안 했으면 잠시 뒤 다시 해 본다.

        **부팅 직후에는 인터넷이 아직 안 붙어 있다.** 그때 곧바로 로그인
        창을 띄우면, 사용자는 컴퓨터를 켜자마자 영문 모를 창부터 보고
        손으로 다시 켜야 한다.

        서버가 **거절한 것**(토큰 만료 같은 것)은 다시 해도 결과가 같다.
        그건 status 가 붙어서 온다. 아예 못 닿은 것만 status 가 0 이다.

        **ApiError 가 아닌 것은 다시 하지 않는다.** status 가 없다고 0 으로
        치면(getattr 의 기본값) 엉뚱한 오류까지 "인터넷이 없구나" 로 읽혀서,
        고쳐지지도 않을 일로 1분 반을 기다리게 된다.
        """
        if not isinstance(err, apimod.ApiError) or err.status != 0:
            return False
        if not self.autostarted and self._login_try >= MANUAL_LOGIN_TRIES:
            return False
        self._login_try += 1
        wait = min(RETRY_MAX_WAIT, 3 * (2 ** (self._login_try - 1)))
        config.log("서버에 못 닿았습니다. %d초 뒤 다시 (%d번째%s)"
                   % (wait, self._login_try,
                      ", 부팅이라 계속" if self.autostarted else ""))
        self.root.after(wait * 1000, self._auto_login)
        return True

    def show_login(self):
        # Dock 에 없는 앱이라 그냥 띄우면 다른 프로그램 뒤에서 뜬다.
        # 그러면 비밀번호를 칠 수가 없다.
        PLAT.activate()
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
        else:
            self.refresh_tray()     # 로그인 전 메뉴를 제대로 된 것으로 바꾼다
        if self.wild is None:
            self.wild = WildController(self)
        self._watch_right_click()
        # 다시 로그인했으면 알림 기록을 비운다. 다른 계정의 요청을
        # "이미 알렸다" 고 여기면 새 계정의 첫 요청을 놓친다.
        self._friend_seen = set()
        self._friend_first = True
        self.friend_unseen = 0
        self.sync()
        # 첫 동기화가 실패하거나(서버가 깨는 중이라 느릴 수 있다) 도트를
        # 아직 못 받았으면 바탕화면이 비어 보인다. 잠시 뒤 한 번 더 맞춘다.
        self.root.after(2500, self._first_sync_retry)
        self.root.after(7000, self._first_sync_retry)
        # **로그인에 성공한 뒤에** 부팅 등록을 맞춘다.
        #
        # 예전에는 boot() 에서 했는데, 그러면 받아서 열어만 보고 가입은
        # 안 한 사람까지 부팅 목록에 들어간다. 그 사람은 다음부터 컴퓨터를
        # 켤 때마다 쓰지도 않는 프로그램의 로그인 창을 닫아야 하고, 그걸
        # 멈추려면 오히려 가입부터 해야 하는 처지가 된다.
        #
        # 여기서 하면 등록해 둔 경로가 지금 파일과 맞는지도 같이 고쳐진다.
        # 버전이 오르면 파일 이름이 바뀌기 때문에 필요한 일이다.
        autostart.sync(self.settings.get("autostart"))
        self._tell_autostart_once()
        self.wild.start()
        self.resume_battle()
        self._schedule_sync()
        self._schedule_update_check()
        self.notify("%s 님, 포스크탑을 시작했습니다." % self.username)
        self._tell_patchnotes_once()

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
            mb.showerror("포스크탑", msg)
        except Exception:
            pass
        self.quit()

    # ---------------------------------------------------------------- 알림
    def _watch_right_click(self):
        """맥 전용 - 오른쪽 클릭을 Cocoa 쪽에서 받아 알맞은 곳으로 보낸다.

        Tk 은 앱이 활성이 아닐 때 온 오른쪽 클릭을 위젯에 전달하지
        않는다. Dock 에 안 뜨는 앱이라 거의 늘 비활성이므로, 그대로 두면
        포켓몬을 한 번 왼쪽 클릭해 앱을 깨우기 전에는 우클릭이 안 먹는다
        (platform_mac.watch_right_click 을 보라).
        """
        if not PLAT.NEEDS_HIT_TRACKING:      # 맥에서만 할 일이 있다
            return
        PLAT.watch_right_click()

        def pump():
            try:
                for x, y, num in PLAT.take_right_clicks():
                    self._right_click_at(x, y, num)
                self._unstick()
            except Exception:                               # noqa: BLE001
                import traceback
                config.log("우클릭 처리 실패\n" + traceback.format_exc())
            self.root.after(60, pump)
        self.root.after(60, pump)

    def _unstick(self):
        """마우스를 뗐는데 눌린 채로 굳은 도트를 풀어 준다.

        Tk 은 앱이 비활성일 때 '뗐다'(ButtonRelease)를 못 받는 일이 있다.
        그러면 도트가 누른 그 자리에 영영 서 있게 된다. 눌린 단추가
        하나도 없다고 맥이 말하면 풀어 준다.
        """
        if PLAT.mouse_buttons_down():
            return
        for pet in self._pets():
            if getattr(pet, "state", None) == "held":
                try:
                    pet.on_release(None)
                except Exception:                           # noqa: BLE001
                    pass

    def _pets(self):
        """지금 화면에 있는 도트 전부. 야생이 먼저다 (위에 있다)."""
        out = []
        if self.wild is not None and self.wild.pet is not None:
            out.append(self.wild.pet)
        if self.overlay is not None:
            out.extend(self.overlay.pets.values())
            out.extend(self.overlay.extra)
        return out

    def _right_click_at(self, x, y, num):
        """그 자리에 있는 것에게 오른쪽 클릭을 넘긴다.

        창 번호로 먼저 찾고, 못 찾으면 좌표로 찾는다. 창 번호가 확실한데,
        도트를 갈아끼우는 동안(진화)에는 잠깐 어긋날 수 있다.
        """
        wild = self.wild
        if wild is not None and wild.grass is not None:
            if self._hit(wild.grass, x, y, num):
                return wild.on_grass_click()
        for pet in self._pets():
            if self._hit(pet, x, y, num):
                # **도트가 스스로 정하게 둔다.** 야생 포켓몬은 우클릭이
                # 볼 던지기라 WildPet 이 on_menu 를 따로 갖고 있다.
                return pet.on_menu(_FakeEvent(x, y))

    @staticmethod
    def _hit(obj, x, y, num):
        view = getattr(obj, "view", None)
        if view is not None and getattr(view, "win_number", None) == num:
            return True
        try:
            return (obj.x <= x < obj.x + obj.fw
                    and obj.y <= y < obj.y + obj.fh)
        except Exception:                                   # noqa: BLE001
            return False

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

    def toast(self, title, message, kind="update"):
        """운영체제 알림 한 번. 띄웠으면 True.

        **아무 일에나 쓰면 안 된다.** notify() 의 주석에 적힌 대로, 게임
        안에서 일어나는 일은 알림으로 띄우지 않는다. 잡을 때마다 화면
        구석에서 튀어나오면 하던 일을 방해하고, 결국 프로그램을 끄게 된다.

        여기로 올 수 있는 것은 **화면에 아무 자국도 남지 않는 일**뿐이다.
        새 버전과 친구 요청 둘이고, 목록은 patchnotes.TOAST_KINDS 에 있다.
        엉뚱한 kind 로 부르면 조용히 안 띄운다 - 나중에 누가 잡았다는
        알림을 여기로 보내려 할 때 그 자리에서 막히도록 둔 문이다.

        사용자가 설정에서 껐으면 안 띄운다. 그래도 기록에는 남기고,
        놓치면 안 되는 것은 트레이 메뉴에 숫자로 남아 있다.
        """
        config.log("[알림:%s] %s / %s" % (kind, title, message))
        if kind not in patchnotes.TOAST_KINDS:
            return False
        if not self.settings.get("notifyImportant", True):
            return False
        if self.tray is None:
            return False
        try:
            return bool(self.tray.toast(title, message))
        except Exception:                                   # noqa: BLE001
            return False

    def refresh_tray(self):
        if self.tray:
            self.tray.refresh()

    # ---------------------------------------------------------------- 동기화
    def _schedule_sync(self):
        if self._quitting:
            return
        # 로그아웃하고 다시 로그인하면 start_ui 가 한 번 더 돌아서 예약이
        # 한 벌 더 생긴다. 그대로 두면 로그인을 반복할 때마다 90초마다
        # 나가는 요청이 한 벌씩 늘어난다. 앞의 예약을 지우고 새로 건다.
        if self._sync_job is not None:
            try:
                self.root.after_cancel(self._sync_job)
            except Exception:                               # noqa: BLE001
                pass
        self._sync_job = self.root.after(
            max(15, self.settings["syncSeconds"]) * 1000, self._tick)

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
            # 친구 요청은 바탕화면에 아무 자국도 남지 않는다. 여기에
            # 얹어서 같이 받아 온다 - 이걸 위해 폴링을 새로 두지 않는다.
            # 실패해도 동기화 전체를 망치지 않는다(알림은 있으면 좋은
            # 것이고, 없다고 포켓몬이 안 걸어다녀서는 안 된다).
            friends = None
            try:
                friends = self.api.friends()
            except Exception:                               # noqa: BLE001
                pass
            return mons, paths, me, walks, friends

        def done(r, err):
            self._syncing = False
            if err:
                config.log("동기화 실패: %s" % err)
                # 세션이 끊긴 거라면 조용히 실패만 하고 있으면 안 된다.
                # 포켓몬이 사라진 채로 계속 돌아가서 사용자는 이유를 모른다.
                if getattr(err, "status", 0) == 401:
                    self.on_session_lost()
                return
            mons, paths, me, walks, friends = r
            if me:
                self.balls = me.get("balls", self.balls)
                self.money = me.get("money", self.money)
                # 상대가 걸어온 대전은 서버가 이 응답에 개수로 실어 준다.
                # 이걸 위해 폴링을 새로 두지 않는다.
                self.announce_pvp(me.get("pvpUnseen", 0))
            if self.overlay:
                self.overlay.sync(mons or [], paths or {}, walks or {})
            self.announce_friends(friends)
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
    def _tab(self, key):
        """창 하나를 띄우고 그 탭으로 간다.

        예전에는 메뉴마다 창을 따로 띄웠다. 가방을 보다가 상점에 가려면
        트레이로 돌아가야 했고 창이 여섯 개까지 겹쳤다.

        탭 내용은 예전 창 클래스를 그대로 쓴다 - 다른 코드가 아직
        self.box_window 같은 이름으로 찾으므로 여기서 채워 준다.
        """
        # 창을 열 때는 앞으로 나온다. Tk 의 자동 활성화를 막아 두었으므로
        # (platform_mac.keep_focus) 여기서 직접 불러야 한다.
        PLAT.activate()
        if not self.hub:
            self.hub = HubWindow(self)
        self.hub.show(key)
        return self.hub.panes.get(key)

    def open_box(self):
        self.box_window = self._tab("box")

    def open_shop(self):
        self.shop_window = self._tab("shop")

    def open_bag(self):
        self.bag_window = self._tab("bag")

    def open_friends(self):
        self.friends_win = self._tab("friends")

    def open_dex(self):
        self.dex_window = self._tab("dex")

    def open_settings(self):
        self.settings_win = self._tab("settings")

    def open_pvp(self):
        self.pvp_window = self._tab("pvp")

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
        # 상대를 찾고 판을 다 계산해서 받기까지 몇 초 걸린다. 그동안
        # 화면에 아무 변화가 없으면 눌린 건지 아닌지를 알 수가 없다.
        wait = ui_loading.Popup(self.root, "상대를 찾는 중")

        def done(r, err):
            self._pvp_busy = False
            wait.close()
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

    def announce_friends(self, listing):
        """친구 요청이 새로 왔는지 본다. sync 응답에 실려 온다.

        **켤 때 이미 쌓여 있던 것은 개수만 한 번 알린다.** 한 사람씩
        알림을 띄우면 오래 안 켠 사람은 켜자마자 화면 구석이 알림으로
        덮인다. 그 뒤에 새로 오는 것은 누가 보냈는지까지 알려준다.
        """
        if not listing:
            return          # 못 받아왔다. 다음 폴링에 다시 본다.
        inc = [x for x in (listing.get("incoming") or [])
               if x.get("id") is not None]
        ids = set(x["id"] for x in inc)
        if len(inc) != self.friend_unseen:
            self.friend_unseen = len(inc)
            self.refresh_tray()
        fresh = ids - self._friend_seen
        self._friend_seen = ids
        first, self._friend_first = self._friend_first, False
        if not fresh:
            return
        where = "트레이 메뉴의 '친구 요청 보기' 에서 받을 수 있습니다."
        if first:
            self.toast("친구 요청 %d건이 와 있습니다" % len(inc), where,
                       kind="friend")
            config.log("친구 요청 %d건" % len(inc))
            return
        names = [x.get("name") or "?" for x in inc if x["id"] in fresh]
        if len(names) == 1:
            self.toast("%s 님이 친구 요청을 보냈습니다" % names[0], where,
                       kind="friend")
        else:
            self.toast("친구 요청 %d건이 새로 왔습니다" % len(names),
                       ", ".join(names[:4]), kind="friend")
        self.notify("친구 요청이 왔습니다 - " + ", ".join(names))

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
        if self.hub:
            try:
                self.hub.close()
            except Exception:                               # noqa: BLE001
                pass
            self.hub = None
        for name in ("box_window", "shop_window", "bag_window",
                     "friends_win", "dex_window", "settings_win",
                     "pvp_window", "notes_win"):
            w = getattr(self, name, None)
            if w:
                try:
                    w.close()
                except Exception:
                    pass
            setattr(self, name, None)

    def open_battle(self, battle, intro=None, options=None):
        """바탕화면에서 배틀을 시작한다. 창은 안 뜬다.

        options 는 배틀 중에 던질 수 있는 볼 목록이다. 없으면 배틀 안에서
        볼을 못 고르고 마지막에 쓴 볼로만 던지게 된다.
        """
        if not battle or self.battle or self.arena:
            return
        self.battle = DesktopBattle(self, battle, intro, options)

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
        title = "%s   Lv.%s" % (info.get("name", "?"), info.get("level", "?"))
        if not PLAT.NATIVE_MENU:
            # 맥. tk.Menu 는 NSMenu 라 여는 순간 앱이 죽는다.
            U.PopupMenu(self.root, [
                {"text": title, "enabled": False},
                None,
                {"text": "정보 보기", "command": lambda: self.pet_open(pet)},
                {"text": "박스로 거두기",
                 "command": lambda: self._recall(pet.id)},
                None,
                {"text": "포켓몬 관리...", "command": self.open_box},
                None,
                {"text": "종료", "command": self.quit},
            ], event.x_root, event.y_root, width=190)
            return
        m = tk.Menu(self.root, tearoff=0, bg=U.BG2, fg=U.FG,
                    activebackground=U.BG4, activeforeground=U.FG,
                    bd=0, font=U.FONT_S)
        m.add_command(label=title, state="disabled")
        m.add_separator()
        m.add_command(label="정보 보기", command=lambda: self.pet_open(pet))
        m.add_command(label="박스로 거두기", command=lambda: self._recall(pet.id))
        m.add_separator()
        m.add_command(label="포켓몬 관리...", command=self.open_box)
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

    def set_show_grass(self, on):
        """풀숲(야생 조우)을 켜거나 끈다.

        끄면 화면에서 사라지는 것으로 끝나지 않고 서버에 물어보는 것도
        멈춘다 (WildController.enabled). 이미 데려온 포켓몬은 그대로
        걸어다닌다 - 끈 사람이 없애려는 것은 야생이지 포켓몬이 아니다.
        """
        on = bool(on)
        if on == bool(self.settings.get("showGrass", True)):
            return on
        self.settings["showGrass"] = on
        config.save_settings(self.settings)
        if self.wild:
            self.wild.set_enabled(on)
        self.refresh_tray()
        self.notify("풀숲을 켰습니다." if on else
                    "풀숲을 껐습니다. 데려온 포켓몬은 그대로 걸어다닙니다.")
        return on

    def toggle_grass(self):
        """트레이 메뉴에서 부른다. 설정 창이 열려 있으면 표시도 맞춘다."""
        on = self.set_show_grass(not self.settings.get("showGrass", True))
        if self.settings_win:
            try:
                self.settings_win.show_grass()
            except Exception:                               # noqa: BLE001
                pass
        return on

    # ---------------------------------------------------------------- 패치노트
    def show_patchnotes(self, greet=False):
        """이번 판에 무엇이 들어왔는지 보여준다.

        갈아탄 뒤 처음 켤 때 한 번 저절로 뜨고, 그 뒤로는 트레이 메뉴에서
        언제든 다시 열 수 있다.
        """
        entry = patchnotes.entry(VERSION)
        if not entry:
            return self.notify("이 버전에는 적어 둔 변경 내역이 없습니다.")
        w = self.notes_win
        if w is not None:
            try:
                if w.win.winfo_exists():
                    return w.show()
            except Exception:                               # noqa: BLE001
                pass
            self.notes_win = None
        try:
            self.notes_win = PatchNotes(self.root, entry, greet=greet)
            self.notes_win.show()
        except Exception as e:                              # noqa: BLE001
            config.log("새로운 기능 창 오류: %s" % e)
            self.notes_win = None

    def _tell_patchnotes_once(self):
        """갈아탄 뒤 처음 켰을 때 한 번만 띄운다.

        **처음 켠 사람에게는 띄우지 않는다.** 아직 써보지도 않은 프로그램의
        변경 내역은 읽을 이유가 없다. 대신 지금 버전을 적어 둬서, 다음에
        갈아탄 뒤에는 보게 한다.

        버전을 적는 것은 창을 띄우든 말든 먼저 한다. 창 쪽에서 무슨 일이
        나도 다음 실행마다 같은 안내가 또 뜨는 일은 없어야 한다.
        """
        last = self.settings.get("lastRunVersion") or ""
        if last == VERSION:
            return
        self.settings["lastRunVersion"] = VERSION
        config.save_settings(self.settings)
        if not last or not patchnotes.entry(VERSION):
            return
        # 부팅으로 켜졌으면 한참 미룬다. 컴퓨터를 켜자마자 창이 튀어나와
        # 포커스를 뺏으면, 그때 타이핑하던 것이 엉뚱한 데로 들어간다.
        self.root.after(12000 if self.autostarted else 2200,
                        lambda: self.show_patchnotes(greet=True))

    # ------------------------------------------------ 켜 둔 동안의 새 버전
    def _schedule_update_check(self):
        """켜 둔 동안에도 새 버전을 살펴본다.

        예전에는 켤 때 한 번만 봤다(check_update). 이 프로그램은 한 번
        켜면 몇 주씩 그대로 도는 종류라, 그러면 새 판이 나와도 컴퓨터를
        다시 켤 때까지 모른다.
        """
        if self._quitting:
            return
        if not updater.is_frozen() or not updater.supported():
            return          # 개발 중(파이썬)에는 건드리지 않는다
        if self._update_job is not None:
            try:
                self.root.after_cancel(self._update_job)
            except Exception:                               # noqa: BLE001
                pass
        self._update_job = self.root.after(
            int(UPDATE_EVERY_HOURS * 3600 * 1000), self._update_tick)

    def _update_tick(self):
        self._look_for_update()
        self._schedule_update_check()

    def _look_for_update(self):
        """깃허브에 새 판이 있는지 물어본다. 있으면 물어보는 창까지.

        확인은 작업 스레드에서 한다. tk 스레드에서 하면 답이 올 때까지
        포켓몬이 얼어붙는다.
        """
        if self._quitting or self._update_asking:
            return
        self._update_asking = True

        def done(info, err):
            # **창을 다 닫은 뒤에 내린다.** 창이 떠 있는 동안에도 예약된
            # 확인은 계속 깨어나므로, 먼저 내리면 물어보는 창이 둘 뜬다.
            try:
                if err:
                    return config.log("업데이트 확인 실패: %s" % err)
                if not info or self._quitting:
                    return
                if info.get("version") == (self.settings.get("updateSkipped")
                                           or ""):
                    return      # 이 판은 나중에 하겠다고 했다
                self._offer_update(info)
            finally:
                self._update_asking = False
        run_async(self.root, updater.check, done)

    def _offer_update(self, info):
        """새 판을 찾았다. 알림을 띄우고 물어본다."""
        ver = info.get("version") or "?"
        config.log("새 버전 %s 발견 (켜 둔 동안)" % ver)
        self.toast("포스크탑 v%s 이(가) 나왔습니다" % ver,
                   "지금 받을지 묻는 창을 열었습니다. 나중에 받아도 됩니다.",
                   kind="update")
        try:
            want = NewVersionAsk(self.root, info).show()
        except Exception as e:                              # noqa: BLE001
            config.log("새 버전 안내 창 오류: %s" % e)
            return
        if want != "now":
            # 같은 판을 UPDATE_EVERY_HOURS 마다 다시 물어보면 그게 방해다.
            # 다음에 새로 켤 때 다시 묻는다.
            self.settings["updateSkipped"] = ver
            config.save_settings(self.settings)
            return self.notify("새 버전은 나중에 받습니다.")
        try:
            result, new_exe = UpdateWindow(self.root, info).show()
        except Exception as e:                              # noqa: BLE001
            config.log("업데이트 창 오류: %s" % e)
            return
        if result != "updated" or not new_exe:
            return
        try:
            updater.relaunch(new_exe,
                             [autostart.FLAG] if self.autostarted else [])
        except Exception as e:                              # noqa: BLE001
            return config.log("새 버전 실행 실패: %s" % e)
        self.quit()

    def toggle_names(self):
        self.settings["showNames"] = not self.settings.get("showNames")
        config.save_settings(self.settings)
        if self.overlay:
            self.overlay.refresh_visuals()
        self.refresh_tray()

    def _tell_autostart_once(self):
        """부팅 등록을 했다는 것을 딱 한 번 알린다.

        기본으로 켜지는 기능이다. 쓰던 사람은 업데이트만 했는데 부팅
        목록에 이름이 생긴다. 나중에 작업 관리자에서 그걸 발견했을 때의
        반응은 "언제 이게 들어갔지" 이고, 거기서부터는 악성코드를 보는
        눈이 된다. 한 번은 말해야 한다.

        부팅으로 켜진 판에서는 띄우지 않는다 - 컴퓨터를 켜자마자 창이
        튀어나오면 그것대로 방해다. (부팅으로 켜졌다는 건 이미 등록돼
        있었다는 뜻이라, 첫 등록이 여기로 올 일은 원래 없다)
        """
        if self.settings.get("autostartTold") or self.autostarted:
            return
        if autostart.state()[0] != "on":
            return
        self.settings["autostartTold"] = True
        config.save_settings(self.settings)
        try:
            import tkinter.messagebox as mb
            mb.showinfo("포스크탑",
                        "이제 컴퓨터를 켜면 포스크탑도 같이 시작합니다."
                        + chr(10) + chr(10) +
                        "끄고 싶으면 트레이 아이콘을 우클릭해서" + chr(10) +
                        "'컴퓨터 켤 때 같이 시작' 의 체크를 풀면 됩니다.")
        except Exception:                                   # noqa: BLE001
            pass

    def set_autostart(self, want):
        """컴퓨터를 켤 때 같이 시작할지 정한다.

        **레지스트리가 진실이고 설정 파일은 그 사본이다.** 그래서 등록에
        실패하면 설정도 바꾸지 않는다 - 화면에는 "켜짐" 인데 실제로는
        안 켜지는 상태를 만들지 않으려는 것이다.

        돌려주는 한 줄은 사용자에게 그대로 보여줘도 되는 말이다.
        """
        want = bool(want)
        ok, msg = autostart.enable() if want else autostart.disable()
        if ok:
            self.settings["autostart"] = want
            config.save_settings(self.settings)
        self.notify(msg)
        self.refresh_tray()
        self._refresh_autostart_ui()
        return ok, msg

    def _refresh_autostart_ui(self):
        """열려 있는 설정 화면의 표시를 다시 맞춘다.

        트레이에서 껐는데 설정 탭은 켜진 채로 남아 있으면, 거기서 다시
        누를 때 tk 가 먼저 체크를 뒤집어 놓기 때문에 정반대로 동작한다.
        """
        pane = None
        if getattr(self, "hub", None):
            pane = self.hub.panes.get("settings")
        pane = pane or getattr(self, "settings_win", None)
        if pane is not None and hasattr(pane, "show_autostart"):
            try:
                pane.show_autostart()
            except Exception:                               # noqa: BLE001
                pass

    def toggle_autostart(self):
        ok, msg = self.set_autostart(not self.settings.get("autostart"))
        # 트레이에서 누른 것은 화면에 아무 자국도 안 남는다. 잘못되면
        # 체크만 안 켜지고 끝이라 왜 안 되는지 알 길이 없다.
        if not ok or "작업 관리자" in msg:
            try:
                import tkinter.messagebox as mb
                mb.showwarning("포스크탑", msg)
            except Exception:                               # noqa: BLE001
                pass

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
        # 로그인을 지웠으면 부팅 등록도 뗀다. 안 그러면 컴퓨터를 켤 때마다
        # 로그인 창만 뜨고, 그걸 멈추려면 오히려 게임에 로그인부터 해야
        # 하는 처지가 된다. 다시 로그인하면 start_ui 에서 다시 붙는다.
        # (세션 만료는 다르다 - 계정은 살아 있으니 거기서는 떼지 않는다)
        autostart.disable()
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
            # 계정이 없어졌다. 이걸 안 떼면 다음 부팅부터 **없는 계정으로
            # 로그인하라는 창**이 뜨고, 그걸 멈출 방법이 프로그램 안에
            # 없다. 지우고 나가는 사람에게 남겨서는 안 되는 흔적이다.
            autostart.disable()
            self.notify(r.get("message", "탈퇴가 완료되었습니다."))
            self.root.after(1500, self.quit)
        run_async(self.root, lambda: self.api.delete_account(pw), done)

    # ---------------------------------------------------------------- 종료
    def quit(self):
        if self._quitting:
            return
        self._quitting = True
        if self._update_job is not None:
            try:
                self.root.after_cancel(self._update_job)
            except Exception:                               # noqa: BLE001
                pass
            self._update_job = None
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
    missing = PLAT.missing_requirement()
    if missing:
        # 여기서 조용히 죽으면 "눌렀는데 아무 일도 안 난다" 가 된다.
        # 무엇이 없는지, 무엇을 치면 되는지까지 말해 준다.
        config.log("필요한 것이 없습니다: %s" % missing)
        _tell_missing(missing)
        return
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


def _tell_missing(msg):
    try:
        import tkinter as tk
        from tkinter import messagebox
        PLAT.before_tk()
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("포스크탑", msg)
        r.destroy()
    except Exception:                                       # noqa: BLE001
        print(msg)
