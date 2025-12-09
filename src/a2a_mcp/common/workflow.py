import json
import logging
import uuid

from collections.abc import AsyncIterable
from enum import Enum
from uuid import uuid4

import httpx
import networkx as nx

from a2a.client import A2AClient
from a2a.client.errors import A2AClientHTTPError
from a2a.types import (
    AgentCard,
    MessageSendParams,
    SendStreamingMessageRequest,
    SendStreamingMessageSuccessResponse,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
)
from a2a_mcp.common.utils import get_mcp_server_config
from a2a_mcp.mcp import client


logger = logging.getLogger(__name__)


class Status(Enum):
    """Represents the status of a workflow and its associated node."""

    READY = 'READY'
    RUNNING = 'RUNNING'
    COMPLETED = 'COMPLETED'
    PAUSED = 'PAUSED'
    INITIALIZED = 'INITIALIZED'


class WorkflowNode:
    """Represents a single node in a workflow graph.

    Each node encapsulates a specific task to be executed, such as finding an
    agent or invoking an agent's capabilities. It manages its own state
    (e.g., READY, RUNNING, COMPLETED, PAUSED) and can execute its assigned task.

    """

    def __init__(
        self,
        task: str,
        node_key: str | None = None,
        node_label: str | None = None,
    ):
        self.id = str(uuid.uuid4())
        self.node_key = node_key
        self.node_label = node_label
        self.task = task
        self.results = None
        self.state = Status.READY

    async def get_planner_resource(self) -> AgentCard | None:
        logger.info(f'Getting resource for node {self.id}')
        config = get_mcp_server_config()
        async with client.init_session(
            config.host, config.port, config.transport
        ) as session:
            response = await client.find_resource(
                session, 'resource://agent_cards/planner_agent'
            )
            data = json.loads(response.contents[0].text)
            return AgentCard(**data['agent_card'][0])

    async def find_agent_for_task(self) -> AgentCard | None:
        logger.info(f'Find agent for task - {self.task}')
        config = get_mcp_server_config()
        async with client.init_session(
            config.host, config.port, config.transport
        ) as session:
            result = await client.find_agent(session, self.task)
            agent_card_json = json.loads(result.content[0].text)
            logger.debug(f'Found agent {agent_card_json} for task {self.task}')
            return AgentCard(**agent_card_json)

    async def run_node(
        self,
        query: str,
        task_id: str,
        context_id: str,
    ) -> AsyncIterable[dict[str, any]]:
        logger.info(f'Executing node {self.id}')
        agent_card = None
        if self.node_key == 'planner':
            agent_card = await self.get_planner_resource()
        else:
            agent_card = await self.find_agent_for_task()
        # Configure timeout for long-running agent operations
        # Use a longer timeout for streaming operations (5 minutes)
        timeout_config = httpx.Timeout(
            timeout=300.0,  # 5 minutes total timeout
            connect=30.0,   # 30 seconds to connect
            read=300.0,     # 5 minutes to read (for streaming)
            write=30.0,     # 30 seconds to write
            pool=10.0,      # 10 seconds for pool operations
        )
        
        async with httpx.AsyncClient(timeout=timeout_config) as httpx_client:
            client = A2AClient(httpx_client, agent_card)

            # Create request payload using dictionary format
            send_message_payload: dict[str, any] = {
                'message': {
                    'role': 'user',
                    'parts': [{'kind': 'text', 'text': query}],
                    'messageId': uuid4().hex,
                    'contextId': context_id,
                    # Note: taskId is NOT specified for new tasks - server will create it
                },
            }
            
            request = SendStreamingMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(**send_message_payload)
            )
            
            try:
                response_stream = client.send_message_streaming(request)
                async for chunk in response_stream:
                    # Save the artifact as a result of the node
                    if isinstance(
                        chunk.root, SendStreamingMessageSuccessResponse
                    ) and (isinstance(chunk.root.result, TaskArtifactUpdateEvent)):
                        artifact = chunk.root.result.artifact
                        self.results = artifact
                        # デバッグ: MCPからの結果を詳細にログ出力
                        logger.info("="*80)
                        logger.info(f"🔍 [MCP結果受信] ノードID: {self.id}")
                        logger.info(f"   Agent名: {self.node_label or self.node_key or 'Unknown'}")
                        logger.info(f"   タスク: {self.task}")
                        logger.info(f"   Artifact名: {artifact.name}")
                        print("\n" + "="*80)
                        print(f"🔍 [MCP結果受信] ノードID: {self.id}")
                        print(f"   Agent名: {self.node_label or self.node_key or 'Unknown'}")
                        print(f"   タスク: {self.task}")
                        print(f"   Artifact名: {artifact.name}")
                        if artifact.parts:
                            first_part = artifact.parts[0].root
                            if hasattr(first_part, 'text') and first_part.text:
                                text_preview = first_part.text[:500]
                                logger.info(f"   Artifact内容(テキスト): {text_preview}...")  # 最初の500文字
                                print(f"   Artifact内容(テキスト): {text_preview}...")
                            elif hasattr(first_part, 'data'):
                                data_str = json.dumps(first_part.data, ensure_ascii=False, indent=2)
                                logger.info(f"   Artifact内容(データ): {data_str}")
                                print(f"   Artifact内容(データ): {data_str}")
                        logger.info("="*80)
                        print("="*80 + "\n")
                    yield chunk
            except A2AClientHTTPError as e:
                # Handle A2A client HTTP errors (including connection issues)
                error_msg = f'HTTP error in node {self.id} execution: {e}'
                if 'peer closed connection' in str(e) or 'incomplete chunked read' in str(e):
                    error_msg += ' - Connection was closed by peer before response completed. This may indicate the agent took too long to respond or crashed.'
                logger.error(error_msg, exc_info=True)
                # Mark node as failed
                self.state = Status.PAUSED
                # Re-raise to let the workflow handle it
                raise RuntimeError(f'Node {self.id} failed: {error_msg}') from e
            except httpx.RemoteProtocolError as e:
                # Handle httpx remote protocol errors
                error_msg = f'Connection error in node {self.id} execution: {e}'
                logger.error(error_msg, exc_info=True)
                # Mark node as failed
                self.state = Status.PAUSED
                # Re-raise as RuntimeError to let the workflow handle it
                raise RuntimeError(f'Node {self.id} failed: {error_msg}') from e
            except httpx.ReadTimeout as e:
                # Handle read timeout errors
                error_msg = f'Read timeout in node {self.id} execution: Agent took too long to respond (timeout: {timeout_config.read}s)'
                logger.error(error_msg, exc_info=True)
                # Mark node as failed
                self.state = Status.PAUSED
                # Re-raise as RuntimeError to let the workflow handle it
                raise RuntimeError(f'Node {self.id} failed: {error_msg}') from e
            except Exception as e:
                # Handle any other exceptions
                error_msg = f'Unexpected error in node {self.id} execution: {e}'
                logger.error(error_msg, exc_info=True)
                # Mark node as failed
                self.state = Status.PAUSED
                # Re-raise to let the workflow handle it
                raise


