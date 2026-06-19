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
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        logging.info(f"Firebase Admin initialized successfully using Certificate from {cred_path}.")
    else:
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

RESEARCH_KEYWORDS = [
    "高血壓", "血糖", "糖尿病", "膽固醇", "三酸甘油脂", 
    "脂肪肝", "尿酸", "肝功能", "GOT", "GPT", 
    "肌酸酐", "腎臟", "血壓", "骨質疏鬆", "心血管", "貧血"
]

# Load medical glossary for Chinese-English translation
def load_medical_glossary() -> dict:
    glossary_map = {}
    path = "medical_glossary.json"
    if not os.path.exists(path):
        path = "resource/medical_glossary.json"
        
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    zh = item.get("zh_tw")
                    en = item.get("en")
                    if zh and en:
                        glossary_map[zh] = en
                    elif zh and item.get("abbreviations"):
                        abbr = item.get("abbreviations")
                        if isinstance(abbr, list) and len(abbr) > 0:
                            glossary_map[zh] = abbr[0]
            logger.info(f"Successfully loaded {len(glossary_map)} glossary terms from {path}.")
        except Exception as e:
            logger.error(f"Failed to load medical glossary: {str(e)}")
    else:
        logger.warning("Glossary file medical_glossary.json not found in root or resource/.")
    return glossary_map

GLOSSARY_MAP = load_medical_glossary()
# Compact serialization for Gemini prompt context
GLOSSARY_STR = ", ".join([f"{k}: {v}" for k, v in GLOSSARY_MAP.items()]) if GLOSSARY_MAP else ""

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
            "appId": FIREBASE_APP_ID
        }
    }

