import io
import docx
import PyPDF2
from fastapi import UploadFile
from app.core.logger import logger

def parse_resume(file: UploadFile) -> str:
    content = file.file.read()
    filename = file.filename.lower()
    text = ""
    try:
        if filename.endswith(".pdf"):
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            for page in reader.pages:
                text += page.extract_text() + "\n"
        elif filename.endswith(".docx"):
            doc = docx.Document(io.BytesIO(content))
            for para in doc.paragraphs:
                text += para.text + "\n"
        else:
            text = content.decode("utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"Error parsing resume: {e}")
        return "Error parsing resume."
    finally:
        file.file.seek(0)
    return text.strip()
