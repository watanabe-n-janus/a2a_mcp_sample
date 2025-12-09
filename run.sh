#!/bin/bash

# A script to automate the execution of the a2a_mcp example.
# It starts all necessary servers and agents in the background,
# runs the client, and then cleans up all background processes.

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
# The main working directory for the example
# If running from repository root, use: WORK_DIR="samples/python/agents/a2a_mcp"
# If running from within a2a_mcp directory, use: WORK_DIR="."
# This script auto-detects the correct directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$SCRIPT_DIR"
# Directory to store log files for background processes
LOG_DIR="logs"


# --- Cleanup Function ---
# This function is called automatically when the script exits (for any reason)
# to ensure all background processes are terminated.
cleanup() {
    echo ""
    echo "Shutting down background processes..."
    # Check if the pids array is not empty
    if [ ${#pids[@]} -ne 0 ]; then
        # Kill all processes using their PIDs stored in the array.
        # The 2>/dev/null suppresses "Terminated" messages or errors if a process is already gone.
        kill "${pids[@]}" 2>/dev/null
        wait "${pids[@]}" 2>/dev/null
    fi
    echo "Cleanup complete."
}

# Trap the EXIT signal to call the cleanup function. This ensures cleanup
# runs whether the script finishes successfully, fails, or is interrupted.
trap cleanup EXIT


# --- Main Script Logic ---

# Check if the working directory exists and contains necessary files.
if [ ! -d "$WORK_DIR" ]; then
    echo "Error: Directory '$WORK_DIR' not found."
    exit 1
fi

# Check if .env file exists
if [ ! -f "$WORK_DIR/.env" ]; then
    echo "Error: .env file not found in '$WORK_DIR'"
    echo "Please create a .env file with your GOOGLE_API_KEY"
    exit 1
fi

# Navigate into the working directory.
cd "$WORK_DIR"
echo "Changed directory to $(pwd)"

# Create a directory for log files if it doesn't exist.
mkdir -p "$LOG_DIR"

echo "Setting up Python virtual environment with 'uv'..."
# Create virtual environment, clearing if it already exists to avoid prompts
if [ -d ".venv" ]; then
    echo "Existing virtual environment found, recreating..."
    uv venv --clear
else
    uv venv
fi

# Activate the virtual environment for the script and all its child processes.
source .venv/bin/activate
echo "Virtual environment activated."

# Sync dependencies to ensure all packages are installed
echo "Installing dependencies..."
uv sync
echo "Dependencies installed."

# Initialize database with attractions data
echo "Initializing database with attractions data..."
python init_database.py
echo "Database initialization completed."

# Array to store Process IDs (PIDs) of background jobs.
pids=()

# --- Start Background Services ---
echo ""
echo "Starting servers and agents in the background..."

# 1. Start MCP Server
echo "-> Starting MCP Server (Port: 10100)... Log: $LOG_DIR/mcp_server.log"
uv run --env-file .env a2a-mcp --run mcp-server --transport sse --port 10100 >> "$LOG_DIR/mcp_server.log" 2>&1 &
mcp_pid=$!
pids+=($mcp_pid)
sleep 2
# Verify MCP server process is still running
if ! kill -0 $mcp_pid 2>/dev/null; then
    echo "ERROR: MCP Server failed to start!"
    echo "Last 20 lines of MCP server log:"
    tail -20 "$LOG_DIR/mcp_server.log" 2>/dev/null || echo "No log file"
    exit 1
fi

# 2. Start Orchestrator Agent
echo "-> Starting Orchestrator Agent (Port: 10101)... Log: $LOG_DIR/orchestrator_agent.log"
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/orchestrator_agent.json --port 10101 > "$LOG_DIR/orchestrator_agent.log" 2>&1 &
pids+=($!)

# 3. Start Planner Agent
echo "-> Starting Planner Agent (Port: 10102)... Log: $LOG_DIR/planner_agent.log"
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/planner_agent.json --port 10102 > "$LOG_DIR/planner_agent.log" 2>&1 &
pids+=($!)

# 4. Start Airline Ticketing Agent
echo "-> Starting Airline Agent (Port: 10103)... Log: $LOG_DIR/airline_agent.log"
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/air_ticketing_agent.json --port 10103 > "$LOG_DIR/airline_agent.log" 2>&1 &
pids+=($!)

# 5. Start Hotel Reservations Agent
echo "-> Starting Hotel Agent (Port: 10104)... Log: $LOG_DIR/hotel_agent.log"
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/hotel_booking_agent.json --port 10104 > "$LOG_DIR/hotel_agent.log" 2>&1 &
pids+=($!)

# 6. Start Car Rental Reservations Agent
echo "-> Starting Car Rental Agent (Port: 10105)... Log: $LOG_DIR/car_rental_agent.log"
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/car_rental_agent.json --port 10105 > "$LOG_DIR/car_rental_agent.log" 2>&1 &
pids+=($!)

# 7. Start Itinerary Generation Agent
echo "-> Starting Itinerary Agent (Port: 10106)... Log: $LOG_DIR/itinerary_agent.log"
uv run --env-file .env src/a2a_mcp/agents/ --agent-card agent_cards/itinerary_agent.json --port 10106 > "$LOG_DIR/itinerary_agent.log" 2>&1 &
pids+=($!)

echo ""
echo "All services are starting. Waiting for services to initialize..."

# Function to check if a port is open
check_port() {
    local port=$1
    local max_attempts=30
    # Increase timeout for itinerary agent (it might take longer to start)
    if [ "$port" = "10106" ]; then
        max_attempts=40
    fi
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    return 1
}

# Wait for MCP server to be ready
echo "Waiting for MCP Server (Port: 10100)..."
if check_port 10100; then
    echo "MCP Server is ready!"
else
    echo "Warning: MCP Server did not start on port 10100"
    echo "Checking logs..."
    tail -20 "$LOG_DIR/mcp_server.log" 2>/dev/null || echo "No log file found"
fi

# Additional wait to ensure all services are fully initialized
echo "Waiting additional 5 seconds for all services to be fully ready..."
sleep 5

# --- Run the Foreground Client ---
echo ""
echo "---------------------------------------------------------"
echo "Starting CLI Client..."
echo "The script will exit after the client finishes."
echo "---------------------------------------------------------"
echo ""

# 7a. Test MCP agent discovery (optional)
echo "Testing MCP agent discovery..."
uv run --env-file .env src/a2a_mcp/mcp/client.py \
    --host localhost \
    --port 10100 \
    --transport sse \
    --resource "resource://agent_cards/list" \
    --find_agent "フランスへの旅行を計画したいです" || true

echo ""
echo "---------------------------------------------------------"
echo "Starting Travel Planning Client..."
echo "This will execute the full travel planning workflow."
echo "---------------------------------------------------------"
echo ""

# 7b. Execute full travel planning workflow with Orchestrator Agent
# The script will pause here until this command completes.
#TRAVEL_QUERY="${TRAVEL_QUERY:-フランスへの旅行を計画したいです。ビジネスクラスの航空券、スイートルームのホテルを予約してください。東京の羽田からパリへのビジネストリップを予約したい。
#12月25日に出発したい。帰国日は12月30日にしたい。予算は1000万円ある。
#人数は2人。レンタカーは不要です。航空会社やホテルの予約はすべてお任せします。エッフェル塔周辺のホテルがいいなぁ。}"

TRAVEL_QUERY="${TRAVEL_QUERY:-フランスへの旅行を計画したいです。おすすめの旅行プランを考えてください。}"

echo "🚀 旅行計画クエリ: $TRAVEL_QUERY"
echo ""

uv run --env-file .env python src/a2a_mcp/orchestrator_client.py \
    --orchestrator-url "http://localhost:10101" \
    --query "$TRAVEL_QUERY" \
    --show-mcp

echo ""
echo "---------------------------------------------------------"
echo "CLI client finished."
echo "---------------------------------------------------------"

# The 'trap' will now trigger the 'cleanup' function automatically upon exiting.
