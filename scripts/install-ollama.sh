#!/usr/bin/env bash
# InboxShield — installation idempotente d'Ollama sur l'hote (Mac ou Linux).
# Objectif : preparer Ollama natif avant `docker compose up`. Aucun appel HTTP
# ne touche au daemon, tout passe par le gestionnaire de paquets de l'OS.

set -euo pipefail

# ─── Parse args ──────────────────────────────────────────
ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y) ASSUME_YES=1 ;;
    --help|-h)
      cat <<'USAGE'
Usage: install-ollama.sh [--yes]

Installe Ollama nativement (Homebrew sur macOS, install.sh officiel sur Linux),
le demarre via le service manager, puis pre-pull le modele par defaut.

Options :
  -y, --yes    Repondre "oui" a toutes les confirmations.
  -h, --help   Afficher cette aide.
USAGE
      exit 0
      ;;
    *)
      echo "Argument inconnu : $arg" >&2
      exit 2
      ;;
  esac
done

# ─── Logging ─────────────────────────────────────────────
if [ -t 1 ]; then
  C_BLUE="\033[1;34m"; C_YELLOW="\033[1;33m"; C_RED="\033[1;31m"; C_GREEN="\033[1;32m"; C_RESET="\033[0m"
else
  C_BLUE=""; C_YELLOW=""; C_RED=""; C_GREEN=""; C_RESET=""
fi

log_info()  { printf "${C_BLUE}[info]${C_RESET} %s\n" "$*"; }
log_warn()  { printf "${C_YELLOW}[warn]${C_RESET} %s\n" "$*" >&2; }
log_error() { printf "${C_RED}[error]${C_RESET} %s\n" "$*" >&2; }
log_ok()    { printf "${C_GREEN}[ok]${C_RESET} %s\n" "$*"; }

confirm() {
  local prompt="${1:-Continuer ?}"
  if [ "$ASSUME_YES" -eq 1 ]; then
    return 0
  fi
  local reply
  printf "%s [y/N] " "$prompt"
  read -r reply || reply=""
  case "$reply" in
    [yY]|[yY][eE][sS]|[oO]|[oO][uU][iI]) return 0 ;;
    *) return 1 ;;
  esac
}

# ─── Detection plateforme ────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"
log_info "Plateforme detectee : $OS / $ARCH"

case "$OS" in
  Darwin|Linux) ;;
  *)
    log_error "OS non supporte : $OS (seuls Darwin et Linux le sont)."
    exit 1
    ;;
esac

# ─── Lecture du modele par defaut + cles API ────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

read_env_var() {
  local key="$1"
  if [ -f "$ENV_FILE" ]; then
    # Pas de sourcing : on parse proprement pour eviter les effets de bord.
    local line
    line="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 || true)"
    if [ -n "$line" ]; then
      # Retire la cle + le '=' et les guillemets eventuels.
      local value="${line#*=}"
      value="${value%\"}"; value="${value#\"}"
      value="${value%\'}"; value="${value#\'}"
      printf "%s" "$value"
      return 0
    fi
  fi
  return 1
}

DEFAULT_MODEL="$(read_env_var DEFAULT_OLLAMA_MODEL || true)"
: "${DEFAULT_MODEL:=qwen3:8b}"

# Fallback cloud : si au moins une cle API cloud est configuree, on propose de skip.
CLOUD_PROVIDERS=()
for key in ANTHROPIC_API_KEY OPENAI_API_KEY MISTRAL_API_KEY; do
  value="$(read_env_var "$key" || true)"
  if [ -n "$value" ]; then
    CLOUD_PROVIDERS+=("${key%_API_KEY}")
  fi
done

if [ "${#CLOUD_PROVIDERS[@]}" -gt 0 ]; then
  log_warn "Cle(s) API cloud detectee(s) dans .env : ${CLOUD_PROVIDERS[*]}"
  log_warn "Tu peux utiliser InboxShield en mode cloud sans installer Ollama."
  if ! confirm "Continuer quand meme l'install d'Ollama ?"; then
    log_info "Installation annulee. Configure 'llm_provider' sur un provider cloud dans Settings."
    exit 0
  fi
fi

log_info "Modele par defaut a pre-puller : $DEFAULT_MODEL"

