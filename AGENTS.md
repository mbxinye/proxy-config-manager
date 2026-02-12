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
# Run all tests
python3 -m unittest discover -s tests -v

# Run a single test file
python3 -m unittest tests.test_validator_naming -v

# Run a single test class
python3 -m unittest tests.test_validator_naming.TestValidatorNaming -v

# Run a single test method
python3 -m unittest tests.test_validator_naming.TestValidatorNaming.test_rename_final_nodes -v

# Alternative: run test file directly
python3 tests/test_validator_naming.py
```

### Application Entry Points

```bash
# Unified entry point - use run.py for all operations
python3 run.py                          # 本地模式 (local)
python3 run.py ci                       # CI/自动化模式
python3 run.py init                     # 仅初始化订阅数据库
python3 run.py fetch                    # 仅获取订阅
python3 run.py validate                 # 仅验证节点

# Subscription management
python3 scripts/subscription_manager.py init      # Initialize subscriptions
python3 scripts/subscription_manager.py select    # Select subscriptions
python3 scripts/subscription_manager.py update-scores  # Update scores
python3 scripts/subscription_manager.py report    # Generate report

# Generate Clash config
python3 scripts/clash_generator.py generate

# Rename nodes by geographic location
python3 scripts/node_renamer.py [input_file] [output_file]
```

### Environment Variables

```bash
PROXY_SUB_TIMEOUT=30      # Subscription fetch timeout (seconds)
PROXY_TCP_TIMEOUT=3        # TCP connection test timeout (seconds)
PROXY_BATCH_SIZE=200       # Concurrent node tests (TCP)
PROXY_BATCH_DELAY=0.01     # Delay between batches
PROXY_MAX_LATENCY=5000     # Maximum allowed latency (ms)
PROXY_MAX_OUTPUT_NODES=100 # Maximum output nodes
PROXY_CLASH_TEST_LIMIT=100 # Clash test node limit
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
- Node renaming: Nodes are automatically renamed by geographic location (flag + country/city)
- IP geolocation cached in `data/ip_cache.json` for performance
- The generator always writes output/clash_config.yml and output/clash_mini.yml
- If there are no valid nodes, placeholder configs are generated so CI copy steps won't fail
- Shadowrocket URI lists are written to output/shadowrocket_nodes_full.txt and output/shadowrocket_nodes_mini.txt
