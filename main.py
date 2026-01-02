"""
LINE AIAvatarKit Bot - メインアプリケーション

このファイルは以下の機能を提供します:
- LINE Messaging APIとの連携
- Dify LLMサービスとの連携
- 複数TTSエンジン（VOICEVOX, Cartesia, Style-Bert-VITS2）の切り替え
- OpenAI Whisperによる音声認識

参考: https://github.com/uezo/aiavatarkit
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# .envファイルから環境変数を読み込む
load_dotenv()

# --- AIAvatarKitのインポート ---
# 注意: パッケージのバージョンによりインポートパスが異なる場合があります
try:
    # AIAvatarKitの主要コンポーネントをインポート
    from aiavatar.bots.line import AIAvatarLineBotServer
    from aiavatar.llms.dify import DifyService
    from aiavatar.speech.openai import OpenAISpeechRecognizer
    from aiavatar.speech.voicevox import VoicevoxSpeechSynthesizer
    from aiavatar.speech.base import create_instant_synthesizer, SpeechSynthesizer
    AIAVATAR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"AIAvatarKit import failed: {e}")
    logger.warning("Running in demo mode without AIAvatarKit")
    AIAVATAR_AVAILABLE = False
    SpeechSynthesizer = object  # Placeholder for type hints


def get_speech_synthesizer() -> Optional[object]:
    """
    .envのTTS_ENGINE設定に応じて、対応するTTSインスタンスを返すファクトリ関数

    サポートするTTSエンジン:
    - VOICEVOX: ローカルまたはDockerコンテナで動作する無料の日本語TTS
    - CARTESIA: クラウドベースのTTSサービス
    - STYLE_BERT_VITS2: 高品質な日本語TTS（自前でサーバー構築が必要）
    """
    if not AIAVATAR_AVAILABLE:
        return None

    engine = os.environ.get("TTS_ENGINE", "VOICEVOX").upper()
    logger.info(f"Selected TTS Engine: {engine}")

    if engine == "VOICEVOX":
        # ローカルまたはDockerのVOICEVOXエンジンを使用
        # Docker Compose使用時: VOICEVOX_BASE_URL=http://voicevox-engine:50021
        # ローカル使用時: VOICEVOX_BASE_URL=http://127.0.0.1:50021
        return VoicevoxSpeechSynthesizer(
            base_url=os.environ.get("VOICEVOX_BASE_URL", "http://voicevox-engine:50021"),
            speaker=int(os.environ.get("VOICEVOX_SPEAKER_ID", "46"))
        )

    elif engine == "CARTESIA":
        # Cartesia APIを使用 (HTTPベースのTTS)
        cartesia_api_key = os.environ.get("CARTESIA_API_KEY")
        cartesia_voice_id = os.environ.get("CARTESIA_VOICE_ID")

        if not cartesia_api_key or not cartesia_voice_id:
            raise ValueError("CARTESIA_API_KEY and CARTESIA_VOICE_ID must be set for Cartesia TTS")

        return create_instant_synthesizer(
            method="POST",
            url="https://api.cartesia.ai/v1/tts/bytes",
            headers={
                "X-API-Key": cartesia_api_key,
                "Content-Type": "application/json"
            },
            json={
                "text": "{text}",
                "voice_id": cartesia_voice_id,
                "output_format": "wav"
            }
        )

    elif engine == "STYLE_BERT_VITS2":
        # Style-Bert-VITS2のAPIを使用 (HTTPベースのTTS)
        base_url = os.environ.get("STYLE_BERT_VITS2_BASE_URL", "http://127.0.0.1:5000/voice")

        return create_instant_synthesizer(
            method="POST",
            url=base_url,
            json={
                "text": "{text}",
                "model_id": 0,
                "speaker_id": 0,
            }
        )

    else:
        raise ValueError(f"Unsupported TTS_ENGINE: {engine}. Supported: VOICEVOX, CARTESIA, STYLE_BERT_VITS2")


# --- FastAPIアプリケーションの初期化 ---
app = FastAPI(
    title="LINE AIAvatarKit Bot",
    description="LINE Messaging APIとAIAvatarKitを連携したAIボット",
    version="1.0.0"
)

# グローバル変数としてbot_serverを初期化
bot_server = None

if AIAVATAR_AVAILABLE:
    try:
        # 必須環境変数のチェック
        required_vars = [
            "LINE_CHANNEL_ACCESS_TOKEN",
            "LINE_CHANNEL_SECRET",
            "DIFY_API_KEY",
            "OPENAI_API_KEY"
        ]

        missing_vars = [var for var in required_vars if not os.environ.get(var) or os.environ.get(var).startswith("YOUR_")]

        if missing_vars:
            logger.warning(f"Missing or placeholder environment variables: {missing_vars}")
            logger.warning("Bot server will not be initialized. Please set all required API keys in .env file.")
        else:
            # Dify LLMサービスを初期化
            dify_service = DifyService(
                api_key=os.environ["DIFY_API_KEY"],
                base_url=os.environ.get("DIFY_BASE_URL", "https://api.dify.ai/v1/chat-messages")
            )

            # AIAvatarKitのLINEボットサーバーを初期化
            bot_server = AIAvatarLineBotServer(
                line_channel_access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"],
                line_channel_secret=os.environ["LINE_CHANNEL_SECRET"],
                llm_service=dify_service,
                speech_synthesizer=get_speech_synthesizer(),
                speech_recognizer=OpenAISpeechRecognizer(api_key=os.environ["OPENAI_API_KEY"])
            )
            logger.info("Bot server initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize bot server: {e}")
        bot_server = None


# --- エンドポイント定義 ---

@app.get("/")
async def root():
    """ヘルスチェック用のルートエンドポイント"""
    tts_engine = os.environ.get("TTS_ENGINE", "VOICEVOX")
    return {
        "message": f"AIAvatarKit LINE Bot Server is running",
        "tts_engine": tts_engine,
        "aiavatar_available": AIAVATAR_AVAILABLE,
        "bot_initialized": bot_server is not None
    }


@app.get("/health")
async def health_check():
    """詳細なヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "aiavatar_available": AIAVATAR_AVAILABLE,
        "bot_initialized": bot_server is not None,
        "tts_engine": os.environ.get("TTS_ENGINE", "VOICEVOX"),
        "voicevox_url": os.environ.get("VOICEVOX_BASE_URL", "not set")
    }


@app.post("/callback")
async def handle_callback(request: Request):
    """
    LINE Webhook用のエンドポイント

    LINE Developersコンソールで設定するWebhook URL:
    - ローカル開発時: https://<ngrok-url>/callback
    - 本番環境: https://<your-domain>/callback
    """
    if bot_server is None:
        logger.error("Bot server not initialized - check your API keys in .env file")
        return JSONResponse(
            status_code=503,
            content={
                "error": "Bot server not initialized",
                "message": "Please check your API keys in .env file"
            }
        )

    try:
        return await bot_server.handle_request(request)
    except Exception as e:
        logger.error(f"Error handling callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 開発時のサーバー起動用 ---
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")

    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True  # 開発時は自動リロード有効
    )
