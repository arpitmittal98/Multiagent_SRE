#!/bin/bash
# start.sh
# Entrypoint for the Docker container

echo "Starting AI War Room Server..."
export DD_TRACE_ENABLED="false"
exec uvicorn server:app --host 0.0.0.0 --port 8000
