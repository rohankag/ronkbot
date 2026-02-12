#!/bin/bash

# ronkbot Interactive Installer
# One-command setup for ronkbot personal AI assistant

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Configuration
INSTALL_DIR="${INSTALL_DIR:-$HOME/.ronkbot}"
REPO_URL="https://github.com/rohankag/ronkbot.git"
VERSION="1.0.0"

# ═══════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════

print_header() {
    clear
    echo ""
    echo "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo "${CYAN}║${NC}                                                        ${CYAN}║${NC}"
    echo "${CYAN}║${NC}   🤖 ${BOLD}ronkbot${NC} - Personal AI Assistant Installer        ${CYAN}║${NC}"
    echo "${CYAN}║${NC}                                                        ${CYAN}║${NC}"
    echo "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo ""
    echo "${BLUE}▶${NC} ${BOLD}$1${NC}"
    echo "─────────────────────────────────────────────────────"
}

print_success() {
    echo "${GREEN}✓${NC} $1"
}

print_error() {
    echo "${RED}✗${NC} $1"
}

print_warning() {
    echo "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo "${CYAN}ℹ${NC} $1"
}

# Spinner for long operations
spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='|/-\'
    while kill -0 $pid 2>/dev/null; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

# ═══════════════════════════════════════════════════════════════
# PREREQUISITE CHECKS
# ═══════════════════════════════════════════════════════════════

check_prerequisites() {
    print_step "Checking Prerequisites"
    
    local missing=()
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        missing+=("Docker")
    else
        print_success "Docker installed"
    fi
    
    # Check Docker Compose
    if ! docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
        missing+=("Docker Compose")
    else
        print_success "Docker Compose installed"
    fi
    
    # Check Git
    if ! command -v git &> /dev/null; then
        missing+=("Git")
    else
        print_success "Git installed"
    fi
    
    # Check curl
    if ! command -v curl &> /dev/null; then
        missing+=("curl")
    else
        print_success "curl installed"
    fi
    
    if [ ${#missing[@]} -ne 0 ]; then
        print_error "Missing prerequisites: ${missing[*]}"
        echo ""
        echo "Please install the missing tools:"
        echo "  • Docker Desktop: https://www.docker.com/products/docker-desktop"
        echo "  • Git: https://git-scm.com/downloads"
        echo ""
        exit 1
    fi
    
    print_success "All prerequisites met!"
}

# ═══════════════════════════════════════════════════════════════
# TELEGRAM BOT SETUP
# ═══════════════════════════════════════════════════════════════

setup_telegram() {
    print_step "Telegram Bot Configuration"
    
    echo ""
    echo "${BOLD}Option A:${NC} Create new bot (recommended)"
    echo "${BOLD}Option B:${NC} Use existing bot"
    echo ""
    read -p "Select option (A/B): " telegram_option
    
    case ${telegram_option^^} in
        A)
            setup_telegram_new
            ;;
        B)
            setup_telegram_existing
            ;;
        *)
            print_warning "Invalid option, defaulting to create new bot"
            setup_telegram_new
            ;;
    esac
}

setup_telegram_new() {
    echo ""
    print_info "I'll guide you through creating a Telegram bot"
    echo ""
    echo "${BOLD}Step 1:${NC} Opening @BotFather in Telegram..."
    
    # Try to open Telegram
    if command -v open &> /dev/null; then
        open "https://t.me/BotFather" 2>/dev/null || true
    elif command -v xdg-open &> /dev/null; then
        xdg-open "https://t.me/BotFather" 2>/dev/null || true
    fi
    
    echo ""
    echo "${BOLD}Instructions:${NC}"
    echo "  1. Click the link above or search @BotFather in Telegram"
    echo "  2. Send: /newbot"
    echo "  3. Enter bot name (displayed to users)"
    echo "  4. Enter bot username (must end in _bot, e.g., mybot_bot)"
    echo "  5. Copy the HTTP API token"
    echo ""
    
    while true; do
        read -p "Enter your bot token: " telegram_token
        
        if [[ $telegram_token =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]]; then
            print_success "Token format looks valid"
            break
        else
            print_error "Invalid token format. Should be like: 123456789:ABCdefGHI..."
            echo "Please try again."
        fi
    done
    
    # Extract bot info from token (optional validation)
    TELEGRAM_BOT_TOKEN="$telegram_token"
    TELEGRAM_BOT_NAME="ronkbot"
    
    echo ""
    read -p "Enter your Telegram username (without @): " telegram_username
    TELEGRAM_OWNER_USERNAME="$telegram_username"
    
    print_success "Telegram bot configured!"
}

