# Telegram Trading Bot - Deployment Guide

## Hosting Options

### 1. Local Machine (Development)
```bash
# Install dependencies
pip install -r requirements.txt

# Configure .env file
cp .env.example .env
# Edit .env with your credentials

# Run the bot
python app.py
```

### 2. VPS/Cloud Server (Recommended for Production)

#### Using a VPS Provider (DigitalOcean, Linode, Vultr, etc.)

**Step 1: Get a VPS**
- Choose a VPS with at least 1GB RAM, 1 CPU
- Ubuntu 22.04 or 20.04 recommended
- Cost: ~$5-10/month

**Step 2: Connect to VPS**
```bash
ssh root@your_vps_ip
```

**Step 3: Install Dependencies**
```bash
# Update system
apt update && apt upgrade -y

# Install Python and pip
apt install python3 python3-pip python3-venv git -y

# Clone repository
git clone <your-repo-url>
cd Telegram-Trading-Bot-main

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Step 4: Configure Environment**
```bash
# Copy example env file
cp .env.example .env

# Edit with your credentials
nano .env
```

**Step 5: Run with Systemd (Auto-restart on boot)**
```bash
# Create systemd service file
nano /etc/systemd/system/telegram-bot.service
```

Add this content:
```ini
[Unit]
Description=Telegram Trading Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/Telegram-Trading-Bot-main
Environment="PATH=/root/Telegram-Trading-Bot-main/venv/bin"
ExecStart=/root/Telegram-Trading-Bot-main/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
systemctl daemon-reload
systemctl enable telegram-bot
systemctl start telegram-bot

# Check status
systemctl status telegram-bot

# View logs
journalctl -u telegram-bot -f
```

### 3. Docker Deployment

**Step 1: Create Dockerfile**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create output directories
RUN mkdir -p output/logs output/media

# Run the bot
CMD ["python", "app.py"]
```

**Step 2: Create docker-compose.yml**
```yaml
version: '3.8'

services:
  telegram-bot:
    build: .
    restart: always
    env_file:
      - .env
    volumes:
      - ./output:/app/output
      - ./tg_channel.db:/app/tg_channel.db
```

**Step 3: Deploy**
```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### 4. Free Hosting Options

#### Railway.app (Recommended - Free Tier Available)
- **Free tier**: $5/month credit (enough for small bots)
- **Easy deployment**: Connect GitHub, auto-deploy
- **Built-in database**: PostgreSQL available
- **Auto-scaling**: Scales automatically
- **Setup time**: ~5 minutes

**Steps:**
1. Go to https://railway.app
2. Click "New Project" → "Deploy from GitHub"
3. Select your repository
4. Railway auto-detects Python
5. Add environment variables in dashboard
6. Deploy!

**Environment Variables to Add:**
```
API_ID=your_api_id
API_HASH=your_api_hash
MISTRAL_API_KEY=your_mistral_key
```

#### Render.com (Free Tier Available)
- **Free tier**: 750 hours/month
- **Persistent storage**: 1GB free
- **SSL certificates**: Free
- **Auto-deploy**: From GitHub
- **Setup time**: ~5 minutes

**Steps:**
1. Go to https://render.com
2. Click "New" → "Web Service"
3. Connect GitHub repository
4. Build command: `pip install -r requirements.txt`
5. Start command: `python app.py`
6. Add environment variables
7. Deploy!

#### PythonAnywhere (Free Tier Available)
- **Free tier**: Limited but functional
- **Always-on**: $5/month (free tier has timeouts)
- **Easy setup**: Web-based interface
- **Setup time**: ~10 minutes

**Steps:**
1. Go to https://www.pythonanywhere.com
2. Create free account
3. Create "Web App"
4. Select Python 3.11
5. Upload your files
6. Configure as a "Always-on task" or scheduled task
7. Add environment variables

#### Koyeb (Free Tier Available)
- **Free tier**: $5.50/month credit
- **Global deployment**: Multiple regions
- **Docker support**: Native Docker
- **Setup time**: ~5 minutes

**Steps:**
1. Go to https://www.koyeb.com
2. Create account
3. Create "App"
4. Connect GitHub or use Docker
5. Deploy globally

#### Zeet (Free Tier Available)
- **Free tier**: $50/month credit
- **Multi-cloud**: Deploy anywhere
- **GitHub integration**: Auto-deploy
- **Setup time**: ~5 minutes

#### Replit (Free Tier Available)
- **Free tier**: Always-on Repls available
- **IDE included**: Browser-based development
- **Easy setup**: Zero configuration
- **Setup time**: ~2 minutes

**Steps:**
1. Go to https://replit.com
2. Create Python Repl
3. Upload your files
4. Click "Run"
5. Configure as Always-on (requires paid plan for 24/7)

### 5. Cloud Platforms (Paid)

#### Railway.app
1. Connect your GitHub repository
2. Railway will auto-detect Python
3. Add environment variables in Railway dashboard
4. Deploy automatically

#### Render.com
1. Create new Web Service
2. Connect GitHub repository
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `python app.py`
5. Add environment variables
6. Deploy

#### Heroku
```bash
# Install Heroku CLI
# Login
heroku login

