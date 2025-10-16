from google import genai
from dotenv import load_dotenv, find_dotenv
import os 


_ = load_dotenv(find_dotenv(".env"
                            , raise_error_if_not_found=True
                             ))


api_key = os.getenv('GOOGLE_API_KEY')
if api_key is None:
    raise ValueError("API key not found. Please set the GOOGLE_API_KEY environment variable.")

gemini_api_key = api_key
print("API key successfully loaded.")



try:
    client = genai.Client(api_key=gemini_api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash", contents="Explain how AI works"
    )
    print(response.text)
except Exception as e:
    print(f"An error occurred: {e}")

    