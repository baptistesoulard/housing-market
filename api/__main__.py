"""Serveur de développement : `python -m api [--port 8000] [--host 127.0.0.1]`.

Le mode debug de Flask reste DÉSACTIVÉ : pratique en développement, jamais au-delà.
Pour un déploiement, servir `api.routes:create_app()` derrière un serveur WSGI.
"""
import argparse

from api.routes import create_app

if __name__ == "__main__":
    p = argparse.ArgumentParser(prog="python -m api")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--origins", default="*", help="Access-Control-Allow-Origin")
    a = p.parse_args()
    print(f"[api] http://{a.host}:{a.port}/api/health")
    create_app(origins=a.origins).run(host=a.host, port=a.port, debug=False, threaded=True)
