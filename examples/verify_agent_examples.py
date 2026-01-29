#!/usr/bin/env python3
"""
Example script demonstrating Verify Agent usage.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.agents.verify_agent import VerifyAgent


async def example_basic_verification():
    """Example 1: Basic verification"""
    print("=" * 60)
    print("Example 1: Basic Verification")
    print("=" * 60)
    print("\nMinimal expected state - checking repository exists")
    print("Expected outputs: verify_report.json, verify_summary.md, etc.")


async def main():
    """Run all examples"""
    print("\nVerify Agent - Usage Examples")
    print("=" * 60)
    
    await example_basic_verification()
    
    print("\nFor more details, see docs/VERIFY_AGENT_USAGE.md")


if __name__ == "__main__":
    asyncio.run(main())
