# -*- coding: utf-8 -*-
"""숨바꼭질 (시즌 7) — 규칙 숫자 (서버가 읽고, 앱도 읽을 수 있다).

  · 풀숲 차례 가운데 가끔(서버 config.HIDE_CHANCE) 야생이 창 뒤 · 작업표시줄 뒤 · 바탕화면 가장자리에 숨는다.
    앱이 '지금 보여 줄 수 있다'(GET /api/wild?hide=1) 고 할 때만 숨긴다 - 서버 main._make_grass.
  · 숨은 포켓몬의 HIDE_SHARE 몫은 숨는 종(HIDERS) 표에서만 뽑는다 (pokelogic.Pokedex.roll_hide). 나머지는 평소 표.
  · 숨겨진 특성 1/HIDE_HIDDEN_RATE (평소 야생 1/128). 숨겨진 특성이 없는 종은 평소대로, 이로치는 평소와 같다.

설계: design-notes/2026-11-27-hide-and-seek.md
"""

# 숨는 종 (설계 목록, 내부 이름) - 고스트 · 악 위주로 '숨기 좋아하는' 종 30종. frozenset 이라 표 캐시 열쇠가 된다
# (Pokedex.hide_pool). 레벨이 높으면 풀숲처럼 진화한 모습으로 나온다 (grown_form - 망망이 Lv30 -> 묘두기 처럼
# 목록 밖 진화형이 될 수도 있다. 목록은 '뽑는 표' 이고, 나온 모습은 풀숲과 같은 규칙을 따른다).
HIDERS = frozenset((
    "GASTLY", "HAUNTER", "GENGAR",                # 고오스 · 고우스트 · 팬텀
    "MISDREAVUS", "MISMAGIUS",                    # 무우마 · 무우마직
    "SABLEYE",                                    # 깜까미
    "SHUPPET", "BANETTE",                         # 어둠대신 · 다크펫
    "DUSKULL", "DUSCLOPS", "DUSKNOIR",            # 해골몽 · 미라몽 · 야느와르몽
    "DRIFLOON", "DRIFBLIM",                       # 흔들풍손 · 둥실라이드
    "SPIRITOMB",                                  # 화강돌
    "ZORUA", "ZOROARK",                           # 조로아 · 조로아크
    "KECLEON",                                    # 켈리몬
    "MIMIKYU",                                    # 따라큐
    "MURKROW", "HONCHKROW",                       # 니로우 · 돈크로우
    "PHANTUMP", "TREVENANT",                      # 나목령 · 대로트
    "PUMPKABOO", "GOURGEIST",                     # 호바귀 · 펌킨인
    "SINISTEA", "POLTEAGEIST",                    # 데인차 · 포트데스
    "GREAVARD",                                   # 망망이
    "SANDYGAST",                                  # 모래꿍
    "DITTO",                                      # 메타몽
    "SMEARGLE",                                   # 루브도
))

# 숨은 포켓몬 가운데 숨는 종 표에서 뽑는 몫. 나머지 절반은 평소 풀숲 표 (할로윈 · 타입 스프레이는 안 얹는다) -
# 숨는 종만 나오면 30종을 다 본 뒤로는 '또 고스트' 가 된다.
HIDE_SHARE = 0.5

# 숨겨진 특성 1/4 (사용자 11/27: 이로치 대신 숨특). 지금 숨겨진 특성을 얻는 길은 야생 1/128 하나뿐이라 숨은 포켓몬을
# 찾는 값어치가 된다. pokelogic.make_pokemon(hidden_rate=) 로 넘긴다.
HIDE_HIDDEN_RATE = 4
