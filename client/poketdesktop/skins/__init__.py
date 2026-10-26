# -*- coding: utf-8 -*-
"""화면 테마 - 리소스팩 (설정 → 화면 테마).

테마 하나가 이 아래 폴더 하나다. 그 세대 게임의 화면을 본뜬다 (사용자 결정, 2026-10-25) - 단 창 · 메뉴 크기와
정보량은 기본 테마 그대로, 읽기 쉽게 (DP v2). DP 가 그 틀이고, 다른 세대 테마는 DP 를 물려받아 빛깔 · 글꼴과
그 세대 대표 화면만 바꾼다 (base="dp", derive.py).

    skins/<열쇠>/__init__.py   그 테마의 색 · 글꼴 (물려받는 테마는 BASE · PALETTE · COLORS · shade)
    skins/<열쇠>/<화면>.py      그 화면의 배치 (bag.py, battle.py, …)

화면 쪽은 `skins.view("bag")` 으로 지금 테마의 배치를 받는다. 그 테마에 없으면 물려받는 테마의 것을, 거기에도
없으면 None 이 와서 지금까지의 화면(기본 테마)을 그대로 그린다. **다 그린 테마만 설정에 보인다** (ready) -
반쯤 바뀐 테마는 내보내지 않는다. 만드는 동안은 POKET_SKINS=all 로 전부 보이게 한다.

**테마는 켤 때 한 번 정한다.** 바꾸면 앱을 다시 켠다 - 열려 있는 창 수십 개를 그 자리에서 다시 그리는
것보다 안전하고, 테마의 글꼴은 tk.Tk() 를 만들기 전에 등록해야 Tk 이 본다.
"""
import importlib
import os

DEFAULT = "default"


class Skin(object):

    def __init__(self, key, name, era, fonts=(), ready=False, base=None):
        self.key = key
        self.name = name          # 설정에 보이는 이름
        self.era = era            # 한 줄 설명 (세대 · 기기)
        self.fonts = tuple(fonts)  # 이 테마가 쓰는 글꼴 파일 (fonts/ 안) - 이 테마일 때만 등록한다
        self.ready = ready
        self.base = base          # 화면 틀을 물려받는 테마 (그 테마에 없는 화면은 이것을 쓴다 - derive.py)


PIXEL = ("Galmuri11.ttf",)

SKINS = (
    Skin(DEFAULT, "기본", "지금까지의 포스크탑", ready=True),
    # DP v2 의 틀을 물려받고 빛깔 · 글꼴 · 그 세대 대표 화면만 바꾼다 (derive.py)
    Skin("gs", "금·은", "2세대 · 게임보이 컬러", PIXEL, ready=True, base="dp"),
    Skin("emerald", "에메랄드", "3세대 · 게임보이 어드밴스", PIXEL, ready=True, base="dp"),
    Skin("dp", "디아루가·펄기아", "4세대 · 닌텐도 DS", PIXEL, ready=True),
    Skin("pt", "플라티나", "4세대 · 닌텐도 DS", PIXEL, ready=True, base="dp"),
    Skin("bw", "블랙·화이트", "5세대 · 닌텐도 DS", PIXEL, ready=True, base="dp"),
    Skin("swsh", "소드·실드", "8세대 · 닌텐도 스위치", ("Pretendard-Bold.otf", "Pretendard-Black.otf"), ready=True,
         base="dp"),
)
BY_KEY = dict((s.key, s) for s in SKINS)

_active = None


def show_all():
    """만드는 중인 테마까지 설정에 보일까 (POKET_SKINS=all)."""
    return os.environ.get("POKET_SKINS", "").strip().lower() == "all"


def choices():
    """설정에서 고를 수 있는 테마."""
    return [s for s in SKINS if s.ready or show_all()]


def usable(key):
    s = BY_KEY.get(key)
    return bool(s and (s.ready or show_all()))


def active():
    """이번 실행의 테마 열쇠. 처음 부를 때 정하고 끝날 때까지 안 바뀐다.

    POKET_SKIN 이 있으면 그것 (테스트 화면 · 캡처용), 없으면 설정의 skin.
    """
    global _active
    if _active is None:
        key = os.environ.get("POKET_SKIN", "").strip()
        if not key:
            try:
                from .. import config
                key = config.load_settings().get("skin") or DEFAULT
            except Exception:                               # noqa: BLE001
                key = DEFAULT
        if key != DEFAULT and not (key in BY_KEY and (BY_KEY[key].ready
                                                      or show_all()
                                                      or os.environ.get("POKET_SKIN"))):
            key = DEFAULT
        _active = key
    return _active


def current():
    return BY_KEY[active()]


def font_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")


