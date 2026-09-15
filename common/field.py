# -*- coding: utf-8 -*-
"""날씨·필드·방·진영 — 포켓몬 한 마리가 아니라 **판 전체**에 걸리는 것.

    weather     sun / rain / sand / hail / snow            (5턴)
    terrain     electric / grassy / misty / psychic        (5턴)
    rooms       trickroom / magicroom / wonderroom / gravity (5턴)
                mudsport / watersport (5턴), fairylock (다음 턴까지)
    sides       진영마다 ("me" / "foe")
                  reflect·lightscreen·auroraveil·safeguard·mist (5턴), tailwind (4턴)
                  spikes (1~3겹), toxicspikes (1~2겹), stealthrock, stickyweb
                  wish {"turns", "amount"}, healingwish / lunardance (다음에 나오는 포켓몬)
                  quickguard·wideguard·craftyshield (그 턴만)

야생·관장 배틀은 요청마다 저장본에서 되살리므로 dump/load 가 있다. 유저 배틀은
한 판을 통째로 계산하므로 라운드끼리 같은 Field 를 나눠 쓴다.

여기는 **상태만** 담는다. 효과는 battle.py 와 statusmoves.py 가 본다.
"""

WEATHER_START = {"sun": "햇살이 강해졌다!", "rain": "비가 내리기 시작했다!",
                 "sand": "모래바람이 불기 시작했다!", "hail": "싸라기눈이 내리기 시작했다!",
                 "snow": "눈이 내리기 시작했다!"}
WEATHER_GOING = {"sun": "햇살이 강하다.", "rain": "비가 계속 내리고 있다.",
                 "sand": "모래바람이 세차게 분다.", "hail": "싸라기눈이 계속 내리고 있다.",
                 "snow": "눈이 계속 내리고 있다."}
WEATHER_END = {"sun": "햇살이 원래대로 돌아왔다!", "rain": "비가 그쳤다!",
               "sand": "모래바람이 가라앉았다!", "hail": "싸라기눈이 그쳤다!", "snow": "눈이 그쳤다!"}
TERRAIN_START = {"electric": "발밑에 전기가 흐르기 시작했다!", "grassy": "발밑에 풀이 무성해졌다!",
                 "misty": "발밑에 안개가 자욱해졌다!", "psychic": "발밑이 기묘한 느낌이 되었다!"}
TERRAIN_END = {"electric": "발밑의 전기가 사라졌다!", "grassy": "발밑의 풀이 사라졌다!",
               "misty": "발밑의 안개가 사라졌다!", "psychic": "발밑의 기묘한 느낌이 사라졌다!"}
ROOM_START = {"trickroom": "시공을 뒤틀었다!", "magicroom": "서로의 도구를 쓸 수 없는 공간이 되었다!",
              "wonderroom": "방어와 특수방어가 뒤바뀌는 공간이 되었다!", "gravity": "중력이 강해졌다!",
              "mudsport": "전기의 위력이 약해졌다!", "watersport": "불꽃의 위력이 약해졌다!",
              "fairylock": "다음 턴에는 아무도 도망칠 수 없게 되었다!"}
ROOM_END = {"trickroom": "뒤틀린 시공이 원래대로 돌아왔다!", "magicroom": "도구를 다시 쓸 수 있게 되었다!",
            "wonderroom": "방어와 특수방어가 원래대로 돌아왔다!", "gravity": "중력이 원래대로 돌아왔다!",
            "mudsport": "흙놀이의 효과가 사라졌다!", "watersport": "물놀이의 효과가 사라졌다!",
            "fairylock": None}
SIDE_KR = {"reflect": "리플렉터", "lightscreen": "빛의장막", "auroraveil": "오로라베일",
           "safeguard": "신비의부적", "mist": "흰안개", "tailwind": "순풍"}
HAZARDS = ("spikes", "toxicspikes", "stealthrock", "stickyweb")
HAZARD_KR = {"spikes": "압정", "toxicspikes": "독압정", "stealthrock": "뾰족한 바위",
             "stickyweb": "끈적끈적네트"}
TURN_ONLY = ("quickguard", "wideguard", "craftyshield")


class Field(object):

    def __init__(self):
        self.weather = None
        self.weather_turns = 0
        self.terrain = None
        self.terrain_turns = 0
        self.rooms = {}
        self.sides = {"me": {}, "foe": {}}
        self.suppressed = False       # 날씨부정·에어록이 서 있다 (저장하지 않는다 - 서 있는 포켓몬으로 매번 정한다)
        self.last_move = None         # 판에서 마지막으로 쓰인 기술 (흉내쟁이)

    # ---- 저장 ----
    def dump(self):
        if not (self.weather or self.terrain or self.rooms or self.sides["me"] or self.sides["foe"]
                or self.last_move):
            return None
        return {"weather": self.weather, "weatherTurns": self.weather_turns, "lastMove": self.last_move,
                "terrain": self.terrain, "terrainTurns": self.terrain_turns,
                "rooms": dict(self.rooms),
                "sides": {"me": dict(self.sides["me"]), "foe": dict(self.sides["foe"])}}

    @classmethod
    def load(cls, d):
        f = cls()
        if not d:
            return f
        f.weather = d.get("weather")
        f.weather_turns = int(d.get("weatherTurns") or 0)
        f.terrain = d.get("terrain")
        f.terrain_turns = int(d.get("terrainTurns") or 0)
        f.rooms = dict(d.get("rooms") or {})
        f.last_move = d.get("lastMove")
        sides = d.get("sides") or {}
        f.sides = {"me": dict(sides.get("me") or {}), "foe": dict(sides.get("foe") or {})}
        return f

    # ---- 읽기 ----
    def side(self, who):
        return self.sides[who]

    def room(self, name):
        return bool(self.rooms.get(name))

    def clear_turn_guards(self):
        for s in self.sides.values():
            for k in TURN_ONLY:
                s.pop(k, None)
