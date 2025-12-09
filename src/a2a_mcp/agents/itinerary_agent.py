# type: ignore

import json
import logging
import re

from collections.abc import AsyncIterable
from typing import Any

from a2a_mcp.common import prompts
from a2a_mcp.common.base_agent import BaseAgent
from a2a_mcp.common.utils import init_api_key
from google import genai
import json as json_lib


logger = logging.getLogger(__name__)


class ItineraryAgent(BaseAgent):
    """Itinerary Generation Agent that creates markdown itineraries from booking results."""

    def __init__(self):
        init_api_key()

        super().__init__(
            agent_name='ItineraryAgent',
            description='Generates comprehensive markdown itineraries from booking results',
            content_types=['text', 'text/plain'],
        )

        logger.info(f'Init {self.agent_name}')

    async def invoke(self, query, session_id) -> dict:
        logger.info(f'Running {self.agent_name} for session {session_id}')
        raise NotImplementedError('Please use the streaming function')

    async def stream(
        self, query, context_id, task_id
    ) -> AsyncIterable[dict[str, Any]]:
        """Generate itinerary from booking results provided in query.
        
        Query should contain JSON string with all booking results.
        """
        logger.info(
            f'Running {self.agent_name} stream for session {context_id} {task_id} - {query[:100]}...'
        )

        if not query:
            raise ValueError('Query cannot be empty')

        # Debug: Log the received query
        logger.info(f"📥 [旅程表エージェント] 受信したクエリ (最初の500文字): {str(query)[:500]}")
        print(f"\n📥 [旅程表エージェント] 受信したクエリ (最初の500文字): {str(query)[:500]}")
        
        try:
            # Parse booking results from query
            # Query format: JSON string containing list of booking artifacts
            # Try to handle different formats
            if isinstance(query, str):
                # Try to parse as JSON
                try:
                    booking_results = json_lib.loads(query)
                except json_lib.JSONDecodeError as e:
                    logger.warning(f'JSON解析エラー (最初の試行): {e}')
                    logger.debug(f'Query content (full): {query}')
                    print(f'⚠️ JSON解析エラー: {e}')
                    print(f'   クエリ内容 (最初の1000文字): {query[:1000]}')
                    # Try to extract JSON from the string if it's wrapped
                    # Sometimes the query might be wrapped in extra text
                    # Try to find JSON array or object in the string
                    # Use a more robust pattern to find JSON
                    # Try multiple strategies to extract JSON
                    # Strategy 1: Try to find JSON array or object (most common case)
                    # Look for JSON array first (most likely format)
                    json_match = re.search(r'(\[[\s\S]*\])', query)
                    if not json_match:
                        # Try to find JSON object
                        json_match = re.search(r'(\{[\s\S]*\})', query)
                    
                    if json_match:
                        try:
                            logger.info('JSONパターンが見つかりました。抽出を試みます...')
                            print('🔍 JSONパターンが見つかりました。抽出を試みます...')
                            extracted_json = json_match.group(1)
                            logger.debug(f'抽出したJSON (最初の200文字): {extracted_json[:200]}...')
                            booking_results = json_lib.loads(extracted_json)
                            logger.info('✅ JSON抽出成功')
                            print('✅ JSON抽出成功')
                        except json_lib.JSONDecodeError as e2:
                            logger.warning(f'抽出したJSONの解析に失敗: {e2}')
                            print(f'⚠️ 抽出したJSONの解析に失敗: {e2}')
                            # Strategy 2: Try to find the first valid JSON starting from the beginning
                            # Sometimes there might be extra characters before the JSON
                            booking_results = None
                            for start_pos in range(min(10, len(query))):
                                try:
                                    test_json = query[start_pos:]
                                    booking_results = json_lib.loads(test_json)
                                    logger.info(f'位置{start_pos}からJSON解析成功')
                                    print(f'✅ 位置{start_pos}からJSON解析成功')
                                    break
                                except json_lib.JSONDecodeError:
                                    continue
                            
                            if booking_results is None:
                                # Strategy 3: If all else fails, wrap the query as a single result
                                logger.warning('JSONが見つかりません。クエリをそのまま使用します。')
                                print('⚠️ JSONが見つかりません。クエリをそのまま使用します。')
                                booking_results = [{'text': query, 'raw_query': True}]
                    else:
                        # If it's not JSON, try to treat it as a single result
                        logger.warning('JSONが見つかりません。クエリをそのまま使用します。')
                        print('⚠️ JSONが見つかりません。クエリをそのまま使用します。')
                        booking_results = [{'text': query, 'raw_query': True}]
            else:
                # Already a dict or list
                booking_results = query
            
            logger.info(f"📋 [旅程表エージェント] 受信した予約結果数: {len(booking_results) if isinstance(booking_results, list) else 1}")
            print(f"\n📋 [旅程表エージェント] 受信した予約結果数: {len(booking_results) if isinstance(booking_results, list) else 1}")
            
            # Extract travel context and destination for attractions
            destination_city = None
            travel_context = {}
            
            for result in booking_results if isinstance(booking_results, list) else [booking_results]:
                if isinstance(result, dict):
                    # Handle direct dict results
                    if 'name' in result:
                        logger.info(f"   結果: {result['name']}")
                        print(f"   結果: {result['name']}")
                elif hasattr(result, 'name'):
                    # Handle artifact objects
                    logger.info(f"   結果: {result.name}")
                    print(f"   結果: {result.name}")
                    if hasattr(result, 'parts') and result.parts:
                        first_part = result.parts[0].root
                        if hasattr(first_part, 'data'):
                            data = first_part.data
                            if isinstance(data, dict):
                                # Extract destination from travel context or booking data
                                if 'trip_info' in data:
                                    travel_context = data['trip_info']
                                    destination_city = travel_context.get('destination', None)
                                elif 'destination' in data:
                                    destination_city = data['destination']
                                elif 'onward' in data:
                                    destination_city = data['onward'].get('arrival_city', None)
            
            # Get attractions if destination is available
            attractions_data = {}
            if destination_city:
                try:
                    attractions_json = await self.get_attractions(destination_city)
                    attractions_data = json_lib.loads(attractions_json) if attractions_json else {}
                    logger.info(f"🎯 観光地情報を取得: {destination_city}")
                    print(f"🎯 観光地情報を取得: {destination_city}")
                except Exception as e:
                    logger.warning(f"観光地情報の取得に失敗: {e}")
                    print(f"⚠️ 観光地情報の取得に失敗: {e}")
            
            # Convert results to JSON string for prompt
            travel_data_str = json_lib.dumps(booking_results, ensure_ascii=False, indent=2, default=str)
            attractions_str = json_lib.dumps(attractions_data, ensure_ascii=False, indent=2)
            
            logger.info(f"📝 [旅程表生成] Gemini API呼び出し開始")
            logger.debug(f"   旅行データサイズ: {len(travel_data_str)} 文字")
            logger.debug(f"   観光スポットデータサイズ: {len(attractions_str)} 文字")
            print(f"📝 [旅程表生成] Gemini API呼び出し開始")
            print(f"   旅行データサイズ: {len(travel_data_str)} 文字")
            print(f"   観光スポットデータサイズ: {len(attractions_str)} 文字")
            
            # Generate itinerary using Gemini
            client = genai.Client()
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompts.ITINERARY_GENERATION_INSTRUCTIONS.replace(
                    '{travel_data}', travel_data_str
                ).replace('{attractions_data}', attractions_str),
                config={
                    'temperature': 0.3,
                    'system_instruction': 'すべての応答を日本語で行ってください。詳細で実用的な旅程表を作成してください。マークダウン形式で整形してください。',
                },
            )
            
            itinerary = response.text
            
            logger.info(f"✅ [旅程表生成] Gemini API呼び出し完了")
            logger.debug(f"   生成された旅程表の長さ: {len(itinerary)} 文字")
            print(f"✅ [旅程表生成] Gemini API呼び出し完了")
            print(f"   生成された旅程表の長さ: {len(itinerary)} 文字\n")
            
            # Yield the itinerary as text response
            yield {
                'response_type': 'text',
                'is_task_complete': True,
                'require_user_input': False,
                'content': itinerary,
            }
            
        except json_lib.JSONDecodeError as e:
            logger.error(f'JSON解析エラー: {e}', exc_info=True)
            error_message = f'予約結果の解析に失敗しました: {str(e)}'
            yield {
                'response_type': 'text',
                'is_task_complete': True,
                'require_user_input': False,
                'content': error_message,
            }
        except Exception as e:
            logger.error(f'旅程表生成エラー: {e}', exc_info=True)
            error_message = f'旅程表の生成中にエラーが発生しました: {str(e)}'
            yield {
                'response_type': 'text',
                'is_task_complete': True,
                'require_user_input': False,
                'content': error_message,
            }

    async def get_attractions(self, destination: str) -> str:
        """Get attractions for the destination using MCP tool."""
        try:
            from a2a_mcp.mcp import client
            from a2a_mcp.common.utils import get_mcp_server_config
            
            config = get_mcp_server_config()
            async with client.init_session(
                config.host, config.port, config.transport
            ) as session:
                result = await client.call_tool(
                    session,
                    'get_attractions',
                    {'destination': destination}
                )
                if result.content:
                    return result.content[0].text
        except Exception as e:
            logger.warning(f'観光地情報取得エラー: {e}')
        return '{}'
