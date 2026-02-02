# AGENTS.md

Guidelines for agentic coding assistants working in this repository.

## Build/Lint/Test Commands

### Setup and Installation

```bash
# Install dependencies (traditional)
pip3 install -r requirements.txt

# Or using uv (recommended, 10-100x faster)
uv sync
```

### Testing

```bash
# Full strict mode test (TCP connection validation)
./test.sh

# High performance mode (multi-threaded, concurrent)
./test_fast.sh

# Using uv package manager
./test_uv.sh

# Test a single subscription link
python3 test_single.py <url>

# Run node validation only
python3 scripts/validator.py validate

# Run fast validator (high concurrency)
python3 scripts/validator_fast.py

# Subscription management
python3 scripts/subscription_manager.py init      # Initialize subscriptions
python3 scripts/subscription_manager.py select    # Select subscriptions to use
python3 scripts/subscription_manager.py fetch     # Fetch subscription content
python3 scripts/subscription_manager.py update-scores  # Update subscription scores
python3 scripts/subscription_manager.py report    # Generate report
python3 scripts/subscription_manager.py generate-meta [max_nodes] [balance]  # Generate Clash.meta configs

# Generate Clash.meta config directly
python3 scripts/clashmeta_generator.py [max_nodes] [balance]
```

### Environment Variables

```bash
PROXY_SUB_TIMEOUT=45      # Subscription fetch timeout (seconds)
PROXY_TCP_TIMEOUT=8       # TCP connection test timeout (seconds)
PROXY_DNS_TIMEOUT=5       # DNS resolution timeout (seconds)
PROXY_HTTP_TIMEOUT=30     # HTTP request timeout (seconds)
PROXY_BATCH_SIZE=20       # Concurrent node tests per batch
PROXY_BATCH_DELAY=0.5     # Delay between batches (seconds)
PROXY_MAX_LATENCY=2000    # Maximum allowed latency (ms)
PROXY_VALIDATION_MODE=strict  # Validation mode: strict|lenient
```

## Code Style Guidelines

### Import Organization

1. Standard library imports (json, os, sys, asyncio, etc.)
2. Third-party imports (aiohttp, yaml, etc.)
3. Local imports (from config import Config)

```python
import json
import os
import sys
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp
import yaml

from config import Config
```

### Formatting

- Use **2-space indentation** (not 4 spaces!)
- Maximum line length: ~120 characters
- Use shebang `#!/usr/bin/env python3` for executable scripts
- Docstrings use triple quotes on separate lines

### Type Hints

```python
from typing import Dict, List, Optional, Tuple

def validate_node(self, node: Dict) -> Tuple[bool, float, str]:
    """Validate a single proxy node"""
    pass

class MyClass:
    def __init__(self, verbose: bool = True):
        self.verbose: bool = verbose
        self.items: List[str] = []
```

### Naming Conventions

- **Classes**: PascalCase (`NodeValidator`, `SubscriptionManager`)
- **Functions/Methods**: snake_case (`validate_node`, `calculate_score`)
- **Variables**: snake_case (`valid_nodes`, `batch_size`)
- **Constants**: UPPER_SNAKE_CASE (`SUBSCRIPTION_TIMEOUT`, `TCP_CONNECT_TIMEOUT`)
- **Private methods**: single underscore prefix (`_convert_ss`)

### String Formatting

Use f-strings exclusively:

```python
print(f"Validating node: {node_name}")
log(f"Progress: {progress:.1f}%")
```

### Error Handling

Use specific exception types, always close resources:

```python
try:
    await asyncio.wait_for(asyncio.open_connection(host, port), timeout=self.timeout)
except asyncio.TimeoutError:
    return False, float("inf"), "TCP连接超时"
except ConnectionRefusedError:
    return False, float("inf"), "连接被拒绝"
except Exception as e:
    return False, float("inf"), f"错误: {str(e)[:30]}"
```

### File I/O

Use `encoding="utf-8"` and context managers:

```python
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)

with open(file_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
```

### Async/Await

Use `asyncio.gather()` for parallel operations:

```python
async def validate_nodes(self, nodes: List[Dict]):
    tasks = [self.validate_node(node) for node in nodes]
    results = await asyncio.gather(*tasks)
    return results
```

### Path Handling

Use `pathlib.Path`:

```python
from pathlib import Path

output_dir = Path("output")
nodes_file = self.output_dir / "valid_nodes.json"
```

### Base64 Handling

Handle padding safely:

```python
decoded = base64.b64decode(content + "=" * (4 - len(content) % 4))
```

## Project-Specific Notes

- Proxy subscription manager for Clash/Shadowrocket
- Supports SS, SSR, VMess, VLESS, Trojan protocols
- Strict TCP connection testing (not just DNS)
- Node deduplication based on server:port:type
- Subscription scoring system (0-100) for quality ranking
- Output files: `output/` directory
- Data files: `data/` directory
- Subscription URLs managed in `subscriptions.txt`
