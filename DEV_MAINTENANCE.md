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
當醫學對照標準有更新，或是有新的健檢解讀文件需要匯入時，您可以使用以下兩種方式之一進行更新：

#### 方法一：網頁管理端一鍵同步（推薦，最方便）
1. 直接瀏覽 WebApp 的管理端網址 「/kb-portal」（例如：https://healthreportview.papagopro.com/kb-portal）。
2. 輸入在系統環境變數中設定的 **管理憑證 Token** (`ADMIN_TOKEN`)。
3. 將新版的對照手冊 PDF 檔案拖曳至上傳區域，或點擊該區域選擇檔案。
4. 點擊 **「上傳並開始同步」** 按鈕。
5. 系統會自動將 PDF 上傳至 Cloud Storage，並呼叫 API 觸發 Vertex AI Search 進行數據導入，前端會即時顯示 Operation 同步進度（這需要 5 ~ 10 分鐘）。更新完成後，API 會自動套用最新手冊，無需重啟服務。

#### 方法二：登入 GCP Console 手動導入（備用）
1. 登入 **GCP Console**，前往您的 **Cloud Storage (GCS)**。
2. 進入對應的 Bucket（例如 `gs://healthcheck-handbook-xxx/`），上傳新的 PDF 文件。
3. 前往 **Agent Builder** 控制台，選擇您的 Data Store (`healthcheck-handbook-ds`)。
4. 點選 **Data** 分頁，選擇 **Import** 匯入新上傳的文件，讓系統對文件進行 OCR 解析與索引建立（可能需要 5 ~ 10 分鐘）。
5. 導入完成後，WebApp API 即會檢索到最新的手冊內容。


### C. 憑證與認證過期維護
當系統存取 Vertex AI 拋出 `DefaultCredentialsError` 或是 403 權限不足錯誤時，請依環境確認以下設定：
* **本地開發環境**：
  * 通常是因為本地的 Application Default Credentials (ADC) 已過期。
  * 請在您的終端機重新執行驗證指令：
    ```bash
    gcloud auth application-default login
    ```
  * 依照瀏覽器指示重新登入擁有專案權限的 Google 帳戶並授權即可。
* **GCP Compute Engine VM 部署環境**：
  * 在 VM 上執行時，SDK 會自動查詢 VM 關聯的 **Service Account** 權限，無須手動執行 `gcloud login`。
  * 若出現權限錯誤，代表 VM 關聯 the Service Account 缺乏讀取 Vertex AI Search 的權限。
  * 請至 GCP 控制台的 **IAM & Admin** -> **IAM** 頁面，確認該 VM 關聯的服務帳戶（例如預設的 `Compute Engine default service account`）已被授予 **`Discovery Engine Viewer` (Discovery Engine 檢視者)** 角色。

#### Cloudflare SSL 憑證更新 (Origin Certificate)
當 Cloudflare SSL 憑證過期或需更換網域時，請依以下步驟更新 VM 上的憑證：
1. 登入 Cloudflare，於 **SSL/TLS** -> **Origin Server** 重新產生並下載新的 Origin Certificate (PEM) 與 Private Key (Key)。
2. 將新憑證與金鑰內容分別覆寫至 VM 專案目錄下的 `cloudflare.crt` 與 `cloudflare.key`。
3. 於 VM 專案目錄下執行以下指令，即可在**不停機**的情況下熱載入新憑證：
   ```bash
   docker-compose exec nginx nginx -s reload
   ```

### D. 日常運維與重啟服務 (GCP VM 環境)
在 VM 上進行日常維護時，可使用以下指令管理 Docker 容器服務：
* **重啟 WebApp 與 Nginx 服務**（如更新了 `.env` 或程式碼）：
  ```bash
  docker-compose down && docker-compose up -d --build
  ```
* **即時查看所有服務 Log**：
  ```bash
  docker-compose logs -f --tail=100
  ```
* **分開查看指定服務 Log**：
  * 僅查看 FastAPI 後端：`docker-compose logs -f web`
  * 僅查看 Nginx 反向代理：`docker-compose logs -f nginx`
* **查看容器運行狀態**：
  ```bash
  docker-compose ps
  ```

### E. 成本監控
* 您可以在 GCP 控制台 of **Billing (帳單)** 頁面監控費用。
* 建議關注以下服務的用量：
  * **Vertex AI Search (Agent Builder)**：按查詢次數計費。
  * **Vertex AI (Gemini API)**：按輸入/輸出 Token 數量計費。
  * **Compute Engine VM 與 GCS**：
    * `e2-micro` 實例若部署在台灣 `asia-east1` 每月約 **$8.86 USD**（若部署於美國免費區域且符合免費層資格則為 $0）。
    * GCS 與磁碟依儲存空間與網路流量計費。

