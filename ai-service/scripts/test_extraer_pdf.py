import argparse
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
sys.path.insert(0, ROOT_DIR)

from pdf_extractor import extract_pdf_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Test PDF extraction")
    parser.add_argument("--pdf", dest="pdf_path", default=None, help="Ruta al PDF")
    parser.add_argument("--self-test", action="store_true", help="Verifica imports sin PDF")
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--max-bytes", type=int, default=15000000)
    parser.add_argument("--min-text-chars", type=int, default=30)
    parser.add_argument("--ocr-lang", type=str, default="spa")
    args = parser.parse_args()

    if args.self_test:
        print("ok: imports")
        return 0

    if not args.pdf_path:
        print("error: provide --pdf or --self-test")
        return 2

    with open(args.pdf_path, "rb") as handle:
        content = handle.read()

    result = extract_pdf_text(
        content,
        max_pages=args.max_pages,
        max_bytes=args.max_bytes,
        min_text_chars=args.min_text_chars,
        ocr_lang=args.ocr_lang,
    )

    print(f"pages={result.page_count} ocr_used={result.ocr_used}")
    for page in result.pages:
        snippet = page.text[:120].replace("\n", " ")
        print(f"p{page.page_number}: ocr={page.ocr_used} text={snippet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