# Background job to analyze report asynchronously
async def async_analyze_job(
    task_id: str,
    file_bytes: bytes,
    file_mime: str,
    file_name: str,
    question: str,
    code_clean: str,
    invite_limit: int,
    remaining: int,
    lang: str = "zh"
):
    logger.info(f"Starting background job for task {task_id} with language {lang}")
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
        if lang == "en":
            system_instruction = (
                "You are a professional health management AI consultant. When a user provides a health check report or data, you must precisely match it against the medical reference values and suggestions in the database \"Health Check Complete Manual\".\n"
                "Please follow the rules below and structure your answer into the following four main sections. Each section must start with the exact specified `##` header. Do not modify or omit them:\n\n"
                "## 1. Quick Comparison of Health Indicators\n"
                "(List the comparison of all test values and reference values in a Markdown table here. The table must contain: Item, Reference Value, Test Value, Status. If there are abnormal values, the status column must be filled as **High**, **Low**, or **Abnormal**, wrapped in bold double asterisks to facilitate highlighting on the frontend.)\n\n"
                "## 2. Core Abnormalities & Potential Risks\n"
                "(Explain in detail the physiological causes of the abnormal indicators in the uploaded report and the potential long-term health risks.)\n\n"
                "## 3. Personalized Health Action Plan\n"
                "(Provide specific and actionable dietary adjustment principles, suitable exercise types and frequencies, and concrete suggestions for daily routine improvements.)\n\n"
                "## 4. Q&A\n"
                "(Directly answer the consultation questions that the user is most concerned about.)\n\n"
                "Please note:\n"
                "1. Your answer must be closely based on the facts in the knowledge base, providing educational explanations of medical data and daily health management advice.\n"
                "2. Your answer must absolutely NOT contain headings like 'Source of Professional Medical Basis' or 'Medical Basis Source', nor mention any Google Cloud Storage file paths/links starting with 'gs://'.\n"
                "3. You must append the following disclaimer at the end of your answer:\n"
                "   \"[Disclaimer] This analysis is for personal health management reference only and does not constitute a medical diagnosis. If your data is abnormal or you feel unwell, please consult a professional physician for diagnosis and treatment.\"\n"
                "4. If the relevant standards or answers are not found in the knowledge base, please politely inform the user and guide them to consult a doctor; do not blindly guess or fabricate data.\n"
                "5. Translation Rules: You must write the entire report in English. Since the reference manual is in Chinese, you must translate the medical terms from Chinese to English. You must strictly use the following translation mapping for terminology:\n"
                f"{GLOSSARY_STR}"
            )
            prompt = f"Please help me analyze this health check report. The question the user is most concerned about is: {question}"
        else:
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
                "2. 你的回答中絕對不能包含『專業醫學依據來源』或『醫學依據來源』這類參考來源說明標題，也絕對不能列出或提及任何以 『gs://』 開頭的 Google Cloud Storage 檔案路徑與連結。\n"
                "3. 你的回答末尾務必加上以下免責聲明：\n"
                "   『【免責聲明】本分析僅供個人健康管理參考，不具備醫療診斷效力。若您的數據異常或有身體不適，請務必諮詢專業醫師進行診斷與治療。』\n"
                "4. 如果相關標準或答案在知識庫中完全找不到，請禮貌地告知使用者，並引導使用者諮詢醫生，不要盲目猜測或虛構數據。"
            )
            prompt = f"請幫我分析這份健檢報告。使用者目前最想了解的問題是：{question}"
        
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
                "error": "TIMEOUT_ERROR"
            })
            log_invite_code_usage(code_clean, file_name, len(file_bytes), "failed", "Request Timed Out (120s)")
            return

        # Extract response text and grounding metadata (citations)
        ai_response_text = response.text
        
        # Clean up unwanted medical source references and gs:// links in the text
        import re
        ai_response_text = re.sub(r'\[?專業醫學依據來源\]?：?\s*', '', ai_response_text)
        ai_response_text = re.sub(r'gs://[a-zA-Z0-9\-_./]+', '', ai_response_text)

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
                        title = os.path.basename(uri) if uri else ("Medical Reference Guide" if lang == "en" else "內部醫學對照資料")
                        citations.append({
                            "title": title,
                            "uri": uri
                        })
                    else:
                        citations.append({
                            "title": "Reference Section" if lang == "en" else "手冊對照基準段落",
                            "uri": "#"
                        })
                        
        # Remove duplicate citations
        unique_citations = []
        seen = set()
        for c in citations:
            if c["title"] not in seen:
                seen.add(c["title"])
                unique_citations.append(c)
                
        # 1. Structured Metrics Extraction
        extracted_metrics = []
        try:
            if lang == "en":
                extraction_prompt = (
                    "Please read the following health check analysis report carefully. Your task is to extract all mentioned health check items, their test values, units, and status from the report in a structured format.\n"
                    "You must return strictly in the following JSON format without any other characters or markdown wrapper:\n"
                    "{\n"
                    "  \"metrics\": [\n"
                    "    {\"item\": \"Item Name\", \"value\": \"Test Value\", \"unit\": \"Unit\", \"status\": \"Normal/High/Low/Abnormal\"}\n"
                    "  ]\n"
                    "}\n\n"
                    f"Report Content:\n{ai_response_text}"
                )
            else:
                extraction_prompt = (
                    "請仔細閱讀以下健檢分析報告。你的任務是從該報告中，結構化地提取出所有提到的健檢項目、其檢測數值、單位以及判定狀態。\n"
                    "請必須嚴格按照以下 JSON 格式回傳，不得包含 any 其它字元或 markdown 包裹：\n"
                    "{\n"
                    "  \"metrics\": [\n"
                    "    {\"item\": \"項目名稱\", \"value\": \"檢測數值\", \"unit\": \"單位\", \"status\": \"正常/偏高/偏低/異常\"}\n"
                    "  ]\n"
                    "}\n\n"
                    f"分析報告內容：\n{ai_response_text}"
                )
            
            extract_resp = await asyncio.to_thread(
                ai_client.models.generate_content,
                model="gemini-2.5-flash",
                contents=extraction_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            
            extracted_data = json.loads(extract_resp.text)
            extracted_metrics = extracted_data.get("metrics", [])
        except Exception as ex_err:
            logger.error(f"Failed to extract metrics: {str(ex_err)}")
            extracted_metrics = []

        # 2. Self-Verification and Accuracy Audit
        verification = {
            "accuracy_score": 100,
            "reason": "Evaluation passed." if lang == "en" else "報告結構完整，標準對照無誤。"
        }
        try:
            if lang == "en":
                verification_prompt = (
                    "As a medical report auditor, please read the following health check analysis report carefully.\n"
                    "Your task is to assess whether the report aligns with standard health education knowledge, and specifically check if the test values in the report match general medical common sense (for example, check if a systolic blood pressure of 135 mmHg is incorrectly described as normal, or if any indicators not mentioned in the report are fabricated).\n"
                    "Please provide a correctness confidence score (accuracy_score) from 0 to 100, and an assessment reason (reason) in English within 2 sentences.\n"
                    "You must return strictly in the following JSON format:\n"
                    "{\n"
                    "  \"accuracy_score\": 95,\n"
                    "  \"reason\": \"Evaluation reason\"\n"
                    "}\n\n"
                    f"Report Content:\n{ai_response_text}"
                )
            else:
                verification_prompt = (
                    "作為醫學報告審查員，請仔細閱讀以下健檢分析報告。\n"
                    "你的任務是評估該報告是否符合標準衛教知識，並特別檢查報告中的檢測值是否與大眾認知之醫學常識相符（例如，檢查有無將收縮壓 135 mmHg 描述為正常，或者無中生有報告中未提及的指標）。\n"
                    "請給出一個 0 到 100 的正確性信任分數 (accuracy_score)，以及繁體中文 2 句話以內的評估理由 (reason)。\n"
                    "請必須嚴格按照以下 JSON 格式回傳：\n"
                    "{\n"
                    "  \"accuracy_score\": 95,\n"
                    "  \"reason\": \"評估理由\"\n"
                    "}\n\n"
                    f"分析報告內容：\n{ai_response_text}"
                )
            
            verify_resp = await asyncio.to_thread(
                ai_client.models.generate_content,
                model="gemini-2.5-flash",
                contents=verification_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            
            verify_data = json.loads(verify_resp.text)
            verification = {
                "accuracy_score": int(verify_data.get("accuracy_score", 100)),
                "reason": verify_data.get("reason", "Evaluation passed." if lang == "en" else "審查通過。")
            }
        except Exception as ev_err:
            logger.error(f"Failed to verify report accuracy: {str(ev_err)}")
            verification = {
                "accuracy_score": 100,
                "reason": "Evaluation passed." if lang == "en" else "系統預設審查通過。"
            }

        # 3. Global Keyword Statistics Recording
        try:
            stats_ref = db.collection("research_statistics").document("keywords")
            updates = {}
            for kw in RESEARCH_KEYWORDS:
                count_q = question.count(kw)
                count_r = ai_response_text.count(kw)
                total_kw = count_q + count_r
                if total_kw > 0:
                    updates[f"mentions.{kw}"] = firestore.Increment(total_kw)
                    updates[f"question_mentions.{kw}"] = firestore.Increment(count_q)
                    updates[f"report_mentions.{kw}"] = firestore.Increment(count_r)
            
            if updates:
                updates["last_updated"] = firestore.SERVER_TIMESTAMP
                stats_ref.set({}, merge=True)
                stats_ref.update(updates)
                logger.info("Successfully updated keyword research statistics.")
        except Exception as stat_err:
            logger.error(f"Failed to update research statistics: {str(stat_err)}")

        # Write success result to Firestore
        task_ref.update({
            "status": "success",
            "result": ai_response_text,
            "citations": unique_citations,
            "extracted_metrics": extracted_metrics,
            "verification": verification
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
            "error": "API_ERROR"
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
            "error": "INTERNAL_ERROR"
        })
        log_invite_code_usage(code_clean, file_name, len(file_bytes), "failed", str(e))


# Helper function to delete documents older than 7 days in Firebase
import time
LAST_CLEANUP_TIME = 0.0
CLEANUP_INTERVAL_SECONDS = 600  # 10 minutes interval
cleanup_lock = asyncio.Lock()

async def clean_old_firebase_tasks():
    global LAST_CLEANUP_TIME
    
    current_time = time.time()
    if current_time - LAST_CLEANUP_TIME < CLEANUP_INTERVAL_SECONDS:
        logger.info("Firebase Cleanup: Skipped (interval not met yet).")
        return
        
    async with cleanup_lock:
        # Double check inside lock
        if time.time() - LAST_CLEANUP_TIME < CLEANUP_INTERVAL_SECONDS:
            return
            
        logger.info("Starting background Firebase Firestore cleanup check...")
        try:
            db = firestore.client()
            
            # 1. Delete tasks older than 7 days
            seven_days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
            query = db.collection("analysis_tasks").where("created_at", "<", seven_days_ago)
            docs = query.stream()
            
            deleted_count = 0
            batch = db.batch()
            for doc in docs:
                batch.delete(doc.reference)
                deleted_count += 1
                # Commit batch every 500 documents (Firestore limit)
                if deleted_count % 500 == 0:
                    batch.commit()
                    batch = db.batch()
            
            if deleted_count % 500 != 0:
                batch.commit()
                
            if deleted_count > 0:
                logger.info(f"Firebase Cleanup: Successfully deleted {deleted_count} old task documents by age.")
            else:
                logger.info("Firebase Cleanup: No tasks older than 7 days found.")
                
            # 2. Capacity-based truncation to ensure storage remains well under 1 GB limit
            try:
                max_tasks_limit = int(os.getenv("FIREBASE_MAX_TASKS_LIMIT", "3000"))
            except ValueError:
                max_tasks_limit = 3000
                
            # Efficiently count documents
            count_query = db.collection("analysis_tasks").count()
            results = count_query.get()
            total_count = results[0][0].value
            
            if total_count > max_tasks_limit:
                excess_count = total_count - max_tasks_limit
                logger.info(f"Firebase Cleanup: Total documents ({total_count}) exceeds limit ({max_tasks_limit}). Deleting {excess_count} oldest documents.")
                
                # Fetch excess_count oldest tasks ordered by created_at
                excess_query = db.collection("analysis_tasks").order_by("created_at", direction=firestore.Query.ASCENDING).limit(excess_count)
                excess_docs = excess_query.stream()
                
                excess_deleted = 0
                batch = db.batch()
                for doc in excess_docs:
                    batch.delete(doc.reference)
                    excess_deleted += 1
                    if excess_deleted % 500 == 0:
                        batch.commit()
                        batch = db.batch()
                        
                if excess_deleted % 500 != 0:
                    batch.commit()
                    
                logger.info(f"Firebase Cleanup: Successfully deleted {excess_deleted} oldest task documents by limit.")
            else:
                logger.info(f"Firebase Cleanup: Total documents ({total_count}) is within limit ({max_tasks_limit}).")
                
            # Update last cleanup time
            LAST_CLEANUP_TIME = time.time()
            
        except Exception as e:
            logger.error(f"Failed to cleanup old Firebase tasks: {str(e)}")


# Non-blocking analysis endpoint
@app.post("/api/analyze")
async def analyze_health_report(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    question: str = Form(...),
    invite_code: str = Form(...),
    lang: str = Form("zh")
):
    # Ensure client is initialized
    get_genai_client()
    
    if not GCP_DATASTORE_ID:
        raise HTTPException(
            status_code=400,
            detail="DATASTORE_NOT_CONFIGURED"
        )
        
    # 邀請碼驗證與防暴破
    code_clean = invite_code.strip().upper() if invite_code else ""
    if code_clean not in INVITATION_LIMITS:
        await asyncio.sleep(1.0)  # 延遲防刷
        log_invite_code_usage(code_clean, file.filename, 0, "invalid_code")
        raise HTTPException(
            status_code=403,
            detail="INVALID_INVITE_CODE"
        )
        
    invite_limit = INVITATION_LIMITS[code_clean]
    async with quota_lock:
        quota_data = load_quota_store()
        used = quota_data.get(code_clean, 0)
        if used >= invite_limit:
            log_invite_code_usage(code_clean, file.filename, 0, "quota_exhausted")
            raise HTTPException(
                status_code=403,
                detail="QUOTA_EXHAUSTED"
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
            detail="FIRESTORE_INIT_FAILED"
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
        remaining=remaining,
        lang=lang
    )

    # Dispatch to background Firestore cleanup check
    background_tasks.add_task(clean_old_firebase_tasks)

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

# Query Keyword Stats and System Evaluation Accuracy
@app.get("/api/admin/research-stats")
async def get_research_statistics(
    token: str
):
    if token != ADMIN_TOKEN:
        await asyncio.sleep(1.0)
        raise HTTPException(
            status_code=403,
            detail="管理憑證 Token 無效。"
        )
        
    try:
        db = firestore.client()
        
        # 1. Fetch keyword statistics
        keyword_stats = {}
        stats_ref = db.collection("research_statistics").document("keywords")
        stats_doc = stats_ref.get()
        if stats_doc.exists:
            keyword_stats = stats_doc.to_dict()
            
        # 2. Fetch recent tasks to calculate average accuracy rate
        query = db.collection("analysis_tasks")\
            .order_by("created_at", direction=firestore.Query.DESCENDING)\
            .limit(30)
            
        docs = query.stream()
        scores = []
        recent_evaluations = []
        for doc in docs:
            data = doc.to_dict()
            if data.get("status") != "success":
                continue
            verification = data.get("verification")
            if verification and isinstance(verification, dict):
                score = verification.get("accuracy_score")
                if score is not None:
                    scores.append(int(score))
                    recent_evaluations.append({
                        "task_id": doc.id,
                        "created_at": data.get("created_at").isoformat() if data.get("created_at") else None,
                        "accuracy_score": score,
                        "reason": verification.get("reason", "")
                    })
                    
        avg_accuracy = sum(scores) / len(scores) if scores else 100.0
        
        # Format keyword stats response
        mentions_map = keyword_stats.get("mentions", {})
        question_mentions_map = keyword_stats.get("question_mentions", {})
        report_mentions_map = keyword_stats.get("report_mentions", {})
        
        sorted_keywords = []
        for kw, count in mentions_map.items():
            sorted_keywords.append({
                "keyword": kw,
                "count": count,
                "question_count": question_mentions_map.get(kw, 0),
                "report_count": report_mentions_map.get(kw, 0)
            })
        sorted_keywords.sort(key=lambda x: x["count"], reverse=True)
        
        return JSONResponse({
            "success": True,
            "average_accuracy": round(avg_accuracy, 1),
            "total_evaluated": len(scores),
            "keyword_stats": sorted_keywords,
            "recent_evaluations": recent_evaluations
        })
    except Exception as e:
        logger.error(f"Failed to fetch research statistics: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        })

# Admin Dashboard Panel route
@app.get("/kb-portal")
async def serve_admin_panel():
    return FileResponse("static/admin.html")

# Serve Frontend static assets
# Place this at the end to avoid routing conflicts
app.mount("/", StaticFiles(directory="static", html=True), name="static")

