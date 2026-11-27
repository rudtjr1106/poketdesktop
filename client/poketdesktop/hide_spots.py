# -*- coding: utf-8 -*-
"""숨바꼭질 (시즌 7) - 숨은 포켓몬이 반쯤 보일 자리를 고른다. **창 · Tk 를 안 쓰는 순수 함수**만 둔다.

자리는 셋 (design-notes/2026-11-27-hide-and-seek.md '사용자가 보는 것' 2):

    window  가장 앞의 보통 창 바로 **뒤** - 그 창의 위 · 왼쪽 · 오른쪽 가장자리 너머로 빼꼼 (나머지는 그 창에 진짜로 가려진다)
    bar     작업표시줄(맥은 Dock) 바로 **아래 층** - 작업 영역 쪽으로 빼꼼 (나머지는 작업표시줄 자리)
    edge    모든 보통 창 **뒤** (바탕화면 바로 위) - 화면 가장자리에서 빼꼼 (나머지는 화면 밖)

좌표는 전부 Tk 화면 좌표다 (윈도우 · 맥 둘 다 왼쪽 위가 원점, y 가 아래로. 왼쪽/위 모니터는 음수).
'side' 는 **빼꼼 내미는 쪽** 이다 - top 이면 몸의 위쪽이 보이고(아래에서 위로 내민다), left 면 몸의 왼쪽이 보인다.
bottom 은 위에서 아래로 내민다 (위 작업표시줄 · 화면 위 가장자리 - 그림은 거꾸로 뒤집어 머리가 아래로 나온다).

지키는 것 (계획 Global Constraints '자리 규칙'):
  · 활동 영역이 있는 모니터만, 모니터끼리 붙은 변은 안 쓴다 (몸의 나머지가 옆 화면에 보인다)
  · 활동 영역에서 AREA_GAP 넘게 떨어진다, 작업 영역 모서리 CORNER 안은 안 쓴다 (시작 단추 · 시계 · 창 닫기 단추)
  · 몸의 40~55% 만 보인다 (SHOW_PX 이상), 맥은 위쪽 변(메뉴 막대)을 안 쓴다
  · 창 뒤 자리는 가장 앞의 보통 창(최대화 아님, 200x150 이상, 윈도우는 DPI 가 다르지 않은 창)만
  · **지금 보이는 자리만** - 바탕화면 가장자리는 어느 창도 안 덮은 곳, 창 뒤 자리는 그 창보다 앞의 창이 안 덮은 곳
    ('어느 창' 에는 이 앱의 테두리 있는 창(own) · 남의 '항상 위' 창(top)도 든다 - 걸지는 않고 가리는 것으로만 본다)
  · 윈도우는 오른쪽 변 · 작업표시줄을 먼저 (바탕화면 아이콘이 왼쪽에 있다), 맥은 왼쪽 변 · Dock 을 먼저 (아이콘이 오른쪽)
"""

KINDS = ("window", "bar", "edge")

AREA_GAP = 120         # 활동 영역에서 이만큼 넘게 (도트가 걷다 숨은 포켓몬에 닿지 않게)
CORNER = 160           # 작업 영역 네 모서리에서 이 안은 안 쓴다
SHOW_MIN, SHOW_MAX = 0.40, 0.55
SHOW_PX = 22           # 몸이 작아도 이만큼은 보이게 (찾을 수 있어야 한다)
PEEK_MORE = 0.70       # 200초쯤 한 번 이만큼 내민다 (자리를 볼 때 이것까지 안에 들어가야 한다)
WIN_MIN_W, WIN_MIN_H = 200, 150
WIN_INSET = 24         # 창 가장자리의 양 끝 (창 모서리 둥근 자리 · 단추)에서 이만큼 안쪽
BAR_MIN = 24           # 작업 영역이 화면보다 이만큼 넘게 들어가 있으면 그쪽에 작업표시줄/Dock 이 있다 (그보다 작으면 자동 숨김)
MAX_FILL = 0.97        # 작업 영역을 이만큼 넘게 덮은 창은 최대화로 본다 (맥은 '최대화' 표시가 없다)
DOCK_SPAN = 3          # 맥 Dock 은 화면 가운데에 아이콘 폭만큼만 있다 - 가운데에서 Dock 두께의 이 배수 안만 쓴다
TRIES = 12             # 한 무리(종류 · 변)에서 자리를 몇 번 뽑아 보나

