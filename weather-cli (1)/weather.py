#!/usr/bin/env python3
"""Weather CLI - current conditions, 24-hour trend and 7-day forecast.

Data: Open-Meteo.com (free, no API key).
"""
import argparse
import sys
from datetime import datetime

try:  # make box/block characters work on Windows consoles
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import requests
from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

console = Console()

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherError(Exception):
    pass


# ---------------------------------------------------------------- look-up tables
CODES = {
    0: ("clear", "Clear sky"), 1: ("clear", "Mainly clear"), 2: ("partly", "Partly cloudy"),
    3: ("cloud", "Overcast"), 45: ("fog", "Fog"), 48: ("fog", "Rime fog"),
    51: ("rain", "Light drizzle"), 53: ("rain", "Drizzle"), 55: ("rain", "Heavy drizzle"),
    56: ("rain", "Freezing drizzle"), 57: ("rain", "Freezing drizzle"),
    61: ("rain", "Light rain"), 63: ("rain", "Rain"), 65: ("rain", "Heavy rain"),
    66: ("rain", "Freezing rain"), 67: ("rain", "Freezing rain"),
    71: ("snow", "Light snow"), 73: ("snow", "Snow"), 75: ("snow", "Heavy snow"),
    77: ("snow", "Snow grains"), 80: ("rain", "Rain showers"), 81: ("rain", "Rain showers"),
    82: ("rain", "Violent showers"), 85: ("snow", "Snow showers"), 86: ("snow", "Snow showers"),
    95: ("storm", "Thunderstorm"), 96: ("storm", "Thunderstorm, hail"), 99: ("storm", "Thunderstorm, hail"),
}

KIND_COLOR = {
    "clear": "bright_yellow", "night": "bright_cyan", "partly": "yellow", "cloud": "grey70",
    "fog": "grey62", "rain": "dodger_blue1", "snow": "bright_white", "storm": "magenta",
}

ICONS = {
    "clear": [r"    \   /    ", r"     .-.     ", r"  -- (   ) -- ", r"     `-'     ", r"    /   \    "],
    "night": [r"    .--.     ", r"  .'  _ )    ", r" (   (_,'    ", r"  `.   `.    ", r"    `--'     "],
    "partly": [r"   \  /      ", r" _ /''.-.    ", r"   \_(   ).  ", r"   /(___(__) ", r"             "],
    "cloud": [r"             ", r"     .--.    ", r"  .-(    ).  ", r" (___.__)__) ", r"             "],
    "fog": [r"             ", r" _ - _ - _ - ", r"  _ - _ - _  ", r" _ - _ - _ - ", r"             "],
    "rain": [r"     .-.     ", r"    (   ).   ", r"   (___(__)  ", r"    ' ' ' '  ", r"   ' ' ' '   "],
    "snow": [r"     .-.     ", r"    (   ).   ", r"   (___(__)  ", r"    *  *  *  ", r"   *  *  *   "],
    "storm": [r"     .-.     ", r"    (   ).   ", r"   (___(__)  ", r"    /_ /_    ", r"     / /     "],
}

DIGITS = {
    "0": (" _ ", "| |", "|_|"), "1": ("   ", "  |", "  |"), "2": (" _ ", " _|", "|_ "),
    "3": (" _ ", " _|", " _|"), "4": ("   ", "|_|", "  |"), "5": (" _ ", "|_ ", " _|"),
    "6": (" _ ", "|_ ", "|_|"), "7": (" _ ", "  |", "  |"), "8": (" _ ", "|_|", "|_|"),
    "9": (" _ ", "|_|", " _|"), "-": ("   ", " _ ", "   "),
}

STOPS = [(-10, (122, 162, 255)), (0, (94, 200, 255)), (10, (79, 227, 193)), (20, (166, 227, 79)),
         (28, (255, 210, 63)), (35, (255, 138, 61)), (42, (255, 77, 77))]
SPARK = "▁▂▃▄▅▆▇█"
COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


# ---------------------------------------------------------------- helpers
def describe(code, is_day):
    kind, text = CODES.get(code, ("cloud", "Unknown"))
    if kind == "clear" and not is_day:
        kind = "night"
    return kind, text