def register_fonts():
    """지금 테마의 글꼴을 이 프로그램 안에서만 등록한다. **tk.Tk() 를 만들기 전에** 부른다.

    기본 테마는 아무것도 등록하지 않는다 - 지금까지와 글꼴이 똑같아야 한다 (후보 목록에
    Pretendard 가 들어 있어서, 등록하면 기본 테마의 글꼴이 바뀐다).
    """
    from .. import platform_os as PLAT
    done = []
    for name in current().fonts:
        path = os.path.join(font_dir(), name)
        if os.path.isfile(path) and PLAT.register_font(path):
            done.append(name)
    return done


def chain(key=None):
    """그 테마와 물려받는 테마들 (가까운 것부터). 예: pt -> ['pt', 'dp']."""
    out = []
    key = key or active()
    while key and key != DEFAULT and key not in out:
        out.append(key)
        s = BY_KEY.get(key)
        key = s.base if s is not None else None
    return out


def view(screen):
    """지금 테마가 그 화면을 따로 그리면 그 모듈, 아니면 None (지금까지의 화면을 쓴다).

    그 테마에 그 화면 파일이 없으면 물려받는 테마(base)의 것을 쓴다 - 플라티나에 bag.py 가 없으면 DP 의 bag.py.
    """
    for key in chain():
        name = "%s.%s.%s" % (__name__, key, screen)
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError as e:
            # 그 화면 파일이 없는 것만 '아직 안 그렸다' 로 본다. 화면 파일 **안에서** 다른 것을
            # 못 찾은 것은 고쳐야 할 오류다 - 조용히 기본 화면으로 돌리면 못 알아챈다.
            if e.name in (name, "%s.%s" % (__name__, key)):
                continue
            raise
    return None


def theme(root, style):
    """지금 테마가 **위젯으로 짠 화면 전체**의 모양(색 · 글꼴 · 단추)을 바꾸면 여기서 건다.

    ui_common.apply_theme 의 끝에서 부른다 (창마다 불려도 된다 - 테마 쪽이 한 번만 건다). 기본 테마는
    아무것도 안 한다. 테마가 따로 그린 화면(캔버스)은 제 색을 쓰고, 아직 따로 안 그린 화면 · 작은 창이
    이것으로 그 테마의 빛깔을 입는다 (skins/<열쇠>/widgets.py 의 install).
    """
    v = view("widgets")
    if v is not None and hasattr(v, "install"):
        v.install(root, style)


def override(cls):
    """지금 테마가 이 화면 클래스를 따로 그리면 그 클래스, 아니면 그대로.

    화면 파일 이름은 기본 화면의 모듈 이름에서 'ui_' 를 뗀 것이다 (ui_bag -> skins/<열쇠>/bag.py),
    클래스 이름은 같다 (BagWindow -> BagWindow).
    """
    mod = cls.__module__.rsplit(".", 1)[-1]
    if mod.startswith("ui_"):
        mod = mod[3:]
    v = view(mod)
    return getattr(v, cls.__name__, cls) if v is not None else cls


def skinnable_fn(screen):
    """함수 꾸밈: 지금 테마의 skins/<열쇠>/<screen>.py 에 **같은 이름 함수**가 있으면 그것을 부른다.

        @skins.skinnable_fn("dialogs")
        def confirm(parent, title, message, ...): ...

    묻는 창처럼 모듈 함수로 된 화면에 쓴다. 테마 쪽 함수는 같은 인자를 받고 같은 것을 돌려줘야 한다.
    기본 함수는 `.base` 로 부를 수 있다 (테마가 기본 것에 조금만 덧붙일 때).
    """
    def deco(fn):
        import functools

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            v = view(screen)
            alt = getattr(v, fn.__name__, None) if v is not None else None
            if alt is not None and alt is not wrapper:
                return alt(*args, **kwargs)
            return fn(*args, **kwargs)
        wrapper.base = fn
        return wrapper
    return deco


def skinnable(cls):
    """클래스 꾸밈: **어디서 만들든** 지금 테마의 같은 이름 클래스로 만든다 (override 를 부르는 쪽마다 잊지 않게).

        @skins.skinnable
        class SettingsWindow(object): ...

        SettingsWindow(app)      # dp 테마면 skins/dp/settings.py 의 SettingsWindow 가 만들어진다

    테마 클래스는 이 클래스를 물려받으므로 __init__ 은 한 번만 불린다 (테마 쪽 것).
    """
    def __new__(klass, *args, **kwargs):
        if klass is cls:
            alt = override(cls)
            if alt is not cls:
                klass = alt
        return object.__new__(klass)
    cls.__new__ = staticmethod(__new__)
    return cls
