import os
import logging
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError

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
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

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

# Analysis endpoint
@app.post("/api/analyze")
async def analyze_health_report(
    file: UploadFile = File(...),
    question: str = Form(...)
):
    # Ensure client is initialized
    ai_client = get_genai_client()
    
    if not GCP_DATASTORE_ID:
        raise HTTPException(
            status_code=400,
            detail="GCP_DATASTORE_ID 未設定。請參考 GCP_GUIDE.md 完成設定。"
        )
        
    try:
        # Read the uploaded file bytes
        file_bytes = await file.read()
        file_mime = file.content_type
        
        logger.info(f"Received file: {file.filename}, type: {file_mime}, size: {len(file_bytes)} bytes")
        
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
            "請遵循以下規則回答：\n"
            "1. 你的回答必須緊密基於知識庫事實，提供醫學數據的衛教解釋與日常健康管理建議（如飲食、運動、生活習慣調整）。\n"
            "2. 回答必須有條理、清晰易讀，並使用 Markdown 格式呈現。\n"
            "3. 你的回答末尾務必加上以下免責聲明：\n"
            "   『【免責聲明】本分析僅供個人健康管理參考，不具備醫療診斷效力。若您的數據異常或有身體不適，請務必諮詢專業醫師進行診斷與治療。』\n"
            "4. 如果相關標準或答案在知識庫中完全找不到，請禮貌地告知使用者，並引導使用者諮詢醫生，不要盲目猜測或虛構數據。"
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
        
        # Call Gemini model
        logger.info(f"Calling Gemini model '{GEMINI_MODEL}' with grounding...")
        response = ai_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[user_report, prompt],
            config=grounding_config
        )
        
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
                
        return JSONResponse({
            "success": True,
            "analysis": ai_response_text,
            "citations": unique_citations
        })
        
    except APIError as g_err:
        logger.error(f"Google API Error: {str(g_err)}")
        return JSONResponse(
            status_code=502,
            content={
                "success": False,
                "detail": f"GCP API 呼叫失敗，請確認您的 Data Store 是否已建立完成且匯入資料。錯誤詳情: {str(g_err)}"
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "detail": f"伺服器內部錯誤：{str(e)}"
            }
        )

# Serve Frontend static assets
# Place this at the end to avoid routing conflicts
app.mount("/", StaticFiles(directory="static", html=True), name="static")
