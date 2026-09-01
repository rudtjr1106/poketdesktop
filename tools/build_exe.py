# -*- coding: utf-8 -*-
"""클라이언트를 윈도우 실행 파일(exe) 하나로 묶는다.

    python tools/build_exe.py

결과: dist/poketdesktop-vX.Y.Z.exe

- 파일 하나로 나온다. 파이썬이 없는 PC 에서도 그냥 실행된다.
- 콘솔 창이 안 뜬다 (백그라운드로 도는 프로그램이라서).
- 포켓몬 그림은 **안 들어간다.** 실행할 때 서버에서 받아 각자 PC 에 캐시한다.
  저작물을 배포하지 않으려는 것이기도 하고, 그래야 파일이 작다.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from common.version import VERSION            # noqa: E402

# GitHub 릴리스는 첨부파일 이름의 한글을 지워버린다. 파일명은 ASCII 로 둔다.
# (창 제목과 프로그램 이름은 그대로 한글이다)
NAME = "poketdesktop-v%s" % VERSION
ENTRY = os.path.join(ROOT, "client", "run.pyw")
ICON = os.path.join(ROOT, "build", "icon.ico")


def make_icon():
    """작업표시줄과 exe 에 쓸 아이콘. 트레이와 같은 그림이다."""
    sys.path.insert(0, os.path.join(ROOT, "client"))
    from poketdesktop import appicon

    os.makedirs(os.path.dirname(ICON), exist_ok=True)
    appicon.save_ico(ICON)
    print("  아이콘: %s" % ICON)
    return ICON


VERSION_TEMPLATE = """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(%(nums)s), prodvers=(%(nums)s),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'rudtjr1106'),
        StringStruct('FileDescription', 'Poket Desktop - a desktop Pokemon companion'),
        StringStruct('FileVersion', '%(ver)s'),
        StringStruct('InternalName', 'poketdesktop'),
        StringStruct('LegalCopyright', 'Fan project. Pokemon is (c) Nintendo / Creatures / GAME FREAK.'),
        StringStruct('OriginalFilename', '%(name)s.exe'),
        StringStruct('ProductName', 'Poket Desktop'),
        StringStruct('ProductVersion', '%(ver)s')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def make_version_file():
    """exe 에 넣을 버전 정보.

    이게 없으면 파일 속성이 텅 비어서 '어디서 왔는지 모를 프로그램' 으로
    보인다. 백신과 SmartScreen 이 평판을 매길 때 불리하게 작용한다.
    서명만큼은 아니지만 공짜로 할 수 있는 일이다.

    설명은 영문으로 적는다. 버전 리소스는 인코딩이 까다로워서 한글을 넣으면
    빌드 환경에 따라 깨지는 일이 있다.
    """
    v = (VERSION.split(".") + ["0", "0", "0", "0"])[:4]
    nums = ", ".join(v)
    path = os.path.join(ROOT, "build", "version.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = VERSION_TEMPLATE % {
        "nums": nums, "ver": VERSION, "name": NAME,
    }
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def build(onedir=False):
    print("포켓 데스크톱 v%s 빌드 (%s)"
          % (VERSION, "폴더형" if onedir else "단일 파일"))
    icon = make_icon()
    verfile = make_version_file()

    # dist 를 통째로 지우면 안 된다. 단일 exe 와 폴더형 zip 을 둘 다 내는데,
    # 나중에 돌린 쪽이 앞서 만든 걸 지워버린다.
    shutil.rmtree(os.path.join(ROOT, "build", "pyi"), ignore_errors=True)
    dist = os.path.join(ROOT, "dist")
    os.makedirs(dist, exist_ok=True)
    if onedir:
        shutil.rmtree(os.path.join(dist, NAME), ignore_errors=True)
    else:
        old = os.path.join(dist, NAME + ".exe")
        if os.path.exists(old):
            os.remove(old)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        # 단일 파일(--onefile)은 실행할 때 자기를 임시 폴더에 풀고 돌린다.
        # 그 동작이 악성코드 패커와 비슷해서 백신 오탐이 자주 난다.
        # 폴더형(--onedir)은 풀어놓은 상태 그대로라 오탐이 훨씬 적다.
        "--onedir" if onedir else "--onefile",
        "--windowed",                     # 콘솔 창 없이
        "--name", NAME,
        "--icon", icon,
        # 파일 속성에 이름·버전·설명을 박는다. 속성이 비어 있으면
        # '출처 모를 프로그램' 으로 취급받아 평판에 불리하다.
        "--version-file", verfile,
        "--distpath", os.path.join(ROOT, "dist"),
        "--workpath", os.path.join(ROOT, "build", "pyi"),
        "--specpath", os.path.join(ROOT, "build"),
        # common 패키지를 찾을 수 있게
        "--paths", ROOT,
        "--paths", os.path.join(ROOT, "client"),
        "--hidden-import", "common.pokelogic",
        "--hidden-import", "common.version",
        # pystray 는 실행할 때 백엔드를 고르므로 직접 알려줘야 한다
        "--hidden-import", "pystray._win32",
        "--hidden-import", "PIL._tkinter_finder",
        # 안 쓰는 무거운 것들은 뺀다
        "--exclude-module", "numpy",
        "--exclude-module", "scipy",
        "--exclude-module", "matplotlib",
        "--exclude-module", "pandas",
        "--exclude-module", "PyQt5",
        "--exclude-module", "PySide2",
        "--exclude-module", "test",
        ENTRY,
    ]
    print("  PyInstaller 실행...")
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        print("  실패")
        return 1

    if onedir:
        folder = os.path.join(ROOT, "dist", NAME)
        exe = os.path.join(folder, NAME + ".exe")
    else:
        folder = None
        exe = os.path.join(ROOT, "dist", NAME + ".exe")
    if not os.path.exists(exe):
        print("  실행 파일이 안 만들어졌습니다")
        return 1
    if onedir:
        # 폴더째 zip 으로 묶는다. 받는 사람은 풀고 exe 를 누르면 된다.
        zip_base = os.path.join(ROOT, "dist", NAME)
        made = shutil.make_archive(zip_base, "zip",
                                   os.path.join(ROOT, "dist"), NAME)
        mb = os.path.getsize(made) / 1048576.0
        print("")
        print("  완성: %s" % made)
        print("  크기: %.1f MB" % mb)
        return 0
    mb = os.path.getsize(exe) / 1048576.0
    print("")
    print("  완성: %s" % exe)
    print("  크기: %.1f MB" % mb)
    return 0


if __name__ == "__main__":
    import argparse
    _ap = argparse.ArgumentParser()
    _ap.add_argument("--onedir", action="store_true",
                     help="폴더형으로 빌드해 zip 으로 묶는다 (백신 오탐이 적다)")
    _a = _ap.parse_args()
    sys.exit(build(onedir=_a.onedir))
