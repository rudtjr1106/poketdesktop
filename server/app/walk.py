# -*- coding: utf-8 -*-
"""친밀도 — 바탕화면을 걸어다닌 만큼 오른다.

본가의 '걷기' 에 해당한다. 데리고 다니는 포켓몬이 옆에 있는 시간이
쌓이면 친해진다.

**여기의 어려움은 서버 권위다.** 걸은 시간은 클라이언트만 안다.
"10시간 걸었어요" 를 그대로 믿으면 친밀도를 마음대로 올릴 수 있다.

그래서 걸음을 세지 않고 **서버가 아는 시각**으로만 계산한다. 어디까지
쳐줬는지를 walk_at 에 적어 두고, 요청이 올 때마다 그 시각부터 지금까지
흐른 만큼만 준다. walk_at 은 앞으로만 가므로 폴링을 아무리 자주 해도
벽시계보다 빨리 오를 수 없다. 클라이언트가 보낼 수 있는 숫자가 아예 없다.

앱을 꺼 두면 안 오른다. 요청이 끊기면 walk_at 이 그 자리에 멈추기
때문인데, 약속이 '걸은 시간' 이므로 그게 맞다. 자는 동안 자란 것으로
치면 켜 두는 의미가 없어진다.
"""
import datetime

from . import config, db

# 20분마다 1점. 시간당 3점이다.
#
# 하루 8시간 켜 두면 보통 종(70)이 임계값 160에 닿는 데 나흘쯤 걸린다.
# 하루 만에 끝나면 시시하고, 몇 주가 걸리면 아무도 안 기다린다.
# 야생은 5~7분(짧은 리듬), 레벨업 진화는 배틀 몇 판(중간 리듬)이니
# 친밀도는 며칠 자리에 있어야 셋이 서로 안 먹는다.
TICK = 1200
GAIN = 1

# 한 번에 몰아줄 수 있는 최대 칸수.
# 이게 없으면 오래 꺼 뒀다가 켰을 때 walk_at 이 옛날에 멈춰 있어서
# 하루치가 한꺼번에 들어온다. '걸은 시간' 이라는 약속과 어긋난다.
MAX_TICKS = 2

# 본가 상한
MAX_HAPPINESS = 255

# 배틀에서 쓰러지면 깎인다. 본가와 같은 방향이되 훨씬 약하게.
FAINT_LOSS = 3


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _parse(s):
    try:
        return datetime.datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def settle(uid, st=None):
    """지금까지 걸은 만큼 친밀도를 올린다. 오른 점수를 돌려준다.

    이미 wild_state 를 읽고 있는 곳에서 부른다(/api/me). 그 행을 넘겨
    주면 조회가 한 번도 안 는다. 대부분의 요청은 쓰기도 0이고, 20분에
    한 번만 두 문장이 나간다.
    """
    now = _now()
    if st is None:
        st = db.q1("SELECT * FROM wild_state WHERE user_id=?", (uid,))
    last = _parse(st["walk_at"]) if st else None
    if last is None:
        # 처음이면 지금부터 센다. 가입 시각부터 몰아주지 않는다.
        db.run("INSERT INTO wild_state (user_id, walk_at) VALUES (?,?)"
               " ON CONFLICT(user_id) DO UPDATE SET walk_at=?",
               (uid, now.isoformat(), now.isoformat()))
        return 0

    ticks = int((now - last).total_seconds() // TICK)
    if ticks <= 0:
        return 0
    ticks = min(ticks, MAX_TICKS)
    # 쓴 만큼만 앞으로 옮긴다. 남는 시간은 다음에 쓰이므로 버려지지 않는다.
    nxt = last + datetime.timedelta(seconds=ticks * TICK)
    if nxt > now:
        nxt = now
    db.run("UPDATE wild_state SET walk_at=? WHERE user_id=?",
           (nxt.isoformat(), uid))

    got = ticks * GAIN
    # 데리고 다니는 애들만 오른다. 박스에 있는 건 같이 걷지 않는다.
    # 럭셔리볼로 잡은 개체는 두 배로 오른다(본가와 같다).
    db.run(
        "UPDATE pokemon SET happiness = MIN(?, happiness + ? * "
        " CASE WHEN luxury=1 THEN 2 ELSE 1 END)"
        " WHERE user_id=? AND on_desktop=1 AND happiness < ?",
        (MAX_HAPPINESS, got, uid, MAX_HAPPINESS))
    return got


def on_faint(uid, mon_id):
    """배틀에서 쓰러진 그 한 마리만 조금 깎인다."""
    db.run("UPDATE pokemon SET happiness = MAX(0, happiness - ?)"
           " WHERE id=? AND user_id=?", (FAINT_LOSS, mon_id, uid))


def hours_to(happiness, want, luxury=False):
    """저 점수까지 몇 시간 더 켜 둬야 하는지. 화면에 보여주려고."""
    need = max(0, int(want) - int(happiness))
    if need <= 0:
        return 0.0
    per_hour = (3600.0 / TICK) * GAIN * (2 if luxury else 1)
    return need / per_hour
