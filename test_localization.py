import os
import time
import json
import urllib.request
import urllib.parse
import mimetypes
import uuid
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# Load environments
load_dotenv()

# Initialize Firebase Admin
try:
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    else:
        firebase_admin.initialize_app()
    print("Firebase Admin initialized successfully.")
except ValueError:
    pass

def submit_analyze_request(url, image_path, invite_code, question, lang):
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    
    with open(image_path, "rb") as f:
        file_data = f.read()
        
    file_name = os.path.basename(image_path)
    content_type = mimetypes.guess_type(image_path)[0] or "application/octet-stream"
    
    body = []
    body.append(f"--{boundary}".encode("utf-8"))
    body.append(f'Content-Disposition: form-data; name="file"; filename="{file_name}"'.encode("utf-8"))
    body.append(f"Content-Type: {content_type}\r\n".encode("utf-8"))
    body.append(file_data)
    
    body.append(f"--{boundary}".encode("utf-8"))
    body.append(f'Content-Disposition: form-data; name="invite_code"\r\n'.encode("utf-8"))
    body.append(invite_code.encode("utf-8"))
    
    body.append(f"--{boundary}".encode("utf-8"))
    body.append(f'Content-Disposition: form-data; name="question"\r\n'.encode("utf-8"))
    body.append(question.encode("utf-8"))
    
    body.append(f"--{boundary}".encode("utf-8"))
    body.append(f'Content-Disposition: form-data; name="lang"\r\n'.encode("utf-8"))
    body.append(lang.encode("utf-8"))
    
    body.append(f"--{boundary}--".encode("utf-8"))
    
    payload = b"\r\n".join(body)
    
    req = urllib.request.Request(f"{url}/api/analyze", data=payload)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Content-Length", str(len(payload)))
    
    with urllib.request.urlopen(req, timeout=30) as response:
        resp_data = json.loads(response.read().decode("utf-8"))
        return resp_data

def wait_for_task(task_id, timeout_sec=120):
    db = firestore.client()
    doc_ref = db.collection("analysis_tasks").document(task_id)
    
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            status = data.get("status")
            if status in ["success", "failed"]:
                return data
        time.sleep(3)
    raise TimeoutError(f"Task {task_id} timed out after {timeout_sec}s")

def test_localization():
    target_url = "http://127.0.0.1:8000"
    image_path = "static/test_report.png"
    invite_code = "TEST30"
    question = "My systolic pressure is high. Explain."
    
    # 1. Test English Report Analysis
    print("\n--- Testing English Report Localization ---")
    resp_en = submit_analyze_request(target_url, image_path, invite_code, question, lang="en")
    task_id_en = resp_en["task_id"]
    print(f"Task submitted. Task ID: {task_id_en}")
    
    result_en = wait_for_task(task_id_en)
    if result_en.get("status") == "success":
        report_text = result_en.get("result", "")
        metrics = result_en.get("extracted_metrics", [])
        
        print("Verification Details:")
        # Check for English headings
        has_en_heading = "## 1. Quick Comparison" in report_text or "Quick Comparison" in report_text
        print(f"  - Has English headings: {has_en_heading}")
        
        # Check for glossary translation (e.g. check if "Systolic" or "BP" or "Diastolic" are translated)
        has_glossary_trans = any("Systolic" in str(m.get("item")) or "Glucose" in str(m.get("item")) for m in metrics)
        print(f"  - Metric names translated to English: {has_glossary_trans}")
        print(f"  - Sample Metrics: {metrics[:3]}")
        
        assert has_en_heading, "English report should contain English subheadings."
        print("English Localization Test PASSED!")
    else:
        print(f"Task Failed! Error: {result_en.get('error')}")
        raise AssertionError("Task failed instead of success.")

    # 2. Test Chinese Report Analysis
    print("\n--- Testing Traditional Chinese Report Localization ---")
    question_zh = "我的收縮壓偏高，請解釋。"
    resp_zh = submit_analyze_request(target_url, image_path, invite_code, question_zh, lang="zh")
    task_id_zh = resp_zh["task_id"]
    print(f"Task submitted. Task ID: {task_id_zh}")
    
    result_zh = wait_for_task(task_id_zh)
    if result_zh.get("status") == "success":
        report_text = result_zh.get("result", "")
        metrics = result_zh.get("extracted_metrics", [])
        
        print("Verification Details:")
        has_zh_heading = "## 1. 健檢指標快速對照" in report_text
        print(f"  - Has Chinese headings: {has_zh_heading}")
        print(f"  - Sample Metrics: {metrics[:3]}")
        
        assert has_zh_heading, "Chinese report should contain Chinese subheadings."
        print("Chinese Localization Test PASSED!")
    else:
        print(f"Task Failed! Error: {result_zh.get('error')}")
        raise AssertionError("Task failed instead of success.")

if __name__ == "__main__":
    try:
        test_localization()
    except Exception as e:
        print(f"\nTest Execution Failed: {e}")
