# GCP Vertex AI Search 資源建立指引

本指引將協助您在 Google Cloud Platform (GCP) 上建立 **Vertex AI Search Data Store**，將您的《健檢報告完全手冊》圖片匯入並建立為 AI 知識庫，以扣抵您擁有的 `$1,000 USD (約 NT$31,405)` Trial credit。

---

## 第一步：建立 Cloud Storage 儲存桶並上傳圖片

1. 登入 [GCP 控制台](https://console.cloud.google.com/)。
2. 搜尋並進入 **Cloud Storage** 頁面。
3. 點擊 **建立 (Create)** 建立一個新的 Bucket（例如命名為：`healthcheck-handbook-xxx`，需全域唯一）。
4. 儲存類別與區域建議選擇與您後續服務相同的區域（例如 `asia-east1` 台灣，或預設的 `us-central1`）。
5. 建立完成後，進入該 Bucket。
6. 將本專案目錄下 [resource/健檢報告完全手冊_修訂版__skOlEQAAQBAJ](resource/健檢報告完全手冊_修訂版__skOlEQAAQBAJ) 資料夾內的所有 `page_xxxx.png` 檔案（共 30 張圖片）上傳至 Bucket 根目錄中。

---

## 第二步：建立 Vertex AI Search Data Store

1. 在 GCP 控制台搜尋並進入 **AI Applications** (舊稱 Vertex AI Search & Conversation 或 GenAI App Builder)。
2. 若是首次使用，請依提示啟用相關 API。
3. 在左側選單點擊 **資料儲存庫 (Data Stores)**，然後點擊 **建立資料儲存庫 (Create Data Store)**。
4. 選擇 **Cloud Storage** 作為資料來源。
5. 在設定中：
   * **路徑**：選擇您剛剛建立的 Bucket 路徑（例如：`gs://healthcheck-handbook-xxx/`）。
   * **資料類型**：選擇 **Unstructured documents (非結構化文件)**，此選項支援 PDF、HTML 以及包含圖片（PNG/JPG）的自動 OCR 解析。
6. 點擊 **Import (匯入)**。
7. 為您的 Data Store 命名並完成建立（例如命名為 `healthcheck-handbook-ds`）。
   * *注意：匯入與 OCR 解析 30 張圖片可能需要 5 ~ 10 分鐘，您可以在控制台查看匯入進度。*

---

## 第三步：建立自訂搜尋應用程式（選用）

雖然本 WebApp 主要是透過 API 直接與 Data Store 進行對接，但若您想在控制台內預覽檢索與對話效果，可以建立一個搜尋應用程式：

1. 在左側選單點擊 **應用程式 (Apps)**，然後點擊 **建立應用程式 (Create Application)**。
2. 在第一個步驟「類型 (Type)」：
   * 選擇 **搜尋與助理 (Search & Assistant)** 頁籤。
   * 找到 **自訂搜尋（一般）(Custom Search - Generic)** 項目，點選下方 **建立 (Create)**。
3. 在第二個步驟「設定 (Settings)」：
   * 輸入應用程式名稱（例如 `healthcheck-search-app`），並填入公司/機構名稱。
4. 在第三個步驟「資料 (Data)」：
   * 勾選您在第二步建立的 `healthcheck-handbook-ds` 資料儲存庫並將其綁定。
5. 點擊 **建立 (Create)** 完成應用程式建立。

---

## 第四步：取得配置資訊並設定本地環境

1. 在 **Data Stores** 頁面中，點擊您建立的 Data Store，複製其 **Data Store ID**。
2. 在專案目錄下複製 `.env.example` 並命名為 `.env`：
   ```bash
   cp .env.example .env
   ```
3. 編輯 `.env`，填入您的 GCP 專案 ID 以及剛剛複製的 Data Store ID：
   ```env
   GCP_PROJECT_ID=您的GCP專案ID
   GCP_LOCATION=global
   GCP_DATASTORE_ID=您的Data Store ID
   GEMINI_MODEL=gemini-1.5-pro
   ```

---

## 第五步：本地環境身分驗證 (Application Default Credentials)

為了讓本地執行的 FastAPI 後端能夠安全地存取您的 GCP 資源，您需要使用 `gcloud` 進行驗證：

1. **安裝 Google Cloud CLI**：
   * **macOS** (使用 Homebrew)：
     ```bash
     brew install --cask google-cloud-sdk
     ```
   * **Windows** / 其它安裝方式請參考 [GCP 官方安裝指引](https://cloud.google.com/sdk/docs/install)。

2. **進行本地驗證授權**：
   在您的終端機（macOS Terminal 或 Windows Git Bash）執行以下指令：
   ```bash
   gcloud auth application-default login
   ```
3. 系統會自動彈出瀏覽器視窗，請登入您擁有該 GCP 專案權限的 Google 帳戶並點選「允許」。
4. 驗證完成後，本地將會產生憑證檔案，FastAPI 中的 `google-genai` SDK 便會自動載入該憑證，開箱即用！

---

## 第六步：在 Google Cloud VM (Compute Engine) 部署 WebApp

既然您已經在 GCP 上建立了 VM 執行個體 `hrv001`（可用區 `asia-east1-c`，外部 IP `35.236.168.126`），您可以直接在該 VM 上部署 WebApp，並利用 GCP 的 **IAM 服務帳戶 (Service Account)** 進行無金鑰身分驗證。

### 1. 設定 VM 的 Service Account 權限
為了讓 VM 內的後端程式能安全且自動地將新文件上傳至 Cloud Storage (GCS) 並同步觸發 Vertex AI Search 資料庫更新，您需要授予該 VM 關聯的服務帳戶適當的 IAM 權限：
1. 進入 [GCP 控制台的 IAM 頁面](https://console.cloud.google.com/iam-admin/iam)。
2. 尋找與您 VM `hrv001` 關聯的服務帳戶（預設通常為 `Compute Engine default service account`，格式為 `[專案編號]-compute@developer.gserviceaccount.com`）。
3. 點選該服務帳戶右側的 **編輯 (Edit)** 圖示。
4. 點選 **新增其他角色 (Add Another Role)**，分別搜尋並新增以下三個角色：
   * **`Discovery Engine Viewer` (Discovery Engine 檢視者)**：允許後端向 Data Store 發起 Grounding 檢索與回答。
   * **`Discovery Engine Editor` (Discovery Engine 編輯者)**：允許網頁管理員透過 API 觸發 Data Store 進行文件重新解析與同步。
   * **`Storage Object Creator` (儲存庫物件建立者)**：允許網頁管理員透過 API 將新的手冊 PDF 檔案直接上傳寫入 GCS 儲存桶。
5. 點選 **儲存 (Save)**。
*提示：使用服務帳戶驗證是 GCP 的安全最佳實踐。您不需要在 VM 上執行 `gcloud auth application-default login`，也不需要上傳任何 `.json` 金鑰檔案，GCP SDK 便會自動載入此服務帳戶權限！*

### 2. 設定 VPC 防火牆規則（開啟 Port 80 與 443）
本系統使用 Nginx 作為 Ingress (反向代理)，外部請求將透過標準 HTTP (Port 80) 與 HTTPS (Port 443) 傳入，因此您需要開通這兩個連接埠的防火牆規則：
1. 進入 [GCP 控制台的防火牆頁面](https://console.cloud.google.com/net-security/firewall-rules)。
2. 點選上方 **建立防火牆規則 (Create Firewall Rule)**。
3. 填入以下配置：
   * **名稱 (Name)**：`allow-http-https`
   * **目標 (Targets)**：選擇 **網路中的所有執行個體 (All instances in the network)**。
   * **來源過濾器 (Source filter)**：選擇 **IPv4 範圍 (IPv4 ranges)**。
   * **來源 IPv4 範圍 (Source IPv4 ranges)**：輸入 `0.0.0.0/0` (允許所有外部 IP 存取)。
   * **通訊協定和連接埠 (Protocols and ports)**：勾選 **指定的通訊協定和連接埠 (Specified protocols and ports)** -> 勾選 **TCP** -> 輸入 `80,443`。
4. 點選 **建立 (Create)**。

### 3. SSH 連線至 VM 並部署環境
1. 在本機終端機使用 `gcloud` 指令連線至您的 VM，或者直接在 GCP 控制台的 VM 頁面點選 **SSH** 按鈕連線：
   ```bash
   gcloud compute ssh hrv001 --zone=asia-east1-c
   ```
2. 連線成功後，安裝 Docker 與 Git (以 Debian/Ubuntu 系統為例)：
   ```bash
   sudo apt-get update
   sudo apt-get install -y git docker.io docker-compose
   sudo systemctl start docker
   sudo systemctl enable docker
   # 將目前使用者加入 docker 群組，以利後續免 sudo 執行 docker
   sudo usermod -aG docker $USER
   ```
   *注意：執行完 `usermod` 後，請輸入 `exit` 登出並重新連線 SSH，該群組設定才會生效。*

### 4. 複製專案、設定憑證與啟動服務
1. 重新連線 SSH 後，將本專案的 GitHub 儲存庫複製到 VM 上：
   ```bash
   git clone <您的 GitHub 儲存庫 URL> healthcheck-webapp
   cd healthcheck-webapp
   ```
2. 建立 `.env` 檔案並填入變數：
   ```bash
   cp .env.example .env
   # 編輯 .env (使用 nano .env) 填入您的 GCP_PROJECT_ID 與 GCP_DATASTORE_ID
   ```
3. 建立並設定 Cloudflare SSL 憑證（用於對接 Cloudflare 代理以支援安全連線）：
   * 在專案目錄下，將您在 Cloudflare 產生的 **Origin Certificate** 內容寫入 `cloudflare.crt`。
   * 將 **Private Key** 內容寫入 `cloudflare.key`。
   * *提示：您可以使用 `nano cloudflare.crt` 與 `nano cloudflare.key` 分別進行貼上。*
4. 建立一個空的 `gcp-key.json` 以免 Docker Compose 掛載失敗（因為在 VM 上我們使用 Service Account 權限，所以不需要實際寫入金鑰內容）：
   ```bash
   touch gcp-key.json
   ```
5. 啟動 Docker 服務（這會同時啟動 FastAPI 服務與 Nginx 反向代理）：
   ```bash
   docker-compose up -d --build
   ```
6. 驗證服務：
   打開瀏覽器直接存取您的網域 `https://healthreportview.papagopro.com`，即可透過安全加密的 HTTPS 連線開始使用健檢報告分析服務！

---

## 第七步：後續維護：上傳與匯入新健檢手冊 (Updating the RAG Knowledge Base)

當您有新的健檢解讀 PDF 手冊或醫學文件需要加入 AI 知識庫時，請依循以下步驟進行更新，以確保資料庫能正確解析：

### 1. 將新文件上傳至 Cloud Storage (GCS)
1. 登入 [GCP 控制台](https://console.cloud.google.com/)。
2. 進入 **Cloud Storage**，找到您的 Bucket（例如：`ealthcheck-handbook-001`）。
3. 點擊 **上傳檔案 (Upload Files)**，將您的新 PDF 文件（如 `De_健檢報告完全手冊.pdf`）上傳至 Bucket 中。

### 2. 將新文件匯入至 Vertex AI Search Data Store
1. 在 GCP 控制台搜尋並進入 **Agent Builder**。
2. 點擊左側選單的 **資料儲存庫 (Data Stores)**，點選進入您綁定的 Data Store。
3. 點選 **資料 (Data)** 頁籤，然後點擊 **匯入資料 (Import Data)**。
4. 在右側抽屜式選單中進行以下設定：
   * **選取要匯入的資料夾或檔案**：
     * **建議選擇「資料夾」**（比單獨匯入「檔案」更不容易出錯）：
       * 點選「資料夾」按鈕。
       * 輸入路徑格式為：`gs://您的Bucket名稱`（例如：`gs://ealthcheck-handbook-001`）。
       * *注意：請確保輸入框的開頭與結尾無多餘的空白字元，否則系統會報出 Bucket 名稱格式不合法的錯誤。*
     * **若選擇「檔案」**：
       * 點選「檔案」按鈕。
       * 輸入路徑格式必須包含完整路徑與檔名，例如：`gs://ealthcheck-handbook-001/De_健檢報告完全手冊.pdf`。
   * **What kind of data are you importing? (您要匯入哪種資料？)**：
     * 勾選 **文件 (File)**，其支援 PDF, HTML, TXT 等格式之非結構化文件。
5. 點擊 **匯入 (Import)** 啟動作業。

### 3. 檢查解析進度與自動套用
1. 點擊 Data Store 頁面中的 **活動 (Activity)** 頁籤。
2. 匯入大於 `50 MB` 的 PDF 檔案時，因為系統需要進行 OCR 與文本向量化，背景解析大約需要 **5 至 15 分鐘**。
3. 當活動記錄的狀態由 `Importing` 轉變為 `Completed`，代表解析已完成。
4. 新資料解析完成後會**立即自動套用**。FastAPI 後端與 VM 上的 Docker 服務**完全無須重啟**，下次提問時 AI 便會即時使用新版手冊進行接地分析。
