"""
menu_attributes.py  (확장판: 26 -> 44 차원)
------------------------------------------
NEIS 급식 메뉴를 파싱하고 해석 가능한 속성 축으로 태깅한다.

축
- form(7): 단일라벨 우선순위
- grain(4): rice일 때 곡물/형태 세분 (다중)
- method(10): 단일라벨
- protein(7): 다중
- cuisine(6): 단일라벨 (한식 기본)
- flag(10): 다중

키워드 리스트는 데이터를 보며 계속 확장하라.
"""
import re

_ALLERGEN_PAREN = re.compile(r"[\(\[][0-9.\s]*[\)\]]")
_ECO_MARK = re.compile(r"[*★]|친환경")
_TRAILING_NUM = re.compile(r"[\d.]+\s*$")
_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)


def parse_menu_string(ddish_nm: str) -> list[str]:
    if not ddish_nm or not isinstance(ddish_nm, str):
        return []
    dishes = []
    for part in _BR.split(ddish_nm):
        p = _ALLERGEN_PAREN.sub("", part)
        p = _ECO_MARK.sub("", p)
        p = _TRAILING_NUM.sub("", p)
        p = re.sub(r"\s+", " ", p).strip()
        if p:
            dishes.append(p)
    return dishes


# ── 단일 라벨 축 (우선순위) ───────────────────────────────────────────
FORM_RULES = [
    ("noodle",   ["국수", "우동", "라면", "짜장", "짬뽕", "파스타", "스파게티", "쫄면",
                   "칼국수", "냉면", "수제비", "비빔면", "쌀국수", "메밀", "라볶이", "면"]),
    ("rice",     ["비빔밥", "볶음밥", "덮밥", "김밥", "주먹밥", "리조", "필라프", "오므라이스",
                   "컵밥", "카레라이스", "하이라이스", "밥"]),
    ("porridge", ["죽"]),
    ("stew",     ["찌개", "전골"]),
    ("soup",     ["국", "탕", "스프", "수프"]),
    ("bread",    ["빵", "버거", "샌드위치", "토스트", "피자", "또띠아", "브리또", "베이글", "모닝롤"]),
]

METHOD_RULES = [
    ("fry",      ["튀김", "까스", "가스", "후라이", "프라이", "강정", "탕수", "깐풍", "유린"]),
    ("stirfry",  ["볶음", "볶이", "잡채", "라조기", "제육"]),
    ("grill",    ["구이", "스테이크", "데리야", "바베큐", "함박", "햄버그", "떡갈비"]),
    ("braise",   ["조림", "찜닭", "장조림", "갈비찜", "찜", "맛탕"]),
    ("pan",      ["전", "부침", "적", "산적", "빈대떡", "동그랑땡"]),
    ("seasoned", ["무침", "생채", "겉절이", "나물", "샐러드", "냉채", "숙주", "초무침"]),
    ("pickle",   ["장아찌", "절임", "피클"]),
    ("raw",      ["회무침", "육회", "물회", "회"]),
    ("boil",     ["삶", "데침", "수육", "백숙", "편육"]),
]

CUISINE_RULES = [
    ("bunsik",   ["떡볶이", "라볶이", "순대", "김밥", "쫄면", "만두", "어묵", "핫도그"]),
    ("chinese",  ["짜장", "짬뽕", "탕수", "마파", "유산슬", "깐풍", "라조", "양장피", "딤섬", "마라"]),
    ("japanese", ["우동", "까스", "규동", "초밥", "스시", "가라아게", "데리야", "라멘", "돈부리", "오야꼬"]),
    ("southeast",["쌀국수", "팟타이", "분짜", "나시고", "월남", "카레"]),
    ("western",  ["파스타", "스파게티", "스테이크", "그라탕", "리조", "피자", "함박", "햄버그",
                   "스프", "수프", "샌드위치", "버거", "필라프", "치즈"]),
]

# ── 다중 라벨 축 ──────────────────────────────────────────────────────
PROTEIN_RULES = {
    "pork":    ["돼지", "제육", "삼겹", "목살", "탕수육", "동그랑땡", "수육", "보쌈", "함박", "햄버그", "돈까스", "돈가스"],
    "beef":    ["소고기", "쇠고기", "우삼겹", "불고기", "장조림", "갈비", "육개장", "스테이크", "차돌"],
    "chicken": ["닭", "치킨", "계육", "닭갈비", "찜닭", "가라아게", "강정"],
    "duck":    ["오리"],
    "seafood": ["생선", "고등어", "갈치", "임연수", "동태", "코다리", "오징어", "쭈꾸미", "주꾸미",
                 "낙지", "새우", "어묵", "맛살", "멸치", "참치", "연어", "해물", "조개", "홍합", "골뱅이", "회"],
    "egg":     ["계란", "달걀", "메추리알", "오므", "스크램블"],
    "tofu":    ["두부", "유부", "순두부", "비지", "콩"],
}

