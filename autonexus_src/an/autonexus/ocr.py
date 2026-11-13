import io
from . import docs, config

class OCRUnavailable(RuntimeError):
    """Local OCR cannot run because its engine or Python dependency is missing."""

def extract_image(data:bytes):
    """Real OCR via Tesseract, then the same field extraction as text docs."""
    try:
        import pytesseract
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise OCRUnavailable("Local OCR needs the pytesseract and Pillow Python packages installed.") from exc
    try:
        executable=config.get("TESSERACT_CMD").strip()
        if executable:
            pytesseract.pytesseract.tesseract_cmd=executable
        image=Image.open(io.BytesIO(data))
        text=pytesseract.image_to_string(image)
    except UnidentifiedImageError as exc:
        raise ValueError("The uploaded file is not a readable image.") from exc
    except pytesseract.TesseractNotFoundError as exc:
        raise OCRUnavailable("Local OCR needs the Tesseract program installed and available on PATH. No cloud OCR is used.") from exc
    return {"ocr_text":text,**docs.extract(text)}
