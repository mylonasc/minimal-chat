# Minimal FastAPI + Langchain Agent UI

This creates a minimal FastAPI server that is compatible with the [Langchain Agent UI](https://docs.langchain.com/oss/python/langchain/ui). 

To start an agent chat UI server, run 

```
# Create a new Agent Chat UI project
npx create-agent-chat-app --project-name my-chat-ui
cd my-chat-ui

# Install dependencies and start
pnpm install
pnpm dev
```

## Creating a minimal agent

You can create a minimal langgraph agent by using the langgraph cli:

```bash
TEMPLATE_NAME='react-agent'
AGENT_NAME='my-react-agent'
langgraph new ${AGENT_NAME} --template ${TEMPLATE_NAME}
```

or simply (to interactively select template etc):

```bash
langgraph new
```





