# -*- coding: utf-8 -*-
"""꾸미기 (버전 2, 시즌 5 길드전 순위 보상) - 바탕화면 포켓몬이 쓰는 장식과 걸어간 자리에 남는 효과.

서버(server/app/deco.py)와 앱(client/poketdesktop/deco_*.py)이 같은 목록을 본다. 그림은 앱만 갖고 있다.

  · 장식 (head · hair · neck): 걷는 도트의 머리 · 목 자리에 얹는다 (위치 점 - common 은 모르고 앱이 안다)
  · 효과 (trail · aura): 걸어간 자리에 남는 발자국 · 별가루 · 꽃잎 · 하트, 발밑 빛

**장식 하나는 포켓몬 한 마리만 쓴다** (다른 포켓몬에 끼우면 먼저 쓰던 포켓몬에서 빠진다). 한 포켓몬은 칸(slot)마다
하나씩 - 왕관(head) + 꽃핀(hair) + 진주(neck) + 별가루(trail) + 발밑 빛(aura) 을 다 같이 쓸 수 있다.

돈으로 바꿀 수 없다 (상점 · 판매 없음). 얻는 길은 선물함(kind 'deco') 뿐이다 - 길드전 순위 보상이 넣는다
(+ 버전 2 가 뜰 때 모두에게 한 번 발자국 - server/app/migrations.py 0340).
"""

SLOTS = ("head", "hair", "neck", "trail", "aura")
SLOT_KR = {"head": "머리", "hair": "머리 장식", "neck": "목", "trail": "발자취", "aura": "발밑"}

DECOS = {
    "crown_gold": {"kr": "금관", "slot": "head", "desc": "루비 구슬이 달린 금관. 가끔 반짝인다."},
    "crown_silver": {"kr": "은관", "slot": "head", "desc": "루비 구슬이 달린 은관. 가끔 반짝인다."},
    "crown_bronze": {"kr": "동관", "slot": "head", "desc": "루비 구슬이 달린 동관. 가끔 반짝인다."},
    "bow": {"kr": "분홍 리본", "slot": "hair", "desc": "머리 오른쪽 위에 작게 다는 리본."},
    "flower": {"kr": "꽃핀", "slot": "hair", "desc": "꽃잎 다섯 장 분홍 꽃과 작은 잎."},
    "pearls": {"kr": "진주 목걸이", "slot": "neck", "desc": "진주 줄에 하트 펜던트."},
    "fx_stars_gold": {"kr": "금빛 별가루", "slot": "trail", "desc": "걸을 때 몸 뒤로 금빛 별가루가 흩날린다."},
    "fx_stars_silver": {"kr": "은빛 별가루", "slot": "trail", "desc": "걸을 때 몸 뒤로 은빛 별가루가 흩날린다."},
    "fx_stars_bronze": {"kr": "동빛 별가루", "slot": "trail", "desc": "걸을 때 몸 뒤로 동빛 별가루가 흩날린다."},
    "fx_paw": {"kr": "발자국", "slot": "trail", "desc": "걸어간 자리에 발자국이 찍혔다 사라진다."},
    "fx_petals": {"kr": "꽃잎", "slot": "trail", "desc": "걸을 때 분홍 꽃잎이 살랑살랑 떨어진다."},
    "fx_hearts": {"kr": "하트", "slot": "trail", "desc": "걸을 때 머리 위로 하트가 퐁퐁 떠오른다."},
    "fx_glow": {"kr": "발밑 빛", "slot": "aura", "desc": "발밑에 금빛 고리가 은은하게 빛난다."},
}

# 길드전 순위 보상 묶음. 참가 묶음은 셋 중 하나를 꾸미기 창에서 고른다 (선택권 PICK).
BUNDLES = {
    "rank1": ("crown_gold", "fx_stars_gold", "fx_glow"),
    "rank2": ("crown_silver", "fx_stars_silver"),
    "rank3": ("crown_bronze", "fx_stars_bronze"),
    "join_bow": ("bow", "fx_paw"),
    "join_flower": ("flower", "fx_petals"),
    "join_pearls": ("pearls", "fx_hearts"),
}
BUNDLE_KR = {
    "rank1": "1위 묶음 (금관 · 금빛 별가루 · 발밑 빛)",
    "rank2": "2위 묶음 (은관 · 은빛 별가루)",
    "rank3": "3위 묶음 (동관 · 동빛 별가루)",
    "join_bow": "리본 + 발자국",
    "join_flower": "꽃핀 + 꽃잎",
    "join_pearls": "진주 목걸이 + 하트",
}
JOIN_CHOICES = ("join_bow", "join_flower", "join_pearls")
PICK = "pick_join"                     # 가진 것 목록에서 '참가 묶음 선택권' 을 뜻하는 열쇠
PICK_KR = "참가 묶음 선택권"
EFFECTS = ("trail", "aura")


def slot_of(key):
    d = DECOS.get(key)
    return d["slot"] if d else None


def name(key):
    if key == PICK:
        return PICK_KR
    if key in BUNDLES:
        return BUNDLE_KR[key]
    return (DECOS.get(key) or {}).get("kr", key)


def clean(raw):
    """포켓몬이 쓰고 있는 것 {칸: 열쇠} 을 믿을 수 있는 꼴로 (모르는 열쇠 · 칸이 안 맞는 것은 버린다)."""
    out = {}
    if not isinstance(raw, dict):
        return out
    for slot, key in raw.items():
        if slot in SLOTS and isinstance(key, str) and slot_of(key) == slot:
            out[slot] = key
    return out


def parts(raw):
    """(장식 열쇠들, 효과 열쇠들). 앱이 그릴 때 쓴다 - 장식은 도트에 얹고 효과는 따로 창에 그린다."""
    d = clean(raw)
    acc = tuple(d[s] for s in ("head", "hair", "neck") if s in d)
    fx = tuple(d[s] for s in EFFECTS if s in d)
    return acc, fx
