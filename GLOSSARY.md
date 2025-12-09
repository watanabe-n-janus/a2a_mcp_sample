# 用語解説集：A2AとMCP

このドキュメントでは、A2A（Agent-to-Agent）プロトコルとMCP（Model Context Protocol）に関連する主要な用語を解説します。

## 目次

- [用語解説集：A2AとMCP](#用語解説集a2aとmcp)
  - [目次](#目次)
  - [A2A（Agent-to-Agent）プロトコル](#a2aagent-to-agentプロトコル)
  - [MCP（Model Context Protocol）](#mcpmodel-context-protocol)
  - [エージェント関連の用語](#エージェント関連の用語)
  - [通信プロトコル関連の用語](#通信プロトコル関連の用語)
  - [データ構造関連の用語](#データ構造関連の用語)
  - [システムアーキテクチャ関連の用語](#システムアーキテクチャ関連の用語)

## A2A（Agent-to-Agent）プロトコル

### A2A（Agent-to-Agent）

**定義**: エージェント間のランタイム通信を標準化するプロトコル。Googleが開発した、異なるエージェントが互いに通信し、協力してタスクを実行するための標準規格。

**特徴**:
- JSON-RPC 2.0ベースの通信
- エージェントカードによる自己記述
- ストリーミング対応
- タスク管理機能

**関連用語**: Agent Card, A2AClient, A2AServer

### Agent Card（エージェントカード）

**定義**: エージェントの識別情報、機能、相互作用エンドポイントを記述するJSONスキーマ。

**主要フィールド**:
- `name`: エージェントの名前
- `description`: エージェントの説明
- `url`: エージェントのエンドポイントURL
- `capabilities`: エージェントの機能（ストリーミング、プッシュ通知など）
- `skills`: エージェントが実行できるスキル/タスクのリスト

**例**:
```json
{
  "name": "Hotel Booking Agent",
  "description": "ホテル予約を処理するエージェント",
  "url": "http://localhost:10104/",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true
  },
  "skills": [
    {
      "id": "book_hotel",
      "name": "Book Hotel",
      "description": "ホテルを予約します"
    }
  ]
}
```

### A2AClient（A2Aクライアント）

**定義**: 他のエージェントと通信するためのクライアントライブラリ。Agent Cardを使用してエージェントに接続し、タスクを送信します。

**主要機能**:
- エージェントへの接続
- タスクの送信
- ストリーミングレスポンスの受信
- エラーハンドリング

**使用例**:
```python
from a2a.client import A2AClient
import httpx

async with httpx.AsyncClient() as client:
    a2a_client = A2AClient(client, agent_card)
    # タスクを送信
    async for chunk in a2a_client.send_message_streaming(request):
        # レスポンスを処理
        pass
```

### A2AServer（A2Aサーバー）

**定義**: A2Aプロトコルに準拠したエージェントをホストするサーバー。エージェントカードを公開し、タスクを受信・処理します。

**主要機能**:
- Agent Cardの公開（`/.well-known/agent-card.json`）
- タスクの受信と処理
- ストリーミングレスポンスの送信
- タスク状態の管理

### Task（タスク）

**定義**: エージェントが実行すべき作業単位。メッセージ、コンテキストID、タスクIDを含みます。

**主要フィールド**:
- `id`: タスクの一意の識別子
- `contextId`: 会話コンテキストの識別子
- `message`: タスクの内容を含むメッセージ
- `status`: タスクの状態（pending, running, completed, failed）

### TaskStatusUpdateEvent（タスクステータス更新イベント）

**定義**: タスクの状態が変更されたときに送信されるイベント。

**状態の種類**:
- `pending`: タスクが待機中
- `running`: タスクが実行中
- `completed`: タスクが完了
- `failed`: タスクが失敗
- `input_required`: ユーザー入力が必要

### TaskArtifactUpdateEvent（タスクアーティファクト更新イベント）

**定義**: タスクの結果（アーティファクト）が生成または更新されたときに送信されるイベント。

**アーティファクト**: タスクの実行結果（テキスト、データ、ファイルなど）

### JSON-RPC 2.0

**定義**: A2Aプロトコルが使用する通信プロトコル。リモートプロシージャコール（RPC）の標準規格。

**主要要素**:
- `jsonrpc`: プロトコルバージョン（"2.0"）
- `id`: リクエストの一意の識別子
- `method`: 呼び出すメソッド名
- `params`: メソッドのパラメータ

## MCP（Model Context Protocol）

### MCP（Model Context Protocol）

**定義**: アプリケーション（AIモデルを含む）がコンテキスト情報（ツール、リソースなど）を発見、アクセス、利用するための標準プロトコル。

**目的**:
- ツールとリソースの標準化されたアクセス
- エージェント間の動的な発見
- コンテキスト情報の共有

**関連用語**: MCP Server, MCP Client, Resource, Tool

### MCP Server（MCPサーバー）

**定義**: リソースとツールを提供するサーバー。エージェントカードやデータベースアクセスのようなツールをホストします。

**主要機能**:
- リソースのリスト提供
- リソースの取得
- ツールの実行
- エージェントカードの検索

**このプロジェクトでの役割**:
- エージェントカードのレジストリ
- データベースアクセストールの提供
- エージェント検索機能の提供

### MCP Client（MCPクライアント）

**定義**: MCPサーバーと通信するクライアント。リソースを取得し、ツールを実行します。

**使用例**:
```python
from a2a_mcp.mcp import client as mcp_client

async with mcp_client.init_session(host, port, transport) as session:
    # リソースを取得
    response = await mcp_client.find_resource(session, 'resource://agent_cards/list')
```

### Resource（リソース）

**定義**: MCPサーバーが提供する情報の単位。エージェントカード、データ、設定など。

**リソースURIの例**:
- `resource://agent_cards/list`: すべてのエージェントカードのリスト
- `resource://agent_cards/orchestrator_agent`: 特定のエージェントカード

### Tool（ツール）

**定義**: MCPサーバーが提供する実行可能な機能。データベースクエリ、計算、検索など。

**このプロジェクトでのツール例**:
- `find_agent`: タスクに適したエージェントを検索
- `query_flights`: フライト情報をデータベースから取得
- `query_hotels`: ホテル情報をデータベースから取得

## エージェント関連の用語

### Orchestrator Agent（オーケストレーターエージェント）

**定義**: 複数のタスクエージェントを調整し、ワークフローを管理するエージェント。

**役割**:
- Planner Agentからプランを受信
- タスクエージェントを発見（MCP経由）
- タスクを適切なエージェントに割り当て
- 結果を集約・要約

### Planner Agent（プランナーエージェント）

**定義**: ユーザーリクエストを構造化されたタスクプランに分解するエージェント。

**役割**:
- ユーザーリクエストの理解
- タスクの分解
- 依存関係の特定
- タスクプランの生成

### Task Agent（タスクエージェント）

**定義**: 特定の種類のタスクを専門に処理するエージェント。

**種類**:
- Air Ticketing Agent: 航空券予約
- Hotel Booking Agent: ホテル予約
- Car Rental Agent: レンタカー予約
- Itinerary Agent: 旅程表生成

### Base Agent（ベースエージェント）

**定義**: すべてのエージェントが継承する基底クラス。共通の機能を提供します。

**主要メソッド**:
- `invoke()`: 同期タスク実行
- `stream()`: ストリーミングタスク実行

## 通信プロトコル関連の用語

### Streaming（ストリーミング）

**定義**: リアルタイムでデータを送受信する通信方式。タスクの進行状況を逐次更新できます。

**利点**:
- リアルタイムフィードバック
- 長時間実行タスクの進捗表示
- メモリ効率の向上

### Server-Sent Events (SSE)

**定義**: サーバーからクライアントへの一方向ストリーミング通信プロトコル。A2Aで使用されます。

### HTTP/HTTPS

**定義**: A2Aプロトコルが使用するトランスポート層。エージェント間の通信にHTTP/HTTPSを使用します。

## データ構造関連の用語

### Message（メッセージ）

**定義**: エージェント間で交換される情報の単位。

**主要フィールド**:
- `role`: メッセージの役割（user, agent, system）
- `parts`: メッセージの内容（テキスト、データ、ファイルなど）
- `messageId`: メッセージの一意の識別子
- `contextId`: 会話コンテキストの識別子

### Artifact（アーティファクト）

**定義**: タスクの実行結果。テキスト、JSONデータ、ファイルなど。

**種類**:
- Text Artifact: テキスト形式の結果
- Data Artifact: JSON形式のデータ
- File Artifact: ファイル形式の結果

### Workflow Graph（ワークフローグラフ）

**定義**: タスク間の依存関係を表す有向グラフ。NetworkXを使用して実装されています。

**主要概念**:
- Node（ノード）: 個々のタスク
- Edge（エッジ）: タスク間の依存関係
- Status（ステータス）: ノードの実行状態

## システムアーキテクチャ関連の用語

### Agent Discovery（エージェント発見）

**定義**: タスクに適したエージェントを見つけるプロセス。MCPサーバーを使用して実行されます。

**プロセス**:
1. タスクの要件を分析
2. MCPサーバーにクエリを送信
3. 適切なエージェントカードを取得
4. エージェントに接続

### Dynamic Orchestration（動的オーケストレーション）

**定義**: 実行時にエージェントを動的に発見し、割り当てるオーケストレーション方式。

**利点**:
- エージェントの追加・削除が容易
- 柔軟なワークフロー構成
- スケーラビリティの向上

### Context ID（コンテキストID）

**定義**: 会話セッションを識別する一意の識別子。複数のタスクが同じ会話に属することを示します。

### Task ID（タスクID）

**定義**: 個々のタスクを識別する一意の識別子。

## 関連ドキュメント

- [README.md](README.md) - プロジェクトの概要
- [動作マニュアル](OPERATION_MANUAL.md) - 使用方法の詳細
- [A2A SDK解説](A2A_SDK_GUIDE.md) - SDKの詳細な解説
- [FastAPI解説](FASTAPI_GUIDE.md) - Webフレームワークの解説
