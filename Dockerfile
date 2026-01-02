# LINE AIAvatarKit Bot - Dockerfile
# Python 3.11 slim image for smaller footprint

FROM python:3.11-slim

# メタデータ
LABEL maintainer="LINE AIAvatarKit Bot"
LABEL description="LINE Messaging API + AIAvatarKit + Dify integration"

# 環境変数の設定
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 作業ディレクトリの設定
WORKDIR /app

# システム依存パッケージのインストール
# audio処理やSSL通信に必要なパッケージを含む
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 依存関係ファイルをコピー
COPY requirements.txt .

# Pythonパッケージのインストール
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# アプリケーションコードをコピー
COPY main.py .

# ヘルスチェック設定
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# ポート公開
EXPOSE 8080

# 非rootユーザーで実行（セキュリティのため）
RUN useradd --create-home appuser
USER appuser

# アプリケーション起動
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
