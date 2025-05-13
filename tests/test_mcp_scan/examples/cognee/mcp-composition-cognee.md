```json
{
  "mcpServers": {
    "cognee": {
      "command": "/Users/{user}/cognee/.venv/bin/uv",
      "args": [
        "--directory",
        "/Users/{user}/cognee/cognee-mcp",
        "run",
        "cognee"
      ],
      "env": {
        "ENV": "local",
        "TOKENIZERS_PARALLELISM": "false",
        "LLM_API_KEY": "sk-"
      }
    }
  }
}
```
