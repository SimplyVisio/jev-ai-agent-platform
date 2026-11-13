"""Cliente de terminal para conversar con el chatbot de JEV AI.

No necesita dependencias extra: usa ``urllib`` de la biblioteca estándar.

Uso:
    python scripts/chat_cli.py --api-key "jev_..."
    python scripts/chat_cli.py --api-key "jev_..." --message "Top 3 anuncios por ROAS"
    JEV_API_KEY="jev_..." python scripts/chat_cli.py
"""

import argparse
import json
import os
import urllib.error
import urllib.request


def send_message(base_url: str, api_key: str, message: str, *, dry_run: bool) -> dict:
    """Envía un mensaje al endpoint de chat y devuelve el JSON de respuesta."""
    payload = json.dumps({"message": message, "dry_run": dry_run}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/v1/chat",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _print_response(body: dict, *, show_plan: bool) -> None:
    print(f"\nJEV AI [{body['status']} · {body['intent']}]:")
    print(body["reply"])
    if show_plan and body.get("query_plan"):
        print("\nQueryPlan validado:")
        print(json.dumps(body["query_plan"], indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat de terminal para JEV AI.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default=os.environ.get("JEV_API_KEY"))
    parser.add_argument("--message", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--show-plan", action="store_true")
    args = parser.parse_args()

    if not args.api_key:
        parser.error("Falta --api-key o la variable de entorno JEV_API_KEY.")

    if args.message:
        try:
            body = send_message(args.base_url, args.api_key, args.message, dry_run=args.dry_run)
        except urllib.error.HTTPError as exc:
            print(f"Error HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
            raise SystemExit(1) from exc
        except urllib.error.URLError as exc:
            print(f"No se pudo conectar con la API: {exc.reason}")
            raise SystemExit(1) from exc
        _print_response(body, show_plan=args.show_plan)
        return

    print("Chat de JEV AI. Escribe 'salir' para terminar.")
    while True:
        try:
            message = input("\nTú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not message:
            continue
        if message.lower() in {"salir", "exit", "quit"}:
            break
        try:
            body = send_message(
                args.base_url,
                args.api_key,
                message,
                dry_run=args.dry_run,
            )
        except urllib.error.HTTPError as exc:
            print(f"Error HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
            continue
        except urllib.error.URLError as exc:
            print(f"No se pudo conectar con la API: {exc.reason}")
            continue
        _print_response(body, show_plan=args.show_plan)


if __name__ == "__main__":
    main()