setup_telegram_existing() {
    echo ""
    read -p "Enter your existing bot token: " telegram_token
    TELEGRAM_BOT_TOKEN="$telegram_token"
    
    read -p "Enter your Telegram username (without @): " telegram_username
    TELEGRAM_OWNER_USERNAME="$telegram_username"
    
    TELEGRAM_BOT_NAME="ronkbot"
    
    print_success "Existing bot configured!"
}

# ═══════════════════════════════════════════════════════════════
# GEMINI API SETUP
# ═══════════════════════════════════════════════════════════════

setup_gemini() {
    print_step "AI Configuration (Google Gemini)"
    
    echo ""
    echo "ronkbot uses Google Gemini for smart AI responses."
    echo ""
    echo "${BOLD}Get your API key:${NC}"
    echo "  1. Visit: https://ai.google.dev/"
    echo "  2. Sign in with your Google account"
    echo "  3. Click 'Get API Key'"
    echo "  4. Create a new key"
    echo ""
    
    # Try to open browser
    if command -v open &> /dev/null; then
        open "https://ai.google.dev/" 2>/dev/null || true
    elif command -v xdg-open &> /dev/null; then
        xdg-open "https://ai.google.dev/" 2>/dev/null || true
    fi
    
    while true; do
        read -p "Enter your Gemini API key: " gemini_key
        
        if [[ $gemini_key =~ ^AIza[0-9A-Za-z_-]{35,}$ ]]; then
            print_success "API key format looks valid"
            break
        else
            print_warning "API key format looks unusual. Continue anyway? (Y/n)"
            read -p "" confirm
            if [[ ${confirm^^} != "N" ]]; then
                break
            fi
        fi
    done
    
    GEMINI_API_KEY="$gemini_key"
    GEMINI_MODEL="gemini-3-flash"
    
    print_success "AI configured!"
}

# ═══════════════════════════════════════════════════════════════
# GMAIL OAUTH SETUP
# ═══════════════════════════════════════════════════════════════

