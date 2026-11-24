# -*- coding: utf-8 -*-
"""배틀 창에서 포켓몬 도트의 키를 도감의 실제 키로 정한다 (2.5.5, 11/23 게시판 #777 댕댕킴).

예전에는 관장 · 실시간 · 레이드 배틀 창이 모든 도트를 같은 높이(내 쪽 132px · 상대 108px ...)로 늘리거나 줄였다.
그래서 따라큐(0.2m, 도트 66px)는 두 배로 커지고 리자몽(1.7m, 127px)은 그대로라 키가 같아 보였다. 쇼다운 도트의
원래 크기도 실제 키와 잘 안 맞는다 (따라큐 66px > 피카츄 59px, 고래왕 80px < 리자몽 127px - 823종을 재 보니 상관
0.63) - 그래서 도트 크기가 아니라 **도감의 키**로 정한다.

키를 그대로 비율로 쓰면 0.1m ~ 14.5m 라 너무 벌어진다. 로그로 눌러서 SMALL_M 이하는 칸 높이의 MIN_RATIO,
BIG_M 이상은 칸을 다 쓰고 그 사이는 완만하게 커진다:

    따라큐 · 파쪼옥 0.55 · 피카츄 0.62 · 이상해씨 0.75 · 1m 0.84 · 리자몽 0.96 · 잠만보 · 그란돈 · 고래왕 1.0

2.5.8 (11/24 게시판 #850 댕댕킴 '전체적으로 축소된 느낌'): 처음 값(0.3m 이하 0.45 ~ 3.5m 이상 1.0)은 사람만 한
포켓몬(1~2m)까지 80% 대로 줄여 화면이 비어 보였다. 위계는 두고 줄이는 폭만 줄였다 - 2m 부터 칸을 다 쓴다.

떠 있는 포켓몬 (2.5.8, 같은 글 '비행 포켓몬이 바닥에 박혀 있다'): 도트는 발(가장 아래 점)을 바닥에 붙여 세우는데,
날거나 떠 있는 모습의 도트도 그렇게 세워져 꼬리 · 날개 끝이 받침에 박혔다. 비행 타입이거나 부유 특성이 있는 종은
칸 높이의 FLOAT_LIFT 만큼 띄우고 발밑에 옅은 그림자를 둔다 (place · lifted). 도트 파일에는 '얼마나 떠 있나' 가 없어
(823종을 재 보니 바닥 여백이 거의 다 0) 타입 · 특성으로 정한다 - 서 있는 모습의 비행 타입도 살짝 뜬다.

도트는 지금처럼 발을 바닥에 붙여 세운다 (anchor "s") - 작아져도 떠 보이지 않는다. 메가 · 폼은 그 모습의 키
(도감 megas · forms 에 있다), 없으면 원래 종의 키. 키를 모르면 예전처럼 칸을 다 쓴다.
"""
import math

SMALL_M = 0.3           # 이 키(m) 이하는 가장 작게
BIG_M = 2.0             # 이 키 이상은 칸을 다 쓴다 (2.5.8: 3.5 -> 2.0)
MIN_RATIO = 0.55        # 가장 작은 포켓몬은 칸 높이의 이만큼 (2.5.8: 0.45 -> 0.55)
FLOAT_LIFT = 0.12       # 떠 있는 포켓몬을 띄우는 높이 (칸 높이의 몫)
SHADOW = (0, 0, 0, 70)  # 띄운 포켓몬 발밑의 그림자 (옅은 검정)


def ratio(height_m):
    """실제 키(m) -> 칸 높이에 곱할 몫 (MIN_RATIO ~ 1.0). 모르면 1.0 (예전과 같다)."""
    try:
        h = float(height_m)
    except (TypeError, ValueError):
        return 1.0
    if not h > 0:
        return 1.0
    t = (math.log(h) - math.log(SMALL_M)) / (math.log(BIG_M) - math.log(SMALL_M))
    t = max(0.0, min(1.0, t))
    return MIN_RATIO + (1.0 - MIN_RATIO) * t


def height_of(dex, num):
    """도감 번호의 키(m). 메가 · 폼에 키가 없으면 원래 종의 키. 모르면 None."""
    if dex is None or not num:
        return None
    try:
        sp = dex.get(int(num))
    except Exception:                                       # noqa: BLE001
        return None
    if not sp:
        return None
    h = sp.get("height")
    if h:
        return h
    base = sp.get("megaOf") or sp.get("formOf")
    if base:
        try:
            b = dex.get(base)
        except Exception:                                   # noqa: BLE001
            b = None
        if b and b.get("height"):
            return b["height"]
    return None


