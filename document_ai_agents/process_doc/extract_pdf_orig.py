import pdfplumber

from pathlib import Path

from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass

import time

import json

  

@dataclass
class ChartDetectionConfig:
  min_shapes: int = 12
  min_area_ratio: float = 0.03
  max_area_ratio: float = 0.6
  score_threshold: float = 50.0

  @staticmethod
  def from_dict(d: Dict[str, Any]) -> "ChartDetectionConfig":
    return ChartDetectionConfig(
      min_shapes=int(d.get("min_shapes", 12)),
      min_area_ratio=float(d.get("min_area_ratio", 0.03)),
      max_area_ratio=float(d.get("max_area_ratio", 0.6)),
      score_threshold=float(d.get("score_threshold", 50.0)),
    )


def _load_chart_config_if_present(preferred_paths: List[Path]) -> Optional[ChartDetectionConfig]:
  for p in preferred_paths:
    try:
      if p and p.exists() and p.is_file():
        with open(p, "r", encoding="utf-8") as f:
          data = json.load(f)
        cfg = ChartDetectionConfig.from_dict(data)
        print(f"Loaded chart config from: {p}")
        return cfg
    except Exception as e:
      print(f"Warning: failed to load chart config from {p}: {e}")
  return None


def extract_text_with_tables(pdf_path, temp_dir, chart_config: Optional[ChartDetectionConfig] = None):

  """

  Extract text, tables, images, and charts from a PDF, preserving their original positions.

  Args:

    pdf_path: Path to the PDF file

    temp_dir: Temporary directory for storing images and metadata

  Returns:

    Tuple of (all_pages_content, page_metadata)

  """

  all_pages_content = []

  page_metadata = []

  # Prepare chart detection config
  chart_cfg = chart_config or ChartDetectionConfig()

  # Analyze document-wide font characteristics for generic heading detection
  print("Analyzing document font hierarchy...")
  doc_font_analysis = analyze_document_fonts(pdf_path)
  print(f"Main font: {doc_font_analysis['main_font']} (size {doc_font_analysis['main_font_size']})")
  print(f"Detected {len(doc_font_analysis['hierarchy']['headings'])} heading font types")

  with pdfplumber.open(pdf_path) as pdf:

    for page_num, page in enumerate(pdf.pages):

      print(f"Processing page {page_num + 1}...")

      # Initialize metadata for this page

      page_meta = {

        'page_number': page_num + 1,

        'width': page.width,

        'height': page.height,

        'num_tables': 0,

        'num_images': 0,

        'num_charts': 0,

        'num_text_blocks': 0

      }

      # Find all tables and their bounding boxes

      tables = page.find_tables()

      table_bboxes = [table.bbox for table in tables]

      page_meta['num_tables'] = len(tables)

      # Detect chart regions (vector graphics clusters) and their bounding boxes
      chart_regions = detect_charts_on_page(page, chart_cfg)
      chart_bboxes = [c['bbox'] for c in chart_regions]
      page_meta['num_charts'] = len(chart_regions) if chart_regions else 0

      # Extract tables as raw data

      extracted_tables = []

      for table in tables:

        table_data = table.extract()

        extracted_tables.append(table_data)

      # Create content blocks with positions

      content_blocks = []

      # Add table blocks

      for i, (bbox, table_data) in enumerate(zip(table_bboxes, extracted_tables)):

        content_blocks.append({

          'type': 'table',

          'y_position': bbox[1],

          'content': table_data,

          'bbox': bbox,

          'x_position': bbox[0],

          'table_index': i + 1

        })

      # Add chart blocks (placeholders; images extracted later in markdown step)
      for i, chart in enumerate(chart_regions):
        cb = chart['bbox']
        content_blocks.append({
          'type': 'chart',
          'y_position': cb[1],
          'bbox': cb,
          'x_position': cb[0],
          'chart_index': i + 1,
          'score': chart.get('score', 0)
        })

      # Extract text blocks (paragraphs) outside of tables

      # Get all words first, then filter them based on table and chart boundaries
      all_words = page.extract_words()

      # Filter words that are NOT within table or chart bounding boxes
      combined_exclusion_bboxes = table_bboxes + chart_bboxes

      # NEW (word-level filtering )
      words = [word for word in all_words if not_within_bboxes(word, combined_exclusion_bboxes, tolerance=5)]

      if words:

        text_blocks = group_words_into_blocks(words)

        page_meta['num_text_blocks'] = len(text_blocks)

        for block in text_blocks:
          # Analyze formatting for this text block
          formatting_info = analyze_text_formatting(page, block['bbox'])
          is_heading, heading_level = is_likely_heading(block['text'], formatting_info, doc_font_analysis['hierarchy'])
          
          content_blocks.append({
            'type': 'text',
            'y_position': block['y_position'],
            'content': block['text'],
            'bbox': block['bbox'],
            'x_position': block['bbox'][0],
            'formatting': formatting_info,
            'is_heading': is_heading,
            'heading_level': heading_level
          })

      # Extract images

      images = page.images

      page_meta['num_images'] = len(images)

      for img_index, img in enumerate(images):

        content_blocks.append({

          'type': 'image',

          'y_position': img['top'],

          'x_position': img['x0'],

          'bbox': [img['x0'], img['top'], img['x1'], img['bottom']],

          'image_index': img_index + 1,

          'image_data': img

        })

      # Sort all content blocks by vertical position (top to bottom)

      content_blocks.sort(key=lambda x: x['y_position'])

      all_pages_content.append({

        'page_number': page_num + 1,

        'content_blocks': content_blocks,

        'width': page.width,

        'height': page.height

      })

      page_metadata.append(page_meta)

  return all_pages_content, page_metadata

  
  

