# HealthCheck WebApp 開發與維護指南 (Development and Maintenance Guide)

本指南旨在協助開發人員了解「健檢報告智慧分析與健康管理線上諮詢 WebApp」的系統架構、日常開發工作流以及後續維護步驟。

---

## 1. 系統架構概覽 (System Architecture)

本專案採用輕量級的前後端分離架構：
* **前端 (Frontend)**：單頁應用程式 (SPA)，以毛玻璃風格 (Glassmorphism) 設計。
  * `static/index.html`：頁面結構與 Markdown 渲染器。
  * `static/style.css`：毛玻璃樣式與骨架屏 (Skeleton) 動畫。
  * `static/app.js`：處理拖曳上傳、發送 API 請求以及動態渲染結果。
* **後端 (Backend)**：基於 Python FastAPI。
  * `main.py`：後端核心邏輯。負責接收前端上傳的報告與提問，並呼叫 Google GenAI SDK。
* **AI 與知識庫 (AI & RAG)**：
  * **Google GenAI SDK (google-genai)**：用於呼叫 Gemini 進行多模態解讀。
  * **Vertex AI Search Grounding**：將您上傳至 GCS 的《健檢報告完全手冊》作為 Data Store，在 Gemini 生成回答時進行資料檢索與接地，以防止醫療幻覺，並回傳引用來源 (Citations)。

---

## 2. 開發環境與依賴管理 (Development Environment & Dependencies)

專案使用 `venv` 管理 Python 依賴，所有依賴清單記錄在 `requirements.txt`。

### 常用開發指令
* **建立虛擬環境**：
  ```bash
  python3 -m venv .venv
  ```
* **啟用虛擬環境 (macOS)**：
  ```bash
  source .venv/bin/activate
  ```
* **安裝依賴套件**：
  ```bash
  .venv/bin/pip install -r requirements.txt
  ```
* **啟動本機開發伺服器** (支援熱重載，預設監聽 `http://localhost:8000`)：
  ```bash
  .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
  ```
* **新增依賴套件**：
  在虛擬環境中安裝套件後，請更新 `requirements.txt`：
  ```bash
  .venv/bin/pip freeze > requirements.txt
  ```

---

## 3. 測試數據生成 (Mock Test Data Generation)

為了方便進行功能測試，專案內提供了一個模擬健檢報告圖片的生成腳本：
* **腳本檔案**：`generate_test_report.py`
* **使用方式**：
  ```bash
  .venv/bin/python generate_test_report.py
  ```
  執行後，會在 `static/test_report.png` 輸出一個包含收縮壓、血糖、膽固醇等紅字異常數據的測試報告。您可以在本地伺服器啟動時，直接前往 `http://localhost:8000/test_report.png` 下載此圖，並在 WebApp 介面上傳進行端到端功能測試。

---

## 4. 系統維護要點 (Maintenance Keypoints)

### A. 更換 Gemini 模型
若您需要升級或更換 Gemini 模型（例如從 `gemini-1.5-pro` 升級為 `gemini-2.5-pro` 或改用較低成本的 `gemini-1.5-flash`）：
1. 編輯專案目錄下的 `.env` 檔案。
2. 修改 `GEMINI_MODEL` 變數：
   ```env
   GEMINI_MODEL=gemini-2.5-pro
   ```
3. 存檔後 FastAPI 會自動偵測並套用新模型。

### B. 更新《健檢報告完全手冊》知識庫
當醫學對照標準有更新，或是有新的健檢解讀文件需要匯入時：
1. 登入 **GCP Console**，前往您的 **Cloud Storage (GCS)**。
2. 進入對應的 Bucket（例如 `gs://healthcheck-handbook-xxx/`），上傳新的圖片或 PDF 文件。
3. 前往 **Vertex AI Search** 控制台，選擇您的 Data Store (`healthcheck-handbook-ds`)。
4. 點選 **Import (匯入)** 或等待自動同步，讓系統對新文件進行 OCR 解析與索引建立（可能需要 5 ~ 10 分鐘）。
5. 匯入完成後，WebApp API 會自動檢索到最新的手冊內容，無需重新部署後端代碼。

### C. 憑證與認證過期維護
若後端拋出 `DefaultCredentialsError` 或是存取 Vertex AI 權限不足的 403 錯誤，通常是因為本地的 Application Default Credentials (ADC) 已過期：
* 請在您的終端機重新執行驗證指令：
  ```bash
  gcloud auth application-default login
  ```
* 依照瀏覽器指示重新登入 Google 帳戶並點選授權即可。

### D. 成本監控
* 您可以在 GCP 控制台的 **Billing (帳單)** 頁面監控費用。
* 建議關注以下服務的用量：
  * **Vertex AI Search (Agent Builder)**：按查詢次數計費。
  * **Vertex AI (Gemini API)**：按輸入/輸出 Token 數量計費。
  * **Cloud Run 與 GCS**：按運算時間與儲存空間計費。
