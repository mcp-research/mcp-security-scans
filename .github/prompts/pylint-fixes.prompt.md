---
mode: 'agent'
tools: ['codebase']
description: 'Address the issues found by flake8 in the codebase.'
comment: 'See the docs to setup this prompt file here: https://code.visualstudio.com/docs/copilot/copilot-customization#_prompt-files-experimental'
---
Your goal is to run the flake8 tool on the codebase and address the issues it finds.

- Execute the following command in the terminal to run flake8: `flake8`
- Address the issues found by flake8 in the codebase by looking at the #terminalLastCommand output.
