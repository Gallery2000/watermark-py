from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image
import io
import os
import shutil
from typing import List
from contextlib import asynccontextmanager
import json
import time
# 引入腾讯云COS SDK
try:
    from qcloud_cos import CosConfig
    from qcloud_cos import CosS3Client
    COS_SDK_INSTALLED = True
except ImportError:
    COS_SDK_INSTALLED = False
    print("WARNING: qcloud_cos SDK not installed. Tencent Cloud upload will be disabled.")
    print("To enable Tencent Cloud COS uploads, run: pip install -U cos-python-sdk-v5")

# Import the function from your watermark_processor.py file
from watermark_processor import apply_watermark_to_image_object, WHITE_WATERMARK_IMAGE_PATH, BLACK_WATERMARK_IMAGE_PATH

# Define the upload directory relative to main.py
_SCRIPT_DIR_MAIN = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIRECTORY = os.path.join(_SCRIPT_DIR_MAIN, "uploaded_files")
TEMPLATES_DIR = os.path.join(_SCRIPT_DIR_MAIN, "templates")

# 腾讯云COS配置
# 以下配置信息需要替换为你自己的腾讯云账户信息
TENCENT_COS_CONFIG = {
    'enabled': True,  # 设置为False可以禁用腾讯云上传
    'secret_id': 'your_secret_id',         # 替换为你的 SecretId
    'secret_key': 'your_secret_key',       # 替换为你的 SecretKey
    'region': 'ap-guangzhou',              # 替换为你的地区，例如：ap-guangzhou
    'bucket': 'your-bucket-name',          # 替换为你的 bucket 名称
    'base_url': 'https://your-bucket-name.cos.ap-guangzhou.myqcloud.com/', # 替换为你的存储桶访问域名
    'upload_folder': 'uploads/'            # COS中存储文件的文件夹路径
}

# CosS3Client实例
cos_client = None

# --- Lifespan Event Handler ---
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # Code to run on startup
    print("INFO:     Application startup...")
    
    # 初始化腾讯云COS客户端
    global cos_client
    if COS_SDK_INSTALLED and TENCENT_COS_CONFIG['enabled']:
        try:
            cos_config = CosConfig(
                Region=TENCENT_COS_CONFIG['region'],
                SecretId=TENCENT_COS_CONFIG['secret_id'],
                SecretKey=TENCENT_COS_CONFIG['secret_key']
            )
            cos_client = CosS3Client(cos_config)
            print("INFO:     Tencent Cloud COS client initialized successfully")
        except Exception as e:
            print(f"ERROR:    Failed to initialize Tencent Cloud COS client: {e}")
            cos_client = None
    
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
    
    # Create templates directory if it doesn't exist
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    
    # Create an HTML template for upload
    create_upload_template()
    
    yield # This is where the application runs
    
    # Code to run on shutdown (if any)
    print("INFO:     Application shutdown...")

