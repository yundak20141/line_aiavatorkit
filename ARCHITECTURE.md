# LINE AIAvatarKit Bot - アーキテクチャ解説

## 現状の設定

```
LLM_TYPE=DIFY        → Dify CloudでLLM処理
TTS_ENGINE=OPENAI    → OpenAI TTSで音声合成
```

---

## 処理フロー図

### テキストメッセージの場合

```
┌──────────┐     ┌──────────────┐     ┌─────────────────┐     ┌────────────┐
│   LINE   │────▶│  LINE Bot    │────▶│   Dify Cloud    │────▶│  LINE Bot  │
│  ユーザー │     │  (main.py)   │     │   (LLM処理)     │     │  (main.py) │
│          │◀────│              │◀────│                 │◀────│            │
└──────────┘     └──────────────┘     └─────────────────┘     └────────────┘
    │                  │                      │                      │
    │ テキスト送信      │ Webhook受信          │ API呼び出し           │ テキスト返信
    │ 「こんにちは」    │                      │                      │ 「こんにちは！」
    │                  │                      │                      │
    ▼                  ▼                      ▼                      ▼
   [1]               [2]                    [3]                    [4]

※ OpenAI APIは使用しない（Dify側で完結）
```

### 音声メッセージの場合

```
┌──────────┐     ┌──────────────┐     ┌─────────────┐     ┌─────────────────┐
│   LINE   │────▶│  LINE Bot    │────▶│  OpenAI     │────▶│   Dify Cloud    │
│  ユーザー │     │  (main.py)   │     │  Whisper    │     │   (LLM処理)     │
└──────────┘     └──────────────┘     │  (STT)      │     └─────────────────┘
                                      └─────────────┘              │
    │                  │                      │                    │
    │ 音声送信          │ 音声ファイル受信      │ 音声→テキスト変換    │ テキスト応答
    │ 🎤               │                      │ 「こんにちは」       │ 「こんにちは！」
    │                  │                      │                    │
    ▼                  ▼                      ▼                    ▼
   [1]               [2]                    [3]                   [4]

                                                                   │
                      ┌─────────────────────────────────────────────┘
                      ▼
┌──────────┐     ┌──────────────┐     ┌─────────────┐
│   LINE   │◀────│  LINE Bot    │◀────│  OpenAI     │
│  ユーザー │     │  (main.py)   │     │  TTS        │
└──────────┘     └──────────────┘     │  (音声合成)  │
                                      └─────────────┘
    │                  │                      │
    │ 音声返信          │ 音声ファイル送信      │ テキスト→音声変換
    │ 🔊               │                      │ 「こんにちは！」→🔊
    │                  │                      │
    ▼                  ▼                      ▼
   [8]               [7]                    [6]

※ OpenAI APIを使用するのはSTT(Whisper)とTTSのみ
※ LLM処理はDify側で行う
```

---

## API使用状況まとめ

| 入力 | 出力 | Dify API | OpenAI API |
|------|------|----------|------------|
| テキスト | テキスト | ✅ 使用 | ❌ 不使用 |
| テキスト | 音声 | ✅ 使用 | ✅ TTS |
| 音声 | テキスト | ✅ 使用 | ✅ STT |
| 音声 | 音声 | ✅ 使用 | ✅ STT + TTS |

### 結論

**テキスト→テキストのやり取りでは、OpenAI APIは使用しません。**
Dify Cloud側でLLM（GPT-4等）を使って応答を生成します。

---

## 各コンポーネントの役割

### 1. LINE Bot (main.py)

```python
# Webhookを受信してAIAvatarKitに渡す
bot_server = AIAvatarLineBotServer(
    channel_access_token=...,  # LINE認証
    channel_secret=...,        # LINE認証
    openai_api_key=...,        # STT/TTS用（音声処理時のみ）
    llm=llm_service,           # → DifyService
    tts=tts_service,           # → OpenAISpeechSynthesizer
    stt=stt_service,           # → OpenAISpeechRecognizer
)
```

### 2. DifyService (LLM)

```python
# main.py: 152-162行目
DifyService(
    api_key="app-UCG0SMyJaEsutsrPHviRPyt7",  # あなたのDify APIキー
    base_url="https://api.dify.ai/v1",
    user="line_user",
    is_agent_mode=True  # エージェントモード
)
```

