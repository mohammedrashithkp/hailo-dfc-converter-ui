import os
import shutil
import zipfile
import subprocess
import asyncio
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Hailo ONNX to HEF Converter")

WORKSPACE_DIR = Path("/home/mrkp/Downloads/onnx_to_hef")
DATASET_DIR = WORKSPACE_DIR / "dataset"
ONNX_FILE_PATH = WORKSPACE_DIR / "best.onnx"
HEF_FILE_PATH = WORKSPACE_DIR / "best.hef"
SCRIPT_PATH = WORKSPACE_DIR / "run_conversion.sh"

# Ensure directories exist
os.makedirs(DATASET_DIR, exist_ok=True)

# Mount static files for CSS/JS
app.mount("/static", StaticFiles(directory=str(WORKSPACE_DIR / "static")), name="static")

# Global reference to the current compilation process so we can stream logs
compilation_process = None

@app.get("/")
async def serve_ui():
    """Serve the main index.html file."""
    return FileResponse(str(WORKSPACE_DIR / "static" / "index.html"))

@app.post("/upload_model")
async def upload_model(file: UploadFile = File(...)):
    """Upload and save the ONNX model."""
    try:
        # Save the uploaded file to the expected ONNX file path
        with open(ONNX_FILE_PATH, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"status": "success", "message": f"Model {file.filename} uploaded successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/upload_dataset")
async def upload_dataset(file: UploadFile = File(...)):
    """Upload and extract a dataset ZIP file."""
    if not file.filename.endswith(".zip"):
        return {"status": "error", "message": "Only .zip files are supported for dataset uploads."}
    
    zip_path = WORKSPACE_DIR / file.filename
    try:
        # Save zip
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Clear previous dataset
        if DATASET_DIR.exists():
            shutil.rmtree(DATASET_DIR)
        os.makedirs(DATASET_DIR, exist_ok=True)
        
        # Extract zip
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(DATASET_DIR)
            
        os.remove(zip_path) # cleanup zip
        return {"status": "success", "message": "Dataset uploaded and extracted successfully."}
    except Exception as e:
        if zip_path.exists():
            os.remove(zip_path)
        return {"status": "error", "message": f"Failed to extract ZIP: {str(e)}"}

@app.post("/compile")
async def trigger_compile(hw_arch: str = Form(...), input_size: str = Form(...)):
    """Triggers the Hailo conversion bash script."""
    global compilation_process
    
    if compilation_process and compilation_process.returncode is None:
        return {"status": "error", "message": "Compilation is already running!"}
    
    # Parse input size (e.g. 640x640)
    try:
        w, h = input_size.lower().split('x')
    except:
        w, h = "640", "640"
        
    # Check if files exist
    if not ONNX_FILE_PATH.exists():
        return {"status": "error", "message": "Please upload an ONNX model first."}
        
    # Setup environment variables for the bash script
    env = os.environ.copy()
    env["HW_ARCH"] = hw_arch
    env["INPUT_W"] = w
    env["INPUT_H"] = h
    env["ONNX_FILE"] = "best.onnx"
    env["CALIB_DATA"] = "/workspace/dataset"
    
    # We remove the previous HEF to prevent returning an old one
    if HEF_FILE_PATH.exists():
        os.remove(HEF_FILE_PATH)
        
    # Start the bash script in a subprocess
    try:
        compilation_process = subprocess.Popen(
            [str(SCRIPT_PATH)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1, # Line buffered
            env=env,
            cwd=str(WORKSPACE_DIR)
        )
        return {"status": "success", "message": "Compilation started!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    """Streams the docker compilation logs to the frontend in real-time."""
    await websocket.accept()
    global compilation_process
    
    try:
        while True:
            if compilation_process is None or compilation_process.poll() is not None:
                # If process isn't running or finished, wait briefly and check again
                if compilation_process and compilation_process.poll() is not None:
                    # It just finished
                    if compilation_process.returncode == 0:
                        await websocket.send_text("\\n[SYSTEM] Compilation completed successfully.\\n")
                        # Tell client to show download button
                        await websocket.send_text("COMPILATION_SUCCESS")
                    else:
                        await websocket.send_text(f"\\n[SYSTEM] Compilation failed with code {compilation_process.returncode}.\\n")
                        await websocket.send_text("COMPILATION_ERROR")
                    compilation_process = None
                await asyncio.sleep(1)
                continue
                
            # Read line from subprocess output
            line = compilation_process.stdout.readline()
            if line:
                await websocket.send_text(line)
            else:
                await asyncio.sleep(0.1)
                
    except WebSocketDisconnect:
        print("Client disconnected from logs.")
        
@app.get("/download")
async def download_hef():
    """Download the final compiled HEF file."""
    if HEF_FILE_PATH.exists():
        return FileResponse(
            path=str(HEF_FILE_PATH), 
            filename="best.hef",
            media_type="application/octet-stream"
        )
    return {"status": "error", "message": "HEF file not found. Did the compilation fail?"}