setup_gmail() {
    print_step "Gmail Integration (Optional)"
    
    echo ""
    echo "ronkbot can read and send emails via Gmail."
    echo "This is optional - you can skip this and add it later."
    echo ""
    read -p "Setup Gmail integration now? (Y/n): " setup_gmail
    
    if [[ ${setup_gmail^^} == "N" ]]; then
        print_info "Skipping Gmail setup. You can configure it later with: ronkbot config"
        GMAIL_SETUP="false"
        return
    fi
    
    echo ""
    print_info "Setting up Gmail OAuth..."
    echo ""
    echo "${BOLD}You'll need to:${NC}"
    echo "  1. Go to Google Cloud Console"
    echo "  2. Create a project"
    echo "  3. Enable Gmail API"
    echo "  4. Create OAuth credentials"
    echo ""
    echo "${CYAN}Don't worry, I'll open the right pages for you!${NC}"
    echo ""
    read -p "Press Enter to open Google Cloud Console..."
    
    # Open Google Cloud Console
    if command -v open &> /dev/null; then
        open "https://console.cloud.google.com/" 2>/dev/null || true
    elif command -v xdg-open &> /dev/null; then
        xdg-open "https://console.cloud.google.com/" 2>/dev/null || true
    fi
    
    echo ""
    echo "${BOLD}Step-by-step instructions:${NC}"
    echo ""
    echo "${YELLOW}1. Create Project:${NC}"
    echo "   • Click project dropdown (top left)"
    echo "   • Click 'New Project'"
    echo "   • Name: ronkbot-email"
    echo "   • Click 'Create'"
    echo ""
    
    echo "${YELLOW}2. Enable Gmail API:${NC}"
    echo "   • Go to 'APIs & Services' → 'Library'"
    echo "   • Search 'Gmail API'"
    echo "   • Click 'Enable'"
    echo ""
    
    echo "${YELLOW}3. Configure OAuth:${NC}"
    echo "   • Go to 'OAuth consent screen'"
    echo "   • Select 'External'"
    echo "   • App name: ronkbot"
    echo "   • User support email: your email"
    echo "   • Developer contact: your email"
    echo "   • Click 'Save and Continue'"
    echo ""
    
    read -p "Press Enter when you've completed the OAuth consent screen..."
    
    echo ""
    echo "${YELLOW}4. Create Credentials:${NC}"
    echo "   • Go to 'Credentials'"
    echo "   • Click 'Create Credentials' → 'OAuth client ID'"
    echo "   • Application type: 'Desktop app'"
    echo "   • Name: ronkbot-desktop"
    echo "   • Click 'Create'"
    echo "   • Click 'Download JSON'"
    echo ""
    
    read -p "Press Enter when you've downloaded the credentials file..."
    
    # Ask for path to credentials file
    while true; do
        read -p "Enter path to downloaded credentials JSON: " creds_path
        
        if [ -f "$creds_path" ]; then
            # Extract client_id and client_secret
            GMAIL_CLIENT_ID=$(grep -o '"client_id":"[^"]*"' "$creds_path" | cut -d'"' -f4)
            GMAIL_CLIENT_SECRET=$(grep -o '"client_secret":"[^"]*"' "$creds_path" | cut -d'"' -f4)
            
            if [ -n "$GMAIL_CLIENT_ID" ] && [ -n "$GMAIL_CLIENT_SECRET" ]; then
                print_success "Credentials extracted!"
                break
            fi
        fi
        
        print_error "Could not read credentials file. Please check the path."
    done
    
    GMAIL_SETUP="true"
    print_success "Gmail OAuth configured!"
}

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION FILE GENERATION
# ═══════════════════════════════════════════════════════════════

generate_config() {
    print_step "Generating Configuration"
    
    local config_file="$INSTALL_DIR/.env"
    
    # Generate secure random password for n8n
    local n8n_password
    if command -v openssl &> /dev/null; then
        n8n_password=$(openssl rand -base64 24 | tr -d '\n')
    else
        n8n_password=$(head /dev/urandom | LC_ALL=C tr -dc A-Za-z0-9 | head -c 32)
    fi
    
    cat > "$config_file" << EOF
# ronkbot Configuration File
# Generated on $(date)

# ═══════════════════════════════════════════════════════════════
# TELEGRAM BOT CONFIGURATION
# ═══════════════════════════════════════════════════════════════
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
TELEGRAM_BOT_NAME=$TELEGRAM_BOT_NAME
TELEGRAM_OWNER_USERNAME=$TELEGRAM_OWNER_USERNAME

# ═══════════════════════════════════════════════════════════════
# GEMINI API CONFIGURATION
# ═══════════════════════════════════════════════════════════════
GEMINI_API_KEY=$GEMINI_API_KEY
GEMINI_MODEL=gemini-3-flash

# ═══════════════════════════════════════════════════════════════
# N8N SECURITY
# ═══════════════════════════════════════════════════════════════
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=$n8n_password
N8N_PORT=5678

# ═══════════════════════════════════════════════════════════════
# DATABASE CONFIGURATION
# ═══════════════════════════════════════════════════════════════
DB_TYPE=sqlite
DB_SQLITE_PATH=/home/node/.n8n/database/ronkbot.db

# ═══════════════════════════════════════════════════════════════
# BOT PERSONALITY
# ═══════════════════════════════════════════════════════════════
BOT_PERSONALITY=conversational_warm
BOT_NAME=ronkbot

# ═══════════════════════════════════════════════════════════════
# SYSTEM ACCESS (SECURITY)
# ═══════════════════════════════════════════════════════════════
ALLOWED_DIRECTORIES=$HOME/Documents,$HOME/Projects,$HOME/Downloads
ALLOWED_COMMANDS=df,du,git,ls,cat,ps,top,whoami,pwd,date,cal,echo,head,tail,wc,find,grep

# ═══════════════════════════════════════════════════════════════
# GMAIL INTEGRATION (OPTIONAL)
# ═══════════════════════════════════════════════════════════════
EOF

    if [ "$GMAIL_SETUP" == "true" ]; then
        cat >> "$config_file" << EOF
GMAIL_ENABLED=true
GMAIL_CLIENT_ID=$GMAIL_CLIENT_ID
GMAIL_CLIENT_SECRET=$GMAIL_CLIENT_SECRET
GMAIL_REDIRECT_URI=http://localhost:5678/gmail-auth
GMAIL_ACCESS_TOKEN=
GMAIL_REFRESH_TOKEN=
EOF
    else
        cat >> "$config_file" << EOF
GMAIL_ENABLED=false
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
EOF
    fi
    
    chmod 600 "$config_file"
    print_success "Configuration saved to $config_file"
}

