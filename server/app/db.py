# -*- coding: utf-8 -*-
"""저장소. 스키마 생성과 조회/갱신 헬퍼.

두 가지를 쓸 수 있다.

    SQLite 파일   그냥 로컬 파일. 개발할 때와 도커로 직접 띄울 때.
    Turso(libSQL) POKET_TURSO_URL 이 있으면 그쪽으로 붙는다.

Render 같은 곳은 재시작하면 디스크가 날아가서 SQLite 파일을 못 쓴다.
그래서 Turso 를 쓸 수 있게 해뒀다.

libSQL 은 SQLite 와 SQL 은 같지만 **행을 튜플로 돌려준다.** 우리 코드는
r["species"] 처럼 컬럼 이름으로 꺼내는 곳이 백 군데가 넘어서, 여기서
dict 로 감싸 준다. 그래야 나머지 코드를 한 줄도 안 고쳐도 된다.
(rowcount 는 libSQL 에서도 제대로 나온다 — 돈·가방을 깎을 때 이걸로
성공 여부를 판단하므로 미리 확인해 뒀다.)
"""
import json
import os
import sqlite3
import threading

from . import config

_local = threading.local()


class Row(dict):
    """sqlite3.Row 처럼 쓸 수 있는 dict.

    r["col"] 과 "col" in r.keys() 둘 다 되어야 한다.
    (row_to_mon 이 옛 DB 행에 새 컬럼이 있는지 keys() 로 확인한다)
    """

    __slots__ = ()


def _wrap_one(cur, row):
    if row is None or cur.description is None:
        return row
    return Row(zip([d[0] for d in cur.description], row))


