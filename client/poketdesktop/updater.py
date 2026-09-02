# -*- coding: utf-8 -*-
"""새 버전이 나왔는지 보고, 받아서 갈아끼운다.

**돌고 있는 exe 는 지울 수도 덮어쓸 수도 없다.** 윈도우가 잠가 놓기 때문이다.
그래서 흔히 쓰는 '따로 업데이터를 띄워서 기다렸다가 바꿔치기' 같은 걸 하는데,
여기서는 그럴 필요가 없다. 배포 폴더 이름에 버전이 들어 있어서다.

    poketdesktop-v0.12.0/poketdesktop-v0.12.0.exe   <- 지금 도는 것
    poketdesktop-v0.13.0/poketdesktop-v0.13.0.exe   <- 옆에 풀고

새 폴더를 **옆에** 풀고 그쪽 exe 를 띄운 뒤 이쪽은 그냥 끝낸다.
지금 도는 파일은 건드리지 않는다. 옛 폴더는 다음에 켤 때 치운다.

받는 곳은 이 저장소의 릴리스 하나로 못박아 둔다. 서버가 알려주는 주소를
따라가면, 서버가 바뀌었을 때 엉뚱한 파일을 받아 실행하게 된다.
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

from common.version import VERSION

from . import config

OWNER = "rudtjr1106"
REPO = "poketdesktop"
API = "https://api.github.com/repos/%s/%s/releases/latest" % (OWNER, REPO)
# 받아도 되는 주소. 이 앞부분으로 시작하지 않으면 손대지 않는다.
ALLOW_PREFIX = "https://github.com/%s/%s/releases/download/" % (OWNER, REPO)

TIMEOUT = 20


def _num(v):
    """'0.12.0' -> (0, 12, 0). 비교할 수 있게."""
    parts = re.findall(r"\d+", v or "")
    return tuple(int(x) for x in parts[:4]) or (0,)


def newer(a, b):
    """a 가 b 보다 새 버전인가."""
    return _num(a) > _num(b)


def is_frozen():
    """exe 로 묶여서 도는 중인가. 개발 중(파이썬)에는 업데이트하지 않는다."""
    return bool(getattr(sys, "frozen", False))


def exe_path():
    return os.path.abspath(sys.executable)


def install_dir():
    """지금 exe 가 들어 있는 폴더."""
    return os.path.dirname(exe_path())


def parent_dir():
    """새 버전을 풀어 놓을 곳. 지금 폴더의 바로 위."""
    return os.path.dirname(install_dir())


# ---------------------------------------------------------------- 확인
def check(timeout=TIMEOUT):
    """새 버전이 있으면 정보를, 없으면 None.

    깃허브 API 는 로그인 없이 시간당 60번까지 된다. 켤 때 한 번만 부르므로
    넉넉하다.
    """
    import urllib.request
    req = urllib.request.Request(API, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "poketdesktop/%s" % VERSION,
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:                                  # noqa: BLE001
        config.log("업데이트 확인 실패: %s" % e)
        return None

    tag = (data.get("tag_name") or "").lstrip("vV")
    if not tag or not newer(tag, VERSION):
        return None

    # zip 만 받는다. 단일 exe 는 백신이 자주 오탐해서 배포하지 않는다.
    asset = None
    for a in data.get("assets") or []:
        url = a.get("browser_download_url") or ""
        if a.get("name", "").endswith(".zip") and url.startswith(ALLOW_PREFIX):
            asset = a
            break
    if not asset:
        config.log("새 버전 %s 은 있는데 받을 zip 이 없습니다" % tag)
        return None

    return {
        "version": tag,
        "url": asset["browser_download_url"],
        "size": int(asset.get("size") or 0),
        "name": asset["name"],
        "notes": (data.get("body") or "").strip(),
    }


# ---------------------------------------------------------------- 내려받기
def download(url, dest, on_progress=None, timeout=60):
    """zip 을 받는다. on_progress(받은바이트, 전체바이트) 로 알려준다."""
    import urllib.request
    if not url.startswith(ALLOW_PREFIX):
        raise ValueError("허락되지 않은 주소입니다")
    req = urllib.request.Request(url, headers={
        "User-Agent": "poketdesktop/%s" % VERSION})
    tmp = dest + ".part"
    got = 0
    with urllib.request.urlopen(req, timeout=timeout) as r:
        total = int(r.headers.get("Content-Length") or 0)
        with io.open(tmp, "wb") as f:
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if on_progress:
                    on_progress(got, total)
    os.replace(tmp, dest)
    return dest


# ---------------------------------------------------------------- 풀기
def _safe_members(zf, root):
    """zip 안의 경로를 확인한다.

    zip 은 '../../어딘가' 같은 경로를 담을 수 있다(zip slip). 그대로 풀면
    폴더 밖에 파일을 쓴다. 풀 위치 안에 떨어지는 것만 통과시킨다.
    """
    root = os.path.abspath(root)
    out = []
    for m in zf.infolist():
        p = os.path.abspath(os.path.join(root, m.filename))
        if p == root or p.startswith(root + os.sep):
            out.append(m)
    return out


def extract(zip_path, parent, version, on_progress=None):
    """새 버전 폴더를 parent 아래에 푼다. 새 exe 경로를 돌려준다."""
    want_dir = "%s-v%s" % (REPO, version)
    target = os.path.join(parent, want_dir)
    staging = target + ".new"
    shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(staging, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        members = _safe_members(zf, staging)
        total = len(members) or 1
        for i, m in enumerate(members):
            zf.extract(m, staging)
            if on_progress and i % 20 == 0:
                on_progress(i, total)
        if on_progress:
            on_progress(total, total)

    # zip 안이 한 겹 더 싸여 있으면(보통 그렇다) 그 안을 쓴다
    inner = os.path.join(staging, want_dir)
    src = inner if os.path.isdir(inner) else staging

    exe = os.path.join(src, want_dir + ".exe")
    if not os.path.exists(exe):
        # 이름이 다르면 폴더 안의 exe 하나를 찾는다
        cands = [f for f in os.listdir(src) if f.lower().endswith(".exe")]
        if len(cands) != 1:
            raise ValueError("새 버전 안에서 실행 파일을 찾지 못했습니다")
        exe = os.path.join(src, cands[0])

    shutil.rmtree(target, ignore_errors=True)
    os.replace(src, target)
    shutil.rmtree(staging, ignore_errors=True)
    return os.path.join(target, os.path.basename(exe))


# ---------------------------------------------------------------- 뒷정리
def cleanup_old(parent=None, keep=VERSION):
    """지난 버전 폴더를 치운다. 켤 때 한 번 부른다.

    새 버전으로 갈아탄 직후에는 옛 폴더가 아직 잠겨 있을 수 있다.
    못 지워도 그냥 넘어간다 — 다음에 켤 때 지워진다.
    """
    parent = parent or parent_dir()
    pat = re.compile(r"^%s-v(\d+(?:\.\d+)*)$" % re.escape(REPO))
    try:
        names = os.listdir(parent)
    except OSError:
        return 0
    gone = 0
    for n in names:
        m = pat.match(n)
        if not m or m.group(1) == keep:
            continue
        p = os.path.join(parent, n)
        if not os.path.isdir(p):
            continue
        try:
            shutil.rmtree(p)
            gone += 1
            config.log("지난 버전 폴더 삭제: %s" % n)
        except OSError:
            pass          # 아직 잠겨 있다. 다음에.
    return gone


def relaunch(exe, args=()):
    """새 exe 를 띄운다. 이쪽은 부르는 쪽에서 끝내면 된다.

    args 는 그대로 넘긴다. 부팅으로 켜졌다는 표시(--autostart)를 이어
    주지 않으면, 갓 갈아탄 판이 '손으로 켠 것' 으로 보여서 인터넷이
    늦게 붙을 때 로그인 창을 띄워 버린다.
    """
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | \
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([exe] + list(args), cwd=os.path.dirname(exe),
                     close_fds=True, creationflags=flags)


def temp_zip(version):
    d = os.path.join(tempfile.gettempdir(), "poketdesktop-update")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "%s-v%s.zip" % (REPO, version))
