#!/usr/bin/env python3

from pathlib import Path
from extract_pdf import _convert_pdf_to_markdown

def test_markdown_conversion():
    """Test the improved markdown conversion on a subset of pages"""
    input_pdf = Path("/home/lixc/Documents/dl/files/VECTOR ABS Users Manual.pdf")
    temp_directory = Path("./temp_test_markdown")
    temp_directory.mkdir(exist_ok=True)
    
    # Convert PDF to markdown with improved heading detection
    result = _convert_pdf_to_markdown(input_pdf, temp_directory)
    
    if result:
        markdown_content, extracted_images, image_count, metadata = result
        
        # Save markdown to file
        output_md = temp_directory / f"{input_pdf.stem}_improved.md"
        with open(output_md, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        print(f"Improved Markdown saved to: {output_md}")
        print(f"Images saved to: {temp_directory / 'images'}")
        
        # Show some sample content from pages 4 and 7
        lines = markdown_content.split('\n')
        
        print("\n=== Sample from Page 4 (around System Requirements) ===")
        in_page_4 = False
        in_page_5 = False
        for i, line in enumerate(lines):
            if "## Page 4" in line:
                in_page_4 = True
            elif "## Page 5" in line:
                in_page_5 = True
                in_page_4 = False
            
            if in_page_4 and not in_page_5:
                if any(text in line.lower() for text in ["system requirements", "installation", "operating system", "software"]):
                    # Show this line and a few around it
                    start = max(0, i-1)
                    end = min(len(lines), i+2)
                    for j in range(start, end):
                        prefix = ">>> " if j == i else "    "
                        print(f"{prefix}{lines[j]}")
                    print()
        
        print("\n=== Sample from Page 7 (around Sector/Region definitions) ===")
        in_page_7 = False  
        in_page_8 = False
        for i, line in enumerate(lines):
            if "## Page 7" in line:
                in_page_7 = True
            elif "## Page 8" in line:
                in_page_8 = True
                in_page_7 = False
            
            if in_page_7 and not in_page_8:
                if any(text in line for text in ["Sector", "Region", "Band ID", "Band Minimum"]):
                    # Show this line and a few around it
                    start = max(0, i-1)
                    end = min(len(lines), i+2)
                    for j in range(start, end):
                        prefix = ">>> " if j == i else "    "
                        print(f"{prefix}{lines[j]}")
                    print()
        
        # Clean up
        import shutil
        shutil.rmtree(temp_directory)
        
        print(f"\nConversion successful! Processed {metadata['total_pages']} pages with {image_count} images.")
    else:
        print("Conversion failed!")

if __name__ == "__main__":
    test_markdown_conversion()