def create_upload_template():
    """Create a simple HTML template for file uploads if it doesn't exist"""
    upload_template_path = os.path.join(TEMPLATES_DIR, "upload.html")
    
    if not os.path.exists(upload_template_path):
        with open(upload_template_path, "w") as f:
            f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>File Upload Service</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        .container {
            border: 1px solid #ddd;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        h1, h2 {
            color: #333;
        }
        input[type="file"] {
            margin: 10px 0;
        }
        button {
            background-color: #4CAF50;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        button:hover {
            background-color: #45a049;
        }
        .file-list {
            margin-top: 20px;
        }
        .file-item {
            padding: 8px;
            border-bottom: 1px solid #eee;
        }
        .file-item:hover {
            background-color: #f9f9f9;
        }
        a {
            color: #0066cc;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <h1>File Upload Service</h1>
    
    <div class="container">
        <h2>Upload a Single File</h2>
        <form action="/upload-file/" method="post" enctype="multipart/form-data">
            <input type="file" name="file" />
            <button type="submit">Upload</button>
        </form>
    </div>
    
    <div class="container">
        <h2>Upload Multiple Files</h2>
        <form action="/upload-files/" method="post" enctype="multipart/form-data">
            <input type="file" name="files" multiple />
            <button type="submit">Upload All</button>
        </form>
    </div>
    
    <div class="container">
        <h2>Upload an Image and Add Watermark</h2>
        <form action="/watermark-image/" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept="image/*" />
            <button type="submit">Watermark Image</button>
        </form>
    </div>
    
    <div class="container file-list">
        <h2>Uploaded Files</h2>
        <div id="files">
            <p>Loading file list...</p>
            <script>
                // Simple JavaScript to load file list
                fetch('/list-files/')
                    .then(response => response.json())
                    .then(data => {
                        const filesDiv = document.getElementById('files');
                        filesDiv.innerHTML = '';
                        
                        if (data.files.length === 0) {
                            filesDiv.innerHTML = '<p>No files uploaded yet.</p>';
                            return;
                        }
                        
                        data.files.forEach(file => {
                            const fileItem = document.createElement('div');
                            fileItem.className = 'file-item';
                            fileItem.innerHTML = `<a href="/files/${file}" target="_blank">${file}</a>`;
                            filesDiv.appendChild(fileItem);
                        });
                    })
                    .catch(error => {
                        console.error('Error fetching file list:', error);
                        document.getElementById('files').innerHTML = '<p>Error loading file list.</p>';
                    });
            </script>
        </div>
    </div>
</body>
</html>
            """)
        print(f"Created upload template at {upload_template_path}")

app = FastAPI(lifespan=lifespan) # Pass the lifespan manager to the app

# Set up Jinja2 templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Route for homepage with upload form
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

# The existing watermark-image endpoint
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

        return StreamingResponse(img_byte_arr, media_type="image/jpeg", 
                                headers={
                                    "Content-Disposition": f"attachment; filename=watermarked_{file.filename}"
                                })

    except FileNotFoundError as e:
        print(f"ERROR during processing: Watermark file not found - {e}")
        return {"error": f"Watermark resource file not found during processing: {e}"}
    except Exception as e:
        print(f"ERROR during processing: {e}")
        return {"error": f"An error occurred while watermarking the image: {e}"}

def upload_to_tencent_cos(file_content, file_name):
    """上传文件到腾讯云COS"""
    if not cos_client:
        return None
    
    try:
        # 构建COS中的文件路径
        cos_key = f"{TENCENT_COS_CONFIG['upload_folder']}{file_name}"
        
        # 执行上传
        response = cos_client.put_object(
            Bucket=TENCENT_COS_CONFIG['bucket'],
            Body=file_content,
            Key=cos_key,
            EnableMD5=False
        )
        
        # 构建访问URL
        file_url = f"{TENCENT_COS_CONFIG['base_url']}{cos_key}"
        
        return {
            "url": file_url,
            "key": cos_key,
            "etag": response.get('ETag', ''),
            "status": "success"
        }
    except Exception as e:
        print(f"ERROR: Failed to upload to Tencent Cloud COS: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

# The existing upload-file endpoint (single file)
@app.post("/upload-file/")
async def create_upload_file(file: UploadFile = File(...)):
    """
    Upload a generic file and save it to the server and Tencent Cloud COS.
    """
    try:
        # Ensure the upload directory exists
        os.makedirs(UPLOAD_DIRECTORY, exist_ok=True) 

        # 读取文件内容
        file_content = await file.read()
        
        # 1. 保存到本地
        file_location = os.path.join(UPLOAD_DIRECTORY, file.filename)
        with open(file_location, "wb+") as file_object:
            file_object.write(file_content)
        
        # 2. 上传到腾讯云COS
        cos_result = None
        if COS_SDK_INSTALLED and TENCENT_COS_CONFIG['enabled'] and cos_client:
            # 创建内存文件对象用于上传
            cos_result = upload_to_tencent_cos(file_content, file.filename)
            
        # 构建返回结果
        result = {
            "info": f"File '{file.filename}' uploaded successfully", 
            "filename": file.filename,
            "local_path": file_location
        }
        
        # 如果上传到了腾讯云，添加云存储信息
        if cos_result:
            result["tencent_cos"] = cos_result
            
        return result
    except Exception as e:
        print(f"ERROR during file upload: {e}")
        return {"error": f"Could not upload file: {e}"}
    finally:
        if file:
            await file.close()

# New endpoint for multiple file uploads
@app.post("/upload-files/")
async def create_upload_files(files: List[UploadFile] = File(...)):
    """
    Upload multiple files at once and save them to the server and Tencent Cloud COS.
    """
    upload_results = []
    
    for file in files:
        try:
            # Ensure the upload directory exists
            os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
            
            # 读取文件内容
            file_content = await file.read()
            
            # 1. 保存到本地
            file_location = os.path.join(UPLOAD_DIRECTORY, file.filename)
            with open(file_location, "wb+") as file_object:
                file_object.write(file_content)
            
            # 准备结果对象
            result = {
                "filename": file.filename,
                "status": "success", 
                "local_path": file_location
            }
            
            # 2. 上传到腾讯云COS
            if COS_SDK_INSTALLED and TENCENT_COS_CONFIG['enabled'] and cos_client:
                cos_result = upload_to_tencent_cos(file_content, file.filename)
                if cos_result:
                    result["tencent_cos"] = cos_result
            
            upload_results.append(result)
        except Exception as e:
            print(f"Error uploading file {file.filename}: {e}")
            upload_results.append({
                "filename": file.filename,
                "status": "error",
                "error": str(e)
            })
        finally:
            if file:
                await file.close()
    
    return {"uploads": upload_results}

# New endpoint to list uploaded files
@app.get("/list-files/")
async def list_files():
    """
    List all files in the upload directory.
    """
    try:
        files = os.listdir(UPLOAD_DIRECTORY)
        # Filter out directories, only return files
        files = [f for f in files if os.path.isfile(os.path.join(UPLOAD_DIRECTORY, f))]
        return {"files": files}
    except Exception as e:
        print(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing files: {e}")

# New endpoint to retrieve/download a specific file
@app.get("/files/{filename}")
async def get_file(filename: str):
    """
    Get a specific file from the upload directory.
    """
    file_path = os.path.join(UPLOAD_DIRECTORY, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=400, detail="Path is not a file")
    
    return FileResponse(path=file_path, filename=filename)

# To run this application:
# 1. Save this file as main.py in the same directory as watermark_processor.py.
# 2. Install dependencies: pip install fastapi uvicorn[standard] Pillow
# 3. Run the server: uvicorn main:app --reload
# 4. Open web browser and visit: http://127.0.0.1:8000/
