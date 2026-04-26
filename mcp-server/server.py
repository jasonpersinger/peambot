import os
import shutil
from urllib.parse import urlparse
import requests
from fastmcp import FastMCP

PIHOLE_HOST = os.environ.get("PIHOLE_HOST", "192.168.1.103")
PIHOLE_PORT = os.environ.get("PIHOLE_PORT", "8080")
PIHOLE_PASSWORD = os.environ.get("PIHOLE_PASSWORD", "")
OWM_API_KEY = os.environ.get("OWM_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_SEARCH_MODEL = os.environ.get("GEMINI_SEARCH_MODEL", "gemini-2.5-flash")

mcp = FastMCP("peambot-tools")


def _gemini_grounded_answer(prompt: str, max_words: int = 90) -> str:
    """Ask Gemini with Google Search grounding for current-world questions."""
    if not GEMINI_API_KEY:
        return "Gemini API key not configured."

    voice_prompt = (
        "You are Peambot, a concise voice assistant. Use Google Search grounding for "
        "fresh facts. Answer in English. Keep the answer under "
        f"{max_words} words. Prefer reputable sources such as AP, Reuters, official "
        "league/team pages, company investor relations, SEC filings, and major market "
        "data providers. Mention source names briefly when useful. If facts are "
        "uncertain or market data may have moved, say so. Do not give financial advice. "
        "Do not invent breaking events. For major news claims, require multiple credible "
        "sources or say you cannot verify a clear top story.\n\n"
        f"User request: {prompt}"
    )

    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_SEARCH_MODEL}:generateContent",
            headers={
                "x-goog-api-key": GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "contents": [{"parts": [{"text": voice_prompt}]}],
                "tools": [{"google_search": {}}],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 260,
                },
            },
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        parts = data["candidates"][0]["content"].get("parts", [])
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            return "I could not find a grounded answer."

        sources = _grounding_source_names(data)
        if sources and "source" not in text.lower():
            text = f"{text} Sources: {', '.join(sources[:3])}."
        return text
    except Exception as e:
        return f"Live lookup failed: {e}"


def _grounding_source_names(data: dict) -> list[str]:
    candidates = data.get("candidates") or []
    if not candidates:
        return []

    metadata = candidates[0].get("groundingMetadata") or {}
    chunks = metadata.get("groundingChunks") or []
    names = []
    for chunk in chunks:
        web = chunk.get("web") or {}
        title = (web.get("title") or "").strip()
        uri = web.get("uri") or ""
        host = urlparse(uri).netloc.removeprefix("www.")
        name = title or host
        if name and name not in names:
            names.append(name)
    return names


def _pihole_base() -> str:
    return f"http://{PIHOLE_HOST}:{PIHOLE_PORT}"


def _pihole_auth() -> str | None:
    """Authenticate with Pi-hole v6 API. Returns session ID or None on failure."""
    if not PIHOLE_PASSWORD:
        return None
    try:
        r = requests.post(
            f"{_pihole_base()}/api/auth",
            json={"password": PIHOLE_PASSWORD},
            timeout=5,
        )
        r.raise_for_status()
        return r.json()["session"]["sid"]
    except Exception:
        return None


@mcp.tool()
def pihole_get_stats() -> str:
    """Get Pi-hole ad-blocking statistics: status, queries today, blocked count, percent blocked."""
    sid = _pihole_auth()
    if sid is None:
        return "Pi-hole unavailable: could not authenticate (check PIHOLE_PASSWORD)."
    try:
        r = requests.get(
            f"{_pihole_base()}/api/stats/summary",
            params={"sid": sid},
            timeout=5,
        )
        r.raise_for_status()
        d = r.json()
        queries = d.get("queries", {})
        gravity = d.get("gravity", {})
        blocking = d.get("blocking", "unknown")
        total = queries.get("total", "?")
        blocked = queries.get("blocked", "?")
        pct = float(queries.get("percent_blocked", 0))
        domains_blocked = gravity.get("domains_being_blocked", "?")
        return (
            f"Pi-hole status: {blocking}\n"
            f"Queries today: {total}\n"
            f"Blocked today: {blocked} ({pct:.1f}%)\n"
            f"Domains on blocklist: {domains_blocked}"
        )
    except Exception as e:
        return f"Pi-hole stats failed: {e}"


@mcp.tool()
def pihole_pause(seconds: int = 0) -> str:
    """
    Pause Pi-hole ad blocking.

    Args:
        seconds: How long to pause in seconds. 0 means pause indefinitely.
    """
    sid = _pihole_auth()
    if sid is None:
        return "Pi-hole unavailable: could not authenticate (check PIHOLE_PASSWORD)."
    payload = {"blocking": False}
    if seconds > 0:
        payload["timer"] = seconds
    try:
        r = requests.post(
            f"{_pihole_base()}/api/dns/blocking",
            params={"sid": sid},
            json=payload,
            timeout=5,
        )
        r.raise_for_status()
        duration = f"for {seconds} seconds" if seconds > 0 else "indefinitely"
        return f"Pi-hole paused {duration}."
    except Exception as e:
        return f"Failed to pause Pi-hole: {e}"


