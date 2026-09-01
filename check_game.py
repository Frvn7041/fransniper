"""
Vigila 3 fichas de producto en game.es (30 Aniversario Pokémon) y avisa
por Telegram en cuanto cada una pasa de "PRÓXIMAMENTE / Avísame" a
"disponible para reservar/comprar".

No hace falta tocar nada salvo, si GAME cambia el texto de la web,
las listas UNAVAILABLE_HINTS / AVAILABLE_HINTS de más abajo.
"""

import os
import re
import sys
import json
import urllib.request

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = "state.json"

# Los 3 productos a vigilar. "id" es una clave corta interna, no la toques.
PRODUCTS = [
    {
        "id": "ditto",
        "name": "Caja de colección Ditto (Premium)",
        "url": "https://www.game.es/coleccionables/cartas-pokmon/merchandising/caja-de-coleccion-premium-cartas-pokemon-30-aniversario-castellano/266952",
    },
    {
        "id": "etb",
        "name": "Elite Trainer Box 30 Aniversario",
        "url": "https://www.game.es/coleccionables/cartas-pokmon/merchandising/caja-de-entrenador-elite-pokemon-30-aniversario-castellano/266941",
    },
    {
        "id": "upc",
        "name": "Caja Ultra Premium 30 Aniversario",
        "url": "https://www.game.es/coleccionables/cartas-pokmon/merchandising/caja-ultra-premium-de-cartas-pokemon-30-aniversario-castellano-surtido/266954",
    },
]

# Frases que indican que TODAVÍA NO se puede reservar/comprar.
UNAVAILABLE_HINTS = [
    "próximamente",
    "proximamente",
    "agotado",
    "avísame cuando",
    "avisame cuando",
    "no disponible",
    "sin stock",
]

# Frases que indican que SÍ se puede reservar/comprar ya.
AVAILABLE_HINTS = [
    "añadir a la cesta",
    "anadir a la cesta",
    "reservar",
    "comprar ahora",
]


def fetch_page(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="ignore")


def looks_available(html: str) -> bool:
    text = re.sub(r"<[^>]+>", " ", html).lower()
    text = re.sub(r"\s+", " ", text)

    has_unavailable = any(hint in text for hint in UNAVAILABLE_HINTS)
    has_available = any(hint in text for hint in AVAILABLE_HINTS)

    return has_available and not has_unavailable


def load_previous_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def send_telegram_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": CHAT_ID, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def main() -> None:
    state = load_previous_state()

    for product in PRODUCTS:
        pid = product["id"]
        try:
            html = fetch_page(product["url"])
        except Exception as exc:  # noqa: BLE001
            print(f"[{pid}] Error al descargar: {exc}", file=sys.stderr)
            continue

        is_available_now = looks_available(html)
        was_available_before = state.get(pid, {}).get("available", False)

        print(f"[{pid}] Disponible ahora: {is_available_now} | Antes: {was_available_before}")

        if is_available_now and not was_available_before:
            send_telegram_message(
                "🚨 ¡Ya se puede reservar/comprar!\n"
                f"{product['name']}\n"
                f"{product['url']}"
            )
            print(f"[{pid}] Aviso enviado por Telegram.")

        state[pid] = {"available": is_available_now}

    save_state(state)


if __name__ == "__main__":
    main()
