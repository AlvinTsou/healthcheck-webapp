# 健檢報告智慧分析與健康管理線上諮詢 WebApp

這是一個基於 Google Vertex AI Search Grounding (RAG) 技術的健檢報告分析系統。使用者可以上傳自己的健檢報告（圖片或 PDF）並提出疑問，系統會對照《健檢報告完全手冊》的專業醫學知識庫，提供精確、具備引用來源且無幻覺的衛教解釋與生活建議。

---

## 🛠️ 環境配置

本專案需要連接您在 GCP 上建立的 Vertex AI Search Data Store。請先閱讀 [GCP_GUIDE.md](GCP_GUIDE.md) 完成資源建構，並在本地終端機執行：
```bash
gcloud auth application-default login
```
並將專案目錄下的 `.env.example` 複製為 `.env` 並填入正確的專案資訊。

---

## 🚀 運行指引 (macOS / Linux)

### 方法一：使用本地 Python 虛擬環境
macOS 系統已內建 Python 3，請打開「終端機 (Terminal)」並執行以下步驟：

1. **建立並啟用 Python 虛擬環境**：
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. **安裝依赖套件**：
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. **啟動 FastAPI 後端伺服器**：
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
4. **開啟網頁**：
   打開瀏覽器存取 `http://localhost:8000`。

### 方法二：使用 Docker 運行
若您希望透過 Docker 進行容器化運行，請確保您的 Docker Desktop 已啟動，並在終端機執行：

1. **建構 Docker 映像檔**：
   ```bash
   docker build -t healthcheck-app .
   ```
2. **掛載本地 GCP 憑證並運行容器**：
   為了讓 Docker 內的應用程式能讀取您本地的 GCP ADC 驗證憑證，執行以下指令：
   ```bash
   docker run -d \
     -p 8000:8000 \
     --env-file .env \
     -v "$HOME/.config/gcloud:/root/.config/gcloud" \
     healthcheck-app
   ```
3. **開啟網頁**：
   打開瀏覽器存取 `http://localhost:8000`。

---

## 💻 運行指引 (Windows)

### 使用 Git Bash / PowerShell

1. **建立並啟用 Python 虛擬環境**：
   * Git Bash:
     ```bash
     python -m venv .venv
     source .venv/Scripts/activate
     ```
   * PowerShell:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
2. **安裝依賴套件與啟動**：
   ```bash
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000
   ```

---

## 📤 上傳至 GitHub 專案庫 (Repository)

若您想將此專案作為一個獨立的 Git 倉庫上傳至 GitHub，請遵循以下步驟：

1. **初始化獨立的 Git 倉庫**：
   在 `HealthCheck WebApp` 目錄下執行：
   ```bash
   git init -b main
   ```
2. **提交程式碼**（`.gitignore` 已設定排除敏感的 `.env` 與 `.venv`）：
   ```bash
   git add .
   git commit -m "Initial commit: HealthCheck WebApp with Vertex AI Grounding"
   ```
3. **建立 GitHub 遠端專案庫並推行**：
   * **方法 A：使用 GitHub CLI (推薦)**
     ```bash
     gh repo create healthcheck-webapp --public --source=. --remote=origin --push
     ```
   * **方法 B：手動在 GitHub 上建庫**
     1. 前往 GitHub 網頁點擊 **New repository**，命名為 `healthcheck-webapp`（不要勾選建立 README 或 gitignore）。
     2. 複製網頁上的遠端 URL 並在終端機執行：
        ```bash
        git remote add origin <您的GitHub儲存庫URL>
        git branch -M main
        git push -u origin main
        ```

---

## 🧪 快速功能測試 (Quick Testing)

本專案內建模擬數據生成腳本，即使您手邊暫時沒有真實的健檢報告，也能輕鬆測試系統的 RAG 健檢分析功能：

1. **生成模擬測試圖片**（需先啟用虛擬環境並安裝套件）：
   ```bash
   python3 generate_test_report.py
   ```
   這會在 `static/test_report.png` 產生一張包含多項血壓、血糖、膽固醇等紅字異常數據的測試報告圖。
2. **下載測試圖片**：
   * 本地伺服器啟動後，直接在瀏覽器下載 `http://localhost:8000/test_report.png`。
3. **上傳並發送測試**：
   * 進入網頁主畫面 `http://localhost:8000`。
   * 將該圖片上傳，並輸入提問（例如：「我的總膽固醇 245 還有空腹血糖 115 該注意什麼？」）即可測試 RAG 與 Gemini 串接結果。

---

## 🛠️ 開發與後續維護 (Development & Maintenance)

關於本系統的架構細節、日常開發指令、更新雲端手冊知識庫以及更換 Gemini 模型版本等，請參閱詳細的 [DEV_MAINTENANCE.md](DEV_MAINTENANCE.md)。
