from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

# Serve static frontend files
frontend_path = os.path.join(os.path.dirname(__file__), '../../frontend/.next/static')
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_path = os.path.join(os.path.dirname(__file__), '../../frontend/.next/server/app/index.html')
    with open(index_path, "r") as f:
        return f.read()

@app.get("/api/ping")
def ping():
    return {"message": "pong"}
