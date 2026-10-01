# 匯入設定所需套件
import os
from pathlib import Path

from dotenv import load_dotenv

# 載入本機環境變數
load_dotenv(Path(__file__).resolve().parent / ".env")

# 讀取 MySQL 連線設定
DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = int(os.getenv("DB_PORT") or "3306")
DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# 讀取 AWS 區域、S3 儲存桶與 CloudFront 網域
AWS_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-northeast-1"
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "").strip()
CLOUDFRONT_DOMAIN = os.getenv("CLOUDFRONT_DOMAIN", "").strip().rstrip("/")

# 設定允許的圖片類型與 5 MB 大小上限
ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_IMAGE_SIZE = 5 * 1024 * 1024
