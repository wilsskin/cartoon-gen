import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import our image generation service
from . import services

# Define the base directory of the backend
BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()

# --- Middleware ---
# Allow frontend running on localhost:5173 to make requests
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Static File Serving ---
# This serves your pre-generated images from the /static/images directory
static_files_path = BASE_DIR.parent / "static"
app.mount("/static", StaticFiles(directory=static_files_path), name="static")

# --- Pydantic Models for Request Body Validation ---
class ImageRequest(BaseModel):
    basePrompt: str
    style: str

# --- API Endpoints ---
@app.get("/api/news")
def get_news():
    """
    Reads and returns the contents of the news.json file.
    """
    data_file_path = BASE_DIR.parent / "data" / "news.json"
    try:
        with open(data_file_path, "r") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="News data file not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

@app.post("/api/generate-image")
async def generate_image(request: ImageRequest):
    """
    Receives a base prompt and a style, constructs a final prompt,
    and calls the image generation service.
    """
    style_modifiers = {
        "Funnier": "in a highly exaggerated, funny, satirical cartoon style, vibrant colors",
        "More Absurd": "in a surreal, abstract, and absurd art style, dreamlike, bizarre",
        "Labubu": "in the whimsical Labubu toy art style — all human figures reimagined as Labubu-like characters with big heads, small bodies, and sharp teeth; expressive pastel colors, vinyl toy aesthetic, cute but mischievous mood, maintaining the original political scene composition; cinematic lighting, soft textures, collectible figure look",
    }

    modifier = style_modifiers.get(request.style, "")
    final_prompt = f"{request.basePrompt}, {modifier}"

    print(f"Generating image with prompt: {final_prompt}")

    # Call the image generation service
    image_url = services.generate_satire_image(final_prompt)

    if image_url:
        # The URL is now a Base64 data URL
        return {"imageUrl": image_url}
    else:
        raise HTTPException(status_code=500, detail="Failed to generate image.")

@app.get("/")
def read_root():
    return {"status": "Backend is running"}
