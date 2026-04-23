# Plan — Gestion propre d'Ollama pour InboxShield

État au 2026-04-23 : Ollama est consommé par le backend via `host.docker.internal:11434` (Mac) ou le container `ollama` (Linux/Docker pur). Sur Mac, l'utilisateur doit installer Ollama manuellement. Si l'app desktop Ollama est utilisée, elle garde inutilement des modèles en RAM (observé : 38 Go pour `glm-4.7-flash` avec contexte 200k). Objectif : fournir une installation et une supervision transparentes, sans app desktop, sans installer automatiquement quoi que ce soit via une API HTTP (surface sécurité).

**Approche retenue** : script d'installation hôte (une fois) + widget de supervision frontend (continu). Pas d'install automatique via le backend containerisé.

Références : `backend/app/services/ollama_manager.py`, `backend/app/api/system.py`, `docker-compose.mac.yml`, `docs/06-DEPLOYMENT.md`.

---

## Phase 1 — Script d'installation hôte

Objectif : un script idempotent qui installe Ollama nativement, le démarre via le service manager de l'OS, et pré-pull le modèle par défaut. Exécuté une fois par l'utilisateur avant `docker compose up`.

### 1.1 Squelette
- [ ] Créer `scripts/install-ollama.sh` (bash, exécutable)
- [ ] En-tête `set -euo pipefail` + détection `uname -s` (Darwin | Linux) + `uname -m` (arm64 | x86_64)
- [ ] Fonctions : `log_info`, `log_warn`, `log_error`, `confirm` (prompt y/N sauf si `--yes`)

### 1.2 Branche macOS
- [ ] Vérifier que Homebrew est présent — si absent : message clair pointant vers `https://brew.sh`, exit 1
- [ ] Si `/Applications/Ollama.app` existe : avertir l'utilisateur, proposer de la déplacer dans la Corbeille (`mv ... ~/.Trash/`), respecter le choix
- [ ] `brew list ollama 2>/dev/null` → si absent : `brew install ollama`
- [ ] `brew services list | grep ollama` → si pas `started` : `brew services start ollama`
- [ ] Poll `curl -s http://localhost:11434/api/tags` jusqu'à 200 (30s max)

