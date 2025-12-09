# type:ignore
import asyncio
import json
import os

from contextlib import asynccontextmanager

import click

from fastmcp.utilities.logging import get_logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, ReadResourceResult


logger = get_logger(__name__)

env = {
    'GOOGLE_API_KEY': os.getenv('GOOGLE_API_KEY'),
}


@asynccontextmanager
async def init_session(host, port, transport):
    """Initializes and manages an MCP ClientSession based on the specified transport.

    This asynchronous context manager establishes a connection to an MCP server
    using either Server-Sent Events (SSE) or Standard I/O (STDIO) transport.
    It handles the setup and teardown of the connection and yields an active
    `ClientSession` object ready for communication.

    Args:
        host: The hostname or IP address of the MCP server (used for SSE).
        port: The port number of the MCP server (used for SSE).
        transport: The communication transport to use ('sse' or 'stdio').

    Yields:
        ClientSession: An initialized and ready-to-use MCP client session.

    Raises:
        ValueError: If an unsupported transport type is provided (implicitly,
                    as it won't match 'sse' or 'stdio').
        Exception: Other potential exceptions during client initialization or
                   session setup.
    """
    if transport == 'sse':
        url = f'http://{host}:{port}/sse'
        async with sse_client(url) as (read_stream, write_stream):
            async with ClientSession(
                read_stream=read_stream, write_stream=write_stream
            ) as session:
                logger.debug('SSE ClientSession created, initializing...')
                await session.initialize()
                logger.info('SSE ClientSession initialized successfully.')
                yield session
    elif transport == 'stdio':
        if not os.getenv('GOOGLE_API_KEY'):
            logger.error('GOOGLE_API_KEY is not set')
            raise ValueError('GOOGLE_API_KEY is not set')
        stdio_params = StdioServerParameters(
            command='uv',
            args=['run', 'a2a-mcp'],
            env=env,
        )
        async with stdio_client(stdio_params) as (read_stream, write_stream):
            async with ClientSession(
                read_stream=read_stream,
                write_stream=write_stream,
            ) as session:
                logger.debug('STDIO ClientSession created, initializing...')
                await session.initialize()
                logger.info('STDIO ClientSession initialized successfully.')
                yield session
    else:
        logger.error(f'Unsupported transport type: {transport}')
        raise ValueError(
            f"Unsupported transport type: {transport}. Must be 'sse' or 'stdio'."
        )


def format_agent_result(data: dict) -> str:
    """Format agent card result in Japanese."""
    lines = []
    lines.append("\n" + "="*60)
    lines.append("🔍 検索結果: 最適なエージェントが見つかりました")
    lines.append("="*60)
    
    if 'name' in data:
        lines.append(f"\n📌 エージェント名: {data['name']}")
    if 'description' in data:
        lines.append(f"\n📝 説明: {data['description']}")
    if 'url' in data:
        lines.append(f"\n🔗 URL: {data['url']}")
    if 'skills' in data and len(data['skills']) > 0:
        lines.append(f"\n🛠️  スキル:")
        for skill in data['skills']:
            if 'name' in skill:
                lines.append(f"   • {skill['name']}")
            if 'description' in skill:
                lines.append(f"     {skill['description']}")
    
    lines.append("\n" + "="*60)
    return "\n".join(lines)


async def find_agent(session: ClientSession, query) -> CallToolResult:
    """Calls the 'find_agent' tool on the connected MCP server.

    Args:
        session: The active ClientSession.
        query: The natural language query to send to the 'find_agent' tool.

    Returns:
        The result of the tool call.
    """
    logger.info(f"Calling 'find_agent' tool with query: '{query[:50]}...'")
    return await session.call_tool(
        name='find_agent',
        arguments={
            'query': query,
        },
    )


