import os
import shutil
import requests
from fastmcp import FastMCP

PIHOLE_HOST = os.environ.get("PIHOLE_HOST", "192.168.1.103")
PIHOLE_API_KEY = os.environ.get("PIHOLE_API_KEY", "")
OWM_API_KEY = os.environ.get("OWM_API_KEY", "")

mcp = FastMCP("peambot-tools")


@mcp.tool()
def pihole_get_stats() -> str:
    """Get Pi-hole ad-blocking statistics: status, queries today, blocked count, percent blocked."""
    url = f"http://{PIHOLE_HOST}/admin/api.php"
    try:
        r = requests.get(url, params={"summaryRaw": "", "auth": PIHOLE_API_KEY}, timeout=5)
        r.raise_for_status()
        d = r.json()
        return (
            f"Pi-hole status: {d.get('status', 'unknown')}\n"
            f"Queries today: {d.get('dns_queries_today', '?')}\n"
            f"Blocked today: {d.get('ads_blocked_today', '?')}\n"
            f"Percent blocked: {float(d.get('ads_percentage_today', 0)):.1f}%"
        )
    except Exception as e:
        return f"Pi-hole unreachable: {e}"


@mcp.tool()
def pihole_pause(seconds: int = 0) -> str:
    """
    Pause Pi-hole ad blocking.

    Args:
        seconds: How long to pause in seconds. 0 means pause indefinitely.
    """
    url = f"http://{PIHOLE_HOST}/admin/api.php"
    # Pi-hole v5 API: bare 'disable' key = indefinite, 'disable=N' = N seconds
    query = f"disable={seconds}&auth={PIHOLE_API_KEY}" if seconds > 0 else f"disable&auth={PIHOLE_API_KEY}"
    try:
        r = requests.get(f"{url}?{query}", timeout=5)
        r.raise_for_status()
        status = r.json().get("status", "unknown")
        duration = f"for {seconds} seconds" if seconds > 0 else "indefinitely"
        return f"Pi-hole paused {duration}. Current status: {status}"
    except Exception as e:
        return f"Failed to pause Pi-hole: {e}"


@mcp.tool()
def pihole_resume() -> str:
    """Resume Pi-hole ad blocking after a pause."""
    url = f"http://{PIHOLE_HOST}/admin/api.php"
    try:
        r = requests.get(f"{url}?enable&auth={PIHOLE_API_KEY}", timeout=5)
        r.raise_for_status()
        status = r.json().get("status", "unknown")
        return f"Pi-hole resumed. Current status: {status}"
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

    # Disk usage of root filesystem
    try:
        u = shutil.disk_usage("/")
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


if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8001)
