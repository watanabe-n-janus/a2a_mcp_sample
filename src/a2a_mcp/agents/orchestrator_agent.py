import json
import logging

from collections.abc import AsyncIterable
from uuid import uuid4

import httpx

from a2a.client import A2AClient
from a2a.types import (
    AgentCard,
    MessageSendParams,
    SendStreamingMessageRequest,
    SendStreamingMessageSuccessResponse,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
)
# Import aliases for event types used in task ID mapping
from a2a.types import TaskArtifactUpdateEvent as TAUE
from a2a.types import TaskStatusUpdateEvent as TSUE
from a2a_mcp.common import prompts
from a2a_mcp.common.base_agent import BaseAgent
from a2a_mcp.common.utils import get_mcp_server_config, init_api_key
from a2a_mcp.common.workflow import Status, WorkflowGraph, WorkflowNode
from a2a_mcp.mcp import client
from google import genai
import json as json_lib


logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """Orchestrator Agent."""

    def __init__(self):
        init_api_key()
        super().__init__(
            agent_name='Orchestrator Agent',
            description='Facilitate inter agent communication',
            content_types=['text', 'text/plain'],
        )
        self.graph = None
        self.results = []
        self.travel_context = {}
        self.query_history = []
        self.context_id = None

    async def get_attractions(self, city: str) -> str:
        """Get attractions for a city from MCP server using SQL query."""
        try:
            import sqlite3
            import os
            from pathlib import Path
            
            # Find database file
            db_path = Path('travel_agency.db')
            if not db_path.exists():
                # Try script directory
                script_dir = Path(__file__).parent
                db_path = script_dir.parent.parent.parent / 'travel_agency.db'
            if not db_path.exists():
                # Try current working directory
                cwd = Path(os.getcwd())
                db_path = cwd / 'travel_agency.db'
            if not db_path.exists():
                # Try parent directories
                db_path = Path(__file__).parent.parent.parent.parent / 'travel_agency.db'
            
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = """
                    SELECT name, city, country, category, description, rating, 
                           opening_hours, entry_fee, recommended_duration_hours, tags
                    FROM attractions
                    WHERE city = ?
                    ORDER BY rating DESC
                    LIMIT 10
                """
                cursor.execute(query, (city,))
                rows = cursor.fetchall()
                result = {'results': [dict(row) for row in rows]}
                conn.close()
                return json_lib.dumps(result, ensure_ascii=False)
        except Exception as e:
            logger.error(f'Error fetching attractions: {e}')
        return json_lib.dumps({'results': []}, ensure_ascii=False)
    
    async def get_itinerary_agent_card(self) -> AgentCard | None:
        """Get the itinerary agent card from MCP server."""
        logger.info('Getting itinerary agent card from MCP server')
        config = get_mcp_server_config()
        async with client.init_session(
            config.host, config.port, config.transport
        ) as session:
            response = await client.find_resource(
                session, 'resource://agent_cards/itinerary_agent'
            )
            data = json.loads(response.contents[0].text)
            return AgentCard(**data['agent_card'][0])
    
    async def call_itinerary_agent(self, context_id: str, task_id: str) -> str:
        """Call the Itinerary Agent to generate itinerary from all booking results."""
        try:
            # Get itinerary agent card
            itinerary_agent_card = await self.get_itinerary_agent_card()
            if not itinerary_agent_card:
                logger.error('Failed to get itinerary agent card, falling back to local generation')
                return await self.generate_itinerary()
            
            # Prepare booking results as JSON string
            # Convert artifacts to serializable format
            booking_results_data = []
            for result in self.results:
                if hasattr(result, 'parts') and result.parts:
                    first_part = result.parts[0].root
                    if hasattr(first_part, 'data'):
                        booking_results_data.append({
                            'name': result.name if hasattr(result, 'name') else 'Unknown',
                            'data': first_part.data
                        })
                    elif hasattr(first_part, 'text'):
                        booking_results_data.append({
                            'name': result.name if hasattr(result, 'name') else 'Unknown',
                            'text': first_part.text
                        })
            
            query = json_lib.dumps(booking_results_data, ensure_ascii=False, default=str)
            
            logger.info(f'Calling Itinerary Agent at {itinerary_agent_card.url}')
            logger.info(f'Booking results data size: {len(query)} characters')
            logger.debug(f'Booking results data (first 500 chars): {query[:500]}')
            print(f'📞 旅程表作成エージェントを呼び出し中: {itinerary_agent_card.url}')
            print(f'   送信データサイズ: {len(query)} 文字')
            print(f'   送信データ (最初の200文字): {query[:200]}...')
            
            # Configure timeout
            timeout_config = httpx.Timeout(
                timeout=300.0,  # 5 minutes total timeout
                connect=30.0,   # 30 seconds to connect
                read=300.0,     # 5 minutes to read
                write=30.0,     # 30 seconds to write
            )
            
            async with httpx.AsyncClient(timeout=timeout_config) as httpx_client:
                a2a_client = A2AClient(httpx_client, itinerary_agent_card)
                
                # Create request
                send_message_payload: dict[str, any] = {
                    'message': {
                        'role': 'user',
                        'parts': [{'kind': 'text', 'text': query}],
                        'messageId': str(uuid4()),
                        'contextId': context_id,
                    },
                }
                
                request = SendStreamingMessageRequest(
                    id=str(uuid4()),
                    params=MessageSendParams(**send_message_payload)
                )
                
                # Stream response from itinerary agent
                itinerary_text = ""
                async for chunk in a2a_client.send_message_streaming(request):
                    if isinstance(chunk.root, SendStreamingMessageSuccessResponse):
                        result = chunk.root.result
                        if isinstance(result, TaskArtifactUpdateEvent):
                            artifact = result.artifact
                            if artifact.parts:
                                first_part = artifact.parts[0].root
                                if hasattr(first_part, 'text') and first_part.text:
                                    itinerary_text = first_part.text
                                    logger.debug(f'Received itinerary artifact: {len(itinerary_text)} chars')
                        elif isinstance(result, TaskStatusUpdateEvent):
                            status = result.status
                            if hasattr(status, 'message') and status.message:
                                if status.message.parts:
                                    for part in status.message.parts:
                                        if hasattr(part, 'root') and hasattr(part.root, 'text'):
                                            text = part.root.text
                                            if text:
                                                itinerary_text += text
                                                logger.debug(f'Received itinerary status text: {len(text)} chars')
                    # Check if chunk is a dict response (from agent_executor)
                    elif isinstance(chunk, dict):
                        if 'content' in chunk:
                            content = chunk['content']
                            if isinstance(content, str):
                                itinerary_text += content
                                logger.debug(f'Received itinerary dict content: {len(content)} chars')
            
            if itinerary_text:
                logger.info(f'Itinerary received from agent: {len(itinerary_text)} characters')
                return itinerary_text
            else:
                logger.warning('No itinerary received from agent, falling back to local generation')
                return await self.generate_itinerary()
                
        except Exception as e:
            logger.error(f'Error calling itinerary agent: {e}', exc_info=True)
            print(f'⚠️ 旅程表作成エージェントの呼び出しに失敗: {e}')
            print('ローカルで旅程表を生成します...')
            # Fallback to local generation
            return await self.generate_itinerary()

    async def generate_itinerary(self) -> str:
        """Generate detailed itinerary including attractions."""
        try:
            # Extract destination city from travel context
            destination = self.travel_context.get('destination', '')
            destination_airport = self.travel_context.get('destination_airport', '')
            
            # Map airport codes to cities
            airport_to_city = {
                'CDG': 'Paris', 'LHR': 'London', 'JFK': 'New York',
                'NRT': 'Tokyo', 'HND': 'Tokyo', 'FCO': 'Rome',
                'BCN': 'Barcelona', 'FRA': 'Frankfurt'
            }
            
            destination_city = airport_to_city.get(destination_airport, destination)
            
            # If destination is a multi-word city, try to match common patterns
            if not destination_city or destination_city == destination:
                # Try to extract city name from destination
                city_mapping = {
                    'paris': 'Paris', 'london': 'London', 'tokyo': 'Tokyo',
                    'new york': 'New York', 'rome': 'Rome', 'barcelona': 'Barcelona',
                    'パリ': 'Paris', 'ロンドン': 'London', '東京': 'Tokyo',
                    'ニューヨーク': 'New York', 'ローマ': 'Rome', 'バルセロナ': 'Barcelona'
                }
                destination_lower = destination.lower()
                for key, city in city_mapping.items():
                    if key in destination_lower:
                        destination_city = city
                        break
                if not destination_city:
                    destination_city = destination
            
            # Get attractions for the destination
            attractions_json = await self.get_attractions(destination_city)
            attractions_data = json_lib.loads(attractions_json) if attractions_json else {}
            
            # デバッグ: 収集した結果をすべて表示
            logger.info("="*80)
            logger.info("📋 [旅程表生成] 収集したすべての結果")
            logger.info(f"   結果数: {len(self.results)}")
            print("\n" + "="*80)
            print("📋 [旅程表生成] 収集したすべてのMCP結果")
            print(f"   結果数: {len(self.results)}")
            for idx, result in enumerate(self.results):
                logger.info(f"\n   結果 {idx+1}:")
                print(f"\n   結果 {idx+1}:")
                if hasattr(result, 'name'):
                    logger.info(f"     名前: {result.name}")
                    print(f"     名前: {result.name}")
                if hasattr(result, 'parts') and result.parts:
                    first_part = result.parts[0].root
                    if hasattr(first_part, 'text') and first_part.text:
                        text_preview = first_part.text[:300]
                        logger.info(f"     内容(テキスト): {text_preview}...")
                        print(f"     内容(テキスト): {text_preview}...")
                    elif hasattr(first_part, 'data'):
                        result_data_str = json_lib.dumps(first_part.data, ensure_ascii=False, indent=2)
                        if len(result_data_str) > 1000:
                            preview = result_data_str[:1000]
                            logger.info(f"     内容(データ): {preview}...")
                            print(f"     内容(データ): {preview}...")
                        else:
                            logger.info(f"     内容(データ): {result_data_str}")
                            print(f"     内容(データ): {result_data_str}")
            logger.info("="*80)
            print("="*80 + "\n")
            
            # Generate itinerary
            client = genai.Client()
            travel_data_str = json_lib.dumps(self.results, ensure_ascii=False, indent=2, default=str)
            attractions_str = json_lib.dumps(attractions_data, ensure_ascii=False, indent=2)
            
            logger.info(f"📝 [旅程表生成] Gemini API呼び出し開始")
            logger.debug(f"   旅行データサイズ: {len(travel_data_str)} 文字")
            logger.debug(f"   観光スポットデータサイズ: {len(attractions_str)} 文字")
            print(f"\n📝 [旅程表生成] Gemini API呼び出し開始")
            print(f"   旅行データサイズ: {len(travel_data_str)} 文字")
            print(f"   観光スポットデータサイズ: {len(attractions_str)} 文字")
            
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
            logger.info(f"✅ [旅程表生成] Gemini API呼び出し完了")
            logger.debug(f"   生成された旅程表の長さ: {len(response.text)} 文字")
            print(f"✅ [旅程表生成] Gemini API呼び出し完了")
            print(f"   生成された旅程表の長さ: {len(response.text)} 文字\n")
            return response.text
        except Exception as e:
            logger.error(f'Error generating itinerary: {e}')
            # Fallback to summary
            return await self.generate_summary()

    async def generate_summary(self) -> str:
        client = genai.Client()
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompts.SUMMARY_COT_INSTRUCTIONS.replace(
                '{travel_data}', str(self.results)
            ),
            config={
                'temperature': 0.0,
                'system_instruction': 'すべての応答を日本語で行ってください。',
            },
        )
        return response.text

    def answer_user_question(self, question) -> str:
        try:
            client = genai.Client()
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompts.QA_COT_PROMPT.replace(
                    '{TRIP_CONTEXT}', str(self.travel_context)
                )
                .replace('{CONVERSATION_HISTORY}', str(self.query_history))
                .replace('{TRIP_QUESTION}', question),
                config={
                    'temperature': 0.0,
                    'response_mime_type': 'application/json',
                    'system_instruction': 'すべての応答を日本語で行ってください。JSONフォーマットのフィールド名は英語のまま、値は日本語で記述してください。',
                },
            )
            return response.text
        except Exception as e:
            logger.info(f'Error answering user question: {e}')
        return '{"can_answer": "no", "answer": "Cannot answer based on provided context"}'

    def set_node_attributes(
        self, node_id, task_id=None, context_id=None, query=None
    ):
        attr_val = {}
        if task_id:
            attr_val['task_id'] = task_id
        if context_id:
            attr_val['context_id'] = context_id
        if query:
            attr_val['query'] = query

        self.graph.set_node_attributes(node_id, attr_val)

    def add_graph_node(
        self,
        task_id,
        context_id,
        query: str,
        node_id: str = None,
        node_key: str = None,
        node_label: str = None,
    ) -> WorkflowNode:
        """Add a node to the graph."""
        node = WorkflowNode(
            task=query, node_key=node_key, node_label=node_label
        )
        self.graph.add_node(node)
        if node_id:
            self.graph.add_edge(node_id, node.id)
        self.set_node_attributes(node.id, task_id, context_id, query)
        return node

    def clear_state(self):
        self.graph = None
        self.results.clear()
        self.travel_context.clear()
        self.query_history.clear()

    async def stream(
        self, query, context_id, task_id
    ) -> AsyncIterable[dict[str, any]]:
        """Execute and stream response."""
        logger.info(
            f'Running {self.agent_name} stream for session {context_id}, task {task_id} - {query}'
        )
        if not query:
            raise ValueError('Query cannot be empty')
        if self.context_id != context_id:
            # Clear state when the context changes
            self.clear_state()
            self.context_id = context_id

        self.query_history.append(query)
        start_node_id = None
        # Graph does not exist, start a new graph with planner node.
        if not self.graph:
            self.graph = WorkflowGraph()
            planner_node = self.add_graph_node(
                task_id=task_id,
                context_id=context_id,
                query=query,
                node_key='planner',
                node_label='Planner',
            )
            start_node_id = planner_node.id
        # Paused state is when the agent might need more information.
        elif self.graph.state == Status.PAUSED:
            start_node_id = self.graph.paused_node_id
            self.set_node_attributes(node_id=start_node_id, query=query)

        # This loop can be avoided if the workflow graph is dynamic or
        # is built from the results of the planner when the planner
        # iself is not a part of the graph.
        # TODO: Make the graph dynamically iterable over edges
        while True:
            # Set attributes on the node so we propagate task and context
            self.set_node_attributes(
                node_id=start_node_id,
                task_id=task_id,
                context_id=context_id,
            )
            # Resume workflow, used when the workflow nodes are updated.
            should_resume_workflow = False
            try:
                async for chunk in self.graph.run_workflow(
                    start_node_id=start_node_id
                ):
                    if isinstance(chunk.root, SendStreamingMessageSuccessResponse):
                        # The graph node retured TaskStatusUpdateEvent
                        # Check if the node is complete and continue to the next node
                        if isinstance(chunk.root.result, TaskStatusUpdateEvent):
                            task_status_event = chunk.root.result
                            # Map task id to the original orchestrator task_id
                            # This ensures consistency with the TaskManager
                            # Check both 'id' and 'task_id' attributes (different A2A versions may use different field names)
                            event_task_id = getattr(task_status_event, 'id', None) or getattr(task_status_event, 'task_id', None)
                            
                            # Only map if task_id is different
                            if event_task_id and event_task_id != task_id:
                                logger.info(
                                    f'Mapping TaskStatusUpdateEvent: task_id {event_task_id} -> {task_id}'
                                )
                                # Create a new event with the correct task id
                                try:
                                    # Extract all fields from the original event
                                    status = getattr(task_status_event, 'status', None)
                                    final = getattr(task_status_event, 'final', None)
                                    metadata = getattr(task_status_event, 'metadata', None)
                                    # Python A2A library requires contextId and taskId fields
                                    event_context_id = getattr(task_status_event, 'contextId', None) or getattr(task_status_event, 'context_id', None) or context_id
                                    event_task_id_field = getattr(task_status_event, 'taskId', None) or getattr(task_status_event, 'task_id', None)
                                    
                                    # Create new event with correct task_id
                                    # Python A2A library requires: id, contextId, taskId, status, final, metadata
                                    task_status_event = TSUE(
                                        id=task_id,
                                        contextId=event_context_id,
                                        taskId=task_id,  # Use the new task_id
                                        status=status,
                                        final=final,
                                        metadata=metadata,
                                    )
                                    chunk.root.result = task_status_event
                                    logger.debug(f'Successfully mapped TaskStatusUpdateEvent to task_id={task_id}, contextId={event_context_id}')
                                except Exception as e:
                                    logger.error(f'Failed to map task id in TaskStatusUpdateEvent: {e}', exc_info=True)
                                    # Try alternative approach: modify in place if possible
                                    try:
                                        if hasattr(task_status_event, 'id'):
                                            object.__setattr__(task_status_event, 'id', task_id)
                                        if hasattr(task_status_event, 'taskId'):
                                            object.__setattr__(task_status_event, 'taskId', task_id)
                                        elif hasattr(task_status_event, 'task_id'):
                                            object.__setattr__(task_status_event, 'task_id', task_id)
                                        logger.debug(f'Successfully updated TaskStatusUpdateEvent in place')
                                    except Exception as e2:
                                        logger.error(f'Failed to update TaskStatusUpdateEvent in place: {e2}', exc_info=True)
                                        # Continue with original event if all mapping fails
                            
                            # Update context_id from event if available, otherwise keep the original
                            event_context_id = getattr(task_status_event, 'contextId', None) or getattr(task_status_event, 'context_id', None)
                            if event_context_id:
                                context_id = event_context_id
                            if (
                                task_status_event.status.state
                                == TaskState.completed
                                and context_id
                            ):
                                ## yeild??
                                continue
                            if (
                                task_status_event.status.state
                                == TaskState.input_required
                            ):
                                question = task_status_event.status.message.parts[
                                    0
                                ].root.text

                                try:
                                    answer = json.loads(
                                        self.answer_user_question(question)
                                    )
                                    logger.info(f'Agent Answer {answer}')
                                    if answer['can_answer'] == 'yes':
                                        # Orchestrator can answer on behalf of the user set the query
                                        # Resume workflow from paused state.
                                        query = answer['answer']
                                        start_node_id = self.graph.paused_node_id
                                        self.set_node_attributes(
                                            node_id=start_node_id, query=query
                                        )
                                        should_resume_workflow = True
                                except Exception:
                                    logger.info('Cannot convert answer data')
                        
                        # The graph node retured TaskArtifactUpdateEvent
                        # Store the node and continue.
                        if isinstance(chunk.root.result, TaskArtifactUpdateEvent):
                            task_artifact_event = chunk.root.result
                            # Map task id to the original orchestrator task_id
                            # This ensures consistency with the TaskManager
                            # Check both 'id' and 'task_id' attributes (different A2A versions may use different field names)
                            event_task_id = getattr(task_artifact_event, 'id', None) or getattr(task_artifact_event, 'task_id', None)
                            
                            # Only map if task_id is different
                            if event_task_id and event_task_id != task_id:
                                logger.info(
                                    f'Mapping TaskArtifactUpdateEvent: task_id {event_task_id} -> {task_id}'
                                )
                                # Create a new event with the correct task id
                                try:
                                    # Extract all fields from the original event
                                    artifact = getattr(task_artifact_event, 'artifact', None)
                                    final = getattr(task_artifact_event, 'final', None)
                                    metadata = getattr(task_artifact_event, 'metadata', None)
                                    # Python A2A library requires contextId and taskId fields
                                    event_context_id = getattr(task_artifact_event, 'contextId', None) or getattr(task_artifact_event, 'context_id', None) or context_id
                                    event_task_id_field = getattr(task_artifact_event, 'taskId', None) or getattr(task_artifact_event, 'task_id', None)
                                    
                                    # Create new event with correct task_id
                                    # Python A2A library requires: id, contextId, taskId, artifact, final, metadata
                                    task_artifact_event = TAUE(
                                        id=task_id,
                                        contextId=event_context_id,
                                        taskId=task_id,  # Use the new task_id
                                        artifact=artifact,
                                        final=final,
                                        metadata=metadata,
                                    )
                                    chunk.root.result = task_artifact_event
                                    logger.debug(f'Successfully mapped TaskArtifactUpdateEvent to task_id={task_id}, contextId={event_context_id}')
                                except Exception as e:
                                    logger.error(f'Failed to map task id in TaskArtifactUpdateEvent: {e}', exc_info=True)
                                    # Try alternative approach: modify in place if possible
                                    try:
                                        if hasattr(task_artifact_event, 'id'):
                                            object.__setattr__(task_artifact_event, 'id', task_id)
                                        if hasattr(task_artifact_event, 'taskId'):
                                            object.__setattr__(task_artifact_event, 'taskId', task_id)
                                        elif hasattr(task_artifact_event, 'task_id'):
                                            object.__setattr__(task_artifact_event, 'task_id', task_id)
                                        logger.debug(f'Successfully updated TaskArtifactUpdateEvent in place')
                                    except Exception as e2:
                                        logger.error(f'Failed to update TaskArtifactUpdateEvent in place: {e2}', exc_info=True)
                                        # Continue with original event if all mapping fails
                            artifact = task_artifact_event.artifact
                            self.results.append(artifact)
                            
                            # デバッグ: MCPからの結果を詳細にログ出力
                            logger.info("="*80)
                            logger.info(f"🔍 [MCP結果回収] Orchestrator Agent")
                            logger.info(f"   Artifact名: {artifact.name}")
                            logger.info(f"   現在の結果数: {len(self.results)}")
                            print("\n" + "="*80)
                            print(f"🔍 [MCP結果回収] Orchestrator Agent")
                            print(f"   Artifact名: {artifact.name}")
                            print(f"   現在の結果数: {len(self.results)}")
                            if artifact.parts:
                                first_part = artifact.parts[0].root
                                if hasattr(first_part, 'text') and first_part.text:
                                    text_preview = first_part.text[:500]
                                    logger.info(f"   Artifact内容(テキスト): {text_preview}...")  # 最初の500文字
                                    print(f"   Artifact内容(テキスト): {text_preview}...")
                                elif hasattr(first_part, 'data'):
                                    artifact_data_str = json_lib.dumps(first_part.data, ensure_ascii=False, indent=2)
                                    logger.info(f"   Artifact内容(データ):")
                                    print(f"   Artifact内容(データ):")
                                    # 長い場合は最初の1000文字を表示
                                    if len(artifact_data_str) > 1000:
                                        preview = artifact_data_str[:1000]
                                        logger.info(f"   {preview}...")
                                        print(f"   {preview}...")
                                    else:
                                        logger.info(f"   {artifact_data_str}")
                                        print(f"   {artifact_data_str}")
                            logger.info("="*80)
                            print("="*80 + "\n")
                            
                            if artifact.name == 'PlannerAgent-result':
                                # Planning agent returned data, update graph.
                                artifact_data = artifact.parts[0].root.data
                                if 'trip_info' in artifact_data:
                                    self.travel_context = artifact_data['trip_info']
                                logger.info(
                                    f'Updating workflow with {len(artifact_data["tasks"])} task nodes'
                                )
                                # Define the edges
                                current_node_id = start_node_id
                                for idx, task_data in enumerate(
                                    artifact_data['tasks']
                                ):
                                    node = self.add_graph_node(
                                        task_id=task_id,
                                        context_id=context_id,
                                        query=task_data['description'],
                                        node_id=current_node_id,
                                    )
                                    current_node_id = node.id
                                    # Restart graph from the newly inserted subgraph state
                                    # Start from the new node just created.
                                    if idx == 0:
                                        should_resume_workflow = True
                                        start_node_id = node.id
                            else:
                                # Not planner but artifacts from other tasks,
                                # continue to the next node in the workflow.
                                # client does not get the artifact,
                                # a summary is shown at the end of the workflow.
                                continue
                    # When the workflow needs to be resumed, do not yield partial.
                    if not should_resume_workflow:
                        logger.info('No workflow resume detected, yielding chunk')
                        # Yield partial execution
                        yield chunk
                # The graph is complete and no updates, so okay to break from the loop.
                if not should_resume_workflow:
                    logger.info(
                        'Workflow iteration complete and no restart requested. Exiting main loop.'
                    )
                    break
                else:
                    # Readable logs
                    logger.info('Restarting workflow loop.')
            except RuntimeError as e:
                # Handle workflow execution errors
                logger.error(f'Workflow execution failed: {e}', exc_info=True)
                # Even if there's an error, if we have results, try to generate itinerary
                if self.results:
                    logger.info(f'Workflow error but have {len(self.results)} results, attempting itinerary generation')
                    print(f"\n⚠️ ワークフローでエラーが発生しましたが、{len(self.results)}件の予約結果があります。")
                    print("旅程表作成を試みます...\n")
                    try:
                        itinerary = await self.call_itinerary_agent(context_id, task_id)
                        self.clear_state()
                        logger.info(f'Itinerary generated after error: {len(itinerary)} characters')
                        yield {
                            'response_type': 'text',
                            'is_task_complete': True,
                            'require_user_input': False,
                            'content': itinerary,
                        }
                        return
                    except Exception as itinerary_error:
                        logger.error(f'Failed to generate itinerary after error: {itinerary_error}', exc_info=True)
                
                error_message = f'ワークフローの実行中にエラーが発生しました: {str(e)}'
                yield {
                    'response_type': 'text',
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': error_message,
                }
                # Mark workflow as paused/failed
                self.graph.state = Status.PAUSED
                return
            except Exception as e:
                # Handle unexpected errors
                logger.error(f'Unexpected error in workflow: {e}', exc_info=True)
                # Even if there's an error, if we have results, try to generate itinerary
                if self.results:
                    logger.info(f'Unexpected error but have {len(self.results)} results, attempting itinerary generation')
                    print(f"\n⚠️ 予期しないエラーが発生しましたが、{len(self.results)}件の予約結果があります。")
                    print("旅程表作成を試みます...\n")
                    try:
                        itinerary = await self.call_itinerary_agent(context_id, task_id)
                        self.clear_state()
                        logger.info(f'Itinerary generated after error: {len(itinerary)} characters')
                        yield {
                            'response_type': 'text',
                            'is_task_complete': True,
                            'require_user_input': False,
                            'content': itinerary,
                        }
                        return
                    except Exception as itinerary_error:
                        logger.error(f'Failed to generate itinerary after error: {itinerary_error}', exc_info=True)
                
                error_message = f'予期しないエラーが発生しました: {str(e)}'
                yield {
                    'response_type': 'text',
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': error_message,
                }
                # Mark workflow as paused/failed
                self.graph.state = Status.PAUSED
                return
        
        # Check if workflow completed or if we have results to generate itinerary
        if self.graph.state == Status.COMPLETED or (self.results and len(self.results) > 0):
            # All individual actions complete, now generate the itinerary using Itinerary Agent
            logger.info(f'Workflow state: {self.graph.state}, Results count: {len(self.results)}')
            print(f"\n{'='*80}")
            print(f"📅 予約完了。旅程表作成エージェントを呼び出し中...")
            print(f"   ワークフロー状態: {self.graph.state}")
            print(f"   収集された結果数: {len(self.results)}")
            print(f"{'='*80}\n")
            
            if not self.results or len(self.results) == 0:
                logger.warning('No results collected, cannot generate itinerary')
                yield {
                    'response_type': 'text',
                    'is_task_complete': True,
                    'require_user_input': False,
                    'content': '予約結果が収集されませんでした。旅程表を生成できません。',
                }
                return
            
            # Call Itinerary Agent to generate the itinerary
            logger.info(f'All bookings completed. Calling Itinerary Agent for {len(self.results)} booking results')
            try:
                itinerary = await self.call_itinerary_agent(context_id, task_id)
                self.clear_state()
                logger.info(f'Itinerary generated: {len(itinerary)} characters')
                
                yield {
                    'response_type': 'text',
                    'is_task_complete': True,
                    'require_user_input': False,
                    'content': itinerary,
                }
            except Exception as e:
                logger.error(f'Failed to call itinerary agent: {e}', exc_info=True)
                print(f'⚠️ 旅程表作成エージェントの呼び出しに失敗: {e}')
                # Fallback to local generation
                try:
                    itinerary = await self.generate_itinerary()
                    self.clear_state()
                    yield {
                        'response_type': 'text',
                        'is_task_complete': True,
                        'require_user_input': False,
                        'content': itinerary,
                    }
                except Exception as fallback_error:
                    logger.error(f'Fallback itinerary generation also failed: {fallback_error}', exc_info=True)
                    yield {
                        'response_type': 'text',
                        'is_task_complete': True,
                        'require_user_input': False,
                        'content': f'旅程表の生成に失敗しました: {str(fallback_error)}',
                    }
