from PIL import Image
import codecs
import pytesseract
IMAGE_PATH = "image.png"

def task_func(filename=IMAGE_PATH, from_encoding="cp1251", to_encoding="utf8"):
    try:
        with Image.open(filename) as img:
            ocr_text = pytesseract.image_to_string(img)
            if ocr_text:
                return ocr_text.encode(from_encoding).decode(to_encoding)
    except Exception:
        pass

    try:
        with Image.open(filename) as img:
            comment = img.info.get("comment")
            if comment:
                if isinstance(comment, bytes):
                    return comment.decode(from_encoding)
                else:
                    return comment.encode(from_encoding).decode(to_encoding)
    except Exception:
        pass

    return ""
