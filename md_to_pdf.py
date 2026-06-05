"""
md_to_pdf.py
------------
마크다운 문서를 PDF로 변환한다. 한글(Noto Sans CJK KR)·인라인 <img>·표·코드블록을
그대로 살리기 위해 마크다운 → HTML → PDF(weasyprint) 경로를 쓴다.

사전 설치(한 번):
    uv pip install --python .venv/bin/python markdown weasyprint

사용:
    .venv/bin/python md_to_pdf.py                 # 루트 주요 문서 일괄 변환
    .venv/bin/python md_to_pdf.py TRENDS.md       # 특정 파일
    .venv/bin/python md_to_pdf.py a.md b.md -o pdf # 여러 파일, 출력 폴더 지정

상대 이미지 경로(assets/...)는 각 MD 파일이 있는 폴더 기준으로 해석한다.
산출물 pdf/ 는 .gitignore 대상(재생성 가능).
"""
import argparse
import sys
from pathlib import Path

# 변환 안 풀어줄 때 친절히 안내
try:
    import markdown
    from weasyprint import HTML
except ModuleNotFoundError as e:
    sys.exit(f"[의존성 없음] {e.name}\n  설치: uv pip install --python .venv/bin/python markdown weasyprint")

# 기본 변환 대상(인자 없을 때) — 발표용 reader 문서
DEFAULT_DOCS = ["README.md", "TRENDS.md", "METHODS.md", "DYNAMICS.md"]

# paper 테마(map.html·figure와 통일): 크림 배경 #f6f1e7, 잉크 #211d17, 강조 #b6452c
CSS = """
@page { size: A4; margin: 18mm 15mm;
  @bottom-center { content: counter(page); font-size: 9pt; color: #9a9080; } }
body { font-family: "Noto Sans CJK KR","Noto Sans KR",sans-serif;
  font-size: 10.5pt; line-height: 1.65; color: #211d17; }
h1,h2,h3,h4 { font-weight: 700; line-height: 1.3; margin: 1.2em 0 .5em; page-break-after: avoid; }
h1 { font-size: 19pt; border-bottom: 2px solid #b6452c; padding-bottom: .2em; }
h2 { font-size: 14.5pt; border-bottom: 1px solid #e0d8c8; padding-bottom: .15em; margin-top: 1.5em; }
h3 { font-size: 12pt; color: #4a4030; }
h4 { font-size: 10.8pt; }
p { margin: .5em 0; }
a { color: #b6452c; text-decoration: none; word-break: break-all; }
img { max-width: 100%; height: auto; vertical-align: top; page-break-inside: avoid; }
table { border-collapse: collapse; width: 100%; margin: .8em 0; font-size: 9pt;
  page-break-inside: avoid; }
th,td { border: 1px solid #d6c9b0; padding: 4px 7px; text-align: left; vertical-align: top; }
th { background: #efe6d5; }
tr:nth-child(even) td { background: #faf6ee; }
blockquote { margin: .8em 0; padding: .35em .9em; border-left: 3px solid #b6452c;
  background: #faf6ee; }
blockquote p { margin: .3em 0; }
code { font-family: "DejaVu Sans Mono",monospace; font-size: 9pt; background: #efe6d5;
  padding: 1px 4px; border-radius: 3px; word-break: break-all; }
pre { background: #f3eee2; padding: 9px 12px; border-radius: 5px;
  white-space: pre-wrap; word-wrap: break-word; }
pre code { background: none; padding: 0; }
hr { border: none; border-top: 1px solid #e0d8c8; margin: 1.3em 0; }
ul,ol { margin: .4em 0 .4em 1.1em; padding-left: .6em; }
li { margin: .2em 0; }
"""

TEMPLATE = '<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">' \
           '<style>{css}</style></head><body>{body}</body></html>'


def convert(md_path: Path, out_dir: Path) -> Path:
    text = md_path.read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["extra", "sane_lists"])
    html = TEMPLATE.format(css=CSS, body=body)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (md_path.stem + ".pdf")
    # base_url = MD 파일 폴더 → 상대 경로 이미지(assets/...) 해석
    HTML(string=html, base_url=str(md_path.resolve().parent) + "/").write_pdf(str(out))
    return out


def main():
    ap = argparse.ArgumentParser(description="마크다운 → PDF (한글·이미지·표 보존)")
    ap.add_argument("files", nargs="*", help="변환할 .md (없으면 루트 주요 문서)")
    ap.add_argument("-o", "--out-dir", default="pdf", help="출력 폴더 (기본 pdf/)")
    args = ap.parse_args()

    targets = [Path(f) for f in args.files] or [Path(d) for d in DEFAULT_DOCS]
    out_dir = Path(args.out_dir)
    ok = 0
    for md in targets:
        if not md.is_file():
            print(f"  건너뜀(없음): {md}")
            continue
        out = convert(md, out_dir)
        size_kb = out.stat().st_size / 1024
        print(f"  ✓ {md} → {out} ({size_kb:.0f} KB)")
        ok += 1
    print(f"완료: {ok}개 PDF 생성 → {out_dir}/")


if __name__ == "__main__":
    main()
