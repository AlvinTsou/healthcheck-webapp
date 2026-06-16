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
