# A2A MCP サンプルセットアップガイド

このガイドは、A2A MCPサンプルを実行するためのセットアップ手順を説明します。

## 必要な環境

- Python 3.13以上
- `uv` (Pythonパッケージマネージャー) - インストール済み ✓

## セットアップ手順

### 1. 環境変数ファイルの作成

`.env`ファイルを作成し、以下の環境変数を設定してください：

```bash
# 必須: Google API Key
# 取得方法: https://makersuite.google.com/app/apikey
GOOGLE_API_KEY=your_google_api_key_here

# オプション: Google Places API Key
# 取得方法: https://console.cloud.google.com/apis/credentials
GOOGLE_PLACES_API_KEY=your_google_places_api_key_here

# オプション: LiteLLMモデル設定（デフォルト: gemini/gemini-2.0-flash）
LITELLM_MODEL=gemini/gemini-2.0-flash

# オプション: ログレベル（DEBUG, INFO, WARNING, ERROR）
A2A_LOG_LEVEL=INFO
```

### 2. 仮想環境の作成と依存関係のインストール

```bash
cd /Users/norihisa/Projects/Panasonic/workshop/A2A/a2a-samples/samples/python/agents/a2a_mcp
uv venv
source .venv/bin/activate
```

依存関係は`uv run`コマンド実行時に自動的にインストールされます。

## 実行方法

### 方法1: 自動実行スクリプトを使用（推奨）

すべてのサービスを自動的に起動して実行します：

```bash
cd /Users/norihisa/Projects/Panasonic/workshop/A2A/a2a-samples
bash samples/python/agents/a2a_mcp/run.sh
```

このスクリプトは以下を自動的に実行します：
1. MCPサーバーの起動（ポート10100）
2. Orchestrator Agentの起動（ポート10101）
3. Planner Agentの起動（ポート10102）
4. Airline Ticketing Agentの起動（ポート10103）
5. Hotel Reservations Agentの起動（ポート10104）
6. Car Rental Reservations Agentの起動（ポート10105）
7. Itinerary Agentの起動（ポート10106）
8. CLIクライアントの実行
9. 終了時の自動クリーンアップ

### 方法2: 手動で各サービスを起動

#### ステップ1: MCPサーバーの起動

```bash
cd /Users/norihisa/Projects/Panasonic/workshop/A2A/a2a-samples/samples/python/agents/a2a_mcp
uv venv
source .venv/bin/activate
uv run --env-file .env a2a-mcp --run mcp-server --transport sse --port 10100
```

#### ステップ2: Orchestrator Agentの起動（新しいターミナル）

```bash
cd /Users/norihisa/Projects/Panasonic/workshop/A2A/a2a-samples/samples/python/agents/a2a_mcp
source .venv/bin/activate
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/orchestrator_agent.json --port 10101
```

#### ステップ3: Planner Agentの起動（新しいターミナル）

```bash
cd /Users/norihisa/Projects/Panasonic/workshop/A2A/a2a-samples/samples/python/agents/a2a_mcp
source .venv/bin/activate
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/planner_agent.json --port 10102
```

#### ステップ4: Airline Ticketing Agentの起動（新しいターミナル）

```bash
cd /Users/norihisa/Projects/Panasonic/workshop/A2A/a2a-samples/samples/python/agents/a2a_mcp
source .venv/bin/activate
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/air_ticketing_agent.json --port 10103
```

#### ステップ5: Hotel Reservations Agentの起動（新しいターミナル）

```bash
cd /Users/norihisa/Projects/Panasonic/workshop/A2A/a2a-samples/samples/python/agents/a2a_mcp
source .venv/bin/activate
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/hotel_booking_agent.json --port 10104
```

#### ステップ6: Car Rental Reservations Agentの起動（新しいターミナル）

```bash
cd /Users/norihisa/Projects/Panasonic/workshop/A2A/a2a-samples/samples/python/agents/a2a_mcp
source .venv/bin/activate
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/car_rental_agent.json --port 10105
```

#### ステップ7: Itinerary Agentの起動（新しいターミナル）

```bash
cd /Users/norihisa/Projects/Panasonic/workshop/A2A/a2a-samples/samples/python/agents/a2a_mcp
source .venv/bin/activate
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/itinerary_agent.json --port 10106
```

#### ステップ8: CLIクライアントの実行（新しいターミナル）

すべてのサービスが起動した後（約10秒待機）、CLIクライアントを実行：

```bash
cd /Users/norihisa/Projects/Panasonic/workshop/A2A/a2a-samples/samples/python/agents/a2a_mcp
source .venv/bin/activate
uv run --env-file .env src/a2a_mcp/mcp/client.py --resource "resource://agent_cards/list" --find_agent "I would like to plan a trip to France."
```

## トラブルシューティング

### エラー: GOOGLE_API_KEY is not set

`.env`ファイルが正しく作成され、`GOOGLE_API_KEY`が設定されていることを確認してください。

### ポートが既に使用されている

別のアプリケーションが同じポートを使用している場合は、各サービス起動時に`--port`オプションで異なるポートを指定してください。

### ログの確認

自動実行スクリプトを使用する場合、ログは`logs/`ディレクトリに保存されます：
- `logs/mcp_server.log`
- `logs/orchestrator_agent.log`
- `logs/planner_agent.log`
- `logs/airline_agent.log`
- `logs/hotel_agent.log`
- `logs/car_rental_agent.log`
- `logs/itinerary_agent.log`

## 参考リンク

- [A2A Protocol Documentation](https://github.com/a2aproject/a2a-samples)
- [Google Generative AI API](https://ai.google.dev/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)

## 関連ドキュメント

- [README.md](README.md) - プロジェクトの概要とアーキテクチャ
- [動作マニュアル](OPERATION_MANUAL.md) - 詳細な使用方法とトラブルシューティング
- [用語解説集](GLOSSARY.md) - A2AとMCPの用語解説
- [FastAPI解説](FASTAPI_GUIDE.md) - FastAPIの概要と使用方法
- [A2A SDK解説](A2A_SDK_GUIDE.md) - A2A SDKの詳細な解説

