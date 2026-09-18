import io
import os
from functools import wraps
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from markitdown import MarkItDown

load_dotenv()

APP_VERSION = os.getenv("APP_VERSION")
if not APP_VERSION:
    try:
        with open(os.path.join(os.path.dirname(__file__), "VERSION")) as f:
            APP_VERSION = f.read().strip()
    except OSError:
        APP_VERSION = "dev"

API_KEY = os.getenv("API_KEY")
MAX_DOWNLOAD_BYTES = int(os.getenv("MAX_DOWNLOAD_BYTES", 50 * 1024 * 1024))
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", 30))

DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".csv",
    ".tsv",
    ".json",
    ".xml",
    ".html",
    ".htm",
    ".txt",
    ".md",
    ".rst",
    ".rtf",
    ".epub",
    ".odt",
    ".ods",
    ".odp",
    ".msg",
}

DOCUMENT_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/json",
    "application/xml",
    "application/epub+zip",
    "application/rtf",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
    "application/vnd.ms-outlook",
}

app = Flask(__name__)
markitdown = MarkItDown()


def require_api_key(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not API_KEY:
            return jsonify(error="server_api_key_not_configured"), 500
        provided = request.headers.get("X-API-Key", "")
        if provided != API_KEY:
            return jsonify(error="unauthorized"), 401
        return view(*args, **kwargs)

    return wrapped


def check_document(extension, mime):
    extension = (extension or "").lower()
    mime = (mime or "").split(";")[0].strip().lower()

    if extension in DOCUMENT_EXTENSIONS:
        return True
    if mime in DOCUMENT_MIME_TYPES:
        return True
    if mime.startswith("text/"):
        return True
    return False


@app.get("/health")
def health():
    return jsonify(status="ok", version=APP_VERSION)


@app.post("/convert")
@require_api_key
def convert():
    payload = request.get_json(silent=True) or {}
    url = payload.get("url")
    if not url or not isinstance(url, str):
        return jsonify(error="url_required"), 400

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return jsonify(error="invalid_url_scheme"), 400

    try:
        upstream = requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT)
        upstream.raise_for_status()
    except requests.RequestException as exc:
        return jsonify(error="download_failed", detail=str(exc)), 502

    extension = os.path.splitext(parsed.path)[1]
    mime = upstream.headers.get("Content-Type", "")

    if not check_document(extension, mime):
        upstream.close()
        return (
            jsonify(
                error="unsupported_document_type",
                extension=extension or None,
                mime=mime or None,
            ),
            415,
        )

    content = bytearray()
    try:
        for chunk in upstream.iter_content(chunk_size=64 * 1024):
            content.extend(chunk)
            if len(content) > MAX_DOWNLOAD_BYTES:
                return jsonify(error="file_too_large"), 413
    finally:
        upstream.close()

    try:
        result = markitdown.convert_stream(
            io.BytesIO(bytes(content)),
            file_extension=extension or None,
            url=url,
        )
    except Exception as exc:
        return jsonify(error="conversion_failed", detail=str(exc)), 422

    return Response(result.markdown, mimetype="text/markdown; charset=utf-8")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
