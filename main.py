"""
LINE AIAvatarKit Bot - メインアプリケーション (v0.8.2対応)

このファイルは以下の機能を提供します:
- LINE Messaging APIとの連携（自動Webhookエンドポイント生成）
- 複数LLMエンジン対応（Dify, ChatGPT, Claude）
- 複数TTSエンジン対応（VOICEVOX, OpenAI TTS, Cartesia, Style-Bert-VITS2）
- OpenAI Whisperによる音声認識
- WebSocketによるリアルタイム音声対話（オプション）
- Adapterコールバックによる柔軟なセッション管理

参考: https://github.com/uezo/aiavatarkit
"""

import os
import logging
from typing import Optional
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# .envファイルから環境変数を読み込む
load_dotenv()

# --- pydantic-settingsによる設定管理 ---
try:
    from pydantic_settings import BaseSettings

    class Settings(BaseSettings):
        """アプリケーション設定（環境変数から自動読み込み）"""
        # LINE Messaging API
        line_channel_access_token: str = ""
        line_channel_secret: str = ""

        # OpenAI API (STT/LLM/TTS共通)
        openai_api_key: str = ""

        # LLM選択 (DIFY, CHATGPT, CLAUDE)
        llm_type: str = "DIFY"

        # Dify設定
        dify_api_key: Optional[str] = None
        dify_base_url: str = "https://api.dify.ai/v1"
        dify_user: str = "line_user"
        dify_is_agent_mode: bool = True

        # ChatGPT設定
        openai_model: str = "gpt-4o"
        openai_temperature: float = 0.7

        # TTS選択 (VOICEVOX, OPENAI, CARTESIA, STYLE_BERT_VITS2)
        tts_engine: str = "VOICEVOX"

        # VOICEVOX設定
        voicevox_base_url: str = "http://voicevox-engine:50021"
        voicevox_speaker_id: int = 46

        # OpenAI TTS設定
        openai_tts_model: str = "tts-1"
        openai_tts_voice: str = "nova"

        # Cartesia設定
        cartesia_api_key: Optional[str] = None
        cartesia_voice_id: Optional[str] = None

        # Style-Bert-VITS2設定
        style_bert_vits2_base_url: str = "http://127.0.0.1:5000/voice"

        # システムプロンプト
        system_prompt: str = "あなたは親切で丁寧なAIアシスタントです。日本語で応答してください。"

        # WebSocket設定
        enable_websocket: bool = False

        # デバッグ設定
        debug: bool = False

        class Config:
            env_file = ".env"
            extra = "ignore"

    settings = Settings()
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    settings = None

# --- ログ設定 ---
log_level = logging.DEBUG if (settings and settings.debug) else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 設定の取得ヘルパー関数
def get_env(key: str, default: str = ""):
    """環境変数を取得（pydantic-settings非対応時のフォールバック）"""
    if PYDANTIC_AVAILABLE and settings:
        return getattr(settings, key.lower(), os.environ.get(key, default))
    return os.environ.get(key, default)

def get_bool_env(key: str, default: bool = False) -> bool:
    """環境変数をbool型で取得"""
    value = get_env(key, str(default))
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"

# --- AIAvatarKit v0.8.2のインポート ---
AIAVATAR_AVAILABLE = False
bot_server = None
ws_server = None

try:
    # LINE Bot Adapter
    from aiavatar.adapter.linebot.server import AIAvatarLineBotServer

    # LLMサービス
    from aiavatar.sts.llm.dify import DifyService
    from aiavatar.sts.llm.chatgpt import ChatGPTService

    # TTSサービス
    from aiavatar.sts.tts.voicevox import VoicevoxSpeechSynthesizer
    from aiavatar.sts.tts.openai import OpenAISpeechSynthesizer
    from aiavatar.sts.tts.base import create_instant_synthesizer

    # STTサービス
    from aiavatar.sts.stt.openai import OpenAISpeechRecognizer

    # WebSocket Adapter（オプション）
    try:
        from aiavatar.adapter.websocket.server import AIAvatarWebSocketServer
        WEBSOCKET_AVAILABLE = True
    except ImportError:
        WEBSOCKET_AVAILABLE = False
        logger.info("WebSocket Adapter not available")

    AIAVATAR_AVAILABLE = True
    logger.info("AIAvatarKit v0.8.2+ successfully imported")

except ImportError as e:
    logger.warning(f"AIAvatarKit import failed: {e}")
    logger.warning("Running in demo mode without AIAvatarKit")
    WEBSOCKET_AVAILABLE = False


