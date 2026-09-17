"""
Vigila la colección "Pokémon 30 Aniversario" en cardzone.es, que ahora
mismo está vacía, y avisa por Telegram en cuanto aparezca CUALQUIER
producto nuevo en ella — uno a uno, según se vayan subiendo a lo largo
del día, sin repetir los que ya conoces.

Además, cada N ejecuciones (por defecto 12, ver HEARTBEAT_EVERY más
abajo — con el cron a 5 min, 12 intentos = 1 hora), manda un mensaje
de "sigo vigilando" con el estado actual (vacía o cuántos productos
hay detectados hasta ahora).
"""

import os
import re
import sys
import json
import urllib.request

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = "state_cardzone.json"

HEARTBEAT_EVERY = 12

COLLECTION_URL = "https://cardzone.es/collections/pokemon-30-aniversario"

EMPTY_HINTS = [
    "esta colección está vacía",
    "esta coleccion esta vacia",
]

PRODUCT_LINK_RE = re.compile(r"cardzone\.es/products/([a-zA-Z0-9\-]+)")


def fetch_page(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="ignore")


def slug_to_name(slug: str) -> str:
    return slug.replace("-", " ").strip().capitalize()


def find_product_slugs(html: str) -> set:
    text_lower = html.lower()
    if any(hint in text_lower for hint in EMPTY_HINTS):
        return set()
    return set(PRODUCT_LINK_RE.findall(html))


def load_previous_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"known_slugs": [], "run_count": 0}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def send_telegram_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": CHAT_ID, "text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def main() -> None:
    state = load_previous_state()
    known_slugs = set(state.get("known_slugs", []))
    state["run_count"] = state.get("run_count", 0) + 1
    is_heartbeat_run = state["run_count"] % HEARTBEAT_EVERY == 0

    try:
        html = fetch_page(COLLECTION_URL)
        current_slugs = find_product_slugs(html)
        fetch_error = None
    except Exception as exc:  # noqa: BLE001
        print(f"Error al descargar: {exc}", file=sys.stderr)
        current_slugs = known_slugs
        fetch_error = str(exc)

    new_slugs = current_slugs - known_slugs

    if new_slugs:
        lines = []
        for slug in sorted(new_slugs):
            lines.append(f"- {slug_to_name(slug)}\n  https://cardzone.es/products/{slug}")
        send_telegram_message(
            "🚨 ¡Nuevo(s) producto(s) del 30 Aniversario en CardZone!\n\n"
            + "\n".join(lines)
        )
        print(f"Aviso enviado por Telegram: {len(new_slugs)} producto(s) nuevo(s).")

    if is_heartbeat_run:
        if fetch_error:
            estado = f"⚠️ error al comprobar ({fetch_error})"
        elif current_slugs:
            estado = f"✅ {len(current_slugs)} producto(s) detectados hasta ahora"
        else:
            estado = "⏳ la colección sigue vacía"
        send_telegram_message(
            f"🤖 Sigo vigilando CardZone (intento nº {state['run_count']}): {estado}"
        )
        print("Heartbeat enviado por Telegram.")

    state["known_slugs"] = sorted(known_slugs | current_slugs)
    save_state(state)


if __name__ == "__main__":
    main()
