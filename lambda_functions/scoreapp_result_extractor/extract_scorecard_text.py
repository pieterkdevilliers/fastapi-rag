import os
import requests
import fitz  # PyMuPDF

FASTAPI_SCORECARD_CALLBACK_URL = os.environ["FASTAPI_CALLBACK_URL"]
INTERNAL_API_KEY = os.environ["INTERNAL_API_KEY"]

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    text_content = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            text_content.append(page.get_text("text"))
    return "\n".join(text_content)

def handler(event, context):
    """
    Lambda event:
    {
        "scorecardresult_id": 123,
        "report_url": "https://example.com/file.pdf"
    }
    """
    scorecard_id = event.get("scorecardresult_id")
    pdf_url = event.get("report_url")

    callback_payload = {"scorecardresult_id": scorecard_id}

    if not scorecard_id or not pdf_url:
        callback_payload.update({
            "status": "FAILED",
            "error_message": "Missing scorecardresult_id or report_url"
        })
        send_callback(callback_payload)
        return callback_payload

    try:
        # Fetch PDF
        response = requests.get(pdf_url, timeout=15)
        response.raise_for_status()
        pdf_bytes = response.content

        # Extract text
        extracted_text = extract_text_from_pdf(pdf_bytes)

        if not extracted_text.strip():
            raise ValueError("No text extracted from PDF.")

        # Success payload
        callback_payload.update({
            "status": "COMPLETED",
            "extracted_report_text": extracted_text[:65000]  # safeguard length
        })

    except Exception as e:
        callback_payload.update({
            "status": "FAILED",
            "error_message": str(e)[:1024]  # truncate error
        })

    # Always send callback
    send_callback(callback_payload)

    return callback_payload


def send_callback(payload: dict):
    headers = {
        "Content-Type": "application/json",
        "X-Internal-API-Key": INTERNAL_API_KEY
    }
    try:
        response = requests.post(
            FASTAPI_CALLBACK_URL,
            json=payload,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        print(f"Callback successful for scorecardresult_id {payload.get('scorecardresult_id')}")
    except requests.exceptions.RequestException as e:
        print(f"FATAL: Could not send callback to FastAPI: {e}")
        raise e
