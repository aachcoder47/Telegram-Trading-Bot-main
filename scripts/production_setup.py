"""
Production Deployment Setup Script
Prepares the system for production deployment
"""

import os
import sys
from pathlib import Path
import shutil
from datetime import datetime


def create_directories():
    """Create required production directories"""
    dirs = [
        "./output/logs",
        "./output/media",
        "./output/wallets",
        "./output/backups",
        "./output/config"
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created: {dir_path}")


def setup_file_permissions():
    """Set secure file permissions"""
    import stat
    
    # Wallets directory: 700 (rwx------)
    wallet_dir = Path("./output/wallets")
    if wallet_dir.exists():
        os.chmod(wallet_dir, stat.S_IRWXU)  # 700
    
    # Database file: 600 (rw-------)
    db_path = Path("./tg_users.db")
    if db_path.exists():
        os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR)  # 600
    
    # Config file: 600
    env_file = Path("./.env")
    if env_file.exists():
        os.chmod(env_file, stat.S_IRUSR | stat.S_IWUSR)  # 600
    
    print("✓ File permissions secured")


def create_backup_schedule():
    """Create backup directory and document backup strategy"""
    backup_dir = Path("./output/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    backup_script = """#!/bin/bash
# Daily backup script
# Add to crontab: 0 2 * * * /path/to/backup.sh

BACKUP_DIR="./output/backups"
DB_FILE="./tg_users.db"
WALLET_DIR="./output/wallets"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Backup database
cp $DB_FILE "$BACKUP_DIR/tg_users_$TIMESTAMP.db.bak"

# Backup wallets
tar -czf "$BACKUP_DIR/wallets_$TIMESTAMP.tar.gz" $WALLET_DIR

# Keep only last 30 days of backups
find $BACKUP_DIR -name "*.bak" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $TIMESTAMP"
"""
    
    backup_file = backup_dir / "backup.sh"
    backup_file.write_text(backup_script)
    os.chmod(backup_file, 0o755)
    
    print("✓ Backup script created: ./output/backups/backup.sh")


def create_monitoring_config():
    """Create health check and monitoring configuration"""
    health_check = """#!/bin/bash
# Health check script for production monitoring

API_URL="http://localhost:5000/health"
LOG_FILE="./output/logs/health.log"

response=$(curl -s -o /dev/null -w "%{http_code}" $API_URL)

if [ "$response" = "200" ]; then
    echo "$(date) - API OK" >> $LOG_FILE
else
    echo "$(date) - API DOWN (HTTP $response)" >> $LOG_FILE
    # Send alert (email, Slack, etc.)
fi
"""
    
    health_file = Path("./output/health_check.sh")
    health_file.write_text(health_check)
    os.chmod(health_file, 0o755)
    
    print("✓ Health check script created")


def create_environment_template():
    """Create .env.template file"""
    template = """.env.template - Production Environment Configuration
======================================================

# Telegram API
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
SESSION_NAME=tg_trading_bot

# Mistral AI
MISTRAL_API_KEY=your_mistral_api_key
MISTRAL_MODEL=mistral-large-latest
MISTRAL_TIMEOUT_SECS=299

# Exchange Configuration (choose one: 'xt' or 'bitunix')
EXCHANGE=xt

# XT Exchange
XT_API_KEY=your_xt_api_key
XT_SECRET=your_xt_secret
XT_PASSWORD=your_xt_password
XT_MARGIN_MODE=cross

# Bitunix Exchange
BITUNIX_API_KEY=your_bitunix_api_key
BITUNIX_SECRET=your_bitunix_secret
BITUNIX_BASE_URL=https://fapi.bitunix.com

# Trading bot configuration
FEE_WALLET_ADDRESS=bc1qdw7cav7z9l2675fslaupjxu4ugdn2lz5x8q5e7
FEE_PERCENTAGE=5.0
MIN_DEPOSIT_USD=50.0
ORDER_QUOTE=USDT
ORDER_NOTIONAL=10.0

# Database
DB_PATH=./tg_users.db

# Logging
LOG_LEVEL=INFO
LOG_FILE=./output/logs/bot.log
LOG_BACKUP_COUNT=30

# Channels (JSON format)
CHANNELS_CONFIG=[{"channel_id":"123456789","channel_title":"Trading Signals","policy":"single_message","enabled":true}]

# Proxy (optional)
PROXY_TYPE=
PROXY_HOST=
PROXY_PORT=

# Image Upload Service
UPLOAD_BASE=http://localhost:8080
"""
    
    template_file = Path(".env.template")
    template_file.write_text(template)
    
    print("✓ Environment template created: .env.template")


def create_docker_config():
    """Create Docker configuration for containerization"""
    dockerfile = """FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    libssl-dev \\
    libffi-dev \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create necessary directories
RUN mkdir -p output/logs output/media output/wallets output/backups

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:5000/health || exit 1

# Expose API port
EXPOSE 5000

# Run the API server
CMD ["python", "cmd/server/api_server.py"]
"""
    
    docker_file = Path("Dockerfile")
    docker_file.write_text(dockerfile)
    
    docker_compose = """version: '3.8'

services:
  trading-bot:
    build: .
    container_name: trading-bot-api
    ports:
      - "5000:5000"
    volumes:
      - ./output:/app/output
      - ./.env:/app/.env:ro
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
"""
    
    compose_file = Path("docker-compose.yml")
    compose_file.write_text(docker_compose)
    
    print("✓ Docker configuration created")


def create_systemd_service():
    """Create systemd service file for Linux deployments"""
    service = """[Unit]
Description=Trading Bot API Service
After=network.target

[Service]
Type=simple
User=trading-bot
WorkingDirectory=/home/trading-bot/trading-bot
Environment="PATH=/home/trading-bot/venv/bin"
ExecStart=/home/trading-bot/venv/bin/python cmd/server/api_server.py
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/trading-bot/api.log
StandardError=append:/var/log/trading-bot/api.log

[Install]
WantedBy=multi-user.target
"""
    
    service_file = Path("trading-bot-api.service")
    service_file.write_text(service)
    
    print("✓ Systemd service file created: trading-bot-api.service")


def create_nginx_config():
    """Create nginx reverse proxy configuration"""
    nginx_conf = """upstream trading_bot_api {
    server localhost:5000;
}

server {
    listen 80;
    server_name trading-bot.example.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name trading-bot.example.com;
    
    # SSL certificates (e.g., from Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/trading-bot.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/trading-bot.example.com/privkey.pem;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req zone=api_limit burst=20 nodelay;
    
    location / {
        proxy_pass http://trading_bot_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
"""
    
    nginx_file = Path("nginx.conf.example")
    nginx_file.write_text(nginx_conf)
    
    print("✓ Nginx configuration created: nginx.conf.example")


def create_requirements_pinned():
    """Create requirements-prod.txt with pinned versions"""
    requirements = """# Pinned versions for production
telethon==1.32.0
ccxt==4.0.60
python-dotenv==1.0.0
requests==2.31.0
mistralai==0.0.11
bitcoinlib==0.6.14
web3==6.11.3
pydantic==2.5.0
sqlalchemy==2.0.23
argon2-cffi==23.1.0
pycryptodome==3.19.0
flask==3.0.0
pytest==7.4.3
gunicorn==21.2.0
"""
    
    req_file = Path("requirements-prod.txt")
    req_file.write_text(requirements)
    
    print("✓ Production requirements file created: requirements-prod.txt")


def main():
    """Run production setup"""
    print("\n" + "=" * 60)
    print("TRADING BOT - PRODUCTION SETUP")
    print("=" * 60 + "\n")
    
    try:
        create_directories()
        setup_file_permissions()
        create_backup_schedule()
        create_monitoring_config()
        create_environment_template()
        create_docker_config()
        create_systemd_service()
        create_nginx_config()
        create_requirements_pinned()
        
        print("\n" + "=" * 60)
        print("✅ PRODUCTION SETUP COMPLETE")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Update .env with your actual API keys and configuration")
        print("2. Run: python -m pytest cmd/test/test_unit.py -v")
        print("3. Run: python internal/services/production_validator.py")
        print("4. Choose deployment method:")
        print("   - Docker: docker-compose up -d")
        print("   - Linux: sudo systemctl start trading-bot-api")
        print("   - Manual: gunicorn -w 4 cmd.server.api_server:app")
        print("\n" + "=" * 60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
