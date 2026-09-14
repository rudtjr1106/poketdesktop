# -*- coding: utf-8 -*-
"""관장 지도에 쓰는 대한민국 시·도 / 시·군·구 경계를 만든다.

    python tools/build_korea_map.py        # server/data/korea_map.json

**shapely 가 필요하다.** 게임도 서버도 이걸 안 쓰므로 requirements 에는
안 넣었다. 지도를 다시 뽑을 때만 따로 깔아서 돌린다.

    python -m venv /tmp/mapvenv && /tmp/mapvenv/bin/pip install shapely
    /tmp/mapvenv/bin/python tools/build_korea_map.py

## 출처

vuski/admdongkor 의 행정동 경계(ver20260701). 원자료는 통계청 SGIS 이고
**출처를 밝혀야 한다**(공공누리 제1유형 + CC BY 4.0). 파일의 `source` 에
적어 두었고, 화면에도 띄운다.

2026년 7월 개편이 들어 있다 - 인천 제물포구·영종구·서해구·검단구,
전남광주통합특별시. 흔히 쓰는 southkorea-maps 는 2018년에 멈춰 있어서
쓰면 안 된다.

## 무엇을 하나

1. 행정동 3,558개를 시군구 코드로 묶어 합친다 -> 256곳
   (수원시팔달구 같은 일반구를 따로 센다)
2. 좌표를 **미리 평면으로 편다.** x = 경도 x cos(36도), y = -위도.
   한국 크기에서는 이 정도로 모양이 안 틀어지고, 받는 쪽은 비율만
   맞춰 그리면 된다.
3. 점을 줄인다. 원본 34MB 를 그대로 보내면 창이 뜰 때마다 무겁다.
   가장 큰 조각의 0.2% 보다 작은 섬은 버린다 - 신안군은 섬이 191개다.
4. 배치에 쓸 특징을 붙인다: 바다에 닿는가, 섬이 몇 개인가, 구/시/군.
"""
import argparse
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tools", "_cache", "HangJeongDong_ver20260701.geojson")
URL = ("https://raw.githubusercontent.com/vuski/admdongkor/master/"
       "ver20260701/HangJeongDong_ver20260701.geojson")
SOURCE = ("통계청 SGIS 행정경계(공공누리 제1유형) · "
          "vuski/admdongkor ver20260701 (CC BY 4.0)")
K = math.cos(math.radians(36.0))


