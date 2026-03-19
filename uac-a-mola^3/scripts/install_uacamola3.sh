#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

REPO_DIR="${DEFAULT_REPO_DIR}"
MSF_ROOT=""
METERPRETER_PY_DIR=""
BACKUP_DIR=""
DO_BACKUP=1
DRY_RUN=0
ASSUME_YES=0

info() { echo "[*] $*"; }
ok() { echo "[+] $*"; }
warn() { echo "[!] $*" >&2; }
die() { echo "[-] $*" >&2; exit 1; }

usage() {
  cat <<'EOF'
install_uacamola3.sh

Instala los componentes de uacamola^3 dentro de Metasploit.

Uso:
  ./install_uacamola3.sh [opciones]

Opciones:
  --repo <path>                  Ruta al directorio uac-a-mola^3 (default: carpeta padre del script)
  --msf-root <path>              Ruta a framework root (contiene lib/rex/post/meterpreter)
  --meterpreter-py-dir <path>    Ruta destino de ext_server_*.py (data/meterpreter)
  --backup-dir <path>            Carpeta de backup (default: /tmp/uacamola3-backup-<timestamp>)
  --no-backup                    No hacer backup antes de sobreescribir
  --dry-run                      Muestra acciones sin escribir cambios
  -y, --yes                      No pedir confirmación interactiva
  -h, --help                     Mostrar ayuda

Ejemplos:
  ./install_uacamola3.sh --dry-run
  ./install_uacamola3.sh --msf-root /opt/metasploit-framework/embedded/framework -y
EOF
}

run() {
  if ((DRY_RUN)); then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

run_root() {
  if ((DRY_RUN)); then
    echo "[dry-run] $*"
    return 0
  fi

  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
  else
    if command -v sudo >/dev/null 2>&1; then
      sudo "$@"
    else
      "$@"
    fi
  fi
}

require_dir() {
  local path="$1"
  [[ -d "$path" ]] || die "No existe el directorio: $path"
}

require_file() {
  local path="$1"
  [[ -f "$path" ]] || die "No existe el fichero: $path"
}

parse_args() {
  while (($#)); do
    case "$1" in
      --repo)
        REPO_DIR="${2:-}"; shift 2 ;;
      --msf-root)
        MSF_ROOT="${2:-}"; shift 2 ;;
      --meterpreter-py-dir)
        METERPRETER_PY_DIR="${2:-}"; shift 2 ;;
      --backup-dir)
        BACKUP_DIR="${2:-}"; shift 2 ;;
      --no-backup)
        DO_BACKUP=0; shift ;;
      --dry-run)
        DRY_RUN=1; shift ;;
      -y|--yes)
        ASSUME_YES=1; shift ;;
      -h|--help)
        usage; exit 0 ;;
      *)
        die "Opción no reconocida: $1" ;;
    esac
  done
}

source_paths() {
  SRC_EXT_DIR="$(find "$REPO_DIR" -type d -path "*/framework/lib/rex/post/meterpreter/extensions/uacamola" | head -n1 || true)"
  SRC_DISPATCHER="$(find "$REPO_DIR" -type f -path "*/framework/lib/rex/post/meterpreter/ui/console/command_dispatcher/uacamola.rb" | head -n1 || true)"
  SRC_PY_EXT="$(find "$REPO_DIR" -type f -path "*/data/meterpreter/ext_server_uacamola.py" | head -n1 || true)"

  [[ -n "$SRC_EXT_DIR" ]] || die "No encontré source extension dir (extensions/uacamola) en: $REPO_DIR"
  [[ -n "$SRC_DISPATCHER" ]] || die "No encontré source dispatcher uacamola.rb en: $REPO_DIR"
  [[ -n "$SRC_PY_EXT" ]] || die "No encontré source ext_server_uacamola.py en: $REPO_DIR"
}

detect_msf_root() {
  if [[ -n "$MSF_ROOT" ]]; then
    return 0
  fi

  local candidates=()
  candidates+=("/opt/metasploit-framework/embedded/framework")
  candidates+=("/usr/share/metasploit-framework")
  candidates+=("$HOME/metasploit-framework")
  candidates+=("$HOME/tools/metasploit-framework")
  candidates+=("$HOME/.msf4/metasploit-framework")

  if command -v msfconsole >/dev/null 2>&1; then
    local msf_bin
    msf_bin="$(command -v msfconsole)"
    if [[ -L "$msf_bin" ]]; then
      msf_bin="$(readlink -f "$msf_bin" || echo "$msf_bin")"
    fi

    local msf_base
    msf_base="$(grep -E '^MSF_BASE=' "$msf_bin" 2>/dev/null | head -n1 | cut -d= -f2- | tr -d '"' || true)"
    if [[ -n "$msf_base" ]]; then
      candidates+=("$msf_base")
      candidates+=("$msf_base/embedded/framework")
    fi

    candidates+=("$(cd "$(dirname "$msf_bin")/.." && pwd 2>/dev/null || true)")
    candidates+=("$(cd "$(dirname "$msf_bin")/../embedded/framework" && pwd 2>/dev/null || true)")
  fi

  for c in "${candidates[@]}"; do
    [[ -n "$c" ]] || continue
    if [[ -d "$c/lib/rex/post/meterpreter/extensions" ]]; then
      MSF_ROOT="$c"
      return 0
    fi
  done

  local found
  found="$(find /opt /usr/share "$HOME" -maxdepth 8 -type d -path "*/lib/rex/post/meterpreter/extensions" 2>/dev/null | head -n1 || true)"
  if [[ -n "$found" ]]; then
    MSF_ROOT="${found%/lib/rex/post/meterpreter/extensions}"
    return 0
  fi

  die "No pude autodetectar MSF root. Pásalo con --msf-root."
}

