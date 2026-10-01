# 匯入 AWS 套件、UUID 與儲存設定
from functools import lru_cache
from urllib.parse import quote
from uuid import uuid4

import boto3
from fastapi import UploadFile

import config

IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

# 建立使用預設憑證來源的 S3 Client
@lru_cache(maxsize=1)
def get_s3_client():
    # 第一次操作 S3 時才取得憑證，避免啟動或純文字留言依賴 AWS 連線。
    return boto3.client("s3", region_name=config.AWS_REGION)


def _require_bucket() -> str:
    if not config.S3_BUCKET_NAME:
        raise ValueError("S3_BUCKET_NAME is required")
    return config.S3_BUCKET_NAME

# upload_image：以 UUID 產生檔名、上傳圖片並回傳 Object Key
def upload_image(file: UploadFile) -> str:
    bucket = _require_bucket()
    if file.content_type not in config.ALLOWED_IMAGE_TYPES:
        raise ValueError("Invalid image type")
    image_key = f"posts/{uuid4()}{IMAGE_EXTENSIONS[file.content_type]}"
    # 寫入前確認 CDN 設定可用，避免成功寫入留言後才無法建立圖片網址。
    build_image_url(image_key)
    file.file.seek(0)
    get_s3_client().upload_fileobj(
        file.file,
        bucket,
        image_key,
        ExtraArgs={"ContentType": file.content_type},
    )
    return image_key

# delete_image：刪除資料庫寫入失敗時已上傳的圖片
def delete_image(image_key: str) -> None:
    bucket = _require_bucket()
    get_s3_client().delete_object(Bucket=bucket, Key=image_key)

# build_image_url：組合 CloudFront 圖片網址，無圖片時回傳 None
def build_image_url(image_key: str | None) -> str | None:
    if image_key is None:
        return None
    domain = config.CLOUDFRONT_DOMAIN
    if not domain:
        raise ValueError("CLOUDFRONT_DOMAIN is required")
    if "://" not in domain:
        domain = f"https://{domain}"
    return f"{domain.rstrip('/')}/{quote(image_key, safe='/')}"
