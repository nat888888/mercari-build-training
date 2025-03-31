# 1. Pythonの公式イメージ（Alpineベース）を使う
FROM alpine

FROM python:3.10

RUN addgroup -S mercari && adduser -S trainee -G mercari
# RUN chown -R trainee:mercari /path/to/db

USER trainee


# `uvicorn` をインストール
RUN pip install --no-cache-dir uvicorn fastapi

# 3. 作業ディレクトリを /app に設定
WORKDIR /app

# 4. アプリのファイルをコピー
COPY . /app

# 5. FastAPIアプリを起動する
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]

# ベースイメージをAlpine + Pythonのものにする
FROM python:3.10-alpine