OPPOSITE = {"top": "bottom", "bottom": "top", "left": "right", "right": "left"}


# ---------------------------------------------------------------- 셈
def place(side, line, along, w, h, p):
    """빼꼼 자리 -> (x, y, crop). line 은 가리는 경계(창 가장자리 · 작업표시줄 안쪽 변 · 화면 끝), along 은 경계를 따라 간
    자리(위/아래로 내밀면 x, 옆이면 y), p 는 보이는 픽셀. crop 은 도트 안에서 보이는 칸 (l, t, r, b), x · y 는 도트 왼쪽 위.

    bottom 은 뒤집은 그림이 기준이다 - 아랫줄(뒤집혀서 머리)이 보인다."""
    p = max(0, min(int(p), h if side in ("top", "bottom") else w))
    if side == "top":
        return along, line - p, (0, 0, w, p)
    if side == "bottom":
        return along, line - (h - p), (0, h - p, w, h)
    if side == "left":
        return line - p, along, (0, 0, p, h)
    return line - (w - p), along, (w - p, 0, w, h)


def shown_rect(side, line, along, w, h, p):
    """그 빼꼼에서 화면에 보이는 칸 (x1, y1, x2, y2)."""
    x, y, c = place(side, line, along, w, h, p)
    return (x + c[0], y + c[1], x + c[2], y + c[3])


def body_len(side, w, h):
    """내미는 쪽 몸 길이 (위/아래로 내밀면 키, 옆으로 내밀면 폭)."""
    return h if side in ("top", "bottom") else w


def peek_px(length, rng):
    """보이는 픽셀 - 몸의 40~55%, 적어도 SHOW_PX. 단 **몸의 55% 를 넘지 않는다** - 좁은 종(훔처우 22px 등)은 SHOW_PX 가
    몸 전체라 하나도 안 숨었다 (실제 앱 시험 11/27). 작은 몸은 55% 까지만 보이고 SHOW_PX 를 양보한다."""
    p = int(round(rng.uniform(SHOW_MIN, SHOW_MAX) * length))
    cap = max(1, int(length * SHOW_MAX))
    return max(1, min(cap, max(min(SHOW_PX, cap), p)))


def more_px(length, p):
    """한 번 더 내밀 때의 픽셀 (PEEK_MORE). 늘 p 보다 크다 (몸보다 길지는 않게)."""
    return max(int(p) + 1, min(int(length), int(round(PEEK_MORE * length))))


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def inside(a, b):
    return b[0] <= a[0] and b[1] <= a[1] and a[2] <= b[2] and a[3] <= b[3]


def grow(r, d):
    return (r[0] - d, r[1] - d, r[2] + d, r[3] + d)


def monitor_for(area, screens):
    """활동 영역이 있는 모니터 번호 (arena_layout.work_for 와 같게 영역의 오른쪽 아래 모서리가 든 화면). 없으면 None."""
    x, y = area[2] - 1, area[3] - 1
    for i, s in enumerate(screens or []):
        if s and s[0] <= x < s[2] and s[1] <= y < s[3]:
            return i
    return None


def is_max(rect, work):
    """작업 영역을 거의 다 덮은 창 (윈도우 IsZoomed 가 아니어도 - 맥 · 손으로 늘린 창)."""
    ww, wh = max(1, work[2] - work[0]), max(1, work[3] - work[1])
    cx1, cy1 = max(rect[0], work[0]), max(rect[1], work[1])
    cx2, cy2 = min(rect[2], work[2]), min(rect[3], work[3])
    return (cx2 - cx1) >= MAX_FILL * ww and (cy2 - cy1) >= MAX_FILL * wh