### 1.3 Branche Linux
- [ ] Si `systemctl is-active ollama` → skip install
- [ ] Sinon : `curl -fsSL https://ollama.com/install.sh | sh` (l'installateur officiel configure déjà systemd)
- [ ] `systemctl enable --now ollama` (au cas où)
- [ ] Même poll de readiness

### 1.4 Pull du modèle par défaut
- [ ] Lire le modèle depuis `.env` (clé `DEFAULT_OLLAMA_MODEL`, fallback `qwen3:8b`)
- [ ] `ollama list | grep -q "^${MODEL} "` → si absent : `ollama pull ${MODEL}` avec progression visible
- [ ] Note : sur Mac, les modèles sont dans `~/.ollama/models/` — partagés entre app desktop et brew (pas de re-download)

### 1.5 Désactivation du keep-alive agressif (optionnel)
- [ ] Documenter `OLLAMA_KEEP_ALIVE` dans `.env.example` (défaut `5m`, suggestion `2m` pour un Mac 24 Go)
- [ ] Le script propose `launchctl setenv OLLAMA_KEEP_ALIVE 2m` après confirmation

### 1.6 Script de désinstallation miroir
- [ ] Créer `scripts/uninstall-ollama.sh` : `brew services stop ollama` + `brew uninstall ollama` (Mac) ou `systemctl disable --now ollama` + remove binary (Linux). Laisser `~/.ollama/` intact (modèles).

### 1.7 Intégration README
- [ ] Section "Prérequis" du README : ajouter `./scripts/install-ollama.sh` en étape 1, avant `docker compose up`
- [ ] Expliquer pourquoi pas Docker pour Ollama sur Mac (GPU Metal)

**Validation Phase 1** : sur une machine Mac où Ollama n'existe pas, `./scripts/install-ollama.sh` termine avec `curl localhost:11434/api/tags` → 200, `ollama list` → modèle par défaut présent, `brew services list` → `ollama started`. Re-exécution → no-op (idempotence).

---

## Phase 2 — Enrichissement backend

Objectif : API `/system/ollama/status` riche, endpoints de supervision non-destructifs uniquement (pas d'install/uninstall via HTTP). Permettre au frontend de décharger un modèle de la RAM sans toucher au daemon.

### 2.1 `OllamaManager` enrichi (`backend/app/services/ollama_manager.py`)
- [ ] `detect_install_method() -> Literal["homebrew", "systemd", "app", "unknown"]` : heuristiques sur `shutil.which("ollama")` + existence de `/Applications/Ollama.app` + `brew list ollama` (via subprocess tolérant)
- [ ] `get_loaded_models() -> list[dict]` : appel `/api/ps` (équivalent de `ollama ps`) → nom, size, context, until
- [ ] `unload_model(name: str) -> bool` : POST `/api/generate` avec `{"model": name, "keep_alive": 0}` + prompt vide → force l'unload immédiat
- [ ] `get_disk_usage() -> dict` : somme des tailles dans `/api/tags` (déjà disponibles)
- [ ] Tests unitaires mockés (httpx) dans `tests/test_ollama_manager.py`

### 2.2 Endpoint enrichi (`backend/app/api/system.py`)
- [ ] Étendre `OllamaManagerStatus` schema : ajouter `install_method`, `loaded_models: list[LoadedModel]`, `total_disk_bytes`, `service_status` (running/stopped/not-installed)
- [ ] `GET /api/v1/system/ollama/status` : route dédiée (aujourd'hui l'info est noyée dans `/system/health`)
- [ ] `POST /api/v1/system/ollama/unload/{model_name}` : appelle `unload_model`
- [ ] **Pas** d'endpoint `install`, `start`, `stop` daemon → hors scope délibéré

### 2.3 Schemas (`backend/app/schemas/system.py`)
- [ ] `LoadedModel(name: str, size_bytes: int, context_length: int, expires_at: datetime | None)`
- [ ] `OllamaManagerStatus` étendu (backward-compat : nouveaux champs optionnels)

**Validation Phase 2** : `curl /api/v1/system/ollama/status` retourne un JSON riche (install_method="homebrew", 2 modèles listés, 0 chargé après idle). `POST /unload/qwen3:8b` sur un modèle chargé → 200, vérif `ollama ps` côté host → modèle absent. Tests : `pytest tests/test_ollama_manager.py` → verts.

---

## Phase 3 — Widget frontend

Objectif : un panneau dans Settings qui affiche l'état Ollama en temps réel et permet de décharger un modèle manuellement. Instructions claires si Ollama est absent.

### 3.1 Store Pinia (`frontend/src/stores/settings.ts` ou nouveau `ollama.ts`)
- [ ] `ollamaStatus` : `ref<OllamaStatus | null>`
- [ ] `fetchOllamaStatus()` : GET `/system/ollama/status`
- [ ] `unloadModel(name)` : POST `/system/ollama/unload/{name}` + refresh

### 3.2 Composant `components/settings/OllamaStatusCard.vue`
- [ ] 3 états visuels (vert/orange/rouge) selon `service_status` :
  - **Running** : badge vert "En cours", liste des modèles installés (nom, taille, chargé/déchargé, bouton "Libérer la RAM" sur chaque chargé)
  - **Not running** : badge orange "Arrêté", texte : "Relance avec `brew services start ollama` / `systemctl start ollama`"
  - **Not installed** : badge rouge, texte : "Exécute `./scripts/install-ollama.sh` depuis la racine du projet"
- [ ] Affichage `install_method` + chemin binaire (debug info)
- [ ] Total disk usage des modèles (en Go)
- [ ] Auto-refresh via `usePolling(10000)` (10s)

### 3.3 Intégration `SettingsView.vue`
- [ ] Insérer `<OllamaStatusCard />` entre la section "Compte IMAP" et "Configuration LLM"
- [ ] Conditionner l'affichage : ne le montrer que si `settings.llm_provider === "ollama"`

### 3.4 Types (`frontend/src/lib/types.ts`)
- [ ] `interface OllamaStatus` miroir du backend schema
- [ ] `interface LoadedModel`

**Validation Phase 3** : `pnpm run type-check` + `pnpm run build-only` verts. Manuel : avec Ollama up, la carte passe vert, liste `qwen3:8b` 5.2 Go. `ollama run qwen3:8b "hi"` depuis un autre terminal → la carte affiche "chargé" dans les 10s. Clic "Libérer la RAM" → après refresh, déchargé.

---

## Phase 4 — Documentation et UX d'onboarding

### 4.1 README.md
- [ ] Section "Quick start" révisée :
  1. `./scripts/install-ollama.sh` (ou clé API cloud en alternative)
  2. `cp .env.example .env` + édit
  3. `docker compose up -d`
- [ ] Tableau "Options LLM" : Ollama natif (Mac/Linux, GPU, privacy) vs. container `ollama` (Linux seulement, CPU, slow) vs. cloud (setup zéro, données sortent)

### 4.2 `docs/06-DEPLOYMENT.md`
- [ ] Nouveau paragraphe "Installation d'Ollama" qui réfère au script + explique pourquoi pas Docker sur Mac (Metal)
- [ ] Déprécier les instructions `docker compose exec ollama ollama pull` pour Mac (le container `ollama` n'est plus utilisé sur Mac)

### 4.3 In-app onboarding (si temps)
- [ ] Au premier lancement, si aucun compte IMAP + LLM provider = `ollama` + `ollama_status.service_status != "running"` : afficher un banner dans Settings avec la commande d'install

**Validation Phase 4** : un utilisateur qui suit le README sur une machine vierge arrive à un InboxShield fonctionnel en moins de 10 min sans chercher d'aide externe.

---

## Phase 5 — Validation bout-en-bout et commit

- [ ] Tester le script sur : Mac M-series (GPU Metal), Linux x86_64 sans GPU, Linux arm64 (Raspberry Pi 5 si dispo)
- [ ] Vérifier le comportement RAM : idle → modèle déchargé après `OLLAMA_KEEP_ALIVE`, pic < 10 Go pendant classification
- [ ] `pytest backend/tests/` → tous verts (dont les nouveaux `test_ollama_manager.py`)
- [ ] `pnpm run lint` + `pnpm run type-check` → 0 warning
- [ ] `ruff check backend/ && ruff format --check backend/`
- [ ] Commit atomique par phase (`feat(ollama): install script`, `feat(ollama): status API`, `feat(ollama): status widget`, `docs(ollama): setup guide`)
- [ ] Mettre à jour `CLAUDE.md` — nouvelle section "Gestion d'Ollama", déplacer le item "[ ] Setup wizard" vers cette approche

---

## Notes et garde-fous

- **Pas de suppression d'app desktop automatique** : le script *propose* de déplacer `/Applications/Ollama.app` vers la Corbeille, il ne force rien. L'utilisateur garde le contrôle.
- **Pas d'install via API HTTP** : le backend containerisé ne doit jamais exécuter des commandes d'installation sur l'hôte. Surface sécurité trop grande, architecture trop complexe (helper host, socket Unix, etc.).
- **Pas de bundle Ollama** : trop gros (~500 Mo), licence à vérifier, updates à gérer. Délégué au package manager OS.
- **Modèle par défaut** : reste `qwen2.5:7b` dans `backend/app/config.py`. Le script pulle ce qui est configuré via `DEFAULT_OLLAMA_MODEL` dans `.env`, avec fallback `qwen3:8b` (déjà observé comme plus léger en RAM et suffisamment performant).
- **Windows** : hors scope pour l'instant. La cible est Mac prod + Linux dev/prod.
- **Fallback cloud** : le script détecte si `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `MISTRAL_API_KEY` sont présents dans `.env` et propose de skip l'install Ollama ("tu utilises déjà un provider cloud, tu peux passer").

---

## Checklist d'exécution pour la nouvelle conversation

Copier-coller dans le nouveau chat :

> Applique `OLLAMA_SETUP_PLAN.md`. Commence par la Phase 1, commit à la fin de chaque phase validée, ne passe à la phase suivante qu'après validation explicite de ma part. Conventions : ruff/pnpm lint doivent rester propres, pas de nouveaux warnings.
