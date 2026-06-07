"""Learning tools — AILIEN researches topics from the web and remembers them."""
from tools import tool


@tool(
    name="learn_from_web",
    description="Research a topic from a web URL or search for it. Fetches the content, extracts readable text, saves it to the knowledge base so you can recall it later.",
    params={
        "url": {"type": "string", "description": "URL to learn from (e.g. https://docs.python.org/3/tutorial/)"},
        "topic": {"type": "string", "description": "Optional topic name. If not provided, auto-detected from the page title.", "default": ""},
        "query": {"type": "string", "description": "Alternative to url: a search query if you want to search the web for information. Provide either url or query.", "default": ""},
    },
    required=[],
)
def learn_from_web(url: str = "", topic: str = "", query: str = "") -> str:
    """Research a topic from the web and save it to the knowledge base."""
    from brain.learner import learn_from_url

    if query and not url:
        # Search the web using a simple approach
        import requests
        search_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        try:
            html = requests.get(
                search_url,
                headers={"User-Agent": "Mozilla/5.0 AILIEN-Learner/1.0"},
                timeout=10,
            ).text
        except requests.RequestException as e:
            return f"Could not search for '{query}': {e}. Try providing a direct URL instead."

        # Extract result links
        import re
        links = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"', html)
        if not links:
            # Fallback to different pattern
            links = re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>', html)

        if links:
            # Pick the most relevant link (skip ads, social media, and known link aggregators)
            skip_domains = ["duckduckgo.com", "twitter.com", "facebook.com", "reddit.com",
                           "instagram.com", "youtube.com", "amazon.com"]
            chosen = None
            for link in links:
                clean_link = link.replace("//duckduckgo.com/l/?uddg=", "")
                from urllib.parse import unquote
                clean_link = unquote(clean_link)
                if not any(d in clean_link for d in skip_domains) and clean_link.startswith("http"):
                    chosen = clean_link
                    break
            if not chosen and links:
                chosen = links[0]

            if chosen:
                url = chosen
                if not topic:
                    topic = query
                result = learn_from_url(url, topic=topic or query)
                # Add a note about the search
                return f"Searched for '{query}' and found a relevant article.\n{result}"
            else:
                return f"Found search results but couldn't extract a clean URL to learn from."
        else:
            return f"Could not find search results for '{query}'. Try providing a direct URL."

    if not url:
        return "Provide a URL to learn from, or a query to search the web."

    from brain.learner import learn_from_url
    return learn_from_url(url, topic=topic if topic else None)


@tool(
    name="learn_from_reddit",
    description="Fetch and save hot or trending posts from a Reddit subreddit to the knowledge base.",
    params={
        "subreddit": {"type": "string", "description": "Subreddit name (without r/), e.g. 'python', 'MachineLearning'", "default": "all"},
        "query": {"type": "string", "description": "Optional search query within the subreddit", "default": ""},
    },
    required=[],
)
def learn_from_reddit(subreddit: str = "all", query: str = "") -> str:
    """Research a topic from Reddit and save it to the knowledge base."""
    from brain.learner import learn_from_reddit as _learn_reddit
    return _learn_reddit(subreddit, query if query else None)


@tool(
    name="learn_from_youtube",
    description="Search YouTube for videos about a topic and save the results to the knowledge base.",
    params={
        "query": {"type": "string", "description": "Search query for YouTube videos"},
    },
    required=["query"],
)
def learn_from_youtube(query: str) -> str:
    """Research a topic from YouTube and save to the knowledge base."""
    from brain.learner import learn_from_youtube as _learn_yt
    return _learn_yt(query)


@tool(
    name="recall",
    description="Recall what you've learned about a topic. Searches the knowledge base and the learning index for relevant information.",
    params={
        "topic": {"type": "string", "description": "Topic to search for (e.g. 'Python async', 'Linux commands', 'sorting algorithms')"},
    },
    required=["topic"],
)
def recall(topic: str) -> str:
    """Recall previously learned information about a topic."""
    from brain.learner import recall as _recall
    return _recall(topic)


@tool(
    name="list_learned_topics",
    description="List all topics that have been learned from the web, grouped by category.",
    params={},
    required=[],
)
def list_learned_topics() -> str:
    """List everything that has been learned so far."""
    from brain.learner import list_learned_topics as _list
    return _list()


@tool(
    name="forget_topic",
    description="Remove a learned topic from the learning index.",
    params={
        "topic": {"type": "string", "description": "Topic name to forget"},
    },
    required=["topic"],
)
def forget_topic(topic: str) -> str:
    """Remove a learned topic from the index."""
    from brain.learner import forget_topic as _forget
    return _forget(topic)
