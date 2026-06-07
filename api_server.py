"""Built-in HTTP API server for AILIEN (OpenAI-compatible /chat/completions).

Uses only Python stdlib (http.server, threading, json) so no extra deps are needed.
Open WebUI can connect by adding a custom OpenAI API endpoint pointing to
http://localhost:<port>/v1

Supports both streaming (SSE) and non-streaming responses.
"""
import json
import logging
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import config
from utils.helpers import setup_crash_logging, setup_logging

logger = logging.getLogger("agent")


def _create_agent():
    """Create a fresh Agent instance for each request to avoid shared state."""
    from main import Agent
    return Agent()


def _extract_last_user_message(body: dict[str, Any]) -> str:
    """Pull the last user message from an OpenAI-style messages list."""
    messages = body.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "user" and msg.get("content"):
            return str(msg.get("content"))
    return ""


def _build_openai_response(content: str, model: str = "ailien") -> dict[str, Any]:
    """Build a minimal OpenAI-compatible chat completion response."""
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


class _AILIENHandler(BaseHTTPRequestHandler):
    """Request handler for /v1/chat/completions and health checks."""

    def log_message(self, format, *args):
        """Override to route access logs through our logger."""
        logger.debug(format % args)

    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self, content: str) -> None:
        """Stream a response as Server-Sent Events (OpenAI-compatible).

        Sends the response in small phrase-sized chunks for a smooth live
        streaming experience. Each chunk is an OpenAI-compatible delta.
        """
        model = "ailien"
        response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

        def _sse_line(data: dict) -> str:
            return f"data: {json.dumps(data)}\n\n"

        # Send the role preamble
        self.wfile.write(_sse_line({
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }).encode())

        # Group words into small phrases (3-5 words) for natural streaming pace
        words = content.split(" ")
        chunk_size = max(1, min(5, max(1, len(words) // 50)))  # Aim for ~50 chunks total
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size]) + " "
            self.wfile.write(_sse_line({
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
            }).encode())
            self.wfile.flush()
            time.sleep(0.04)  # Brief delay between phrases

        # Send the final [DONE] message
        self.wfile.write(_sse_line({
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }).encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/health", "/v1/models"):
            if self.path == "/v1/models":
                return self._send_json(200, {
                    "object": "list",
                    "data": [
                        {
                            "id": "ailien",
                            "object": "model",
                            "created": 0,
                            "owned_by": "ailien",
                        }
                    ],
                })
            return self._send_json(200, {"status": "ok", "agent": "ailien"})
        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path not in ("/v1/chat/completions", "/chat/completions"):
            return self._send_json(404, {"error": "Not found"})

        try:
            content_len = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_len).decode("utf-8")
            body = json.loads(raw_body) if raw_body else {}
        except Exception as exc:
            return self._send_json(400, {"error": f"Invalid JSON: {exc}"})

        user_text = _extract_last_user_message(body)
        if not user_text:
            return self._send_json(400, {"error": "No user message found in request"})

        is_stream = body.get("stream", False)

        logger.info("API request (%s): %s...", "stream" if is_stream else "block", user_text[:80])

        try:
            agent = _create_agent()
            response_text = agent._chat_with_tools(user_text)
        except Exception as exc:
            logger.exception("API chat failed")
            return self._send_json(500, {"error": {"message": str(exc), "type": "agent_error"}})

        if is_stream:
            self._send_sse(response_text)
        else:
            response = _build_openai_response(response_text)
            self._send_json(200, response)


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the threaded HTTP server."""
    # API mode has no interactive terminal — disable confirmations to avoid
    # deadlock waiting for console.input(). The user can review safety via Open WebUI.
    config.AGENT_CONFIRM_DANGEROUS = False
    setup_logging()
    setup_crash_logging()
    server = ThreadingHTTPServer((host, port), _AILIENHandler)
    logger.info(f"AILIEN API server running on http://{host}:{port}")
    logger.info("In Open WebUI, add a new OpenAI API connection pointing to this URL.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down API server...")
        server.shutdown()


if __name__ == "__main__":
    run_server()
