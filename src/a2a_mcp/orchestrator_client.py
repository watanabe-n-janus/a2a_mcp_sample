#!/usr/bin/env python3
"""Client to interact with Orchestrator Agent for travel planning."""

import asyncio
import json
import logging
from typing import Optional
from uuid import uuid4

import click
import httpx
from a2a.client import A2AClient
from a2a.types import (
    AgentCard,
    MessageSendParams,
    SendStreamingMessageRequest,
    SendStreamingMessageSuccessResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
    TaskState,
)

logger = logging.getLogger(__name__)

# Import MCP modules at module level to avoid UnboundLocalError
# These are imported here to avoid circular import issues if imported at top
try:
    from a2a_mcp.mcp import client as mcp_client_module
    from a2a_mcp.common.utils import get_mcp_server_config as get_mcp_config
except ImportError:
    # If import fails, will import locally when needed
    mcp_client_module = None
    get_mcp_config = None


def format_itinerary(content: str) -> str:
    """Format itinerary content for display."""
    lines = []
    lines.append("\n" + "="*80)
    lines.append("🗓️  旅行旅程表")
    lines.append("="*80)
    lines.append(content)
    lines.append("="*80 + "\n")
    return "\n".join(lines)


async def handle_user_input_loop(
    a2a_client: A2AClient,
    context_id: str,
    task_id: str,
    show_mcp_interactions: bool,
    booking_results: list,
    initial_question: str = None,
) -> tuple[str, bool]:
    """Handle user input loop when input_required status is received.
    
    Args:
        a2a_client: A2A client instance
        context_id: Context ID for the conversation
        task_id: Task ID to continue
        show_mcp_interactions: Whether to show MCP interactions
        booking_results: List to append booking results to
        initial_question: Initial question to display (optional)
    
    Returns:
        tuple: (full_response, is_complete) - The final response and completion status
    """
    full_response = ""
    max_iterations = 10  # Prevent infinite loops
    iteration = 0
    current_question = initial_question
    
    while iteration < max_iterations:
        iteration += 1
        
        # Display question if available
        if current_question:
            print("\n" + "=" * 80)
            print(f"❓ {current_question}")
            print("=" * 80)
        else:
            print("\n" + "=" * 80)
            print("⏸️  ユーザー入力待ち...")
            print("=" * 80)
        
        # Get user input
        user_input = input("\n💬 回答を入力してください（空欄でスキップ、予約結果があれば旅程表を作成）: ").strip()
        
        if not user_input:
            print("⚠️  入力が空です。")
            # Check if we have booking results - if so, we can try to generate itinerary
            if booking_results:
                print(f"📋 {len(booking_results)}件の予約結果があります。旅程表作成を試みます...\n")
                # Return False to indicate we should try to generate itinerary with existing results
                return full_response, False
            else:
                print("予約結果もありません。処理を終了します。\n")
                break
        
        print(f"\n📤 回答を送信中: {user_input}\n")
        
        # Create a new message with user input
        user_message_payload: dict[str, any] = {
            'message': {
                'role': 'user',
                'parts': [{'kind': 'text', 'text': user_input}],
                'messageId': str(uuid4()),
                'contextId': context_id,
                'taskId': task_id,  # Continue the same task
            },
        }
        
        user_request = SendStreamingMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**user_message_payload)
        )
        
        # Process response from user input
        input_required_again = False
        task_completed = False
        
        async for user_chunk in a2a_client.send_message_streaming(user_request):
            if isinstance(user_chunk.root, SendStreamingMessageSuccessResponse):
                user_result = user_chunk.root.result
                
                # Handle status updates
                if isinstance(user_result, TaskStatusUpdateEvent):
                    user_status = user_result.status
                    if user_status.state == TaskState.input_required:
                        question = user_status.message.parts[0].root.text if user_status.message.parts else "追加情報が必要です"
                        current_question = question  # Update current question for next iteration
                        input_required_again = True
                    elif user_status.state == TaskState.completed:
                        print(f"\n✅ 予約タスク完了\n")
                        if show_mcp_interactions:
                            print("-" * 80)
                        task_completed = True
                        # Don't return yet - continue to receive final itinerary artifact
                        # The loop will continue to receive events until stream ends
                
                # Handle artifacts (this includes the final itinerary)
                if isinstance(user_result, TaskArtifactUpdateEvent):
                    artifact = user_result.artifact
                    if artifact.parts:
                        first_part = artifact.parts[0].root
                        
                        if hasattr(first_part, 'text') and first_part.text:
                            full_response = first_part.text
                            print(f"\n📋 旅程表を受け取りました: {artifact.name}\n")
                            # If we got the itinerary, mark as complete
                            # Continue to receive any remaining events, then return
                        elif hasattr(first_part, 'data'):
                            artifact_data = first_part.data
                            artifact_name = artifact.name
                            
                            booking_results.append({
                                'name': artifact_name,
                                'data': artifact_data
                            })
                            
                            print(f"📦 予約完了: {artifact_name}")
                            if show_mcp_interactions:
                                if isinstance(artifact_data, dict):
                                    if 'onward' in artifact_data:
                                        print(f"   ✈️  往路: {artifact_data.get('onward', {}).get('airline', 'N/A')} 便 {artifact_data.get('onward', {}).get('flight_number', 'N/A')}")
                                    if 'return' in artifact_data:
                                        print(f"   ✈️  復路: {artifact_data.get('return', {}).get('airline', 'N/A')} 便 {artifact_data.get('return', {}).get('flight_number', 'N/A')}")
                                    if 'name' in artifact_data:
                                        print(f"   🏨 ホテル: {artifact_data.get('name', 'N/A')}")
                                    if 'provider' in artifact_data:
                                        print(f"   🚗 レンタカー: {artifact_data.get('provider', 'N/A')}")
                                print("-" * 80)
        
        # After stream ends, check if we have the final response
        # If task is completed and we have the full response (itinerary), return with completion
        if task_completed and full_response:
            return full_response, True
        # If no more input required, break the loop
        if not input_required_again:
            break
    
    return full_response, False


