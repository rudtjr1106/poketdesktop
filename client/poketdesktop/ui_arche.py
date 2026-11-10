# -*- coding: utf-8 -*-
"""아르케의 여섯 봉인 — 고고학자의 발굴 일지 (시안 A, 2026-11-09 사용자 고름).

펼친 수첩 한 장을 **PIL 로 낮은 해상도(380 x 236)에 그려 k 배로 키운다** (Galmuri11 · 도트 결).

    왼쪽 쪽   제N장 · 장소 · 날짜 / 큰 제목 / 고고학자의 일지 · 실마리 / 내가 본 것 (빨간 줄) - 넘치면 쪽 넘기기
    오른쪽 쪽 발굴 현장 사진 (봉인된 입구 · 열린 입구, 횃불이 흔들린다) / 글 / 도장 (푼 트레이너 · 첫 발견자) /
              내 봉인 상태 · 전설 자리 / '전설에게 간다'
    책갈피    1~6 (열린 장 붉은색 · 지난 장 갈색 · 앞 장 '?')
    아래      '떠오른 말을 적는다' (열쇠 입력 - 모든 OS. 윈도우는 브라우저 창 제목으로도 된다)

의식이 맞으면 컨트롤러(arche.ArcheController)가 `unsealed(n)` 을 부른다: 도장 "봉인이 풀렸다" → 사진이 창 가득 커진다 →
같은 자리에 전설 배틀 창(arche_battle)이 입장 장면부터 연다. 배틀 창이 닫히면 일지가 다시 보인다.

허브 '이벤트' 묶음의 '아르케' 탭(ArchePane)은 요약 + 일지 펼치기.
"""
import datetime
import re
import time
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from common.version import VERSION

from . import arche_art as A
from . import config
from . import ui_common as U

LW, LH = 380, 236
LEFT = (10, 9, 184, 214)           # 왼쪽 쪽 (x0, y0, x1, y1)
RIGHT = (192, 9, 364, 214)
TEXT_L = (18, 16, 178, 186)        # 왼쪽 글 칸
PHOTO = (202, 16, 354, 104)        # 사진 (흰 테 안쪽)
TABS_X = 364

COVER = (58, 40, 28)
COVER_HI = (88, 62, 42)
STITCH = (124, 92, 60)
PAPER = (239, 228, 200)
PAPER_SH = (222, 207, 170)
INK = (61, 43, 31)
INK_DIM = (138, 106, 72)
RED = (163, 58, 46)
SEEN_BG = (227, 213, 176)
TAB_PAST = (110, 90, 68)
TAB_FUT = (66, 50, 38)
GOOD = (52, 110, 74)

PLACE_KR = {"cave": "동굴", "volcano": "화산", "abyss": "심해", "sky": "구름 위", "castle": "모래 속 고성", "throne": "왕좌"}


# ---------------------------------------------------------------- 시각
def _ts(iso):
    try:
        t = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=datetime.timezone.utc)
        return t.timestamp()
    except Exception:                                       # noqa: BLE001
        return None


KST = datetime.timezone(datetime.timedelta(hours=9))


def _kst(ts, fmt="%m/%d %H:%M"):
    if ts is None:
        return ""
    s = datetime.datetime.fromtimestamp(ts, KST).strftime(fmt)
    return s.lstrip("0").replace("/0", "/")


