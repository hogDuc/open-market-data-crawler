FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libcurl4 \
    libdbus-1-3 \
    libexpat1 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libudev1 \
    libvulkan1 \
    libx11-6 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    wget \
    xdg-utils \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash chromeuser

WORKDIR /scripts

COPY --chown=chromeuser:chromeuser ./open_market_operation /scripts

RUN pip install --no-cache-dir selenium webdriver-manager pandas tqdm lxml fastapi uvicorn

RUN chmod +x /scripts/chrome-linux64/chrome /scripts/chromedriver-linux64/chromedriver

ENV PATH="/scripts/chrome-linux64:/scripts/chromedriver-linux64:${PATH}"
ENV CHROME_BIN="/scripts/chrome-linux64/chrome"
ENV CHROMEDRIVER_PATH="/scripts/chromedriver-linux64/chromedriver"
ENV STATEBANK_URL="https://dttktt.sbv.gov.vn/webcenter/portal/vi/menu/trangchu//hdtttt"

USER chromeuser

CMD ["uvicorn", "crawler_api:app", "--host", "0.0.0.0", "--port", "8000"]
