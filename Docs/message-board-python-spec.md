# 圖文留言板 Python 後端規格文件

## 1. 專案目標

建立一個以 **FastAPI** 驅動的一頁式圖文留言板。

使用者不需要登入，可以：

1.  輸入文字留言。
2.  選擇一張圖片。
3.  送出留言。
4.  瀏覽所有留言。
5.  圖片儲存在 AWS S3。
6.  留言資料儲存在 AWS RDS MySQL。
7.  圖片透過 AWS CloudFront CDN 提供。
8.  FastAPI 使用 Docker 部署至 AWS EC2。

### 整體基礎架構

``` text
Browser
   │
   │ HTTPS
   ▼
Cloudflare DNS
   │
   ▼
AWS EC2
┌──────────────────────────┐
│ Docker                   │
│                          │
│ FastAPI                  │
│  ├─ HTML                 │
│  ├─ POST /api/posts      │
│  └─ GET  /api/posts      │
└────────┬─────────┬───────┘
         │         │
         │ SQL     │ boto3
         ▼         ▼
     RDS MySQL    S3
                    │
                    ▼
                CloudFront
                    │
                    ▼
                  Browser
```

------------------------------------------------------------------------

## 2. Python 技術規格

建議使用：

``` text
Python >= 3.12
```

### 主要 Libraries

  Library                    用途
  -------------------------- ---------------------------------
  `fastapi`                  Web Framework / API
  `uvicorn`                  ASGI Server
  `python-multipart`         接收 multipart/form-data 與圖片
  `boto3`                    AWS S3 操作
  `mysql-connector-python`   RDS MySQL 連線
  `python-dotenv`            本機開發載入 `.env`
  `jinja2`                   FastAPI HTML Template

`requirements.txt` 至少包含：

``` text
fastapi
uvicorn[standard]
python-multipart
boto3
mysql-connector-python
python-dotenv
jinja2
```

Production 部署時應固定套件版本，避免 Docker 每次 build 取得不同版本。

------------------------------------------------------------------------

## 3. 專案主要架構

本專案採用簡單模組化架構，不導入較重的 ORM、Repository Pattern 或 Clean
Architecture。

``` text
message-board/
│
├── app/
│   ├── main.py
│   ├── database.py
│   ├── s3.py
│   ├── config.py
│   │
│   ├── templates/
│   │   └── index.html
│   │
│   └── static/
│       ├── css/
│       │   └── style.css
│       └── js/
│           └── main.js
│
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

核心責任：

``` text
main.py
 │
 ├── HTTP Request / Response
 │
 ├── database.py ─────→ RDS MySQL
 │
 └── s3.py ───────────→ AWS S3
                            │
                            ▼
                       CloudFront
```

------------------------------------------------------------------------

## 4. `config.py`

### 目的

集中處理應用程式設定。

不得直接將 AWS Access Key、AWS Secret Key、Database Password 寫死在
Python 原始碼。

需要的設定：

``` text
DB_HOST
DB_PORT
DB_NAME
DB_USER
DB_PASSWORD

AWS_REGION
S3_BUCKET_NAME

CLOUDFRONT_DOMAIN
```

本機 `.env` 範例：

``` env
DB_HOST=...
DB_PORT=3306
DB_NAME=message_board
DB_USER=...
DB_PASSWORD=...

AWS_REGION=ap-northeast-1
S3_BUCKET_NAME=...

CLOUDFRONT_DOMAIN=https://xxxxxxxx.cloudfront.net
```

`.env` 不得 commit 至 GitHub。

Production EC2 應優先使用 IAM Role 提供 S3 權限，而不是把 AWS Access Key
存放於 `.env`。

------------------------------------------------------------------------

## 5. `database.py`

### 目的

負責 FastAPI 與 AWS RDS MySQL 之間的資料存取。

``` text
FastAPI
   │
database.py
   │
   ▼
RDS MySQL
```

使用：

``` text
mysql-connector-python
```

最低需要以下 interface：

``` python
def get_connection():
    ...
```

取得 MySQL Connection。

留言操作：

``` python
def create_post(content: str, image_key: str | None):
    ...
```

以及：

``` python
def get_posts():
    ...
```

### `create_post()`

責任：

``` sql
INSERT INTO posts
(content, image_key)
VALUES (...)
```

### `get_posts()`

責任：

``` sql
SELECT
    id,
    content,
    image_key,
    created_at