async def find_resource(session: ClientSession, resource) -> ReadResourceResult:
    """Reads a resource from the connected MCP server.

    Args:
        session: The active ClientSession.
        resource: The URI of the resource to read (e.g., 'resource://agent_cards/list').

    Returns:
        The result of the resource read operation.
    """
    logger.info(f'Reading resource: {resource}')
    return await session.read_resource(resource)


async def search_flights(session: ClientSession) -> CallToolResult:
    """Calls the 'search_flights' tool on the connected MCP server.

    Args:
        session: The active ClientSession.
        query: The natural language query to send to the 'search_flights' tool.

    Returns:
        The result of the tool call.
    """
    # TODO: Implementation pending
    logger.info("Calling 'search_flights' tool'")
    return await session.call_tool(
        name='search_flights',
        arguments={
            'departure_airport': 'SFO',
            'arrival_airport': 'LHR',
            'start_date': '2025-06-03',
            'end_date': '2025-06-09',
        },
    )


async def search_hotels(session: ClientSession) -> CallToolResult:
    """Calls the 'search_hotels' tool on the connected MCP server.

    Args:
        session: The active ClientSession.
        query: The natural language query to send to the 'search_hotels' tool.

    Returns:
        The result of the tool call.
    """
    # TODO: Implementation pending
    logger.info("Calling 'search_hotels' tool'")
    return await session.call_tool(
        name='search_hotels',
        arguments={
            'location': 'A Suite room in St Pancras Square in London',
            'check_in_date': '2025-06-03',
            'check_out_date': '2025-06-09',
        },
    )


async def search_attractions(session: ClientSession, city: str, category: str = None) -> CallToolResult:
    """Calls the 'search_attractions' tool on the connected MCP server.
    
    Args:
        session: The active ClientSession.
        city: City name to search for attractions.
        category: Optional category filter.
    
    Returns:
        The result of the tool call.
    """
    logger.info(f"Calling 'search_attractions' tool with city: {city}")
    args = {'city': city}
    if category:
        args['category'] = category
    return await session.call_tool(
        name='search_attractions',
        arguments=args,
    )


async def query_db(session: ClientSession) -> CallToolResult:
    """Calls the 'query' tool on the connected MCP server.

    Args:
        session: The active ClientSession.
        query: The natural language query to send to the 'query_db' tool.

    Returns:
        The result of the tool call.
    """
    logger.info("Calling 'query_db' tool'")
    return await session.call_tool(
        name='query_travel_data',
        arguments={
            'query': "SELECT id, name, city, hotel_type, room_type, price_per_night FROM hotels WHERE city='London'",
        },
    )


