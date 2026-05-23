#!/usr/bin/env bash
# install-deps.sh — install this project's runtime dependencies.
# Generated and maintained by depgen.
#
# Anything OUTSIDE the `# >>> depgen:<section> <<<` / `# <<< depgen:<section> <<<`
# markers is yours to edit — depgen will not touch it.
# Anything INSIDE the markers will be rewritten on the next `depgen` run.
set -euo pipefail

# ── Distro detection (self-contained, no external deps) ──────────────
detect_pm() {
  if command -v apt-get >/dev/null 2>&1; then echo apt
  elif command -v dnf     >/dev/null 2>&1; then echo dnf
  elif command -v pacman  >/dev/null 2>&1; then echo pacman
  elif command -v brew    >/dev/null 2>&1; then echo brew
  fi
}
pm_install() {
  local pkg="$1"
  case "$(detect_pm)" in
    apt)    sudo apt-get install -y "$pkg" ;;
    dnf)    sudo dnf install -y "$pkg" ;;
    pacman) sudo pacman -S --noconfirm "$pkg" ;;
    brew)   brew install "$pkg" ;;
    *)      echo "No supported package manager (apt/dnf/pacman/brew) found." >&2
            return 1 ;;
  esac
}

# ── System packages ──────────────────────────────────────────────────
# >>> depgen:system <<<
REQUIRED_CMDS=()
# <<< depgen:system <<<

if (( ${#REQUIRED_CMDS[@]} > 0 )); then
  PM="$(detect_pm)"
  if [[ -z "$PM" ]]; then
    echo "No supported package manager — install ${REQUIRED_CMDS[*]} manually." >&2
    exit 1
  fi
  [[ "$PM" == "apt" ]] && sudo apt-get update -qq
  for cmd in "${REQUIRED_CMDS[@]}"; do
    if command -v "$cmd" >/dev/null 2>&1; then
      printf '  OK      %s already installed\n' "$cmd"
    else
      printf '  MISSING %s — installing\n' "$cmd"
      pm_install "$cmd" || printf '  FAIL    could not install %s\n' "$cmd"
    fi
  done
fi

# ── Python dependencies ──────────────────────────────────────────────
# >>> depgen:python <<<
if [[ -f requirements.txt ]]; then
  python3 -m venv .venv
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pip install --upgrade pip >/dev/null
  pip install -r requirements.txt
fi
# <<< depgen:python <<<

echo "Done."
