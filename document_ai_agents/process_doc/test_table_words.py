#!/usr/bin/env python3

import pdfplumber
from pathlib import Path
from extract_pdf import not_within_bboxes

def test_specific_table_words():
    """Test that specific words from tables are properly excluded"""
    pdf_path = "/home/lixc/Documents/dl/files/VECTOR ABS Users Manual.pdf"
    
    print("Testing specific table word exclusion on page 10...")
    
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[9]  # Page 10 (0-indexed)
        
        # Find tables and their bounding boxes
        tables = page.find_tables()
        table_bboxes = [table.bbox for table in tables]
        
        # Extract all words
        all_words = page.extract_words()
        
        # Filter words outside tables 
        filtered_words = [word for word in all_words if not_within_bboxes(word, table_bboxes, tolerance=5)]
        
        # Get words inside tables for comparison
        table_words = [word for word in all_words if not not_within_bboxes(word, table_bboxes, tolerance=5)]
        
        print(f"Total words on page: {len(all_words)}")
        print(f"Words outside tables: {len(filtered_words)}")
        print(f"Words inside tables: {len(table_words)}")
        
        # Show some table words that should be excluded
        print(f"\nFirst 10 words that are INSIDE tables (should be excluded):")
        for i, word in enumerate(table_words[:10]):
            print(f"  {i+1}. '{word['text']}' at ({word['x0']:.1f}, {word['top']:.1f})")
        
        # Check if some common table header words are properly excluded
        filtered_text_words = set(word['text'].lower() for word in filtered_words)
        table_text_words = set(word['text'].lower() for word in table_words)
        
        print(f"\nChecking exclusion of table-specific words:")
        table_headers = ['correlation', 'structure', 'fitch', 'defined']
        for header in table_headers:
            in_filtered = header in filtered_text_words  
            in_table = header in table_text_words
            print(f"  '{header}' - in filtered text: {in_filtered}, in table text: {in_table}")
            
        # Show the text content of the first table for reference
        if tables:
            print(f"\nFirst table content (for reference):")
            table_data = tables[0].extract()
            for i, row in enumerate(table_data[:3]):  # Show first 3 rows
                print(f"  Row {i+1}: {row}")

if __name__ == "__main__":
    test_specific_table_words()