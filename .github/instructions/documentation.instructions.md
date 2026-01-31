---
applyTo: "docs/**/*.md"
---
# Documentation Instructions

## Documentation Standards
- Use clear, concise language
- Include code examples where helpful
- Keep documentation up-to-date with code changes
- Use proper Markdown formatting

## Document Structure
```markdown
# Feature Name

Brief description of the feature.

## Overview

More detailed explanation of what this feature does and why it exists.

## Usage

### Basic Example
\`\`\`python
# Code example
\`\`\`

### Advanced Example
\`\`\`python
# More complex example
\`\`\`

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| option1 | string | "default" | What it does |

## API Reference

### `function_name(param1, param2)`

Description of the function.

**Parameters:**
- `param1` (type): Description
- `param2` (type): Description

**Returns:**
- (type): Description

## Troubleshooting

### Common Issue 1
Solution...

### Common Issue 2
Solution...

## See Also
- [Related Doc](./RELATED.md)
- [External Resource](https://example.com)
```

## Key Documentation Files
- `README.md` - Project overview and quick start
- `docs/ARCHITECTURE.md` - System architecture
- `docs/PLAN_SCHEMA.md` - Migration plan structure
- `docs/MIGRATION_COVERAGE.md` - What gets migrated
- `backend/app/agents/README.md` - Agent system

## When to Update Docs
- Adding new features
- Changing API contracts
- Modifying configuration options
- Fixing known issues
- Adding new agents or components