def insets(scr, work):
    """화면 네 변에서 작업 영역이 얼마나 들어가 있나 {변: 픽셀}."""
    return {"left": work[0] - scr[0], "top": work[1] - scr[1],
            "right": scr[2] - work[2], "bottom": scr[3] - work[3]}


def touches(scr, other, side):
    """other 화면이 scr 의 그 변에 붙어 있나 (조금이라도 맞닿으면)."""
    if other is None or tuple(other) == tuple(scr):
        return False
    if side == "left":
        return abs(other[2] - scr[0]) <= 2 and other[1] < scr[3] and scr[1] < other[3]
    if side == "right":
        return abs(other[0] - scr[2]) <= 2 and other[1] < scr[3] and scr[1] < other[3]
    if side == "top":
        return abs(other[3] - scr[1]) <= 2 and other[0] < scr[2] and scr[0] < other[2]
    return abs(other[1] - scr[3]) <= 2 and other[0] < scr[2] and scr[0] < other[2]


def corners(work):
    """작업 영역 네 모서리의 CORNER 칸 (그 안은 안 쓴다)."""
    x1, y1, x2, y2 = work
    c = CORNER
    return [(x1, y1, x1 + c, y1 + c), (x2 - c, y1, x2, y1 + c), (x1, y2 - c, x1 + c, y2), (x2 - c, y2 - c, x2, y2)]


def _span(lo, hi, length):
    """[lo, hi] 안에 길이 length 를 놓을 수 있는 시작 범위. 못 놓으면 None."""
    lo, hi = int(lo), int(hi) - int(length)
    return (lo, hi) if hi >= lo else None


def _ok_common(spot, area, work, w, h):
    """모든 자리가 지키는 것: 활동 영역과 떨어짐 · 모서리 · 작업 영역 안 (가장 많이 내밀 때까지)."""
    side, line, along = spot["side"], spot["line"], spot["along"]
    x, y = spot["x"], spot["y"]
    if overlaps((x, y, x + w, y + h), grow(area, AREA_GAP + 1)):   # '120px 넘게' - 딱 120 은 안 된다
        return False
    big = shown_rect(side, line, along, w, h, more_px(body_len(side, w, h), spot["peek"]))
    if not inside(big, work):
        return False
    return not any(overlaps(big, c) for c in corners(work))


def _make(kind, side, line, along, w, h, p, scr_i, edge, anchor=None, arect=None):
    x, y, crop = place(side, line, along, w, h, p)
    return {"kind": kind, "side": side, "line": int(line), "along": int(along), "peek": int(p),
            "x": int(x), "y": int(y), "crop": crop, "anchor": anchor, "arect": tuple(arect) if arect else None,
            "screen": scr_i, "edge": edge}


# ---------------------------------------------------------------- 무리 (종류 · 변)
def _edge_group(i, scr, work, screens, windows, side_of_screen, os_name, w, h, area, rng):
    """화면 가장자리 (모든 보통 창 뒤) - 그 변에 작업표시줄 · 다른 모니터가 없을 때. 어느 창도 안 덮은 곳만."""
    ins = insets(scr, work)[side_of_screen]
    if ins != 0:
        return None                     # 작업표시줄(막대 자리) 이거나 자동 숨김 작업표시줄이 걸쳐 있다
    if any(touches(scr, o, side_of_screen) for o in screens or []):
        return None
    side = OPPOSITE[side_of_screen]
    line = {"left": scr[0], "right": scr[2], "top": scr[1], "bottom": scr[3]}[side_of_screen]
    L = body_len(side, w, h)
    if side in ("top", "bottom"):
        sp = _span(work[0] + CORNER, work[2] - CORNER, w)
    else:
        sp = _span(work[1] + CORNER, work[3] - CORNER, h)
    if sp is None:
        return None
    for _ in range(TRIES):
        p = peek_px(L, rng)
        spot = _make("edge", side, line, rng.randint(*sp), w, h, p, i, side_of_screen)
        if not _ok_common(spot, area, work, w, h):
            continue
        r = shown_rect(side, line, spot["along"], w, h, p)
        if any(overlaps(r, tuple(win["rect"])) for win in windows or []):
            # 창이 덮었다 - 바탕화면 바로 위라 안 보인다. 이 앱의 창(own) · '항상 위' 창(top)도 본다 - 둘 다 늘 이
            # 자리보다 앞이다 (검토 #4 · #6: 빼고 보면 그 밑 가장자리를 '보인다' 고 골라 4분 내내 가려진 채 놓친다)
            continue
        return spot
    return None


