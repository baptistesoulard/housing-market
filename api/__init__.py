"""API HTTP mince devant le moteur de calcul (queries.py + forecast.py).

Trois couches, chacune ne connaissant que la suivante :

    navigateur ──fetch()──► api/routes.py ──► api/engine.py ──► queries.py / forecast.py

`api/engine.py` n'importe pas Flask : le moteur reste exécutable et testable serveur
éteint. Lancer le serveur de développement : `python -m api` (port 8000 par défaut).
"""
