#!/usr/bin/env python3

from pathlib import Path
from extract_pdf import analyze_document_fonts, extract_text_with_tables
import shutil

def test_document_font_analysis(pdf_file, test_pages=None):
    """Test font analysis on a specific PDF"""
    print(f"\n{'='*60}")
    print(f"Testing: {pdf_file}")
    print(f"{'='*60}")
    
    pdf_path = Path(f"/home/lixc/Documents/dl/files/{pdf_file}")
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        return
    
    try:
        # Analyze document fonts
        font_analysis = analyze_document_fonts(str(pdf_path))
        
        print(f"\nDocument Font Analysis:")
        print(f"Main body font: {font_analysis['main_font']}")
        print(f"Main font size: {font_analysis['main_font_size']}")
        print(f"Total characters analyzed: {font_analysis['total_chars_analyzed']}")
        
        print(f"\nFont Distribution:")
        for font, stats in sorted(font_analysis['all_fonts'].items(), 
                                key=lambda x: x[1]['count'], reverse=True)[:5]:
            percentage = (stats['count'] / font_analysis['total_chars_analyzed']) * 100
            avg_size = sum(stats['sizes']) / len(stats['sizes'])
            print(f"  {font}: {stats['count']} chars ({percentage:.1f}%), avg size: {avg_size:.1f}")
        
        print(f"\nDetected Heading Hierarchy:")  
        headings = font_analysis['hierarchy']['headings']
        if headings:
            for font_name, info in sorted(headings.items(), key=lambda x: x[1]['level']):
                print(f"  Level {info['level']}: {font_name}")
                print(f"    Score: {info['score']}, Avg size: {info['avg_size']:.1f}")
                char_info = info['characteristics']
                print(f"    Bold: {char_info['is_bold']}, Usage: {char_info['usage_percent']:.1f}%")
        else:
            print("  No heading fonts detected")
        
        # Test on a few text blocks if test_pages specified
        if test_pages:
            print(f"\nTesting heading detection on sample pages: {test_pages}")
            temp_dir = Path("./temp_generic_test")
            temp_dir.mkdir(exist_ok=True)
            
            try:
                pages_content, _ = extract_text_with_tables(str(pdf_path), temp_dir)
                
                for page_idx in test_pages:
                    if page_idx < len(pages_content):
                        page_data = pages_content[page_idx]
                        text_blocks = [b for b in page_data['content_blocks'] if b['type'] == 'text']
                        
                        print(f"\n  Page {page_idx + 1} - Text blocks with headings:")
                        heading_count = 0
                        for i, block in enumerate(text_blocks[:10]):  # Show first 10
                            if block.get('is_heading', False):
                                heading_count += 1
                                text = block['content'][:60] + ("..." if len(block['content']) > 60 else "")
                                level = block.get('heading_level', 0)
                                font = block.get('formatting', {}).get('most_common_font', 'unknown')
                                print(f"    {'#' * level} {text}")
                                print(f"      Font: {font}, Level: {level}")
                        
                        if heading_count == 0:
                            print("    No headings detected in first 10 text blocks")
                        else:
                            print(f"    Found {heading_count} headings in first 10 blocks")
                            
            except Exception as e:
                print(f"Error processing pages: {e}")
            finally:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                
    except Exception as e:
        print(f"Error analyzing {pdf_file}: {e}")

def main():
    """Test generic font detection on various PDF types"""
    
    # Test different types of PDFs
    test_cases = [
        ("VECTOR ABS Users Manual.pdf", [3, 6]),  # Technical manual (we know this one)
        ("2008 Financial Turmoil Increases Variable Annuity Risk.pdf", [0, 1]),  # Financial report
        ("edu-2008-spring-c-solutions.pdf", [0, 2]),  # Academic document
        ("Bulletin 2A - IRE Rating Process Manual[1].pdf", [0, 1]),  # Process manual
        ("fhar1003.pdf", None),  # Unknown type
    ]
    
    for pdf_file, test_pages in test_cases:
        test_document_font_analysis(pdf_file, test_pages)
    
    print(f"\n{'='*60}")
    print("Generic font detection testing completed!")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()