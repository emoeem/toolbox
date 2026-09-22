from __future__ import annotations

from pathlib import Path
from pypdf import PdfReader, PdfWriter


def merge_pdfs(inputs: list[str], output: str) -> str:
    writer = PdfWriter()
    for path in inputs:
        reader = PdfReader(path)
        for page in reader.pages:
            writer.add_page(page)
    with open(output, "wb") as f:
        writer.write(f)
    return output


def split_pdf(input_path: str, output_dir: str) -> list[str]:
    reader = PdfReader(input_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = []
    stem = Path(input_path).stem
    for i, page in enumerate(reader.pages, 1):
        writer = PdfWriter()
        writer.add_page(page)
        out = out_dir / f"{stem}_{i:03d}.pdf"
        with out.open("wb") as f:
            writer.write(f)
        result.append(str(out))
    return result


def rotate_pdf(input_path: str, output: str, degrees: int = 90) -> str:
    reader = PdfReader(input_path)
    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(degrees)
        writer.add_page(page)
    with open(output, "wb") as f:
        writer.write(f)
    return output


def remove_pages(input_path: str, output: str, pages: list[int]) -> str:
    reader = PdfReader(input_path)
    remove = {p - 1 for p in pages}
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i not in remove:
            writer.add_page(page)
    with open(output, "wb") as f:
        writer.write(f)
    return output


def extract_text(input_path: str) -> str:
    reader = PdfReader(input_path)
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def set_metadata(input_path: str, output: str, metadata: dict[str, str]) -> str:
    reader = PdfReader(input_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata({f"/{k.lstrip('/')}": str(v) for k, v in metadata.items()})
    with open(output, "wb") as f:
        writer.write(f)
    return output


def protect_pdf(input_path: str, output: str, password: str) -> str:
    reader = PdfReader(input_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)
    with open(output, "wb") as f:
        writer.write(f)
    return output
