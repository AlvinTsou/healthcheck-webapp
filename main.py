import os
import logging
import datetime
import uuid
import asyncio
import json
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError
from google.cloud import storage
from google.cloud import discoveryengine_v1beta as discoveryengine
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase Admin SDK
try:
    # Use Application Default Credentials (ADC) automatically
    firebase_admin.initialize_app()
    logging.info("Firebase Admin initialized successfully using Application Default Credentials.")
except ValueError:
    # App already initialized
    pass
except Exception as e:
    logging.error(f"Failed to initialize Firebase Admin: {str(e)}")


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("healthcheck-backend")

# Load environment variables
load_dotenv()

# Support dynamic GCP Key from env var (useful for serverless/Zeabur deployments)
gcp_key_json = os.getenv("GCP_KEY_JSON")
if gcp_key_json:
    key_path = "/tmp/gcp-key.json"
    try:
        # Check if it looks like base64 (doesn't start with '{')
        stripped_key = gcp_key_json.strip()
        if not stripped_key.startswith("{"):
            import base64
            logger.info("Detecting Base64-encoded GCP_KEY_JSON, decoding...")
            decoded_bytes = base64.b64decode(stripped_key)
            gcp_key_json = decoded_bytes.decode("utf-8")
            
        with open(key_path, "w", encoding="utf-8") as f:
            f.write(gcp_key_json)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
        logger.info(f"Dynamically wrote GCP key to {key_path} and set GOOGLE_APPLICATION_CREDENTIALS")
    except Exception as e:
        logger.error(f"Failed to write dynamic GCP key: {str(e)}")

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_LOCATION = os.getenv("GCP_LOCATION", "global")
GCP_DATASTORE_ID = os.getenv("GCP_DATASTORE_ID")
GCP_BUCKET_NAME = os.getenv("GCP_BUCKET_NAME")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")
FIREBASE_AUTH_DOMAIN = os.getenv("FIREBASE_AUTH_DOMAIN")
FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET")
FIREBASE_MESSAGING_SENDER_ID = os.getenv("FIREBASE_MESSAGING_SENDER_ID")
FIREBASE_APP_ID = os.getenv("FIREBASE_APP_ID")

try:
    MAX_QUOTA = int(os.getenv("MAX_QUOTA", "50"))
except ValueError:
    MAX_QUOTA = 50

# MVP Invitation Quota System Config - Support "CODE:LIMIT" format
INVITATION_CODES_RAW = os.getenv("INVITATION_CODES", "")
INVITATION_LIMITS = {}  # mapping: CODE -> LIMIT
for item in INVITATION_CODES_RAW.split(","):
    item = item.strip()
    if not item:
        continue
    parts = item.split(":")
    code = parts[0].strip().upper()
    if len(parts) > 1:
        try:
            limit = int(parts[1].strip())
        except ValueError:
            limit = MAX_QUOTA
    else:
        limit = MAX_QUOTA
    INVITATION_LIMITS[code] = limit

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "papago-reset-secret-2026")

QUOTA_STORE_PATH = "quota_store.json"
USAGE_LOG_PATH = "usage_log.jsonl"
quota_lock = asyncio.Lock()

