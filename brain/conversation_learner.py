"""Conversation Learner — automatically saves useful tech/coding/AI information from chats.

This module analyzes conversation turns and auto-saves relevant technical content
to the knowledge base so AILIEN gets smarter over time without explicit commands.
"""

import logging
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger("agent")

# ── Topic Detection ──────────────────────────────────────────────────────────
# Hierarchical: category → keywords to match

_TECH_TOPICS: dict[str, list[str]] = {
    "programming_languages": [
        "python", "javascript", "typescript", "rust", "golang", "go ",
        "java", "c++", "c#", "ruby", "php", "swift", "kotlin", "scala",
        "perl", "lua", "elixir", "haskell", "clojure",
    ],
    "web": [
        "html", "css", "react", "vue", "angular", "svelte", "next.js",
        "node.js", "django", "flask", "fastapi", "express", "api", "rest",
        "graphql", "tailwind", "bootstrap", "jquery", "webpack", "vite",
    ],
    "ai_ml": [
        "machine learning", "deep learning", "neural network", "ai",
        "llm", "gpt", "transformer", "tensorflow", "pytorch",
        "hugging face", "fine-tuning", "rag", "vector database",
        "embedding", "tokenizer", "attention", "backpropagation",
        "cnn", "rnn", "lstm", "reinforcement learning",
    ],
    "databases": [
        "sql", "postgresql", "postgres", "mysql", "mongodb", "redis",
        "sqlite", "database", "query", "orm", "index", "migration",
        "schema", "acid", "nosql",
    ],
    "linux_devops": [
        "linux", "bash", "shell", "command", "terminal", "docker",
        "kubernetes", "k8s", "nginx", "ssh", "git", "github", "ci/cd",
        "jenkins", "ansible", "terraform", "aws", "gcp", "azure",
        "deployment", "container", "microservice",
    ],
    "security": [
        "encryption", "authentication", "oauth", "jwt", "xss",
        "sql injection", "cors", "https", "firewall", "csrf",
        "cryptography", "hash", "salt", "certificate",
    ],
    "programming_concepts": [
        "algorithm", "data structure", "recursion", "sorting",
        "binary search", "hash map", "big o", "complexity",
        "object-oriented", "functional programming", "async",
        "concurrency", "threading", "decorator", "generator",
        "design pattern", "singleton", "factory",
    ],
}

# Flatten for quick topic detection
_ALL_KEYWORDS: list[str] = []
for kw_list in _TECH_TOPICS.values():
    _ALL_KEYWORDS.extend(kw_list)

# Query patterns that suggest the user wants to learn something
_RESEARCH_PATTERNS: list[str] = [
    "what is", "what are", "how does", "how do", "how to", "how can",
    "explain", "tell me about", "learn about", "research",
    "find out about", "look up", "search for", "teach me",
    "difference between", "compare", "what's the best",
    "show me how", "give me an example", "walk me through",
    "i want to understand", "can you explain", "define",
]


# ── Detection Functions ──────────────────────────────────────────────────────

def _is_research_query(text: str) -> bool:
    """Check if a user message is asking for research/learning."""
    lower = text.lower().strip()
    for pattern in _RESEARCH_PATTERNS:
        if lower.startswith(pattern):
            return True
    return False


def _find_tech_topics(text: str) -> list[str]:
    """Find all tech/coding/AI keywords mentioned in the text.

    Returns matched keywords in order of appearance.
    """
    lower = text.lower()
    found: list[str] = []
    seen: set[str] = set()
    for kw in _ALL_KEYWORDS:
        if kw in lower and kw not in seen:
            found.append(kw.strip())
            seen.add(kw)
    return found


def _is_tech_related(text: str) -> bool:
    """Check if text contains any tech/coding/AI related content."""
    return len(_find_tech_topics(text)) > 0


def _categorize_topic(topics: list[str]) -> str:
    """Determine the best category for a set of detected topics."""
    lower_topics = [t.lower() for t in topics]
    for category, keywords in _TECH_TOPICS.items():
        for kw in keywords:
            if any(kw in t for t in lower_topics):
                return category
    return "notes"


