
#!/usr/bin/env bash
set -Eeuo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'
BOLD='\033[1m'

log_info() { echo -e "${CYAN}$1${NC}"; }
log_warn() { echo -e "${YELLOW}$1${NC}"; }
log_success() { echo -e "${GREEN}$1${NC}"; }
log_error() { echo -e "${RED}$1${NC}" >&2; }

on_error() {
    log_error "Ошибка на строке $1. Установка прервана."
}
trap 'on_error $LINENO' ERR

prompt() {
    local message="$1"
    local __var="$2"
    local value
    read -r -p "$message" value < /dev/tty
    printf -v "$__var" '%s' "$value"
}

confirm() {
    local message="$1"
    local reply
    read -r -n1 -p "$message" reply < /dev/tty || true
    echo
    [[ "$reply" =~ ^[Yy]$ ]]
}

sanitize_domain() {
    local input="$1"
    echo "$input" \
        | sed -e 's%^https\?://%%' -e 's%/.*$%%' \
        | tr -cd 'A-Za-z0-9.-' \
        | tr '[:upper:]' '[:lower:]'
}

get_server_ip() {
    local ipv4_re='^([0-9]{1,3}\.){3}[0-9]{1,3}$'
    local ip
    for url in \
        "https://api.ipify.org" \
        "https://ifconfig.co/ip" \
        "https://ipv4.icanhazip.com"; do
        ip=$(curl -fsS "$url" 2>/dev/null | tr -d '\r\n\t ')
        if [[ $ip =~ $ipv4_re ]]; then
            echo "$ip"
            return 0
        fi
    done
    ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    if [[ $ip =~ $ipv4_re ]]; then
        echo "$ip"
    fi
}

resolve_domain_ip() {
    local domain="$1"
    local ipv4_re='^([0-9]{1,3}\.){3}[0-9]{1,3}$'
    local ip
    ip=$(getent ahostsv4 "$domain" 2>/dev/null | awk '{print $1}' | head -n1)
    if [[ $ip =~ $ipv4_re ]]; then
        echo "$ip"
        return 0
    fi
    if command -v dig >/dev/null 2>&1; then
        ip=$(dig +short A "$domain" 2>/dev/null | grep -E "$ipv4_re" | head -n1)
        if [[ $ip =~ $ipv4_re ]]; then
            echo "$ip"
            return 0
        fi
    fi
    if command -v nslookup >/dev/null 2>&1; then
        ip=$(nslookup -type=A "$domain" 2>/dev/null | awk '/^Address: /{print $2; exit}')
        if [[ $ip =~ $ipv4_re ]]; then
            echo "$ip"
            return 0
        fi
    fi
    if command -v ping >/dev/null 2>&1; then
        ip=$(ping -4 -c1 -W1 "$domain" 2>/dev/null | sed -n 's/.*(\([0-9.]*\)).*/\1/p' | head -n1)
        if [[ $ip =~ $ipv4_re ]]; then
            echo "$ip"
            return 0
        fi
    fi
    return 1
}

