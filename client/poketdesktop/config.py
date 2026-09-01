# -*- coding: utf-8 -*-
"""클라이언트 설정과 저장 위치.

설정/세션/도감 캐시는 전부 %APPDATA%\\poketdesktop 아래에 둔다.
프로그램 폴더에는 아무것도 쓰지 않아서 어디에 두고 실행해도 된다.
"""
import hashlib
import json
import os
import sys
import uuid

APP_NAME = "poketdesktop"


def data_dir():
    """설정과 도트를 두는 곳.

    POKET_HOME 으로 다른 데를 가리킬 수 있다. 만들고 있는 것을 실제
    계정과 섞지 않고 시험해 보려고 둔 문이다 - 그게 없으면 시험 한 번에
    쓰던 설정과 로그인이 덮여 버린다. 배포된 프로그램에서는 이 변수가
    없으므로 늘 원래 자리를 쓴다.
    """
    home = os.environ.get("POKET_HOME")
    if home:
        os.makedirs(home, exist_ok=True)
        return home
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


SETTINGS_PATH = os.path.join(data_dir(), "settings.json")
SESSION_PATH = os.path.join(data_dir(), "session.json")
POKEDEX_CACHE = os.path.join(data_dir(), "pokedex.json")
LOG_PATH = os.path.join(data_dir(), "poketdesktop.log")

_HERE = os.path.dirname(os.path.abspath(__file__))
CLIENT_DIR = os.path.dirname(_HERE)
REPO_DIR = os.path.dirname(CLIENT_DIR)

# 실제로 돌고 있는 서버. 사용자가 주소를 칠 일이 없도록 여기에 박아 둔다.
# 서버 주소는 박아 둔다. 사용자가 주소를 칠 일이 없어야 한다.
# POKET_SERVER 는 시험용 문이다(배포판에는 이 변수가 없다).
SERVER = os.environ.get("POKET_SERVER") or "https://poketdesktop.onrender.com"

# 예전에 기본값이었던 주소들. 저장된 설정이 이 중 하나면 새 주소로 옮긴다.
# 사용자가 일부러 고쳐 넣은 주소는 건드리지 않는다.
OLD_SERVERS = (
    "http://127.0.0.1:8787",
    "http://localhost:8787",
    "https://desktop-kb3pg3b.taile9bd90.ts.net:10000",
)

DEFAULTS = {
    "server": SERVER,
    # --- 화면 ---
    "targetHeight": 48,      # 어떤 포켓몬이든 이 높이에 맞춰 크기를 통일한다
    "minScale": 0.25,
    "maxScale": 2.0,
    "fps": 30,
    "walkSpeed": 1.2,
    "animEvery": 8,
    "showNames": False,
    # --- 활동 영역 (화면 오른쪽 아래) ---
    "areaW": 520,
    "areaH": 360,
    "areaMarginR": 24,
    "areaMarginB": 24,
    "areaMargin": 4,
    # --- 동작 ---
    "syncSeconds": 90,       # 서버와 목록을 맞추는 주기(초)
    "notifyEncounter": True, # 야생이 나타나면 알림을 띄운다
}


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            s.update(json.load(f))
    except (OSError, ValueError):
        pass
    # 예전 설정에 없던 키를 채워 넣는다
    for k, v in DEFAULTS.items():
        s.setdefault(k, v)
    # 서버를 옮겼으면 옛 기본값을 쓰던 사람도 같이 데려간다.
    # (직접 고쳐 넣은 주소는 그대로 둔다)
    if (s.get("server") or "").rstrip("/") in [x.rstrip("/") for x in OLD_SERVERS]:
        s["server"] = SERVER
    return s


def save_settings(s):
    tmp = SETTINGS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SETTINGS_PATH)


def load_session():
    try:
        with open(SESSION_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_session(d):
    tmp = SESSION_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SESSION_PATH)


def clear_session():
    try:
        os.remove(SESSION_PATH)
    except OSError:
        pass


def device_id():
    """이 PC 를 가리키는 고정 문자열.

    윈도우 설치마다 고유한 MachineGuid 를 쓰고, 없으면 MAC 주소로 대체한다.
    원본을 그대로 보내지 않고 해시해서 보낸다.
    """
    raw = None
    if sys.platform == "win32":
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                               r"SOFTWARE\Microsoft\Cryptography", 0,
                               winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            raw = winreg.QueryValueEx(k, "MachineGuid")[0]
            winreg.CloseKey(k)
        except OSError:
            raw = None
    if not raw:
        raw = "%012x" % uuid.getnode()
    raw += "|" + (os.environ.get("USERNAME") or "")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def log(msg):
    try:
        import datetime
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n"
                    % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass
