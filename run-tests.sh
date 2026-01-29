#!/bin/bash

# Run foundation tests inside Docker container

echo "Running platform foundation tests inside Docker container..."
echo ""

if ! docker ps | grep -q "gl2gh-backend"; then
    echo "Error: Backend container not running"
    echo "Start services first with: ./start.sh"
    exit 1
fi

# Copy test file to container and run it
docker cp test_foundation.py gl2gh-backend:/tmp/test_foundation.py
docker exec gl2gh-backend python /tmp/test_foundation.py

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "✓ All foundation tests passed in Docker environment"
else
    echo ""
    echo "✗ Some tests failed - check logs above"
fi

exit $exit_code
