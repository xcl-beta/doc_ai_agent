#!/usr/bin/env python3

import pdfplumber
from pathlib import Path
from extract_pdf import analyze_text_formatting, is_likely_heading, extract_text_with_tables

def test_heading_detection_on_page(page_num):
    """Test the new heading detection on a specific page"""
    pdf_path = "/home/lixc/Documents/dl/files/VECTOR ABS Users Manual.pdf"
    
    print(f"=== Testing Heading Detection on Page {page_num} ===")
    
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) < page_num:
            print(f"PDF only has {len(pdf.pages)} pages")
            return
            
        page = pdf.pages[page_num - 1]  # Convert to 0-indexed
        
        # Get text blocks from our updated extraction function
        temp_dir = Path("./temp_test")
        temp_dir.mkdir(exist_ok=True)
        
        pages_content, page_metadata = extract_text_with_tables(pdf_path, temp_dir)
        page_content = pages_content[page_num - 1]  # Get specific page content
        
        print(f"Found {len(page_content['content_blocks'])} content blocks")
        
        # Test each text block for heading detection
        text_blocks = [block for block in page_content['content_blocks'] if block['type'] == 'text']
        
        print(f"\nText blocks and heading detection:")
        for i, block in enumerate(text_blocks):
            text = block['content'][:100] + ("..." if len(block['content']) > 100 else "")
            formatting = block.get('formatting', {})
            is_heading = block.get('is_heading', False)
            heading_level = block.get('heading_level', 0)
            
            print(f"\nBlock {i+1}:")
            print(f"  Text: '{text}'")
            print(f"  Is heading: {is_heading} (level {heading_level})")
            print(f"  Font: {formatting.get('most_common_font', 'unknown')}")
            print(f"  Size: {formatting.get('avg_font_size', 0):.1f}")
            print(f"  Bold: {formatting.get('is_bold', False)}")
            print(f"  Helvetica: {formatting.get('is_helvetica', False)}")
        
        # Look for specific patterns we know should be headings
        expected_headings = []
        if page_num == 4:
            expected_headings = ["A. System Requirements", "B. ", "System Requirements"]
        elif page_num == 7:
            expected_headings = ["Sector", "Region"]
        
        if expected_headings:
            print(f"\nChecking for expected headings:")
            for expected in expected_headings:
                found = False
                for block in text_blocks:
                    if expected.lower() in block['content'].lower():
                        is_heading = block.get('is_heading', False)
                        heading_level = block.get('heading_level', 0)
                        print(f"  '{expected}' -> Detected as heading: {is_heading} (level {heading_level})")
                        found = True
                        break
                if not found:
                    print(f"  '{expected}' -> Not found in text blocks")

def main():
    """Test heading detection on pages 4 and 7"""
    test_heading_detection_on_page(4)
    print("\n" + "="*60 + "\n")
    test_heading_detection_on_page(7)
    
    # Clean up
    temp_dir = Path("./temp_test")
    if temp_dir.exists():
        import shutil
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    main()