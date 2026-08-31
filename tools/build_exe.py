# -*- coding: utf-8 -*-
"""클라이언트를 윈도우 실행 파일(exe) 하나로 묶는다.

    python tools/build_exe.py

결과: dist/포켓데스크톱-vX.Y.Z.exe

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

NAME = "포켓데스크톱-v%s" % VERSION
ENTRY = os.path.join(ROOT, "client", "run.pyw")
ICON = os.path.join(ROOT, "build", "icon.ico")


def make_icon():
    """몬스터볼 아이콘을 직접 그려서 .ico 로 저장한다."""
    sys.path.insert(0, os.path.join(ROOT, "client"))
    from PIL import Image
    from poketdesktop import effects

    os.makedirs(os.path.dirname(ICON), exist_ok=True)
    key = (0, 255, 0)
    imgs = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        flat = effects.ball_image(size, key)
        # 투명색으로 칠한 배경을 실제 투명으로 되돌린다
        px = flat.tobytes()
        mask = bytearray(size * size)
        for i in range(0, len(px), 3):
            if (px[i], px[i + 1], px[i + 2]) != key:
                mask[i // 3] = 255
        rgba = flat.convert("RGBA")
        rgba.putalpha(Image.frombytes("L", flat.size, bytes(mask)))
        imgs.append(rgba)
    imgs[-1].save(ICON, format="ICO",
                  sizes=[(im.width, im.height) for im in imgs])
    print("  아이콘: %s" % ICON)
    return ICON


def build():
    print("포켓 데스크톱 v%s 빌드" % VERSION)
    icon = make_icon()

    for d in ("build/pyi", "dist"):
        p = os.path.join(ROOT, d)
        if os.path.exists(p):
            shutil.rmtree(p, ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",                      # 파일 하나로
        "--windowed",                     # 콘솔 창 없이
        "--name", NAME,
        "--icon", icon,
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

    exe = os.path.join(ROOT, "dist", NAME + ".exe")
    if not os.path.exists(exe):
        print("  실행 파일이 안 만들어졌습니다")
        return 1
    mb = os.path.getsize(exe) / 1048576.0
    print("")
    print("  완성: %s" % exe)
    print("  크기: %.1f MB" % mb)
    return 0


if __name__ == "__main__":
    sys.exit(build())