def _extract_key_content(response: str, max_chars: int = 2000) -> str:
    """Extract the key informational content from an LLM response.

    Filters out conversational fluff and keeps the meaty parts.
    Preserves short technical lines like commands and code snippets.
    """
    # Single-word conversational tokens to filter
    _FLUFF_WORDS = {"yes", "no", "ok", "okay", "sure", "thanks", "done", "hello", "hi", "bye", "got it", "great", "perfect"}
    _FLUFF_PREFIXES = ("sure ", "okay ", "got it", "here ", "let me", "i'll ", "i can ", "no problem")

    lines = response.split("\n")
    kept: list[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        lower = s.lower()
        # Skip purely conversational single words
        if len(s) < 20 and lower in _FLUFF_WORDS:
            continue
        if len(s) < 20 and any(lower.startswith(p) for p in _FLUFF_PREFIXES):
            continue
        # Remove markdown separators
        if s in ("---", "___", "***"):
            continue
        kept.append(s)

    text = "\n".join(kept)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n..."
    return text


# ── Rate Limiting ────────────────────────────────────────────────────────────

_last_save: dict[str, float] = {}
# Different cooldowns for different trigger types
_COOLDOWN_RESEARCH = 300      # 5 min — research queries
_COOLDOWN_TOOL_RESULT = 120   # 2 min — tool results
_COOLDOWN_GENERAL = 600       # 10 min — general tech chat


def _can_save(topic_key: str, cooldown: int = 300) -> bool:
    """Rate-limit saves per topic to avoid flooding the knowledge base."""
    now = time.time()
    if topic_key in _last_save:
        elapsed = now - _last_save[topic_key]
        if elapsed < cooldown:
            return False
    _last_save[topic_key] = now
    return True


# ── Learning from Response ───────────────────────────────────────────────────

def auto_learn_from_response(
    user_text: str,
    response_text: str,
    tool_results: list[str] | None = None,
) -> str | None:
    """Auto-save useful information from a conversation turn.

    Checks if the conversation is tech-related, extracts key content,
    and saves to the knowledge base. Returns a status message or None.

    Args:
        user_text: What the user said
        response_text: What the LLM responded
        tool_results: Optional list of tool output strings (for extra content)

    Returns:
        A short status message like "Auto-saved: Python Async" or None.
    """
    # Build combined text for analysis
    all_text = user_text + " " + response_text
    if tool_results:
        all_text += " " + " ".join(tool_results)

    # Skip if not tech-related
    topics_in_user = _find_tech_topics(user_text)
    topics_in_response = _find_tech_topics(response_text)
    all_topics = list(dict.fromkeys(topics_in_user + topics_in_response))  # deduped ordered

    is_research = _is_research_query(user_text)
    is_tech = len(all_topics) > 0

    if not is_tech and not is_research:
        return None

    # Need at least some substantial content to save
    content = _extract_key_content(response_text, max_chars=2000)
    if len(content) < 150:
        # Check if tool results have more substance
        if tool_results:
            combined = "\n".join(tool_results)
            content = _extract_key_content(combined, max_chars=3000)
        if len(content) < 150:
            return None

    # Determine primary topic for the title
    if all_topics:
        primary_topic = all_topics[0].title()
    else:
        # Use the first few words of the user's query
        primary_topic = user_text.strip()[:40].rstrip("?.!")

    topic_key = primary_topic.lower()

    # Rate limit based on trigger type
    cooldown = _COOLDOWN_RESEARCH if is_research else _COOLDOWN_GENERAL
    if not _can_save(topic_key, cooldown):
        return None

    # Auto-categorize
    category = _categorize_topic(all_topics) if all_topics else "notes"

    # Build the save content
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    timestamp = f"_Auto-saved from conversation on {now_str}_\n\n"
    user_context = f"> **Query**: {user_text.strip()}\n\n" if user_text else ""
    save_content = timestamp + user_context + content

    # Create a descriptive title
    title_parts = [primary_topic]
    if is_research:
        title_parts.append("(Research)")
    title = "Chat: " + " ".join(title_parts) + f" — {datetime.now().strftime('%b %d %H:%M')}"

    try:
        from brain.knowledge import save
        result = save(title, save_content, category=category)
        logger.info("Auto-learned from conversation: %s → %s", title, result)
        return result
    except Exception as exc:
        logger.debug("Auto-learn failed: %s", exc)
        return None


# ── Learning from Tool Results ───────────────────────────────────────────────

# Tool names whose results are worth auto-learning
_LEARNABLE_TOOLS: set[str] = {
    "learn_from_web", "learn_from_reddit", "learn_from_youtube",
    "find_recipes", "track_package",
    "pdf_extract_text", "weather", "translate",
    "git_status", "git_log",
}


def auto_learn_from_tool(tool_name: str, tool_args: dict[str, Any], tool_result: str) -> str | None:
    """Auto-save useful information from certain tool calls.

    Called after a tool returns. If the tool fetches or generates useful info,
    saves it to the knowledge base automatically.

    Returns a status message or None.
    """
    if tool_name not in _LEARNABLE_TOOLS:
        return None

    # Skip if result is an error or too short
    if not tool_result or len(tool_result) < 100:
        return None
    if tool_result.startswith("Error") or tool_result.startswith("Could not") or tool_result.startswith("No"):
        return None

    # Build context from tool args
    context_parts = []
    for key in ("query", "topic", "url", "subreddit", "file"):
        if key in tool_args and tool_args[key]:
            context_parts.append(f"{key}={tool_args[key]}")
    context_str = ", ".join(context_parts) if context_parts else tool_name

    # Extract meaningful content
    content = tool_result[:2500]

    # Rate limit
    topic_key = f"tool_{tool_name}_{context_str[:30].lower()}"
    if not _can_save(topic_key, _COOLDOWN_TOOL_RESULT):
        return None

    # Determine category and title
    category = "topics"
    title = f"Web: {context_str[:50]} — {datetime.now().strftime('%b %d %H:%M')}"

    # Add source annotation
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    annotated = f"_Auto-saved from tool `{tool_name}({context_str})` on {now_str}_\n\n{content}"

    try:
        from brain.knowledge import save
        result = save(title, annotated, category=category)
        logger.info("Auto-learned from tool %s: %s", tool_name, result)
        return result
    except Exception as exc:
        logger.debug("Auto-learn from tool failed: %s", exc)
        return None
