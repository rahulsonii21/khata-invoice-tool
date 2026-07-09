# Render's native Python runtime can't install system-level packages
# (no apt-get access), but Tesseract OCR needs the actual binary + language
# data, not just the Python wrapper. Docker is the reliable way to get that.
FROM python:3.12-slim

# Tesseract binary + English/Hindi language packs
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Swap in the higher-accuracy "best" LSTM models instead of the default
# fast/legacy ones bundled by apt - meaningfully better recognition,
# especially for the Hindi/Devanagari script.
RUN TESSDATA_DIR=$(find / -type d -name tessdata 2>/dev/null | head -1) && \
    echo "Using tessdata dir: $TESSDATA_DIR" && \
    curl -fsSL -o "$TESSDATA_DIR/eng.traineddata" \
        https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/eng.traineddata && \
    curl -fsSL -o "$TESSDATA_DIR/hin.traineddata" \
        https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/hin.traineddata && \
    test -s "$TESSDATA_DIR/eng.traineddata" && test -s "$TESSDATA_DIR/hin.traineddata"

# Devanagari-capable font, needed to render Hindi text when generating bill images
RUN mkdir -p /app/assets/fonts && \
    curl -fsSL -o /app/assets/fonts/NotoSansDevanagari.ttf \
        "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansdevanagari/NotoSansDevanagari%5Bwdth%2Cwght%5D.ttf" && \
    test -s /app/assets/fonts/NotoSansDevanagari.ttf

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
