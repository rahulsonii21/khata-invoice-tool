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
# --retry handles transient network blips during the build (seen in practice);
# a User-Agent header avoids some CDNs' bot-blocking heuristics on bare requests.
RUN TESSDATA_DIR=$(find / -type d -name tessdata 2>/dev/null | head -1) && \
    echo "Using tessdata dir: $TESSDATA_DIR" && \
    curl -fsSL --retry 5 --retry-delay 3 -A "Mozilla/5.0 (Docker build)" \
        -o "$TESSDATA_DIR/eng.traineddata" \
        https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/eng.traineddata && \
    curl -fsSL --retry 5 --retry-delay 3 -A "Mozilla/5.0 (Docker build)" \
        -o "$TESSDATA_DIR/hin.traineddata" \
        https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/hin.traineddata && \
    test -s "$TESSDATA_DIR/eng.traineddata" && test -s "$TESSDATA_DIR/hin.traineddata"

# Devanagari-capable font, needed to render Hindi text when generating bill
# images. Committed directly into the repo (backend/assets/fonts/) rather than
# downloaded during build - a prior attempt to fetch it from GitHub at build
# time failed consistently on Render's build network (but not elsewhere),
# so removing that external dependency entirely is the reliable fix.
# (COPY . . below brings this in along with the rest of the app.)

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
