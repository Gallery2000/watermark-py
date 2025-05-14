from fastapi import FastAPI, File, UploadFile
from fastapi.responses import StreamingResponse
from PIL import Image
import io
import os
from contextlib import asynccontextmanager

# Import the function from your watermark_processor.py file
from watermark_processor import apply_watermark_to_image_object, WHITE_WATERMARK_IMAGE_PATH, BLACK_WATERMARK_IMAGE_PATH

# Define the upload directory relative to main.py
_SCRIPT_DIR_MAIN = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIRECTORY = os.path.join(_SCRIPT_DIR_MAIN, "uploaded_files")

# --- Lifespan Event Handler ---
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # Code to run on startup
    print("INFO:     Application startup...")
    # Check for watermark files
    if not os.path.exists(WHITE_WATERMARK_IMAGE_PATH):
        print(f"CRITICAL ERROR: White watermark image not found at {WHITE_WATERMARK_IMAGE_PATH}")
    else:
        print(f"White watermark image found: {WHITE_WATERMARK_IMAGE_PATH}")
    if not os.path.exists(BLACK_WATERMARK_IMAGE_PATH):
        print(f"CRITICAL ERROR: Black watermark image not found at {BLACK_WATERMARK_IMAGE_PATH}")
    else:
        print(f"Black watermark image found: {BLACK_WATERMARK_IMAGE_PATH}")
    
    # Create the upload directory if it doesn't exist
    os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
    print(f"INFO:     Upload directory is {UPLOAD_DIRECTORY}")
    
    yield # This is where the application runs
    
    # Code to run on shutdown (if any)
    print("INFO:     Application shutdown...")

app = FastAPI(lifespan=lifespan) # Pass the lifespan manager to the app

# The @app.on_event("startup") for startup_create_upload_dir is no longer needed as it's in lifespan

@app.post("/watermark-image/")
async def create_watermarked_image(file: UploadFile = File(...)):
    """
    Upload an image, apply a watermark, and return the watermarked image.
    """
    try:
        contents = await file.read()
        input_image = Image.open(io.BytesIO(contents))
    except Exception as e:
        return {"error": f"Could not read or open image file: {e}"}
    finally:
        if file:
            await file.close()

    if input_image is None:
        return {"error": "Image could not be processed from uploaded file."}

    try:
        watermarked_image_pil = apply_watermark_to_image_object(input_image)
        
        img_byte_arr = io.BytesIO()
        watermarked_image_pil.save(img_byte_arr, format='JPEG', quality=95) 
        img_byte_arr.seek(0)

        return StreamingResponse(img_byte_arr, media_type="image/jpeg")

    except FileNotFoundError as e:
        print(f"ERROR during processing: Watermark file not found - {e}")
        return {"error": f"Watermark resource file not found during processing: {e}"}
    except Exception as e:
        print(f"ERROR during processing: {e}")
        return {"error": f"An error occurred while watermarking the image: {e}"}

@app.post("/upload-file/")
async def create_upload_file(file: UploadFile = File(...)):
    """
    Upload a generic file and save it to the server.
    """
    try:
        # Ensure the upload directory exists (it should from lifespan, but as a safeguard here too)
        os.makedirs(UPLOAD_DIRECTORY, exist_ok=True) 

        file_location = os.path.join(UPLOAD_DIRECTORY, file.filename)
        
        with open(file_location, "wb+") as file_object:
            file_object.write(await file.read())
            
        return {"info": f"File '{file.filename}' saved at '{file_location}'"}
    except Exception as e:
        print(f"ERROR during file upload: {e}")
        return {"error": f"Could not upload file: {e}"}
    finally:
        if file:
            await file.close()

# To run this application:
# 1. Save this file as main.py in the same directory as watermark_processor.py.
