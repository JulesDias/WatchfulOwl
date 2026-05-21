# The Watchful Owl

The Watchful Owl est un POC de bot de veille cyber defensif. Il collecte des signaux faibles depuis des sources publiques autorisees, les normalise dans un modele commun, extrait des metadonnees utiles, deduplique, score les signaux et expose les resultats via une API FastAPI avec une interface web de lecture.

Le projet ne clone pas de depot, n'execute aucun exploit et ne stocke que des metadonnees, du texte, des liens, des scores et des resumes.

## Sources

- RSS cyber par defaut :
  - `https://www.bleepingcomputer.com/feed/`
  - `https://thehackernews.com/feeds/posts/default`
  - `https://www.darkreading.com/rss.xml`
  - `https://www.cisa.gov/news.xml`
- GitHub Search Repositories API pour reperer des depots recents lies a CVE, PoC, exploit, RCE, LPE ou auth bypass.
- X/Twitter Recent Search API v2, activee par defaut mais inactive sans `X_BEARER_TOKEN`.

## Regles de securite

- Aucune execution de code d'exploit.
- Aucun clonage automatique de depot d'exploit.
- Utilisation d'APIs officielles ou de flux publics autorises.
- Pas de secret en dur dans le code.
- Tokens et webhooks fournis via variables d'environnement.
- Le collecteur X est optionnel et ne demarre pas sans `X_BEARER_TOKEN`.
- Les erreurs HTTP et les rate limits sont logges sans faire planter l'application.

## Limites du POC

- SQLite est utilise pour simplifier le lancement local.
- Le scoring est heuristique et doit etre calibre sur des donnees reelles.
- La deduplication repose sur URL, CVE ou titre normalise.
- L'API n'inclut pas encore d'authentification.
- Le dashboard est une API JSON, pas encore une interface web.

## Installation locale

Prerequis : Python 3.12+.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Sous Linux ou macOS :

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Configuration

Editez `.env` selon vos besoins :

```env
APP_NAME=The Watchful Owl
DATABASE_URL=sqlite:///./watchful_owl.db
LOG_LEVEL=INFO

GITHUB_TOKEN=
X_BEARER_TOKEN=
DISCORD_WEBHOOK_URL=

ENABLE_RSS=true
ENABLE_GITHUB=true
ENABLE_X=true

COLLECTION_INTERVAL_MINUTES=15
ALERT_SCORE_THRESHOLD=15
MAX_RESULTS_PER_SOURCE=25
```

`GITHUB_TOKEN` est optionnel mais recommande pour augmenter les limites de l'API GitHub. `DISCORD_WEBHOOK_URL` est optionnel : si la valeur est vide, aucune alerte Discord n'est envoyee.
`ENABLE_X` active uniquement l'API officielle X v2 Recent Search. Sans `X_BEARER_TOKEN`, le collecteur X se desactive proprement et ne fait aucun appel.

## Lancement

```bash
python -m uvicorn app.main:app --reload
```

Au demarrage, l'application cree la base SQLite si necessaire et lance le scheduler APScheduler. Une collecte peut aussi etre declenchee manuellement.

Interface web :

```text
http://localhost:8000/
```

## Tests

```bash
pytest
```

Lint optionnel :

```bash
ruff check .
```

## Exemples API

```bash
curl http://localhost:8000/health
curl http://localhost:8000/signals
curl "http://localhost:8000/signals?source_type=github&min_score=12"
curl http://localhost:8000/alerts
curl http://localhost:8000/stats
curl -X POST http://localhost:8000/collect/run
```

Routes exposees :

- `GET /health`
- `GET /signals`
- `GET /signals/{id}`
- `GET /alerts`
- `GET /stats`
- `POST /collect/run`

## Scoring

Le score augmente avec les signaux suivants : CVE, 0day, no CVE, unpatched, PoC released, exploit released, lien GitHub, source GitHub, source X, produit sensible, RCE, auth bypass, privilege escalation ou LPE.

Severite :

- `0-5` : `info`
- `6-11` : `watch`
- `12-18` : `important`
- `19+` : `critical`

Confiance :

- `0-7` : `low`
- `8-15` : `medium`
- `16+` : `high`

## Docker

```bash
docker build -t watchful-owl .
docker run --rm -p 8000:8000 --env-file .env watchful-owl
```

## Prochaines evolutions

- PostgreSQL.
- Interface web.
- Integration CISA KEV.
- Integration NVD.
- Integration Mastodon/Bluesky.
- Clustering des signaux similaires.
- Resume automatique par LLM.
- Lien avec un inventaire de packages type VersionFinder.
