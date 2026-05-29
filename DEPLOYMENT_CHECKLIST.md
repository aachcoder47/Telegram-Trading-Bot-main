# TESTING & DEPLOYMENT CHECKLIST

## Pre-Deployment Testing Checklist

### Unit Tests
- [ ] All wallet generation tests pass
- [ ] User creation and authentication tests pass
- [ ] Signup flow tests pass
- [ ] Deposit watcher tests pass
- [ ] Configuration validation tests pass

**Run:**
```bash
python -m pytest cmd/test/test_unit.py -v
```

### Integration Tests
- [ ] Complete user registration works
- [ ] Login authentication works
- [ ] Deposit address retrieval works
- [ ] Deposit status checking works
- [ ] Trade execution flow works

**Run:**
```bash
python cmd/test/test_trading_api.py
```

### API Endpoint Tests
- [ ] `/health` returns 200
- [ ] `/api/register` creates user with deposit addresses
- [ ] `/api/login` authenticates user
- [ ] `/api/user/<id>` returns user info
- [ ] `/api/user/<id>/deposit-addresses` returns wallet addresses
- [ ] `/api/user/<id>/deposit-status` checks deposit balance
- [ ] `/api/trade` places trades

**Run:**
```bash
# Terminal 1
python cmd/server/api_server.py

# Terminal 2
curl http://localhost:5000/health
# Test endpoints from PRODUCTION_GUIDE.md
```

### Security Tests
- [ ] No hardcoded API keys in code
- [ ] Database file permissions are 600 (rw-------)
- [ ] Wallet directory permissions are 700 (rwx------)
- [ ] .env file permissions are 600
- [ ] SSL/HTTPS enabled for external APIs
- [ ] Input validation working (SQL injection protection)
- [ ] Password hashing using Argon2

**Run:**
```bash
python internal/services/production_validator.py
```

### Performance Tests
- [ ] User registration completes in < 2 seconds
- [ ] Login completes in < 1 second
- [ ] Deposit check completes in < 5 seconds
- [ ] Trade placement completes in < 3 seconds
- [ ] API handles 10+ concurrent requests

### Load Testing
- [ ] Server stable under 100 req/sec
- [ ] No memory leaks after 1 hour
- [ ] Database handles 1000+ trades
- [ ] Connection pooling working

---

## Deployment Checklist

### Pre-Deployment (24 hours before)

**Configuration**
- [ ] `.env` file created with all required keys
- [ ] `MISTRAL_API_KEY` is valid (not test/placeholder)
- [ ] Exchange API keys verified and funded
- [ ] `FEE_WALLET_ADDRESS` is correct Bitcoin address
- [ ] Database path is writable
- [ ] Log directory exists and is writable
- [ ] Wallet directory permissions are 700

**Secrets Management**
- [ ] `.env` added to `.gitignore`
- [ ] No production keys in git history
- [ ] Backup of encryption keys stored securely
- [ ] Database backups scheduled

**Infrastructure**
- [ ] Firewall configured (only allow 80/443)
- [ ] SSL certificates obtained (Let's Encrypt)
- [ ] DNS records updated
- [ ] Load balancer configured (if needed)
- [ ] Database replicas configured

**Testing**
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] Production validator passing
- [ ] Manual API testing completed

### Deployment Day

**Pre-Go**
- [ ] Notify all stakeholders
- [ ] Backup current database
- [ ] Document deployment start time
- [ ] Have rollback plan ready

**Deployment**

**Option 1: Docker**
```bash
# [ ] Pull latest code
git pull origin main

# [ ] Build image
docker build -t trading-bot:latest .

# [ ] Start containers
docker-compose up -d

# [ ] Verify health
curl http://localhost:5000/health

# [ ] Check logs
docker-compose logs -f
```

**Option 2: Systemd**
```bash
# [ ] Pull latest code
cd /home/trading-bot/trading-bot
sudo -u trading-bot git pull

# [ ] Update dependencies
sudo -u trading-bot venv/bin/pip install -r requirements-prod.txt

# [ ] Restart service
sudo systemctl restart trading-bot-api

# [ ] Verify status
sudo systemctl status trading-bot-api
```

**Option 3: Manual**
```bash
# [ ] Pull latest code
git pull origin main

# [ ] Install/update dependencies
pip install -r requirements-prod.txt

# [ ] Start server
gunicorn -w 4 -b 0.0.0.0:5000 cmd.server.api_server:app &

# [ ] Verify running
curl http://localhost:5000/health
```