# ═══════════════════════════════════════════════════════════════
# INSTALLATION
# ═══════════════════════════════════════════════════════════════

install_ronkbot() {
    print_step "Installing ronkbot"
    
    # Clone repository
    if [ -d "$INSTALL_DIR" ]; then
        print_warning "Directory $INSTALL_DIR already exists"
        read -p "Overwrite? (y/N): " overwrite
        if [[ ${overwrite^^} == "Y" ]]; then
            rm -rf "$INSTALL_DIR"
        else
            print_error "Installation cancelled"
            exit 1
        fi
    fi
    
    echo "Cloning repository..."
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR" &
    spinner $!
    
    print_success "Repository cloned"
    
    # Create data directories
    mkdir -p "$INSTALL_DIR/data/n8n"
    mkdir -p "$INSTALL_DIR/data/sqlite"
    chmod 755 "$INSTALL_DIR/data"
    
    # Generate config
    cd "$INSTALL_DIR"
    generate_config
    
    # Create CLI symlink
    create_cli_symlink
    
    print_success "Installation complete!"
}

# ═══════════════════════════════════════════════════════════════
# CLI SETUP
# ═══════════════════════════════════════════════════════════════

create_cli_symlink() {
    local cli_source="$INSTALL_DIR/bin/ronkbot"
    local cli_target="/usr/local/bin/ronkbot"
    
    # Create CLI script
    mkdir -p "$INSTALL_DIR/bin"
    
    cat > "$cli_source" << 'EOF'
#!/bin/bash
# ronkbot CLI

INSTALL_DIR="${INSTALL_DIR:-$HOME/.ronkbot}"

show_help() {
    cat << 'HELP'
🤖 ronkbot - Personal AI Assistant

USAGE:
    ronkbot <command> [options]

COMMANDS:
    start           Start ronkbot
    stop            Stop ronkbot
    restart         Restart ronkbot
    status          Check if ronkbot is running
    logs            View logs (follow mode)
    config          Re-run configuration wizard
    update          Update to latest version
    backup          Backup data and configuration
    restore         Restore from backup
    doctor          Run diagnostics
    reset           Factory reset (WARNING: deletes all data!)
    help            Show this help message

EXAMPLES:
    ronkbot start              # Start the bot
    ronkbot logs               # Follow logs
    ronkbot config             # Reconfigure settings
    ronkbot backup             # Create backup

HELP
}

cmd_start() {
    cd "$INSTALL_DIR"
    if docker compose ps 2>/dev/null | grep -q "Up"; then
        echo "✓ ronkbot is already running"
        echo "  Web UI: http://localhost:5678"
        return 0
    fi
    
    echo "🚀 Starting ronkbot..."
    docker compose up -d
    
    # Wait for startup
    echo "⏳ Waiting for services to start..."
    for i in {1..30}; do
        if curl -s http://localhost:5678/healthz > /dev/null 2>&1; then
            echo ""
            echo "✅ ronkbot is running!"
            echo ""
            echo "📱 Access your bot on Telegram"
            echo "🌐 Web Interface: http://localhost:5678"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    
    echo ""
    echo "⚠️  ronkbot is still starting. Check logs with: ronkbot logs"
}

cmd_stop() {
    cd "$INSTALL_DIR"
    echo "🛑 Stopping ronkbot..."
    docker compose stop
    echo "✓ ronkbot stopped"
}

cmd_restart() {
    cmd_stop
    sleep 2
    cmd_start
}

cmd_status() {
    cd "$INSTALL_DIR"
    if docker compose ps 2>/dev/null | grep -q "Up"; then
        echo "✅ ronkbot is running"
        echo ""
        docker compose ps
        echo ""
        echo "🌐 Web Interface: http://localhost:5678"
    else
        echo "⚠️  ronkbot is not running"
        echo "   Start with: ronkbot start"
    fi
}

cmd_logs() {
    cd "$INSTALL_DIR"
    echo "📋 Showing logs (Ctrl+C to exit)..."
    docker compose logs -f
}

cmd_config() {
    echo "⚙️  Running configuration wizard..."
    cd "$INSTALL_DIR"
    ./install.sh --reconfigure
}

cmd_update() {
    echo "⬆️  Updating ronkbot..."
    cd "$INSTALL_DIR"
    
    # Backup first
    cmd_backup
    
    # Pull latest code
    git pull origin main
    
    # Pull latest Docker images
    docker compose pull
    
    # Restart
    cmd_restart
    
    echo "✅ Update complete!"
}

cmd_backup() {
    local backup_dir="$INSTALL_DIR/backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    
    echo "💾 Creating backup..."
    
    # Backup config
    cp "$INSTALL_DIR/.env" "$backup_dir/" 2>/dev/null || true
    
    # Backup database
    if [ -f "$INSTALL_DIR/data/sqlite/ronkbot.db" ]; then
        cp "$INSTALL_DIR/data/sqlite/ronkbot.db" "$backup_dir/"
    fi
    
    # Backup workflows
    cp -r "$INSTALL_DIR/n8n-workflows" "$backup_dir/" 2>/dev/null || true
    
    echo "✅ Backup created: $backup_dir"
}

cmd_restore() {
    echo "Available backups:"
    ls -1td "$INSTALL_DIR/backups"/* 2>/dev/null | head -10 | nl
    echo ""
    read -p "Enter backup number to restore: " backup_num
    
    local backup_dir
    backup_dir=$(ls -1td "$INSTALL_DIR/backups"/* 2>/dev/null | sed -n "${backup_num}p")
    
    if [ -z "$backup_dir" ]; then
        echo "❌ Invalid backup number"
        exit 1
    fi
    
    echo "⚠️  This will overwrite current data!"
    read -p "Continue? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        echo "Cancelled"
        exit 0
    fi
    
    # Stop bot
    cmd_stop
    
    # Restore files
    cp "$backup_dir/.env" "$INSTALL_DIR/" 2>/dev/null || true
    cp "$backup_dir/ronkbot.db" "$INSTALL_DIR/data/sqlite/" 2>/dev/null || true
    cp -r "$backup_dir/n8n-workflows/"* "$INSTALL_DIR/n8n-workflows/" 2>/dev/null || true
    
    echo "✅ Restore complete!"
    echo "Start with: ronkbot start"
}

cmd_doctor() {
    echo "🔍 Running diagnostics..."
    
    local issues=0
    
    # Check Docker
    if docker version &>/dev/null; then
        echo "✓ Docker is running"
    else
        echo "✗ Docker is not running"
        ((issues++))
    fi
    
    # Check config
    if [ -f "$INSTALL_DIR/.env" ]; then
        echo "✓ Configuration file exists"
    else
        echo "✗ Configuration file missing"
        ((issues++))
    fi
    
    # Check data directory
    if [ -d "$INSTALL_DIR/data" ]; then
        echo "✓ Data directory exists"
    else
        echo "✗ Data directory missing"
        ((issues++))
    fi
    
    # Check if running
    if docker compose -f "$INSTALL_DIR/docker-compose.yml" ps 2>/dev/null | grep -q "Up"; then
        echo "✓ ronkbot is running"
    else
        echo "⚠ ronkbot is not running (start with: ronkbot start)"
    fi
    
    echo ""
    if [ $issues -eq 0 ]; then
        echo "✅ All checks passed!"
    else
        echo "⚠️  Found $issues issue(s). Run: ronkbot config"
    fi
}

cmd_reset() {
    echo "⚠️  WARNING: This will delete all data and configuration!"
    read -p "Type 'DELETE' to confirm: " confirm
    
    if [ "$confirm" != "DELETE" ]; then
        echo "Cancelled"
        exit 0
    fi
    
    cmd_stop
    rm -rf "$INSTALL_DIR"
    rm -f "/usr/local/bin/ronkbot"
    
    echo "✅ ronkbot has been completely removed"
}

# Main command dispatcher
case "${1:-help}" in
    start) cmd_start ;;
    stop) cmd_stop ;;
    restart) cmd_restart ;;
    status) cmd_status ;;
    logs) cmd_logs ;;
    config) cmd_config ;;
    update) cmd_update ;;
    backup) cmd_backup ;;
    restore) cmd_restore ;;
    doctor) cmd_doctor ;;
    reset) cmd_reset ;;
    help|--help|-h) show_help ;;
    *) echo "Unknown command: $1"; show_help; exit 1 ;;
esac
EOF

    chmod +x "$cli_source"
    
    # Create symlink (may require sudo)
    if [ -w "/usr/local/bin" ]; then
        ln -sf "$cli_source" "$cli_target"
        print_success "CLI installed: ronkbot command available"
    else
        print_warning "Need sudo to install ronkbot command globally"
        sudo ln -sf "$cli_source" "$cli_target"
        print_success "CLI installed with sudo: ronkbot command available"
    fi
}

# ═══════════════════════════════════════════════════════════════
# MAIN INSTALLATION FLOW
# ═══════════════════════════════════════════════════════════════

main() {
    print_header
    
    echo "${BOLD}Welcome to ronkbot installer!${NC}"
    echo ""
    echo "This wizard will guide you through setting up your personal"
    echo "AI assistant that runs on your Mac and responds to Telegram."
    echo ""
    echo "${CYAN}Estimated time: 5-10 minutes${NC}"
    echo ""
    read -p "Press Enter to continue..."
    
    # Check prerequisites
    check_prerequisites
    
    # Setup components
    setup_telegram
    setup_gemini
    setup_gmail
    
    # Install
    install_ronkbot
    
    # Success message
    print_header
    echo ""
    echo "${GREEN}${BOLD}🎉 Installation Complete!${NC}"
    echo ""
    echo "${BOLD}Your ronkbot is ready to use:${NC}"
    echo ""
    echo "  🤖 Telegram Bot: @$TELEGRAM_BOT_NAME"
    echo "  🌐 Web Interface: http://localhost:5678"
    echo "  📁 Installation: $INSTALL_DIR"
    echo ""
    echo "${BOLD}Quick Start:${NC}"
    echo "  • Start:    ${CYAN}ronkbot start${NC}"
    echo "  • Stop:     ${CYAN}ronkbot stop${NC}"
    echo "  • Status:   ${CYAN}ronkbot status${NC}"
    echo "  • Logs:     ${CYAN}ronkbot logs${NC}"
    echo "  • Help:     ${CYAN}ronkbot help${NC}"
    echo ""
    echo "${BOLD}Try these commands in Telegram:${NC}"
    echo "  • Hello!"
    echo "  • /help"
    echo "  • /status"
    echo ""
    echo "${YELLOW}Documentation:${NC} https://github.com/rohankag/ronkbot"
    echo ""
    
    # Ask to start now
    read -p "Start ronkbot now? (Y/n): " start_now
    if [[ ${start_now^^} != "N" ]]; then
        ronkbot start
    fi
}

# Handle --reconfigure flag
if [ "${1:-}" == "--reconfigure" ]; then
    INSTALL_DIR="${INSTALL_DIR:-$HOME/.ronkbot}"
    cd "$INSTALL_DIR" 2>/dev/null || {
        echo "Error: ronkbot not installed at $INSTALL_DIR"
        exit 1
    }
    
    setup_telegram
    setup_gemini
    setup_gmail
    generate_config
    
    echo ""
    echo "✅ Configuration updated!"
    echo "Restart with: ronkbot restart"
    exit 0
fi

# Run main installation
main
