```json
{
  "mcpServers": {
    "kubernetes-readonly": {
      "command": "npx", 
      "args": ["mcp-server-kubernetes"], 
      "env": {
        "ALLOW_ONLY_NON_DESTRUCTIVE_TOOLS": "true"}
    }
  }
}
```