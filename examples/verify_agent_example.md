# Verify Agent Example Usage

## Quick Start

```python
from app.agents.verify_agent import VerifyAgent

# Initialize the agent
agent = VerifyAgent()

# Prepare inputs
inputs = {
    "github_token": "ghp_your_github_token",
    "github_repo": "owner/repo",
    "expected_state": {
        "repository": {
            "branch_count": 5,
            "tag_count": 10
        },
        "ci_cd": {
            "workflow_count": 3
        },
        "issues": {
            "issue_count": 50
        }
    },
    "output_dir": "/path/to/output"
}

# Execute verification
result = await agent.execute(inputs)

# Check results
if result["status"] == "success":
    print("✅ Verification passed!")
else:
    print(f"⚠️ Status: {result['status']}")
    print(f"Errors: {result['outputs']['total_errors']}")
    print(f"Warnings: {result['outputs']['total_warnings']}")
```

## Output Files

After execution, the following files are created in `output_dir/verify/`:

1. **verify_report.json** - Complete verification results
2. **verify_summary.md** - Human-readable summary  
3. **component_status.json** - Status per component
4. **discrepancies.json** - List of all discrepancies

## Running Tests

```bash
# Unit tests
cd backend
python -m pytest tests/test_verify_agent.py -v

# Integration tests
python -m pytest tests/test_verify_agent_integration.py -v

# All verify agent tests
python -m pytest tests/test_verify_agent*.py -v
```

## See Also

- `docs/VERIFY_AGENT_USAGE.md` - Complete usage guide
- `backend/tests/test_verify_agent.py` - Unit test examples
- `backend/tests/test_verify_agent_integration.py` - Integration test examples
