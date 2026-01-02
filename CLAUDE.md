# LINE AIAvatarKit Bot - 作業記録

## プロジェクト概要

LINE、Dify、AIAvatarKitを連携させたAIボットをDocker環境で動作させるプロジェクト。
複数のTTS（音声合成エンジン）に対応する拡張性の高い設計を採用。

## 作成日

2026年1月2日

## プロジェクト構成

```
line_aiavatorkit/
├── .env                  # 環境変数（API keys - gitignore対象）
├── .env.example          # 環境変数テンプレート
├── .gitignore           # Git除外設定
├── CLAUDE.md            # 作業記録（このファイル）
├── Dockerfile           # Dockerイメージ定義
├── docker-compose.yml   # Docker Compose設定
├── main.py              # メインアプリケーション
└── requirements.txt     # Python依存ライブラリ
```

## 実装内容

### 1. メインアプリケーション (`main.py`)

- **FastAPI** を使用したWebサーバー
- **LINE Messaging API** との連携（Webhookエンドポイント `/callback`）
- **Dify** LLMサービスとの統合
- **OpenAI Whisper** による音声認識
- **複数TTSエンジン対応**（ファクトリパターンで切り替え）
  - VOICEVOX（ローカル/Docker）
  - Cartesia（クラウドサービス）
  - Style-Bert-VITS2（自前サーバー）

### 2. Docker環境

- **line-bot**: メインのLINEボットアプリケーション
- **voicevox-engine**: 日本語音声合成エンジン（VOICEVOXの公式Dockerイメージ使用）

### 3. TTS切り替え方式

`.env` ファイルの `TTS_ENGINE` 変数を変更するだけでTTSエンジンを切り替え可能：

```bash
TTS_ENGINE="VOICEVOX"      # デフォルト
TTS_ENGINE="CARTESIA"      # クラウドTTS
TTS_ENGINE="STYLE_BERT_VITS2"  # 高品質日本語TTS
```

## 起動方法

### 前提条件

1. Docker および Docker Compose がインストールされていること
2. ngrok がインストールされていること（ローカル公開用）
3. 各種APIキーを取得済みであること

### 手順

#### Step 1: 環境変数の設定

```bash
# .envファイルを編集してAPIキーを設定
cp .env.example .env
# エディタで.envを開き、実際のAPIキーを入力
```

必要なAPIキー:
- `LINE_CHANNEL_ACCESS_TOKEN`: LINE Developersコンソールから取得
- `LINE_CHANNEL_SECRET`: LINE Developersコンソールから取得
- `DIFY_API_KEY`: Difyダッシュボードから取得
- `OPENAI_API_KEY`: OpenAI Platformから取得

#### Step 2: Dockerコンテナの起動

```bash
# コンテナをビルドして起動
docker-compose up -d --build

# ログを確認
docker-compose logs -f
```

#### Step 3: ngrokでローカルサーバーを公開

```bash
# 別のターミナルで実行
ngrok http 8080
```

表示されるHTTPS URL（例: `https://xxxx.ngrok.io`）をコピー。

#### Step 4: LINE Webhookの設定

1. [LINE Developers Console](https://developers.line.biz/console/) にアクセス
2. 作成したMessaging APIチャネルを選択
3. 「Messaging API設定」タブを開く
4. Webhook URL に `https://xxxx.ngrok.io/callback` を設定
5. 「Webhookの利用」をONに設定
6. 「検証」ボタンで接続確認

#### Step 5: 動作確認

1. LINEアプリでボットを友だち追加
2. テキストメッセージを送信 → テキスト返信を確認
3. 音声メッセージを送信 → 音声認識・音声合成での返信を確認

## コンテナ操作コマンド

```bash
# 起動
docker-compose up -d

# 停止
docker-compose down

# ログ確認
docker-compose logs -f

# 特定サービスのログ
docker-compose logs -f line-bot
docker-compose logs -f voicevox-engine

# 再ビルド
docker-compose up -d --build

# コンテナ内でシェル実行
docker-compose exec line-bot /bin/bash
```

## ヘルスチェック

```bash
# アプリケーションの状態確認
curl http://localhost:8080/
curl http://localhost:8080/health

# VOICEVOXエンジンの確認
curl http://localhost:50021/speakers
```

## トラブルシューティング

### VOICEVOXの起動が遅い

VOICEVOXエンジンは初回起動時にモデルのロードで1分程度かかることがあります。
`docker-compose logs -f voicevox-engine` でログを確認してください。

### APIキーエラー

`.env` ファイルのAPIキーがプレースホルダー（`YOUR_XXX`）のままになっていないか確認してください。
`/health` エンドポイントで `bot_initialized: false` の場合、APIキーの設定に問題があります。

### ngrokの制限

無料版ngrokはURLが再起動のたびに変わります。
その場合はLINE DevelopersコンソールでWebhook URLを更新してください。

## 次のステップ

1. **API Keyの取得**: LINE、Dify、OpenAI各サービスでAPIキーを取得
2. **ローカルテスト**: ngrokを使って実際のLINEとの通信をテスト
3. **GCP Cloud Runデプロイ**: 本番環境へのデプロイ

## 参考リンク

- [AIAvatarKit GitHub](https://github.com/uezo/aiavatarkit)
- [LINE Developers](https://developers.line.biz/console/)
- [Dify](https://dify.ai/)
- [OpenAI Platform](https://platform.openai.com/)
- [VOICEVOX](https://voicevox.hiroshiba.jp/)
- [VOICEVOX Docker Hub](https://hub.docker.com/r/voicevox/voicevox_engine)

## 技術スタック

- **言語**: Python 3.11
- **フレームワーク**: FastAPI, uvicorn
- **AI/ML**: AIAvatarKit, OpenAI Whisper
- **LLM**: Dify
- **TTS**: VOICEVOX, Cartesia, Style-Bert-VITS2
- **インフラ**: Docker, Docker Compose
- **外部サービス**: LINE Messaging API