@mcp.tool()
def pihole_resume() -> str:
    """Resume Pi-hole ad blocking after a pause."""
    sid = _pihole_auth()
    if sid is None:
        return "Pi-hole unavailable: could not authenticate (check PIHOLE_PASSWORD)."
    try:
        r = requests.post(
            f"{_pihole_base()}/api/dns/blocking",
            params={"sid": sid},
            json={"blocking": True},
            timeout=5,
        )
        r.raise_for_status()
        return "Pi-hole resumed."
    except Exception as e:
        return f"Failed to resume Pi-hole: {e}"


@mcp.tool()
def system_get_stats() -> str:
    """Get voidberry system stats: CPU temperature, uptime, and disk usage."""
    # CPU temperature — kernel exports millidegrees Celsius
    try:
        raw = open("/host/sys/class/thermal/thermal_zone0/temp").read().strip()
        temp_str = f"{int(raw) / 1000:.1f}°C"
    except Exception:
        temp_str = "unavailable"

    # Uptime — /proc/uptime first field is seconds since boot
    try:
        secs = float(open("/host/proc/uptime").read().split()[0])
        d, rem = divmod(int(secs), 86400)
        h, m = divmod(rem // 60, 60)
        uptime_str = f"{d}d {h}h {m}m"
    except Exception:
        uptime_str = "unavailable"

    # Disk usage of the host root filesystem, mounted read-only by docker-compose.
    try:
        u = shutil.disk_usage("/host/root")
        disk_str = f"{u.used / 1e9:.1f} GB / {u.total / 1e9:.1f} GB ({u.used / u.total * 100:.0f}%)"
    except Exception:
        disk_str = "unavailable"

    return f"CPU temperature: {temp_str}\nUptime: {uptime_str}\nDisk: {disk_str}"


@mcp.tool()
def get_weather(city: str) -> str:
    """
    Get current weather conditions for a city using OpenWeatherMap.

    Args:
        city: City name, e.g. 'London' or 'New York'.
    """
    if not OWM_API_KEY:
        return "OpenWeatherMap API key not configured."
    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": OWM_API_KEY, "units": "metric"},
            timeout=10,
        )
        if r.status_code == 404:
            return f"City '{city}' not found."
        r.raise_for_status()
        d = r.json()
        return (
            f"Weather in {d['name']}: {d['weather'][0]['description'].capitalize()}\n"
            f"Temperature: {d['main']['temp']:.1f}°C "
            f"(feels like {d['main']['feels_like']:.1f}°C)\n"
            f"Humidity: {d['main']['humidity']}%\n"
            f"Wind: {d['wind']['speed']} m/s"
        )
    except Exception as e:
        return f"Weather lookup failed: {e}"


@mcp.tool()
def analyze_news(topic: str = "top news in the United States right now") -> str:
    """
    Analyze current news using live Google Search grounding.

    Args:
        topic: News topic or scope, e.g. 'biggest US news story right now',
            'AI regulation', or 'Philadelphia local news'.
    """
    return _gemini_grounded_answer(
        "Analyze the current news for this topic. Identify the biggest story or "
        "most important development, explain why it matters, and name the source "
        f"types or outlets you used. Topic: {topic}",
        max_words=95,
    )


@mcp.tool()
def financial_update(query: str) -> str:
    """
    Get a current financial or market update using live Google Search grounding.

    Args:
        query: Ticker, asset, market, company, or financial question, e.g.
            'NVDA stock today', 'Bitcoin price', or 'market open summary'.
    """
    return _gemini_grounded_answer(
        "Give a current financial update for this request. Include the latest "
        "price or direction if available, the main driver, and one caveat. Do not "
        f"recommend buying or selling. Request: {query}",
        max_words=90,
    )


@mcp.tool()
def sports_lineup_analysis(query: str) -> str:
    """
    Analyze current sports lineups, injuries, rosters, or matchups using live Google Search grounding.

    Args:
        query: Team, player, league, game, or lineup question, e.g.
            'Eagles projected starters', 'Sixers injury report', or
            'Phillies lineup tonight'.
    """
    return _gemini_grounded_answer(
        "Analyze the current sports lineup or matchup for this request. Use the "
        "latest available injury, roster, depth chart, or official lineup reports. "
        "Call out if lineups are projected rather than confirmed. Request: "
        f"{query}",
        max_words=95,
    )


if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8001)