def fit(dex, num, size):
    """칸 높이 size(px) 를 이 포켓몬의 키에 맞춘 높이 (1px 이상)."""
    return max(1, int(round(size * ratio(height_of(dex, num)))))


def floats(dex, num):
    """떠 있는 모습으로 그릴 종인가: 비행 타입이거나 부유 특성이 있다 (그 종이 가질 수 있는 특성 - 상대의 특성은
    화면이 모를 수 있어 종으로 본다). 메가 · 폼은 그 모습의 타입 · 특성. 모르면 False."""
    if dex is None or not num:
        return False
    try:
        sp = dex.get(int(num))
    except Exception:                                       # noqa: BLE001
        return False
    if not sp:
        return False
    if "FLYING" in (sp.get("types") or ()):
        return True
    return "LEVITATE" in (sp.get("abil") or ()) or sp.get("hidden") == "LEVITATE"


def place(dex, num, box):
    """칸 높이 box(px) 에 이 포켓몬을 세울 (도트 높이, 띄울 높이). 띄운 만큼은 도트를 줄여 칸을 안 넘는다
    (칸을 다 쓰는 큰 비행 포켓몬 - 레쿠쟈 · 루기아 - 이 이름표를 가리지 않게)."""
    lift = max(1, int(round(box * FLOAT_LIFT))) if floats(dex, num) else 0
    return max(1, min(fit(dex, num, box), int(box) - lift)), lift


def lifted(frames, lift):
    """RGBA 그림들을 lift(px) 만큼 띄운 새 그림들: 아래에 투명한 띠를 덧대고 그 바닥에 옅은 그림자를 그린다.

    그림 자체를 키워 두면 창은 지금처럼 **아래를 바닥에 붙여** 세우기만 하면 된다 - 흔들기 · 돌진 · 쓰러짐 · 볼에서
    나오기 같은 연출이 자리를 다시 셈하지 않아도 된다. lift 가 0 이면 받은 그대로.
    """
    if not lift or not frames:
        return frames
    from PIL import Image, ImageDraw
    w, h = frames[0].size
    sw = max(6, int(w * 0.5))
    sh = max(3, min(int(lift * 0.6), int(sw * 0.3)))
    base = Image.new("RGBA", (w, h + lift), (0, 0, 0, 0))
    x0, y1 = (w - sw) // 2, h + lift - 1
    ImageDraw.Draw(base).ellipse((x0, y1 - sh, x0 + sw, y1), fill=SHADOW)
    out = []
    for f in frames:
        im = base.copy()
        f = f if f.mode == "RGBA" else f.convert("RGBA")
        im.alpha_composite(f, (0, 0))
        out.append(im)
    return out


# ---------------------------------------------------------------- 내 포켓몬 뒷모습 (2.5.8, 게시판 #850)
def back_view(app):
    """관장 · 실시간 배틀에서 내 포켓몬을 뒷모습으로 세우나 (설정 battleBack, 기본 켜짐)."""
    s = getattr(app, "settings", None) or {}
    return bool(s.get("battleBack", True))


def bind_flip(win):
    """배틀 창의 내 포켓몬 그림에 '누르면 앞뒤가 바뀐다' 를 건다. 몇 번 불러도 하나만 걸린다 (tag_bind 는 갈아 끼운다) -
    장면을 다시 지어 그림 칸이 새로 생겨도(창 크기 · 테마) 포켓몬을 세울 때마다 불러 두면 된다."""
    try:
        win.cv.tag_bind(win.sprite["me"], "<Button-1>", lambda _e=None: flip_me(win))
    except Exception:                                       # noqa: BLE001
        pass


def flip_me(win):
    """내 포켓몬을 눌렀다: 뒷모습 ↔ 앞모습. 이 PC 에 기억하고(설정 battleBack) 지금 선 포켓몬을 바로 다시 세운다."""
    app = getattr(win, "app", None)
    s = getattr(app, "settings", None)
    if s is None:
        return
    s["battleBack"] = not back_view(app)
    try:
        from . import config
        config.save_settings(s)
    except Exception:                                       # noqa: BLE001
        pass
    mon = (getattr(win, "shown", None) or {}).get("me")
    if mon and not mon.get("fainted"):
        win.set_mon("me", mon)
