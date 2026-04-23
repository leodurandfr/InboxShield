#!/usr/bin/env bash
# InboxShield — desinstallation d'Ollama (miroir de install-ollama.sh).
# Laisse volontairement ~/.ollama/models intact : l'utilisateur peut vouloir
# recuperer plusieurs Go de modeles plus tard.

set -euo pipefail

ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y) ASSUME_YES=1 ;;
    --help|-h)
      cat <<'USAGE'
Usage: uninstall-ollama.sh [--yes]

Arrete et desinstalle Ollama natif. Les modeles dans ~/.ollama/ ne sont pas
touches : supprime-les manuellement avec `rm -rf ~/.ollama` si besoin.
USAGE
      exit 0
      ;;
    *)
      echo "Argument inconnu : $arg" >&2
      exit 2
      ;;
  esac
done

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

OS="$(uname -s)"

if ! confirm "Desinstaller Ollama de cette machine (modeles conserves) ?"; then
  log_info "Annulation."
  exit 0
fi

case "$OS" in
  Darwin)
    if command -v brew >/dev/null 2>&1; then
      if brew services list | awk '$1 == "ollama" { print $2 }' | grep -q '^started$'; then
        log_info "Arret du service brew 'ollama'…"
        brew services stop ollama || log_warn "brew services stop a echoue."
      fi
      if brew list ollama >/dev/null 2>&1; then
        log_info "Desinstallation de la formule 'ollama'…"
        brew uninstall ollama
      else
        log_info "La formule 'ollama' n'etait pas installee via Homebrew."
      fi
    else
      log_warn "Homebrew introuvable — rien a desinstaller via brew."
    fi
    ;;
  Linux)
    if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet ollama; then
      log_info "Arret + desactivation du service systemd 'ollama'…"
      if [ "$(id -u)" -eq 0 ]; then
        systemctl disable --now ollama || log_warn "systemctl disable a echoue."
      else
        sudo systemctl disable --now ollama || log_warn "systemctl disable a echoue."
      fi
    fi
    if [ -f /etc/systemd/system/ollama.service ]; then
      log_info "Suppression de l'unit systemd /etc/systemd/system/ollama.service…"
      if [ "$(id -u)" -eq 0 ]; then
        rm -f /etc/systemd/system/ollama.service
      else
        sudo rm -f /etc/systemd/system/ollama.service
      fi
    fi
    if command -v ollama >/dev/null 2>&1; then
      bin_path="$(command -v ollama)"
      log_info "Suppression du binaire $bin_path…"
      if [ -w "$bin_path" ] || [ "$(id -u)" -eq 0 ]; then
        rm -f "$bin_path"
      else
        sudo rm -f "$bin_path"
      fi
    fi
    ;;
  *)
    log_error "OS non supporte : $OS"
    exit 1
    ;;
esac

log_ok "Ollama desinstalle. Les modeles sont toujours dans ~/.ollama/ (supprime avec 'rm -rf ~/.ollama' si voulu)."
