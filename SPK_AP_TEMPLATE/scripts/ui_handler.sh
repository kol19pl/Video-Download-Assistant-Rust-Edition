#!/bin/sh

# UI Handler for VDA Server DSM Interface
PKG_NAME="vda_serwer"
PKG_DIR="/var/packages/$PKG_NAME"
CONF_FILE="$PKG_DIR/var/config.env"
LOG_FILE="$PKG_DIR/var/$PKG_NAME.log"
SCRIPT_DIR="$(dirname "$0")"
START_STOP_SCRIPT="$SCRIPT_DIR/start-stop-status"

# Load configuration
load_config() {
    if [ -f "$CONF_FILE" ]; then
        . "$CONF_FILE"
    fi
}

# Save configuration
save_config() {
    # Read POST data from DSM UI
    read -r input
    eval "$input"

    # Validate and save configuration
    DOWNLOAD_DIR="${DOWNLOAD_DIR:-/volume1/vda_serwer}"
    PORT="${PORT:-8081}"
    VERBOSE="${VERBOSE:-0}"

    # Create config file
    mkdir -p "$(dirname "$CONF_FILE")"
    cat > "$CONF_FILE" << EOF
DOWNLOAD_DIR="$DOWNLOAD_DIR"
PORT="$PORT"
VERBOSE="$VERBOSE"
EOF

    echo "Configuration saved successfully"
}

# Get status
get_status() {
    load_config
    if [ -f "$START_STOP_SCRIPT" ]; then
        if "$START_STOP_SCRIPT" status > /dev/null 2>&1; then
            echo "{\"status\":\"running\",\"port\":\"$PORT\",\"download_dir\":\"$DOWNLOAD_DIR\"}"
        else
            echo "{\"status\":\"stopped\",\"port\":\"$PORT\",\"download_dir\":\"$DOWNLOAD_DIR\"}"
        fi
    else
        echo "{\"status\":\"error\",\"message\":\"Script not found\"}"
    fi
}

# Start service
start_service() {
    if [ -f "$START_STOP_SCRIPT" ]; then
        "$START_STOP_SCRIPT" start
        echo "Service started"
    else
        echo "Error: Script not found"
    fi
}

# Stop service
stop_service() {
    if [ -f "$START_STOP_SCRIPT" ]; then
        "$START_STOP_SCRIPT" stop
        echo "Service stopped"
    else
        echo "Error: Script not found"
    fi
}

# Restart service
restart_service() {
    stop_service
    sleep 2
    start_service
    echo "Service restarted"
}

# Get logs
get_logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -n 100 "$LOG_FILE"
    else
        echo "No logs available"
    fi
}

# Clear logs
clear_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo "" > "$LOG_FILE"
        echo "Logs cleared"
    else
        echo "No logs to clear"
    fi
}

# Main command handling
case "$1" in
    get_status) get_status ;;
    start_service) start_service ;;
    stop_service) stop_service ;;
    restart_service) restart_service ;;
    save_config) save_config ;;
    get_logs) get_logs ;;
    clear_logs) clear_logs ;;
    *) echo "Unknown command: $1" ;;
esac

exit 0
