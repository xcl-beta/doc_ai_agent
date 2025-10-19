#!/usr/bin/env python3

import pdfplumber
from pathlib import Path
from collections import defaultdict, Counter

def analyze_font_information(page_num):
    """Analyze font information for a specific page"""
    pdf_path = "/home/lixc/Documents/dl/files/VECTOR ABS Users Manual.pdf"
    
    print(f"=== Font Analysis for Page {page_num} ===")
    
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) < page_num:
            print(f"PDF only has {len(pdf.pages)} pages")
            return
            
        page = pdf.pages[page_num - 1]  # Convert to 0-indexed
        
        # Extract characters with font information
        chars = page.chars
        print(f"Total characters on page: {len(chars)}")
        
        if not chars:
            print("No character information available")
            return
            
        # Analyze font properties
        font_sizes = Counter()
        font_names = Counter()
        font_weights = defaultdict(list)
        
        # Sample some characters to understand structure
        print(f"\nFirst 5 characters with font info:")
        for i, char in enumerate(chars[:5]):
            print(f"  {i+1}. '{char['text']}' - size: {char.get('size', 'N/A')}, "
                  f"fontname: {char.get('fontname', 'N/A')}")
        
        # Collect statistics
        for char in chars:
            if char.get('size'):
                font_sizes[char['size']] += 1
            if char.get('fontname'):
                font_names[char['fontname']] += 1
                font_weights[char['fontname']].append(char.get('size', 0))
        
        print(f"\nFont Size Distribution:")
        for size, count in sorted(font_sizes.items(), reverse=True):
            percentage = (count / len(chars)) * 100
            print(f"  Size {size}: {count} chars ({percentage:.1f}%)")
        
        print(f"\nFont Name Distribution:")
        for name, count in font_names.most_common():
            percentage = (count / len(chars)) * 100
            avg_size = sum(font_weights[name]) / len(font_weights[name]) if font_weights[name] else 0
            print(f"  {name}: {count} chars ({percentage:.1f}%), avg size: {avg_size:.1f}")
        
        # Look for potential headings (larger fonts or different font names)
        main_font_size = font_sizes.most_common(1)[0][0] if font_sizes else 0
        larger_fonts = [size for size in font_sizes.keys() if size > main_font_size]
        
        print(f"\nMain font size: {main_font_size}")
        if larger_fonts:
            print(f"Larger font sizes found: {sorted(larger_fonts, reverse=True)}")
            
            # Find text with larger fonts
            print(f"\nText with larger fonts:")
            words_by_size = defaultdict(list)
            
            # Group characters into words by size
            current_word = ""
            current_size = None
            current_pos = None
            
            for char in chars:
                char_size = char.get('size', main_font_size)
                char_pos = (char['x0'], char['top'])
                
                # If we're starting a new word (different size or position gap)
                if (current_size is None or 
                    char_size != current_size or
                    (current_pos and abs(char['x0'] - current_pos[0]) > 5)):  # Gap in position
                    
                    if current_word.strip() and current_size:
                        words_by_size[current_size].append(current_word.strip())
                    
                    current_word = char['text']
                    current_size = char_size
                    current_pos = char_pos
                else:
                    current_word += char['text']
                    current_pos = char_pos
            
            # Add the last word
            if current_word.strip() and current_size:
                words_by_size[current_size].append(current_word.strip())
            
            # Show words by font size
            for size in sorted(words_by_size.keys(), reverse=True):
                if size > main_font_size and words_by_size[size]:
                    print(f"  Size {size}: {words_by_size[size][:10]}")  # Show first 10 words
        else:
            print("No larger fonts found")
            
        # Look for specific text patterns mentioned in the issue
        search_patterns = []
        if page_num == 4:
            search_patterns = ["A. System Requirements", "B.", "System", "Requirements"]
        elif page_num == 7:
            search_patterns = ["Sector", "Region", "provides a set of predefined sectors"]
            
        if search_patterns:
            print(f"\nSearching for specific patterns:")
            for pattern in search_patterns:
                found_chars = []
                # Simple search through characters
                text_chars = ''.join([c['text'] for c in chars])
                if pattern.lower() in text_chars.lower():
                    # Find the characters for this pattern
                    start_idx = text_chars.lower().find(pattern.lower())
                    end_idx = start_idx + len(pattern)
                    pattern_chars = chars[start_idx:end_idx]
                    
                    if pattern_chars:
                        sizes = [c.get('size', 0) for c in pattern_chars]
                        fonts = [c.get('fontname', 'unknown') for c in pattern_chars]
                        avg_size = sum(sizes) / len(sizes) if sizes else 0
                        print(f"  '{pattern}' - avg size: {avg_size:.1f}, fonts: {set(fonts)}")

def main():
    """Test font analysis on pages 4 and 7"""
    analyze_font_information(4)
    print("\n" + "="*60 + "\n")
    analyze_font_information(7)

if __name__ == "__main__":
    main()