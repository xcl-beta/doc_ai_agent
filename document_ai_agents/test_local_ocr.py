import fitz  # PycoMuPDF for PDFs
import ollama
import io
from PIL import Image
import os


import openai
import os
import logging 

from dotenv import load_dotenv, find_dotenv
from openai import OpenAI

import openai
import os
import logging 

from dotenv import load_dotenv, find_dotenv
from openai import OpenAI

import base64

def load_openai_api_key(env_path="/home/lixc/Documents/dl/.env"):
    """
    Load the OpenAI API key from environment variables.
    
    Args:
        env_path (str): Path to the .env file
        
    Returns:
        str: The loaded API key
        
    Raises:
        ValueError: If the API key is not found
    """
    _ = load_dotenv(
        find_dotenv(env_path, raise_error_if_not_found=True)
    )
    
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key is None:
        raise ValueError(
            "API key not found. Please set the OPENAI_API_KEY environment variable."
        )
    
    openai.api_key = api_key
    print("API key successfully loaded.")
    return api_key

 
def convert_pdf_to_images(pdf_path, output_dir=None):
    images = []
    doc = fitz.open(pdf_path)  # Open the PDF
    
    # Create output directory if specified and doesn't exist
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    for page_num in range(len(doc)):
        pix = doc[page_num].get_pixmap()  # Render page to pixel map
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)  # Convert to PIL image
        
        # Save to memory buffer for return value
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="PNG")  # Save as in-memory PNG
        images.append(img_buffer.getvalue())  # Raw PNG bytes
        
        # Save to disk if output directory is specified
        if output_dir:
            img_path = os.path.join(output_dir, f"page_{page_num+1}.png")
            img.save(img_path)
            print(f"Saved image to {img_path}")
            
    return images

prompt = "Extract all readable text and text chunks from this image" + \
         " and format it as structured Markdown." + \
         " Look in the entire image always and try to retrieve all text." + \
         " Output everything possible in the image in the output. Dont miss anything! "

def query_llm_with_images(image_bytes_list, model="gemma3:12b", prompt=prompt):
    response = ollama.chat(
        model=model,
        messages=[{
            "role": "user",
            "content": prompt,
            "images": image_bytes_list
        }]
    )
    return response["message"]["content"]

def encode_image(image_path):
    """
    Encodes an image file to a base64 string.
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')
    
def extract_text_from_openai_api(image_path):
    """
    Sends the base64-encoded image to the OpenAI API and retrieves the extracted text.
    """
    base64_image = encode_image(image_path)
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract the text from this image, ensuring all text is captured accurately." \
                                “ If the info looks from a table, add markdown tags for this part of info.“ \
                                    ” No summary and interpretation is needed."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
        )
        return response.choices[0].message['content']
    except Exception as e:
        print(f"\nError extracting text from image {image_path}: {e}")
        return ""
    


if __name__ == '__main__':

    pdf_path = "/home/lixc/Documents/dl/document_ai_agents/data/XLCL_Rating Package_8.4.2008_P.pdf"  # Replace with your PDF file
    images = convert_pdf_to_images(pdf_path, output_dir="/home/lixc/Documents/dl/document_ai_agents/data/images")

    if images:
        print(f"Converted {len(images)} pages to images.")
    
        extracted_text = query_llm_with_images(images)
    
        with open("/home/lixc/Documents/dl/document_ai_agents/data/output.md", "w", encoding="utf-8") as md_file:
            md_file.write(extracted_text)
        print("\nMarkdown Conversion Complete! Check `output.md`.")
    else:
        print("No images found in the PDF.")