# 쓰인 자료

## 포켓몬 도감 자료 (타입 · 종족값 · 기술 · 한국어 이름 · 진화)
[PokeAPI](https://pokeapi.co/) 의 공개 CSV.
`tools/build_pokedex.py` 가 이걸로 `server/data/pokedex.json` 을 만든다.

## 배틀 도트 · 도구 그림
[PokeAPI/sprites](https://github.com/PokeAPI/sprites) 와
[msikma/pokesprite](https://github.com/msikma/pokesprite).

## 걷는 도트 (바탕화면을 돌아다니는 4방향 애니메이션)
[PMDCollab / SpriteCollab](https://github.com/PMDCollab/SpriteCollab) —
포켓몬 불가사의 던전 풍으로 팬들이 그린 스프라이트다.
**라이선스: [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)**
(출처를 밝히고, **상업적으로 쓰지 않는 조건**)

> 이게 이 프로젝트에서 유일하게 조건이 붙은 자료다.
> 광고를 붙이거나 돈을 받는 순간 이 조건을 어기게 된다.
> 그렇게 할 생각이면 걷는 도트를 걷어내고 배틀 도트만 쓰거나,
> 직접 그린 도트로 갈아야 한다.
> (애초에 포켓몬 자체가 닌텐도 저작물이라 수익화는 별개로 어렵다.)

SpriteCollab 에 없는 14종은
[baptiste-ro/pokemon-followers-sprites](https://github.com/baptiste-ro/pokemon-followers-sprites)
로 메웠다 (HGSS 풍 4방향 도트).

어느 쪽에도 없는 43종(야생에 나오는 건 29종)은 배틀 도트로 대신한다.
그 종들은 정면 고정이라 걷는 모습이 없다.

## 관장 도전

### 대한민국 지도 (시·도 / 시·군·구 경계)
통계청 SGIS 행정경계(공공누리 제1유형)를 행정동 단위로 정리한
[vuski/admdongkor](https://github.com/vuski/admdongkor) ver20260701.
**라이선스: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)** (출처를 밝히는 조건)
`tools/build_korea_map.py` 가 행정동을 시·군·구로 묶고 점을 줄여
`server/data/korea_map.json` 을 만든다. 관장 탭의 지도 아래에도 출처를 띄운다.

### 트레이너와 데리고 다니는 포켓몬
[Bulbapedia](https://bulbapedia.bulbagarden.net/) 의 트레이너 문서
(원작 게임에서 쓰는 팀과 레벨)를 참고했다.
**Bulbapedia 본문 라이선스: [CC BY-NC-SA 2.5](https://creativecommons.org/licenses/by-nc-sa/2.5/)**
`tools/build_gyms.py` 가 문서의 팀 표를 읽어 256명을 뽑고 레벨대에 나눠
`server/data/gyms.json` 을 만든다. 배치(어느 지역에 누가 있는지)와 이유는 직접 정했다.

### 트레이너 도트
[Pokémon Showdown](https://play.pokemonshowdown.com/sprites/trainers/) 의
트레이너 스프라이트. `server/data/trainer_sprites/` 에 있다.
의정부시의 이스터에그 트레이너와 지우의 도트는 개발자가 따로 준비한 그림이다.

## 포켓몬
포켓몬과 관련된 이름·그림의 저작권은 닌텐도 / Game Freak / 포켓몬 컴퍼니에 있다.
이 프로젝트는 팬이 만든 비상업 프로젝트다.
