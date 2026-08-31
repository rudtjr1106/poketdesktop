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

DEFAULTS = {
    "server": "http://127.0.0.1:8787",
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
