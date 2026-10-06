# -*- coding: utf-8 -*-
"""프로그램 본체 — 로그인, 도감, 오버레이, 트레이, 야생 조우를 이어 붙인다."""
import os
import random
import sys
import tkinter as tk

from common import patchnotes                  # noqa: E402
from common import pokelogic as P              # noqa: E402
from common import tint as T                   # noqa: E402
from common.korean import natural              # noqa: E402
from common.version import VERSION             # noqa: E402

from . import api as apimod                    # noqa: E402
from . import autostart                     # noqa: E402
from . import config, single, sprite_cache, ui_loading, updater, walk_cache  # noqa: E402
from . import platform_os as PLAT              # noqa: E402
from . import ui_common as U                   # noqa: E402
from .overlay import Overlay, look_num         # noqa: E402
from .tray import Tray                         # noqa: E402
if sys.platform == "darwin" and PLAT.gui_ready():   # noqa: E402
    # 맥은 pystray 를 못 쓴다 (tray_mac 의 첫 주석을 보라).
    # pyobjc 가 없으면 여기서 ImportError 가 나서 앱이 아예 안 뜬다.
    # 그래서 먼저 물어보고, 없으면 main() 이 사람에게 말해 준다.
    from .tray_mac import Tray                 # noqa: E402,F811
from .desktop_battle import DesktopBattle       # noqa: E402
from . import ui_bag                          # noqa: E402
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
from .ui_update import NewVersionAsk, UpdateWindow  # noqa: E402
from .wild_ui import WildController            # noqa: E402
from . import raid_fx                          # noqa: E402
from . import mega_fx                          # noqa: E402


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
        self.tm_window = None
        self._learn_queue = []       # 배울지 물어볼 포켓몬
        self._gift_queue = []        # 알릴 선물
        self._gift_showing = False
        self._learn_asking = False
        self.friends_win = None
        self.guild_window = None
        # 길드 채팅 표시 (1.10.1). 남이 쓴 가장 최근 줄의 번호 - 본 데(settings.guildChatSeen)
        # 보다 뒤면 길드 탭에 점을 찍는다. 길드 탭이 떠 있지 않은 동안에는 여기서 웹소켓을
        # 하나 붙여 바로 안다 (guild_sock). 못 붙으면 동기화(90초)에 실려 오는 번호로 안다.
        self.guild_id = None
        self.guild_chat = 0
        self.guild_sock = None
        self._guild_dot = None
        self.dex_window = None
        self.settings_win = None
        # 마지막으로 있었던 일. 트레이 메뉴에서 보여준다.
        self.last_message = ""
        # 받아 놓고 아직 안 받아준 친구 요청 수.
        # 트레이에 숫자로 남긴다 - 화면에 아무 자국이 없다.
        self.friend_unseen = 0
        # 게시판 (1.8.0): 서버가 알려 준 가장 최근 공지 번호. 마지막으로 본
        # 번호(settings.noticeSeen)보다 크면 탭과 트레이에 표시한다.
        self.board_notice = 0
        self.board_window = None
        # 1.9.0: 가장 최근 패치노트 글 번호(settings.patchSeen 과 견준다)와
        # 안 본 게시판 알림(내 글의 댓글, 내 댓글의 답글). 알림은 친구 요청처럼
        # 운영체제 알림으로 한 번 알리고 트레이에 수로 남긴다.
        self.board_patch = 0
        self.board_unseen = 0
        self._board_seen = set()     # 이미 알린 알림 번호
        self._board_first = True
        self.mypage_window = None
        # 키스톤이 있나 (서버가 /api/me 에 실어 준다). 메가진화한 모습으로
        # 걸어다니게 할 수 있는지를 이걸로 본다 (1.8.0).
        self.keystone = False
        # 도감 업적 알림 (시즌 3)
        self._ach_queue = []
        self._ach_known = set()
        self._ach_showing = False
        # 메가진화 (시즌 3): 바탕화면의 빛나는 돌과 저절로 받은 스톤 알림
        from .bond_stone import BondStones
        self.bond_stones = BondStones(self)
        self._bond_queue = []
        self._bond_known = set()
        self._bond_showing = False
        # 이미 알린 요청. 폴링마다 같은 것을 또 띄우지 않기 위해서다.
        self._friend_seen = set()
        self._friend_first = True
        # 켜 둔 동안의 새 버전 확인.
        self._update_job = None
        self._update_asking = False
        self._anim_job = False
        self.arena = None
        self.battle = None
        # 레이드 (1.5.0). 탭·배틀 창·바탕화면 기둥.
        self.raid_window = None
        self.raid_battle = None
        self.raid_pillar = None
        self.user_id = None
        # 마지막으로 알린 회차. 같은 회차를 두 번 알리지 않는다.
        self._raid_told = None
        # 실시간 배틀 (1.6.0). 창 하나와, 초대를 물어보는 예약.
        self.live_battle = None
        # 내가 걸어 두고 아직 답을 못 받은 초대. 친구 탭이 이걸 보고
        # "수락을 기다리는 중" 을 띄운다 - 알림 한 줄은 금방 사라져서
        # 신청이 갔는지 안 갔는지 알 수가 없었다.
        self.live_pending = None
        self._live_job = None
        self._live_asking = False
        self._live_told = None
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
            me = None
            try:
                me = self.api.me()
            except Exception:
                pass
            # 메가진화한 모습으로 걷게 해 둔 포켓몬은 그 폼의 도트를 받는다 (1.8.0).
            # 키스톤은 방금 받은 me 로 본다 - 켜자마자의 첫 동기화에서도 맞게.
            stone = self.keystone
            if me is not None:
                stone = bool(((me.get("bond") or {}).get("keystone") or {}).get("has"))
            want = [(m.get("num"), T.skin(m)) for m in mons]
            want += self.dress_megas(mons, stone)
            paths = sprite_cache.ensure_many(self.api, want)
            # 걷는 도트도 같이 받아 둔다. 없는 종은 알아서 건너뛴다.
            walks = walk_cache.ensure_many(self.api, want)
            self.undress_missing(mons, paths, walks)
            if me and me.get("eggs"):
                # 알 그림도 여기서 받아 둔다 (tk 스레드에서 받으면 멈춘다)
                from . import eggs_ui
                eggs_ui.fetch_icons(self.api, me.get("eggs"))
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
                # 운영자가 보낸 선물. 서버가 /api/me 에서 이미 지급했고
                # 여기서는 알리기만 한다.
                self.announce_gifts(me.get("gifts") or [])
                # 도감 업적 (시즌 3). 선물처럼 연출이 끝난 뒤 한 창에 묶어 알린다.
                self.announce_achievements(
                    (me.get("achievements") or {}).get("unseen") or [])
                # 저절로 받은 메가스톤 (시즌 3). 업적과 같은 식으로 알린다.
                self.announce_bond((me.get("bond") or {}).get("got") or [])
                # 게시판의 새 공지 (1.8.0). 탭과 트레이 메뉴에 표시만 한다.
                # 1.9.0: 새 패치노트와 내 글·댓글에 달린 댓글도 같이 실려 온다.
                self.note_board(me.get("board"))
                self.keystone = bool(((me.get("bond") or {}).get("keystone") or {}).get("has"))
                self.user_id = (me.get("user") or {}).get("id", self.user_id)
                # 길드 채팅 (1.10.1): 안 읽은 줄이 있으면 길드 탭에 점
                self.note_guild(me.get("guild"))
                # 레이드 안내(announce_raid)는 1.10.0 에서 끊었다 - 레이드 탭을 뺐으므로
                # 빛기둥·결과 알림이 없는 탭을 가리키면 안 된다 (ui_hub.TABS 를 보라).
                # 실시간 배틀. 걸려온 초대·싸우던 판·안 본 결과가 있으면
                # 한 번 더 물어본다 (여기 실린 것은 요약이라 판 자체는 없다).
                live = me.get("live")
                if live and (live.get("invited") or live.get("state") == "fighting"
                             or live.get("unseen")):
                    self.check_live()
            if self.overlay:
                added = self.overlay.sync(mons or [], paths or {}, walks or {})
                # 빛나는 돌 표식. 새로 올라온 도트에도 붙어야 하므로 sync 뒤에.
                if me is not None and "bond" in me:
                    self.bond_stones.sync(me.get("bond"))
                else:
                    self.bond_stones.apply()
                if me is not None and "eggs" in me:
                    self.overlay.sync_eggs(me.get("eggs") or [])
                    self.announce_hatch(me.get("eggs") or [])
                self._prefetch_anims(mons or [])
                # 배틀 중에 새 도트가 생기면(창에서 바탕화면에 올렸을 때)
                # '항상 위' 맨 위에 놓여 체력바 층을 가린다. 체력바 틱은 더
                # 이상 순서를 올리지 않으므로(메뉴 위로 올라오던 원인이라
                # 뺐다) 새 창이 생긴 여기서 한 번 올린다.
                layer = (getattr(self.battle, "layer", None)
                         if self.battle else None)
                if added and layer:
                    try:
                        layer.raise_above()
                    except Exception:                       # noqa: BLE001
                        pass
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
            self._paint_notice()
            self._guild_dot = None
            self._paint_guild()
        self.hub.show(key)
        return self.hub.panes.get(key)

    def open_box(self):
        self.box_window = self._tab("box")

    def open_shop(self):
        self.shop_window = self._tab("shop")

    def open_bag(self):
        self.bag_window = self._tab("bag")

    def open_tms(self):
        # 기술머신은 가방 탭 안의 한 칸이다 (1.8.0, ui_bag_tabs)
        pane = self._tab("bag")
        self.bag_window = self.tm_window = pane
        if pane is not None:
            pane.show("tms")

    def open_board(self, post=None, kind=None):
        """게시판을 연다. post 가 있으면 그 글로, kind 가 있으면 그 칸으로."""
        pane = self.board_window = self._tab("board")
        if pane is None:
            return
        try:
            if post:
                pane.open_post(int(post))
            elif kind:
                pane.show_kind(kind)
        except Exception as e:                              # noqa: BLE001
            config.log("게시판 열기 오류: %s" % e)

    def open_patchnotes(self):
        """패치노트를 본다. 게시판의 패치노트 칸이다 (1.9.0 - 예전의 '새로운 기능' 창)."""
        self.open_board(kind="patch")

    def open_mypage(self):
        self.mypage_window = self._tab("my")

    # ---------------- 게시판의 새 공지 ----------------
    @property
    def notice_unseen(self):
        try:
            return int(self.board_notice or 0) > int(self.settings.get("noticeSeen") or 0)
        except (TypeError, ValueError):
            return False

    def note_notice(self, latest):
        """서버가 알려 준 가장 최근 공지 번호 (sync 에 실려 온다)."""
        try:
            latest = int(latest or 0)
        except (TypeError, ValueError):
            return
        if latest != self.board_notice:
            self.board_notice = latest
            self._paint_notice()

    def mark_notice_seen(self, latest=None):
        """게시판을 열어 공지를 봤다. 표시를 끈다."""
        try:
            n = max(int(latest or 0), int(self.board_notice or 0))
        except (TypeError, ValueError):
            return
        self.board_notice = max(self.board_notice, n)
        if n > int(self.settings.get("noticeSeen") or 0):
            self.settings["noticeSeen"] = n
            config.save_settings(self.settings)
        self._paint_notice()

    def _paint_notice(self):
        if self.hub:
            self.hub.set_badge("board", self.notice_unseen or self.patch_unseen
                               or self.board_unseen > 0)
        self.refresh_tray()

    # ---------------- 길드 채팅 표시 (1.10.1) ----------------
    # 1.10.0 에서는 길드 탭을 한 번 열어야 점이 찍혔다 (그 탭의 웹소켓이 듣는 것이라).
    # 프로그램을 켜고 다른 탭만 보던 사람은 채팅이 온 줄 몰랐다.
    def _guild_pane(self):
        """떠 있는 길드 탭. 없으면 None."""
        pane = self.hub.panes.get("guild") if self.hub else None
        return pane if pane is not None and getattr(pane, "alive", False) else None

    @property
    def guild_unseen(self):
        try:
            return int(self.guild_chat or 0) > int(self.settings.get("guildChatSeen") or 0)
        except (TypeError, ValueError):
            return False

    def note_guild(self, card):
        """동기화에 실려 온 길드 안내 ({"id", "chat"}). 길드가 없으면 None."""
        gid = (card or {}).get("id") if isinstance(card, dict) else None
        try:
            latest = int((card or {}).get("chat") or 0) if gid else 0
        except (TypeError, ValueError, AttributeError):
            latest = 0
        # 같은 길드면 웹소켓으로 먼저 안 번호가 더 클 수 있다 - 뒤로 물리지 않는다
        self.guild_chat = max(latest, self.guild_chat) if gid and gid == self.guild_id else latest
        self.guild_id = gid
        self._watch_guild(bool(gid))
        self._paint_guild()

    def note_guild_chat(self, mid):
        """방금 온 채팅 줄의 번호 (웹소켓). 남이 쓴 줄만 넘긴다."""
        try:
            mid = int(mid or 0)
        except (TypeError, ValueError):
            return
        if mid > self.guild_chat:
            self.guild_chat = mid
        self._paint_guild()

    def mark_guild_chat_seen(self, latest=None):
        """채팅 칸에서 거기까지 읽었다."""
        try:
            n = int(latest or 0)
        except (TypeError, ValueError):
            return
        if n > int(self.settings.get("guildChatSeen") or 0):
            self.settings["guildChatSeen"] = n
            config.save_settings(self.settings)
        self._paint_guild()

    def _paint_guild(self):
        """길드 탭의 점: 안 읽은 채팅이 있고, 지금 길드 탭을 보고 있지 않을 때."""
        if not self.hub:
            return
        pane = self._guild_pane()
        looking = False
        if pane is not None:
            try:
                looking = bool(pane.pane_visible())
            except Exception:                               # noqa: BLE001
                looking = False
        on = bool(self.guild_unseen and not looking)
        if on == self._guild_dot:
            return
        self._guild_dot = on
        try:
            self.hub.set_badge("guild", on)
        except Exception:                                   # noqa: BLE001
            pass

    def _watch_guild(self, on):
        """길드 탭이 안 떠 있는 동안 채팅이 오는지 듣는다. 탭이 뜨면 그 탭의 웹소켓이 듣는다
        (한 PC 에서 연결을 둘씩 쓰지 않는다 - 서버는 한 사람에 셋까지만 받는다)."""
        if not on or self._guild_pane() is not None:
            return self._stop_guild_sock()
        if self.guild_sock is not None and getattr(self.guild_sock, "gave_up", None):
            self._stop_guild_sock()
        if self.guild_sock is None:
            try:
                from . import ui_guild
                self.guild_sock = ui_guild.make_socket(self, self._on_guild_ws)
            except Exception:                               # noqa: BLE001
                self.guild_sock = None

    def _stop_guild_sock(self):
        sock, self.guild_sock = self.guild_sock, None
        if sock is not None:
            try:
                sock.stop()
            except Exception:                               # noqa: BLE001
                pass

    def _on_guild_ws(self, ev):
        t = (ev or {}).get("t")
        if t == "chat":
            m = ev.get("m") or {}
            if not m.get("system") and m.get("userId") != self.user_id:
                self.note_guild_chat(m.get("id"))
        elif t == "left":
            self._stop_guild_sock()          # 길드에서 나왔다. 다음 동기화가 정리한다

    # ---------------- 새 패치노트 (1.9.0) ----------------
    @property
    def patch_unseen(self):
        try:
            return int(self.board_patch or 0) > int(self.settings.get("patchSeen") or 0)
        except (TypeError, ValueError):
            return False

    def mark_patch_seen(self, latest=None):
        """게시판의 패치노트 칸을 열어 봤다. 표시를 끈다."""
        try:
            n = max(int(latest or 0), int(self.board_patch or 0))
        except (TypeError, ValueError):
            return
        self.board_patch = max(self.board_patch, n)
        if n > int(self.settings.get("patchSeen") or 0):
            self.settings["patchSeen"] = n
            config.save_settings(self.settings)
        self._paint_notice()

    def note_board(self, card):
        """동기화에 실려 온 게시판 소식 - 새 공지·새 패치노트·내 알림."""
        card = card or {}
        self.note_notice(card.get("notice"))
        try:
            patch = int(card.get("patch") or 0)
        except (TypeError, ValueError):
            patch = 0
        changed = patch != self.board_patch
        self.board_patch = max(self.board_patch, patch)
        if "patchSeen" not in self.settings and patch:
            # 처음 깐 사람에게 옛 패치노트 마흔 개가 다 '새 글' 일 수는 없다.
            # 지금 것까지는 본 것으로 친다. 방금 갈아탄 사람은 이번 판의 글
            # 하나만 새 글이다 (_tell_patchnotes_once 가 표시해 둔다).
            fresh = bool(getattr(self, "_patch_fresh", False))
            self.settings["patchSeen"] = patch - 1 if fresh else patch
            config.save_settings(self.settings)
            changed = True
        self.announce_board(card.get("notify"))
        if changed:
            self._paint_notice()

    def set_board_unseen(self, n):
        """화면이 방금 서버에서 들은 안 본 알림 수 (마이페이지). 다음 동기화를
        기다리지 않고 탭의 점과 트레이의 수를 바로 맞춘다."""
        try:
            n = max(0, int(n or 0))
        except (TypeError, ValueError):
            return
        if n != self.board_unseen:
            self.board_unseen = n
            self._paint_notice()

    def announce_board(self, notify):
        """내 글에 댓글이, 내 댓글에 답글이 달렸다. 친구 요청과 같은 식으로 알린다.

        **켤 때 이미 쌓여 있던 것은 수만 한 번 알린다** (announce_friends 와 같은
        이유). 그 뒤에 새로 오는 것은 누가 무슨 글에 달았는지까지 알려 준다.
        글을 열어 보면 서버가 본 것으로 치므로 다음 동기화에 수가 줄어든다.
        """
        if not isinstance(notify, dict):
            return
        items = [x for x in (notify.get("items") or []) if x.get("id") is not None]
        try:
            count = int(notify.get("count") or 0)
        except (TypeError, ValueError):
            count = len(items)
        if count != self.board_unseen:
            self.board_unseen = count
            self._paint_notice()
        fresh = [x for x in items if x["id"] not in self._board_seen]
        self._board_seen.update(x["id"] for x in items)
        first, self._board_first = self._board_first, False
        if not fresh:
            return
        where = "게시판이나 마이페이지에서 볼 수 있습니다."
        if first and count > 1:
            self.toast("게시판에 새 댓글 %d개가 있습니다" % count, where, kind="board")
            return
        if len(fresh) == 1:
            x = fresh[0]
            what = "답글" if x.get("kind") == "reply" else "댓글"
            self.toast("%s 님이 %s을 남겼습니다" % (x.get("actor") or "?", what),
                       "%s — %s" % (x.get("title") or "", x.get("snippet") or ""),
                       kind="board")
        else:
            names = []
            for x in fresh:
                if x.get("actor") and x["actor"] not in names:
                    names.append(x["actor"])
            self.toast("게시판에 새 댓글 %d개가 달렸습니다" % len(fresh),
                       ", ".join(names[:4]), kind="board")
        self.notify("게시판에 새 댓글이 달렸습니다 - %d개" % len(fresh))

    # ---------------- 배우려고 기다리는 기술 ----------------
    # 레벨업으로 배울 기술이 생겼는데 자리가 네 개 다 찼을 때다. 서버는
    # 밀어내지 않고 적어만 두고(pokemon.pending), 여기서 물어본다.
    #
    # **배틀이 끝난 뒤에 띄운다.** 싸우는 도중에 창이 튀어나오면 연출이
    # 끊기고, 자동으로 도는 배틀이라 사용자가 화면을 안 보고 있을 수도 있다.
    def want_learn(self, mon_id, name=""):
        if not mon_id:
            return
        for i, (mid, _n) in enumerate(self._learn_queue):
            if mid == mon_id:
                return              # 이미 줄에 있다
        self._learn_queue.append((int(mon_id), name or "포켓몬"))
        self.root.after(900, self._ask_learn)

    def _ask_learn(self):
        if self._learn_asking or self._quitting or not self._learn_queue:
            return
        # 배틀이나 진화 연출 중이면 기다린다. 창이 겹치면 무엇을 고르는
        # 중인지 알 수 없다.
        if (self.battle or self.arena or getattr(self, "evolving", None)
                or getattr(self, "gym_battle", None)):
            return self.root.after(1500, self._ask_learn)
        self._learn_asking = True
        mon_id, name = self._learn_queue[0]

        def work():
            return self.api.pokemon()

        def done(r, err):
            if err or self._quitting:
                self._learn_asking = False
                self._learn_queue.pop(0) if self._learn_queue else None
                return
            mons = r if isinstance(r, list) else (r or {}).get("pokemon") or []
            mon = next((m for m in mons if m.get("id") == mon_id), None)
            pending = list((mon or {}).get("pending") or [])
            moves = list((mon or {}).get("moves") or [])
            if not mon or not pending:
                self._learn_asking = False
                if self._learn_queue:
                    self._learn_queue.pop(0)
                return self.root.after(200, self._ask_learn)
            nick = (mon.get("info") or {}).get("name") or name
            self._ask_one(mon_id, nick, pending, moves)

        run_async(self.root, work, done)

    def _ask_one(self, mon_id, name, pending, moves):
        """기다리는 것 하나를 물어본다. 여럿이면 하나씩 이어서."""
        from .ui_learn import ask_forget

        move = pending[0]
        PLAT.activate()
        try:
            pick = ask_forget(self.root, name, move, moves, self.dex)
        except Exception as e:                              # noqa: BLE001
            config.log("기술 배우기 창 오류: %s" % e)
            self._learn_asking = False
            if self._learn_queue:
                self._learn_queue.pop(0)
            return
        if pick is None:
            # 그냥 닫았다. 서버에 아무것도 안 보낸다 - 다음에 다시 묻는다.
            self._learn_asking = False
            if self._learn_queue:
                self._learn_queue.pop(0)
            return

        self._send_learn(mon_id, name, move, pick)

    def _send_learn(self, mon_id, name, move, pick):
        """고른 답을 서버에 보낸다. **끝날 때까지 기다림 창을 띄운다.**

        전에는 창을 닫자마자 뒤에서 보내고, 실패하면 로그에만 적었다. 인터넷이
        느리면 15초 만에 끊겨서, 사용자는 기술이 그냥 안 배워진 줄 알았다.
        이제 끝날 때까지 기다리고(api.LEARN_TIMEOUT), 실패하면 _learn_failed 가
        정말 안 배워졌는지 서버에 다시 확인한다.
        """
        wait = ui_loading.Popup(self.root, "기술을 배우는 중" if pick != "" else "정리하는 중",
                                slow=ui_loading.LEARN_SLOW)

        def work():
            return self.api.learn_pending(mon_id, move, pick,
                                          skip=(pick == ""))

        def done(r, err):
            wait.close()
            if err:
                config.log("기술 배우기 실패: %s" % err)
                return self._learn_failed(mon_id, name, move, pick, err)
            self._learn_asking = False
            if r.get("message"):
                self.notify(r["message"])
            self._learn_next(r.get("pending") or [])

        run_async(self.root, work, done)

    def _learn_next(self, rest):
        """한 마리를 끝냈다. 남은 게 있으면 이어서 묻고, 없으면 다음 포켓몬."""
        self._learn_asking = False
        if rest:
            # 한 번에 여러 개가 기다릴 수 있다. 이어서 묻는다.
            return self.root.after(400, self._ask_learn)
        if self._learn_queue:
            self._learn_queue.pop(0)
        self.sync()
        self.root.after(400, self._ask_learn)

    def _learn_failed(self, mon_id, name, move, pick, err):
        """응답을 못 받았다. **서버에서는 이미 배웠을 수도 있다** - 먼저 확인한다.

          · 기다리던 목록에서 빠졌으면 처리된 것이다. 결과를 알린다.
          · 아직 기다리는 중이면 다시 할지 묻는다. 안 하면 그대로 남겨 둔다
            (다음 배틀 뒤에, 또는 포켓몬 관리의 기술 떠올리기에서 무료로 배운다).
          · 확인도 안 되면(인터넷이 끊겼다) 그렇게 알리고 남겨 둔다.
        """
        wait = ui_loading.Popup(self.root, "결과를 확인하는 중", slow=ui_loading.LEARN_SLOW)
        kr = self.dex.move_name(move) if self.dex else move

        def done(r, e2):
            wait.close()
            mons = r if isinstance(r, list) else (r or {}).get("pokemon") or []
            mon = next((m for m in mons if m.get("id") == mon_id), None)
            if e2 or mon is None:
                self._learn_asking = False
                if self._learn_queue:
                    self._learn_queue.pop(0)
                return self.notify(natural(
                    "인터넷 연결이 불안정해 %s을(를) 배우지 못했습니다. 연결되면 포켓몬 관리의 "
                    "'기술 떠올리기' 에서 무료로 배울 수 있습니다." % kr))
            pending = list(mon.get("pending") or [])
            if move not in pending:
                done_text = ("%s은(는) %s을(를) 배웠다!" % (name, kr)) if move in (mon.get("moves") or []) \
                    else ("%s은(는) %s을(를) 배우지 않았다." % (name, kr))
                self.notify(natural(done_text))
                return self._learn_next(pending)
            PLAT.activate()
            again = confirm(self.root, "기술 배우기",
                            natural("인터넷 연결이 불안정해 %s을(를) 배우지 못했습니다. "
                                    "다시 시도할까요?" % kr),
                            danger=False, ok_text="다시 시도")
            if again:
                return self._send_learn(mon_id, name, move, pick)
            self._learn_asking = False
            if self._learn_queue:
                self._learn_queue.pop(0)
            self.notify(natural("%s은(는) 나중에 포켓몬 관리의 '기술 떠올리기' 에서 무료로 "
                                "배울 수 있습니다." % kr))

        run_async(self.root, lambda: self.api.pokemon(), done)

    def open_friends(self):
        self.friends_win = self._tab("friends")

    def open_guild(self):
        self.guild_window = self._tab("guild")

    def open_dex(self):
        self.dex_window = self._tab("dex")

    def open_settings(self):
        """설정은 마이페이지의 톱니바퀴 안에 있다 (1.9.0)."""
        pane = self.mypage_window = self._tab("my")
        if pane is not None:
            pane.show_settings()
            self.settings_win = pane.settings

    def open_gym(self):
        self.gym_window = self._tab("gym")

    def open_raid(self):
        self.raid_window = self._tab("raid")

    # ---------------- 실시간 배틀 ----------------
    # 친구끼리 **둘 다 켜 있을 때만** 하는 1:1. 초대를 알아차리는 가장 늦은
    # 때가 다음 동기화(90초)라, 초대는 그보다 넉넉히 살아 있다(서버의
    # LIVE_INVITE_SEC). 친구 탭을 열어 두면 거기서 자주 물어본다.
    def live_invite(self, uid, name=""):
        """친구에게 실시간 배틀을 건다."""
        if self.live_battle:
            return self.live_battle.focus()

        def done(r, err):
            if err:
                return self.notify(getattr(err, "message", str(err)))
            self.notify("%s 님에게 실시간 배틀을 신청했습니다. 수락하면 바로 시작합니다."
                        % (name or "상대"))
            # 폴링을 기다리지 않고 그 자리에서 친구 탭에 표시한다.
            if isinstance(r, dict) and r.get("state") == "invited":
                self.live_pending = r
            self.live_watch(2000)
        run_async(self.root, lambda: self.api.live_invite(uid), done)

    def live_cancel(self, then=None):
        """걸어 둔 초대를 거둬들인다 (서버에서는 answer(ok=False) 가 취소다)."""
        m = self.live_pending
        if not m:
            return
        mid = m.get("id")

        def done(r, err):
            self.live_pending = None
            if err:
                self.notify(getattr(err, "message", str(err)))
            if callable(then):
                then()
        run_async(self.root, lambda: self.api.live_answer(mid, False), done)

    def live_watch(self, ms=3000):
        """잠깐 자주 물어본다 (초대를 걸어 뒀거나 친구 탭을 보고 있을 때)."""
        if self._live_job is not None:
            try:
                self.root.after_cancel(self._live_job)
            except Exception:                               # noqa: BLE001
                pass
        self._live_job = self.root.after(max(1000, ms), self.check_live)

    def check_live(self):
        """지금 내 실시간 배틀 상태를 한 번 물어본다."""
        self._live_job = None
        if not self.api or self._quitting:
            return

        def done(r, err):
            if err or not isinstance(r, dict):
                return
            m = r.get("match")
            self.announce_live(m, int(r.get("unseen") or 0))
            # 아직 답을 기다리는 초대가 있으면 계속 본다
            if m and m.get("state") == "invited":
                self.live_watch(3000)
        run_async(self.root, lambda: self.api.live(), done)

    def announce_live(self, match, unseen=0):
        """/api/live 나 /api/me 가 알려준 상태에 따라 화면을 띄운다."""
        self.live_pending = (match if match and match.get("state") == "invited"
                             and match.get("mine") else None)
        if not match:
            if unseen and not self.live_battle:
                self.notify("실시간 배틀 결과가 도착했습니다.")
            return
        state = match.get("state")
        if state == "fighting":
            return self.open_live_battle(match)
        if state == "invited" and not match.get("mine"):
            return self._ask_live(match)
        if state == "done" and match.get("outcome") and not self.live_battle:
            self.open_live_battle(match)

    def _ask_live(self, match):
        """걸려온 초대를 물어본다. 한 번에 하나만."""
        if self._live_asking or self.live_battle:
            return
        mid = match.get("id")
        if mid is None or mid == self._live_told:
            return
        self._live_asking = True
        self._live_told = mid
        try:
            from .ui_box import confirm
            PLAT.activate()
            ok = confirm(self.root, "실시간 배틀",
                         "%s 님이 실시간 배틀을 신청했습니다.\n"
                         "수락하면 바로 시작합니다. 양쪽 포켓몬은 모두 Lv.%d 로 "
                         "맞춰집니다." % (match.get("foeName") or "친구",
                                          match.get("level") or 50),
                         danger=False, ok_text="수락")
        except Exception:                                   # noqa: BLE001
            ok = False
        finally:
            self._live_asking = False

        def done(r, err):
            if err:
                return self.notify(getattr(err, "message", str(err)))
            if ok and isinstance(r, dict) and r.get("state") == "fighting":
                self.open_live_battle(r)
        run_async(self.root, lambda: self.api.live_answer(mid, ok), done)

    def open_live_battle(self, match):
        """실시간 배틀 창을 띄운다 (이미 떠 있으면 앞으로)."""
        if not match:
            return None
        if self.live_battle:
            self.live_battle.focus()
            return self.live_battle
        from .ui_live_battle import LiveBattleWindow
        PLAT.activate()
        self.live_battle = LiveBattleWindow(self, match)
        return self.live_battle

    def resume_live(self):
        """싸우던 판이 남아 있으면 창을 다시 띄운다."""
        if self.live_battle:
            return self.live_battle.focus()
        self.check_live()

    # ---------------- 레이드 ----------------
    def open_raid_battle(self, room):
        """판이 열렸다. 배틀 창을 띄운다 (이미 떠 있으면 앞으로)."""
        if not room or (room.get("state") or "") != "fighting":
            return None
        if self.raid_battle:
            self.raid_battle.focus()
            return self.raid_battle
        from .ui_raid_battle import RaidBattleWindow
        PLAT.activate()
        self.raid_battle = RaidBattleWindow(self, room)
        return self.raid_battle

    def resume_raid(self):
        """싸우던 판이 남아 있으면 창을 다시 띄운다 (트레이·기둥에서)."""
        if self.raid_battle:
            return self.raid_battle.focus()

        def done(r, err):
            if err or not r:
                return self.open_raid()
            if (r.get("state") or "") == "fighting":
                return self.open_raid_battle(r)
            self.open_raid()
        run_async(self.root, lambda: self.api.raid_room(), done)

    def announce_raid(self, card):
        """/api/me 가 실어 준 레이드 안내. 폴링을 새로 두지 않는다.

        · 회차가 가까우면 바탕화면에 빛기둥을 세운다 (raid_fx)
        · 싸우던 판이 있으면 배틀 창을 다시 띄운다
        · 끝났는데 아직 안 본 결과가 있으면 한 번 알린다
        """
        if not card:
            return self._drop_pillar()
        nxt = card.get("next") or {}
        left = int(nxt.get("leftSec") or 0)
        soon = bool(nxt) and (card.get("open") or 0 < left <= raid_fx.SHOW_BEFORE)
        key = nxt.get("session")
        # 한 번 눌러서 치운 회차는 다시 안 띄운다. 다음 회차가 되면 열쇠가
        # 달라지므로 저절로 풀린다.
        dismissed = key and key == (self.settings.get("raidPillarSeen") or "")
        if soon and not dismissed and not card.get("playedToday") \
                and not card.get("room"):
            first = self.raid_pillar is None
            self._raise_pillar(nxt)
            if first and key and key != self._raid_told:
                self._raid_told = key
                name = nxt.get("kr") if nxt.get("revealed") else "전설의 포켓몬"
                self.notify("%s 레이드가 곧 시작됩니다. 바탕화면의 빛기둥을 눌러 참가하세요."
                            % name)
        else:
            self._drop_pillar()
        if card.get("room") and not self.raid_battle:
            self.resume_raid()
        n = int(card.get("unseen") or 0)
        if n and not self.raid_battle:
            self.notify("레이드 결과가 도착했습니다. 레이드 탭에서 확인해 보세요.")

    def _raise_pillar(self, nxt):
        if not self.overlay:
            return
        if self.raid_pillar is None:
            try:
                self.raid_pillar = raid_fx.RaidPillar(self, nxt, self._pillar_clicked)
            except Exception:                               # noqa: BLE001
                import traceback
                config.log("레이드 기둥을 못 세웠습니다:\n%s" % traceback.format_exc())
                self.raid_pillar = None
            return
        self.raid_pillar.update(nxt)

    def _pillar_clicked(self):
        """빛기둥을 눌렀다. **치우고 그 회차에는 다시 안 띄운다.**

        누른 사람은 이미 레이드를 보러 가는 중이다. 거기서 안 하기로 했다면
        더더욱 바탕화면에 계속 떠 있을 이유가 없다.
        """
        key = (self.raid_pillar.card or {}).get("session") if self.raid_pillar else None
        if key:
            self.settings["raidPillarSeen"] = key
            config.save_settings(self.settings)
        self._drop_pillar()
        self.resume_raid()

    def _drop_pillar(self):
        if self.raid_pillar is not None:
            try:
                self.raid_pillar.destroy()
            except Exception:                               # noqa: BLE001
                pass
            self.raid_pillar = None

    # ---------------- 유저 배틀 ----------------
    # 대전은 비동기다. 상대가 켜져 있지 않아도 그 사람의 지금 파티를
    # 가져와 붙인다. 그래서 누르면 그 자리에서 끝나고, 상대는 다음에
    # 켤 때 결과를 받는다.
    def pvp_random(self, on_done=None):
        self._pvp(lambda: self.api.pvp_random(), on_done)

    def pvp_challenge(self, uid, on_done=None):
        self._pvp(lambda: self.api.pvp_challenge(uid), on_done)

    def _pvp(self, fn, on_done=None):
        """대전을 건다. on_done(결과, 오류 문구) 는 **어떤 길로 끝나든 한 번** 부른다.

        대전·랭킹 창은 누르는 순간 '상대를 찾는 중...' 을 적는다. 끝났다는
        소식을 못 받으면 그 글이 영영 남는다 (1.4.0 까지 그랬다 - 창이 2.5초
        뒤에 목록만 다시 불러오고 글은 안 지웠다).
        """
        def tell(r, why):
            if on_done:
                try:
                    on_done(r, why)
                except Exception:                           # noqa: BLE001
                    pass
        if getattr(self, "_pvp_busy", False):
            return tell(None, "이미 상대를 찾는 중입니다.")
        if self.arena:
            return tell(None, "보고 있는 대전이 끝난 뒤에 해주세요.")
        if self.battle:
            self.notify("야생 배틀이 끝난 뒤에 해주세요.")
            return tell(None, "야생 배틀이 끝난 뒤에 해주세요.")
        self._pvp_busy = True
        # 상대를 찾고 판을 다 계산해서 받기까지 몇 초 걸린다. 그동안
        # 화면에 아무 변화가 없으면 눌린 건지 아닌지를 알 수가 없다.
        wait = ui_loading.Popup(self.root, "상대를 찾는 중")

        def done(r, err):
            self._pvp_busy = False
            wait.close()
            if err:
                msg = getattr(err, "message", str(err))
                self.notify(msg)
                return tell(None, msg)
            self.show_pvp_result(r)
            tell(r, None)
        run_async(self.root, fn, done)

    # ---------------- 진화 알림 ----------------
    def show_evolutions(self, infos, parent=None):
        """사냥이 아닌 길(가방의 이상한사탕·진화의 돌, 관장 배틀)로 진화했을 때.

        바탕화면에 있는 포켓몬은 그 자리에서 진화 연출을 한다(야생 배틀 뒤와
        같은 것). 박스에 있어서 연출할 도트가 없으면 전/후 도트를 보여 주는
        창을 띄운다. 1.4.0 까지 가방은 창만 띄워서 바탕화면에서는 아무 일도
        안 일어났다.
        """
        from .desktop_battle import play_evolutions
        infos = [i for i in (infos or []) if i]
        if not infos:
            return
        ov = self.overlay
        desk, box = [], []
        for i in infos:
            pet = ov.pets.get(i.get("pokemonId")) if ov is not None else None
            (desk if pet is not None and not ov.hidden else box).append(i)
        for i in box:
            try:
                from .ui_bag import announce_evolve
                announce_evolve(parent or self.root, self, i)
            except Exception as e:                          # noqa: BLE001
                config.log("진화 창을 못 띄웠습니다: %s" % e)
            if i.get("pendingIds"):
                self.want_learn(i.get("pokemonId"), i.get("toKr", ""))
        if desk:
            play_evolutions(self, desk)

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
                    nums = [(x.get("num"), T.skin(x)) for x in
                            (e.get("me") or []) + (e.get("foe") or [])]
                    break
            paths = sprite_cache.ensure_many(
                self.api, [(n, s) for n, s in nums if n])
            walks = walk_cache.ensure_many(self.api, [(n, s) for n, s in nums if n])
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
        if mine.get("rpDelta"):
            bits.append("RP %+d" % mine["rpDelta"])
        elif mine.get("delta") and "rp" not in mine:
            bits.append("%+d점" % mine["delta"])
        if mine.get("myLeft") is not None:
            bits.append("%d대 %d 남음"
                        % (mine.get("myLeft", 0), mine.get("foeLeft", 0)))
        self.notify(head + ("  (" + " · ".join(bits) + ")" if bits else ""))
        self.sync()

    def announce_hatch(self, eggs):
        """부화한 알을 하나씩 보여준다. 배틀·진화·선물 창이 끝난 뒤에.

        서버는 알릴 때까지(seen) 계속 실어 보낸다. 보여주는 중인 알은 다음
        동기화가 또 실어 와도 한 번만 띄운다.
        """
        showing = getattr(self, "_hatch_showing", None)
        if showing is None:
            showing = self._hatch_showing = set()
        for e in eggs or []:
            if not e.get("hatched") or e.get("id") in showing:
                continue
            showing.add(e.get("id"))
            self.root.after(300, lambda egg=e: self._show_hatch(egg))

    def _show_hatch(self, egg):
        if self._quitting or not self.api:
            return
        if (self.battle or self.arena or getattr(self, "evolving", None)
                or getattr(self, "_gift_showing", False)
                or getattr(self, "_hatching_now", False)):
            return self.root.after(1500, lambda: self._show_hatch(egg))
        from . import eggs_ui
        self._hatching_now = True
        eid = egg.get("id")

        def finished():
            self._hatching_now = False
            run_async(self.root, lambda: self.api.egg_seen(eid),
                      lambda _r, err: self._hatch_seen(eid, err))

        def reveal():
            if self.overlay:
                self.overlay.eggs_done.add(eid)
            pet = self.overlay.eggs.pop(eid, None) if self.overlay else None
            if pet is not None:
                try:
                    pet.destroy()
                except Exception:                          # noqa: BLE001
                    pass
            try:
                win = eggs_ui.announce_hatch(self.root, self, egg,
                                             on_close=finished)
                win.lift()
            except Exception as ex:                        # noqa: BLE001
                config.log("부화 창을 못 띄웠습니다: %s" % ex)
                finished()
            self.sync()

        pet = self.overlay.eggs.get(eid) if self.overlay else None
        if pet is not None and not self.overlay.hidden:
            pet.hatch(reveal)
        else:
            reveal()

    def _hatch_seen(self, eid, err):
        if err:
            # 못 알렸으면 다음 동기화 때 다시 보여준다
            getattr(self, "_hatch_showing", set()).discard(eid)

    def announce_gifts(self, gifts):
        """선물이 왔다고 알린다. 창은 배틀·진화가 끝난 뒤에 띄운다.

        **창이 떠 있는 동안 다음 sync 가 와도 두 번 안 뜬다.** 서버가
        이미 claimed 로 찍었으므로 그 다음 응답에는 안 실려 온다. 여기서는
        띄우는 중인지만 보면 된다 - 같은 선물을 두 창이 물고 있으면
        뒤엣것이 앞엣것을 덮는다.
        """
        if not gifts or self._gift_showing:
            return
        self._gift_queue.extend(gifts)
        self._show_gifts()

    def _show_gifts(self):
        if self._gift_showing or self._quitting or not self._gift_queue:
            return
        # 배틀이나 진화 연출 중이면 기다린다. 그 위에 겹치면 무엇이
        # 일어났는지 안 읽힌다.
        if self.battle or self.arena:
            return self.root.after(1500, self._show_gifts)
        got, self._gift_queue = list(self._gift_queue), []
        self._gift_showing = True
        try:
            PLAT.activate()
            ui_bag.announce_gifts(self.root, self, got)
        except Exception as e:                              # noqa: BLE001
            config.log("선물 알림 오류: %s" % e)
        finally:
            self._gift_showing = False
        # 창이 떠 있는 동안 새로 온 것이 있으면 이어서 보여준다.
        if self._gift_queue:
            self.root.after(400, self._show_gifts)

    def announce_achievements(self, items):
        """새로 달성한 업적을 알린다. **운영체제 알림은 쓰지 않는다** - 게임
        안의 일이라서다(toast 의 규칙). 선물처럼 배틀·진화가 끝난 뒤 작은
        창으로, 여럿이면 한 창에 묶는다.

        다 보여준 뒤에 seen 을 부른다. 그전까지는 다음 동기화에도 실려 오므로,
        같은 것을 두 번 띄우지 않게 이미 받은 열쇠를 기억한다.
        """
        fresh = [a for a in items if a.get("key") not in self._ach_known]
        if not fresh:
            return
        self._ach_known.update(a["key"] for a in fresh)
        self._ach_queue.extend(fresh)
        self._show_achievements()

    def _show_achievements(self):
        if self._ach_showing or self._quitting or not self._ach_queue:
            return
        if self.battle or self.arena or self._gift_showing:
            return self.root.after(1500, self._show_achievements)
        got, self._ach_queue = list(self._ach_queue), []
        self._ach_showing = True
        try:
            from . import ui_achievements
            PLAT.activate()
            ui_achievements.announce(self.root, self, got)
        except Exception as e:                              # noqa: BLE001
            config.log("업적 알림 오류: %s" % e)
        finally:
            self._ach_showing = False
        if self.api:
            run_async(self.root, lambda: self.api.achievements_seen(),
                      lambda _r, _e: None)
        if self._ach_queue:
            self.root.after(400, self._show_achievements)

    def announce_bond(self, items):
        """저절로 받은 메가스톤을 알린다 (bond_stone.announce_got). 업적과 같이
        배틀·진화·선물 창이 끝난 뒤에, 다 보여 준 다음 seen 을 부른다."""
        fresh = [g for g in items if g.get("pokemon") not in self._bond_known]
        if not fresh:
            return
        self._bond_known.update(g["pokemon"] for g in fresh)
        self._bond_queue.extend(fresh)
        self._show_bond()

    def _show_bond(self):
        if self._bond_showing or self._quitting or not self._bond_queue:
            return
        if self.battle or self.arena or self._gift_showing or self._ach_showing:
            return self.root.after(1500, self._show_bond)
        got, self._bond_queue = list(self._bond_queue), []
        self._bond_showing = True
        try:
            from . import bond_stone
            PLAT.activate()
            win = bond_stone.announce_got(self.root, got)
            if win is not None:
                win.grab_set()
                self.root.wait_window(win)
        except Exception as e:                              # noqa: BLE001
            config.log("메가스톤 알림 오류: %s" % e)
        finally:
            self._bond_showing = False
        if self.api:
            api = self.api
            ids = [g["pokemon"] for g in got]
            run_async(self.root, lambda: [api.bond_seen(i) for i in ids],
                      lambda _r, _e: None)
        if self._bond_queue:
            self.root.after(400, self._show_bond)

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

    def close_windows(self):
        """열려 있는 창을 전부 닫는다. 로그아웃·탈퇴·종료 때 부른다."""
        self.close_arena()
        gb = getattr(self, "gym_battle", None)
        if gb:
            try:
                gb.close()          # 판은 서버에 남는다. 다시 들어오면 이어서 한다
            except Exception:                               # noqa: BLE001
                pass
            self.gym_battle = None
        if self.hub:
            try:
                self.hub.close()
            except Exception:                               # noqa: BLE001
                pass
            self.hub = None
        lv = getattr(self, "live_battle", None)
        if lv:
            try:
                lv.close()          # 판은 서버에 남는다
            except Exception:                               # noqa: BLE001
                pass
            self.live_battle = None
        if self._live_job is not None:
            try:
                self.root.after_cancel(self._live_job)
            except Exception:                               # noqa: BLE001
                pass
            self._live_job = None
        rb = getattr(self, "raid_battle", None)
        if rb:
            try:
                rb.close()          # 판은 서버에 남는다. 다시 들어오면 이어서 한다
            except Exception:                               # noqa: BLE001
                pass
            self.raid_battle = None
        self._drop_pillar()
        for name in ("box_window", "shop_window", "bag_window",
                     "friends_win", "dex_window", "settings_win",
                     "raid_window", "board_window", "mypage_window"):
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
        # 메가진화한 모습으로 걷기 (1.8.0). 될 수 있는 포켓몬에게만 줄이 생긴다.
        mega = self.mega_menu_row(pet)
        # 이로치는 색을 고를 수 있다 (1.8.0). 모든 사람의 화면에 그 색으로 나온다.
        tint = ({"text": "색 고르기...", "command": lambda: self.open_tint(pet)}
                if pet.mon.get("shiny") and (pet.id or 0) > 0 else None)
        if not PLAT.NATIVE_MENU:
            # 맥. tk.Menu 는 NSMenu 라 여는 순간 앱이 죽는다.
            rows = [
                {"text": title, "enabled": False},
                None,
                {"text": "정보 보기", "command": lambda: self.pet_open(pet)},
                {"text": "박스로 거두기",
                 "command": lambda: self._recall(pet.id)},
            ]
            if mega:
                rows.append(mega)
            if tint:
                rows.append(tint)
            rows += [
                None,
                {"text": "포켓몬 관리...", "command": self.open_box},
                None,
                {"text": "종료", "command": self.quit},
            ]
            U.PopupMenu(self.root, rows, event.x_root, event.y_root,
                        width=230 if mega else 190)
            return
        m = tk.Menu(self.root, tearoff=0, bg=U.BG2, fg=U.FG,
                    activebackground=U.BG4, activeforeground=U.FG,
                    bd=0, font=U.FONT_S)
        m.add_command(label=title, state="disabled")
        m.add_separator()
        m.add_command(label="정보 보기", command=lambda: self.pet_open(pet))
        m.add_command(label="박스로 거두기", command=lambda: self._recall(pet.id))
        if mega:
            m.add_command(label=mega["text"], command=mega.get("command"),
                          state="normal" if mega.get("enabled", True) else "disabled")
        if tint:
            m.add_command(label=tint["text"], command=tint["command"])
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

    def float_over_pet(self, pid, text, color="#7bffa0", ms=1100):
        """바탕화면의 그 포켓몬 머리 위에 글씨를 잠깐 띄운다 (배틀 밖에서).

        배틀 중에는 배틀이 가진 이펙트 층에 쓴다. 여기는 층이 없을 때 - 싸우지
        않고 잡아서 경험치를 받았을 때(1.8.1) - 잠깐 층을 열었다 닫는다.
        """
        ov = self.overlay
        pet = ov.pets.get(pid) if ov else None
        if pet is None or not text:
            return False
        from .fx_layer import FloatText, open_layer
        try:
            layer = open_layer(self.root, ov.area())
        except Exception:                                   # noqa: BLE001
            layer = None
        if not layer:
            return False
        try:
            FloatText(layer, pet.x + pet.fw / 2.0, pet.y - 6, text, color, ms=ms)
        except Exception:                                   # noqa: BLE001
            layer.destroy()
            return False

        def gone():
            try:
                layer.destroy()
            except Exception:                               # noqa: BLE001
                pass
        self.root.after(ms + 500, gone)
        return True

    def open_tint(self, pet):
        """이로치의 색 고르기 창. 고르면 바탕화면과 열려 있는 관리 창을 다시 맞춘다."""
        if self.arena or self.battle or not pet.mon.get("shiny"):
            return
        from .ui_tint import TintPicker

        def done(_mon):
            self.request_sync()
            box = getattr(self, "box_window", None)
            if box is not None:
                try:
                    box.reload()
                except Exception:                           # noqa: BLE001
                    pass
        TintPicker(self, pet.mon, on_done=done)

    # ---------------- 메가진화한 모습으로 걷기 (1.8.0) ----------------
    # 겉모습뿐이다. 능력치도 배틀도 그대로고, 배틀 창에서는 여전히 메가진화
    # 단추를 눌러야 변한다. 그래서 서버에 두지 않고 이 PC 의 설정에 적는다
    # (settings.megaWalk = 포켓몬 id 목록).
    #
    # **배틀에서 메가진화할 수 있는 포켓몬만** 된다: 키스톤이 있고, 자기
    # 메가스톤을 지녔다(레쿠쟈는 화룡점정). 스톤을 떼면 다음 동기화에서
    # 원래 모습으로 돌아오고, 다시 지니면 다시 메가 폼이 된다 - 켜 둔 것은
    # 남아 있다.
    def mega_ids(self):
        out = []
        for i in self.settings.get("megaWalk") or []:
            try:
                out.append(int(i))
            except (TypeError, ValueError):
                pass
        return out

    def mega_form(self, mon, keystone=None):
        """이 포켓몬이 바탕화면에서 입을 수 있는 메가 폼 (도감 megas 의 한 줄). 없으면 None.

        메가 폼의 도트가 있어야 한다 - 걷는 도트(walk)가 없으면 배틀 도트(dot)로
        선다. 둘 다 없는 폼(26개)은 안 된다.
        """
        if not self.dex or not (self.keystone if keystone is None else keystone):
            return None
        try:
            form = self.dex.mega_for(mon)
        except Exception:                                   # noqa: BLE001
            return None
        if not form or not (form.get("walk") or form.get("dot")):
            return None
        return form

    def dress_megas(self, mons, keystone=None):
        """켜 둔 포켓몬에 lookNum(메가 폼의 번호)을 붙인다. 받아야 할 도트 목록을 준다."""
        ids = set(self.mega_ids())
        want = []
        for m in mons or []:
            m.pop("lookNum", None)
            if m.get("id") not in ids:
                continue
            form = self.mega_form(m, keystone)
            if form:
                m["lookNum"] = form["num"]
                want.append((form["num"], T.skin(m)))
        return want

    @staticmethod
    def undress_missing(mons, paths, walks):
        """메가 폼의 도트를 못 받았으면 원래 모습으로 둔다."""
        for m in mons or []:
            n = m.get("lookNum")
            if not n:
                continue
            sh = T.skin(m)
            walk = (walks or {}).get(walk_cache.key(n, sh)) or (walks or {}).get(n)
            if not ((paths or {}).get((n, sh)) or (paths or {}).get((n, False))
                    or (walk and walk[0] and walk[1])):
                m.pop("lookNum", None)

    def mega_menu_row(self, pet):
        """우클릭 메뉴에 넣을 줄. 메가진화와 상관없는 포켓몬이면 None."""
        mon = pet.mon or {}
        if not self.dex or getattr(pet, "id", 0) is None or (pet.id or 0) < 0:
            return None
        forms = [f for f in (self.dex.mega_of.get(mon.get("species")) or [])
                 if f.get("walk") or f.get("dot")]
        if not forms:
            return None
        if pet.id in self.mega_ids() and (pet.look or 0) >= 10000:
            return {"text": "원래 모습으로 걷기",
                    "command": lambda: self.toggle_mega_walk(pet)}
        if self.mega_form(mon):
            return {"text": "메가진화한 모습으로 걷기",
                    "command": lambda: self.toggle_mega_walk(pet)}
        # 될 수 있는 종인데 아직 못 한다 - 무엇이 모자란지 알려 준다.
        why = "키스톤 필요" if not self.keystone else "메가스톤을 지녀야 함"
        return {"text": "메가 모습으로 걷기 (%s)" % why, "enabled": False}

    def toggle_mega_walk(self, pet):
        """그 도트를 메가진화한 모습으로 (또는 원래 모습으로) 바꾼다. 연출과 함께."""
        if self.arena or self.battle or getattr(pet, "evolving", False):
            return
        ids = self.mega_ids()
        if pet.id in ids and (pet.look or 0) >= 10000:
            ids = [i for i in ids if i != pet.id]
            self.settings["megaWalk"] = ids
            config.save_settings(self.settings)
            mega_fx.play(self, pet, pet.mon.get("num"), revert=True)
            return
        form = self.mega_form(pet.mon)
        if not form:
            return
        if pet.id not in ids:
            ids.append(pet.id)
        self.settings["megaWalk"] = ids
        config.save_settings(self.settings)
        num = form["num"]

        def done():
            if getattr(pet, "look", None) == num:
                self._prefetch_anims([pet.mon])
                return
            # 도트를 못 받았다. 켜 둔 것을 무르고 알린다 (화면에 아무 자국이 없다).
            self.settings["megaWalk"] = [i for i in self.mega_ids() if i != pet.id]
            config.save_settings(self.settings)
            self.notify("메가진화한 모습의 도트를 받지 못했습니다.")
        mega_fx.play(self, pet, num, on_done=done)

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
                self.api, [(m.get("num"), T.skin(m)) for m in picked])
        run_async(self.root, work, lambda r, e: self.request_sync())

    def set_size(self, px):
        self.settings["targetHeight"] = int(px)
        config.save_settings(self.settings)
        if self.overlay:
            self.overlay.refresh_visuals()
            self.bond_stones.apply()       # 도트를 새로 만들었다 - 표식도 다시
        self.refresh_tray()

    def set_area(self, w, h):
        if w == 0:                       # 화면 전체
            self.settings["areaW"] = 100000
            self.settings["areaH"] = 100000
        else:
            self.settings["areaW"] = w
            self.settings["areaH"] = h
        # 미리 정해진 크기를 고르면 직접 그린 영역은 버린다 - 둘 다 켜져 있으면
        # 눌러도 아무 일이 없는 것처럼 보인다(그린 영역이 이기므로).
        self.settings["areaRect"] = None
        self._area_changed()

    def set_area_rect(self, rect):
        """직접 그린 영역을 쓴다. None 이면 다시 기본(오른쪽 아래)으로."""
        self.settings["areaRect"] = list(rect) if rect else None
        self._area_changed()

    def screen_choices(self):
        """모니터가 둘 이상일 때 고를 화면들 [(이름, 영역)]. 한 대면 빈 목록."""
        from .overlay import screen_choices
        try:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            return screen_choices(PLAT.screens(sw, sh), PLAT.screen_works(sw, sh))
        except Exception as e:                              # noqa: BLE001
            config.log("화면 목록을 못 읽었습니다: %s" % e)
            return []

    def set_area_screen(self, rect, name=""):
        """그 화면 전체를 활동 영역으로 (트레이·설정의 '왼쪽 화면 / 오른쪽 화면')."""
        self.set_area_rect(rect)
        self.notify("포켓몬이 돌아다닐 영역을 %s 전체로 정했습니다." % (name or "그 화면"))

    def pick_area(self):
        """화면에 끌어서 활동 영역을 그린다 (캡처처럼)."""
        from .ui_area import pick_area
        if getattr(self, "_picking_area", False):
            return
        self._picking_area = True
        try:
            rect = pick_area(self.root, self.settings.get("areaRect")
                             or (self.overlay.area() if self.overlay else None))
        finally:
            self._picking_area = False
        if rect:
            self.set_area_rect(rect)
            self.notify("포켓몬이 돌아다닐 영역을 %d x %d 로 정했습니다."
                        % (rect[2] - rect[0], rect[3] - rect[1]))
        return rect

    def _area_changed(self):
        """영역이 바뀌었다. 저장하고, 밖에 있던 포켓몬을 안으로 들인다."""
        config.save_settings(self.settings)
        if self.overlay:
            for p in list(self.overlay.pets.values()) + list(self.overlay.eggs.values()):
                p.clamp()
                p.place()
        # 레이드 기둥은 영역 윗변에서 내려온다 - 영역이 바뀌면 따라간다.
        if self.raid_pillar is not None:
            self.raid_pillar.reposition()
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
        """이번 판에 무엇이 들어왔는지 본다 - 게시판의 패치노트 칸이다 (1.9.0).

        예전에는 '새로운 기능' 창을 따로 띄웠다. 이제 새 버전이 나오면 서버가
        게시판에 글을 올리므로 거기서 본다 - 지난 판들도 다 남아 있고, 댓글도
        달 수 있다.
        """
        self.open_patchnotes()

    def _tell_patchnotes_once(self):
        """갈아탄 뒤 처음 켰을 때 한 번 알린다. **창은 띄우지 않는다** (1.9.0).

        예전에는 '새로운 기능' 창이 저절로 떴다. 이제는 운영체제 알림 한 번과
        게시판 탭의 표시로 알리고, 내용은 게시판의 패치노트 칸에서 본다.

        **처음 켠 사람에게는 알리지 않는다.** 아직 써보지도 않은 프로그램의
        변경 내역은 읽을 이유가 없다. 대신 지금 버전을 적어 둬서, 다음에
        갈아탄 뒤에는 보게 한다.

        버전을 적는 것은 알리든 말든 먼저 한다. 알림 쪽에서 무슨 일이
        나도 다음 실행마다 같은 안내가 또 뜨는 일은 없어야 한다.
        """
        last = self.settings.get("lastRunVersion") or ""
        if last == VERSION:
            return
        self.settings["lastRunVersion"] = VERSION
        config.save_settings(self.settings)
        if not last or not patchnotes.entry(VERSION):
            return
        # 이번 판의 패치노트 글은 아직 안 본 것이다 (note_board 가 본다)
        self._patch_fresh = True
        # 부팅으로 켜졌으면 한참 미룬다. 컴퓨터를 켜자마자 알림이 튀어나오면
        # 다른 알림들에 묻힌다.
        self.root.after(12000 if self.autostarted else 2200, self._toast_updated)

    def _toast_updated(self):
        self.toast("포스크탑 v%s 업데이트 완료" % VERSION,
                   "바뀐 것은 게시판의 '패치노트' 에서 볼 수 있습니다.", kind="update")

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

    # 걷기 말고 다른 동작. 종마다 아홉 개라 켤 때 다 받으면 첫 화면이
    # 한참 늦어진다. 포켓몬이 이미 나와서 걸어다니는 동안 뒷줄에서
    # 하나씩 받아 채운다 - 다 받기 전에는 그냥 걷기만 한다.
    #
    # 순서가 중요하다. Idle 이 제일 자주 보이고(가만히 있을 때마다),
    # Faint 는 배틀에서 지는 순간에만 쓴다.
    # Attack/Charge/Shoot 은 뺐다 - 칸 크기가 크게 달라서 배틀 연출에서
    # 도트가 튀었다. 안 쓰는 것을 받아 둘 이유가 없다.
    ANIM_ORDER = walk_cache.ANIMS

    def _prefetch_anims(self, mons):
        if self._anim_job or not self.overlay:
            return
        nums = []
        for m in mons:
            # 메가 폼으로 걷는 포켓몬은 그 폼의 동작을 받는다 (look_num)
            n, sh = look_num(m), T.skin(m)
            # 걷는 도트가 없는 종은 다른 동작도 없다. 물어볼 것도 없다.
            if (n and (n, sh) not in nums
                    and (self.overlay.walks.get(walk_cache.key(n, sh))
                         or self.overlay.walks.get(n))):
                nums.append((n, sh))
        want = [(n, sh, a) for n, sh in nums for a in self.ANIM_ORDER
                if walk_cache.sheet_key(n, a, sh) not in self.overlay.sheets]
        if not want:
            return
        self._anim_job = True

        def work():
            got = {}
            for n, sh, a in want:
                if self._quitting:
                    break
                got[walk_cache.sheet_key(n, a, sh)] = walk_cache.ensure(
                    self.api, n, a, shiny=sh)
            return got

        def done(r, err):
            self._anim_job = False
            if err or not r or self._quitting or not self.overlay:
                return
            self.overlay.sheets.update(r)

        run_async(self.root, work, done)

    def toggle_names(self):
        self.settings["showNames"] = not self.settings.get("showNames")
        config.save_settings(self.settings)
        if self.overlay:
            # 이름표 창만 붙이거나 뗀다. refresh_visuals() 로 도트를 다시
            # 만들면 배틀 중에 싸우던 도트까지 사라진다. 배틀 중이면 저장만
            # 되고, 배틀이 끝나 이름표를 풀 때 반영된다.
            self.overlay.apply_names()
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
            # 설정 화면은 마이페이지 탭 안에 있다 (톱니바퀴를 눌러야 생긴다)
            pane = getattr(self.hub.panes.get("my"), "settings", None)
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
        self._stop_guild_sock()
        self.guild_id, self.guild_chat, self._guild_dot = None, 0, None
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
        self._stop_guild_sock()
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
