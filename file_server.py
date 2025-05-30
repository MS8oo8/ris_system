from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import os

app = FastAPI()

# Ścieżka do folderu z obrazami
IMAGE_DIR = "ris_patterns"

@app.get("/{image_name}")
def get_image(image_name: str):
    # Zabezpieczenie przed ../ w nazwie pliku
    safe_name = os.path.basename(image_name)
    image_path = os.path.join(IMAGE_DIR, safe_name)

    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(image_path)

# uvicorn file_server:app --reload --port 8001