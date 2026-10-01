# 匯入 FastAPI、設定與資料存取模組
import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

import config
import database
import s3

logger = logging.getLogger(__name__)

# 建立 FastAPI 應用程式並設定模板與靜態檔案
BASE_DIR = Path(__file__).resolve().parent
app = FastAPI()
# 使用專案目前的目錄名稱 tmeplates。
templates = Jinja2Templates(directory=str(BASE_DIR / "tmeplates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# 統一錯誤回應：輸入錯誤 400、圖片過大 413、服務異常 500
@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"detail": "Invalid request"})


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def handle_service_error(request: Request, exc: Exception):
    logger.error("Service error", exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# validate_content：驗證留言文字不可為空白
def validate_content(content: str) -> str:
    content = content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Content cannot be empty")
    return content

# validate_image：驗證圖片 MIME 類型與大小
def validate_image(image: UploadFile) -> None:
    # config.py 應提供 ALLOWED_IMAGE_TYPES 與 MAX_IMAGE_SIZE（bytes）。
    if image.content_type not in config.ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid image type")

    # 量測實際檔案大小，不依賴用戶端提供的 Content-Length。
    image.file.seek(0, 2)
    size = image.file.tell()
    image.file.seek(0)
    if size > config.MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="Image exceeds size limit")


def serialize_post(post: dict) -> dict:
    return {
        "id": post["id"],
        "content": post["content"],
        "image_url": s3.build_image_url(post["image_key"]),
        "created_at": post["created_at"],
    }

# GET /：回傳一頁式留言板
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

# GET /api/posts：取得留言並轉換圖片網址，回傳 posts 列表
@app.get("/api/posts")
def list_posts():
    return {"posts": [serialize_post(post) for post in database.get_posts()]}

# POST /api/posts：驗證文字與選填圖片、先上傳再寫入，失敗清理圖片，成功回傳 201 與留言資料
@app.post("/api/posts", status_code=201)
def create_post(content: str = Form(...), image: UploadFile | None = File(None)):
    # 同步路由由 FastAPI 在執行緒池執行，避免 MySQL / S3 阻塞事件迴圈。
    content = validate_content(content)
    image_key = None
    if image is not None:
        validate_image(image)
        image_key = s3.upload_image(image)

    try:
        post = database.create_post(content, image_key)
    except Exception:
        if image_key is not None:
            try:
                s3.delete_image(image_key)
            except Exception:
                logger.exception("Failed to clean up uploaded image %s", image_key)
        raise

    # 寫入成功後的回應轉換失敗，不應刪除資料庫已引用的圖片。
    return {"success": True, "post": serialize_post(post)}