class WorkflowGraph:
    """Represents a graph of workflow nodes."""

    def __init__(self) -> None:
        self.graph = nx.DiGraph()
        self.nodes = {}
        self.latest_node = None
        self.node_type = None
        self.state = Status.INITIALIZED
        self.paused_node_id = None

    def add_node(self, node) -> None:
        logger.info(f'Adding node {node.id}')
        self.graph.add_node(node.id, query=node.task)
        self.nodes[node.id] = node
        self.latest_node = node.id

    def add_edge(self, from_node_id: str, to_node_id: str) -> None:
        if from_node_id not in self.nodes or to_node_id not in self.nodes:
            raise ValueError('Invalid node IDs')

        self.graph.add_edge(from_node_id, to_node_id)

    async def run_workflow(
        self, start_node_id: str | None = None
    ) -> AsyncIterable[dict[str, any]]:
        logger.info('Executing workflow graph')
        if not start_node_id or start_node_id not in self.nodes:
            start_nodes = [n for n, d in self.graph.in_degree() if d == 0]
        else:
            start_nodes = [self.nodes[start_node_id].id]

        applicable_graph = set()

        for node_id in start_nodes:
            applicable_graph.add(node_id)
            applicable_graph.update(nx.descendants(self.graph, node_id))

        complete_graph = list(nx.topological_sort(self.graph))
        sub_graph = [n for n in complete_graph if n in applicable_graph]
        logger.info(f'Sub graph {sub_graph} size {len(sub_graph)}')
        self.state = Status.RUNNING
        # Alternative is to loop over all nodes, but we only need the connected nodes.
        for node_id in sub_graph:
            node = self.nodes[node_id]
            node.state = Status.RUNNING
            query = self.graph.nodes[node_id].get('query')
            task_id = self.graph.nodes[node_id].get('task_id')
            context_id = self.graph.nodes[node_id].get('context_id')
            try:
                async for chunk in node.run_node(query, task_id, context_id):
                    # When the workflow node is paused, do not yield any chunks
                    # but, let the loop complete.
                    if node.state != Status.PAUSED:
                        if isinstance(
                            chunk.root, SendStreamingMessageSuccessResponse
                        ) and (
                            isinstance(chunk.root.result, TaskStatusUpdateEvent)
                        ):
                            task_status_event = chunk.root.result
                            context_id = task_status_event.context_id
                            if (
                                task_status_event.status.state
                                == TaskState.input_required
                                and context_id
                            ):
                                node.state = Status.PAUSED
                                self.state = Status.PAUSED
                                self.paused_node_id = node.id
                        yield chunk
            except RuntimeError as e:
                # Handle node execution errors
                logger.error(f'Node {node_id} execution failed: {e}', exc_info=True)
                node.state = Status.PAUSED
                # Don't mark entire workflow as paused if we have results
                # Continue to next node or allow itinerary generation if we have results
                # Only pause if this is critical
                if 'critical' in str(e).lower() or 'fatal' in str(e).lower():
                    self.state = Status.PAUSED
                    self.paused_node_id = node.id
                    break
                # Otherwise, continue to next node
                logger.warning(f'Node {node_id} failed but continuing workflow')
                continue
            except Exception as e:
                # Handle unexpected errors
                logger.error(f'Unexpected error in node {node_id}: {e}', exc_info=True)
                node.state = Status.PAUSED
                # Don't mark entire workflow as paused if we have results
                # Continue to next node or allow itinerary generation if we have results
                logger.warning(f'Node {node_id} error but continuing workflow')
                continue
            if self.state == Status.PAUSED:
                break
            if node.state == Status.RUNNING:
                node.state = Status.COMPLETED
        # Mark workflow as completed if it was running and all nodes processed
        if self.state == Status.RUNNING:
            self.state = Status.COMPLETED
        elif self.state == Status.INITIALIZED and len(sub_graph) > 0:
            # If we processed nodes but state wasn't set, check if we should complete
            all_completed = all(self.nodes[n_id].state == Status.COMPLETED for n_id in sub_graph)
            if all_completed:
                self.state = Status.COMPLETED

    def set_node_attribute(self, node_id, attribute, value) -> None:
        nx.set_node_attributes(self.graph, {node_id: value}, attribute)

    def set_node_attributes(self, node_id, attr_val) -> None:
        nx.set_node_attributes(self.graph, {node_id: attr_val})

    def is_empty(self) -> bool:
        return self.graph.number_of_nodes() == 0
