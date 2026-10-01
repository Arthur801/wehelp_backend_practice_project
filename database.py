# 匯入 MySQL 套件與資料庫設定
import logging
import os
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

import config

# 載入本機環境變數
load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger(__name__)


def _close_resources(cursor, connection) -> None:
    # 清理失敗不應掩蓋原始錯誤，也不應讓已 commit 的留言被視為寫入失敗。
    for resource in (cursor, connection):
        if resource is not None:
            try:
                resource.close()
            except Exception:
                logger.exception("Failed to close database resource")

# get_connection：建立 MySQL 連線
def get_connection():
    missing = [
        name for name in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
        if not getattr(config, name)
    ]
    if missing:
        raise ValueError("資料庫環境變數缺失：" + ", ".join(missing))
    settings = {
        "host": os.getenv("DB_HOST", ""),
        "port": int(os.getenv("DB_PORT") or "3306"),
        "database": os.getenv("DB_NAME", ""),
        "user": os.getenv("DB_USER", ""),
        "password": os.getenv("DB_PASSWORD", ""),
    }
        
    return mysql.connector.connect(**settings)


# 初始化資料庫
def init_database() -> None:
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST", ""),
        port=int(os.getenv("DB_PORT") or "3306"),
        user=os.getenv("DB_USER", ""),
        password=os.getenv("DB_PASSWORD", ""),
    )
    cursor = None
    try:
        cursor = connection.cursor()
        # SQL 識別字不能使用值參數，須將反引號跳脫。
        database_name = os.getenv("DB_NAME")
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
        )
        cursor.execute(f"USE `{database_name}`")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                content TEXT NOT NULL,
                image_key VARCHAR(500) NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()
    finally:
        _close_resources(cursor, connection)

# create_post：以參數化 SQL 新增留言並回傳資料，處理交易與資源釋放
def create_post(content: str, image_key: str | None) -> dict:
    connection = get_connection()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "INSERT INTO posts (content, image_key) VALUES (%s, %s)",
            (content, image_key),
        )
        cursor.execute(
            "SELECT id, content, image_key, created_at FROM posts WHERE id = %s",
            (cursor.lastrowid,),
        )
        post = cursor.fetchone()
        if post is None:
            raise RuntimeError("Created post could not be retrieved")
        connection.commit()
        return post
    except Exception:
        try:
            connection.rollback()
        except Exception:
            logger.exception("Failed to roll back post creation")
        raise
    finally:
        _close_resources(cursor, connection)

# get_posts：依建立時間由新到舊查詢留言並釋放資源
def get_posts() -> list[dict]:
    connection = get_connection()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, content, image_key, created_at "
            "FROM posts ORDER BY created_at DESC, id DESC"
        )
        return cursor.fetchall()
    finally:
        _close_resources(cursor, connection)

if __name__ == "__main__":
    init_database()
    print("資料庫與 posts 資料表初始化完成。")