def temp_color(c):
    if c <= STOPS[0][0]:
        rgb = STOPS[0][1]
    elif c >= STOPS[-1][0]:
        rgb = STOPS[-1][1]
    else:
        for (t0, c0), (t1, c1) in zip(STOPS, STOPS[1:]):
            if t0 <= c <= t1:
                f = (c - t0) / (t1 - t0)
                rgb = tuple(round(a + (b - a) * f) for a, b in zip(c0, c1))
                break
    return "#%02x%02x%02x" % rgb


def big_number(value, unit_letter, style):
    rows = ["", "", ""]
    for ch in str(round(value)):
        for i in range(3):
            rows[i] += DIGITS[ch][i] + " "
    rows[0] += "o"
    rows[1] += unit_letter
    return Text("\n".join(rows), style=f"bold {style}")


# ---------------------------------------------------------------- data
def fetch(city, units):
    imperial = units == "imperial"
    try:
        g = requests.get(GEO_URL, params={"name": city, "count": 1, "language": "en"}, timeout=10)
        g.raise_for_status()
        results = g.json().get("results")
        if not results:
            raise WeatherError(f"Couldn't find a place called '{city}'. Check the spelling or try 'City, Country'.")
        place = results[0]
        w = requests.get(FORECAST_URL, timeout=10, params={
            "latitude": place["latitude"], "longitude": place["longitude"], "timezone": "auto",
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,weather_code,"
                       "surface_pressure,wind_speed_10m,wind_direction_10m",
            "hourly": "temperature_2m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
            "forecast_days": 7,
            "temperature_unit": "fahrenheit" if imperial else "celsius",
            "wind_speed_unit": "mph" if imperial else "kmh",
        })
        w.raise_for_status()
        return place, w.json()
    except requests.RequestException:
        raise WeatherError("Couldn't reach the weather service. Check your internet connection and try again.")


