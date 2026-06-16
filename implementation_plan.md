# Implementation Plan - HealthCheck WebApp (Vertex AI Search Grounding)

根據您的要求，我們將以 **Vertex AI Search Grounding (GCP 原生 RAG 方案)** 為主，並在專案中加入一份 **在 macOS 上運行的完整指引** (適用於已安裝 Python 與 Docker 的環境)。

## User Review Required

> [!IMPORTANT]
> **本地開發與 GCP 資源連接設定**
> 
> 為了在本地開發的 WebApp 中使用您的 GCP Vertex AI Search 資源，我們需要建立對接。請確認以下步驟：
> 1.  **GCP 資源建立**：您需要在 GCP 控制台建立 GCS Bucket、上傳健檢手冊圖片，並在 Vertex AI Search & Conversation 中建立 Data Store。我們將在專案中提供詳細的操作指引 `GCP_GUIDE.md` 協助您。
> 2.  **環境變數配置**：本地 WebApp 將透過 `.env` 檔案讀取 GCP 專案 ID、Data Store ID 以及驗證金鑰（或使用 `gcloud` CLI 的 Application Default Credentials）。
> 3.  **身分驗證**：若在本地運行，請確保您的開發環境已安裝 Google Cloud CLI 並執行了 `gcloud auth application-default login`，或者提供 Service Account 金鑰。

## Proposed Changes

本專案將於 [HealthCheck WebApp](./) 目錄下建立，結構如下：

```
HealthCheck WebApp/
├── .venv/                      # Python 虛擬環境
├── resource/                   # 原始健檢手冊圖片 (已存在)
├── static/                     # 前端網頁靜態資源
│   ├── index.html              # [NEW] 前端 UI (Glassmorphism 設計)
│   ├── style.css               # [NEW] 精美 CSS 樣式
│   └── app.js                  # [NEW] 前端邏輯 (拖曳上傳、AJAX 請求、Markdown 渲染)
├── main.py                     # [NEW] FastAPI 後端服務 (整合 Vertex AI Search)
├── requirements.txt            # [NEW] Python 套件清單
├── Dockerfile                  # [NEW] 容器化設定
├── .env.example                # [NEW] 環境變數範本
├── README.md                   # [NEW] 專案說明與 macOS/Windows 運行指引
└── GCP_GUIDE.md                # [NEW] GCP 資源建立指引手冊
```

---

### 1. 後端與配置元件

#### [NEW] [.env.example](.env.example)
*   提供專案所需的環境變數範本：
    ```env
    GCP_PROJECT_ID=your-gcp-project-id
    GCP_LOCATION=global
    GCP_DATASTORE_ID=your-datastore-id
    GEMINI_MODEL=gemini-1.5-pro
    ```

#### [NEW] [requirements.txt](requirements.txt)
*   列出所需的 Python 依賴套件：
    *   `fastapi`
    *   `uvicorn`
    *   `google-genai` (支援呼叫 Vertex AI Search Grounding)
    *   `python-multipart`
    *   `python-dotenv`

#### [NEW] [main.py](main.py)
*   讀取 `.env` 檔案中的設定。
*   提供 API 路由：
    *   `POST /api/analyze`：
        *   接收使用者上傳的 `file` (健檢報告圖片/PDF) 和 `question` (問題)。
        *   使用 `google-genai` SDK，並帶入 `vertex_ai_search_datastore` 參數。
        *   呼叫 `gemini-1.5-pro` 進行 Grounded Generation，讓 Gemini 讀懂上傳報告的同時，翻閱 Vertex AI Search 裡的健檢手冊。
        *   解析 `response.candidates[0].grounding_metadata`，提取引用文檔片段 (Citations)，一併回傳給前端。

#### [NEW] [GCP_GUIDE.md](GCP_GUIDE.md)
*   以中文詳細說明：
    1.  如何在 GCP 控制台建立 Cloud Storage Bucket，並上傳手冊圖片。
    2.  如何建立 Vertex AI Search Data Store，並將其連接至該 Bucket，啟動自動 OCR。
    3.  如何取得 `GCP_PROJECT_ID` 與 `GCP_DATASTORE_ID` 並填入 `.env`。
    4.  如何使用 `gcloud auth application-default login` 授權本地開發環境。

