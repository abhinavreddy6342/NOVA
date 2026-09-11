from pathlib import Path

from app.knowledge.extractor import extract_text


pdf_path = (
    Path(__file__).resolve().parent
    / "app"
    / "knowledge"
    / "documents"
    / "test.pdf"
)

print(f"Testing PDF: {pdf_path}")

try:
    text = extract_text(str(pdf_path))

    print("\n========== OCR RESULT ==========\n")

    if text:
        print(text[:5000])
    else:
        print("NO TEXT EXTRACTED")

    print("\n===============================\n")
    print(f"Characters extracted: {len(text)}")

except Exception as exc:
    print("\nOCR TEST FAILED")
    print(exc)