FLAG_RULES = {
    "spicy":     ["매운", "매콤", "고추", "제육", "떡볶이", "닭갈비", "짬뽕", "마파", "마라",
                   "불닭", "청양", "고추장", "낙지", "쭈꾸미", "주꾸미", "김치찌개", "춘천", "양념", "아라비아따"],
    "sweet":     ["강정", "맛탕", "데리야", "불고기", "탕수", "유린", "케첩", "갈비", "허니"],
    "fermented": ["된장", "청국장", "쌈장", "젓갈", "장아찌", "묵은지"],
    "curry":     ["카레", "커리"],
    "processed": ["소세지", "소시지", "햄", "너겟", "너깃", "맛살", "어묵", "비엔나", "스팸", "동그랑땡"],
    "dessert":   ["요구르트", "요거트", "우유", "주스", "음료", "푸딩", "케이크", "과일",
                   "샤베트", "아이스", "젤리", "쿠키", "타르트", "단호박찐"],
    "kimchi":    ["김치", "깍두기", "겉절이", "단무지"],
    "ricecake":  ["떡볶이", "떡국", "가래떡", "떡갈비"],   # '떡' 단독은 디저트로 빠질 수 있어 복합어만
    "salad":     ["샐러드"],
    "namul":     ["나물", "숙주", "시금치", "고사리", "도라지", "취나물", "콩나물무침", "무생채"],
}

GRAIN_RULES = {   # form==rice 일 때만 평가
    "white":  ["흰쌀", "백미", "쌀밥"],
    "multi":  ["잡곡", "현미", "기장", "보리", "흑미", "오곡", "귀리", "수수", "찰"],
    "fried":  ["볶음밥"],
    "mixed":  ["비빔밥", "덮밥", "김밥", "주먹밥"],
}

FEATURE_COLUMNS = (
    [f"form_{x}" for x in ["rice", "noodle", "porridge", "stew", "soup", "bread", "side"]]
    + [f"grain_{x}" for x in ["white", "multi", "fried", "mixed"]]
    + [f"method_{x}" for x in ["fry", "stirfry", "grill", "braise", "pan", "seasoned", "pickle", "raw", "boil"]]
    + [f"protein_{x}" for x in ["pork", "beef", "chicken", "duck", "seafood", "egg", "tofu"]]
    + [f"cuisine_{x}" for x in ["korean", "bunsik", "chinese", "japanese", "southeast", "western"]]
    + [f"flag_{x}" for x in ["spicy", "sweet", "fermented", "curry", "processed", "dessert", "kimchi", "ricecake", "salad", "namul"]]
)


def _first_match(name, rules):
    for label, kws in rules:
        if any(kw in name for kw in kws):
            return label
    return None


def tag_dish(name: str) -> dict:
    form = _first_match(name, FORM_RULES) or "side"
    method = _first_match(name, METHOD_RULES)
    cuisine = _first_match(name, CUISINE_RULES) or "korean"
    proteins = [p for p, kws in PROTEIN_RULES.items() if any(k in name for k in kws)]
    flags = [f for f, kws in FLAG_RULES.items() if any(k in name for k in kws)]
    grains = []
    if form == "rice":
        grains = [g for g, kws in GRAIN_RULES.items() if any(k in name for k in kws)]
    return {"form": form, "method": method, "cuisine": cuisine,
            "proteins": proteins, "flags": flags, "grains": grains}


def meal_feature_vector(dishes: list[str], normalize: bool = True) -> dict:
    vec = {c: 0.0 for c in FEATURE_COLUMNS}
    if not dishes:
        return vec
    for d in dishes:
        t = tag_dish(d)
        vec[f"form_{t['form']}"] += 1
        if t["method"]:
            vec[f"method_{t['method']}"] += 1
        vec[f"cuisine_{t['cuisine']}"] += 1
        for p in t["proteins"]:
            vec[f"protein_{p}"] += 1
        for fl in t["flags"]:
            vec[f"flag_{fl}"] += 1
        for g in t["grains"]:
            vec[f"grain_{g}"] += 1
    if normalize:
        n = len(dishes)
        for c in FEATURE_COLUMNS:
            vec[c] /= n
    return vec


if __name__ == "__main__":
    sample = "기장밥<br/>쇠고기무국 (5.6)<br/>제육볶음 (10.13)<br/>두부조림<br/>배추김치 (9)<br/>요구르트"
    ds = parse_menu_string(sample)
    print("parsed:", ds)
    for d in ds:
        print(f"  {d:12s}", tag_dish(d))
    print(f"\n총 속성 차원: {len(FEATURE_COLUMNS)}")
    print("meal vec:", {k: round(v, 2) for k, v in meal_feature_vector(ds).items() if v})