detect_meterpreter_py_dir() {
  if [[ -n "$METERPRETER_PY_DIR" ]]; then
    return 0
  fi

  local search_roots=()
  search_roots+=("$MSF_ROOT")
  search_roots+=("$(cd "$MSF_ROOT/../.." && pwd 2>/dev/null || true)")
  search_roots+=("/opt/metasploit-framework")
  search_roots+=("/usr/share/metasploit-framework")

  local found=""
  for root in "${search_roots[@]}"; do
    [[ -d "$root" ]] || continue
    found="$(find "$root" -type f -name ext_server_stdapi.py 2>/dev/null | head -n1 || true)"
    if [[ -n "$found" ]]; then
      METERPRETER_PY_DIR="$(dirname "$found")"
      break
    fi
  done

  [[ -n "$METERPRETER_PY_DIR" ]] || die "No pude autodetectar data/meterpreter. Pásalo con --meterpreter-py-dir."
}

confirm_plan() {
  cat <<EOF
Plan de instalación:
  Repo source:            $REPO_DIR
  Source extension dir:   $SRC_EXT_DIR
  Source dispatcher file: $SRC_DISPATCHER
  Source python ext:      $SRC_PY_EXT

  Metasploit root:        $MSF_ROOT
  Dest extension dir:     $DST_EXT_DIR
  Dest dispatcher file:   $DST_DISPATCHER
  Dest python ext:        $DST_PY_EXT

  Backup:                 $([[ "$DO_BACKUP" -eq 1 ]] && echo "enabled ($BACKUP_DIR)" || echo "disabled")
  Dry-run:                $([[ "$DRY_RUN" -eq 1 ]] && echo "yes" || echo "no")
EOF

  if ((ASSUME_YES)); then
    return 0
  fi

  read -r -p "¿Continuar con la instalación? [y/N] " ans
  [[ "${ans:-}" =~ ^[Yy]$ ]] || die "Instalación cancelada."
}

backup_item() {
  local src="$1"
  [[ -e "$src" ]] || return 0

  local safe="${src#/}"
  safe="${safe//\//__}"
  local dst="${BACKUP_DIR}/${safe}"
  run_root mkdir -p "$(dirname "$dst")"
  run_root cp -a "$src" "$dst"
}

main() {
  parse_args "$@"

  require_dir "$REPO_DIR"
  source_paths
  detect_msf_root
  detect_meterpreter_py_dir

  require_dir "$MSF_ROOT/lib/rex/post/meterpreter/extensions"
  require_dir "$MSF_ROOT/lib/rex/post/meterpreter/ui/console/command_dispatcher"
  require_dir "$METERPRETER_PY_DIR"

  DST_EXT_DIR="$MSF_ROOT/lib/rex/post/meterpreter/extensions/uacamola"
  DST_DISPATCHER="$MSF_ROOT/lib/rex/post/meterpreter/ui/console/command_dispatcher/uacamola.rb"
  DST_PY_EXT="$METERPRETER_PY_DIR/ext_server_uacamola.py"

  if [[ -z "$BACKUP_DIR" ]]; then
    BACKUP_DIR="/tmp/uacamola3-backup-$(date +%Y%m%d-%H%M%S)"
  fi

  confirm_plan

  if ((DO_BACKUP)); then
    info "Creando backup..."
    run_root mkdir -p "$BACKUP_DIR"
    backup_item "$DST_EXT_DIR"
    backup_item "$DST_DISPATCHER"
    backup_item "$DST_PY_EXT"
    ok "Backup listo en: $BACKUP_DIR"
  fi

  info "Instalando extensión Ruby..."
  run_root rm -rf "$DST_EXT_DIR"
  run_root mkdir -p "$DST_EXT_DIR"
  run_root cp -a "$SRC_EXT_DIR/." "$DST_EXT_DIR/"

  info "Instalando dispatcher..."
  run_root cp -a "$SRC_DISPATCHER" "$DST_DISPATCHER"

  info "Instalando extensión Python meterpreter..."
  run_root cp -a "$SRC_PY_EXT" "$DST_PY_EXT"

  [[ "$DRY_RUN" -eq 1 ]] || {
    require_dir "$DST_EXT_DIR"
    require_file "$DST_DISPATCHER"
    require_file "$DST_PY_EXT"
  }

  ok "Instalación completada."
  cat <<EOF

Siguiente paso en msfconsole/meterpreter:
  meterpreter > load uacamola
  meterpreter > start_uacamola
  uac-a-mola> help
  uac-a-mola> autoelevate_search C:\\
EOF
}

main "$@"