def log_invite_code_usage(invite_code: str, file_name: str, file_size: int, status: str, error_detail: str = None):
    log_entry = {
        "timestamp": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        "invite_code": invite_code,
        "file_name": file_name,
        "file_size_bytes": file_size,
        "status": status
    }
    if error_detail:
        log_entry["error"] = error_detail
    try:
        with open(USAGE_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        logger.info(f"Usage Logged: {invite_code} - {status}")
    except Exception as e:
        logger.error(f"Failed to write usage log: {str(e)}")

def load_quota_store() -> dict:
    if not os.path.exists(QUOTA_STORE_PATH):
        try:
            with open(QUOTA_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump({}, f)
            return {}
        except Exception as e:
            logger.error(f"Failed to create quota store file: {str(e)}")
            return {}
    try:
        with open(QUOTA_STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read quota store file: {str(e)}")
        return {}

def save_quota_store(data: dict):
    try:
        with open(QUOTA_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write quota store file: {str(e)}")

# Initialize FastAPI
app = FastAPI(title="HealthCheck WebApp Backend")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Google GenAI client
# It will use Application Default Credentials (ADC) by default
client = None

def get_genai_client():
    global client
    if client is None:
        try:
            if not GCP_PROJECT_ID:
                raise ValueError("GCP_PROJECT_ID is not configured in environment variables.")
            
            logger.info(f"Initializing Google GenAI Client with Project: {GCP_PROJECT_ID}, Location: {GCP_LOCATION}")
            # Initialize for Vertex AI integration
            client = genai.Client(
                vertexai=True,
                project=GCP_PROJECT_ID,
                location=GCP_LOCATION
            )
        except Exception as e:
            logger.error(f"Failed to initialize GenAI client: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"GCP SDK 載入失敗：請確認您已設定 .env 且在本地執行了 `gcloud auth application-default login`。錯誤資訊: {str(e)}"
            )
    return client

# Health check endpoint
@app.get("/api/health")
def health_check():
    configured = bool(GCP_PROJECT_ID and GCP_DATASTORE_ID)
    return {
        "status": "healthy",
        "gcp_configured": configured,
        "model": GEMINI_MODEL,
        "datastore_id": GCP_DATASTORE_ID
    }

# Firebase web client configuration endpoint
@app.get("/api/config")
def get_firebase_config():
    return {
        "firebase_config": {
            "apiKey": FIREBASE_API_KEY,
            "authDomain": FIREBASE_AUTH_DOMAIN,
            "projectId": GCP_PROJECT_ID,
            "storageBucket": FIREBASE_STORAGE_BUCKET,
            "messagingSenderId": FIREBASE_MESSAGING_SENDER_ID,
            "appId": FIREB# Background job to analyze report asynchronously
async def async_analyze_job(
    task_id: str,
    file_bytes: bytes,
    file_mime: str,
    file_name: str,
    question: str,
    code_clean: str,
    invite_limit: int,
    remaining: int
):
    logger.info(f"Starting background job for task {task_id}")
    try:
        db = firestore.client()
        task_ref = db.collection("analysis_tasks").document(task_id)
    except Exception as e:
        logger.error(f"Firestore Client initialization failed in background: {str(e)}")
        # 即使 Firestore 連線異常，為了安全仍須先寫入 local usage_log 備份
        log_invite_code_usage(code_clean, file_name, len(file_bytes), "failed", f"Firestore Error: {str(e)}")
        return

    try:
        ai_client = get_genai_client()
        
        # Package for multimodal generation
        user_report = types.Part.from_bytes(
            data=file_bytes,
            mime_type=file_mime
        )
        
        # Build Vertex AI Search Datastore path
        datastore_path = f"projects/{GCP_PROJECT_ID}/locations/{GCP_LOCATION}/collections/default_collection/dataStores/{GCP_DATASTORE_ID}"
        logger.info(f"Using Datastore for grounding: {datastore_path}")
        
        # System instructions to prevent medical hallucinations and enforce formatting
        system_instruction = (
            "你是一位專業的健康管理 AI 顧問。當使用者提供健檢報告或數據時，你必須精確對照知識庫中《健檢報告完全手冊》的醫學標準值與建議。\n"
            "請遵循以下規則回答，且必須將分析內容結構化地劃分為以下四個大區塊，每個區塊開頭必須精確使用規定的 `##` 標題，不得自行更改或省略：\n\n"
            "## 1. 健檢指標快速對照\n"
            "（在此處以 Markdown 表格列出所有檢測數值與標準值的對比。表格必須包含項目、參考值、檢測值、狀態。如果有異常的數值，狀態欄必須填寫為 **偏高**、**偏低** 或 **異常**，以加粗的星號包裹，方便前端加亮顯示。）\n\n"
            "## 2. 核心異常解析與潛在風險\n"
            "（在此處詳細解釋上傳報告中異常指標的生理學成因以及可能帶來的長期健康風險。）\n\n"
            "## 3. 個人化健康管理行動方案\n"
            "（在此處提供具體可執行的飲食調整原則、適合的運動類型與頻率，以及日常起居作息之具體改善建議。）\n\n"
            "## 4. 專屬諮詢解答\n"
            "（在此處正面解答使用者最關心的諮詢問題。）\n\n"
            "請注意：\n"
            "1. 你的回答必須緊密基於知識庫事實，提供醫學數據的衛教解釋與日常健康管理建議。\n"
            "2. 你的回答末尾務必加上以下免責聲明：\n"
            "   『【免責聲明】本分析僅供個人健康管理參考，不具備醫療診斷效力。若您的數據異常或有身體不適，請務必諮詢專業醫師進行診斷與治療。』\n"
            "3. 如果相關標準或答案在知識庫中完全找不到，請禮貌地告知使用者，並引導使用者諮詢醫生，不要盲目猜測或虛構數據。"
        )
        
        # Define Grounding Tool
        grounding_tool = types.Tool(
            retrieval=types.Retrieval(
                vertex_ai_search=types.VertexAISearch(datastore=datastore_path)
            )
        )
        
        # Setup Grounding config
        grounding_config = types.GenerateContentConfig(
            tools=[grounding_tool],
            system_instruction=system_instruction,
            temperature=0.2 # low temperature for strict factual outputs
        )
        
        prompt = f"請幫我分析這份健檢報告。使用者目前最想了解的問題是：{question}"
        
        # Call Gemini model with 120s timeout limit using asyncio.wait_for and asyncio.to_thread
        logger.info(f"Background task {task_id}: Calling Gemini '{GEMINI_MODEL}' (120s timeout)...")
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    ai_client.models.generate_content,
                    model=GEMINI_MODEL,
                    contents=[user_report, prompt],
                    config=grounding_config
                ),
                timeout=120.0
            )
        except asyncio.TimeoutError:
            logger.error(f"Background task {task_id} timed out after 120s.")
            # 發生超時，退回額度
            async with quota_lock:
                quota_data = load_quota_store()
                used = quota_data.get(code_clean, 1)
                quota_data[code_clean] = max(0, used - 1)
                save_quota_store(quota_data)
            
            task_ref.update({
                "status": "failed",
                "error": "AI 顧問分析超時，請確認您的網路狀況或稍後再試。"
            })
            log_invite_code_usage(code_clean, file_name, len(file_bytes), "failed", "Request Timed Out (120s)")
            return

        # Extract response text and grounding metadata (citations)
        ai_response_text = response.text
        citations = []
        
        # Extract citation metadata from grounding response
        if response.candidates and response.candidates[0].grounding_metadata:
            metadata = response.candidates[0].grounding_metadata
            if metadata.grounding_chunks:
                for chunk in metadata.grounding_chunks:
                    # Capture source title or page
                    if chunk.web:
                        citations.append({
                            "title": chunk.web.title,
                            "uri": chunk.web.uri
                        })
                    elif chunk.retrieved_context:
                        uri = chunk.retrieved_context.uri
                        # Clean up cloud storage uri to be more user-friendly
                        title = os.path.basename(uri) if uri else "內部醫學對照資料"
                        citations.append({
                            "title": title,
                            "uri": uri
                        })
                    else:
                        citations.append({
                            "title": "手冊對照基準段落",
                            "uri": "#"
                        })
                        
        # Remove duplicate citations
        unique_citations = []
        seen = set()
        for c in citations:
            if c["title"] not in seen:
                seen.add(c["title"])
                unique_citations.append(c)
                
        # Write success result to Firestore
        task_ref.update({
            "status": "success",
            "result": ai_response_text,
            "citations": unique_citations
        })
        log_invite_code_usage(code_clean, file_name, len(file_bytes), "success")
        logger.info(f"Background task {task_id} finished successfully.")

    except APIError as g_err:
        logger.error(f"Background task APIError: {str(g_err)}")
        # 發生錯誤，退回額度
        async with quota_lock:
            quota_data = load_quota_store()
            used = quota_data.get(code_clean, 1)
            quota_data[code_clean] = max(0, used - 1)
            save_quota_store(quota_data)
            
        task_ref.update({
            "status": "failed",
            "error": f"GCP API 呼叫失敗，請確認您的 Data Store 是否已建立完成且匯入資料。錯誤詳情: {str(g_err)}"
        })
        log_invite_code_usage(code_clean, file_name, len(file_bytes), "failed", str(g_err))
        
    except Exception as e:
        logger.error(f"Background task unexpected error: {str(e)}")
        # 發生錯誤，退回額度
        async with quota_lock:
            quota_data = load_quota_store()
            used = quota_data.get(code_clean, 1)
            quota_data[code_clean] = max(0, used - 1)
            save_quota_store(quota_data)
            
        task_ref.update({
            "status": "failed",
            "error": f"伺服器背景處理發生內部錯誤：{str(e)}"
        })
        log_invite_code_usage(code_clean, file_name, len(file_bytes), "failed", str(e))


# Non-blocking analysis endpoint
@app.post("/api/analyze")
async def analyze_health_report(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    question: str = Form(...),
    invite_code: str = Form(...)
):
    # Ensure client is initialized
    get_genai_client()
    
    if not GCP_DATASTORE_ID:
        raise HTTPException(
            status_code=400,
            detail="GCP_DATASTORE_ID 未設定。請參考 GCP_GUIDE.md 完成設定。"
        )
        
    # 邀請碼驗證與防暴破
    code_clean = invite_code.strip().upper() if invite_code else ""
    if code_clean not in INVITATION_LIMITS:
        await asyncio.sleep(1.0)  # 延遲防刷
        log_invite_code_usage(code_clean, file.filename, 0, "invalid_code")
        raise HTTPException(
            status_code=403,
            detail="邀請碼無效，請聯繫管理員。"
        )
        
    invite_limit = INVITATION_LIMITS[code_clean]
    async with quota_lock:
        quota_data = load_quota_store()
        used = quota_data.get(code_clean, 0)
        if used >= invite_limit:
            log_invite_code_usage(code_clean, file.filename, 0, "quota_exhausted")
            raise HTTPException(
                status_code=403,
                detail="此邀請碼的配額已用盡。"
            )
        # 先扣減額度以防併發超用
        quota_data[code_clean] = used + 1
        save_quota_store(quota_data)
        remaining = invite_limit - (used + 1)

    # Generate unique Task ID
    task_id = str(uuid.uuid4())
    logger.info(f"Received request, generated task ID: {task_id}")

    try:
        # Create Firestore placeholder doc first to establish status "processing"
        db = firestore.client()
        task_ref = db.collection("analysis_tasks").document(task_id)
        task_ref.set({
            "status": "processing",
            "created_at": firestore.SERVER_TIMESTAMP,
            "result": None,
            "citations": [],
            "error": None
        })
    except Exception as e:
        logger.error(f"Failed to create task in Firestore: {str(e)}")
        # 回退已扣除的額度
        async with quota_lock:
            quota_data = load_quota_store()
            used = quota_data.get(code_clean, 1)
            quota_data[code_clean] = max(0, used - 1)
            save_quota_store(quota_data)
        raise HTTPException(
            status_code=500,
            detail=f"無法建立任務狀態，請確認 GCP 服務帳戶已配置 Cloud Datastore User 權限。錯誤: {str(e)}"
        )

    # Read uploaded file bytes in memory
    file_bytes = await file.read()
    file_mime = file.content_type

    # Dispatch to background task execution
    background_tasks.add_task(
        async_analyze_job,
        task_id=task_id,
        file_bytes=file_bytes,
        file_mime=file_mime,
        file_name=file.filename,
        question=question,
        code_clean=code_clean,
        invite_limit=invite_limit,
        remaining=remaining
    )

    # Immediately respond with task details for polling/real-time subscription
    return JSONResponse({
        "success": True,
        "task_id": task_id,
        "status": "processing",
        "remaining_quota": remaining
    })

# Quota reset endpoint
@app.post("/api/reset")
async def reset_quota(
    token: str = Form(...)
):
    if token != ADMIN_TOKEN:
        await asyncio.sleep(1.0)  # 延遲防刷
        raise HTTPException(
            status_code=403,
            detail="管理憑證 Token 無效。"
        )
        
    async with quota_lock:
        try:
            with open(QUOTA_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump({}, f)
            logger.info("Quota store successfully reset by admin.")
            return JSONResponse({
                "success": True,
                "message": "所有邀請碼之已用配額已重置歸零。"
            })
        except Exception as e:
            logger.error(f"Failed to reset quota store: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"重置失敗：{str(e)}"
            )

# Admin Upload and Sync handbook to RAG
@app.post("/api/admin/upload-handbook")
async def upload_handbook_and_sync(
    file: UploadFile = File(...),
    token: str = Form(...)
):
    if token != ADMIN_TOKEN:
        await asyncio.sleep(1.0)  # 防暴破
        raise HTTPException(
            status_code=403,
            detail="管理憑證 Token 無效。"
        )
        
    if not GCP_BUCKET_NAME or not GCP_DATASTORE_ID:
        raise HTTPException(
            status_code=400,
            detail="GCP_BUCKET_NAME 或 GCP_DATASTORE_ID 未於環境變數配置。"
        )
        
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="目前僅支援上傳 PDF 格式的健檢對照手冊。"
        )
        
    try:
        file_bytes = await file.read()
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCP_BUCKET_NAME)
        blob = bucket.blob(file.filename)
        blob.upload_from_string(file_bytes, content_type="application/pdf")
        gcs_uri = f"gs://{GCP_BUCKET_NAME}/{file.filename}"
        logger.info(f"Admin uploaded file {file.filename} to GCS: {gcs_uri}")
    except Exception as e:
        logger.error(f"Admin failed GCS upload: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"上傳至 Google Cloud Storage 失敗：{str(e)}"
        )
        
    try:
        client = discoveryengine.DocumentServiceClient()
        parent = client.data_store_path(
            project=GCP_PROJECT_ID,
            location=GCP_LOCATION,
            data_store=GCP_DATASTORE_ID
        )
        gcs_source = discoveryengine.GcsSource(
            input_uris=[gcs_uri]
        )
        request = discoveryengine.ImportDocumentsRequest(
            parent=parent,
            gcs_source=gcs_source,
        )
        operation = client.import_documents(request=request)
        logger.info(f"Successfully triggered Vertex AI Search import. Operation: {operation.operation.name}")
        
        return JSONResponse({
            "success": True,
            "gcs_uri": gcs_uri,
            "operation_name": operation.operation.name
        })
    except Exception as e:
        logger.error(f"Admin failed to trigger Discovery Engine import: {str(e)}")
        raise HTTPException(
            status_code=502,
            detail=f"上傳成功，但觸發 Vertex AI Search 同步失敗。錯誤詳情：{str(e)}"
        )

# Query Vertex AI Search Import Operation Status
@app.get("/api/admin/operation-status")
async def get_import_operation_status(
    operation_name: str,
    token: str
):
    if token != ADMIN_TOKEN:
        await asyncio.sleep(1.0)
        raise HTTPException(
            status_code=403,
            detail="管理憑證 Token 無效。"
        )
        
    try:
        client = discoveryengine.DocumentServiceClient()
        op = client.api_client.transport.operations_client.get_operation(
            name=operation_name
        )
        
        error_msg = None
        if op.HasField("error"):
            error_msg = op.error.message
            
        return JSONResponse({
            "success": True,
            "done": op.done,
            "error": error_msg
        })
    except Exception as e:
        logger.error(f"Failed to get import operation status: {str(e)}")
        return JSONResponse({
            "success": False,
            "done": False,
            "error": str(e)
        })

# Serve Frontend static assets
# Place this at the end to avoid routing conflicts
app.mount("/", StaticFiles(directory="static", html=True), name="static")
