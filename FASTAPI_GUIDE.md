# FastAPI解説

このドキュメントでは、FastAPIの概要と、このプロジェクトでの使用方法について説明します。

## 目次

- [FastAPI解説](#fastapi解説)
  - [目次](#目次)
  - [FastAPIとは](#fastapiとは)
  - [FastAPIの特徴](#fastapiの特徴)
  - [このプロジェクトでの使用状況](#このプロジェクトでの使用状況)
  - [FastAPIの基本概念](#fastapiの基本概念)
  - [実装例](#実装例)
  - [ベストプラクティス](#ベストプラクティス)
  - [参考リソース](#参考リソース)

## FastAPIとは

**FastAPI**は、Python用のモダンで高速なWebフレームワークです。RESTful APIの構築に最適化されており、以下の特徴があります：

- **高速**: NodeJSやGoと同等のパフォーマンス
- **簡単**: 直感的なAPI設計
- **標準準拠**: OpenAPI（旧Swagger）とJSON Schemaに基づく
- **型安全性**: Pythonの型ヒントを活用した自動バリデーション
- **自動ドキュメント生成**: インタラクティブなAPIドキュメントを自動生成

## FastAPIの特徴

### 1. パフォーマンス

- **非同期処理**: `async/await`を完全サポート
- **高スループット**: UvicornやGunicornなどのASGIサーバーで実行
- **低レイテンシ**: 最適化されたリクエスト処理

### 2. 型安全性

Pythonの型ヒントを使用して、リクエストとレスポンスの型を定義できます：

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Item(BaseModel):
    name: str
    price: float

@app.post("/items/")
async def create_item(item: Item):
    return item
```

### 3. 自動ドキュメント生成

FastAPIは自動的に以下のドキュメントを生成します：

- **Swagger UI**: `/docs`でアクセス可能
- **ReDoc**: `/redoc`でアクセス可能

### 4. データバリデーション

Pydanticを使用して、リクエストデータの自動バリデーションとシリアライゼーションを提供します。

## このプロジェクトでの使用状況

このプロジェクトでは、FastAPIは**間接的に**使用されています。具体的には：

### 1. A2A SDKの依存関係

A2A Python SDKは、内部でFastAPIを使用してエージェントサーバーを構築します。`A2AStarletteApplication`は、Starlette（FastAPIの基盤）を使用しています。

### 2. エージェントサーバーの実装

`src/a2a_mcp/agents/__main__.py`で、A2A SDKを使用してエージェントサーバーを起動しています：

```python
from a2a.server.apps import A2AStarletteApplication
import uvicorn

# A2Aアプリケーションの作成
app = A2AStarletteApplication(...)

# Uvicornでサーバーを起動
uvicorn.run(app, host="0.0.0.0", port=10101)
```

### 3. エンドポイントの自動生成

A2A SDKは、以下のエンドポイントを自動的に生成します：

- `/.well-known/agent-card.json`: エージェントカードの取得
- `/a2a`: A2Aプロトコルエンドポイント（JSON-RPC 2.0）
- `/stream`: ストリーミングエンドポイント（SSE）

## FastAPIの基本概念

### アプリケーションの作成

```python
from fastapi import FastAPI

app = FastAPI(
    title="My API",
    description="APIの説明",
    version="1.0.0"
)
```

### ルートの定義

```python
@app.get("/")
async def read_root():
    return {"message": "Hello World"}

@app.post("/items/")
async def create_item(item: Item):
    return {"item": item}
```

### パスパラメータ

```python
@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}
```

### クエリパラメータ

```python
@app.get("/items/")
async def read_items(skip: int = 0, limit: int = 10):
    return {"skip": skip, "limit": limit}
```

### リクエストボディ

```python
from pydantic import BaseModel

class Item(BaseModel):
    name: str
    price: float

@app.post("/items/")
async def create_item(item: Item):
    return item
```

### 非同期処理

```python
import httpx

@app.get("/external-data/")
async def get_external_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        return response.json()
```

## 実装例

### 基本的なAPIサーバー

```python
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI()

class Item(BaseModel):
    name: str
    price: float

items: List[Item] = []

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/items/", response_model=List[Item])
async def get_items():
    return items

@app.post("/items/", response_model=Item)
async def create_item(item: Item):
    items.append(item)
    return item
```

### エラーハンドリング

```python
from fastapi import HTTPException

@app.get("/items/{item_id}")
async def read_item(item_id: int):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    return items[item_id]
```

### ミドルウェア

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### バックグラウンドタスク

```python
from fastapi import BackgroundTasks

def process_item(item: Item):
    # バックグラウンドで処理
    pass

@app.post("/items/")
async def create_item(item: Item, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_item, item)
    return item
```

## ベストプラクティス

### 1. 型ヒントの使用

常に型ヒントを使用して、コードの可読性と保守性を向上させます：

```python
from typing import List, Optional

@app.get("/items/", response_model=List[Item])
async def get_items(skip: int = 0, limit: int = 10) -> List[Item]:
    return items[skip:skip+limit]
```

### 2. Pydanticモデルの活用

リクエストとレスポンスの型をPydanticモデルで定義します：

```python
class ItemCreate(BaseModel):
    name: str
    price: float

class ItemResponse(BaseModel):
    id: int
    name: str
    price: float

@app.post("/items/", response_model=ItemResponse)
async def create_item(item: ItemCreate):
    # 処理
    return ItemResponse(id=1, **item.dict())
```

### 3. 依存性注入

共通の機能を依存性として注入します：

```python
from fastapi import Depends

def get_db():
    # データベース接続
    pass

@app.get("/items/")
async def get_items(db = Depends(get_db)):
    # データベースを使用
    pass
```

### 4. エラーハンドリング

適切なエラーレスポンスを返します：

```python
from fastapi import HTTPException, status

@app.get("/items/{item_id}")
async def read_item(item_id: int):
    if item_id < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid item ID"
        )
    # 処理
```

### 5. ロギング

適切なロギングを実装します：

```python
import logging

logger = logging.getLogger(__name__)

@app.post("/items/")
async def create_item(item: Item):
    logger.info(f"Creating item: {item.name}")
    # 処理
```

## 参考リソース

### 公式ドキュメント

- [FastAPI公式ドキュメント](https://fastapi.tiangolo.com/)
- [FastAPIチュートリアル](https://fastapi.tiangolo.com/tutorial/)
- [Pydanticドキュメント](https://docs.pydantic.dev/)

### 関連プロジェクト

- [Starlette](https://www.starlette.io/) - FastAPIの基盤
- [Uvicorn](https://www.uvicorn.org/) - ASGIサーバー
- [Pydantic](https://docs.pydantic.dev/) - データバリデーション

### 学習リソース

- [FastAPI GitHub](https://github.com/tiangolo/fastapi)
- [FastAPI Examples](https://github.com/tiangolo/fastapi/tree/master/docs_src)

## このプロジェクトでのFastAPIの役割

このプロジェクトでは、FastAPIは**A2A SDKの内部実装**として使用されています。開発者は直接FastAPIを操作する必要はありませんが、以下の点を理解しておくと役立ちます：

1. **エージェントサーバー**: A2A SDKがFastAPIを使用してエージェントサーバーを構築
2. **自動エンドポイント**: A2Aプロトコルに必要なエンドポイントが自動生成
3. **非同期処理**: すべてのエージェント処理は非同期で実行
4. **型安全性**: A2Aの型定義がPydanticモデルとして実装

## まとめ

FastAPIは、このプロジェクトでは間接的に使用されていますが、A2A SDKの基盤として重要な役割を果たしています。高速で型安全なAPIを構築するための優れたフレームワークであり、A2Aプロトコルの実装を支えています。

## 関連ドキュメント

- [README.md](README.md) - プロジェクトの概要
- [動作マニュアル](OPERATION_MANUAL.md) - 使用方法の詳細
- [用語解説集](GLOSSARY.md) - A2AとMCPの用語解説
- [A2A SDK解説](A2A_SDK_GUIDE.md) - SDKの詳細な解説