# --- LLMサービスのファクトリ関数 ---
def get_llm_service():
    """LLM_TYPE設定に応じてLLMサービスを初期化"""
    if not AIAVATAR_AVAILABLE:
        return None

    llm_type = get_env("LLM_TYPE", "DIFY").upper()
    logger.info(f"Selected LLM: {llm_type}")

    if llm_type == "DIFY":
        dify_api_key = get_env("DIFY_API_KEY")
        if not dify_api_key or dify_api_key.startswith("your_"):
            raise ValueError("DIFY_API_KEY must be set for Dify LLM")

        return DifyService(
            api_key=dify_api_key,
            base_url=get_env("DIFY_BASE_URL", "https://api.dify.ai/v1"),
            user=get_env("DIFY_USER", "line_user"),
            is_agent_mode=get_bool_env("DIFY_IS_AGENT_MODE", True)
        )

    elif llm_type == "CHATGPT":
        openai_api_key = get_env("OPENAI_API_KEY")
        if not openai_api_key or openai_api_key.startswith("your_"):
            raise ValueError("OPENAI_API_KEY must be set for ChatGPT LLM")

        return ChatGPTService(
            openai_api_key=openai_api_key,
            model=get_env("OPENAI_MODEL", "gpt-4o"),
            temperature=float(get_env("OPENAI_TEMPERATURE", "0.7")),
            system_prompt=get_env("SYSTEM_PROMPT", "あなたは親切なAIアシスタントです。")
        )

    else:
        raise ValueError(f"Unsupported LLM_TYPE: {llm_type}. Supported: DIFY, CHATGPT")


# --- TTSサービスのファクトリ関数 ---
def get_speech_synthesizer():
    """TTS_ENGINE設定に応じてTTSサービスを初期化"""
    if not AIAVATAR_AVAILABLE:
        return None

    engine = get_env("TTS_ENGINE", "VOICEVOX").upper()
    logger.info(f"Selected TTS Engine: {engine}")

    if engine == "VOICEVOX":
        return VoicevoxSpeechSynthesizer(
            base_url=get_env("VOICEVOX_BASE_URL", "http://voicevox-engine:50021"),
            speaker=int(get_env("VOICEVOX_SPEAKER_ID", "46"))
        )

    elif engine == "OPENAI":
        openai_api_key = get_env("OPENAI_API_KEY")
        if not openai_api_key or openai_api_key.startswith("your_"):
            raise ValueError("OPENAI_API_KEY must be set for OpenAI TTS")

        return OpenAISpeechSynthesizer(
            openai_api_key=openai_api_key,
            model=get_env("OPENAI_TTS_MODEL", "tts-1"),
            speaker=get_env("OPENAI_TTS_VOICE", "nova")
        )

    elif engine == "CARTESIA":
        cartesia_api_key = get_env("CARTESIA_API_KEY")
        cartesia_voice_id = get_env("CARTESIA_VOICE_ID")

        if not cartesia_api_key or not cartesia_voice_id:
            raise ValueError("CARTESIA_API_KEY and CARTESIA_VOICE_ID must be set")

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
        base_url = get_env("STYLE_BERT_VITS2_BASE_URL", "http://127.0.0.1:5000/voice")

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
        raise ValueError(f"Unsupported TTS_ENGINE: {engine}. Supported: VOICEVOX, OPENAI, CARTESIA, STYLE_BERT_VITS2")


# --- STTサービスのファクトリ関数 ---
def get_speech_recognizer():
    """STTサービス（OpenAI Whisper）を初期化"""
    if not AIAVATAR_AVAILABLE:
        return None

    openai_api_key = get_env("OPENAI_API_KEY")
    if not openai_api_key or openai_api_key.startswith("your_"):
        return None

    return OpenAISpeechRecognizer(
        openai_api_key=openai_api_key,
        language="ja"  # 日本語優先
    )