### F. 邀請碼與配額系統管理 (MVP)

本專案在 MVP 階段採用輕量級的邀請碼共用配額防刷機制。配額已用次數記錄在 VM 專案目錄下的 `quota_store.json` 檔案中，並已掛載為 Docker Volume。

#### 1. 重置邀請碼配額 (Reset Quotas)
您可以透過以下三種方式之一重置所有邀請碼的配額：
* **方法一：手動刪除（推薦，最方便）**：
  直接在 VM 專案目錄下刪除 `quota_store.json`。後端檢測到檔案不存在時會自動重新初始化為空狀態，因此**免重啟服務，立即生效**：
  ```bash
  rm ~/healthcheck-webapp/quota_store.json
  ```
* **方法二：手動編輯（微調額度）**：
  使用 nano 編輯該狀態檔，手動將特定邀請碼的已用次數改回需要的數值（如改回 `0`），修改存檔後**立即生效，免重啟**：
  ```bash
  nano ~/healthcheck-webapp/quota_store.json
  ```
* **方法三：透過管理員 API 一鍵重置**：
  在本地或 VM 上執行以下 API 呼叫，傳送您在環境變數設定的 `ADMIN_TOKEN` 進行驗證：
  ```bash
  curl -X POST \
    -F "token=您的ADMIN_TOKEN" \
    https://healthreportview.papagopro.com/api/reset
  ```

#### 2. 新增、變更邀請碼或最高配額
1. 登入 VM 並編輯 `.env` 檔案：
   ```bash
   nano ~/healthcheck-webapp/.env
   ```
2. 修改對應變數：
   * `INVITATION_CODES`：以英文逗號分隔。支援使用 `CODE:LIMIT` 格式為特定代碼自訂最高額度上限（例如 `PAPAGO2026:100,VIP888:500,NEWYEAR:50`）。若未指定 `:LIMIT` 則預設套用 `MAX_QUOTA` 設定之數值。
   * `MAX_QUOTA`：每組未指定自訂上限之邀請碼的預設最高配額使用次數（例如 `50`）。
3. 存檔後重啟 Docker 容器以套用新配置：
   ```bash
   docker-compose down && docker-compose up -d --build
   ```

### G. Firebase Firestore 異步整合與 API/IAM 權限

本專案採用 **Firebase Firestore** 作為非同步任務狀態追踪與即時同步的儲存庫。
* **API 啟用**：必須在 GCP 專案中啟用 `firestore.googleapis.com` API。
* **資料庫模式**：需於專案中建立一個預設資料庫 `(default)`，且其模式必須為 **FIRESTORE_NATIVE (Native 模式)**，區域建議選擇 `asia-east1`。
* **安全性規則配置 (Security Rules)**：因為前端是匿名使用者且需要透過 `onSnapshot` 訂閱任務進度，您必須在 Firebase 控制台的 Firestore Database -> **Rules (規則)** 頁面中，設定允許公眾讀取但禁止寫入的安全性規則（寫入一律由後端 Admin SDK 處理）。請直接將專案根目錄的 `firestore.rules` 內容貼入並發佈。
* **服務帳戶權限**：VM 的服務帳戶或是 `/app/gcp-key.json` 對應的服務帳戶（例如 `healthcheck-app`）必須在 GCP 控制台的 **IAM & Admin** 中被授予 **`Cloud Datastore User`** (或更高如 `Cloud Datastore Owner`) 以及 **`Firebase Admin`** 角色。
* **安全性與憑證初始化**：後端 `main.py` 會自動偵測 `GOOGLE_APPLICATION_CREDENTIALS` 環境變數。若金鑰檔案存在，會優先使用 `credentials.Certificate` 明確指定金鑰載入，避免在容器環境下因 API Access Scopes 限制而 fallback 導致 403 權限拒絕；若無設定則使用 GCP Application Default Credentials (ADC) 自動登入。
* **前端 Web 連線設定**：需於本機與遠端的 `.env` 中加入 Firebase Web Client 設定。


### H. Firebase 自動清理與容量控制 (Auto-Cleanup & Capacity Truncation)

