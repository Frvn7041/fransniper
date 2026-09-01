"""
Vigila 3 fichas de producto en game.es (30 Aniversario Pokémon) y avisa
por Telegram en cuanto alguna pasa de "PRÓXIMAMENTE / Avísame" a
"disponible para reservar/comprar". Cada aviso (tanto el inmediato de
disponibilidad como el heartbeat) incluye el estado de LOS 3 PRODUCTOS,
para que siempre tengas claro cuál está disponible y cuál no.

Además, cada N ejecuciones (por defecto 5, ver HEARTBEAT_EVERY más
abajo), manda un mensaje de "sigo vigilando" con el estado actual de
los 3 productos, tanto si hay cambios como si no — así sabes que el
robot sigue vivo.

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

HEARTBEAT_EVERY = 15

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

UNAVAILABLE_HINTS = [
    "próximamente", "proximamente", "agotado",
    "avísame cuando", "avisame cuando", "no disponible", "sin stock",
]

AVAILABLE_HINTS = [
    "añadir a la cesta", "anadir a la cesta", "reservar", "comprar ahora",
]


def fetch_page(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"},
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
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def format_status_block(results: list) -> str:
    lines = []
    for r in results:
        if r["available"] is None:
            estado = "⚠️ error al comprobar"
        elif r["available"]:
            estado = "✅ DISPONIBLE"
        else:
            estado = "⏳ aún no disponible"
        line = f"- {r['name']}: {estado}"
        if r["available"]:
            line += f"\n  {r['url']}"
        lines.append(line)
    return "\n".join(lines)


def main() -> None:
    state = load_previous_state()
    meta = state.get("_meta", {"run_count": 0})
    meta["run_count"] = meta.get("run_count", 0) + 1
    is_heartbeat_run = meta["run_count"] % HEARTBEAT_EVERY == 0

    results = []
    any_new_availability = False

    # --- Cada producto se procesa en SU PROPIA iteración del bucle,
    # --- con SU PROPIO html, SU PROPIO is_available_now y SU PROPIO
    # --- was_available_before. Ninguno depende de los otros dos.
    for product in PRODUCTS:
        pid = product["id"]
        try:
            html = fetch_page(product["url"])
        except Exception as exc:  # noqa: BLE001
            print(f"[{pid}] Error al descargar: {exc}", file=sys.stderr)
            results.append({"name": product["name"], "url": product["url"], "available": None})
            continue

        is_available_now = looks_available(html)
        was_available_before = state.get(pid, {}).get("available", False)

        print(f"[{pid}] Disponible ahora: {is_available_now} | Antes: {was_available_before}")

        # OR, no AND: basta con que ESTE producto cambie para disparar el aviso.
        if is_available_now and not was_available_before:
            any_new_availability = True

        state[pid] = {"available": is_available_now}
        results.append({"name": product["name"], "url": product["url"], "available": is_available_now})

    if any_new_availability:
        send_telegram_message("🚨 ¡Cambio de disponibilidad detectado!\n\n" + format_status_block(results))
        print("Aviso de disponibilidad enviado por Telegram.")

    if is_heartbeat_run:
        send_telegram_message(f"🤖 Sigo vigilando (intento nº {meta['run_count']}):\n\n" + format_status_block(results))
        print("Heartbeat enviado por Telegram.")

    state["_meta"] = meta
    save_state(state)


if __name__ == "__main__":
    main()