FROM posts
ORDER BY created_at DESC
```

最新留言顯示於最上方。

------------------------------------------------------------------------

## 6. RDS MySQL 資料模型

資料庫：

``` text
message_board
```

資料表：

``` text
posts
```

### Schema

  Column         Type              規則
  -------------- ----------------- ------------------------------------
  `id`           BIGINT UNSIGNED   PK, AUTO_INCREMENT
  `content`      TEXT              NOT NULL
  `image_key`    VARCHAR(500)      NULL
  `created_at`   DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP

資料庫建議儲存 **S3 Object Key**，而非完整 CloudFront URL。

例如：

``` text
posts/550e8400-e29b.jpg
```

而不是：

``` text
https://abc.cloudfront.net/posts/550e8400-e29b.jpg
```

如此未來更換 CloudFront Distribution Domain 時，不需要更新既有資料。

------------------------------------------------------------------------

## 7. `s3.py`

### 目的

集中處理所有 S3 操作。

``` text
main.py
   │
   │ upload
   ▼
s3.py
   │
   │ boto3
   ▼
AWS S3
```

使用：

``` python
import boto3
```

建立 S3 Client：

``` python
s3_client = boto3.client("s3")
```

主要 interface：

``` python
def upload_image(file) -> str:
    ...
```

輸入為 FastAPI `UploadFile`，輸出為 S3 Object Key。

例如：

``` text
posts/550e8400-e29b-41d4-a716-446655440000.jpg
```

------------------------------------------------------------------------

## 8. S3 Object Key 規則

不得直接使用使用者原始 filename 作為唯一檔名，以避免檔名衝突。

使用：

``` text
UUID + extension
```

例如：

``` text
posts/
    1ad39143-....jpg
    8fe92153-....png
    bce19282-....webp
```

Python 可使用標準函式庫：

``` python
import uuid
```

不需要額外安裝。

------------------------------------------------------------------------

## 9. 圖片驗證

允許的 MIME Type：

``` text
image/jpeg
image/png
image/webp
```

其他格式拒絕。

設定最大圖片大小，例如：

``` text
MAX_IMAGE_SIZE = 5 MB
```

驗證流程：

``` text
UploadFile
    │
    ├── MIME type？
    │       └── 不允許 → 400
    │
    ├── Size <= 5 MB？
    │       └── No → 413
    │
    ▼
Upload S3
```

不得只依賴副檔名進行判斷。

------------------------------------------------------------------------

## 10. CloudFront URL

建立：

``` python
def build_image_url(image_key: str | None) -> str | None:
    ...
```

例如：

``` text
CLOUDFRONT_DOMAIN=https://abc.cloudfront.net
```

Database：

``` text
posts/123.jpg
```

FastAPI Response：

``` text
https://abc.cloudfront.net/posts/123.jpg
```

資料流：

``` text
RDS
 │
 │ image_key
 ▼
FastAPI
 │
 │ CLOUDFRONT_DOMAIN + image_key
 ▼
Browser
 │
 ▼
CloudFront
 │
 ▼
S3
```

------------------------------------------------------------------------

## 11. FastAPI `main.py`

`main.py` 為主要程式入口。

最低需要：

``` python
app = FastAPI()
```

主要 endpoints：

``` text
GET  /
GET  /api/posts
POST /api/posts
```

------------------------------------------------------------------------

## 12. `GET /`

目的為回傳：

``` text
index.html
```

使用 FastAPI `Jinja2Templates`。

使用者開啟網站首頁即可看到留言表單與留言列表。

------------------------------------------------------------------------

## 13. `GET /api/posts`

### 目的

取得留言列表。

Request：

``` http
GET /api/posts
```

Response：

``` json
{
  "posts": [
    {
      "id": 5,
      "content": "測試",
      "image_url": "https://cdn.example.com/posts/xxx.jpg",
      "created_at": "2026-09-30T23:30:00"
    }
  ]
}
```

處理流程：

``` text
Browser
   │
GET /api/posts
   │
   ▼
main.py
   │
get_posts()
   ▼
database.py
   │
   ▼
RDS
   │
   ▼
Post records
   │
build_image_url()
   │
   ▼
JSON
```

------------------------------------------------------------------------

## 14. `POST /api/posts`

使用：

``` text
multipart/form-data
```

Request：

``` text
content = "測試留言"
image   = image.jpg
```

FastAPI interface：

``` python
async def create_post(
    content: str = Form(...),
    image: UploadFile | None = File(None)
):
    ...
