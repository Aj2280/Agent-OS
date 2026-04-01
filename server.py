import os
import json
import base64
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
from agent_core import MultiModelAgent, PROVIDER_CONFIG
import uvicorn
import traceback

app = FastAPI(title="Agent OS", version="3.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.join(BASE_DIR, "workspace")
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(WORKSPACE_DIR, exist_ok=True)

agent = MultiModelAgent()

class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None

class ConfigUpdate(BaseModel):
    api_key: Optional[str] = None
    system_prompt: Optional[str] = None
    provider: Optional[str] = None

class ProviderKeyUpdate(BaseModel):
    provider: str
    api_key: str

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        if request.model:
            agent.model = request.model

        agent.tool_logs = []
        old_cwd = os.getcwd()
        os.chdir(WORKSPACE_DIR)

        response = agent.chat(request.message)

        os.chdir(old_cwd)

        # Detect created HTML files
        created_files = []
        for log in agent.tool_logs:
            if log.get("name") == "write_file" and log.get("status") == "success":
                filename = log.get("args", {}).get("filename", "")
                if filename:
                    created_files.append(filename)

        preview_file = None
        for f in created_files:
            if f.endswith(".html"):
                preview_file = f
                break

        return {
            "response": response,
            "logs": agent.tool_logs,
            "model": agent.model,
            "created_files": created_files,
            "preview_file": preview_file
        }
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e), "logs": agent.tool_logs})

@app.post("/reset")
async def reset():
    agent.reset()
    return {"status": "ok"}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file or photo to workspace."""
    try:
        filename = file.filename or "uploaded_file"
        # Sanitize filename
        filename = filename.replace("..", "").replace("/", "_")
        filepath = os.path.join(WORKSPACE_DIR, filename)
        content = await file.read()
        with open(filepath, 'wb') as f:
            f.write(content)
        size = len(content)
        return {"status": "ok", "filename": filename, "size": size}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/upload-base64")
async def upload_base64(data: dict):
    """Upload a base64 image (from camera capture)."""
    try:
        b64_data = data.get("image", "")
        filename = data.get("filename", "camera_capture.png")
        if "," in b64_data:
            b64_data = b64_data.split(",")[1]
        img_bytes = base64.b64decode(b64_data)
        filepath = os.path.join(WORKSPACE_DIR, filename)
        with open(filepath, 'wb') as f:
            f.write(img_bytes)
        return {"status": "ok", "filename": filename, "size": len(img_bytes)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/set-provider-key")
async def set_provider_key(data: ProviderKeyUpdate):
    """Save an API key for a specific provider."""
    provider = data.provider
    api_key = data.api_key.strip()

    if provider not in PROVIDER_CONFIG:
        return JSONResponse(status_code=400, content={"error": f"Unknown provider: {provider}"})

    # Save to agent memory
    agent.api_keys[provider] = api_key

    # Persist to .env
    env_key = PROVIDER_CONFIG[provider].get("env_key")
    if env_key:
        env_path = os.path.join(BASE_DIR, ".env")
        try:
            lines = []
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    lines = f.readlines()
            new_lines = []
            found = False
            for line in lines:
                if line.startswith(f"{env_key}="):
                    new_lines.append(f"{env_key}={api_key}\n")
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f"{env_key}={api_key}\n")
            with open(env_path, 'w') as f:
                f.writelines(new_lines)
        except Exception as e:
            return {"status": "ok", "message": f"Key set in memory, but .env save failed: {e}"}

    return {"status": "ok", "message": f"{PROVIDER_CONFIG[provider]['name']} API key saved!"}

@app.post("/update-config")
async def update_config(config: ConfigUpdate):
    messages = []
    if config.system_prompt is not None:
        if config.system_prompt.strip():
            agent.history[0]["content"] = config.system_prompt
            messages.append("System prompt updated.")
        else:
            from agent_core import SYSTEM_PROMPT
            agent.history[0]["content"] = SYSTEM_PROMPT
            messages.append("System prompt reset to default.")
    return {"status": "ok", "message": " | ".join(messages) if messages else "No changes."}

@app.get("/providers")
async def get_providers():
    """Return all providers, their models, and key status."""
    result = {}
    for pid, pconfig in PROVIDER_CONFIG.items():
        result[pid] = {
            "name": pconfig["name"],
            "models": pconfig["models"],
            "prefix": pconfig.get("prefix", ""),
            "has_key": pid in agent.api_keys and bool(agent.api_keys[pid]),
            "needs_key": pconfig.get("env_key") is not None,
        }
    # Add custom models
    result["_custom_models"] = agent.custom_models
    return result

@app.post("/add-custom-model")
async def add_custom_model(data: dict):
    """Add a custom model to any provider."""
    model_id = data.get("model_id", "").strip()
    model_name = data.get("model_name", "").strip() or model_id
    provider = data.get("provider", "openrouter")

    if not model_id:
        return JSONResponse(status_code=400, content={"error": "Model ID required"})

    agent.custom_models.append({
        "id": model_id,
        "name": model_name,
        "provider": provider
    })
    return {"status": "ok", "message": f"Custom model '{model_name}' added!"}

@app.get("/preview/{filename:path}")
async def preview_file(filename: str):
    filepath = os.path.join(WORKSPACE_DIR, filename)
    if os.path.exists(filepath) and os.path.isfile(filepath):
        return FileResponse(filepath)
    return JSONResponse(status_code=404, content={"error": "File not found"})

@app.get("/workspace-files")
async def list_workspace():
    files = []
    for item in sorted(os.listdir(WORKSPACE_DIR)):
        path = os.path.join(WORKSPACE_DIR, item)
        is_dir = os.path.isdir(path)
        size = os.path.getsize(path) if not is_dir else 0
        files.append({
            "name": item, "is_dir": is_dir,
            "size": size, "ext": os.path.splitext(item)[1] if not is_dir else ""
        })
    return {"files": files}

@app.get("/workspace-file/{filename:path}")
async def read_workspace_file(filename: str):
    filepath = os.path.join(WORKSPACE_DIR, filename)
    if os.path.exists(filepath) and os.path.isfile(filepath):
        with open(filepath, 'r') as f:
            return {"filename": filename, "content": f.read()}
    return JSONResponse(status_code=404, content={"error": "File not found"})

@app.get("/config")
async def get_config():
    return {
        "model": agent.model,
        "api_keys": {pid: bool(agent.api_keys.get(pid)) for pid in PROVIDER_CONFIG},
        "history_length": len(agent.history)
    }

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    print("🚀 Agent OS v3.0 starting on http://localhost:8000")
    print(f"📁 Workspace: {WORKSPACE_DIR}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