為了確保 Firestore 的總儲存量不會超出免費額度限制 (1 GB)，且防止大量請求在背景短時間內重複觸發清理導致 API 額度浪費，系統在每次背景發起分析時，會異步執行 `clean_old_firebase_tasks` 任務，執行雙重清理策略：
1. **時間過期清理**：自動刪除 7 天前創建的任務文件（以 `created_at` timestamp 進行比對）。
2. **容量控制清理**：系統會透過 `count()` 查詢總任務數量。若大於設定的 `FIREBASE_MAX_TASKS_LIMIT`（預設值為 `3000` 筆），則會按時間順序自動刪除最舊的超量文件。
* **防開銷浪費頻率鎖 (Rate Limiting)**：引進 `cleanup_lock` 鎖與 10 分鐘（`600s`）的時間間隔保護，限制在極短時間內不會重複向 Firestore 觸發清理請求，節省 API 讀寫計費。
* **調整任務上限**：可於 `.env` 中加入選用變數調整保留數（建議 1000 ~ 5000）：
  ```env
  FIREBASE_MAX_TASKS_LIMIT=3000
  ```

### I. 臨床分析驗證、數值結構化紀錄與研究關鍵字統計

本系統在每次背景分析成功後，會自動執行以下研究與驗證流程：
1. **臨床分析正確性自我驗證 (Self-Verification)**：
   * 後端在背景自動調用獨立的評估 AI（`gemini-2.5-flash`），針對生成的分析報告進行邏輯審查，評估是否符合醫學標準，計算出 `accuracy_score`（0-100）與簡短評估理由，並存入任務中的 `verification` 物件。這在學術與系統監控中可用作「幻覺率/正確率」的統計指標。
2. **指標數值結構化紀錄 (Metrics Extraction)**：
   * 透過 Structured JSON 輸出，自動從生成報告中提取具體的項目、檢測值、單位及判定狀態，結構化存入任務中的 `extracted_metrics` 欄位。這可用於後續統計使用者的健康指標趨勢。
3. **關鍵字提及頻率累計 (Keyword Tracking)**：
   * 後端定義了 16 個核心健康研究關鍵字（如三酸甘油脂、血糖、脂肪肝等），統計使用者提問與 AI 回覆中該詞彙的頻率，並利用 **Firestore Increment 原子操作** 累加更新至 `research_statistics/keywords` 全局文檔。
4. **查詢統計 API**：
   * 管理端可發送 GET 請求到 `/api/admin/research-stats?token=您的ADMIN_TOKEN` 查詢這些數據，後端會在 Python 記憶體中進行篩選與統計，完全避開了手動在 Firestore 中建立複合索引 (Composite Index) 的限制，上線即可直接運作。
5. **數據展示**：
   * 管理員 Modal 頁面提供「📊 研究數據與驗證」分頁 Tab，可動態展示平均正確率百分比、HSL 漸層進度條與研究關鍵字排行榜。

### J. 網址連結自動填入邀請碼 (UX)
* 前端 `app.js` 支援解析網址 Query 參數。
* 支援使用 `?code=XXX` 與 `?invite=XXX`（例如 `https://domain/?code=PAPAGO2026`）。
* 網頁載入時若發現參數，會自動填入邀請碼輸入框並觸發按鈕啟用狀態，免去手動輸入的麻煩。

### K. 無伺服器/容器部署之 GCP 憑證整合 (Serverless & Container Deployments)
當應用程式部署於 **Zeabur**、**Render**、**Cloud Run** 等無伺服器託管平台時，由於其不方便掛載 `/app/gcp-key.json` 實體金鑰檔案，系統額外提供了動態憑證解析機制：
1. **設定環境變數**：在託管平台控制台新增環境變數 `GCP_KEY_JSON`。
2. **傳入格式**：
   * **原始 JSON 格式**：將您的 GCP Service Account 金鑰 JSON 檔案內容直接貼入環境變數中。
   * **Base64 編碼格式**：如果平台對換行或特殊字元有敏感限制，您可以先在本地將金鑰 JSON 檔案轉換為 Base64 字串，再貼入 `GCP_KEY_JSON`。
3. **運作原理**：後端啟動時，若偵測到 `GCP_KEY_JSON` 環境變數：
   * 會自動判斷是否為 Base64，如果是則會自動解碼。
   * 將解碼後的 JSON 金鑰動態寫入容器內的 `/tmp/gcp-key.json`。
   * 自動將系統 `GOOGLE_APPLICATION_CREDENTIALS` 環境變數指向該路徑，完成 Firebase 與 Vertex AI SDK 的無縫驗證。

