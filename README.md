# The Watchful Owl

**The Watchful Owl** est une plateforme de renseignement en cybersécurité défensive. Elle collecte des signaux faibles provenant de sources publiques autorisées, les normalise selon un modèle commun, extrait des métadonnées pertinentes, déduplique, score les signaux et expose les résultats via une API FastAPI avec un tableau de bord web.

### Principes de conception

- **Observations uniquement** : collecte passive de renseignements publics
- **Pas de code malveillant** : aucun clonage de dépôt d'exploit, aucune exécution de PoC
- **Données non-sensibles** : stockage de métadonnées, textes, liens, scores et résumés uniquement
- **Transparence** : configuration via variables d'environnement, logs détaillés

## Sources de données

### Flux RSS
- **Bleeping Computer** : `https://www.bleepingcomputer.com/feed/`
- **The Hacker News** : `https://thehackernews.com/feeds/posts/default`
- **Dark Reading** : `https://www.darkreading.com/rss.xml`
- **CISA Alerts** : `https://www.cisa.gov/news.xml`
- **HackerNews** : `https://news.ycombinator.com/rss` (articles tech/sécurité tendance)
- **Reddit r/netsec** : `https://www.reddit.com/r/netsec/.rss` (discussions sécurité réseau)
- **CS Hub** : `https://www.cshub.com/rss/categories/attacks` (incidents cyber)

### API
- **GitHub Search API** : dépôts récents contenant CVE, PoC, exploit, RCE, LPE ou authentification bypass
- **X/Twitter API v2** : recherche récente sur menaces cyber (optionnel, nécessite authentification)

## Sécurité

### Garanties
- Aucune exécution de code malveillant
- Aucun clonage automatique de dépôts d'exploit
- Utilisation d'APIs officielles et flux publics autorisés
- Secrets stockés en variables d'environnement uniquement
- Gestion gracieuse des erreurs HTTP et rate limits

### Configuration d'accès
- `GITHUB_TOKEN` : optionnel mais recommandé (augmente les limites API)
- `X_BEARER_TOKEN` : optionnel (désactive le collecteur X/Twitter s'il manque)
- `DISCORD_WEBHOOK_URL` : optionnel (alerte Discord désactivée si vide)

## État du projet

### Fonctionnalités actuelles
- Collecte multi-sources (RSS, GitHub, X)
- Pipeline de traitement : extraction, déduplication, scoring
- API REST complète avec FastAPI
- Tableau de bord web interactif
- Scheduler de collecte autonome
- Intégration Discord pour alertes
- Tests unitaires

### Points à affiner
- **Base de données** : SQLite utilisé pour le déploiement local (PostgreSQL envisagé)
- **Scoring** : basé sur heuristiques (calibrage recommandé en production)
- **Déduplication** : URL, CVE ou titre normalisé
- **API** : pas encore d'authentification (à ajouter)

## Installation

### Prérequis
- Python 3.12+
- pip ou poetry

### Setup local

**Windows :**
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

**Linux / macOS :**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Configuration

Éditez `.env` selon votre déploiement :

```env
# Application
APP_NAME=The Watchful Owl
LOG_LEVEL=INFO

# Base de données
DATABASE_URL=sqlite:///./watchful_owl.db

# Authentification APIs (optionnel)
GITHUB_TOKEN=
X_BEARER_TOKEN=
DISCORD_WEBHOOK_URL=

# Collecte
ENABLE_RSS=true
ENABLE_GITHUB=true
ENABLE_X=true
ENABLE_SCHEDULER=true

# Paramètres
COLLECTION_INTERVAL_MINUTES=15
ALERT_SCORE_THRESHOLD=15
MAX_RESULTS_PER_SOURCE=25
MAX_CONCURRENT_COLLECTORS=3
COLLECTOR_TIMEOUT_SECONDS=60.0
RSS_FEED_CONCURRENCY=5
HTTP_TIMEOUT_SECONDS=15.0
GITHUB_MIN_STARS=0
```

### Variables clés
| Variable | Obligatoire | Effet |
|----------|------------|-------|
| `GITHUB_TOKEN` | Non | Augmente limites API GitHub |
| `X_BEARER_TOKEN` | Non | Active collecteur X/Twitter |
| `DISCORD_WEBHOOK_URL` | Non | Active alertes Discord |
| `ENABLE_SCHEDULER` | Non | Lance le scheduler embarqué avec l'application |
| `ALERT_SCORE_THRESHOLD` | Non | Seuil de score minimum pour alerte |
| `MAX_CONCURRENT_COLLECTORS` | Non | Nombre maximum de collecteurs exécutés en parallèle |
| `COLLECTOR_TIMEOUT_SECONDS` | Non | Timeout global par collecteur |
| `RSS_FEED_CONCURRENCY` | Non | Nombre de flux RSS récupérés en parallèle |

## Démarrage

### Development
```bash
python -m uvicorn app.main:app --reload
```

### Production
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

L'application crée automatiquement la base SQLite et lance le scheduler si `ENABLE_SCHEDULER=true`. Évitez `--workers > 1` avec le scheduler embarqué, sinon chaque worker lancera sa propre collecte planifiée. Pour un déploiement multi-workers, lancez les workers API avec `ENABLE_SCHEDULER=false` et gardez un seul processus chargé de la collecte. Une collecte peut être déclenchée manuellement via l'API.

**Accès** : http://localhost:8000/

## Tests

### Exécuter les tests
```bash
pytest
```

### Linting (optionnel)
```bash
ruff check .
ruff format .
```

## Migrations

Les migrations de schéma sont versionnées avec Alembic.

```bash
python -m alembic upgrade head
python -m alembic revision --autogenerate -m "description"
```

`SQLModel.metadata.create_all` reste utilisé au démarrage pour les installations locales neuves, mais les évolutions de schéma doivent passer par Alembic.

## Utilisation API

### Exemples de requêtes
```bash
# Santé de l'application
curl http://localhost:8000/health

# Tous les signaux
curl http://localhost:8000/signals

# Signaux filtrés
curl "http://localhost:8000/signals?source_type=github&min_score=12"
curl "http://localhost:8000/signals?limit=50"
curl "http://localhost:8000/signals?limit=50&offset=50"

# Alertes générées
curl http://localhost:8000/alerts

# Statistiques
curl http://localhost:8000/stats

# Déclencher collecte manuelle
curl -X POST http://localhost:8000/collect/run

# Historique des collectes
curl http://localhost:8000/collection-runs
```

### Endpoints
| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/health` | Status de l'application |
| GET | `/signals` | Liste tous les signaux |
| GET | `/signals/{id}` | Détail d'un signal |
| GET | `/alerts` | Alertes générées |
| GET | `/stats` | Statistiques globales |
| GET | `/collection-runs` | Historique paginé des collectes par source |
| POST | `/collect/run` | Collecte manuelle immédiate |

Les endpoints de liste acceptent `limit` et `offset`, et renvoient les headers `X-Total-Count`, `X-Page-Limit`, `X-Page-Offset` et `X-Has-More`.

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
