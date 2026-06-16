FROM python:3.10

# 作業ディレクトリの設定
WORKDIR /app

# 必要なパッケージ一覧をコピーしてインストール
COPY requirement.txt .
RUN pip install --no-cache-dir -r requirement.txt

# アプリケーションのコードをすべてコピー
COPY . .

# FastAPIサーバーを起動（Hugging Faceの指定ポート 7860）
CMD ["uvicorn", "Orbit_app:app", "--host", "0.0.0.0", "--port", "7860"]