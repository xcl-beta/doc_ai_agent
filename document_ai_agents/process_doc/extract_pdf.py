import pdfplumber

from pathlib import Path

from typing import List, Dict, Optional, Tuple, Any

import time

import json

  

def extract_text_with_tables(pdf_path, temp_dir):

  """

  Extract text and tables from a PDF, preserving their original positions.

  Args:

    pdf_path: Path to the PDF file

    temp_dir: Temporary directory for storing images and metadata

  Returns:

    Tuple of (all_pages_content, page_metadata)

  """

  all_pages_content = []

  page_metadata = []

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

      # Extract text blocks (paragraphs) outside of tables

      # Get all words first, then filter them based on table boundaries
      all_words = page.extract_words()

      # Filter words that are NOT within table bounding boxes
 
      # NEW (word-level filtering )
      # Filter words that are NOT within table bounding boxes
      words = [word for word in all_words if not_within_bboxes(word, table_bboxes, tolerance=5)]

      if words:

        text_blocks = group_words_into_blocks(words)

        page_meta['num_text_blocks'] = len(text_blocks)

        for block in text_blocks:

          content_blocks.append({

            'type': 'text',

            'y_position': block['y_position'],

            'content': block['text'],

            'bbox': block['bbox'],

            'x_position': block['bbox'][0]

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

  
  

def _convert_pdf_to_markdown(input_path: Path, temp_dir: Path) -> Optional[Tuple[str, List[Dict], int, Dict]]:

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

    with pdfplumber.open(str(input_path)) as pdf:

      total_pages = len(pdf.pages)

      print(f"Processing {total_pages} pages...")

      # Extract content with preserved positions

      pages_content, page_metadata = extract_text_with_tables(str(input_path), temp_dir)

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

            # Detect if text should be a header

            text = block['content']

            if (len(text) < 100 and

              (text.isupper() or

              any(word in text.lower() for word in ['chapter', 'section', 'part']))):

              markdown_lines.append(f"### {text}")

              # need refinement for better header detection

            else:

              markdown_lines.append(text)

            markdown_lines.append("")

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

  input_pdf = Path("/home/lixc/Documents/dl/files/VECTOR ABS Users Manual.pdf")

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