# Test util
async def main(host, port, transport, query, resource, tool, city, category):
    """Main asynchronous function to connect to the MCP server and execute commands.

    Used for local testing.

    Args:
        host: Server hostname.
        port: Server port.
        transport: Connection transport ('sse' or 'stdio').
        query: Optional query string for the 'find_agent' tool.
        resource: Optional resource URI to read.
        tool: Optional tool name to execute. Valid options are:
            'search_flights', 'search_hotels', or 'query_db'.
    """
    logger.info('Starting Client to connect to MCP')
    async with init_session(host, port, transport) as session:
        if query:
            logger.info(f"\n{'='*60}")
            logger.info(f"🔍 クエリ: {query}")
            logger.info(f"{'='*60}")
            result = await find_agent(session, query)
            if result.content and len(result.content) > 0:
                response_text = result.content[0].text
                if response_text:
                    try:
                        data = json.loads(response_text)
                        # Display in Japanese format
                        formatted_result = format_agent_result(data)
                        print(formatted_result)
                        logger.info(formatted_result)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON response: {e}")
                        logger.error(f"Response text: {response_text}")
                else:
                    logger.error("Empty response text from find_agent")
            else:
                logger.error("No content in result from find_agent")
                logger.error(f"Result: {result}")
        if resource:
            result = await find_resource(session, resource)
            logger.info(result)
            if result.contents and len(result.contents) > 0:
                data = json.loads(result.contents[0].text)
                if 'agent_cards' in data:
                    print(f"\n{'='*60}")
                    print("📋 利用可能なエージェントカード一覧")
                    print(f"{'='*60}")
                    for i, card_uri in enumerate(data['agent_cards'], 1):
                        card_name = card_uri.split('/')[-1]
                        print(f"{i}. {card_name}")
                    print(f"{'='*60}\n")
                logger.info(json.dumps(data, indent=2))
        if tool:
            if tool == 'search_flights':
                results = await search_flights(session)
                logger.info(results.model_dump())
            if tool == 'search_hotels':
                result = await search_hotels(session)
                if result.content and len(result.content) > 0:
                    data = json.loads(result.content[0].text)
                    logger.info(json.dumps(data, indent=2))
            if tool == 'query_db':
                result = await query_db(session)
                logger.info(result)
                if result.content and len(result.content) > 0:
                    data = json.loads(result.content[0].text)
                    logger.info(json.dumps(data, indent=2))
            if tool == 'search_attractions':
                if not city:
                    logger.error("City parameter is required for search_attractions")
                else:
                    result = await search_attractions(session, city, category)
                    if result.content and len(result.content) > 0:
                        data = json.loads(result.content[0].text)
                        print(f"\n{'='*60}")
                        print(f"🎯 {city}の観光地検索結果")
                        print(f"{'='*60}")
                        if isinstance(data, str):
                            data = json.loads(data)
                        if 'results' in data:
                            for idx, attraction in enumerate(data['results'], 1):
                                print(f"\n{idx}. {attraction.get('name', 'N/A')}")
                                print(f"   カテゴリ: {attraction.get('category', 'N/A')}")
                                print(f"   評価: ⭐ {attraction.get('rating', 'N/A')}")
                                print(f"   説明: {attraction.get('description', 'N/A')}")
                                print(f"   入場料: ${attraction.get('entry_fee', 0)}")
                                print(f"   所要時間: {attraction.get('recommended_duration_hours', 'N/A')}時間")
                        print(f"{'='*60}\n")
                        logger.info(json.dumps(data, indent=2, ensure_ascii=False))


# Command line tester
@click.command()
@click.option('--host', default='localhost', help='SSE Host')
@click.option('--port', default='10100', help='SSE Port')
@click.option('--transport', default='stdio', help='MCP Transport')
@click.option('--find_agent', help='Query to find an agent')
@click.option('--resource', help='URI of the resource to locate')
@click.option('--tool_name', type=click.Choice(['search_flights', 'search_hotels', 'query_db', 'search_attractions']),
              help='Tool to execute: search_flights, search_hotels, query_db, or search_attractions')
@click.option('--city', help='City name for attraction search')
@click.option('--category', help='Category for attraction search (Landmark, Museum, Park, etc.)')
@click.option('--queries', help='Comma-separated list of queries to test')
def cli(host, port, transport, find_agent, resource, tool_name, queries, city, category):
    """A command-line client to interact with the Agent Cards MCP server."""
    if queries:
        # Process multiple queries
        query_list = [q.strip() for q in queries.split(',')]
        print(f"\n{'='*60}")
        print(f"🧪 複数クエリのテストを開始します (全{len(query_list)}件)")
        print(f"{'='*60}\n")
        for idx, q in enumerate(query_list, 1):
            print(f"\n{'#'*60}")
            print(f"テスト {idx}/{len(query_list)}")
            print(f"{'#'*60}\n")
            asyncio.run(main(host, port, transport, q, None, None, None, None))
            if idx < len(query_list):
                print("\n" + "-"*60 + "\n")
        print(f"\n{'='*60}")
        print("✅ すべてのテストが完了しました")
        print(f"{'='*60}\n")
    else:
        asyncio.run(main(host, port, transport, find_agent, resource, tool_name, city, category))


if __name__ == '__main__':
    cli()