# ---------------------------------------------------------------- rendering
def render(place, data, units):
    imperial = units == "imperial"
    deg, spd = ("°F", "mph") if imperial else ("°C", "km/h")
    to_c = (lambda v: (v - 32) * 5 / 9) if imperial else (lambda v: v)
    col = lambda v: temp_color(to_c(v))

    cur, day, hr = data["current"], data["daily"], data["hourly"]
    kind, desc = describe(cur["weather_code"], cur["is_day"])
    accent = KIND_COLOR[kind]
    t = cur["temperature_2m"]

    # --- hero: icon, big temperature, details
    icon = Text("\n".join(ICONS["partly" if kind == "partly" else kind]), style=accent)
    mid = Group(big_number(t, "F" if imperial else "C", col(t)), Text(""), Text(desc, style=f"bold {accent}"))

    rain_today = (day["precipitation_probability_max"][0] or 0)
    details = Table.grid(padding=(0, 2))
    for label, value in [
        ("Feels like", f"{round(cur['apparent_temperature'])}{deg}"),
        ("Humidity", f"{cur['relative_humidity_2m']}%"),
        ("Wind", f"{round(cur['wind_speed_10m'])} {spd} {COMPASS[round(cur['wind_direction_10m'] / 22.5) % 16]}"),
        ("Pressure", f"{round(cur['surface_pressure'])} hPa"),
        ("Rain today", f"{rain_today}%"),
        ("Sunrise / set", f"{day['sunrise'][0][11:16]} / {day['sunset'][0][11:16]}"),
    ]:
        details.add_row(Text(label, style="grey62"), Text(value, style="bold"))

    hero = Table.grid(padding=(0, 4))
    parts = []
    if console.width >= 86:
        hero.add_row(icon, mid, details)
        parts.append(Align.center(hero))
    else:
        hero.add_row(icon, mid)
        parts += [Align.center(hero), Text(""), Align.center(details)]

    name = ", ".join(x for x in (place["name"], place.get("admin1"), place.get("country")) if x)
    when = datetime.fromisoformat(cur["time"]).strftime("%A, %d %B %Y  %H:%M")
    console.print(Panel(Group(*parts), title=f"[bold]{name}[/]", subtitle=when,
                        border_style=accent, box=box.ROUNDED, padding=(1, 3)))

    # --- next 24 hours
    now = cur["time"][:13]
    start = next((i for i, x in enumerate(hr["time"]) if x[:13] >= now), 0)
    vals = hr["temperature_2m"][start:start + 24]
    lo, hi = min(vals), max(vals)
    mult = 2 if console.width >= 62 else 1
    spark = Text()
    for v in vals:
        idx = round((v - lo) / (hi - lo) * 7) if hi > lo else 3
        spark.append(SPARK[idx] * mult, style=col(v))
    width = len(vals) * mult
    labels = Text("Now".ljust(width // 2) + "+12h".ljust(width - width // 2 - 4) + "+24h"[: 4], style="grey62")
    summary = Text(f"low {round(lo)}{deg}   high {round(hi)}{deg}", style="grey62")
    console.print(Panel(Group(spark, labels, Text(""), summary), title="Next 24 hours",
                        border_style="grey35", box=box.ROUNDED, padding=(0, 2), expand=False))

    # --- 7-day forecast
    mins, maxs = day["temperature_2m_min"], day["temperature_2m_max"]
    wk_lo, wk_hi = min(mins), max(maxs)
    span = (wk_hi - wk_lo) or 1
    W = min(16, console.width - 54)
    show_bar = W >= 6
    table = Table(box=box.SIMPLE_HEAD, header_style="grey62", pad_edge=False, padding=(0, 1))
    table.add_column("Day")
    table.add_column("Conditions", min_width=16)
    table.add_column("Low", justify="right")
    if show_bar:
        table.add_column("Range", no_wrap=True)
    table.add_column("High", justify="right")
    table.add_column("Rain", justify="right")
    for i, date in enumerate(day["time"]):
        k, ds = describe(day["weather_code"][i], 1)
        a = round((mins[i] - wk_lo) / span * (W - 1))
        b = round((maxs[i] - wk_lo) / span * (W - 1))
        bar = Text()
        for p in range(W if show_bar else 0):
            if a <= p <= b:
                bar.append("━", style=col(wk_lo + p / (W - 1) * span))
            else:
                bar.append("─", style="grey23")
        r = day["precipitation_probability_max"][i]
        label = "Today" if i == 0 else datetime.fromisoformat(date).strftime("%a %d")
        cells = [Text(label, style="bold" if i == 0 else ""), Text(ds, style=KIND_COLOR[k]),
                 Text(f"{round(mins[i])}{deg}", style=col(mins[i]))]
        if show_bar:
            cells.append(bar)
        cells += [Text(f"{round(maxs[i])}{deg}", style=col(maxs[i])),
                  Text("-" if r is None else f"{r}%", style="dodger_blue1" if (r or 0) >= 50 else "grey62")]
        table.add_row(*cells)
    console.print(Panel(table, title="7-day forecast", border_style="grey35", box=box.ROUNDED,
                        padding=(0, 2), expand=False))
    console.print("[grey50]Data from Open-Meteo.com[/]\n")


def show(city, units):
    with console.status("[bold]Fetching weather...[/]", spinner="dots"):
        try:
            place, data = fetch(city, units)
        except WeatherError as e:
            err = str(e)
            data = None
    if data is None:
        console.print(Panel(err, title="Couldn't get the weather", border_style="red", expand=False))
        return False
    render(place, data, units)
    return True


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Beautiful weather in your terminal.")
    ap.add_argument("city", nargs="*", help="city name (leave empty for interactive mode)")
    ap.add_argument("-u", "--units", choices=["metric", "imperial"], default="metric")
    args = ap.parse_args()
    units = args.units

    if args.city:
        sys.exit(0 if show(" ".join(args.city), units) else 1)

    console.print(Panel(Align.center(Text("Weather CLI", style="bold bright_cyan")),
                        subtitle="type a city name", border_style="bright_cyan", expand=False, padding=(0, 6)))
    last = None
    try:
        while True:
            answer = Prompt.ask("[bold bright_cyan]City[/] [grey62](u = switch units, q = quit)[/]").strip()
            if answer.lower() in ("q", "quit", "exit"):
                break
            if answer.lower() == "u":
                units = "imperial" if units == "metric" else "metric"
                console.print(f"[grey62]Units: {units}[/]")
                if last:
                    show(last, units)
            elif answer:
                last = answer
                show(last, units)
    except (KeyboardInterrupt, EOFError):
        pass
    console.print("[grey62]Goodbye![/]")


if __name__ == "__main__":
    main()