```

圖片為 optional。

以下兩種留言都合法：

``` text
文字 + 圖片
文字
```

文字不可為空。

------------------------------------------------------------------------

## 15. 建立留言核心流程

``` text
POST /api/posts
       │
       ▼
FastAPI
       │
       ├── 驗證 content
       │
       └── 是否有 image？
               │
             Yes
               │
               ▼
          驗證圖片
               │
               ▼
          upload_image()
               │
               ▼
              S3
               │
               ▼
           image_key
               │
               ▼
       create_post()
               │
               ▼
              RDS
               │
               ▼
       build_image_url()
               │
               ▼
         JSON Response
```

------------------------------------------------------------------------

## 16. S3 與 Database 寫入順序

規格：

``` text
① 驗證資料
↓
② 上傳 S3
↓
③ 取得 image_key
↓
④ INSERT RDS
↓
⑤ Response
```

若：

``` text
S3 Upload Success
        ↓
RDS INSERT Failed
```

會產生 orphan object。

因此 `s3.py` 應提供：

``` python
def delete_image(image_key: str) -> None:
    ...
```

此 function 僅作為後端 rollback 使用，不提供使用者刪除留言功能。

``` text
upload S3
   ↓
成功
   ↓
INSERT RDS
   ↓
失敗
   ↓
delete_image()
   ↓
HTTP 500
```

------------------------------------------------------------------------

## 17. API Response 規格

成功：

``` json
{
  "success": true,
  "post": {
    "id": 123,
    "content": "Hello",
    "image_url": "https://cdn.example.com/posts/xxx.jpg",
    "created_at": "..."
  }
}
```

輸入錯誤：

``` json
{
  "detail": "Invalid image type"
}
```

### HTTP Status

  情況                        Status
  ------------------------- --------
  GET 成功                       200
  建立成功                       201
  不合法 Request                 400
  圖片過大                       413
  Server / AWS / DB error        500

------------------------------------------------------------------------

## 18. 前端 JavaScript

`main.js` 負責：

### 載入留言

``` text
頁面載入
   ↓
GET /api/posts
   ↓
產生留言 DOM
```

### 建立留言

``` text
使用者 Submit
   ↓
建立 FormData
   ↓
POST /api/posts
   ↓
成功
   ↓
重新取得留言
```

前端使用：

``` text
HTML
CSS
JavaScript
Fetch API
```

不需要 React 或 Vue。

------------------------------------------------------------------------

## 19. AWS S3 權限設計

S3 Bucket 不應直接設定為 Public Access。

推薦：

``` text
                 boto3
FastAPI ───────────────────→ S3
                              ▲
                              │
                         CloudFront
                              ▲
                              │
Browser ──────────────────────┘
```

Browser 不直接存取 S3 Public URL。

圖片對外存取統一經過 CloudFront。

CloudFront 建議使用 **Origin Access Control（OAC）** 存取 private S3
bucket。

------------------------------------------------------------------------

## 20. EC2 AWS Credential

EC2 Production 環境不得將長期 AWS Access Key 寫入程式碼或 Docker Image。

推薦：

``` text
EC2
 │
 ▼
IAM Role
 │
 └── S3 Permission
