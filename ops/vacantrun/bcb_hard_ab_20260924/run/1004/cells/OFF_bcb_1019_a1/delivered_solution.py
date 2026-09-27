from PIL import Image
import codecs
import pytesseract
IMAGE_PATH = "image.png"
def task_func(filename=IMAGE_PATH, from_encoding="cp1251", to_encoding="utf8"):
    try:
        img = Image.open(filename)
        ocr_text = pytesseract.image_to_string(img)
        
        if ocr_text and isinstance(ocr_text, str):
            return ocr_text.encode(from_encoding).decode(to_encoding)
        else:
            info = getattr(img, "info", {})
            comment = ""
            if hasattr(info, 'get'):
                comment = info.get("comment", "")
            elif isinstance(info, dict):
                comment = info.get("comment", "")

            if isinstance(comment, bytes):
                return comment.decode(from_encoding).encode(to_encoding).decode(to_encoding)
            elif isinstance(comment, str):
                return comment.encode(from_encoding).decode(to_encoding)
            else:
                return ""
    except (UnicodeDecodeError, LookupError):
        raise ValueError("Incorrect encodings provided for the text or comment conversion.")
    except Exception:
        try:
            img = Image.open(filename)
            info = getattr(img, "info", {})
            comment = ""
            if hasattr(info, 'get'):
                comment = info.get("comment", "")
            elif isinstance(info, dict):
                comment = info.get("comment", "")

            if isinstance(comment, bytes):
                return comment.decode(from_encoding).encode(to_encoding).decode(to_encoding)
            elif isinstance(comment, str):
                return comment.encode(from_encoding).decode(to_encoding)
            else:
                return ""
        except (UnicodeDecodeError, LookupError):
            raise ValueError("Incorrect encodings provided for the text or comment conversion.")
        except Exception:
            return ""
