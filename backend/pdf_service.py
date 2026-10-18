import io
import re
from typing import List, Dict, Any, Tuple
from pypdf import PdfReader
from fastapi import HTTPException, UploadFile

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

def validate_pdf_file(file: UploadFile, content: bytes) -> None:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Please upload a standard PDF document (.pdf)."
        )
    
    if len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty (0 bytes). Please upload a valid PDF note."
        )
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum upload size of {MAX_FILE_SIZE // (1024 * 1024)}MB. Please upload a smaller document."
        )

def extract_pdf_data(content: bytes) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Extracts text page by page from PDF bytes.
    Returns: (pages_data, total_page_count, total_word_count)
    """
    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not parse the PDF file. It may be corrupt or encrypted. Details: {str(e)}"
        )
    
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="The uploaded PDF is password-protected. Please upload an unprotected document."
            )
            
    page_count = len(reader.pages)
    if page_count == 0:
        raise HTTPException(
            status_code=400,
            detail="The PDF contains 0 pages."
        )
        
    pages_data = []
    total_words = 0
    
    for i, page in enumerate(reader.pages):
        page_num = i + 1
        raw_text = ""
        try:
            raw_text = page.extract_text() or ""
        except Exception:
            raw_text = ""
            
        # Clean up whitespace
        clean_text = re.sub(r'[ \t]+', ' ', raw_text)
        clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip()
        
        words = clean_text.split()
        word_count = len(words)
        total_words += word_count
        
        pages_data.append({
            "page": page_num,
            "text": clean_text,
            "word_count": word_count
        })
        
    return pages_data, page_count, total_words

def split_into_chunks(pages_data: List[Dict[str, Any]], chunk_size: int = 150) -> List[Dict[str, Any]]:
    """
    Splits page text into smaller search chunks with page metadata for accurate RAG citations.
    """
    chunks = []
    chunk_id = 0
    
    for page in pages_data:
        page_num = page["page"]
        text = page["text"]
        
        if not text:
            continue
            
        # Split into paragraphs or sentences
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [text]
            
        for para in paragraphs:
            words = para.split()
            if len(words) <= chunk_size:
                chunks.append({
                    "id": chunk_id,
                    "page": page_num,
                    "text": para
                })
                chunk_id += 1
            else:
                # Sub-chunk by word window
                for w_idx in range(0, len(words), chunk_size - 30):
                    sub_text = " ".join(words[w_idx:w_idx + chunk_size])
                    chunks.append({
                        "id": chunk_id,
                        "page": page_num,
                        "text": sub_text
                    })
                    chunk_id += 1
                    
    return chunks
