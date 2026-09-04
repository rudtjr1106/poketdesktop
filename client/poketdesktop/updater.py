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


IS_MAC = sys.platform == "darwin"


def supported():
    """자동 업데이트를 해도 되는 운영체제인가.

    윈도우와 맥 둘 다 한다. 받는 것이 서로 다르다.

      윈도우   `poketdesktop-vX.Y.Z.zip`      -> 폴더로 풀고 exe 를 띄운다
      맥       `poketdesktop-vX.Y.Z-mac.dmg`  -> .app 을 꺼내 갈아끼운다

    **자산을 운영체제별로 골라야 한다.** 예전 check() 는 `.zip` 으로 끝나는
    첫 번째를 그냥 집었다. 그래서 맥 것을 `.zip` 으로 올리면 윈도우
    사용자가 그걸 받아서 "실행 파일을 찾지 못했습니다" 로 끝난다.
    맥 자산을 `.dmg` 로 내는 이유가 그것이다 - 이미 나가 있는 옛
    클라이언트는 고칠 수 없으니, 그쪽이 집을 수 없는 이름으로 둔다.
    """
    return sys.platform in ("win32", "darwin")


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

    깃허브 API 는 로그인 없이 시간당 60번까지 된다. 이걸 부르는 자리는
    둘뿐이다 - 켤 때 한 번(app.check_update), 켜 둔 동안 한 시간마다 한 번
    (app.UPDATE_EVERY_HOURS). 한 사람이 한 시간에 많아야 한두 번이라
    넉넉하다.
    """
    import urllib.request
    req = urllib.request.Request(API, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "poketdesktop/%s" % VERSION,
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout,
                                    context=ssl_context()) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:                                  # noqa: BLE001
        config.log("업데이트 확인 실패: %s" % e)
        return None

    tag = (data.get("tag_name") or "").lstrip("vV")
    if not tag or not newer(tag, VERSION):
        return None

    asset = pick_asset(data.get("assets") or [])
    if not asset:
        config.log("새 버전 %s 은 있는데 이 운영체제용 파일이 없습니다" % tag)
        return None

    return {
        "version": tag,
        "url": asset["browser_download_url"],
        "size": int(asset.get("size") or 0),
        "name": asset["name"],
        "notes": (data.get("body") or "").strip(),
    }


_SSL = None


def ssl_context():
    """인증서를 확인할 때 쓸 것.

    **묶어 놓은 앱에는 인증서 꾸러미가 안 들어 있다.** 그래서 파이썬
    기본값으로 https 를 열면 이렇게 끝난다.

        [SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer
        certificate

    게임 서버 쪽은 멀쩡한데(requests 가 certifi 를 들고 다닌다) 업데이트
    확인만 조용히 실패한다. 새 버전이 나와도 영영 안 받는 것이라 알아채기
    어렵다. 맥 번들에서 실제로 그랬다.

    같은 certifi 를 여기서도 쓴다. 없으면 기본값으로 간다 - 인증서를
    아예 안 보는 쪽으로는 절대 가지 않는다. 남이 준 파일을 받아 실행하는
    자리다.
    """
    global _SSL
    if _SSL is not None:
        return _SSL
    import ssl
    try:
        import certifi
        _SSL = ssl.create_default_context(cafile=certifi.where())
    except Exception:                                       # noqa: BLE001
        _SSL = ssl.create_default_context()
    return _SSL


def pick_asset(assets):
    """이 운영체제가 받아야 할 자산 하나. 없으면 None.

    윈도우는 zip(단일 exe 는 백신이 자주 오탐해서 배포하지 않는다),
    맥은 dmg 다. **이름에 `-mac` 이 있는 것은 윈도우가 집지 않는다** -
    한 릴리스에 둘을 같이 올리기 때문이다.
    """
    for a in assets:
        name = a.get("name") or ""
        url = a.get("browser_download_url") or ""
        if not url.startswith(ALLOW_PREFIX):
            continue
        if IS_MAC:
            if name.endswith(".dmg"):
                return a
        elif name.endswith(".zip") and "-mac" not in name:
            return a
    return None


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
    with urllib.request.urlopen(req, timeout=timeout,
                                context=ssl_context()) as r:
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


def app_bundle():
    """맥. 지금 돌고 있는 .app 번들의 경로. 번들이 아니면 None.

    sys.executable 이 `<번들>/Contents/MacOS/포스크탑` 이다.
    """
    exe = exe_path()
    parts = exe.split(os.sep)
    try:
        i = len(parts) - 1 - parts[::-1].index("Contents")
    except ValueError:
        return None
    if i < 1:
        return None
    return os.sep.join(parts[:i])


def _mac_extract(dmg_path, version, on_progress=None):
    """dmg 를 붙여서 안의 .app 을 꺼내 둔다. 꺼내 둔 경로를 돌려준다.

    **zipfile 로 풀듯 하면 안 된다.** .app 안에는 심볼릭 링크와 실행
    권한이 들어 있는데 그게 다 날아간다. 맥에는 `ditto` 가 있다.
    """
    stage = os.path.join(os.path.dirname(dmg_path), "stage-v%s" % version)
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage, exist_ok=True)
    if on_progress:
        on_progress(0, 3)

    r = subprocess.run(["hdiutil", "attach", dmg_path, "-nobrowse",
                        "-readonly", "-mountrandom", stage],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise ValueError("새 버전을 열지 못했습니다: %s"
                         % (r.stderr or "").strip()[:200])
    # 붙은 자리를 찾는다. hdiutil 은 심볼릭 링크를 풀어서 알려주므로
    # (/var -> /private/var) 우리 쪽도 풀어서 견줘야 한다.
    want = os.path.realpath(stage)
    mnt = None
    for line in (r.stdout or "").splitlines():
        last = line.split("\t")[-1].strip()
        if last and os.path.realpath(last).startswith(want):
            mnt = last
    try:
        if not mnt:
            raise ValueError("새 버전을 붙였는데 자리를 못 찾았습니다")
        apps = [f for f in os.listdir(mnt) if f.endswith(".app")]
        if len(apps) != 1:
            raise ValueError("새 버전 안에서 앱을 찾지 못했습니다")
        if on_progress:
            on_progress(1, 3)
        out = os.path.join(stage, apps[0])
        c = subprocess.run(["ditto", os.path.join(mnt, apps[0]), out],
                           capture_output=True, text=True)
        if c.returncode != 0:
            raise ValueError("새 버전을 꺼내지 못했습니다: %s"
                             % (c.stderr or "").strip()[:200])
    finally:
        if mnt:
            subprocess.run(["hdiutil", "detach", mnt, "-quiet"],
                           capture_output=True)
    if on_progress:
        on_progress(3, 3)
    return out


# 갈아끼우는 스크립트. **우리가 끝난 뒤에** 돌아야 한다 - 돌고 있는
# 번들을 그 자리에서 바꿀 수는 없다.
_SWAP = r'''#!/bin/sh
# 포스크탑 갈아끼우기. 인자: <기다릴 PID> <새 앱> <설치 자리> [앱에 넘길 것...]
PID="$1"; NEW="$2"; APP="$3"; shift 3
i=0
while [ $i -lt 100 ]; do
  kill -0 "$PID" 2>/dev/null || break
  sleep 0.1
  i=$((i+1))
done
TMP="$APP.new-$$"
OLD="$APP.old-$$"
rm -rf "$TMP" "$OLD"
/usr/bin/ditto "$NEW" "$TMP" || exit 1
if [ -d "$APP" ]; then
  mv "$APP" "$OLD" || { rm -rf "$TMP"; exit 1; }
fi
if mv "$TMP" "$APP"; then
  rm -rf "$OLD"
else
  # 못 바꿨으면 있던 것을 되돌린다. 앱이 사라지는 것이 제일 나쁘다.
  [ -d "$OLD" ] && mv "$OLD" "$APP"
  rm -rf "$TMP"
  exit 1
fi
/usr/bin/open -n "$APP" --args "$@"
rm -rf "$(dirname "$NEW")"
'''


def _mac_relaunch(new_app, args=()):
    """새 .app 으로 갈아끼우고 다시 띄운다.

    돌고 있는 번들을 그 자리에서 바꿀 수는 없으니, 우리가 끝나기를
    기다렸다가 바꾸는 작은 스크립트를 띄워 두고 물러난다.
    """
    app = app_bundle()
    if not app:
        raise ValueError("설치된 자리를 찾지 못했습니다")
    sh = os.path.join(os.path.dirname(new_app), "swap.sh")
    with open(sh, "w") as f:
        f.write(_SWAP)
    os.chmod(sh, 0o755)
    subprocess.Popen(["/bin/sh", sh, str(os.getpid()), new_app, app]
                     + list(args),
                     start_new_session=True, close_fds=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def extract(zip_path, parent, version, on_progress=None):
    """새 버전을 꺼낸다. 다시 띄울 것의 경로를 돌려준다."""
    if IS_MAC:
        return _mac_extract(zip_path, version, on_progress)
    return _extract_win(zip_path, parent, version, on_progress)


def _extract_win(zip_path, parent, version, on_progress=None):
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

    맥은 폴더에 버전을 안 붙이고 번들 하나를 그 자리에서 갈아끼우므로
    치울 것이 없다.

    새 버전으로 갈아탄 직후에는 옛 폴더가 아직 잠겨 있을 수 있다.
    못 지워도 그냥 넘어간다 — 다음에 켤 때 지워진다.
    """
    if IS_MAC:
        return 0
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
    if IS_MAC:
        return _mac_relaunch(exe, args)
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | \
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([exe] + list(args), cwd=os.path.dirname(exe),
                     close_fds=True, creationflags=flags)


def temp_zip(version):
    """받은 것을 잠깐 둘 자리."""
    d = os.path.join(tempfile.gettempdir(), "poketdesktop-update")
    os.makedirs(d, exist_ok=True)
    ext = ".dmg" if IS_MAC else ".zip"
    return os.path.join(d, "%s-v%s%s" % (REPO, version, ext))