# ─── Branche macOS ───────────────────────────────────────
install_mac() {
  if ! command -v brew >/dev/null 2>&1; then
    log_error "Homebrew introuvable."
    log_error "Installe-le via https://brew.sh puis relance ce script."
    exit 1
  fi

  if [ -d "/Applications/Ollama.app" ]; then
    log_warn "L'application desktop Ollama.app est presente dans /Applications/."
    log_warn "Elle garde souvent un modele charge en RAM en permanence (keep-alive desktop agressif)."
    if confirm "Deplacer /Applications/Ollama.app vers la Corbeille ?"; then
      mv "/Applications/Ollama.app" "$HOME/.Trash/" || {
        log_warn "Impossible de deplacer Ollama.app (droits ?). Poursuite sans toucher."
      }
      log_ok "Ollama.app deplacee vers la Corbeille."
    else
      log_info "Ollama.app conservee. Quitte-la manuellement si elle tourne pour eviter les doublons."
    fi
  fi

  if brew list ollama >/dev/null 2>&1; then
    log_ok "Formule 'ollama' deja installee via Homebrew."
  else
    log_info "Installation d'Ollama via Homebrew…"
    brew install ollama
  fi

  # Demarre le service si pas deja started.
  if brew services list | awk '$1 == "ollama" { print $2 }' | grep -q '^started$'; then
    log_ok "Service brew 'ollama' deja demarre."
  else
    log_info "Demarrage du service brew 'ollama'…"
    brew services start ollama
  fi
}

# ─── Branche Linux ───────────────────────────────────────
install_linux() {
  if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet ollama; then
    log_ok "Service systemd 'ollama' deja actif."
    return 0
  fi

  if command -v ollama >/dev/null 2>&1; then
    log_ok "Binaire 'ollama' deja present."
  else
    log_info "Telechargement et installation via installeur officiel…"
    curl -fsSL https://ollama.com/install.sh | sh
  fi

  if command -v systemctl >/dev/null 2>&1; then
    log_info "Activation + demarrage du service systemd 'ollama'…"
    if [ "$(id -u)" -eq 0 ]; then
      systemctl enable --now ollama
    else
      sudo systemctl enable --now ollama
    fi
  else
    log_warn "systemctl indisponible — lance 'ollama serve' manuellement en arriere-plan."
  fi
}

# ─── Readiness probe ────────────────────────────────────
wait_for_ollama() {
  log_info "Attente de la disponibilite d'Ollama sur http://localhost:11434…"
  local attempt=0
  local max_attempts=30  # ~30s avec sleep 1
  while [ "$attempt" -lt "$max_attempts" ]; do
    if curl -fsS -o /dev/null -w "%{http_code}" "http://localhost:11434/api/tags" 2>/dev/null | grep -q '^200$'; then
      log_ok "Ollama repond sur localhost:11434."
      return 0
    fi
    attempt=$((attempt + 1))
    sleep 1
  done
  log_error "Ollama n'a pas repondu apres ${max_attempts}s."
  log_error "Verifie le service (brew services list / systemctl status ollama)."
  exit 1
}

# ─── Pull modele par defaut ─────────────────────────────
pull_default_model() {
  if ! command -v ollama >/dev/null 2>&1; then
    log_error "Binaire 'ollama' introuvable dans le PATH apres installation."
    exit 1
  fi

  if ollama list 2>/dev/null | awk 'NR>1 { print $1 }' | grep -qx "$DEFAULT_MODEL"; then
    log_ok "Modele '$DEFAULT_MODEL' deja present localement."
    return 0
  fi

  log_info "Pull du modele '$DEFAULT_MODEL' (peut prendre plusieurs minutes)…"
  ollama pull "$DEFAULT_MODEL"
  log_ok "Modele '$DEFAULT_MODEL' disponible."
}

# ─── Keep-alive ajustable (optionnel) ───────────────────
suggest_keep_alive() {
  if [ "$OS" != "Darwin" ]; then
    return 0
  fi
  local current
  current="$(launchctl getenv OLLAMA_KEEP_ALIVE 2>/dev/null || true)"
  if [ -n "$current" ]; then
    log_info "OLLAMA_KEEP_ALIVE deja defini : $current"
    return 0
  fi
  log_info "Astuce RAM : reduire OLLAMA_KEEP_ALIVE de 5m (defaut) a 2m decharge les modeles plus vite."
  if confirm "Definir OLLAMA_KEEP_ALIVE=2m via launchctl (persiste sur cette session utilisateur) ?"; then
    launchctl setenv OLLAMA_KEEP_ALIVE 2m
    log_ok "OLLAMA_KEEP_ALIVE=2m applique. Redemarre le service si tu veux qu'il soit pris en compte : brew services restart ollama"
  else
    log_info "Keep-alive par defaut conserve (5m)."
  fi
}

# ─── Orchestration ──────────────────────────────────────
case "$OS" in
  Darwin) install_mac ;;
  Linux)  install_linux ;;
esac

wait_for_ollama
pull_default_model
suggest_keep_alive

log_ok "Installation d'Ollama terminee."
log_info "Lance ensuite : docker compose -f docker-compose.yml -f docker-compose.mac.yml up -d (Mac) ou docker compose up -d (Linux)."