**処理内容:**
1. ユーザーのテキストを受け取る
2. Dify APIにリクエスト送信
3. Dify側でLLM（GPT-4等）が応答生成
4. 応答テキストを返す

### 3. OpenAI STT (音声認識)

```python
# main.py: 254-257行目
OpenAISpeechRecognizer(
    openai_api_key=...,
    language="ja"  # 日本語優先
)
```

**処理内容:**
- 音声ファイル → テキスト変換
- OpenAI Whisper APIを使用

### 4. OpenAI TTS (音声合成)

```python
# main.py: 200-204行目
OpenAISpeechSynthesizer(
    openai_api_key=...,
    model="tts-1",
    voice="nova"
)
```

**処理内容:**
- テキスト → 音声ファイル変換
- OpenAI TTS APIを使用

---

## Difyエージェントモードとは

`is_agent_mode=True` の設定により:

1. **ストリーミング応答**: チャンク単位で応答を受信
2. **ツール呼び出し**: Dify側で設定したツール（Web検索等）を実行可能
3. **会話履歴**: Dify側でセッション管理

```
[ユーザー] → [LINE Bot] → [Dify Agent] → [ツール実行] → [LLM] → [応答]
                              │
                              ├── Web検索
                              ├── データベース検索
                              └── カスタムAPI呼び出し
```

---

## ローカルデータベース（SQLite）の役割

AIAvatarKitは内部でSQLiteデータベース（`/app/data/context.db`）を使用します。

### LLMモード別の用途

| モード | Dify側の役割 | SQLite（ローカル）の役割 |
|--------|--------------|-------------------------|
| **Dify** | ✅ 会話履歴を保持 | セッションIDマッピング |
| **ChatGPT** | なし | ✅ 会話履歴を保持（必須） |

### Difyモードの場合

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│ LINE User   │────▶│   AIAvatarKit    │────▶│    Dify     │
│   U1234     │     │   (SQLite)       │     │  conv_abc   │
└─────────────┘     └──────────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │  マッピング  │
                    │ U1234 ←→    │
                    │ conv_abc    │
                    └─────────────┘
```

**SQLiteの用途:**
- LINEユーザーIDとDify会話ID（conversation_id）の紐付け
- 次回メッセージ時に同じ会話を継続するため

**会話履歴の実体:**
- Dify Cloud側で保持（SQLiteには保存しない）

### ChatGPTモードの場合

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│ LINE User   │────▶│   AIAvatarKit    │────▶│   OpenAI    │
│   U1234     │     │   (SQLite)       │     │   API       │
└─────────────┘     └──────────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │  会話履歴    │
                    │  保存       │
                    └─────────────┘
```

**SQLiteの用途:**
- 会話履歴の保存（OpenAI APIはステートレスなため必須）
- コンテキストウィンドウの管理

### まとめ

| 項目 | Difyモード | ChatGPTモード |
|------|-----------|---------------|
| SQLiteの重要度 | 低（補助的） | 高（必須） |
| 会話履歴の場所 | Dify Cloud | SQLite |
| SQLiteのサイズ | 小さい | 大きくなる可能性 |

---

## 課金の発生場所

| サービス | 課金タイミング | テキストのみの場合 |
|----------|----------------|-------------------|
| **Dify** | LLMトークン消費時 | ✅ 発生 |
| **OpenAI STT** | 音声認識時 | ❌ 発生しない |
| **OpenAI TTS** | 音声合成時 | ❌ 発生しない |
| **LINE** | メッセージ数制限内は無料 | - |

---

## テスト時の確認ポイント

### 1. テキストメッセージテスト

```
あなた: こんにちは
ボット: [Difyで設定した応答]
```

確認事項:
- [ ] Dify APIが正しく呼び出されているか
- [ ] 応答が返ってくるか
- [ ] OpenAI APIは使われていないか（コスト確認）

### 2. ログで確認

```bash
docker logs -f line-aiavatar-bot
```

期待されるログ:
```
INFO - Selected LLM: DIFY
INFO - LINE Bot Adapter initialized - Webhook endpoint: POST /webhook
INFO - Incoming request from user: line_xxx
```

### 3. ヘルスチェック

```bash
curl http://localhost:8080/health
```

期待される応答:
```json
{
  "status": "healthy",
  "components": {
    "aiavatar": true,
    "line_bot": true
  },
  "config": {
    "llm_type": "DIFY",
    "tts_engine": "OPENAI"
  }
}
```
