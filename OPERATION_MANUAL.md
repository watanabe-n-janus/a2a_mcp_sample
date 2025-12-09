# 動作マニュアル

このドキュメントでは、A2A MCP旅行計画システムの使用方法、トラブルシューティング、よくある質問について説明します。

## 目次

- [動作マニュアル](#動作マニュアル)
  - [目次](#目次)
  - [システム概要](#システム概要)
  - [基本的な使用方法](#基本的な使用方法)
  - [詳細な操作手順](#詳細な操作手順)
  - [対話的入力の使用方法](#対話的入力の使用方法)
  - [トラブルシューティング](#トラブルシューティング)
  - [よくある質問（FAQ）](#よくある質問faq)
  - [ログの確認方法](#ログの確認方法)
  - [パフォーマンス最適化](#パフォーマンス最適化)

## システム概要

このシステムは、複数のエージェントが協力して旅行計画を作成する分散型エージェントシステムです。

### 主要コンポーネント

1. **MCPサーバー** (ポート10100): エージェントカードとツールのレジストリ
2. **Orchestrator Agent** (ポート10101): 全体のワークフローを管理
3. **Planner Agent** (ポート10102): ユーザーリクエストをタスクに分解
4. **Air Ticketing Agent** (ポート10103): 航空券予約を処理
5. **Hotel Booking Agent** (ポート10104): ホテル予約を処理
6. **Car Rental Agent** (ポート10105): レンタカー予約を処理
7. **Itinerary Agent** (ポート10106): 旅程表を生成

## 基本的な使用方法

### クイックスタート

最も簡単な方法は、自動実行スクリプトを使用することです：

```bash
cd /Users/norihisa/Projects/Panasonic/workshop/A2A/a2a-samples/samples/python/agents/a2a_mcp
bash run.sh
```

このスクリプトは以下を自動的に実行します：
1. すべてのエージェントの起動
2. データベースの初期化
3. CLIクライアントの実行
4. 終了時のクリーンアップ

### カスタムクエリの実行

`run.sh`を編集して、`TRAVEL_QUERY`変数を変更することで、異なる旅行リクエストを実行できます：

```bash
TRAVEL_QUERY="フランスへの旅行を計画したいです。おすすめの旅行プランを考えてください。"
```

## 詳細な操作手順

### ステップ1: 環境の準備

1. `.env`ファイルが正しく設定されていることを確認：
   ```bash
   cat .env
   ```
   `GOOGLE_API_KEY`が設定されている必要があります。

2. 仮想環境がアクティブであることを確認：
   ```bash
   source .venv/bin/activate
   ```

### ステップ2: データベースの初期化（初回のみ）

```bash
uv run --env-file .env python init_database.py
```

これにより、`travel_agency.db`が作成され、サンプルデータが投入されます。

### ステップ3: サービスの起動

#### 方法A: 自動実行スクリプト（推奨）

```bash
bash run.sh
```

#### 方法B: 手動起動

各サービスを個別のターミナルで起動：

**ターミナル1: MCPサーバー**
```bash
uv run --env-file .env a2a-mcp --run mcp-server --transport sse --port 10100
```

**ターミナル2: Orchestrator Agent**
```bash
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/orchestrator_agent.json --port 10101
```

**ターミナル3: Planner Agent**
```bash
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/planner_agent.json --port 10102
```

**ターミナル4-6: 各タスクエージェント**
```bash
# Air Ticketing Agent
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/air_ticketing_agent.json --port 10103

# Hotel Booking Agent
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/hotel_booking_agent.json --port 10104

# Car Rental Agent
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/car_rental_agent.json --port 10105
```

**ターミナル7: Itinerary Agent**
```bash
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/itinerary_agent.json --port 10106
```

### ステップ4: クライアントの実行

すべてのサービスが起動した後（約10-15秒待機）、CLIクライアントを実行：

```bash
uv run --env-file .env python src/a2a_mcp/orchestrator_client.py \
  --orchestrator-url http://localhost:10101 \
  --query "フランスへの旅行を計画したいです。ビジネスクラスの航空券、スイートルームのホテルを予約してください。"
```

## 対話的入力の使用方法

システムは、追加情報が必要な場合にユーザーに入力を求めます。

### 入力が求められる場合

- 予算の詳細
- 出発地・目的地の明確化
- 日付の指定
- 人数の確認
- その他の不明確な情報

### 入力方法

プロンプトが表示されたら、必要な情報を入力してください：

```
📝 追加情報が必要です: 出発地を指定してください
> 東京
```

空の入力を送信すると、システムは既存の情報で処理を続行します。

### 対話の例

```
ユーザー: フランスへの旅行を計画したいです。

システム: 📝 追加情報が必要です: 出発地を指定してください
> 東京

システム: 📝 追加情報が必要です: 出発日を指定してください
> 12月25日

システム: 📝 追加情報が必要です: 帰国日を指定してください
> 12月30日

システム: [予約処理を開始...]
```

## トラブルシューティング

### 問題1: ポートが既に使用されている

**症状:**
```
Error: Address already in use
```

**解決方法:**
1. 既存のプロセスを確認：
   ```bash
   lsof -i :10100
   ```
2. プロセスを終了：
   ```bash
   kill -9 <PID>
   ```
3. または、別のポートを使用：
   ```bash
   uv run --env-file .env a2a-mcp --run mcp-server --transport sse --port 10110
   ```

### 問題2: GOOGLE_API_KEYが設定されていない

**症状:**
```
Error: GOOGLE_API_KEY is not set
```

**解決方法:**
1. `.env`ファイルを確認：
   ```bash
   cat .env | grep GOOGLE_API_KEY
   ```
2. APIキーを設定：
   ```bash
   echo "GOOGLE_API_KEY=your_api_key_here" >> .env
   ```

### 問題3: エージェントが応答しない

**症状:**
- タイムアウトエラー
- 接続エラー

**解決方法:**
1. すべてのエージェントが起動していることを確認
2. ログファイルを確認（`logs/`ディレクトリ）
3. ネットワーク接続を確認
4. タイムアウト設定を延長（`workflow.py`の`timeout_config`を調整）

### 問題4: データベースが見つからない

**症状:**
```
Error: travel_agency.db not found
```

**解決方法:**
```bash
uv run --env-file .env python init_database.py
```

### 問題5: 旅程表が生成されない

**症状:**
- 予約は完了したが、旅程表が表示されない

**解決方法:**
1. Itinerary Agentが起動していることを確認
2. `logs/itinerary_agent.log`を確認
3. Gemini APIキーが正しく設定されていることを確認

## よくある質問（FAQ）

### Q1: システムはどのくらいの時間で応答しますか？

A: 通常、簡単なリクエストで30秒〜2分程度です。複雑なリクエストや複数の予約が必要な場合は、5分程度かかる場合があります。

### Q2: 同時に複数のリクエストを処理できますか？

A: 現在の実装では、1つのリクエストを順次処理します。並行処理が必要な場合は、システムの拡張が必要です。

### Q3: カスタムエージェントを追加できますか？

A: はい。以下の手順で追加できます：
1. 新しいエージェントカードを作成（`agent_cards/`）
2. エージェント実装を作成（`src/a2a_mcp/agents/`）
3. MCPサーバーに登録

### Q4: データベースのデータを変更できますか？

A: はい。`init_database.py`を編集して、`travel_agency.db`を再生成してください。

### Q5: ログレベルを変更できますか？

A: はい。`.env`ファイルに以下を追加：
```bash
A2A_LOG_LEVEL=DEBUG
```

## ログの確認方法

### ログファイルの場所

すべてのログは`logs/`ディレクトリに保存されます：

```
logs/
├── mcp_server.log          # MCPサーバーのログ
├── orchestrator_agent.log   # Orchestrator Agentのログ
├── planner_agent.log        # Planner Agentのログ
├── airline_agent.log       # Air Ticketing Agentのログ
├── hotel_agent.log         # Hotel Booking Agentのログ
├── car_rental_agent.log    # Car Rental Agentのログ
└── itinerary_agent.log     # Itinerary Agentのログ
```

### ログの確認方法

**リアルタイムでログを監視:**
```bash
tail -f logs/orchestrator_agent.log
```

**特定のエラーを検索:**
```bash
grep -i error logs/*.log
```

**最新のログエントリを表示:**
```bash
tail -n 100 logs/orchestrator_agent.log
```

### ログレベルの理解

- **DEBUG**: 詳細なデバッグ情報
- **INFO**: 一般的な情報メッセージ
- **WARNING**: 警告メッセージ
- **ERROR**: エラーメッセージ

## パフォーマンス最適化

### タイムアウト設定の調整

長時間実行されるタスクがある場合、`src/a2a_mcp/common/workflow.py`のタイムアウト設定を調整：

```python
timeout_config = httpx.Timeout(
    timeout=600.0,  # 10分に延長
    connect=30.0,
    read=600.0,
    write=30.0,
)
```

### 並行処理の有効化

複数のタスクを並行して実行するには、`orchestrator_agent.py`のワークフローグラフを調整してください。

### キャッシュの活用

MCPサーバーはエージェントカードをキャッシュするため、繰り返しクエリのパフォーマンスが向上します。

## 次のステップ

- [用語解説集](GLOSSARY.md)でA2AとMCPの概念を理解する
- [A2A SDK解説](A2A_SDK_GUIDE.md)でSDKの詳細を学ぶ
- [FastAPI解説](FASTAPI_GUIDE.md)でWebフレームワークを理解する
