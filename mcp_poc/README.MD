# MCP Prototype

## What it does
This prototype connects a ChatGPT model to the Virge Shop backend via an MCP server generated from the backend’s OpenAPI spec.
It exposes the backend **GET** endpoints as MCP resources, and the client lets the model “browse” those resources (read endpoints) to answer questions.

## What to configure
Set these environment variables (e.g., in a `.env`):

- `CHATGPT_KEY` — your OpenAI API key (used by the client)
- `SHOP_VIRGE_BACKEND_URL` — base URL of the Virge backend (used by the MCP server)
- `SHOP_VIRGE_TOKEN` — bearer token (optional, if your backend requires auth)

Also update `OPENAPI_PATH` in `virgeJson.py` to point to your backend’s OpenAPI JSON path (commonly `/openapi.json`).

## Run
Run the client script; it will start the MCP server automatically and you can pick a canned question or type your own prompt.