def _bar_group(i, scr, work, side_of_screen, os_name, w, h, area, rng):
    """작업표시줄/Dock 바로 아래 층 - 작업 영역 쪽으로 빼꼼. 맥 Dock 은 화면 가운데 아이콘 폭 안만."""
    ins = insets(scr, work)[side_of_screen]
    if ins < BAR_MIN:
        return None                     # 그 변에 작업표시줄이 없거나 자동 숨김
    side = OPPOSITE[side_of_screen]
    line = {"left": work[0], "right": work[2], "top": work[1], "bottom": work[3]}[side_of_screen]
    L = body_len(side, w, h)
    flat = side in ("top", "bottom")
    lo, hi = (work[0], work[2]) if flat else (work[1], work[3])
    lo, hi = lo + CORNER, hi - CORNER
    if os_name == "mac":
        mid = (scr[0] + scr[2]) / 2.0 if flat else (scr[1] + scr[3]) / 2.0
        lo, hi = max(lo, int(mid - DOCK_SPAN * ins)), min(hi, int(mid + DOCK_SPAN * ins))
    sp = _span(lo, hi, w if flat else h)
    if sp is None:
        return None
    for _ in range(TRIES):
        p = peek_px(L, rng)
        spot = _make("bar", side, line, rng.randint(*sp), w, h, p, i, side_of_screen)
        if _ok_common(spot, area, work, w, h):
            return spot
    return None


def nested(windows, k):
    """창 k 가 **같은 앱(pid)의 더 뒤 창** 안에 통째로 들어 있나 - 맥의 자식 창 · 시트 (저장 대화상자, 카카오톡 큰 창 안의
    작은 창). 맥은 자식 창 바로 뒤에 넣으라 해도 창 서버가 부모와 붙여 두어 부모 뒤로 간다 - 보일 줄 안 띠가 부모에
    통째로 가려진 채 4분을 보낸다 (검토 #5). pid 를 안 주는 OS(윈도우 - 주인 창 뒤에 끼울 수 있다)는 늘 False."""
    win = windows[k]
    pid = win.get("pid")
    if pid is None:
        return False
    r = tuple(win.get("rect") or (0, 0, 0, 0))
    return any(o.get("pid") == pid and inside(r, tuple(o.get("rect") or (0, 0, 0, 0))) for o in windows[k + 1:])


