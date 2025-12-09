# A2A SDK解説

このドキュメントでは、A2A（Agent-to-Agent）Python SDKの詳細な使用方法と、このプロジェクトでの実装について説明します。

## 目次

- [A2A SDK解説](#a2a-sdk解説)
  - [目次](#目次)
  - [A2A SDKとは](#a2a-sdkとは)
  - [SDKの主要コンポーネント](#sdkの主要コンポーネント)
  - [クライアント側の使用](#クライアント側の使用)
  - [サーバー側の使用](#サーバー側の使用)
  - [このプロジェクトでの実装](#このプロジェクトでの実装)
  - [実装例](#実装例)
  - [ベストプラクティス](#ベストプラクティス)
  - [トラブルシューティング](#トラブルシューティング)
  - [参考リソース](#参考リソース)

## A2A SDKとは

**A2A Python SDK**は、Googleが開発したAgent-to-Agentプロトコルを実装するPythonライブラリです。エージェント間の通信を簡単に実装できるように設計されています。

### 主要機能

- **エージェント間通信**: 標準化されたプロトコルでエージェントが通信
- **タスク管理**: タスクの送信、状態管理、キャンセル
- **ストリーミング**: リアルタイムでのタスク進行状況の更新
- **型安全性**: Pydanticモデルによる型安全なデータ構造
- **非同期処理**: `async/await`による非同期通信

## SDKの主要コンポーネント

### 1. A2AClient（クライアント）

他のエージェントと通信するためのクライアントライブラリ。

**主要クラス**:
- `A2AClient`: エージェントへの接続と通信を管理

**主要メソッド**:
- `send_message_streaming()`: ストリーミングでメッセージを送信
- `send_message()`: 同期でメッセージを送信

### 2. A2AServer（サーバー）

エージェントサーバーを構築するためのフレームワーク。

**主要クラス**:
- `A2AStarletteApplication`: StarletteベースのA2Aアプリケーション
- `DefaultRequestHandler`: デフォルトのリクエストハンドラー
- `AgentExecutor`: エージェントの実行を管理

### 3. 型定義（Types）

A2Aプロトコルのデータ構造を定義するPydanticモデル。

**主要型**:
- `AgentCard`: エージェントカード
- `Message`: メッセージ
- `Task`: タスク
- `TaskStatusUpdateEvent`: タスクステータス更新イベント
- `TaskArtifactUpdateEvent`: タスクアーティファクト更新イベント

## クライアント側の使用

### 基本的な使用方法

```python
from a2a.client import A2AClient
from a2a.types import AgentCard, MessageSendParams, SendStreamingMessageRequest
import httpx
from uuid import uuid4

# Agent Cardを取得
agent_card = AgentCard(
    name="My Agent",
    url="http://localhost:10101/",
    # ... その他のフィールド
)

# HTTPクライアントを作成
async with httpx.AsyncClient(timeout=60.0) as http_client:
    # A2Aクライアントを作成
    a2a_client = A2AClient(http_client, agent_card)
    
    # リクエストを作成
    request = SendStreamingMessageRequest(
        id=str(uuid4()),
        params=MessageSendParams(
            message={
                "role": "user",
                "parts": [{"kind": "text", "text": "Hello, Agent!"}],
                "messageId": str(uuid4()),
                "contextId": str(uuid4()),
            }
        )
    )
    
    # ストリーミングでメッセージを送信
    async for chunk in a2a_client.send_message_streaming(request):
        # レスポンスを処理
        if isinstance(chunk.root, SendStreamingMessageSuccessResponse):
            result = chunk.root.result
            # 結果を処理
            pass
```

### タイムアウト設定

長時間実行されるタスクには、タイムアウトを延長します：

```python
timeout_config = httpx.Timeout(
    timeout=300.0,  # 5分
    connect=30.0,   # 接続タイムアウト
    read=300.0,     # 読み取りタイムアウト
    write=30.0,     # 書き込みタイムアウト
)

async with httpx.AsyncClient(timeout=timeout_config) as http_client:
    a2a_client = A2AClient(http_client, agent_card)
    # ...
```

### エラーハンドリング

```python
from a2a.client.errors import A2AClientHTTPError

try:
    async for chunk in a2a_client.send_message_streaming(request):
        # 処理
        pass
except A2AClientHTTPError as e:
    print(f"HTTPエラー: {e}")
except httpx.ReadTimeout as e:
    print(f"タイムアウトエラー: {e}")
except Exception as e:
    print(f"予期しないエラー: {e}")
```

## サーバー側の使用

### エージェントサーバーの構築

```python
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)
from a2a.types import AgentCard
import uvicorn

# Agent Cardを読み込み
with open("agent_cards/my_agent.json") as f:
    agent_card_dict = json.load(f)
    agent_card = AgentCard(**agent_card_dict)

# タスクストアとプッシュ通知設定を作成
task_store = InMemoryTaskStore()
push_notification_config_store = InMemoryPushNotificationConfigStore()
push_notification_sender = BasePushNotificationSender()

# リクエストハンドラーを作成
request_handler = DefaultRequestHandler(
    task_store=task_store,
    push_notification_config_store=push_notification_config_store,
    push_notification_sender=push_notification_sender,
)

# A2Aアプリケーションを作成
app = A2AStarletteApplication(
    agent_card=agent_card,
    request_handler=request_handler,
)

# サーバーを起動
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10101)
```

### エージェントの実装

エージェントは`BaseAgent`を継承して実装します：

```python
from a2a_mcp.common.base_agent import BaseAgent
from collections.abc import AsyncIterable
from typing import Any

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name='MyAgent',
            description='My custom agent',
            content_types=['text', 'text/plain'],
        )
    
    async def invoke(self, query, session_id) -> dict:
        # 同期処理
        return {"result": "Hello"}
    
    async def stream(
        self, query, context_id, task_id
    ) -> AsyncIterable[dict[str, Any]]:
        # ストリーミング処理
        yield {
            'response_type': 'text',
            'is_task_complete': True,
            'require_user_input': False,
            'content': 'Hello, World!',
        }
```

### AgentExecutorの使用

```python
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Task, TaskState

class MyAgentExecutor(AgentExecutor):
    def __init__(self, agent: BaseAgent):
        self.agent = agent
    
    async def execute(
        self,
        task: Task,
        context: RequestContext,
        event_queue: EventQueue,
        task_updater: TaskUpdater,
    ):
        # タスクを実行
        query = task.message.parts[0].root.text
        
        # ストリーミングで処理
        async for response in self.agent.stream(
            query, task.context_id, task.id
        ):
            # イベントを送信
            if response.get('is_task_complete'):
                await task_updater.update_task_state(
                    task.id, TaskState.COMPLETED
                )
```

## このプロジェクトでの実装

### 1. Orchestrator Agent

`orchestrator_agent.py`では、以下のようにA2A SDKを使用しています：

```python
from a2a.client import A2AClient
from a2a.types import AgentCard, MessageSendParams, SendStreamingMessageRequest

# エージェントカードを取得
itinerary_agent_card = await self.get_itinerary_agent_card()

# A2Aクライアントを作成
async with httpx.AsyncClient(timeout=timeout_config) as httpx_client:
    a2a_client = A2AClient(httpx_client, itinerary_agent_card)
    
    # リクエストを作成
    request = SendStreamingMessageRequest(
        id=str(uuid4()),
        params=MessageSendParams(**send_message_payload)
    )
    
    # ストリーミングで送信
    async for chunk in a2a_client.send_message_streaming(request):
        # レスポンスを処理
        pass
```

### 2. エージェントサーバーの起動

`agents/__main__.py`では、A2A SDKを使用してエージェントサーバーを起動しています：

```python
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler

# A2Aアプリケーションを作成
app = A2AStarletteApplication(
    agent_card=agent_card,
    request_handler=request_handler,
)

# Uvicornで起動
uvicorn.run(app, host="0.0.0.0", port=port)
```

### 3. ワークフローでの使用

`workflow.py`では、複数のエージェントを順次呼び出しています：

```python
from a2a.client import A2AClient
from a2a.client.errors import A2AClientHTTPError

async def run_node(self, agent_card: AgentCard):
    async with httpx.AsyncClient(timeout=timeout_config) as httpx_client:
        client = A2AClient(httpx_client, agent_card)
        
        try:
            async for chunk in client.send_message_streaming(request):
                # 結果を処理
                if isinstance(chunk.root.result, TaskArtifactUpdateEvent):
                    self.results = chunk.root.result.artifact
        except A2AClientHTTPError as e:
            # エラーハンドリング
            raise RuntimeError(f"Node failed: {e}")
```

## 実装例

### シンプルなエージェント

```python
from a2a_mcp.common.base_agent import BaseAgent
from collections.abc import AsyncIterable
from typing import Any

class EchoAgent(BaseAgent):
    """入力されたテキストをそのまま返すエージェント"""
    
    def __init__(self):
        super().__init__(
            agent_name='EchoAgent',
            description='Echoes the input text',
            content_types=['text'],
        )
    
    async def stream(
        self, query, context_id, task_id
    ) -> AsyncIterable[dict[str, Any]]:
        yield {
            'response_type': 'text',
            'is_task_complete': True,
            'require_user_input': False,
            'content': query,
        }
```

### 複雑なエージェント（LLM使用）

```python
from google import genai
from a2a_mcp.common.base_agent import BaseAgent

class LLMAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name='LLMAgent',
            description='Uses LLM to process queries',
            content_types=['text'],
        )
        self.client = genai.Client()
    
    async def stream(
        self, query, context_id, task_id
    ) -> AsyncIterable[dict[str, Any]]:
        # LLMで処理
        response = self.client.models.generate_content(
            model='gemini-2.0-flash',
            contents=query,
        )
        
        yield {
            'response_type': 'text',
            'is_task_complete': True,
            'require_user_input': False,
            'content': response.text,
        }
```

## ベストプラクティス

### 1. タイムアウト設定

長時間実行されるタスクには、適切なタイムアウトを設定します：

```python
timeout_config = httpx.Timeout(
    timeout=300.0,  # タスクの予想実行時間に基づいて設定
    connect=30.0,
    read=300.0,
    write=30.0,
)
```

### 2. エラーハンドリング

すべてのA2A通信で適切なエラーハンドリングを実装します：

```python
try:
    async for chunk in a2a_client.send_message_streaming(request):
        # 処理
        pass
except A2AClientHTTPError as e:
    logger.error(f"A2A HTTPエラー: {e}")
    # フォールバック処理
except httpx.ReadTimeout as e:
    logger.error(f"タイムアウト: {e}")
    # リトライまたはエラー通知
except Exception as e:
    logger.error(f"予期しないエラー: {e}", exc_info=True)
```

### 3. ロギング

適切なロギングを実装して、デバッグと監視を容易にします：

```python
import logging

logger = logging.getLogger(__name__)

logger.info(f"エージェントに接続: {agent_card.url}")
logger.debug(f"リクエスト送信: {request.id}")
logger.info(f"レスポンス受信: {len(response)} bytes")
```

### 4. リソース管理

`async with`を使用して、リソースを適切に管理します：

```python
async with httpx.AsyncClient(timeout=timeout_config) as http_client:
    a2a_client = A2AClient(http_client, agent_card)
    # 処理
    # 自動的にクリーンアップ
```

### 5. 型安全性

型ヒントを活用して、コードの可読性と保守性を向上させます：

```python
from a2a.types import AgentCard, SendStreamingMessageRequest

async def call_agent(
    agent_card: AgentCard,
    message: str
) -> str:
    # 型安全な実装
    pass
```

## トラブルシューティング

### 問題1: 接続エラー

**症状**: `A2AClientHTTPError`が発生

**解決方法**:
1. エージェントが起動していることを確認
2. URLが正しいことを確認
3. ネットワーク接続を確認
4. ファイアウォール設定を確認

### 問題2: タイムアウトエラー

**症状**: `httpx.ReadTimeout`が発生

**解決方法**:
1. タイムアウト設定を延長
2. タスクの実行時間を確認
3. ネットワークの遅延を確認

### 問題3: 型エラー

**症状**: Pydanticバリデーションエラー

**解決方法**:
1. Agent Cardの形式を確認
2. メッセージの構造を確認
3. 型定義を確認

## 参考リソース

### 公式ドキュメント

- [A2A Protocol Specification](https://github.com/a2aproject/a2a-samples)
- [A2A Python SDK](https://github.com/a2aproject/a2a-samples/tree/main/samples/python)

### 関連プロジェクト

- [Starlette](https://www.starlette.io/) - A2Aサーバーの基盤
- [Pydantic](https://docs.pydantic.dev/) - 型定義とバリデーション
- [httpx](https://www.python-httpx.org/) - 非同期HTTPクライアント

### コード例

- このプロジェクトの`src/a2a_mcp/`ディレクトリ
- A2Aサンプルリポジトリの他の例

## まとめ

A2A Python SDKは、エージェント間通信を簡単に実装できる強力なツールです。このプロジェクトでは、以下のように使用されています：

1. **クライアント側**: 他のエージェントとの通信
2. **サーバー側**: エージェントサーバーの構築
3. **ワークフロー**: 複数エージェントの協調実行

適切なエラーハンドリング、タイムアウト設定、ロギングを実装することで、堅牢なエージェントシステムを構築できます。

## 関連ドキュメント

- [README.md](README.md) - プロジェクトの概要
- [動作マニュアル](OPERATION_MANUAL.md) - 使用方法の詳細
- [用語解説集](GLOSSARY.md) - A2AとMCPの用語解説
- [FastAPI解説](FASTAPI_GUIDE.md) - Webフレームワークの解説
