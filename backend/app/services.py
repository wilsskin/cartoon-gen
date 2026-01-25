import os
import base64
from io import BytesIO
from typing import Optional
from google import genai
from PIL import Image

_client: Optional[genai.Client] = None


def _get_gemini_client() -> genai.Client:
    """
    Lazily initialize the Gemini client.

    The FastAPI app is responsible for loading environment variables once at
    process startup (see backend/app/main.py). This module relies purely on
    os.environ and must never call load_dotenv() to avoid nondeterminism.
    """
    global _client
    if _client is not None:
        return _client

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Never include the key value in errors/logs.
        raise RuntimeError("GEMINI_API_KEY is not configured")

    _client = genai.Client(api_key=api_key)
    return _client


def generate_satire_image(prompt: str) -> Optional[str]:
    """
    Generates an image using the Gemini 2.5 Flash Image API and returns a Base64 data URL.

    Args:
        prompt: The descriptive prompt for the image.

    Returns:
        A data URL string (e.g., "data:image/png;base64,...") or None if generation failed.
    """
    client = _get_gemini_client()
    
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
        # Do not print stack traces or secrets. Let the caller decide how to surface errors.
        return None