```

`boto3` 可以透過 AWS Credential Provider Chain 自動取得 EC2 IAM Role
credentials。

因此程式只需要：

``` python
boto3.client("s3")
```

------------------------------------------------------------------------

## 21. IAM 最小權限

FastAPI EC2 IAM Role 原則上只允許操作指定 Bucket / Prefix。

需要：

``` text
s3:PutObject
s3:DeleteObject
```

作用範圍例如：

``` text
arn:aws:s3:::YOUR_BUCKET/posts/*
```

`DeleteObject` 僅供 transaction rollback 使用。

------------------------------------------------------------------------

## 22. Docker 規格

架構：

``` text
EC2
 │
 ▼
Docker
 │
 └── FastAPI
       │
       └── Uvicorn
```

Dockerfile 負責：

``` text
Python Base Image
       ↓
requirements.txt
       ↓
pip install
       ↓
COPY app
       ↓
啟動 Uvicorn
```

Container 對外 port：

``` text
8000
```

啟動：

``` text
uvicorn app.main:app
```

監聽：

``` text
0.0.0.0:8000
```

Production 不使用 `--reload`。

------------------------------------------------------------------------

## 23. Docker 環境變數

不得把 `.env` COPY 進 Docker Image。

環境變數應由 EC2 / Docker runtime 提供：

``` text
EC2
 │
 │ Environment
 ▼
Docker Container
 │
 ▼
config.py
```

------------------------------------------------------------------------

## 24. RDS 網路規格

RDS MySQL `3306` 不應對：

``` text
0.0.0.0/0
```

開放。

推薦：

``` text
Internet
   │
   ▼
EC2 Security Group
   │
   │ TCP 3306
   ▼
RDS Security Group
```

RDS Security Group inbound source 指定 EC2 Security Group。

------------------------------------------------------------------------

## 25. Python 模組依賴關係

``` text
                 ┌──────────────┐
                 │   config.py  │
                 └──────┬───────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
      main.py       database.py      s3.py
          │             │             │
          │             ▼             ▼
          │          RDS MySQL       S3
          │                           │
          │                           ▼
          │                       CloudFront
          │
          ▼
       Browser
```

依賴方向：

``` text
main.py
 ├── config.py
 ├── database.py
 └── s3.py
```

避免：

``` text
database.py → main.py
s3.py       → main.py
```

以避免 circular import。

------------------------------------------------------------------------

## 26. 各 Python 檔案最低要求

### `config.py`

責任：

``` text
Load application configuration
```

必須提供：

``` text
DB configuration
AWS region
S3 bucket
CloudFront domain
```

### `database.py`

最低 interface：

``` python
def get_connection():
    ...

def create_post(
    content: str,
    image_key: str | None
):
    ...

def get_posts():
    ...
```

### `s3.py`

最低 interface：

``` python
def upload_image(file: UploadFile) -> str:
    ...

def delete_image(image_key: str) -> None:
    ...

def build_image_url(
    image_key: str | None
) -> str | None:
    ...
```

### `main.py`

最低 endpoints：

``` text
GET  /
GET  /api/posts
POST /api/posts
```

------------------------------------------------------------------------

## 27. 完整資料流

### 發表留言

``` text
Browser
   │
   │ POST multipart/form-data
   ▼
FastAPI
   │
   ├── validate content
   │
   └── validate image
             │
             ▼
           boto3
             │
             ▼
             S3
             │
             ▼
         image_key
             │
             ▼
     mysql-connector
             │
             ▼
            RDS
             │
             ▼
       JSON Response
```

### 查看留言

``` text
Browser
   │
   │ GET /api/posts
   ▼
FastAPI
   │
   ▼
RDS
   │
   │ image_key
   ▼
FastAPI
   │
   │ CloudFront URL
   ▼
Browser
   │
   │ GET image
   ▼
CloudFront
   │
   ▼
Private S3
```

------------------------------------------------------------------------

## 28. 工程師實作順序

1.  建立 `requirements.txt`、`app/` 與 `main.py`，先讓 FastAPI `/`
    能啟動。
2.  建立 RDS `posts` table 與 `database.py`。
3.  完成 `get_connection()`、`create_post()`、`get_posts()`。
4.  完成沒有圖片版本的 `POST /api/posts`、`GET /api/posts`。
5.  建立 S3 與 `s3.py`，用 `boto3` 完成圖片 upload。
6.  加入 MIME Type、檔案大小與 UUID Object Key 驗證。
7.  將 `image_key` 存入 RDS。
8.  建立 CloudFront Distribution，以 private S3 + OAC 作為 Origin。
9.  FastAPI 將 `image_key` 轉換成 CloudFront URL。
10. 完成 `index.html`、`main.js`、`style.css`。
11. 加入 S3 成功但 RDS 失敗時的 rollback。
12. 建立 Dockerfile，在本機 Container 驗證。
13. EC2 建立 IAM Role、Security Group 並部署 Docker。
14. Cloudflare DNS 指向服務入口並設定 HTTPS。

------------------------------------------------------------------------

## 29. 最終專案結構

``` text
message-board/
│
├── app/
│   ├── main.py
│   ├── database.py
│   ├── s3.py
│   ├── config.py
│   │
│   ├── templates/
│   │   └── index.html
│   │
│   └── static/
│       ├── css/
│       │   └── style.css
│       └── js/
│           └── main.js
│
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

本專案維持小型、直接的 Python 模組化設計。現階段不需要導入
SQLAlchemy、Repository Pattern、Service Layer 或 Dependency
Injection；當功能與資料模型明顯增加時，再進一步拆分。