def anchor_for(scr, work, windows):
    """창 뒤 자리를 걸 창 - 이 모니터에서 가장 앞의 보통 창 (index, 창). 없으면 (None, None).

    최대화 · 작은 창 · '항상 위' 창 · DPI 가 다른 창(윈도우 'odd' - 좌표가 어긋난다) · 이 앱의 창(own) · 같은 앱 창 안의
    자식 창/시트(nested)는 걸지 않는다. own · top 은 목록에 **가리는 창으로만** 들어 있다 (검토 #4 · #6). 맨 앞 창이
    최대화면 그 뒤 창들은 어차피 가려져 있다 - 아래 '앞 창이 덮었나' 검사가 걸러 낸다."""
    for k, win in enumerate(windows or []):
        r = tuple(win.get("rect") or (0, 0, 0, 0))
        cx, cy = (r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0
        if not (scr[0] <= cx < scr[2] and scr[1] <= cy < scr[3]):
            continue
        if r[2] - r[0] < WIN_MIN_W or r[3] - r[1] < WIN_MIN_H:
            continue
        if win.get("max") or is_max(r, work) or win.get("odd") or win.get("top") or win.get("own"):
            continue
        if nested(windows, k):
            continue
        return k, win
    return None, None


def _window_spot(i, work, windows, k, win, side, along, p, w, h, area, front=True):
    """창 k 의 그 변에 그 자리로 빼꼼 - 규칙에 맞으면 자리, 아니면 None. front 면 그 창보다 앞의 창이 덮은 자리도 뺀다
    (고를 때 - 보이는 자리만. 따라갈 때는 안 본다: 다른 창이 앞에 오면 겹침 순서대로 가려진 채 그 자리에 있는다)."""
    r = tuple(win["rect"])
    line = {"top": r[1], "left": r[0], "right": r[2]}[side]
    spot = _make("window", side, line, along, w, h, p, i, side, anchor=win.get("id"), arect=r)
    if not _ok_common(spot, area, work, w, h):
        return None
    shown = shown_rect(side, line, along, w, h, p)
    if front and any(overlaps(shown, tuple(o["rect"])) for o in (windows or [])[:k]):
        # 그 창보다 앞의 창이 덮었다. 앞의 창에는 이 앱의 창(own) · '항상 위' 창(top)도 든다 - 목록이 겹침 순서대로라
        # 그 창보다 앞에 있으면 [:k] 안에 있다 (검토 #4 · #6)
        return None
    return spot


def _window_group(i, scr, work, windows, w, h, area, rng):
    k, win = anchor_for(scr, work, windows)
    if win is None:
        return None
    r = tuple(win["rect"])
    for _ in range(TRIES):
        side = rng.choice(("top", "top", "left", "right"))      # 위로 빼꼼이 가장 그럴듯하다
        if side == "top":
            sp = _span(r[0] + WIN_INSET, r[2] - WIN_INSET, w)
        else:
            sp = _span(r[1] + WIN_INSET, r[3] - WIN_INSET, h)
        if sp is None:
            continue
        spot = _window_spot(i, work, windows, k, win, side, rng.randint(*sp),
                            peek_px(body_len(side, w, h), rng), w, h, area)
        if spot is not None:
            return spot
    return None


def groups(os_name, kinds=KINDS):
    """무리와 무게 [(무게, 종류, 화면 변)]. 윈도우는 작업표시줄 · 오른쪽 변을, 맥은 Dock · 왼쪽 변을 먼저 (무게가 크다)."""
    if os_name == "mac":
        edges = (("left", 3), ("bottom", 1), ("right", 1))      # 위쪽(메뉴 막대)은 안 쓴다
    else:
        edges = (("right", 3), ("bottom", 1), ("top", 1), ("left", 1))
    out = []
    if "window" in kinds:
        out.append((3, "window", None))
    if "bar" in kinds:
        for s in ("bottom", "left", "right", "top"):
            if os_name == "mac" and s == "top":
                continue
            out.append((3, "bar", s))
    if "edge" in kinds:
        for s, wt in edges:
            out.append((wt, "edge", s))
    return out


def _order(items, rng):
    """무게대로 섞는다 (무거운 것이 앞에 오기 쉽다 - 늘 같은 자리만 나오지 않게)."""
    items, out = list(items), []
    while items:
        tot = sum(it[0] for it in items)
        x = rng.uniform(0, tot)
        for k, it in enumerate(items):
            x -= it[0]
            if x <= 0 or k == len(items) - 1:
                out.append(items.pop(k))
                break
    return out


def pick(area, screens, works, windows, sprite_wh, os_name, rng, kinds=KINDS):
    """숨을 자리 하나. 없으면 None.

    area 활동 영역 · screens/works 모니터와 작업 영역(같은 차례) · windows 창 [{"rect", "id", "max", "top", "odd",
    "own", "pid"?}] 겹침 순서 앞에서부터 (own · top 은 가리는 창으로만 - 걸지 않는다, pid 는 맥만) · sprite_wh 도트(테 포함)
    크기 · os_name 'win' | 'mac' | 그 밖 · kinds 이 OS 에서 쓸 수 있는 종류.
    돌려주는 것: {"kind", "side", "line", "along", "peek", "x", "y", "crop", "anchor", "arect", "screen", "edge"}."""
    i = monitor_for(area, screens)
    if i is None or i >= len(works or []):
        return None
    scr, work = tuple(screens[i]), tuple(works[i])
    w, h = int(sprite_wh[0]), int(sprite_wh[1])
    if w <= 0 or h <= 0:
        return None
    for _wt, kind, s in _order(groups(os_name, kinds), rng):
        if kind == "window":
            spot = _window_group(i, scr, work, windows, w, h, area, rng)
        elif kind == "bar":
            spot = _bar_group(i, scr, work, s, os_name, w, h, area, rng)
        else:
            spot = _edge_group(i, scr, work, screens, windows, s, os_name, w, h, area, rng)
        if spot is not None:
            return spot
    return None


def still_ok(spot, area, screens, works, sprite_wh):
    """작업표시줄 · 가장자리 자리가 아직 맞나 - 영역이 다른 모니터로 감 · 작업표시줄을 옮기거나 숨김 · 영역을 다시 그려
    가까워짐 · 해상도가 바뀜이면 False (부르는 쪽이 다른 자리를 고른다). 창 뒤 자리는 follow 가 본다."""
    if not spot:
        return False
    i = monitor_for(area, screens)
    if i is None or i != spot.get("screen") or i >= len(works or []):
        return False
    scr, work = tuple(screens[i]), tuple(works[i])
    w, h = int(sprite_wh[0]), int(sprite_wh[1])
    edge = spot.get("edge")
    if spot["kind"] == "bar":
        if insets(scr, work)[edge] < BAR_MIN:
            return False
        line = {"left": work[0], "right": work[2], "top": work[1], "bottom": work[3]}[edge]
    elif spot["kind"] == "edge":
        if insets(scr, work)[edge] != 0:
            return False
        line = {"left": scr[0], "right": scr[2], "top": scr[1], "bottom": scr[3]}[edge]
    else:
        return True
    return line == spot["line"] and _ok_common(spot, area, work, w, h)


def follow(spot, windows, area, screens, works, sprite_wh):
    """창 뒤 자리: 그 창이 지금 어디 있나 보고 같은 자리(창 기준)로 옮긴 자리를 돌려준다.

    창이 없어짐(닫힘 · 내림 · 다른 Space) · 최대화 · 작아짐 · 다른 모니터로 감 · 규칙(영역 · 모서리 · 작업 영역)에 안 맞음이면
    None (부르는 쪽이 다른 자리를 고른다). **다른 창이 앞에 와서 덮은 것은 그대로 둔다** - 사용자가 창을 바꿀 때마다 숨은
    포켓몬이 자리를 옮기면 쫓아다니는 것처럼 보인다 (겹침 순서가 알아서 가린다). 창이 그대로면 같은 값이 나온다."""
    if not spot or spot.get("kind") != "window":
        return spot
    k = next((n for n, win in enumerate(windows or []) if win.get("id") == spot.get("anchor")), None)
    if k is None:
        return None
    win = windows[k]
    r = tuple(win["rect"])
    i = monitor_for(area, screens)
    if i is None or i >= len(works or []):
        return None
    scr, work = tuple(screens[i]), tuple(works[i])
    cx, cy = (r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0
    if not (scr[0] <= cx < scr[2] and scr[1] <= cy < scr[3]):
        return None
    if (r[2] - r[0] < WIN_MIN_W or r[3] - r[1] < WIN_MIN_H or win.get("max") or is_max(r, work)
            or win.get("odd") or win.get("top") or win.get("own")):
        return None
    w, h = int(sprite_wh[0]), int(sprite_wh[1])
    old = spot.get("arect") or r
    side = spot["side"]
    if side == "top":
        along = r[0] + (spot["along"] - old[0])
        sp = _span(r[0] + WIN_INSET, r[2] - WIN_INSET, w)
    else:
        along = r[1] + (spot["along"] - old[1])
        sp = _span(r[1] + WIN_INSET, r[3] - WIN_INSET, h)
    if sp is None:
        return None
    along = max(sp[0], min(sp[1], along))               # 창이 줄었으면 끝에 맞춘다
    return _window_spot(i, work, windows, k, win, side, along, spot["peek"], w, h, area, front=False)