**Post-Deployment**
- [ ] API responding to requests
- [ ] Database connection working
- [ ] User registration working end-to-end
- [ ] Deposit monitoring active
- [ ] Trade execution enabled
- [ ] Monitoring alerts active
- [ ] Logs being written
- [ ] Backups running

### Post-Deployment Monitoring (First 24 hours)

- [ ] API uptime: 100%
- [ ] Response times: < 500ms (p95)
- [ ] Error rate: < 0.1%
- [ ] Database: healthy
- [ ] CPU usage: < 50%
- [ ] Memory usage: stable
- [ ] No uncaught exceptions
- [ ] No database corruption

**Monitor with:**
```bash
# Terminal 1: API logs
tail -f ./output/logs/api.log

# Terminal 2: Error logs
tail -f ./output/logs/error.log

# Terminal 3: Health check
watch -n 5 'curl -s http://localhost:5000/health'

# Terminal 4: System stats
watch -n 1 'ps aux | grep api_server'
```

---

## Rollback Procedure

If deployment fails:

```bash
# Rollback to previous version
cd /path/to/bot

# Option 1: Git rollback
git revert HEAD
git push origin main

# Option 2: Docker rollback
docker-compose down
docker pull trading-bot:previous
docker-compose up -d

# Option 3: Restore database backup
sqlite3 ./tg_users.db < ./output/backups/tg_users_BACKUP.sql

# Restart service
systemctl restart trading-bot-api
# or
docker-compose restart
```

---

## Performance Baseline

Record these metrics for comparison:

| Metric | Baseline | Alert Level |
|--------|----------|-------------|
| API Response Time (p95) | < 200ms | > 1000ms |
| Error Rate | < 0.05% | > 1% |
| CPU Usage | < 30% | > 80% |
| Memory Usage | < 200MB | > 500MB |
| Database Connections | < 10 | > 50 |
| Daily Active Users | ? | ? |
| Total Trades/Day | ? | ? |

---

## Monitoring Commands

```bash
# Real-time API health
watch -n 1 'curl -s http://localhost:5000/health | jq'

# Database size
du -h ./tg_users.db

# Disk usage
du -sh ./output/

# Process memory
ps aux | grep api_server | awk '{print $6}' | numfmt --to=iec

# Network connections
netstat -an | grep :5000

# Check for errors in logs (last hour)
find ./output/logs -name "*.log" -mmin -60 -exec grep -l ERROR {} \;

# Count errors by type
grep ERROR ./output/logs/api.log | cut -d'-' -f2 | sort | uniq -c | sort -rn

# User count
sqlite3 ./tg_users.db "SELECT COUNT(*) FROM users;"

# Total deposits
sqlite3 ./tg_users.db "SELECT SUM(total_deposit_usd) FROM users;"

# Active trades
sqlite3 ./tg_users.db "SELECT COUNT(*) FROM trades WHERE status='open';"
```

---

## Incident Response

### API Down
1. Check service status: `systemctl status trading-bot-api`
2. Check logs: `tail -100 ./output/logs/api.log`
3. Restart service: `systemctl restart trading-bot-api`
4. Verify health: `curl http://localhost:5000/health`

### High Memory Usage
1. Check process: `ps aux | grep api_server`
2. Identify memory leak in logs
3. Restart service to free memory
4. Review recent code changes

### Database Issues
1. Check integrity: `sqlite3 ./tg_users.db "PRAGMA integrity_check;"`
2. Check size: `du -h ./tg_users.db`
3. Restore from backup if corrupted
4. Review error logs for SQL errors

### Trade Execution Failures
1. Verify exchange connectivity
2. Check API keys are valid
3. Verify account has sufficient balance
4. Check market is open
5. Review trade logs for error details

---

## Success Metrics

After deployment, track:
- ✅ Uptime: 99.9%+
- ✅ User registration: < 2 seconds
- ✅ Successful deposits: 95%+
- ✅ Trade execution success: 98%+
- ✅ Fee collection: 100% (5% deducted from profits)
- ✅ User satisfaction: 4.0+ stars (if applicable)

---

## Support

For deployment issues:
1. Check `PRODUCTION_GUIDE.md`
2. Run `python internal/services/production_validator.py`
3. Review logs: `./output/logs/`
4. Test API: `curl http://localhost:5000/health`