def _wrap_all(cur, rows):
    if not rows or cur.description is None:
        return rows or []
    cols = [d[0] for d in cur.description]
    return [Row(zip(cols, r)) for r in rows]

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT NOT NULL UNIQUE COLLATE NOCASE,
    pw_hash     BLOB NOT NULL,
    pw_salt     BLOB NOT NULL,
    pw_iter     INTEGER NOT NULL,
    balls       INTEGER NOT NULL DEFAULT 10,
    money       INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    last_login  TEXT,
    last_ip     TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ip          TEXT NOT NULL,
    ip_real     INTEGER NOT NULL DEFAULT 0,
    device      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS pokemon (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    species        TEXT NOT NULL,
    nickname       TEXT,
    level          INTEGER NOT NULL,
    exp            INTEGER NOT NULL,
    nature         TEXT NOT NULL,
    ability        TEXT,
    hidden_ability INTEGER NOT NULL DEFAULT 0,
    gender         TEXT NOT NULL DEFAULT 'N',
    shiny          INTEGER NOT NULL DEFAULT 0,
    happiness      INTEGER NOT NULL DEFAULT 70,
    ivs            TEXT NOT NULL,
    evs            TEXT NOT NULL,
    moves          TEXT NOT NULL,
    on_desktop     INTEGER NOT NULL DEFAULT 0,
    slot           INTEGER,
    met_level      INTEGER NOT NULL,
    caught_at      TEXT NOT NULL,
    -- 하이퍼트레이닝. 개체값 자체는 그대로 두고 "이 능력은 31로 쳐준다" 는
    -- 표시만 남긴다. 본가도 실제 개체값은 안 바꾼다.
    hyper          TEXT NOT NULL DEFAULT '{}',
    -- 변함없는돌을 쥐여준 것과 같은 상태. 레벨업 진화를 멈춘다.
    no_evolve      INTEGER NOT NULL DEFAULT 0,
    -- 럭셔리볼로 잡았나. 친밀도가 두 배로 오른다(본가와 같다).
    -- 럭셔리볼은 그동안 happinessRate 를 돌려주기만 하고 읽는 쪽이
    -- 없어서 아무 일도 안 하고 있었다.
    luxury         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_pokemon_user ON pokemon(user_id);

-- 아직 내 것이 아닌, 바탕화면에 나타난 야생 개체
CREATE TABLE IF NOT EXISTS wild (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    state       TEXT NOT NULL,          -- grass(풀숲) / revealed(모습을 드러냄)
    species     TEXT NOT NULL,
    data        TEXT NOT NULL,
    throws      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wild_user ON wild(user_id);

-- 진행 중인 야생 배틀. 판정은 전부 서버가 한다.
CREATE TABLE IF NOT EXISTS battle (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    wild_id     INTEGER NOT NULL,
    mine_id     INTEGER NOT NULL,
    state       TEXT NOT NULL,          -- active / done
    result      TEXT,                   -- won / lost / fled / caught
    turn        INTEGER NOT NULL DEFAULT 0,
    me          TEXT NOT NULL,          -- json (hp, pp, status, stages)
    foe         TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_battle_user ON battle(user_id);

CREATE TABLE IF NOT EXISTS wild_state (
    user_id     INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    next_at     TEXT,
    encounters  INTEGER NOT NULL DEFAULT 0,
    caught      INTEGER NOT NULL DEFAULT 0,
    fled        INTEGER NOT NULL DEFAULT 0,
    battles     INTEGER NOT NULL DEFAULT 0,
    wins        INTEGER NOT NULL DEFAULT 0,
    -- 친밀도를 어디까지 쳐줬는지. 이 시각부터 지금까지 흐른 만큼만 준다.
    -- **앞으로만 간다.** 그래서 폴링을 아무리 자주 해도 벽시계보다 빨리
    -- 오를 수 없다 - 걸은 시간을 클라이언트가 말하게 두면 얼마든지
    -- 부풀릴 수 있는데, 서버가 아는 시각으로만 계산하면 그 여지가 없다.
    walk_at     TEXT
);

-- 로그인 실패 기록.
-- 예전에는 프로세스 메모리에 뒀는데, 무료 호스팅은 하루에도 몇 번씩
-- 재시작해서 그때마다 카운터가 지워졌다. 비밀번호가 숫자 4자리(만 가지)라
-- 시도 제한이 사실상 유일한 방어선인데 그게 계속 풀리면 안 된다.
CREATE TABLE IF NOT EXISTS login_fail (
    key    TEXT NOT NULL,
    at     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_login_fail ON login_fail(key, at);

CREATE TABLE IF NOT EXISTS bag (
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item     TEXT NOT NULL,
    count    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, item)
);

-- 리피트볼이 "이미 잡아본 종" 을 봐야 해서 남긴다. 도감 역할도 겸한다.
CREATE TABLE IF NOT EXISTS seen (
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    species  TEXT NOT NULL,
    caught   INTEGER NOT NULL DEFAULT 0,
    first_at TEXT NOT NULL,
    PRIMARY KEY (user_id, species)
);

-- 친구. 관계는 **대칭**이라 행을 하나만 두고 항상 작은 id 를 a_id 에 넣는다.
-- 양쪽에 한 행씩 두면 수락/삭제 때 두 문장을 맞춰 써야 하는데, db.run 은
-- 한 문장씩 커밋이라 중간에 끊기면 한쪽만 남는다. Turso 는 가끔 끊기는 게
-- 전제인 환경이라(3회 재시도가 그래서 있다) 그 반쪽 상태를 풀 방법이 없다.
--   asked_by  누가 신청했나. pending 의 방향이 이걸로 정해진다.
--   rejected  거절도 남긴다. 바로 다시 신청하는 걸 막아야 해서다.
CREATE TABLE IF NOT EXISTS friend (
    a_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    b_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    state       TEXT NOT NULL,
    asked_by    INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    decided_at  TEXT,
    PRIMARY KEY (a_id, b_id)
);
-- a_id 는 기본키가 곧 인덱스다. b_id 로 들어오는 쪽은 따로 걸어 줘야
-- '나에게 온 신청' 을 찾을 때 표를 통째로 훑지 않는다.
CREATE INDEX IF NOT EXISTS idx_friend_b ON friend(b_id);

-- 차단은 **비대칭**이다(내가 저 사람을 차단). friend.state 에 섞으면
-- 서로 차단한 경우를 표현할 수 없고, 풀었을 때 원래 친구였는지도 잃는다.
CREATE TABLE IF NOT EXISTS friend_block (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (user_id, target_id)
);
-- '나를 차단한 사람' 도 봐야 한다. 신청과 도전을 막을 때 양쪽을 다 본다.
CREATE INDEX IF NOT EXISTS idx_block_target ON friend_block(target_id);

-- 유저끼리 붙은 한 판. **여기 들어오는 순간 승패가 이미 끝나 있다.**
-- 진행이 AI 자동이라 팀과 시드만 있으면 결과가 정해지므로, 서버가 매칭
-- 순간 끝까지 계산해서 로그를 넣어 둔다. 양쪽 클라이언트는 그 같은
-- 로그를 재생하기만 한다.
--   log   gzip + base64 한 이벤트 목록. 서버는 풀지 않고 그대로 흘린다.
--   seed  같은 판을 나중에 다시 돌려볼 수 있게 남긴다.
-- 보고 나면 값이 없어지는 자료라 오래된 것은 치운다. 영구 기록은
-- battle_record 쪽이다.
CREATE TABLE IF NOT EXISTS pvp_match (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,
    a_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    b_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    a_name      TEXT NOT NULL,
    b_name      TEXT NOT NULL,
    winner      INTEGER,
    turns       INTEGER NOT NULL DEFAULT 0,
    seed        INTEGER NOT NULL,
    engine      TEXT NOT NULL DEFAULT '',
    log         TEXT NOT NULL,
    a_reward    INTEGER NOT NULL DEFAULT 0,
    b_reward    INTEGER NOT NULL DEFAULT 0,
    a_seen      INTEGER NOT NULL DEFAULT 0,
    b_seen      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pvp_match_a ON pvp_match(a_id, id);
CREATE INDEX IF NOT EXISTS idx_pvp_match_b ON pvp_match(b_id, id);

-- 전적. 한 경기에 **사람마다 한 행**을 남긴다. 한 행만 두고
-- (a=? OR b=?) 로 찾으면 목록을 뽑을 때마다 승패를 뒤집어 계산해야 하고
-- 인덱스도 두 개가 필요하다.
--
-- 상대에는 외래키를 걸지 않는다. 걸면 상대가 탈퇴할 때 **내 전적까지**
-- 함께 지워진다. 그래서 그때의 닉네임을 베껴 둔다.
CREATE TABLE IF NOT EXISTS battle_record (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    foe_id      INTEGER,
    foe_name    TEXT NOT NULL,
    kind        TEXT NOT NULL,
    result      TEXT NOT NULL,
    rating      INTEGER NOT NULL DEFAULT 0,
    delta       INTEGER NOT NULL DEFAULT 0,
    reward      INTEGER NOT NULL DEFAULT 0,
    turns       INTEGER NOT NULL DEFAULT 0,
    my_left     INTEGER NOT NULL DEFAULT 0,
    foe_left    INTEGER NOT NULL DEFAULT 0,
    lead        TEXT NOT NULL DEFAULT '',
    foe_lead    TEXT NOT NULL DEFAULT '',
    match_id    INTEGER,
    ended_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_record_user ON battle_record(user_id, id DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_record_once ON battle_record(match_id, user_id);

-- 랭킹판. 경기가 끝날 때 갱신해 두고 랭킹 조회는 이 표만 읽는다.
-- battle_record 를 GROUP BY 로 집계하면 경기가 쌓일수록 느려진다.
CREATE TABLE IF NOT EXISTS rank_stat (
    user_id     INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    rating      INTEGER NOT NULL DEFAULT 1000,
    games       INTEGER NOT NULL DEFAULT 0,
    wins        INTEGER NOT NULL DEFAULT 0,
    losses      INTEGER NOT NULL DEFAULT 0,
    draws       INTEGER NOT NULL DEFAULT 0,
    fr_wins     INTEGER NOT NULL DEFAULT 0,
    fr_losses   INTEGER NOT NULL DEFAULT 0,
    fr_draws    INTEGER NOT NULL DEFAULT 0,
    streak      INTEGER NOT NULL DEFAULT 0,
    best        INTEGER NOT NULL DEFAULT 1000,
    ranked      INTEGER NOT NULL DEFAULT 0,
    earned_day  TEXT NOT NULL DEFAULT '',
    earned      INTEGER NOT NULL DEFAULT 0,
    -- 하루에 건 도전 횟수. 상대는 자고 있을 수도 있어서, 몇 번이고 걸 수
    -- 있으면 아침에 점수가 바닥나 있게 된다.
    fought_day  TEXT NOT NULL DEFAULT '',
    fought      INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rank_board ON rank_stat(ranked, rating DESC);

-- 서버가 스스로 기억해야 하는 잡다한 것. 지금은 '어떤 자료 손질까지
-- 끝냈는가' 를 적는 데 쓴다.
CREATE TABLE IF NOT EXISTS meta (
    k  TEXT PRIMARY KEY,
    v  TEXT NOT NULL
);
"""

MIGRATIONS = [
    ("wild_state", "battles",
     "ALTER TABLE wild_state ADD COLUMN battles INTEGER NOT NULL DEFAULT 0"),
    ("wild_state", "wins",
     "ALTER TABLE wild_state ADD COLUMN wins INTEGER NOT NULL DEFAULT 0"),
    ("sessions", "ip_real",
     "ALTER TABLE sessions ADD COLUMN ip_real INTEGER NOT NULL DEFAULT 0"),
    ("users", "balls",
     "ALTER TABLE users ADD COLUMN balls INTEGER NOT NULL DEFAULT 10"),
    ("users", "money",
     "ALTER TABLE users ADD COLUMN money INTEGER NOT NULL DEFAULT 0"),
    ("pokemon", "hyper",
     "ALTER TABLE pokemon ADD COLUMN hyper TEXT NOT NULL DEFAULT '{}'"),
    ("pokemon", "no_evolve",
     "ALTER TABLE pokemon ADD COLUMN no_evolve INTEGER NOT NULL DEFAULT 0"),
    ("rank_stat", "fought_day",
     "ALTER TABLE rank_stat ADD COLUMN fought_day TEXT NOT NULL DEFAULT ''"),
    ("rank_stat", "fought",
     "ALTER TABLE rank_stat ADD COLUMN fought INTEGER NOT NULL DEFAULT 0"),
    ("wild_state", "walk_at",
     "ALTER TABLE wild_state ADD COLUMN walk_at TEXT"),
    ("pokemon", "luxury",
     "ALTER TABLE pokemon ADD COLUMN luxury INTEGER NOT NULL DEFAULT 0"),
]


def using_turso():
    return bool(config.TURSO_URL)


def _open():
    """새 커넥션 하나. 스레드마다 따로 만든다."""
    if using_turso():
        import libsql
        if config.TURSO_REPLICA:
            # 붙박이 복제본: 읽기는 로컬 파일에서 하고 쓰기만 Turso 로 간다.
            # 배틀은 한 턴에도 여러 번 읽으므로 이쪽이 훨씬 빠르다.
            d = os.path.dirname(os.path.abspath(config.TURSO_REPLICA))
            if d:
                os.makedirs(d, exist_ok=True)
            return libsql.connect(config.TURSO_REPLICA,
                                  sync_url=config.TURSO_URL,
                                  auth_token=config.TURSO_TOKEN)
        # libsql:// 주소가 아니라 로컬 파일 경로를 준 경우(시험용)에는
        # 폴더가 없으면 열리지 않으므로 먼저 만들어 준다.
        if "://" not in config.TURSO_URL:
            d = os.path.dirname(os.path.abspath(config.TURSO_URL))
            if d:
                os.makedirs(d, exist_ok=True)
        return libsql.connect(config.TURSO_URL, auth_token=config.TURSO_TOKEN)

    d = os.path.dirname(os.path.abspath(config.DB_PATH))
    if d:
        os.makedirs(d, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def connect():
    """스레드마다 커넥션 하나."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _open()
        try:
            conn.execute("PRAGMA foreign_keys=ON")
        except Exception:            # noqa: BLE001 — Turso 는 이미 켜져 있다
            pass
        _local.conn = conn
    return conn


def _schema_for(conn):
    """이 백엔드에 맞는 스키마 문장들.

    원격 Turso 는 스크립트 안에 PRAGMA 가 하나라도 있으면 **스크립트 전체를
    조용히 건너뛴다.** 오류도 안 난다. 그래서 테이블이 하나도 안 생긴 채로
    서버가 뜨고, 첫 요청에서 "no such table" 로 죽는다.
    Turso 는 어차피 WAL 과 외래키를 알아서 하므로 PRAGMA 를 빼고 보낸다.
    """
    if not using_turso():
        return SCHEMA
    keep = []
    for stmt in SCHEMA.split(";"):
        t = stmt.strip()
        if t and not t.upper().startswith("PRAGMA"):
            keep.append(t)
    return ";\n".join(keep) + ";"


def init():
    conn = connect()
    conn.executescript(_schema_for(conn))
    for table, col, sql in MIGRATIONS:
        cur = conn.execute("PRAGMA table_info(%s)" % table)
        rows = cur.fetchall()
        # PRAGMA 결과도 백엔드에 따라 모양이 다르다. 이름은 두 번째 칸이다.
        have = set(r["name"] if isinstance(r, (dict, sqlite3.Row)) else r[1]
                   for r in rows)
        if have and col not in have:
            conn.execute(sql)
    conn.commit()


# 네트워크 너머의 DB(Turso)는 가끔 그냥 끊긴다. 그때마다 500 이 나가면
# 사용자는 "가끔 오류가 뜬다" 로만 겪는다. 몇 번 다시 해보고, 그래도 안 되면
# 그때 올린다. 재시도해도 되는 건 '읽기' 와 '한 문장짜리 쓰기' 뿐이라
# 여기서만 한다.
RETRY = 3
RETRY_WAIT = 0.25


def _transient(e):
    """다시 해보면 될 만한 오류인가."""
    t = "%s %s" % (type(e).__name__, e)
    t = t.lower()
    for word in ("hrana", "stream", "connection", "timeout", "timed out",
                 "temporarily", "reset", "broken pipe", "eof", "network",
                 "unavailable", "502", "503", "504"):
        if word in t:
            return True
    return False


def _retry(fn):
    """일시적인 실패면 잠깐 쉬었다 다시."""
    import time
    last = None
    for i in range(RETRY):
        try:
            return fn()
        except Exception as e:                              # noqa: BLE001
            if not using_turso() or not _transient(e):
                raise
            last = e
            # 끊긴 커넥션을 붙들고 있어봐야 소용없다. 버리고 새로 연다.
            try:
                conn = getattr(_local, "conn", None)
                if conn is not None:
                    conn.close()
            except Exception:                               # noqa: BLE001
                pass
            _local.conn = None
            if i < RETRY - 1:
                time.sleep(RETRY_WAIT * (i + 1))
    raise last


def q(sql, args=()):
    def go():
        cur = connect().execute(sql, args)
        rows = cur.fetchall()
        return _wrap_all(cur, rows) if using_turso() else rows
    return _retry(go)


def q1(sql, args=()):
    def go():
        cur = connect().execute(sql, args)
        row = cur.fetchone()
        return _wrap_one(cur, row) if using_turso() else row
    return _retry(go)


def run(sql, args=()):
    """한 문장 실행 + 커밋.

    한 문장짜리라 다시 해도 안전하다(모두 조건이 붙은 UPDATE 이거나
    INSERT ... ON CONFLICT 다). 그래서 일시적 실패면 다시 해본다.
    """
    def go():
        conn = connect()
        cur = conn.execute(sql, args)
        conn.commit()
        return cur
    return _retry(go)


# ---------------------------------------------------------------- 변환
def row_to_mon(r):
    """DB 행 -> pokelogic 이 쓰는 dict."""
    return {
        "id": r["id"],
        "species": r["species"],
        "nickname": r["nickname"],
        "level": r["level"],
        "exp": r["exp"],
        "nature": r["nature"],
        "ability": r["ability"],
        "hiddenAbility": bool(r["hidden_ability"]),
        "gender": r["gender"],
        "shiny": bool(r["shiny"]),
        "happiness": r["happiness"],
        "ivs": json.loads(r["ivs"]),
        "evs": json.loads(r["evs"]),
        "moves": json.loads(r["moves"]),
        "onDesktop": bool(r["on_desktop"]),
        "slot": r["slot"],
        "metLevel": r["met_level"],
        "caughtAt": r["caught_at"],
        # 옛 DB 행에는 없을 수 있어 keys() 로 확인하고 꺼낸다
        "hyper": json.loads(r["hyper"]) if "hyper" in r.keys() and r["hyper"] else {},
        "noEvolve": bool(r["no_evolve"]) if "no_evolve" in r.keys() else False,
        "luxury": bool(r["luxury"]) if "luxury" in r.keys() else False,
    }


def insert_mon(user_id, mon, now):
    cur = run(
        "INSERT INTO pokemon (user_id, species, nickname, level, exp, nature, ability,"
        " hidden_ability, gender, shiny, happiness, ivs, evs, moves, on_desktop, slot,"
        " met_level, caught_at, hyper, no_evolve, luxury)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (user_id, mon["species"], mon.get("nickname"), mon["level"], mon["exp"],
         mon["nature"], mon.get("ability"), int(bool(mon.get("hiddenAbility"))),
         mon.get("gender", "N"), int(bool(mon.get("shiny"))), mon.get("happiness", 70),
         json.dumps(mon["ivs"]), json.dumps(mon["evs"]), json.dumps(mon["moves"]),
         0, None, mon["level"], now,
         json.dumps(mon.get("hyper") or {}), int(bool(mon.get("noEvolve"))),
         int(bool(mon.get("luxury")))))
    return cur.lastrowid
