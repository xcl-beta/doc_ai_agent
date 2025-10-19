#!/usr/bin/env python3

from pathlib import Path
from extract_pdf import _convert_pdf_to_markdown


def test_charts_extraction():
    input_pdf = Path("/home/lixc/Documents/dl/data/files/2008 Financial Turmoil Increases Variable Annuity Risk.pdf")
    temp_directory = Path("./temp_charts_test")
    temp_directory.mkdir(exist_ok=True)

    result = _convert_pdf_to_markdown(input_pdf, temp_directory)
    if not result:
        print("Conversion failed")
        return

    markdown_content, extracted_images, image_count, metadata = result

    charts = [img for img in extracted_images if img.get('type') == 'chart']
    print(f"Total images saved: {image_count}")
    print(f"Charts detected: {len(charts)}")
    for c in charts[:5]:
        print(f"  Page {c['page_number']} -> {c['filename']} at {c['position']}")

    output_md = temp_directory / f"{input_pdf.stem}_with_charts.md"
    with open(output_md, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    print(f"Markdown saved: {output_md}")
    print(f"Images dir: {temp_directory / 'images'}")


if __name__ == "__main__":
    test_charts_extraction()