async def execute_travel_plan(
    orchestrator_url: str,
    query: str,
    show_mcp_interactions: bool = True
) -> None:
    """Execute travel planning with Orchestrator Agent.
    
    Args:
        orchestrator_url: URL of the Orchestrator Agent
        query: User's travel query in Japanese
        show_mcp_interactions: Whether to show MCP interactions
    """
    # Declare global variables at the start of the function
    global mcp_client_module, get_mcp_config
    
    # Ensure MCP modules are imported
    if mcp_client_module is None or get_mcp_config is None:
        from a2a_mcp.mcp import client as mcp_client_module
        from a2a_mcp.common.utils import get_mcp_server_config as get_mcp_config
    
    print(f"\n{'='*80}")
    print(f"🚀 旅行計画を開始します")
    print(f"{'='*80}")
    print(f"📝 ユーザーリクエスト: {query}")
    print(f"{'='*80}\n")
    
    try:
        # Use a single httpx client for the entire operation
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            # Get Orchestrator Agent card
            orchestrator_card_url = f"{orchestrator_url.rstrip('/')}/.well-known/agent-card.json"
            response = await http_client.get(orchestrator_card_url)
            if response.status_code != 200:
                print(f"❌ エラー: Orchestrator Agent カードの取得に失敗しました (Status: {response.status_code})")
                return
            agent_card_dict = response.json()
            agent_card = AgentCard(**agent_card_dict)
            
            print(f"✓ Orchestrator Agent に接続しました: {agent_card.name}\n")
            
            # Create A2A client (must be inside the async with block)
            a2a_client = A2AClient(http_client, agent_card)
            
            # Generate IDs (don't specify taskId for new tasks - server will create it)
            context_id = str(uuid4())
            message_id = str(uuid4())
            
            # Create request payload using dictionary format (like helloworld example)
            send_message_payload: dict[str, any] = {
                'message': {
                    'role': 'user',
                    'parts': [{'kind': 'text', 'text': query}],
                    'messageId': message_id,
                    'contextId': context_id,
                    # Note: taskId is NOT specified for new tasks - server will create it
                },
            }
            
            request = SendStreamingMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(**send_message_payload)
            )
            
            full_response = ""
            mcp_interactions = []
            
            print("📡 Orchestrator Agent と対話中...\n")
            print("-" * 80)
            if show_mcp_interactions:
                print("🔄 MCPのやりとり:")
                print("-" * 80)
            
            booking_results = []
            current_task_id = None
            current_context_id = context_id
            
            async for chunk in a2a_client.send_message_streaming(request):
                # Handle MCP interactions (from logs or agent responses)
                if isinstance(chunk.root, SendStreamingMessageSuccessResponse):
                    result = chunk.root.result
                    
                    # Handle initial Task event (first event may be a Task object)
                    if isinstance(result, Task):
                        if result.id:
                            if not current_task_id:
                                logger.info(f'Setting initial task_id from Task event: {result.id}')
                            current_task_id = result.id
                        if result.context_id:
                            current_context_id = result.context_id
                        logger.debug(f'Task event - task_id: {current_task_id}, context_id: {current_context_id}')
                    
                    # Handle status updates
                    if isinstance(result, TaskStatusUpdateEvent):
                        status = result.status
                        # Get task_id and context_id from the event
                        # Python A2A library uses task_id field (as seen in cli/__main__.py)
                        # Try task_id first, then taskId, then id
                        event_task_id = getattr(result, 'task_id', None)
                        if not event_task_id:
                            event_task_id = getattr(result, 'taskId', None)
                        if not event_task_id:
                            event_task_id = getattr(result, 'id', None)
                        
                        # Try multiple ways to get context_id
                        event_context_id = getattr(result, 'contextId', None)
                        if not event_context_id:
                            event_context_id = getattr(result, 'context_id', None)
                        
                        # Update current values if found in event
                        # Always update task_id if we find it (first event should have it)
                        if event_task_id:
                            if not current_task_id:
                                logger.info(f'Setting initial task_id from event: {event_task_id}')
                            current_task_id = event_task_id
                        if event_context_id:
                            current_context_id = event_context_id
                        
                        # Debug logging - show all available attributes if task_id still not found
                        if not current_task_id:
                            logger.warning(f'TaskStatusUpdateEvent - task_id not found. Available attributes: {[attr for attr in dir(result) if not attr.startswith("_")]}')
                            # Try to get from model_dump if available
                            if hasattr(result, 'model_dump'):
                                try:
                                    dump = result.model_dump()
                                    logger.warning(f'TaskStatusUpdateEvent model_dump keys: {list(dump.keys()) if isinstance(dump, dict) else "N/A"}')
                                except Exception:
                                    pass
                        
                        logger.debug(f'TaskStatusUpdateEvent - task_id: {current_task_id}, context_id: {current_context_id}, event_task_id: {event_task_id}, event_context_id: {event_context_id}')
                        
                        if status.state == TaskState.input_required:
                            question = status.message.parts[0].root.text if status.message.parts else "追加情報が必要です"
                            print(f"\n⏸️  ユーザー入力が必要: {question}\n")
                            if show_mcp_interactions:
                                print("-" * 80)
                            
                            # Debug: Log current IDs
                            logger.info(f'Input required - current_task_id: {current_task_id}, current_context_id: {current_context_id}')
                            
                            # Handle user input interactively
                            # Use context_id from initial request if event doesn't have it
                            effective_context_id = current_context_id or context_id
                            effective_task_id = current_task_id
                            
                            if effective_task_id and effective_context_id:
                                user_response, is_complete = await handle_user_input_loop(
                                    a2a_client,
                                    effective_context_id,
                                    effective_task_id,
                                    show_mcp_interactions,
                                    booking_results,
                                    initial_question=question,  # Pass the initial question
                                )
                                
                                if user_response:
                                    full_response = user_response
                                
                                # Even if task is complete, continue to receive final itinerary
                                # The final itinerary will come as a TaskArtifactUpdateEvent
                                # Don't break here, let the main loop continue to receive final events
                                if is_complete:
                                    logger.info('User input loop completed, waiting for final itinerary...')
                                    # Continue the main loop to receive final events
                                    # The main loop will continue to process events until stream ends
                                    # Don't break - let it continue naturally
                            else:
                                print(f"⚠️  タスクIDまたはコンテキストIDが取得できませんでした。")
                                print(f"   タスクID: {effective_task_id}, コンテキストID: {effective_context_id}")
                                print(f"   イベントから取得した値 - task_id: {event_task_id}, context_id: {event_context_id}")
                                print(f"   初期コンテキストID: {context_id}\n")
                                
                        elif status.state == TaskState.completed:
                            print(f"\n✅ 予約タスク完了\n")
                            if show_mcp_interactions:
                                print("-" * 80)
                    
                    # Handle artifacts (booking results and final itinerary)
                    if isinstance(result, TaskArtifactUpdateEvent):
                        artifact = result.artifact
                        if artifact.parts:
                            # Check if it's a text artifact (itinerary) or data artifact (booking result)
                            first_part = artifact.parts[0].root
                            
                            # Check for text content (itinerary)
                            if hasattr(first_part, 'text') and first_part.text:
                                full_response = first_part.text
                                print(f"\n📋 旅程表を受け取りました: {artifact.name}\n")
                            # Check for data content (booking result)
                            elif hasattr(first_part, 'data'):
                                artifact_data = first_part.data
                                artifact_name = artifact.name
                                
                                booking_results.append({
                                    'name': artifact_name,
                                    'data': artifact_data
                                })
                                
                                print(f"📦 予約完了: {artifact_name}")
                                if show_mcp_interactions:
                                    # Format booking result nicely
                                    if isinstance(artifact_data, dict):
                                        if 'onward' in artifact_data:
                                            print(f"   ✈️  往路: {artifact_data.get('onward', {}).get('airline', 'N/A')} 便 {artifact_data.get('onward', {}).get('flight_number', 'N/A')}")
                                        if 'return' in artifact_data:
                                            print(f"   ✈️  復路: {artifact_data.get('return', {}).get('airline', 'N/A')} 便 {artifact_data.get('return', {}).get('flight_number', 'N/A')}")
                                        if 'name' in artifact_data:
                                            print(f"   🏨 ホテル: {artifact_data.get('name', 'N/A')}")
                                        if 'provider' in artifact_data:
                                            print(f"   🚗 レンタカー: {artifact_data.get('provider', 'N/A')}")
                                    print("-" * 80)
                    
                    # Handle status messages with text content
                    if isinstance(result, TaskStatusUpdateEvent):
                        status = result.status
                        if hasattr(status, 'message') and status.message:
                            if status.message.parts:
                                for part in status.message.parts:
                                    if hasattr(part, 'root') and hasattr(part.root, 'text'):
                                        text = part.root.text
                                        if text and text not in full_response:
                                            # This might be intermediate status, not final itinerary
                                            pass
            
            # After stream ends, check if we have booking results but no itinerary
            # If so, try to call itinerary agent directly
            if not full_response and booking_results and len(booking_results) > 0:
                logger.info(f'Stream ended with {len(booking_results)} booking results but no itinerary. Attempting itinerary generation...')
                print(f"\n📋 ストリーム終了: {len(booking_results)}件の予約結果がありますが、旅程表がありません。")
                print("旅程表作成を試みます...\n")
                
                # Request itinerary generation from orchestrator by sending a special message
                # or call itinerary agent directly
                try:
                    # Get MCP server config to find itinerary agent
                    # mcp_client_module and get_mcp_config are already declared as global at function start
                    config = get_mcp_config()
                    
                    async with mcp_client_module.init_session(
                        config.host, config.port, config.transport
                    ) as session:
                        # Find itinerary agent card
                        response = await mcp_client_module.find_resource(
                            session, 'resource://agent_cards/itinerary_agent'
                        )
                        data = json.loads(response.contents[0].text)
                        itinerary_agent_card = AgentCard(**data['agent_card'][0])
                        
                        # Call itinerary agent
                        booking_results_json = json.dumps(booking_results, ensure_ascii=False, default=str)
                        
                        async with httpx.AsyncClient(timeout=300.0) as itinerary_client:
                            itinerary_a2a_client = A2AClient(itinerary_client, itinerary_agent_card)
                            
                            itinerary_request = SendStreamingMessageRequest(
                                id=str(uuid4()),
                                params=MessageSendParams(**{
                                    'message': {
                                        'role': 'user',
                                        'parts': [{'kind': 'text', 'text': booking_results_json}],
                                        'messageId': str(uuid4()),
                                        'contextId': context_id,
                                    },
                                })
                            )
                            
                            logger.info('Calling itinerary agent directly with booking results...')
                            print('📞 旅程表作成エージェントを直接呼び出し中...')
                            
                            async for itinerary_chunk in itinerary_a2a_client.send_message_streaming(itinerary_request):
                                if isinstance(itinerary_chunk.root, SendStreamingMessageSuccessResponse):
                                    itinerary_result = itinerary_chunk.root.result
                                    if isinstance(itinerary_result, TaskArtifactUpdateEvent):
                                        artifact = itinerary_result.artifact
                                        if artifact.parts:
                                            first_part = artifact.parts[0].root
                                            if hasattr(first_part, 'text') and first_part.text:
                                                full_response = first_part.text
                                                logger.info(f'Received itinerary from agent: {len(full_response)} characters')
                                                print(f'✅ 旅程表を受信しました: {len(full_response)} 文字')
                                                break
                except Exception as e:
                    logger.error(f'Failed to call itinerary agent directly: {e}', exc_info=True)
                    print(f'⚠️ 旅程表作成エージェントの直接呼び出しに失敗: {e}')
            
            print("\n" + "=" * 80)
            
            # If we have booking results but no itinerary, try to request itinerary generation
            if not full_response and booking_results:
                print(f"\n📋 {len(booking_results)}件の予約結果が収集されました。")
                print("旅程表作成エージェントを呼び出して旅程表を生成します...\n")
                
                # Try to call itinerary agent directly with booking results
                try:
                    # Get orchestrator agent card to access itinerary agent
                        orchestrator_card_url = f"{orchestrator_url.rstrip('/')}/.well-known/agent-card.json"
                        response = await http_client.get(orchestrator_card_url)
                        if response.status_code == 200:
                            agent_card_dict = response.json()
                            # AgentCard is already imported at the top of the file
                            agent_card = AgentCard(**agent_card_dict)
                        
                        # Get MCP server config to find itinerary agent
                        # mcp_client_module and get_mcp_config are already declared as global at function start
                        config = get_mcp_config()
                        
                        async with mcp_client_module.init_session(
                            config.host, config.port, config.transport
                        ) as session:
                            # Find itinerary agent card
                            response = await mcp_client_module.find_resource(
                                session, 'resource://agent_cards/itinerary_agent'
                            )
                            data = json.loads(response.contents[0].text)
                            itinerary_agent_card = AgentCard(**data['agent_card'][0])
                            
                            # Call itinerary agent
                            # A2AClient, MessageSendParams, SendStreamingMessageRequest are already imported at the top
                            booking_results_json = json.dumps(booking_results, ensure_ascii=False, default=str)
                            
                            async with httpx.AsyncClient(timeout=300.0) as itinerary_client:
                                itinerary_a2a_client = A2AClient(itinerary_client, itinerary_agent_card)
                                
                                itinerary_request = SendStreamingMessageRequest(
                                    id=str(uuid4()),
                                    params=MessageSendParams(**{
                                        'message': {
                                            'role': 'user',
                                            'parts': [{'kind': 'text', 'text': booking_results_json}],
                                            'messageId': str(uuid4()),
                                            'contextId': context_id,
                                        },
                                    })
                                )
                                
                                async for itinerary_chunk in itinerary_a2a_client.send_message_streaming(itinerary_request):
                                    if isinstance(itinerary_chunk.root, SendStreamingMessageSuccessResponse):
                                        itinerary_result = itinerary_chunk.root.result
                                        if isinstance(itinerary_result, TaskArtifactUpdateEvent):
                                            artifact = itinerary_result.artifact
                                            if artifact.parts:
                                                first_part = artifact.parts[0].root
                                                if hasattr(first_part, 'text') and first_part.text:
                                                    full_response = first_part.text
                                                    break
                except Exception as e:
                    logger.error(f'旅程表作成エージェントの直接呼び出しに失敗: {e}', exc_info=True)
                    print(f"⚠️ 旅程表作成エージェントの呼び出しに失敗: {e}")
            
            # Display final itinerary
            if full_response:
                print("\n" + full_response)
                
                # Save to file
                with open('itinerary.txt', 'w', encoding='utf-8') as f:
                    f.write(full_response)
                print(f"\n💾 旅程表を 'itinerary.txt' に保存しました\n")
            else:
                print("\n⚠️  旅程表の生成に失敗しました。予約結果のみ表示します。\n")
                if booking_results:
                    for result in booking_results:
                        print(f"📋 {result['name']}:")
                        print(json.dumps(result['data'], ensure_ascii=False, indent=2))
                        print()
        
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(f"Error executing travel plan: {error_type}: {error_msg}", exc_info=True)
        print(f"\n❌ エラーが発生しました: {error_type}: {error_msg}\n")
        
        # Check if it's a connection error - might need to wait for server
        if '503' in error_msg or 'connection' in error_msg.lower() or 'closed' in error_msg.lower():
            print("💡 ヒント: サーバーが完全に起動していない可能性があります。")
            print("   - Orchestrator Agent がポート 10101 で起動しているか確認してください")
            print("   - ログファイル (logs/orchestrator_agent.log) を確認してください\n")
        
        import traceback
        traceback.print_exc()


@click.command()
@click.option('--orchestrator-url', default='http://localhost:10101', help='Orchestrator Agent URL')
@click.option('--query', help='Travel planning query in Japanese')
@click.option('--show-mcp/--no-show-mcp', default=True, help='Show MCP interactions')
def main(orchestrator_url: str, query: Optional[str], show_mcp: bool):
    """Travel planning client that interacts with Orchestrator Agent."""
    if not query:
        query = "フランスへの旅行を計画したいです。パリに3泊4日で、ビジネスクラスの航空券、スイートルームのホテルを予約してください。"
        print(f"ℹ️  デフォルトクエリを使用: {query}\n")
    
    asyncio.run(execute_travel_plan(orchestrator_url, query, show_mcp))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()