def _left(sec):
    sec = max(0, int(sec or 0))
    if sec >= 86400:
        return "%d일 %d시간" % (sec // 86400, sec % 86400 // 3600)
    if sec >= 3600:
        return "%d시간 %d분" % (sec // 3600, sec % 3600 // 60)
    return "%d분" % max(1, sec // 60)


def _ver(v):
    try:
        return tuple(int(x) for x in str(v).split(".")[:3])
    except Exception:                                       # noqa: BLE001
        return (0, 0, 0)


# ---------------------------------------------------------------- 글자
def _font():
    return A.font(11)


def text_w(s):
    if not s:
        return 0
    l, t, r, b = _font().getbbox(s)
    return r - l


LINE_H = 13


def wrap(text, width):
    """글을 width 칸에 맞춰 줄로 (낱말을 되도록 안 자른다, 한글은 글자 단위로도). 글자 크기는 안 줄인다."""
    out = []
    for para in str(text or "").split("\n"):
        if not para:
            out.append("")
            continue
        cur = ""
        for word in para.split(" "):
            cand = (cur + " " + word) if cur else word
            if text_w(cand) <= width:
                cur = cand
                continue
            if cur:
                out.append(cur)
                cur = ""
            while text_w(word) > width:                     # 긴 낱말은 글자로 끊는다
                i = 1
                while i < len(word) and text_w(word[:i + 1]) <= width:
                    i += 1
                out.append(word[:i])
                word = word[i:]
            cur = word
        out.append(cur)
    return out


def _text(d, xy, s, fill=INK):
    d.text(xy, s, font=_font(), fill=fill)


def _big(im, xy, s, fill=INK):
    """큰 제목: Galmuri11 을 두 배로 (도트 결 그대로)."""
    small = A_text(s, fill)
    big = small.resize((small.width * 2, small.height * 2), Image.NEAREST)
    im.paste(big, xy, big)


def A_text(s, fill):
    f = _font()
    l, t, r, b = f.getbbox(s or " ")
    w, h = max(1, r - l + 1), max(1, b - t + 2)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    d.text((-l, -t), s, font=f, fill=fill)
    return im


# ---------------------------------------------------------------- 왼쪽 쪽 블록
PARADE_GW, PARADE_GH = 19, 23        # 행렬 글자 한 칸 (2배 글자 18x22 + 틈)


def _parade_per(width):
    return max(1, int((width - 8) // PARADE_GW))


def left_blocks(ch, seen, width):
    """왼쪽 쪽에 쌓을 블록들 [(kind, payload, height)]. 쪽 나누기는 높이로 한다."""
    blocks = []
    for e in ch.get("journal") or []:
        head = "고고학자의 일지 · %s" % _kst(_ts(e.get("at")))
        text = e.get("text") or ""
        lines = wrap(text, width)
        blocks.append(("entry", (head, lines, False), (len(lines) + 1) * LINE_H + 6, (text, width)))
    for e in ch.get("hints") or []:
        head = "고고학자의 일지 (실마리) · %s" % _kst(_ts(e.get("at")))
        text = e.get("text") or ""
        lines = wrap(text, width)
        blocks.append(("entry", (head, lines, True), (len(lines) + 1) * LINE_H + 6, (text, width)))
    for r in seen:
        head = "내가 본 것 · %s" % _kst(r.get("at"))
        kind = r.get("kind")
        if kind == "parade":
            gl = r.get("glyphs") or []
            got = sum(1 for g in gl if g is not None)
            lines = wrap("작은 것들이 줄지어 지나갔다. 본 글자 %d / %d" % (got, len(gl)), width - 6)
            rows = (len(gl) + _parade_per(width) - 1) // _parade_per(width)
            blocks.append(("seen", (head, lines, r), (len(lines) + 1) * LINE_H + rows * PARADE_GH + 8))
            continue
        if kind == "unown" and r.get("glyph") is not None:
            lines = wrap("안농이 지나가며 글자 하나를 떨궜다.", width - 6)
            blocks.append(("seen", (head, lines, r), (len(lines) + 1) * LINE_H + 26))
            continue
        if kind == "relic":
            lines = wrap("떨어진 돌 조각에 새겨진 글: " + (r.get("text") or "…"), width - 6)
        elif kind == "stars":
            lines = wrap("화면 위쪽에 별이 떴다.", width - 6)
            blocks.append(("seen", (head, lines, r), (len(lines) + 1) * LINE_H + 34))
            continue
        else:
            lines = wrap({"drip": "어디선가 물방울이 떨어졌다.", "sand": "모래바람이 바탕화면을 쓸고 지나갔다.",
                          "tremor": "포켓몬들이 무언가에 놀라 몸을 떨었다."}.get(kind, "무언가를 봤다."), width - 6)
        blocks.append(("seen", (head, lines, r), (len(lines) + 1) * LINE_H + 8))
    if not blocks:
        blocks.append(("entry", ("", wrap("아직 적힌 것이 없다.", width), False), 2 * LINE_H))
    return blocks


# 문장이 끝나는 곳: 마침표 · 물음표 · 느낌표 · 말줄임 (닫는 따옴표 · 괄호까지) 뒤에 빈칸이나 글 끝
_SENT_END = re.compile(r"[.!?…](?:[\"'”’)\]」』]*)(?=\s|$)")


def _sentence_ends(text):
    """글 안에서 쪽을 끊어도 되는 자리 (문장 끝 · 문단 끝) 들 - 오름차순."""
    ends = {m.end() for m in _SENT_END.finditer(text)}
    ends.update(m.start() for m in re.finditer(r"\n", text))
    ends.add(len(text))
    return sorted(e for e in ends if e > 0)


def split_at_sentence(text, width, max_lines):
    """text 앞에서 max_lines 줄 안에 드는 가장 긴 '문장 끝' 까지 자른다 -> (그 줄들, 나머지 글).
    한 문장도 안 들어가면 ([], text). 나머지 글 앞의 빈칸 · 빈 줄은 뗀다 (다음 쪽이 빈 줄로 시작하지 않게)."""
    best = None
    for e in _sentence_ends(text):
        if len(wrap(text[:e].rstrip(), width)) <= max_lines:
            best = e
        else:
            break
    if best is None or not text[:best].strip():
        return [], text
    return wrap(text[:best].rstrip(), width), text[best:].lstrip(" \n")


def paginate(blocks, first_h, h):
    """블록을 쪽으로 나눈다 (첫 쪽은 제목만큼 짧다). **글 하나가 남은 자리보다 길면 다음 쪽으로 잇는다** -
    전에는 긴 일지 글 하나가 한 쪽에 통째로 들어가 쪽 아래로 넘쳐 그려졌다 (11/09 시연).
    **잇는 곳은 문장이 끝나는 곳** - 줄 단위로 끊으면 '새겨져 / 있다.' 처럼 말 끝이 다음 쪽으로 넘어갔다 (11/10 사용자).
    한 문장이 빈 쪽보다도 길 때만 줄 단위로 끊는다. 블록 넷째 칸 (글, 폭) 이 있으면 문장으로, 없으면 줄로 나눈다."""
    pages, cur, room = [], [], first_h
    for blk in blocks:
        kind, payload, bh = blk[:3]
        src = blk[3] if len(blk) > 3 else None
        while True:
            if bh <= room:
                cur.append((kind, payload, bh))
                room -= bh
                break
            head, lines, extra = payload
            if kind == "entry" and src is not None:
                text, width = src
                head_h = LINE_H if head else 0
                fit = int((room - 6 - head_h) // LINE_H)
                first, rest = split_at_sentence(text, width, fit) if fit >= 1 else ([], text)
                if first and not rest:                      # 다 들어간다 (높이 셈 반올림 차이)
                    cur.append((kind, (head, first, extra), head_h + len(first) * LINE_H + 6))
                    room -= head_h + len(first) * LINE_H + 6
                    break
                if first and rest:
                    cur.append((kind, (head, first, extra), head_h + len(first) * LINE_H + 6))
                    pages.append(cur)
                    cur, room = [], h
                    rl = wrap(rest, width)
                    payload, bh, src = ("", rl, extra), len(rl) * LINE_H + 6, (rest, width)
                    continue
                if cur:                                     # 이 쪽엔 한 문장도 안 들어간다 - 새 쪽에서 다시
                    pages.append(cur)
                    cur, room = [], h
                    continue
                src = None                                  # 빈 쪽보다 긴 한 문장 - 줄 단위로
            if kind == "entry" and len(lines) > 1:
                head_h = LINE_H if head else 0
                fit = int((room - 6 - head_h) // LINE_H)
                if fit >= 1:
                    cur.append((kind, (head, lines[:fit], extra), head_h + fit * LINE_H + 6))
                    payload, bh = ("", lines[fit:], extra), len(lines[fit:]) * LINE_H + 6
                    pages.append(cur)
                    cur, room = [], h
                    continue
            if cur:
                pages.append(cur)
                cur, room = [], h
                continue
            cur.append((kind, payload, bh))                 # 빈 쪽에도 안 들어가는 그림 블록 - 그대로 둔다
            room -= bh
            break
    pages.append(cur)
    return pages


# ---------------------------------------------------------------- 수첩 그리기
def draw_book(state, n, page, ctl, t=0, stamp=None, version=VERSION):
    """수첩 한 장 (LW x LH, RGB). 돌려주는 것: (그림, 누를 곳 {이름: (x0,y0,x1,y1)}, 쪽 수)."""
    im = Image.new("RGB", (LW, LH), COVER)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    hits = {}
    # 표지 테 · 바느질
    d.rectangle([2, 2, LW - 3, LH - 3], outline=COVER_HI)
    for x in range(6, LW - 6, 4):
        d.point([(x, 4), (x, LH - 5)], fill=STITCH)
    # 쪽 (아래로 쌓인 종이 두 겹)
    for (x0, y0, x1, y1) in (LEFT, RIGHT):
        d.rectangle([x0, y0 + 3, x1, y1 + 3], fill=PAPER_SH)
        d.rectangle([x0, y0 + 1, x1, y1 + 1], fill=(230, 217, 184))
        d.rectangle([x0, y0, x1, y1], fill=PAPER)
    for x in range(LEFT[2] - 6, LEFT[2] + 1):           # 가운데 접힌 그늘
        k = (x - (LEFT[2] - 6)) / 7.0
        for y in range(LEFT[1], LEFT[3] + 1):
            if (x + y) % 2 == 0 or k > 0.7:
                im.putpixel((x, y), _mix(PAPER, (196, 178, 140), k * 0.8))
    for x in range(RIGHT[0], RIGHT[0] + 6):
        k = 1 - (x - RIGHT[0]) / 6.0
        for y in range(RIGHT[1], RIGHT[3] + 1):
            if (x + y) % 2 == 0 or k > 0.7:
                im.putpixel((x, y), _mix(PAPER, (196, 178, 140), k * 0.8))

    chapters = (state or {}).get("chapters") or []
    ch = next((c for c in chapters if int(c.get("n") or 0) == n), None)
    # 책갈피
    for i in range(6):
        c = next((c for c in chapters if int(c.get("n") or 0) == i + 1), {})
        y0 = 18 + i * 32
        on = (i + 1) == n
        col = RED if c.get("open") else (TAB_PAST if c.get("past") else TAB_FUT)
        x1 = LW - 3 if on else LW - 6
        d.rectangle([TABS_X + 1, y0, x1, y0 + 26], fill=col)
        d.rectangle([TABS_X + 1, y0, x1, y0], fill=_mix(col, (255, 255, 255), 0.25))
        lab = str(i + 1) if (c.get("open") or c.get("past")) else "?"
        _text(d, (TABS_X + 4 + (1 if on else 0), y0 + 8), lab, (255, 246, 230) if c.get("open") else (220, 204, 176))
        hits["tab%d" % (i + 1)] = (TABS_X, y0, LW - 2, y0 + 26)

    if not (state or {}).get("ready", True) or ch is None:
        _big(im, (LEFT[0] + 10, 30), "아르케의 여섯 봉인")
        for i, s in enumerate(wrap("고고학자가 아직 발굴 일지를 정리하고 있다. 조금 뒤에 다시 펼쳐 보자.", TEXT_L[2] - TEXT_L[0])):
            _text(d, (TEXT_L[0], 70 + i * LINE_H), s, INK)
        return im, hits, 1

    width = TEXT_L[2] - TEXT_L[0]
    place = ch.get("place") or "cave"
    opens, closes = _ts(ch.get("opensAt")), _ts(ch.get("closesAt"))
    head = "제%d장 · %s · %s ~ %s" % (n, ch.get("placeKr") or PLACE_KR.get(place, ""), _kst(opens, "%m/%d"),
                                     _kst(closes - 1 if closes else None, "%m/%d"))
    future = bool(ch.get("future")) or (not ch.get("open") and not ch.get("past"))
    old = _ver(version) < _ver(ch.get("minClient") or "0")

    # ----- 왼쪽 (장 머리줄 · 큰 제목은 첫 쪽에만 - 넘긴 쪽은 이어진 글이 맨 위부터)
    if future or page <= 0:
        _text(d, (TEXT_L[0], TEXT_L[1]), head, INK_DIM)
        _big(im, (TEXT_L[0], TEXT_L[1] + 14), ch.get("title") or "?")
    pages = 1
    if future:
        for i, s in enumerate(wrap("아직 펼쳐지지 않은 쪽이다. 고고학자의 일지는 %s 에 이어진다." % _kst(opens), width)):
            _text(d, (TEXT_L[0], TEXT_L[1] + 50 + i * LINE_H), s, INK_DIM)
    else:
        seen = ctl.seen_in(n) if ctl is not None else []
        blocks = left_blocks(ch, seen, width)
        top = TEXT_L[1] + 44
        pgs = paginate(blocks, TEXT_L[3] - top, TEXT_L[3] - TEXT_L[1])
        pages = len(pgs)
        page = max(0, min(page, pages - 1))
        y = top if page == 0 else TEXT_L[1]
        for kind, payload, h in pgs[page]:
            head2, lines, extra = payload
            if kind == "seen":
                d.rectangle([TEXT_L[0] - 2, y - 1, TEXT_L[2], y + h - 4], fill=SEEN_BG)
                d.rectangle([TEXT_L[0] - 2, y - 1, TEXT_L[0], y + h - 4], fill=RED)
                _text(d, (TEXT_L[0] + 3, y), head2, INK_DIM)
                for i, s in enumerate(lines):
                    _text(d, (TEXT_L[0] + 3, y + (i + 1) * LINE_H), s, INK)
                yy = y + (len(lines) + 1) * LINE_H + 1
                if extra.get("kind") == "unown" and extra.get("glyph") is not None:
                    g = A.glyph(int(extra["glyph"]), 2, (30, 120, 108), glow=False)
                    im.paste(g, (TEXT_L[0] + 4, yy - 2), g)
                elif extra.get("kind") == "parade":
                    per = _parade_per(TEXT_L[2] - TEXT_L[0])
                    for i, gi in enumerate(extra.get("glyphs") or []):
                        gx = TEXT_L[0] + 4 + (i % per) * PARADE_GW
                        gy = yy + (i // per) * PARADE_GH
                        if gi is None:                      # 놓친 자리 - 빈칸 표시
                            d.rectangle([gx + 6, gy + 9, gx + 11, gy + 10], fill=INK_DIM)
                            continue
                        try:
                            g = A.glyph(int(gi), 2, (30, 120, 108), glow=False)
                            im.paste(g, (gx, gy - 2), g)
                        except (TypeError, ValueError):
                            pass
                elif extra.get("kind") == "stars":
                    d.rectangle([TEXT_L[0] + 3, yy, TEXT_L[2] - 4, yy + 22], fill=(24, 30, 52))
                    for p in extra.get("pts") or []:
                        try:
                            px = TEXT_L[0] + 4 + int(float(p[0]) * (TEXT_L[2] - TEXT_L[0] - 10))
                            py = yy + 1 + int(float(p[1]) * 20)
                            d.point([(px, py)], fill=(255, 255, 255))
                            if len(p) > 2 and int(p[2]) > 0:
                                d.point([(px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)], fill=(160, 176, 230))
                        except Exception:                   # noqa: BLE001
                            pass
            else:
                if head2:
                    _text(d, (TEXT_L[0], y), head2, RED if extra else INK_DIM)
                for i, s in enumerate(lines):
                    _text(d, (TEXT_L[0], y + (i + 1 if head2 else i) * LINE_H), s, INK)
            y += h
        if pages > 1:
            lab = "◀ %d / %d ▶" % (page + 1, pages)
            x = TEXT_L[2] - text_w(lab)
            _text(d, (x, TEXT_L[3] + 2), lab, INK_DIM)
            hits["prev"] = (x - 2, TEXT_L[3], x + 12, TEXT_L[3] + 14)
            hits["next"] = (TEXT_L[2] - 12, TEXT_L[3], TEXT_L[2] + 2, TEXT_L[3] + 14)

    # ----- 오른쪽
    if future:
        d.rectangle([PHOTO[0] - 4, PHOTO[1] - 4, PHOTO[2] + 4, PHOTO[3] + 16], fill=(214, 200, 166))
        _big(im, ((PHOTO[0] + PHOTO[2]) // 2 - 8, (PHOTO[1] + PHOTO[3]) // 2 - 12), "?", INK_DIM)
        return im, hits, pages
    # 사진
    d.rectangle([PHOTO[0] - 3, PHOTO[1] - 3, PHOTO[2] + 5, PHOTO[3] + 17], fill=(180, 164, 128))
    d.rectangle([PHOTO[0] - 4, PHOTO[1] - 4, PHOTO[2] + 4, PHOTO[3] + 16], fill=(250, 248, 242))
    pw, ph = PHOTO[2] - PHOTO[0], PHOTO[3] - PHOTO[1]
    hits["photo"] = PHOTO
    cap = ch.get("caption") or ("%s · %s" % (ch.get("title") or "", "봉인이 풀렸다" if ch.get("ritual") else "굳게 닫혀 있다"))
    cl = wrap(cap, pw)
    one = cl[0] if cl else ""
    if len(cl) > 1:                                          # 한 줄 칸이다 - 넘치면 줄임표 (글자는 안 줄인다)
        while one and text_w(one + "…") > pw:
            one = one[:-1]
        one += "…"
    _text(d, (PHOTO[0] + (pw - text_w(one)) // 2, PHOTO[3] + 3), one, (106, 84, 64))
    # 글 · 상태
    y = PHOTO[3] + 22
    if old:
        for s in wrap("이 장은 새 판(%s)에서 볼 수 있어요. 트레이 메뉴에서 업데이트해 주세요." % ch.get("minClient"), pw):
            _text(d, (PHOTO[0], y), s, RED)
            y += LINE_H
        return im, hits, pages
    solvers = int(ch.get("solvers") or 0)
    if ch.get("open") and not ch.get("ritual"):
        _text(d, (PHOTO[0], y), "봉인", INK_DIM)
        _text(d, (PHOTO[2] - text_w("굳게 닫혀 있다"), y), "굳게 닫혀 있다", INK)
        y += LINE_H + 2
        left = (closes - time.time()) if closes else 0
        _text(d, (PHOTO[0], y), "장이 닫히기까지", INK_DIM)
        s = _left(left)
        _text(d, (PHOTO[2] - text_w(s), y), s, RED)
        y += LINE_H + 2
    elif ch.get("ritual"):
        _text(d, (PHOTO[0], y), "봉인이 풀렸다!", GOOD)
        y += LINE_H + 2
        for e in ch.get("encounters") or []:
            st = e.get("state")
            lab = "석실 %d" % (int(e.get("slot") or 0) + 1)
            s = {"caught": "잡았다" + (" · " + e["name"] if e.get("name") else ""), "ready": "기다린다",
                 "locked": "닫혀 있다"}.get(st, st or "")
            _text(d, (PHOTO[0], y), lab, INK_DIM)
            _text(d, (PHOTO[2] - text_w(s), y), s, GOOD if st == "caught" else INK)
            y += LINE_H
    else:
        _text(d, (PHOTO[0], y), "봉인은 다시 닫혔다.", INK_DIM)
        y += LINE_H + 2
    # 전설에게 간다
    if ch.get("ritual") and any(e.get("state") == "ready" for e in ch.get("encounters") or []):
        lab = "전설에게 간다 ▶"
        bw = text_w(lab) + 12
        bx, by = PHOTO[0], RIGHT[3] - 20
        d.rectangle([bx, by, bx + bw, by + 15], fill=RED)
        d.rectangle([bx, by, bx + bw, by], fill=_mix(RED, (255, 255, 255), 0.3))
        _text(d, (bx + 6, by + 2), lab, (255, 246, 230))
        hits["go"] = (bx, by, bx + bw, by + 15)
    return im, hits, pages


def stamp_overlay(ch, stamp=None):
    """사진 오른쪽 위 모서리에 찍힌 도장 (RGBA 낮은 해상도, (x, y)). 사진 위에 따로 얹는다."""
    if not ch or ch.get("future") or (not ch.get("open") and not ch.get("past")):
        return None, None
    solvers = int(ch.get("solvers") or 0)
    if stamp:
        lines = [stamp]
    elif solvers <= 0:
        lines = ["아직 아무도 못 열었다"]
    else:
        lines = ["봉인을 연 트레이너 %d명" % solvers]
        if ch.get("first"):
            lines.append("첫 발견자 · %s" % ch["first"])
    sw = max(text_w(x) for x in lines) + 10
    sh = LINE_H * len(lines) + 4
    im = Image.new("RGBA", (sw + 1, sh + 1), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    d.rectangle([0, 0, sw, sh], fill=PAPER + (255,), outline=RED)
    d.rectangle([1, 1, sw - 1, sh - 1], outline=_mix(RED, PAPER, 0.5))
    for i, x in enumerate(lines):
        d.text((5, 2 + i * LINE_H), x, font=_font(), fill=RED)
    return im, (PHOTO[2] - sw + 4, PHOTO[1] - 6)


def _mix(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def photo_img(ch, t, k):
    """사진 칸에 들어갈 장소 그림 (k 배). 의식 전 봉인 · 뒤 열린 입구."""
    pw, ph = PHOTO[2] - PHOTO[0], PHOTO[3] - PHOTO[1]
    marks = ch.get("marks") or None
    try:                                                     # 모양이 틀린 값이 와도 창이 터지지 않게 (리뷰)
        marks = [[int(g) for g in m] for m in marks] if marks else None
    except (TypeError, ValueError):
        marks = None
    state = "open" if ch.get("ritual") else "sealed"
    return A.scene(ch.get("place") or "cave", pw * k, ph * k, state, t, marks)


# ---------------------------------------------------------------- 창
class JournalWindow(object):
    """아르케의 발굴 일지 창."""

    def __init__(self, app, ctl):
        self.app, self.ctl = app, ctl
        self.root = app.root
        self.alive = True
        self.n = int(((ctl.state or {}).get("chapter")) or 1) or 1
        self.pages = {}
        self.t = 0
        self.stamp = None
        self.hits = {}
        self.k = max(2, int(round(U.h(472) / float(LH))))
        self.cw, self.ch = LW * self.k, LH * self.k + U.h(44)
        self.win = tk.Toplevel(self.root)
        U.style_window(self.win, "아르케의 여섯 봉인 — 고고학자의 발굴 일지", self.cw, self.ch)
        self.win.configure(bg="#3a281c")
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.cv = tk.Canvas(self.win, width=self.cw, height=LH * self.k, bg="#3a281c", highlightthickness=0, cursor="arrow")
        self.cv.pack()
        self.cv.bind("<Button-1>", self._click)
        self.cv.bind("<Motion>", self._hover)
        self.book = self.cv.create_image(0, 0, anchor="nw")
        self.photo = self.cv.create_image(PHOTO[0] * self.k, PHOTO[1] * self.k, anchor="nw")
        self.stamp_item = self.cv.create_image(0, 0, anchor="nw")
        bar = tk.Frame(self.win, bg="#3a281c")
        bar.pack(fill="x", padx=U.h(14), pady=(U.h(4), U.h(8)))
        tk.Label(bar, text="떠오른 말을 적는다", bg="#3a281c", fg="#e7d6b0", font=U.FONT_S).pack(side="left")
        self.entry = tk.Entry(bar, bg="#efe4c8", fg="#3d2b1f", insertbackground="#3d2b1f", relief="flat",
                              font=U.FONT, width=28)
        self.entry.pack(side="left", padx=U.h(8), ipady=U.h(3))
        self.entry.bind("<Return>", lambda e: self.send())
        self.send_btn = tk.Button(bar, text="새긴다", command=self.send, relief="flat", bg="#a33a2e", fg="#fff6e6",
                                  activebackground="#8a2f25", activeforeground="#fff", font=U.FONT_S, cursor="hand2")
        self.send_btn.pack(side="left")
        self.msg = tk.Label(bar, text="", bg="#3a281c", fg="#e7d6b0", font=U.FONT_S, anchor="w")
        self.msg.pack(side="left", padx=U.h(10), fill="x", expand=True)
        self._imgs = {}
        self.refresh()
        self._tick_job = self.root.after(400, self._tick)
        self.focus()

    # ---------------- 틀
    def focus(self):
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except Exception:                                   # noqa: BLE001
            pass

    def close(self):
        self.alive = False
        try:
            self.root.after_cancel(self._tick_job)
        except Exception:                                   # noqa: BLE001
            pass
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        if getattr(self.ctl, "window", None) is self:
            self.ctl.window = None

    def geometry(self):
        try:
            self.win.update_idletasks()
            return "%dx%d+%d+%d" % (self.win.winfo_width(), self.win.winfo_height(),
                                    self.win.winfo_rootx(), self.win.winfo_rooty())
        except Exception:                                   # noqa: BLE001
            return None

    def show_chapter(self, n):
        self.n = int(n)
        self.refresh()

    # ---------------- 그리기
    def _chapter(self):
        return self.ctl.chapter(self.n) if self.ctl is not None else None

    def refresh(self):
        if not self.alive:
            return
        st = self.ctl.state if self.ctl is not None else None
        page = self.pages.get(self.n, 0)
        im, self.hits, pages = draw_book(st, self.n, page, self.ctl, self.t, self.stamp)
        if page >= pages:
            self.pages[self.n] = pages - 1
        big = im.resize((LW * self.k, LH * self.k), Image.NEAREST)
        self._imgs["book"] = ImageTk.PhotoImage(big)
        self.cv.itemconfigure(self.book, image=self._imgs["book"])
        self._paint_photo()
        ch = self._chapter() or {}
        sim, sxy = stamp_overlay(ch, self.stamp)
        if sim is not None:
            sim = sim.resize((sim.width * self.k, sim.height * self.k), Image.NEAREST)
            self._imgs["stamp"] = ImageTk.PhotoImage(sim)
            self.cv.coords(self.stamp_item, sxy[0] * self.k, sxy[1] * self.k)
            self.cv.itemconfigure(self.stamp_item, image=self._imgs["stamp"])
            self.cv.tag_raise(self.stamp_item)
        else:
            self.cv.itemconfigure(self.stamp_item, image="")
        can = bool(ch.get("open")) and not ch.get("ritual")
        try:
            self.entry.configure(state="normal" if can else "disabled")
            self.send_btn.configure(state="normal" if can else "disabled")
        except Exception:                                   # noqa: BLE001
            pass

    def _paint_photo(self):
        ch = self._chapter()
        if not ch or "photo" not in self.hits:
            self.cv.itemconfigure(self.photo, image="")
            return
        im = photo_img(ch, self.t, self.k)
        self._imgs["photo"] = ImageTk.PhotoImage(im)
        self.cv.itemconfigure(self.photo, image=self._imgs["photo"])

    def _tick(self):
        """횃불 · 물결이 흔들린다 (사진만 다시 칠한다 - 작은 그림)."""
        if not self.alive:
            return
        self.t = (self.t + 1) % 12
        self._paint_photo()
        self._tick_job = self.root.after(400, self._tick)

    # ---------------- 누르기
    def _at(self, e):
        x, y = e.x / float(self.k), e.y / float(self.k)
        for name, (x0, y0, x1, y1) in self.hits.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return name
        return None

    def _hover(self, e):
        name = self._at(e)
        self.cv.configure(cursor="hand2" if name and name != "photo" else "arrow")

    def _click(self, e):
        name = self._at(e)
        if not name:
            return
        if name.startswith("tab"):
            self.show_chapter(int(name[3:]))
        elif name == "prev":
            self.pages[self.n] = max(0, self.pages.get(self.n, 0) - 1)
            self.refresh()
        elif name == "next":
            self.pages[self.n] = self.pages.get(self.n, 0) + 1
            self.refresh()
        elif name == "go":
            self.go()

    # ---------------- 열쇠
    def send(self):
        text = (self.entry.get() or "").strip()
        ch = self._chapter() or {}
        if not text or not ch.get("open") or ch.get("ritual"):
            return
        self.msg.configure(text="돌판에 새기는 중…")
        self.send_btn.configure(state="disabled")

        def done(r, err):
            if not self.alive:
                return
            self.send_btn.configure(state="normal")
            if err:
                code = getattr(err, "status", None)
                self.msg.configure(text="너무 많이 새겼다. 손을 좀 쉬었다가 다시 해 보자." if code == 429
                                   else getattr(err, "message", str(err)))
                return
            if r.get("ok"):
                self.entry.delete(0, "end")
                self.msg.configure(text="돌판이 희미하게 빛났다. 무언가 맞아떨어진 것 같다…")
            else:
                self.msg.configure(text="…아무 일도 일어나지 않았다.")

        self.ctl.send_key(self.n, text, "type", done)

    # ---------------- 입장
    def unsealed(self, n):
        """의식이 맞았다 (컨트롤러). 도장을 찍고, 사진이 창 가득 커진 뒤 전설에게 간다."""
        self.show_chapter(n)
        self.focus()
        self.stamp = "봉인이 풀렸다"
        self.refresh()
        self.root.after(1400, self.go)

    def go(self):
        ch = self._chapter() or {}
        slot = next((int(e.get("slot") or 0) for e in ch.get("encounters") or [] if e.get("state") == "ready"), None)
        if slot is None:
            return
        self.stamp = None
        self.cv.itemconfigure(self.stamp_item, image="")
        self._grow(lambda: self._open_battle(slot))

    def _grow(self, done, steps=7):
        """사진이 창 가득 커진다 (같은 장소 그림을 점점 크게 - 이어서 배틀 창의 입장 장면이 같은 그림부터 연다)."""
        ch = self._chapter() or {}
        x0, y0, x1, y1 = [v * self.k for v in PHOTO]
        W, H = LW * self.k, LH * self.k
        place = ch.get("place") or "cave"

        def step(i):
            if not self.alive:
                return
            f = (i / float(steps)) ** 1.5
            ax, ay = int(x0 * (1 - f)), int(y0 * (1 - f))
            bx, by = int(x1 + (W - x1) * f), int(y1 + (H - y1) * f)
            im = A.scene(place, max(8, bx - ax), max(8, by - ay), "open" if ch.get("ritual") else "sealed",
                         self.t, ch.get("marks"))
            self._imgs["photo"] = ImageTk.PhotoImage(im)
            self.cv.coords(self.photo, ax, ay)
            self.cv.itemconfigure(self.photo, image=self._imgs["photo"])
            if i < steps:
                self.root.after(55, lambda: step(i + 1))
            else:
                self.root.after(80, done)

        step(1)

    def _open_battle(self, slot):
        geo = self.geometry()

        def closed(err):
            if not self.alive:
                return
            try:
                self.win.deiconify()
            except Exception:                               # noqa: BLE001
                pass
            self.cv.coords(self.photo, PHOTO[0] * self.k, PHOTO[1] * self.k)
            if err:
                self.msg.configure(text=err)
            self.refresh()

        self.ctl.open_battle(self.n, slot, geometry=geo, on_close=closed)
        self.root.after(350, self._hide_under_battle)

    def _hide_under_battle(self):
        b = getattr(self.ctl, "battle", None)
        if b is not None and getattr(b, "alive", False):
            try:
                self.win.withdraw()
            except Exception:                               # noqa: BLE001
                pass
        else:
            self.cv.coords(self.photo, PHOTO[0] * self.k, PHOTO[1] * self.k)
            self.refresh()


# ---------------------------------------------------------------- 허브 탭 · 메뉴
class ArchePane(object):
    """허브 '이벤트' 묶음의 '아르케' 탭: 지금 장 요약 + 일지 펼치기."""

    def __init__(self, app, holder):
        self.app = app
        # 허브가 pane.win.pack 으로 붙인다 (스스로 붙지 않는다 - 리뷰 C2: win 이 없어 탭을 열 때마다 터졌다)
        self.win = self.frame = tk.Frame(holder, bg=U.BG)
        self.title = tk.Label(self.frame, text="아르케의 여섯 봉인", bg=U.BG, fg=U.FG, font=U.FONT_H, anchor="w")
        self.title.pack(fill="x", padx=U.h(18), pady=(U.h(16), U.h(4)))
        self.body = tk.Label(self.frame, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT, anchor="nw", justify="left",
                             wraplength=U.h(520))
        self.body.pack(fill="x", padx=U.h(18))
        U.PushButton(self.frame, text="고고학자의 일지 펼치기", command=self.open).pack(anchor="w", padx=U.h(18), pady=U.h(12))
        self.on_shown()

    def open(self):
        ctl = getattr(self.app, "arche", None)
        if ctl is not None:
            ctl.open_window()

    def on_shown(self):
        ctl = getattr(self.app, "arche", None)
        st = (ctl.state if ctl is not None else None) or {}
        n = int(st.get("chapter") or 0)
        c = ctl.chapter(n) if (ctl is not None and n) else None
        if not st.get("active"):
            text = ("시즌 6 첫날 밤, 게시판에 처음 보는 이름으로 글이 올라온다. 어느 고고학자의 발굴 일지…\n"
                    "11월 16일 0시부터 2주 동안 열립니다.")
        elif c:
            text = ("지금 열린 장: 제%d장 「%s」 (%s)\n봉인을 연 트레이너 %d명%s\n\n"
                    "단서는 바탕화면 · 게임 속 · 웹 곳곳에 흩어져 있어요. 본 것은 일지의 '내가 본 것'에 남아요."
                    % (n, c.get("title") or "?", c.get("placeKr") or "", int(c.get("solvers") or 0),
                       (" · 첫 발견자 " + c["first"]) if c.get("first") else ""))
        else:
            text = "지금은 열린 장이 없어요."
        self.body.configure(text=text)

    def reload(self):
        self.on_shown()


def menu_row(app, pet):
    ctl = getattr(app, "arche", None)
    if ctl is None or not ctl.on() or (getattr(pet, "id", 0) or 0) <= 0:
        return None
    return {"text": "아르케의 일지...", "command": lambda: ctl.open_window()}


def open_journal(app):
    ctl = getattr(app, "arche", None)
    if ctl is None:
        return None
    return ctl.open_window()
