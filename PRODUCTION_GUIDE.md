# Production Testing & Deployment Guide

## Table of Contents
1. [Local Testing](#local-testing)
2. [Production Validation](#production-validation)
3. [Deployment Options](#deployment-options)
4. [Security Checklist](#security-checklist)
5. [Monitoring & Maintenance](#monitoring--maintenance)

---

## Local Testing

### Setup Test Environment

```bash
# Clone/enter the project
cd Telegram-Trading-Bot-main

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov  # For testing
```

### Run Unit Tests

```bash
# Run all unit tests
python -m pytest cmd/test/test_unit.py -v

# Run with coverage report
python -m pytest cmd/test/test_unit.py --cov=internal --cov-report=html

# Run specific test class
python -m pytest cmd/test/test_unit.py::TestWalletManager -v
```

### Run Integration Tests

```bash
# Test the complete signup and trading flow
python cmd/test/test_trading_api.py
```

### Test API Endpoints (using curl)

```bash
# Start the API server in one terminal
python cmd/server/api_server.py

# In another terminal, test endpoints:

# 1. Health check
curl http://localhost:5000/health

# 2. Register user
curl -X POST http://localhost:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "securepass123"
  }'

# 3. Login
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "securepass123"
  }'

# 4. Get user info (replace USER_ID with actual ID)
curl http://localhost:5000/api/user/USER_ID

# 5. Check deposit addresses
curl http://localhost:5000/api/user/USER_ID/deposit-addresses

# 6. Check deposit status
curl http://localhost:5000/api/user/USER_ID/deposit-status
```

---

## Production Validation

### Run Production Checks

```bash
# This validates config, API keys, database, file permissions, etc.
python internal/services/production_validator.py
```

This will check:
- ✓ Mistral API key validity
- ✓ Database connectivity
- ✓ Exchange API keys
- ✓ Wallet directory security
- ✓ File permissions
- ✓ SSL certificates
- ✓ Rate limiting config

### Address Common Issues

| Issue | Solution |
|-------|----------|
| `MISTRAL_API_KEY not set` | Add to `.env`: `MISTRAL_API_KEY=your_key` |
| `Database permission denied` | Run: `chmod 700 ./output/wallets` |
| `Exchange API key invalid` | Verify in exchange account settings |
| `HTTP instead of HTTPS` | Update `UPLOAD_BASE` to use HTTPS |

---

## Deployment Options

### Option 1: Docker (Recommended)

```bash
# Build and deploy
docker-compose up -d

# View logs
docker-compose logs -f trading-bot

# Stop
docker-compose down
```

### Option 2: Linux Systemd Service

```bash
# Create user and directories
sudo useradd -r -s /bin/bash trading-bot
sudo mkdir -p /home/trading-bot/trading-bot
sudo chown trading-bot:trading-bot /home/trading-bot/trading-bot

# Copy project
sudo cp -r . /home/trading-bot/trading-bot/
cd /home/trading-bot/trading-bot

# Setup virtual environment
sudo -u trading-bot python -m venv venv
sudo -u trading-bot venv/bin/pip install -r requirements-prod.txt

# Install service
sudo cp trading-bot-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable trading-bot-api
sudo systemctl start trading-bot-api

# Check status
sudo systemctl status trading-bot-api
sudo journalctl -u trading-bot-api -f  # View logs
```

### Option 3: Manual Deployment with Gunicorn

```bash
# Install production server
pip install gunicorn

# Run with 4 workers
gunicorn -w 4 -b 0.0.0.0:5000 cmd.server.api_server:app

# Or with custom logging
gunicorn -w 4 -b 0.0.0.0:5000 \
  --access-logfile ./output/logs/access.log \
  --error-logfile ./output/logs/error.log \
  cmd.server.api_server:app
```

### Option 4: Nginx Reverse Proxy

```bash
# Copy nginx config
sudo cp nginx.conf.example /etc/nginx/sites-available/trading-bot

# Enable site
sudo ln -s /etc/nginx/sites-available/trading-bot /etc/nginx/sites-enabled/

# Test and reload
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate (Let's Encrypt)
sudo certbot certonly --nginx -d trading-bot.example.com
```

---

## Security Checklist

### Before Production

- [ ] Never commit `.env` file to git
- [ ] Use strong passwords (min 16 chars, mixed case, numbers, symbols)
- [ ] Rotate API keys regularly
- [ ] Set file permissions: `chmod 700 output/wallets`
- [ ] Encrypt wallet mnemonics at rest (implement in production)
- [ ] Enable HTTPS/SSL for all communications
- [ ] Use environment variables for all secrets
- [ ] Set up database backups (daily)
- [ ] Configure firewall rules (only allow API port)
- [ ] Implement rate limiting on API endpoints
- [ ] Enable access logging
- [ ] Monitor for suspicious activity

### API Security

```bash
# Test rate limiting
for i in {1..20}; do
  curl -s http://localhost:5000/api/register
done

# Should see 429 Too Many Requests after threshold
```

### Database Security

```bash
# Regular backups
./output/backups/backup.sh

# Verify backups
ls -alh ./output/backups/
```

### Wallet Security

```bash
# Encrypt mnemonics in database (TODO: implement encryption)
# Current: Stored in plain text (UNSAFE for production)
# Recommended: Use AWS KMS, HashiCorp Vault, or cryptography library
```

---

## Monitoring & Maintenance

### Health Check

```bash
# Manual health check
curl http://localhost:5000/health

# Automated monitoring (add to crontab)
*/5 * * * * /path/to/output/health_check.sh
```

### View Logs

```bash
# API logs
tail -f ./output/logs/api.log

# Database logs
tail -f ./output/logs/bot.log

# Error logs
tail -f ./output/logs/error.log
```

### Database Maintenance

```bash
# Backup database
./output/backups/backup.sh

# View user account
sqlite3 ./tg_users.db "SELECT * FROM users LIMIT 1;"

# View trades
sqlite3 ./tg_users.db "SELECT * FROM trades LIMIT 5;"

# View deposits
sqlite3 ./tg_users.db "SELECT * FROM deposits LIMIT 5;"
```

### Update Dependencies

```bash
# Check for updates
pip list --outdated

# Update with pinned versions
pip install -r requirements-prod.txt --upgrade
```

### Performance Monitoring

```python
# Monitor in application logs (check LOG_FILE)
# Metrics tracked:
# - API response times
# - Trade execution times
# - Database query times
# - Error rates
# - Active connections
```

---

## Troubleshooting

### API Not Starting

```bash
# Check Python version
python --version  # Should be 3.10+

# Check port is free
lsof -i :5000

# Check dependencies
pip list | grep mistralai
pip list | grep flask

# View error logs
tail -100 ./output/logs/api.log
```

### Database Errors

```bash
# Check database integrity
sqlite3 ./tg_users.db "PRAGMA integrity_check;"

# Reset corrupt database
rm ./tg_users.db
# Tables will be recreated on next run
```

### Trade Execution Failures

```bash
# Verify exchange API keys
grep "API_KEY" .env | head -5

# Check exchange connectivity
python -c "import ccxt; print(ccxt.exchanges)"

# Test trade placement
python cmd/test/test_trading_api.py
```

---

## Performance Optimization

### Database Optimization

```bash
# Add indexes
sqlite3 ./tg_users.db << EOF
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_trades_user_id ON trades(user_id);
CREATE INDEX idx_deposits_user_id ON deposits(user_id);
EOF
```

### API Optimization

```bash
# Use production WSGI server (gunicorn)
gunicorn -w 8 -k gevent --worker-connections 1000 cmd.server.api_server:app

# Or with async workers
gunicorn -w 4 -k uvicorn.workers.UvicornWorker cmd.server.api_server:app
```

### Caching

```python
# Add Redis for session caching (optional)
pip install redis flask-caching
```

---

## Next Steps

1. ✅ Complete all unit tests
2. ✅ Run production validator
3. ✅ Setup monitoring/logging
4. ✅ Choose deployment option
5. ✅ Configure firewalls/security
6. ✅ Test with real deposits
7. ✅ Monitor metrics
8. ✅ Scale based on load

---

## Support

For issues or questions:
- Check logs: `./output/logs/api.log`
- Run diagnostics: `python internal/services/production_validator.py`
- Test API: `python cmd/test/test_trading_api.py`
