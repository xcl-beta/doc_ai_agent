#!/usr/bin/env python3

import pdfplumber
from pathlib import Path
from extract_pdf import extract_text_with_tables, not_within_bboxes

def test_page_10_filtering():
    """Test table text filtering on page 10 of the PDF"""
    pdf_path = "/home/lixc/Documents/dl/files/VECTOR ABS Users Manual.pdf"
    
    print("Testing table text filtering on page 10...")
    
    with pdfplumber.open(pdf_path) as pdf:
        # Get page 10 (index 9)
        if len(pdf.pages) < 10:
            print(f"PDF only has {len(pdf.pages)} pages")
            return
            
        page = pdf.pages[9]  # Page 10 (0-indexed)
        print(f"Page dimensions: {page.width} x {page.height}")
        
        # Find tables and their bounding boxes
        tables = page.find_tables()
        table_bboxes = [table.bbox for table in tables]
        
        print(f"\nFound {len(tables)} tables on page 10:")
        for i, bbox in enumerate(table_bboxes):
            print(f"  Table {i+1} bbox: {bbox}")
        
        if tables:
            # Extract table data for comparison
            print(f"\nTable data preview:")
            for i, table in enumerate(tables):
                table_data = table.extract()
                print(f"  Table {i+1} has {len(table_data)} rows")
                if table_data and len(table_data) > 0:
                    print(f"    First row: {table_data[0]}")
        
        # Extract all text from page
        all_text = page.extract_text()
        print(f"\nAll text from page (first 200 chars):")
        print(repr(all_text[:200]))
        
        # Extract text outside tables using the FIXED filtering approach
        all_words_page = page.extract_words()
        # Filter words that are NOT within table bounding boxes
        filtered_words = [word for word in all_words_page if not_within_bboxes(word, table_bboxes, tolerance=5)]
        
        # Reconstruct filtered text from filtered words
        if filtered_words:
            # Sort by position and join
            sorted_filtered_words = sorted(filtered_words, key=lambda w: (w['top'], w['x0']))
            filtered_text = ' '.join([w['text'] for w in sorted_filtered_words])
        else:
            filtered_text = ""
        print(f"\nFiltered text (outside tables, first 200 chars):")
        print(repr(filtered_text[:200] if filtered_text else "No filtered text"))
        
        # Get words to see detailed positioning
        all_words = all_words_page
        
        print(f"\nWord count comparison:")
        print(f"  All words: {len(all_words)}")
        print(f"  Filtered words: {len(filtered_words)}")
        print(f"  Words in tables (should be): {len(all_words) - len(filtered_words)}")
        
        # Show some example words and their positions
        print(f"\nFirst 5 words from page:")
        for i, word in enumerate(all_words[:5]):
            print(f"  {i+1}. '{word['text']}' at ({word['x0']:.1f}, {word['top']:.1f})")
            
        print(f"\nFirst 5 filtered words:")
        for i, word in enumerate(filtered_words[:5]):
            print(f"  {i+1}. '{word['text']}' at ({word['x0']:.1f}, {word['top']:.1f})")
            
        # Test not_within_bboxes function directly on some words
        if all_words and table_bboxes:
            print(f"\nTesting not_within_bboxes function on first few words:")
            for i, word in enumerate(all_words[:10]):
                is_outside = not_within_bboxes(word, table_bboxes, tolerance=5)
                print(f"  Word '{word['text']}' at ({word['x0']:.1f}, {word['top']:.1f}) -> outside tables: {is_outside}")

if __name__ == "__main__":
    test_page_10_filtering()