def not_within_bboxes(obj, bboxes, tolerance=2):

  """

  Check if an object's bbox is NOT within any of the provided bboxes.

  Args:

    obj: Object with bbox coordinates (x0, y0, x1, y1 or top/bottom)

    bboxes: List of bounding boxes to check against

    tolerance: Pixel tolerance for bbox overlap detection

  """

  obj_x0 = obj.get("x0", 0)

  obj_y0 = obj.get("y0", obj.get("top", 0))

  obj_x1 = obj.get("x1", 0)

  obj_y1 = obj.get("y1", obj.get("bottom", 0))

  for bbox in bboxes:

    bbox_x0, bbox_y0, bbox_x1, bbox_y1 = bbox

    # Check if object overlaps with or is contained within the bbox

    # Using tolerance to catch edge cases

    if (obj_x0 >= (bbox_x0 - tolerance) and

      obj_y0 >= (bbox_y0 - tolerance) and

      obj_x1 <= (bbox_x1 + tolerance) and

      obj_y1 <= (bbox_y1 + tolerance)):

      return False

    # Also check for any overlap (not just complete containment)

    if (obj_x0 < bbox_x1 and obj_x1 > bbox_x0 and

      obj_y0 < bbox_y1 and obj_y1 > bbox_y0):

      return False

  return True

  
  