#### [NEW] [README.md](README.md)
*   撰寫完整的專案說明。
*   針對 **macOS** 提供兩種運行指引：
    *   **方法一：使用 Python 虛擬環境 (macOS 終端機)**
        *   建立與啟動虛擬環境：`python3 -m venv .venv && source .venv/bin/activate`
        *   安裝依賴：`pip install -r requirements.txt`
        *   環境變數設定與驗證：安裝 Google Cloud CLI 並執行 `gcloud auth application-default login`
        *   啟動服務：`uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
    *   **方法二：使用 Docker (macOS 容器化)**
        *   建構映像檔：`docker build -t healthcheck-app .`
        *   掛載驗證金鑰並運行容器，確保 GCP 存取權限。

---

### 2. 前端介面設計 (Glassmorphism 玻璃擬態)

#### [NEW] [index.html](static/index.html)
*   使用 Google Fonts (Outfit 與 Noto Sans TC) 提供優雅的字體排版。
*   引入 `marked.js` 用於 Markdown 渲染。
*   雙欄響應式佈局：
    *   **左欄：上傳與控制區**：拖曳上傳區域、預覽卡片、提問輸入框。
    *   **右欄：分析結果區**：包含 AI 骨架載入動畫 (Skeleton Loader) 的卡片。

#### [NEW] [style.css](static/style.css)
*   深色漸層背景 + `backdrop-filter: blur(16px)` 與微弱發光邊框，打造現代感的高級毛玻璃效果。
*   平滑的 hover 漸層與微動畫。
*   設計精美的骨架屏載入動畫。

#### [NEW] [app.js](static/app.js)
*   處理拖曳上傳與即時圖片預覽。
*   發送 Multipart 請求給 FastAPI 後端。
*   接收後端回傳的分析結果與 **Citations (引用來源)**，使用 `marked.parse` 渲染回答，並將引用來源以高質感的標籤卡片形式單獨展示。

---

### 3. 容器化與部署

#### [NEW] [Dockerfile](file:///Users/alvintsou/Documents/Projects/healthcheck-webapp/Dockerfile)
*   打包 Python FastAPI 服務，暴露特定連接埠以相容於 GCP Cloud Run 部署。

#### [NEW] [docker-compose.yml](file:///Users/alvintsou/Documents/Projects/healthcheck-webapp/docker-compose.yml)
*   提供本機及 VPS 多容器環境的啟動配置，將金鑰掛載進容器，並限制系統資源。

#### 最佳部署方案 (VPS 與 Zeabur 混合架構)
由於伺服器的主機 Port 80 與 443 已被既存的 `pokerroom-nginx` 與 `n8n-caddy` 佔用，為避免衝突並讓 Zeabur 與其他服務和平共處，部署策略如下：

1.  **修正 Zeabur (K3s) Ingress Controller 狀態** (已完成)：
    *   將 Zeabur 內部的 `ingress-controller` DaemonSet 調整為 `hostNetwork: false`，避免其與主機的 80/443 Port 產生衝突。
    *   新增一個 `NodePort` 服務 (`ingress-controller-nodeport`)，將 K3s 內部的 Ingress 暴露在主機的 Port `30080` (HTTP) 與 `30443` (HTTPS)。
2.  **服務部署**：
    *   **方式一：透過 Zeabur CLI 遠端部署**：
        1. 本地使用 API Key 登入：`npx zeabur auth login --token <TOKEN>`。
        2. 專案根目錄下執行：`npx zeabur deploy`。
        3. 在 Zeabur 網頁控制台設定環境變數與 Config 掛載金鑰。
        4. 外部流量路由：在伺服器的 `n8n-caddy` 或 `pokerroom-nginx` 中，將該服務網域的請求反向代理（`reverse_proxy`）至 `http://localhost:30080`。
    *   **方式二：使用 Docker Compose 直接在 VPS 部署**：
        1. 透過 Git 將專案拉取至伺服器。
        2. 將 `gcp-key.json` 上傳至伺服器專案目錄下。
        3. 執行 `sudo docker compose up -d --build`，服務將運行在 Port `8000`。
        4. 外部流量路由：在伺服器的 Caddy 或 Nginx 設定中，將網域請求反向代理至 `http://localhost:8000`。

## Verification Plan

### Manual Verification
1.  **GCP 設定與認證**：
    *   依照 `GCP_GUIDE.md` 設定 Data Store，並於本地執行 `gcloud auth application-default login`。
    *   建立 `.env` 檔案並填入正確的 `GCP_PROJECT_ID` 及 `GCP_DATASTORE_ID`。
2.  **本地啟動測試**：
    *   執行 `uvicorn main:app --reload --port 8000`。
    *   在瀏覽器打開 `http://localhost:8000`。
3.  **Zeabur (K3s) 狀態確認**：
    *   在伺服器上執行 `sudo kubectl get pods -n default -l app.kubernetes.io/name=ingress-controller`，確認狀態為 `Running` (1/1)。
4.  **端到端功能測試**：
    *   上傳測試用的健檢報告圖片，輸入問題並送出，確認 AI 回答是否正確參考了您上傳手冊的數據，且帶有 Citation。