def main():
    try:
        from shapely.geometry import MultiPolygon, shape
        from shapely.ops import polylabel, transform, unary_union
    except ImportError:
        sys.stderr.write("shapely 가 없습니다. 파일 머리글의 방법으로 까세요.\n")
        return 1

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "server", "data", "korea_map.json"))
    a = ap.parse_args()

    if not os.path.exists(SRC):
        import subprocess
        os.makedirs(os.path.dirname(SRC), exist_ok=True)
        sys.stderr.write("  받는 중 %s\n" % URL)
        subprocess.run(["curl", "-sL", "-m", "600", "-o", SRC, URL], check=True)

    d = json.load(open(SRC, encoding="utf-8"))
    proj = lambda g: transform(lambda x, y, z=None: (x * K, -y), g)   # noqa: E731

    groups = {}
    order = []
    for f in d["features"]:
        p = f["properties"]
        key = p["sgg"]
        if key not in groups:
            groups[key] = {"sido": p["sido"], "sidonm": p["sidonm"],
                           "name": p["sggnm"], "geoms": []}
            order.append(key)
        groups[key]["geoms"].append(shape(f["geometry"]))

    def parts(g):
        return list(g.geoms) if isinstance(g, MultiPolygon) else [g]

    merged = {k: unary_union(groups[k]["geoms"]) for k in order}
    # **바다에 닿는지는 줄인 선으로 잰다.** 원본 해안선에 폭을 주고 256번
    # 겹쳐 보면 5분이 넘어도 안 끝났다. 50m 로 줄이면 몇 초면 된다 -
    # 우리가 알고 싶은 것은 '닿는가' 이지 해안선의 정확한 길이가 아니다.
    rough = {k: merged[k].simplify(0.0005, preserve_topology=True) for k in order}
    # 줄이면 이웃한 구끼리 선이 따로 움직여 **사이에 틈**이 생긴다. 그대로
    # 합치면 그 틈이 전부 '바깥선' 이 되어 256곳 중 245곳이 바다에 닿는
    # 것으로 나왔다. 조금 부풀려 합친 뒤 도로 줄여 틈을 메우고, 구멍(안쪽
    # 고리)은 버리고 바깥 고리만 쓴다.
    from shapely.geometry import LineString
    nation = unary_union([r.buffer(0.003) for r in rough.values()]).buffer(-0.003)
    # 나라 바깥선 = 바다(와 휴전선). 휴전선은 북쪽 끝이라 위도로 거른다.
    outline = unary_union([LineString(q.exterior.coords) for q in parts(nation)]).buffer(0.002)

    def rings(g, tol, min_frac):
        g = proj(g).simplify(tol, preserve_topology=True)
        ps = [x for x in parts(g) if not x.is_empty]
        if not ps:
            return []
        big = max(x.area for x in ps)
        return [[[round(x, 4), round(y, 4)] for x, y in q.exterior.coords]
                for q in ps if q.area >= big * min_frac]

    sgg = []
    by_sido = {}
    for k in order:
        g = merged[k]
        info = groups[k]
        shared = rough[k].boundary.intersection(outline)
        # 휴전선(위도 38도 이북의 바깥선)은 바다가 아니다.
        coast_len = 0.0
        for seg in (shared.geoms if hasattr(shared, "geoms") else [shared]):
            if seg.is_empty:
                continue
            if seg.centroid.y > 37.9 and seg.centroid.x < 128.4:
                continue
            coast_len += seg.length
        big_parts = [q for q in parts(g) if q.area > 0.00002]
        name = info["name"]
        kind = "구" if name.endswith("구") else ("군" if name.endswith("군") else "시")
        # 이름표 자리: 가장 큰 조각 안에서 **테두리에서 가장 먼 점**.
        # representative_point 는 안에만 있으면 돼서 울진군처럼 가늘고 긴
        # 곳은 테두리에 붙은 점을 준다. 거기 글자를 쓰면 이웃 칸을 덮는다.
        # label_r 은 그 점에서 테두리까지 거리 - 받는 쪽이 글자가 들어갈지 잰다.
        pg = proj(g)
        main_part = max(parts(pg), key=lambda q: q.area)
        c = polylabel(main_part, tolerance=0.002)
        label_r = main_part.exterior.distance(c)
        for hole in main_part.interiors:
            label_r = min(label_r, hole.distance(c))
        lat = g.centroid.y
        area_km2 = g.area * (111.32 ** 2) * math.cos(math.radians(lat))
        sgg.append({
            "code": k, "sido": info["sido"], "sidonm": info["sidonm"], "name": name,
            "kind": kind,
            "coast": coast_len > 0.03,
            "islands": max(0, len(big_parts) - 1),
            "area": round(area_km2, 1),
            "center": [round(c.x, 4), round(c.y, 4)],
            "labelR": round(label_r, 4),
            "rings": rings(g, 0.0015, 0.002),
        })
        by_sido.setdefault((info["sido"], info["sidonm"]), []).append(g)

    sido = []
    for (code, nm), gs in by_sido.items():
        u = unary_union(gs)
        # 이름표 자리. 고리는 바깥선만 보내므로 경기도 도형은 서울을 덮는다 -
        # 무게중심을 쓰면 경기 이름이 서울 위에 앉는다. 구멍(서울)을 뺀
        # 실제 모양에서 테두리와 가장 먼 점을 쓴다.
        pu = proj(u)
        part = max(parts(pu), key=lambda q: q.area)
        c = polylabel(part, tolerance=0.002)
        r = min([part.exterior.distance(c)] + [h.distance(c) for h in part.interiors])
        sido.append({"code": code, "name": nm, "center": [round(c.x, 4), round(c.y, 4)],
                     "labelR": round(r, 4), "area": round(pu.area, 5),
                     "rings": rings(u, 0.006, 0.004)})

    out = {"version": 1, "source": SOURCE, "projection": "x=lon*cos(36deg), y=-lat",
           "sido": sido, "sgg": sgg}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    print("  시도 %d · 시군구 %d · %.0fKB -> %s"
          % (len(sido), len(sgg), os.path.getsize(a.out) / 1024, a.out))
    coast = [s["name"] for s in sgg if s["coast"]]
    print("  바다에 닿는 곳 %d곳 · 섬이 많은 곳 %s"
          % (len(coast), sorted(((s["islands"], s["name"]) for s in sgg), reverse=True)[:4]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