def analyze_document_fonts(pdf_path, sample_pages=None):
  """
  Analyze font usage patterns across the entire document to identify typography hierarchy.
  
  Args:
    pdf_path: Path to the PDF file
    sample_pages: List of page indices to sample (None = analyze all pages)
  
  Returns:
    Dict with document font characteristics and hierarchy
  """
  import pdfplumber
  from collections import Counter, defaultdict
  
  with pdfplumber.open(pdf_path) as pdf:
    # Sample pages for analysis (use all if not specified, or first 10 for large docs)
    if sample_pages is None:
      if len(pdf.pages) <= 10:
        sample_pages = list(range(len(pdf.pages)))
      else:
        # Sample first, middle, and last pages for large documents
        total = len(pdf.pages)
        sample_pages = [0, 1, 2, total//4, total//2, 3*total//4, total-3, total-2, total-1]
        sample_pages = [i for i in sample_pages if 0 <= i < total]
    
    # Collect font statistics
    font_stats = defaultdict(lambda: {'count': 0, 'sizes': [], 'total_chars': 0})
    all_sizes = Counter()
    all_chars = 0
    
    for page_idx in sample_pages:
      if page_idx >= len(pdf.pages):
        continue
        
      page = pdf.pages[page_idx]
      chars = page.chars
      
      for char in chars:
        font_name = char.get('fontname', 'unknown')
        font_size = char.get('size', 12.0)
        
        font_stats[font_name]['count'] += 1
        font_stats[font_name]['sizes'].append(font_size)
        font_stats[font_name]['total_chars'] += 1
        all_sizes[font_size] += 1
        all_chars += 1
    
    # Analyze patterns
    # 1. Identify main body font (most frequent)
    main_font = max(font_stats.keys(), key=lambda f: font_stats[f]['count'])
    main_font_stats = font_stats[main_font]
    main_font_size = Counter(main_font_stats['sizes']).most_common(1)[0][0]
    
    # 2. Identify potential heading fonts
    heading_indicators = {}
    
    for font_name, stats in font_stats.items():
      if stats['count'] < 10:  # Skip rarely used fonts
        continue
        
      avg_size = sum(stats['sizes']) / len(stats['sizes'])
      max_size = max(stats['sizes'])
      usage_percentage = (stats['count'] / all_chars) * 100
      
      # Check if this could be a heading font
      is_bold = 'bold' in font_name.lower()
      is_larger = avg_size > main_font_size * 1.1  # 10% larger than main
      is_much_larger = avg_size > main_font_size * 1.3  # 30% larger than main
      is_different_family = not any(main_word in font_name.lower() for main_word in main_font.lower().split('-'))
      
      heading_score = 0
      if is_bold: heading_score += 3
      if is_much_larger: heading_score += 3
      elif is_larger: heading_score += 2
      if is_different_family and usage_percentage < 30: heading_score += 2
      if usage_percentage < 5: heading_score += 1  # Less frequent = more likely heading
      
      heading_indicators[font_name] = {
        'score': heading_score,
        'avg_size': avg_size,
        'max_size': max_size,
        'usage_percent': usage_percentage,
        'is_bold': is_bold,
        'is_larger': is_larger,
        'is_different_family': is_different_family
      }
    
    # Create hierarchy levels
    # Sort fonts by heading score and size
    potential_headings = [(name, info) for name, info in heading_indicators.items() if info['score'] >= 2]
    potential_headings.sort(key=lambda x: (-x[1]['score'], -x[1]['avg_size']))
    
    # Assign hierarchy levels
    font_hierarchy = {
      'main_body': {'font': main_font, 'size': main_font_size, 'level': 0},
      'headings': {}
    }
    
    for i, (font_name, info) in enumerate(potential_headings[:4]):  # Max 4 heading levels
      level = i + 2  # Start from level 2 (## heading)
      font_hierarchy['headings'][font_name] = {
        'level': level,
        'avg_size': info['avg_size'],
        'score': info['score'],
        'characteristics': info
      }
    
    return {
      'main_font': main_font,
      'main_font_size': main_font_size,
      'hierarchy': font_hierarchy,
      'all_fonts': dict(font_stats),
      'size_distribution': dict(all_sizes),
      'total_chars_analyzed': all_chars
    }

def analyze_text_formatting(page, text_bbox):
  """
  Analyze the formatting characteristics of text within a bounding box.
  
  Args:
    page: pdfplumber page object
    text_bbox: Bounding box coordinates [x0, y0, x1, y1]
  
  Returns:
    Dict with formatting info: font_names, font_sizes, is_bold, is_larger, etc.
  """
  chars = page.chars
  if not chars:
    return {}
  
  # Find characters within the text bbox
  text_chars = []
  for char in chars:
    char_x = char.get('x0', 0)
    char_y = char.get('top', 0)
    if (char_x >= text_bbox[0] and char_x <= text_bbox[2] and
        char_y >= text_bbox[1] and char_y <= text_bbox[3]):
      text_chars.append(char)
  
  if not text_chars:
    return {}
  
  # Analyze font characteristics
  font_names = [c.get('fontname', '') for c in text_chars if c.get('fontname')]
  font_sizes = [c.get('size', 0) for c in text_chars if c.get('size')]
  
  # Calculate statistics
  avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12.0
  most_common_font = max(set(font_names), key=font_names.count) if font_names else ''
  
  # Determine if this is likely a heading
  is_bold = any('bold' in font.lower() for font in font_names)
  is_helvetica = any('helvetica' in font.lower() for font in font_names)
  has_larger_font = avg_font_size > 12.5  # Slightly larger than normal
  
  return {
    'font_names': list(set(font_names)),
    'font_sizes': list(set(font_sizes)),
    'avg_font_size': avg_font_size,
    'most_common_font': most_common_font,
    'is_bold': is_bold,
    'is_helvetica': is_helvetica,
    'has_larger_font': has_larger_font
  }

def is_likely_heading(text, formatting_info, doc_font_hierarchy=None, page_chars=None):
  """
  Determine if text is likely a heading based on content and formatting.
  
  Args:
    text: The text content
    formatting_info: Font/formatting information from analyze_text_formatting
    page_chars: Optional page characters for context
  
  Returns:
    Tuple of (is_heading: bool, heading_level: int)
  """
  if not text or not text.strip():
    return False, 0
  
  text = text.strip()
  
  # Skip very long text (likely paragraphs)
  if len(text) > 200:
    return False, 0
  
  # Dynamic font-based detection (primary)
  most_common_font = formatting_info.get('most_common_font', '')
  avg_font_size = formatting_info.get('avg_font_size', 12.0)
  
  # Use document hierarchy if available, otherwise fall back to heuristics
  if doc_font_hierarchy:
    main_font = doc_font_hierarchy['main_body']['font']
    main_font_size = doc_font_hierarchy['main_body']['size']
    heading_fonts = doc_font_hierarchy['headings']
    
    # Check if this text uses a known heading font
    font_level = 0
    for font_name, font_info in heading_fonts.items():
      if most_common_font == font_name:
        font_level = font_info['level']
        break
    
    # Additional checks for size-based headings
    is_larger_font = avg_font_size > main_font_size * 1.15  # 15% larger
    is_much_larger_font = avg_font_size > main_font_size * 1.4  # 40% larger
  else:
    # Fallback to heuristic detection
    is_bold = 'bold' in most_common_font.lower()
    is_italic = 'italic' in most_common_font.lower()
    has_larger_font = avg_font_size > 12.5
    font_level = 0
  
  # Content-based patterns (secondary)
  # Pattern for numbered/lettered sections: "A. Something", "1. Something", "B)", etc.
  import re
  is_numbered_section = bool(re.match(r'^[A-Z]\.|^\d+\.|^[A-Z]\)', text))
  
  # Pattern for section headers ending with dash/colon
  is_section_header = bool(re.match(r'^[A-Z][a-z]+\s*[-:]', text))
  
  # Very short text that's all caps (but not too common)
  is_short_caps = len(text) < 50 and text.isupper() and len(text.split()) <= 4
  
  # Determine heading characteristics
  heading_score = 0
  
  # Font-based scoring (most reliable)
  if doc_font_hierarchy:
    # Use document-specific font hierarchy
    if font_level > 0:
      heading_score += 4  # Strong indicator from document analysis
    if is_much_larger_font:
      heading_score += 2
    elif is_larger_font:
      heading_score += 1
  else:
    # Fallback heuristic scoring
    if is_bold:
      heading_score += 2
    if is_italic:
      heading_score += 1
    if has_larger_font:
      heading_score += 1
  
  # Content-based scoring
  if is_numbered_section:
    heading_score += 2
  elif is_section_header:
    heading_score += 2
  elif is_short_caps:
    heading_score += 1
  
  # Determine heading level
  if doc_font_hierarchy and font_level > 0:
    # Use the level from document analysis
    return True, font_level
  elif heading_score >= 4:
    return True, 2  # ## heading
  elif heading_score >= 2:
    return True, 3  # ### heading
  
  return False, 0

def group_words_into_blocks(words, vertical_gap_threshold=5):

  """

  Group words into text blocks based on vertical proximity.

  Args:

    words: List of word dictionaries from pdfplumber

    vertical_gap_threshold: Maximum vertical gap to consider words in same block

  Returns:

    List of text blocks with position information

  """

  if not words:

    return []

  sorted_words = sorted(words, key=lambda w: (w['top'], w['x0']))

  blocks = []

  current_block = {

    'words': [sorted_words[0]],

    'y_position': sorted_words[0]['top'],

    'bbox': [sorted_words[0]['x0'], sorted_words[0]['top'],

        sorted_words[0]['x1'], sorted_words[0]['bottom']]

  }

  for word in sorted_words[1:]:

    vertical_gap = abs(word['top'] - current_block['words'][-1]['top'])

    if vertical_gap <= vertical_gap_threshold:

      current_block['words'].append(word)

      current_block['bbox'][0] = min(current_block['bbox'][0], word['x0'])

      current_block['bbox'][1] = min(current_block['bbox'][1], word['top'])

      current_block['bbox'][2] = max(current_block['bbox'][2], word['x1'])

      current_block['bbox'][3] = max(current_block['bbox'][3], word['bottom'])

    else:

      current_block['text'] = ' '.join([w['text'] for w in current_block['words']])

      blocks.append(current_block)

      current_block = {

        'words': [word],

        'y_position': word['top'],

        'bbox': [word['x0'], word['top'], word['x1'], word['bottom']]

      }

  current_block['text'] = ' '.join([w['text'] for w in current_block['words']])

  blocks.append(current_block)

  return blocks

  
  

def _bbox_from_shape(shape: Dict[str, Any]) -> List[float]:
  x0 = shape.get('x0', shape.get('x_min', 0))
  x1 = shape.get('x1', shape.get('x_max', 0))
  top = shape.get('top', shape.get('y0', 0))
  bottom = shape.get('bottom', shape.get('y1', 0))
  # Normalize in case values are swapped
  x_left = min(x0, x1)
  x_right = max(x0, x1)
  y_top = min(top, bottom)
  y_bottom = max(top, bottom)
  return [x_left, y_top, x_right, y_bottom]


def _bboxes_overlap(b1, b2, tolerance=2) -> bool:
  return not (b1[2] < b2[0] - tolerance or b1[0] > b2[2] + tolerance or b1[3] < b2[1] - tolerance or b1[1] > b2[3] + tolerance)


def _merge_bbox(b1, b2):
  return [min(b1[0], b2[0]), min(b1[1], b2[1]), max(b1[2], b2[2]), max(b1[3], b2[3])]


def _merge_overlapping_bboxes(bboxes: List[List[float]], tolerance=4) -> List[List[float]]:
  if not bboxes:
    return []
  merged = []
  for b in bboxes:
    placed = False
    for i in range(len(merged)):
      if _bboxes_overlap(merged[i], b, tolerance=tolerance):
        merged[i] = _merge_bbox(merged[i], b)
        placed = True
        break
    if not placed:
      merged.append(b)
  # Iterate until stable
  changed = True
  while changed:
    changed = False
    result = []
    for b in merged:
      merged_flag = False
      for i in range(len(result)):
        if _bboxes_overlap(result[i], b, tolerance=tolerance):
          result[i] = _merge_bbox(result[i], b)
          merged_flag = True
          changed = True
          break
      if not merged_flag:
        result.append(b)
    merged = result
  return merged


def detect_charts_on_page(page, chart_cfg: ChartDetectionConfig) -> List[Dict[str, Any]]:
  """Heuristically detect chart regions by clustering vector graphics (lines/rects/curves).
  Returns list of dicts with bbox and score.
  """
  page_width, page_height = page.width, page.height
  # Unpack config
  min_shapes = chart_cfg.min_shapes
  min_area_ratio = chart_cfg.min_area_ratio
  max_area_ratio = chart_cfg.max_area_ratio
  score_threshold = chart_cfg.score_threshold
  page_area = page_width * page_height

  shapes = []
  # Collect vector objects
  for ln in getattr(page, 'lines', []) or []:
    shapes.append(_bbox_from_shape(ln))
  for rc in getattr(page, 'rects', []) or []:
    shapes.append(_bbox_from_shape(rc))
  for cv in getattr(page, 'curves', []) or []:
    shapes.append(_bbox_from_shape(cv))

  if not shapes:
    return []

  # Merge nearby/overlapping shapes to form candidate regions
  merged_boxes = _merge_overlapping_bboxes(shapes, tolerance=6)

  # Score regions
  chart_regions = []
  for mb in merged_boxes:
    area = (mb[2] - mb[0]) * (mb[3] - mb[1])
    if area <= 0:
      continue
    area_ratio = area / page_area
    if area_ratio < min_area_ratio or area_ratio > max_area_ratio:
      continue

    # Count shapes whose centers fall within this region
    count = 0
    for s in shapes:
      cx = (s[0] + s[2]) / 2
      cy = (s[1] + s[3]) / 2
      if (cx >= mb[0] and cx <= mb[2] and cy >= mb[1] and cy <= mb[3]):
        count += 1

    if count < min_shapes:
      continue

    # Compute word density inside region
    words = page.extract_words()
    words_in_region = [w for w in words if not_within_bboxes(w, [mb]) is False]
    word_count = len(words_in_region)
    shapes_density = count / (area_ratio + 1e-6)
    word_density = word_count / (area_ratio + 1e-6)

    # Heuristic: charts have high shapes density and relatively lower word density
    score = shapes_density - (0.5 * word_density)
    if score > score_threshold:  # threshold from config
      chart_regions.append({'bbox': mb, 'score': score, 'shapes': count, 'words': word_count})

  # Merge overlapping chart regions once more
  final_bboxes = _merge_overlapping_bboxes([c['bbox'] for c in chart_regions], tolerance=6)
  final_regions = []
  for fb in final_bboxes:
    # recompute basic score approx
    area = (fb[2] - fb[0]) * (fb[3] - fb[1])
    area_ratio = area / page_area
    # approximate counts
    count = sum(1 for s in shapes if ( (s[0]+s[2])/2 >= fb[0] and (s[0]+s[2])/2 <= fb[2] and (s[1]+s[3])/2 >= fb[1] and (s[1]+s[3])/2 <= fb[3]))
    words = page.extract_words()
    word_count = len([w for w in words if not_within_bboxes(w, [fb]) is False])
    shapes_density = count / (area_ratio + 1e-6)
    word_density = word_count / (area_ratio + 1e-6)
    score = shapes_density - (0.5 * word_density)
    final_regions.append({'bbox': fb, 'score': score, 'shapes': count, 'words': word_count})

  return final_regions


def _skip_watermark_images(img, page, min_area_ratio=0.01, max_area_ratio=0.9):

  """Skip very small or very large images that might be watermarks or backgrounds."""

  img_area = (img['x1'] - img['x0']) * (img['bottom'] - img['top'])

  page_area = page.width * page.height

  area_ratio = img_area / page_area

  return area_ratio < min_area_ratio or area_ratio > max_area_ratio

  
  

def _convert_table_to_markdown(table_data) -> List[str]:

  """Convert a table data structure to markdown table format."""

  if not table_data or len(table_data) == 0:

    return []

  markdown_lines = []

  # Filter out None values and empty rows

  clean_table = []

  for row in table_data:

    if row and any(cell is not None and str(cell).strip() for cell in row):

      clean_row = [str(cell).strip() if cell is not None else "" for cell in row]

      clean_table.append(clean_row)

  if not clean_table:

    return []

  # Determine number of columns

  max_cols = max(len(row) for row in clean_table)

  # Normalize all rows to have the same number of columns

  for row in clean_table:

    while len(row) < max_cols:

      row.append("")

  # Create markdown table

  if len(clean_table) > 0:

    header_row = clean_table[0]

    markdown_lines.append("| " + " | ".join(header_row) + " |")

    separator = "|" + "|".join([" --- " for _ in range(max_cols)]) + "|"

    markdown_lines.append(separator)

    for row in clean_table[1:]:

      markdown_lines.append("| " + " | ".join(row) + " |")

  return markdown_lines

  
  

def _convert_pdf_to_markdown(input_path: Path, temp_dir: Path, chart_config: Optional[ChartDetectionConfig] = None) -> Optional[Tuple[str, List[Dict], int, Dict]]:

  """

  Convert PDF to Markdown using pdfplumber.

  Args:

    input_path: Path to the PDF file

    temp_dir: Temporary directory for storing images and metadata

  Returns:

    Tuple of (markdown_content, extracted_images, image_counter, metadata)

  """

  try:

    from PIL import Image

    # Create image extraction directory

    images_dir = temp_dir / "images"

    images_dir.mkdir(exist_ok=True)

    print(f"Converting PDF {input_path.name} to Markdown with pdfplumber...")

    markdown_lines = []

    extracted_images = []

    image_counter = 0

    # Load chart config if not provided
    if chart_config is None:
      default_paths = [
        temp_dir / "chart_config.json",
        Path.cwd() / "chart_config.json",
        input_path.parent / "chart_config.json",
      ]
      chart_config = _load_chart_config_if_present(default_paths) or ChartDetectionConfig()

    with pdfplumber.open(str(input_path)) as pdf:

      total_pages = len(pdf.pages)

      print(f"Processing {total_pages} pages...")

      # Extract content with preserved positions

      pages_content, page_metadata = extract_text_with_tables(str(input_path), temp_dir, chart_config)

      # Document header

      markdown_lines.append(f"# {input_path.stem}")

      markdown_lines.append("")

      markdown_lines.append(f"*Converted from PDF on {time.strftime('%Y-%m-%d %H:%M:%S')}*")

      markdown_lines.append(f"*Total Pages: {total_pages}*")

      markdown_lines.append("")

      markdown_lines.append("---")

      markdown_lines.append("")

      for page_idx, page_data in enumerate(pages_content):

        page_num = page_data['page_number']

        page = pdf.pages[page_idx]

        # Page header

        markdown_lines.append(f"## Page {page_num}")

        markdown_lines.append("")

        # Add metadata comment

        meta = page_metadata[page_idx]

        markdown_lines.append(f"<!-- Page Metadata: Tables={meta['num_tables']}, Images={meta['num_images']}, "

                  f"TextBlocks={meta['num_text_blocks']}, Dimensions={meta['width']:.2f}x{meta['height']:.2f} -->")

        markdown_lines.append("")

        # Process content blocks in order

        for block in page_data['content_blocks']:

          if block['type'] == 'text':

            # Use font-based heading detection
            text = block['content']
            is_heading = block.get('is_heading', False)
            heading_level = block.get('heading_level', 0)
            
            if is_heading and heading_level > 0:
              heading_prefix = '#' * heading_level
              markdown_lines.append(f"{heading_prefix} {text}")
            else:
              markdown_lines.append(text)
            
            markdown_lines.append("")

          elif block['type'] == 'chart':
            # Render chart region to image
            bbox = block['bbox']
            try:
              img_obj = page.within_bbox((bbox[0], bbox[1], bbox[2], bbox[3]))
              pil_image = img_obj.to_image(resolution=150).original
              image_counter += 1
              img_filename = f"page_{page_num:03d}_chart_{block['chart_index']:02d}.png"
              img_path = images_dir / img_filename
              pil_image.save(img_path, 'PNG')
              relative_path = f"images/{img_filename}"
              markdown_lines.append(f"<!-- Chart {block['chart_index']}: pos=({bbox[0]:.2f},{bbox[1]:.2f},{bbox[2]:.2f},{bbox[3]:.2f}), score={block.get('score',0):.1f} -->")
              markdown_lines.append(f"![Chart {block['chart_index']} from page {page_num}]({relative_path})")
              markdown_lines.append("")
              extracted_images.append({
                'index': image_counter,
                'image': pil_image,
                'filename': img_filename,
                'path': str(img_path),
                'relative_path': relative_path,
                'page_number': page_num,
                'position': bbox,
                'type': 'chart'
              })
            except Exception as e:
              print(f"Error rendering chart region on page {page_num}: {e}")

          elif block['type'] == 'table':
            # Add table with position metadata

            bbox = block['bbox']

            markdown_lines.append(f"<!-- Table {block['table_index']}: pos=({bbox[0]:.2f},{bbox[1]:.2f},{bbox[2]:.2f},{bbox[3]:.2f}) -->")

            markdown_table = _convert_table_to_markdown(block['content'])

            if markdown_table:

              markdown_lines.extend(markdown_table)

              markdown_lines.append("")

          elif block['type'] == 'image':

            # Extract and save image

            img = block['image_data']

            if _skip_watermark_images(img, page):

              continue

            try:

              img_obj = page.within_bbox((img['x0'], img['top'], img['x1'], img['bottom']))

              pil_image = img_obj.to_image(resolution=150).original

              image_counter += 1

              img_filename = f"page_{page_num:03d}_image_{block['image_index']:02d}.png"

              img_path = images_dir / img_filename

              pil_image.save(img_path, 'PNG')

              relative_path = f"images/{img_filename}"

              # Add image with position metadata

              bbox = block['bbox']

              markdown_lines.append(f"<!-- Image {image_counter}: pos=({bbox[0]:.2f},{bbox[1]:.2f},{bbox[2]:.2f},{bbox[3]:.2f}) -->")

              markdown_lines.append(f"![Image {image_counter} from page {page_num}]({relative_path})")

              markdown_lines.append("")

              # Store image for OCR

              extracted_images.append({

                'index': image_counter,

                'image': pil_image,

                'filename': img_filename,

                'path': str(img_path),

                'relative_path': relative_path,

                'page_number': page_num,

                'position': bbox

              })

              print(f"Extracted image: page {page_num}, image {block['image_index']} -> {img_filename}")

            except Exception as e:

              print(f"Error extracting image {block['image_index']} from page {page_num}: {e}")

        markdown_lines.append("---")

        markdown_lines.append("")

      markdown_content = '\n'.join(markdown_lines)

      # Save metadata to JSON file

      metadata_path = temp_dir / "metadata.json"

      metadata = {

        'pdf_name': input_path.name,

        'total_pages': total_pages,

        'conversion_date': time.strftime('%Y-%m-%d %H:%M:%S'),

        'total_images': image_counter,

        'pages': page_metadata

      }

      with open(metadata_path, 'w', encoding='utf-8') as f:

        json.dump(metadata, f, indent=2)

      print(f"Successfully converted PDF to Markdown")

      print(f"Extracted {image_counter} images")

      print(f"Metadata saved to: {metadata_path}")

      return markdown_content, extracted_images, image_counter, metadata

  except Exception as e:

    print(f"Error converting PDF {input_path.name}: {e}")

    return None

  
  

# Example usage

if __name__ == "__main__":

  from pathlib import Path

  input_pdf = Path("/home/lixc/Documents/dl/files/2008 Financial Turmoil Increases Variable Annuity Risk.pdf")

  temp_directory = Path("./temp_output")

  temp_directory.mkdir(exist_ok=True)

  # Convert PDF to markdown with images and metadata

  result = _convert_pdf_to_markdown(input_pdf, temp_directory)

  if result:

    markdown_content, extracted_images, image_count, metadata = result

    # Save markdown to file

    output_md = temp_directory / f"{input_pdf.stem}.md"

    with open(output_md, 'w', encoding='utf-8') as f:

      f.write(markdown_content)

    print(f"\nMarkdown saved to: {output_md}")

    print(f"Images saved to: {temp_directory / 'images'}")

    print(f"Metadata saved to: {temp_directory / 'metadata.json'}")

    # Print summary

    print(f"\nSummary:")

    print(f" Total pages: {metadata['total_pages']}")

    print(f" Total images: {metadata['total_images']}")

    for page_meta in metadata['pages']:

      print(f" Page {page_meta['page_number']}: "

         f"{page_meta['num_tables']} tables, "

         f"{page_meta['num_images']} images, "

         f"{page_meta['num_text_blocks']} text blocks")
      


      