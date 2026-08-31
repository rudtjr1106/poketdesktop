# -*- coding: utf-8 -*-
"""SQLite 저장소. 스키마 생성과 조회/갱신 헬퍼."""
import json
import os
import sqlite3
import threading

from . import config

_local = threading.local()

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
    caught_at      TEXT NOT NULL
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
    wins        INTEGER NOT NULL DEFAULT 0
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
]


def connect():
    """스레드마다 커넥션 하나."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        d = os.path.dirname(os.path.abspath(config.DB_PATH))
        if d:
            os.makedirs(d, exist_ok=True)
        conn = sqlite3.connect(config.DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


def init():
    conn = connect()
    conn.executescript(SCHEMA)
    for table, col, sql in MIGRATIONS:
        have = set(r["name"] for r in conn.execute("PRAGMA table_info(%s)" % table))
        if have and col not in have:
            conn.execute(sql)
    conn.commit()


def q(sql, args=()):
    return connect().execute(sql, args).fetchall()


def q1(sql, args=()):
    return connect().execute(sql, args).fetchone()


def run(sql, args=()):
    conn = connect()
    cur = conn.execute(sql, args)
    conn.commit()
    return cur


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
    }


def insert_mon(user_id, mon, now):
    cur = run(
        "INSERT INTO pokemon (user_id, species, nickname, level, exp, nature, ability,"
        " hidden_ability, gender, shiny, happiness, ivs, evs, moves, on_desktop, slot,"
        " met_level, caught_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (user_id, mon["species"], mon.get("nickname"), mon["level"], mon["exp"],
         mon["nature"], mon.get("ability"), int(bool(mon.get("hiddenAbility"))),
         mon.get("gender", "N"), int(bool(mon.get("shiny"))), mon.get("happiness", 70),
         json.dumps(mon["ivs"]), json.dumps(mon["evs"]), json.dumps(mon["moves"]),
         0, None, mon["level"], now))
    return cur.lastrowid