ensure_packages() {
    log_info "\nШаг 1: проверка и установка системных зависимостей"
    declare -A packages=(
        [git]='git'
        [docker]='docker.io'
        [docker-compose]='docker-compose'
        [nginx]='nginx'
        [curl]='curl'
        [certbot]='certbot'
        [dig]='dnsutils'
    )
    local missing=()
    for cmd in "${!packages[@]}"; do
        # docker-compose-plugin (v2) satisfies the docker-compose requirement
        if [[ "$cmd" == "docker-compose" ]] && docker compose version >/dev/null 2>&1; then
            log_success "✔ docker compose (plugin v2) уже установлен."
            continue
        fi
        if ! command -v "$cmd" >/dev/null 2>&1; then
            log_warn "Утилита '$cmd' не найдена. Будет установлен пакет '${packages[$cmd]}'."
            missing+=("${packages[$cmd]}")
        else
            log_success "✔ $cmd уже установлен."
        fi
    done
    if ((${#missing[@]})); then
        # Настройка debconf для неинтерактивной установки
        export DEBIAN_FRONTEND=noninteractive
        export DEBCONF_NONINTERACTIVE_SEEN=true
        
        sudo apt-get update
        sudo apt-get install -y --no-install-recommends "${missing[@]}"
        
        # Сброс переменных после установки
        unset DEBIAN_FRONTEND
        unset DEBCONF_NONINTERACTIVE_SEEN
    else
        log_info "Все необходимые пакеты уже присутствуют."
    fi
}

ensure_services() {
    for service in docker nginx; do
        if ! sudo systemctl is-active --quiet "$service"; then
            log_warn "Сервис $service не запущен. Включаем и запускаем..."
            sudo systemctl enable "$service"
            sudo systemctl start "$service"
        else
            log_success "✔ Сервис $service активен."
        fi
    done
}

ensure_certbot_nginx() {
    log_info "\nПроверка плагина Certbot для Nginx"

    local has_nginx_plugin=0
    if command -v certbot >/dev/null 2>&1; then
        if certbot plugins 2>/dev/null | grep -qi 'nginx'; then
            has_nginx_plugin=1
        fi
    fi

    if [[ $has_nginx_plugin -eq 1 ]]; then
        log_success "✔ Плагин nginx для Certbot найден."
        return
    fi

    if command -v apt-get >/dev/null 2>&1; then
        log_info "Устанавливаю плагин python3-certbot-nginx (apt)..."
        # Настройка debconf для неинтерактивной установки
        export DEBIAN_FRONTEND=noninteractive
        export DEBCONF_NONINTERACTIVE_SEEN=true
        
        sudo apt-get update
        if sudo apt-get install -y --no-install-recommends python3-certbot-nginx; then
            if certbot plugins 2>/dev/null | grep -qi 'nginx'; then
                log_success "✔ Плагин nginx для Certbot установлен (apt)."
                unset DEBIAN_FRONTEND
                unset DEBCONF_NONINTERACTIVE_SEEN
                return
            fi
        else
            log_warn "Не удалось установить python3-certbot-nginx через apt."
        fi
        
        # Сброс переменных
        unset DEBIAN_FRONTEND
        unset DEBCONF_NONINTERACTIVE_SEEN
    fi

    log_warn "Пробую установить Certbot (snap) с поддержкой nginx."
    if ! command -v snap >/dev/null 2>&1; then
        # Настройка debconf для неинтерактивной установки
        export DEBIAN_FRONTEND=noninteractive
        export DEBCONF_NONINTERACTIVE_SEEN=true
        
        sudo apt-get update
        sudo apt-get install -y --no-install-recommends snapd
        
        # Сброс переменных
        unset DEBIAN_FRONTEND
        unset DEBCONF_NONINTERACTIVE_SEEN
    fi
    sudo snap install core || true
    sudo snap refresh core || true
    sudo snap install --classic certbot
    sudo ln -sf /snap/bin/certbot /usr/bin/certbot

    if certbot plugins 2>/dev/null | grep -qi 'nginx'; then
        log_success "✔ Плагин nginx для Certbot доступен (snap)."
        return
    fi

    log_error "Плагин nginx для Certbot недоступен. Невозможно продолжить выпуск сертификата с параметром --nginx."
    exit 1
}

configure_nginx() {
    local domain="$1"
    local port="$2"
    local nginx_conf="$3"
    local nginx_link="$4"

    log_info "\nШаг 4: настройка Nginx"
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo tee "$nginx_conf" >/dev/null <<EOF
limit_req_zone \$binary_remote_addr zone=xatabchik_login:10m rate=5r/m;

server {
    listen ${port} ssl http2;
    listen [::]:${port} ssl http2;
    server_name ${domain};

    ssl_certificate /etc/letsencrypt/live/${domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${domain}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;

    location = /login {
        limit_req zone=xatabchik_login burst=10 nodelay;
        proxy_pass http://127.0.0.1:1488;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:1488;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

    if [[ ! -L "$nginx_link" ]]; then
        sudo ln -s "$nginx_conf" "$nginx_link"
    fi
    sudo nginx -t
    sudo systemctl reload nginx
    log_success "✔ Конфигурация Nginx обновлена."
}

restrict_panel_firewall() {
    if ! command -v ufw >/dev/null 2>&1; then
        return 0
    fi
    if ! sudo ufw status | grep -q 'Status: active'; then
        return 0
    fi
    log_info "Панель слушает только 127.0.0.1:1488 — убираем публичный UFW 1488."
    sudo ufw delete allow 1488/tcp >/dev/null 2>&1 || true
    sudo ufw delete allow 1488 >/dev/null 2>&1 || true
}

REPO_URL="https://github.com/Xatabchik/Xatabchik.git"
PROJECT_DIR="xatabchik"
NGINX_CONF="/etc/nginx/sites-available/${PROJECT_DIR}.conf"
NGINX_LINK="/etc/nginx/sites-enabled/${PROJECT_DIR}.conf"

# Prefer standalone binary; fall back to V2 plugin
if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose)
else
    COMPOSE=(docker compose)
fi

log_success "--- Запуск скрипта установки/обновления Xatabchik ---"

if [[ -f "$NGINX_CONF" ]]; then
    log_info "\nОбнаружена существующая конфигурация. Запускается режим обновления."
    if [[ ! -d "$PROJECT_DIR" ]]; then
        log_error "Конфигурация Nginx найдена, но каталог '${PROJECT_DIR}' отсутствует. Удалите $NGINX_CONF и повторите установку."
        exit 1
    fi
    cd "$PROJECT_DIR"
    log_info "\nШаг 1: обновление исходного кода"
    git fetch --all
    git reset --hard "origin/$(git rev-parse --abbrev-ref HEAD)"
    log_success "✔ Репозиторий обновлён."
    log_info "\nШаг 2: пересборка и перезапуск контейнеров"
    restrict_panel_firewall
    sudo "${COMPOSE[@]}" down --remove-orphans
    sudo "${COMPOSE[@]}" up -d --build --force-recreate
    log_success "\n🎉 Обновление успешно завершено!"
    exit 0
fi

log_info "\nСуществующая конфигурация не найдена. Запускается новая установка."

ensure_packages
ensure_services
ensure_certbot_nginx

log_info "\nШаг 2: клонирование репозитория"
if [[ ! -d "$PROJECT_DIR/.git" ]]; then
    git clone "$REPO_URL" "$PROJECT_DIR"
else
    log_warn "Каталог $PROJECT_DIR уже существует. Будет использована текущая версия."
fi
cd "$PROJECT_DIR"
log_success "✔ Репозиторий Xatabchik готов."

log_info "\nШаг 3: настройка домена и SSL"

prompt "Введите ваш домен (например, my-vpn-shop.com): " USER_DOMAIN_INPUT
DOMAIN=$(sanitize_domain "$USER_DOMAIN_INPUT")
if [[ -z "$DOMAIN" ]]; then
    log_error "Некорректное доменное имя. Установка прервана."
    exit 1
fi

prompt "Введите email для Let's Encrypt: " EMAIL
if [[ -z "$EMAIL" ]]; then
    log_error "Email обязателен для выпуска сертификата."
    exit 1
fi

SERVER_IP=$(get_server_ip || true)
DOMAIN_IP=$(resolve_domain_ip "$DOMAIN" || true)

if [[ -n "$SERVER_IP" ]]; then
    log_info "IP сервера: ${SERVER_IP}"
else
    log_warn "Не удалось автоматически определить IP сервера."
fi

if [[ -n "$DOMAIN_IP" ]]; then
    log_info "IP домена ${DOMAIN}: ${DOMAIN_IP}"
else
    log_warn "Не удалось получить IP для домена ${DOMAIN}."
fi

if [[ -n "$SERVER_IP" && -n "$DOMAIN_IP" && "$SERVER_IP" != "$DOMAIN_IP" ]]; then
    log_warn "DNS-запись домена ${DOMAIN} не совпадает с IP этого сервера."
    if ! confirm "Продолжить установку? (y/n): "; then
        log_info "Установка прервана пользователем."
        exit 1
    fi
fi

if command -v ufw >/dev/null 2>&1 && sudo ufw status | grep -q 'Status: active'; then
    log_warn "Обнаружен активный UFW. Открываем порты 80, 443, 8443 (1488 только localhost)."
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw allow 8443/tcp
    restrict_panel_firewall
fi

if [[ -d "/etc/letsencrypt/live/${DOMAIN}" ]]; then
    log_success "✔ SSL-сертификаты для ${DOMAIN} уже существуют."
else
    log_info "Получение SSL-сертификатов для ${DOMAIN}..."
    # Создаём временный HTTP server block, чтобы certbot --nginx мог найти server_name
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo tee "$NGINX_CONF" >/dev/null <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};
}
EOF
    if [[ ! -L "$NGINX_LINK" ]]; then
        sudo ln -s "$NGINX_CONF" "$NGINX_LINK"
    fi
    sudo nginx -t && sudo systemctl reload nginx
    sudo certbot --nginx -d "$DOMAIN" --email "$EMAIL" --agree-tos --non-interactive --redirect
    log_success "✔ Сертификаты Let's Encrypt успешно получены."
fi

prompt "Какой порт использовать для вебхуков YooKassa? (443 или 8443, по умолчанию 8443): " YOOKASSA_PORT_INPUT
YOOKASSA_PORT="${YOOKASSA_PORT_INPUT:-8443}"
if [[ "$YOOKASSA_PORT" != "443" && "$YOOKASSA_PORT" != "8443" ]]; then
    log_warn "Указан неподдерживаемый порт. Будет использован 8443."
    YOOKASSA_PORT=8443
fi

configure_nginx "$DOMAIN" "$YOOKASSA_PORT" "$NGINX_CONF" "$NGINX_LINK"

log_info "\nШаг 5: сборка и запуск Docker-контейнеров"
if [[ -n "$(sudo "${COMPOSE[@]}" ps -q 2>/dev/null)" ]]; then
    sudo "${COMPOSE[@]}" down
fi
sudo "${COMPOSE[@]}" up -d --build

cat <<SUMMARY

${GREEN}┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓${NC}
${GREEN}┃${NC}  🎉 ${BOLD}Установка Xatabchik завершена!${NC} 🎉                ${GREEN}┃${NC}
${GREEN}┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛${NC}

${BOLD}Веб‑панель:${NC}
  ${YELLOW}https://${DOMAIN}:${YOOKASSA_PORT}/login${NC}

${BOLD}Данные для первого входа:${NC}
  Логин:  ${CYAN}admin${NC}
  Пароль: ${CYAN}admin${NC}

${YELLOW}⚠️  Обязательно измените пароль после первого входа.${NC}

${BOLD}URL вебхука YooKassa:${NC}
  ${YELLOW}https://${DOMAIN}:${YOOKASSA_PORT}/yookassa-webhook${NC}

SUMMARY
