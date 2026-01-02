# LINE AIAvatarKit Bot - 作業記録

## プロジェクト概要

LINE、Dify、AIAvatarKitを連携させたAIボットをDocker環境で動作させるプロジェクト。
AIAvatarKit v0.8.2の最新機能を活用し、複数のLLM/TTSエンジンに対応する拡張性の高い設計を採用。

## バージョン情報

- **初回作成日**: 2026年1月2日
- **最終更新日**: 2026年1月2日
- **AIAvatarKit**: v0.8.2対応
- **アプリバージョン**: 2.0.0

## プロジェクト構成

```
line_aiavatorkit/
├── .env                  # 環境変数（API keys - gitignore対象）
├── .env.example          # 環境変数テンプレート
├── .gitignore           # Git除外設定
├── CLAUDE.md            # 作業記録（このファイル）
├── Dockerfile           # Dockerイメージ定義
├── docker-compose.yml   # Docker Compose設定
├── main.py              # メインアプリケーション（v0.8.2対応）
└── requirements.txt     # Python依存ライブラリ
```

## 実装内容

### 1. メインアプリケーション (`main.py`)

AIAvatarKit v0.8.2の最新Adapter APIを使用:

- **FastAPI** を使用したWebサーバー（lifespan対応）
- **LINE Messaging API** との連携
  - 自動Webhookエンドポイント生成 (`/webhook`)
  - Adapterコールバック機能（セッション管理、リクエスト前処理）
- **複数LLMエンジン対応**（ファクトリパターンで切り替え）
  - Dify（エージェントモード対応）
  - ChatGPT（OpenAI GPT-4o）
- **複数TTSエンジン対応**
  - VOICEVOX（ローカル/Docker）
  - OpenAI TTS
  - Cartesia（クラウドサービス）
  - Style-Bert-VITS2（自前サーバー）
- **OpenAI Whisper** による音声認識（STT）
- **WebSocket対応**（オプション）- Webブラウザからのリアルタイム対話
- **pydantic-settings** による厳格な設定管理

### 2. インポートパス (v0.8.2)

```python
# LINE Bot Adapter
from aiavatar.adapter.linebot.server import AIAvatarLineBotServer

# LLM Services
from aiavatar.sts.llm.dify import DifyService
from aiavatar.sts.llm.chatgpt import ChatGPTLLMService

# TTS Services
from aiavatar.sts.tts.voicevox import VoicevoxSpeechSynthesizer
from aiavatar.sts.tts.openai import OpenAISpeechSynthesizer
from aiavatar.sts.tts.base import create_instant_synthesizer

# STT Services
from aiavatar.sts.stt.openai import OpenAISpeechRecognizer

# WebSocket Adapter (optional)
from aiavatar.adapter.websocket.server import AIAvatarWebSocketServer
```

### 3. Docker環境

- **line-bot**: メインのLINEボットアプリケーション
- **voicevox-engine**: 日本語音声合成エンジン（VOICEVOXの公式Dockerイメージ使用）

### 4. LLM/TTS切り替え方式

`.env` ファイルの変数を変更するだけで切り替え可能:

```bash
# LLM選択
LLM_TYPE="DIFY"      # デフォルト（Difyエージェント）
LLM_TYPE="CHATGPT"   # OpenAI ChatGPT

# TTS選択
TTS_ENGINE="VOICEVOX"         # デフォルト
TTS_ENGINE="OPENAI"           # OpenAI TTS
TTS_ENGINE="CARTESIA"         # Cartesia
TTS_ENGINE="STYLE_BERT_VITS2" # Style-Bert-VITS2
```

## APIエンドポイント

| Method | Path | 説明 |
|--------|------|------|
| GET | `/` | サーバー状態確認 |
| GET | `/health` | 詳細ヘルスチェック |
| POST | `/webhook` | LINE Webhook（v0.8.2で自動生成） |
| POST | `/callback` | レガシーWebhook（後方互換性、リダイレクト） |
| WS | `/ws` | WebSocket（ENABLE_WEBSOCKET=true時） |

**重要**: v0.8.2では `/webhook` が推奨エンドポイントです。LINE DevelopersコンソールでWebhook URLを更新してください。

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
- `OPENAI_API_KEY`: OpenAI Platformから取得（STT必須）
- `DIFY_API_KEY`: Difyダッシュボードから取得（LLM_TYPE=DIFY時）

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
4. Webhook URL に `https://xxxx.ngrok.io/webhook` を設定
   - **注意**: v0.8.2では `/webhook` を使用
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
`/health` エンドポイントで `line_bot: false` の場合、APIキーの設定に問題があります。

### ngrokの制限

無料版ngrokはURLが再起動のたびに変わります。
その場合はLINE DevelopersコンソールでWebhook URLを更新してください。

### Webhookエンドポイントのエラー

v0.8.2では `/webhook` が推奨されます。古い `/callback` を使用している場合は、LINE DevelopersコンソールでWebhook URLを更新してください。

## 次のステップ

1. **API Keyの取得**: LINE、Dify、OpenAI各サービスでAPIキーを取得
2. **ローカルテスト**: ngrokを使って実際のLINEとの通信をテスト
3. **WebSocket機能の有効化**: ENABLE_WEBSOCKET=true でブラウザ対話を追加
4. **GCP Cloud Runデプロイ**: 本番環境へのデプロイ

## 参考リンク

- [AIAvatarKit GitHub](https://github.com/uezo/aiavatarkit)
- [LINE Developers](https://developers.line.biz/console/)
- [Dify](https://dify.ai/)
- [OpenAI Platform](https://platform.openai.com/)
- [VOICEVOX](https://voicevox.hiroshiba.jp/)
- [VOICEVOX Docker Hub](https://hub.docker.com/r/voicevox/voicevox_engine)

## 技術スタック

- **言語**: Python 3.10+
- **フレームワーク**: FastAPI, uvicorn, pydantic-settings
- **AI/ML**: AIAvatarKit v0.8.2, OpenAI Whisper, silero-vad
- **LLM**: Dify, ChatGPT (OpenAI)
- **TTS**: VOICEVOX, OpenAI TTS, Cartesia, Style-Bert-VITS2
- **インフラ**: Docker, Docker Compose
- **外部サービス**: LINE Messaging API

## 変更履歴

### v2.0.0 (2026-01-02)
- AIAvatarKit v0.8.2対応
- インポートパスを最新形式に更新
- `get_api_router()`による自動Webhook生成
- Adapterコールバック機能の実装
- 複数LLMエンジン対応（Dify/ChatGPT）
- OpenAI TTS追加
- pydantic-settingsによる設定管理
- WebSocket Adapter対応（オプション）

### v1.0.0 (2026-01-02)
- 初期実装
- 基本的なLINE Bot機能
- VOICEVOX/Cartesia/Style-Bert-VITS2対応