# --- FastAPIアプリケーションのライフサイクル ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションの起動・終了時の処理"""
    global bot_server, ws_server

    if AIAVATAR_AVAILABLE:
        try:
            # 必須環境変数のチェック
            line_token = get_env("LINE_CHANNEL_ACCESS_TOKEN")
            line_secret = get_env("LINE_CHANNEL_SECRET")
            openai_key = get_env("OPENAI_API_KEY")

            missing_vars = []
            if not line_token or line_token.startswith("your_") or line_token.startswith("YOUR_"):
                missing_vars.append("LINE_CHANNEL_ACCESS_TOKEN")
            if not line_secret or line_secret.startswith("your_") or line_secret.startswith("YOUR_"):
                missing_vars.append("LINE_CHANNEL_SECRET")
            if not openai_key or openai_key.startswith("your_") or openai_key.startswith("YOUR_"):
                missing_vars.append("OPENAI_API_KEY")

            if missing_vars:
                logger.warning(f"Missing or placeholder environment variables: {missing_vars}")
                logger.warning("Bot server will not be initialized. Please set all required API keys in .env file.")
            else:
                # コンポーネントの初期化
                llm_service = get_llm_service()

                # LINE Bot Adapterの初期化（v0.8.2形式）
                # 注意: tts/sttは直接指定不可。テキストメッセージはllmのみで処理
                bot_server = AIAvatarLineBotServer(
                    channel_access_token=line_token,
                    channel_secret=line_secret,
                    openai_api_key=openai_key,
                    llm=llm_service,
                    system_prompt=get_env("SYSTEM_PROMPT", "あなたは親切なAIアシスタントです。"),
                    debug=get_bool_env("DEBUG", False)
                )

                # APIルーターを登録（/webhook エンドポイントが自動生成される）
                app.include_router(bot_server.get_api_router())
                logger.info("LINE Bot Adapter initialized - Webhook endpoint: POST /webhook")

                # Adapterコールバックの登録
                @bot_server.edit_linebot_session
                async def edit_session(linebot_session):
                    """LINEユーザーIDをアプリ独自IDにマッピング"""
                    linebot_session.user_id = f"line_{linebot_session.linebot_user_id}"
                    logger.debug(f"Session mapped: LINE {linebot_session.linebot_user_id} -> {linebot_session.user_id}")

                @bot_server.preprocess_request
                async def log_request(request, session):
                    """リクエストのログ出力"""
                    logger.info(f"Incoming request from user: {session.user_id}")

                # WebSocket Adapterの初期化（オプション）
                if WEBSOCKET_AVAILABLE and get_bool_env("ENABLE_WEBSOCKET", False):
                    ws_server = AIAvatarWebSocketServer(
                        openai_api_key=openai_key,
                        llm=llm_service,
                        tts=tts_service,
                        stt=stt_service,
                        system_prompt=get_env("SYSTEM_PROMPT", "あなたは親切なAIアシスタントです。"),
                        debug=get_bool_env("DEBUG", False)
                    )
                    app.include_router(ws_server.get_websocket_router())
                    logger.info("WebSocket Adapter initialized - Endpoint: WS /ws")

        except Exception as e:
            logger.error(f"Failed to initialize adapters: {e}", exc_info=True)

    yield

    # シャットダウン処理
    logger.info("Shutting down...")


# --- FastAPIアプリケーションの初期化 ---
app = FastAPI(
    title="LINE AIAvatarKit Bot",
    description="LINE Messaging API + AIAvatarKit v0.8.2 integration",
    version="2.0.0",
    lifespan=lifespan
)


# --- ヘルスチェックエンドポイント ---
@app.get("/")
async def root():
    """ルートエンドポイント（サーバー状態確認）"""
    return {
        "message": "AIAvatarKit LINE Bot Server is running",
        "version": "2.0.0",
        "aiavatar_available": AIAVATAR_AVAILABLE,
        "pydantic_settings": PYDANTIC_AVAILABLE,
        "line_bot_initialized": bot_server is not None,
        "websocket_initialized": ws_server is not None,
        "llm_type": get_env("LLM_TYPE", "DIFY"),
        "tts_engine": get_env("TTS_ENGINE", "VOICEVOX")
    }


@app.get("/health")
async def health_check():
    """詳細なヘルスチェックエンドポイント"""
    return {
        "status": "healthy" if bot_server else "degraded",
        "components": {
            "aiavatar": AIAVATAR_AVAILABLE,
            "line_bot": bot_server is not None,
            "websocket": ws_server is not None
        },
        "config": {
            "llm_type": get_env("LLM_TYPE", "DIFY"),
            "tts_engine": get_env("TTS_ENGINE", "VOICEVOX"),
            "voicevox_url": get_env("VOICEVOX_BASE_URL", "not set"),
            "debug": get_env("DEBUG", "false")
        }
    }


# --- 後方互換性のための/callbackエンドポイント ---
# 注意: v0.8.2では /webhook が自動生成されますが、既存の設定との互換性のため残しています
@app.post("/callback")
async def callback_redirect():
    """
    レガシーWebhookエンドポイント

    注意: v0.8.2では /webhook が推奨されます。
    LINE Developersコンソールで /webhook に変更してください。
    """
    return JSONResponse(
        status_code=301,
        content={
            "message": "Please use /webhook instead of /callback",
            "new_endpoint": "/webhook"
        },
        headers={"Location": "/webhook"}
    )


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
        reload=True
    )
