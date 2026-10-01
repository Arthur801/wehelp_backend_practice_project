# 匯入 FastAPI、設定與資料存取模組

# 建立 FastAPI 應用程式並設定模板與靜態檔案

# 統一錯誤回應：輸入錯誤 400、圖片過大 413、服務異常 500

# validate_content：驗證留言文字不可為空白

# validate_image：驗證圖片 MIME 類型與大小

# GET /：回傳一頁式留言板

# GET /api/posts：取得留言並轉換圖片網址，回傳 posts 列表

# POST /api/posts：驗證文字與選填圖片、先上傳再寫入，失敗清理圖片，成功回傳 201 與留言資料
