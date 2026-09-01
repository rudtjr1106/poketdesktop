<div align="center">

<img src="docs/images/icon.png" width="96" alt="포켓 데스크톱">

# 포켓 데스크톱

**바탕화면에서 포켓몬을 만나고 키웁니다.**

일하는 화면 한켠에서 포켓몬들이 걸어다닙니다.
가끔 풀숲이 돋아나고, 야생 포켓몬이 나타나고, 잡아서 키웁니다.

[**최신 버전 받기**](https://github.com/rudtjr1106/poketdesktop/releases/latest) · [쓰인 자료](CREDITS.md)

</div>

---

<div align="center">
<img src="docs/images/desktop.png" width="600" alt="바탕화면을 돌아다니는 포켓몬들">
</div>

## 진짜로 걸어다닙니다

미끄러지듯 움직이는 게 아니라 **발이 바뀝니다.**
가는 방향에 따라 몸을 돌리고, 위로 올라가면 등이 보입니다.
나는 포켓몬은 나는 모습으로 움직입니다.
걸음은 실제로 나아가는 속도에 맞춰 돌아갑니다 — 천천히 가면 발도 천천히 움직입니다.

<sub>1025종 중 982종(야생에 나오는 종 기준 96.8%)에 걷는 도트가 있습니다.
없는 종은 기존 도트로 나오고, 이 경우 걷는 모습 대신 제자리 애니메이션입니다.</sub>

<div align="center">
<img src="docs/images/walk-directions.png" width="620" alt="네 방향 걷기">
</div>

## 어떻게 노나요

**5~7분에 한 번 풀숲이 돋아납니다.** 클릭하면 야생 포켓몬이 나옵니다.

- **왼쪽 클릭** — 배틀을 겁니다. 내 포켓몬이 다가가서 알아서 싸웁니다
- **오른쪽 클릭** — 바로 몬스터볼을 던집니다

배틀은 별도 화면 없이 **바탕화면 그 자리에서** 벌어집니다.
체력을 깎아두면 훨씬 잘 잡힙니다.

<div align="center">
<img src="docs/images/box.png" width="600" alt="포켓몬 관리">
</div>

파티는 여섯 마리, 넘치면 PC 박스로 갑니다.
개체값·성격·특성·기술 전부 본가와 같은 규칙입니다.

## 본가 그대로

| | |
|---|---|
| **1~9세대 1025마리** | 타입·종족값·기술·특성 전부 정식 도감 자료 |
| **개체값 · 성격 · 특성** | 3세대 이후 능력치 공식 그대로 |
| **경험치** | 5세대 공식. 학습장치로 파티 전원이 나눠 받습니다 |
| **노력치** | 스탯당 252, 총합 510 |
| **진화** | 레벨 · 돌 · 친밀도. 이브이 여덟 갈래도 조건대로 |
| **포획** | 5세대 이후 공식. 볼 종류마다 상황을 봅니다 |
| **이로치** | 4096분의 1 |

전설의 포켓몬은 야생에 나오지 않습니다. 나중에 이벤트로 넣을 예정입니다.

## 도구와 상점

야생을 잡거나 쓰러뜨리면 **도구가 떨어집니다.** 106종이 있습니다.

<div align="center">
<img src="docs/images/shop.png" width="600" alt="프렌들리샵">
</div>

흔한 건 자주, 귀한 건 가끔 나옵니다.
안 쓰는 건 상점에 팔아 돈을 만들고, 그 돈으로 필요한 걸 삽니다.
**돈은 도구를 팔아서만 법니다.**

<div align="center">
<img src="docs/images/bag.png" width="600" alt="가방">
</div>

- **진화의 돌** — 이브이를 여덟 갈래 중 어디로 보낼지 고릅니다
- **영양제 · 깃털 · 열매** — 노력치를 올리고 내립니다
- **은색/금색 병뚜껑** — 레벨 50부터 개체값을 최고로 단련합니다
- **이상한사탕 · 변함없는돌** — 레벨을 올리고, 진화를 멈춥니다

## 시작하기

1. [릴리스](https://github.com/rudtjr1106/poketdesktop/releases/latest)에서 `poketdesktop-vX.Y.Z.exe` 를 받습니다
2. 실행하고 **닉네임 + 숫자 4자리**로 가입합니다
3. 1~9세대 스타팅 27마리 중 하나를 고릅니다

<div align="center">
<img src="docs/images/login.png" width="330" alt="로그인">
</div>

서버 주소를 입력할 필요 없습니다. 설치도 필요 없습니다.
트레이 아이콘에서 포켓몬 관리 · 가방 · 상점을 열 수 있습니다.

> **보안 경고가 뜬다면**
>
> **"Windows에서 PC를 보호했습니다"** — SmartScreen 입니다.
> **추가 정보 → 실행** 을 누르면 되고, 그 다음부터는 안 뜹니다.
>
> **백신이 파일을 지우거나 실행을 막는다면** — 오탐입니다.
> 릴리스의 **`.zip` (폴더형)** 을 받아 보세요. 단일 exe 는 실행할 때 자기를
> 임시 폴더에 풀고 돌리는데, 그 동작이 악성코드와 비슷해 보여서 오탐이 잦습니다.
> 폴더형은 이미 풀린 상태라 훨씬 덜 걸립니다.
>
> 둘 다 코드 서명 인증서(연 수십만원)가 없어서 생기는 일이고, 프로그램 문제가 아닙니다.
> 자세한 대처는 [백신 오탐 안내](docs/defender-false-positive.md)를 보세요.
>
> **파일을 카카오톡이나 메일로 받으면 더 엄격하게 검사받습니다.**
> 위 릴리스 주소에서 직접 받는 편이 훨씬 덜 걸립니다.

## 만들어 보기

```bash
docker compose up -d                       # 서버 (SQLite)
python client/run.py                       # 클라이언트
```

```bash
python tools/build_pokedex.py --out server/data/pokedex.json   # 도감 다시 만들기
python tools/build_items.py                                    # 도구 목록
python tools/build_exe.py                                      # exe 빌드
```

서버는 [Render](https://render.com) + [Turso](https://turso.tech) 에서 돌아갑니다.
설정은 [`render.yaml`](render.yaml) 에 있습니다.

## 앞으로

- 유저끼리 배틀
- 체육관
- 경매장
- 전설의 포켓몬 이벤트

---

<div align="center">

포켓몬은 닌텐도 / Game Freak / 포켓몬 컴퍼니의 저작물입니다.
이 프로젝트는 팬이 만든 **비상업** 프로젝트입니다.

걷는 도트는 [PMDCollab/SpriteCollab](https://github.com/PMDCollab/SpriteCollab)
([CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)) 을 씁니다.
자세한 출처는 [CREDITS.md](CREDITS.md) 에 있습니다.

</div>
