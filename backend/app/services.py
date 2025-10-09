import os
import base64
from io import BytesIO
from dotenv import load_dotenv
from google import genai
from PIL import Image

# Load environment variables from .env file
load_dotenv()

# --- Gemini API Configuration ---
try:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in .env file.")

    # Initialize the Gemini client with the API key
    client = genai.Client(api_key=api_key)

except (KeyError, ValueError) as e:
    raise RuntimeError(f"Configuration error: {e}") from e


def generate_satire_image(prompt: str) -> str | None:
    """
    Generates an image using the Gemini 2.5 Flash Image API and returns a Base64 data URL.

    Args:
        prompt: The descriptive prompt for the image.

    Returns:
        A data URL string (e.g., "data:image/png;base64,...") or None if generation failed.
    """
    try:
        # Generate image using Gemini 2.5 Flash Image model
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt
        )

        # Extract image data from the response
        image_parts = [
            part.inline_data.data
            for part in response.candidates[0].content.parts
            if part.inline_data
        ]

        if not image_parts:
            print("Image generation succeeded but returned no image data.")
            return None

        # Get the first image (there should only be one for text-to-image)
        image_bytes = image_parts[0]

        # Encode the bytes into a Base64 string
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        # Format as a data URL, which can be used directly in an <img> src attribute
        return f"data:image/png;base64,{base64_image}"

    except Exception as e:
        print(f"An error occurred during image generation: {e}")
        import traceback
        traceback.print_exc()
        return None
