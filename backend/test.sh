#!/bin/bash

# Quick development helper script
# Run backend tests

cd /home/runner/work/gl2gh/gl2gh/backend

echo "Running backend tests..."
pytest -v

echo ""
echo "Run specific tests with:"
echo "  pytest tests/test_models.py -v"
echo "  pytest tests/test_api.py -v"