# Create app
heroku create your-bot-name

# Set environment variables
heroku config:set API_ID=your_id
heroku config:set API_HASH=your_hash
heroku config:set MISTRAL_API_KEY=your_key

# Deploy
git push heroku main
```

## Security Best Practices

### 1. Environment Variables
- Never commit `.env` file to version control
- Use different API keys for development and production
- Rotate API keys regularly

### 2. Database Security
- The SQLite database contains sensitive wallet data
- Use encrypted storage in production
- Regular database backups

### 3. Private Key Security
- Currently using base64 encoding (NOT secure for production)
- Implement proper encryption (AES-256) for production
- Store encryption key in secure environment variable

### 4. Network Security
- Use firewall to restrict access
- Enable HTTPS if exposing any web endpoints
- Use VPN for server access

## Monitoring and Maintenance

### 1. Logs
```bash
# View logs
tail -f output/logs/bot.log

# Systemd logs
journalctl -u telegram-bot -f
```

### 2. Database Backups
```bash
# Backup database
cp tg_channel.db tg_channel.db.backup.$(date +%Y%m%d)

# Automated backup (add to crontab)
0 2 * * * cp /path/to/tg_channel.db /path/to/backups/tg_channel.db.$(date +\%Y\%m\%d)
```

### 3. Health Checks
```bash
# Check if bot is running
ps aux | grep "python app.py"

# Check systemd status
systemctl is-active telegram-bot
```

## Troubleshooting

### Bot won't start
1. Check environment variables are set correctly
2. Verify Telegram API credentials
3. Check logs for specific error messages
4. Ensure all dependencies are installed

### Connection issues
1. Check internet connectivity
2. Verify Telegram API is accessible
3. Check firewall settings
4. Try with proxy if needed

### Database errors
1. Check database file permissions
2. Ensure sufficient disk space
3. Verify SQLite is working properly

## Cost Estimates

### VPS Hosting
- DigitalOcean: $5-10/month
- Linode: $5-10/month
- Vultr: $5-10/month
- AWS Lightsail: $3.50-20/month

### Cloud Platforms
- Railway.app: $5-20/month (free tier available)
- Render.com: $7-25/month (free tier available)
- Heroku: $5-50/month (free tier available)

### Docker Hosting
- AWS ECS: Variable
- Google Cloud Run: Variable
- Azure Container Instances: Variable

## Recommended Setup for Production

**For beginners:** Railway.app or Render.com (easiest, free tier available)

**For more control:** VPS with systemd (DigitalOcean, Linode)

**For containerized deployment:** Docker with VPS or cloud platform

**For enterprise:** Kubernetes with cloud provider
