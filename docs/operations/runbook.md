# Operations Runbook

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Incident Response](#incident-response)
3. [Common Operations](#common-operations)
4. [Monitoring and Alerting](#monitoring-and-alerting)
5. [Backup and Recovery](#backup-and-recovery)
6. [Scaling](#scaling)
7. [Performance Tuning](#performance-tuning)

## Quick Reference

### Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3000 | admin / (from env) |
| Prometheus | http://localhost:9091 | - |
| AlertManager | http://localhost:9093 | - |
| Health Check | http://localhost:8080/health | - |
| Metrics | http://localhost:9090/metrics | - |

### Emergency Contacts

| Role | Contact | Escalation |
|------|---------|------------|
| On-Call Engineer | oncall@example.com | PagerDuty |
| Team Lead | lead@example.com | Phone |
| Infrastructure | infra@example.com | Slack #infra |

### Quick Commands

```bash
# Check service status
docker-compose -f docker-compose.production.yml ps
# or
kubectl get pods -n discovery-agent

# View logs
docker-compose -f docker-compose.production.yml logs -f discovery-agent
# or
kubectl logs -f deployment/discovery-agent -n discovery-agent

# Restart service
docker-compose -f docker-compose.production.yml restart discovery-agent
# or
kubectl rollout restart deployment/discovery-agent -n discovery-agent

# Check health
curl http://localhost:8080/health | jq
```

## Incident Response

### Severity Levels

| Level | Description | Response Time | Action |
|-------|-------------|---------------|--------|
| P0 - Critical | Service completely down | 15 minutes | Page on-call immediately |
| P1 - High | Degraded service, high error rate | 30 minutes | Alert on-call |
| P2 - Medium | Minor issues, low impact | 2 hours | Create ticket |
| P3 - Low | No impact, informational | Next business day | Create ticket |

### P0: Service Down

**Symptoms**: ServiceDown alert firing, health checks failing

**Steps**:

1. **Acknowledge alert** in PagerDuty/AlertManager

2. **Check service status**:
   ```bash
   # Docker
   docker-compose -f docker-compose.production.yml ps
   docker-compose -f docker-compose.production.yml logs --tail=100 discovery-agent
   
   # Kubernetes
   kubectl get pods -n discovery-agent
   kubectl logs -f deployment/discovery-agent -n discovery-agent --tail=100
   ```

3. **Check health endpoint**:
   ```bash
   curl -v http://localhost:8080/health
   ```

4. **Check resource usage**:
   ```bash
   # Docker
   docker stats discovery-agent
   
   # Kubernetes
   kubectl top pod -n discovery-agent
   ```

5. **Restart service** if unresponsive:
   ```bash
   # Docker
   docker-compose -f docker-compose.production.yml restart discovery-agent
   
   # Kubernetes
   kubectl rollout restart deployment/discovery-agent -n discovery-agent
   ```

6. **Verify recovery**:
   ```bash
   curl http://localhost:8080/health/ready
   ```

7. **Document incident** in postmortem template

### P1: High Error Rate

**Symptoms**: HighErrorRate or CriticalErrorRate alert firing

**Steps**:

1. **Check error metrics** in Grafana:
   - Open "Discovery Agent - Overview" dashboard
   - Check "Error Rate" panel
   - Identify error types in logs

2. **Review error logs**:
   ```bash
   # Docker
   docker-compose logs discovery-agent | grep ERROR
   
   # Kubernetes
   kubectl logs deployment/discovery-agent -n discovery-agent | grep ERROR
   ```

3. **Common causes**:
   - **403 Forbidden**: Token permissions issue → Check token scopes
   - **429 Rate Limited**: Too many requests → Wait or reduce concurrency
   - **500 Server Error**: GitLab API issues → Check GitLab status
   - **Connection timeout**: Network issues → Check connectivity

4. **Mitigation**:
   - Reduce `MAX_API_CALLS` temporarily
   - Increase backoff delays
   - Skip problematic projects

5. **Monitor recovery**:
   - Watch error rate in Grafana
   - Verify successful operations resume

### P1: API Rate Limit Exhausted

**Symptoms**: APIRateLimitExhausted alert firing

**Steps**:

1. **Check rate limit status**:
   ```bash
   curl http://localhost:9090/metrics | grep gitlab_api_rate_limit_remaining
   ```

2. **Wait for reset**:
   - GitLab rate limits reset every minute (per-minute limit)
   - Check headers for reset time

3. **Temporary mitigation**:
   ```bash
   # Reduce API call budget
   # Update environment variable
   docker-compose -f docker-compose.production.yml down
   # Edit .env: MAX_API_CALLS=1000
   docker-compose -f docker-compose.production.yml up -d
   ```

4. **Long-term fixes**:
   - Implement caching
   - Reduce polling frequency
   - Use webhooks instead of polling
   - Request rate limit increase from GitLab

### P2: High API Latency

**Symptoms**: HighAPILatency alert firing, slow responses

**Steps**:

1. **Check latency metrics**:
   - Open Grafana "API Latency (p95)" panel
   - Identify slow endpoints

2. **Check network connectivity**:
   ```bash
   # Docker
   docker exec discovery-agent curl -w "@curl-format.txt" -o /dev/null -s https://gitlab.com/api/v4/version
   
   # Kubernetes
   kubectl exec deployment/discovery-agent -n discovery-agent -- curl -w "@curl-format.txt" -o /dev/null -s https://gitlab.com/api/v4/version
   ```

3. **Check GitLab status**: https://status.gitlab.com

4. **Mitigation**:
   - Increase timeout values
   - Reduce concurrent requests
   - Enable retry with exponential backoff

## Common Operations

### Restart Service

```bash
# Docker
docker-compose -f docker-compose.production.yml restart discovery-agent

# Kubernetes
kubectl rollout restart deployment/discovery-agent -n discovery-agent
```

### Update Configuration

```bash
# Docker
# 1. Edit .env file
vim .env

# 2. Restart service
docker-compose -f docker-compose.production.yml down
docker-compose -f docker-compose.production.yml up -d

# Kubernetes
# 1. Update configmap
kubectl edit configmap discovery-agent-config -n discovery-agent

# 2. Restart pods
kubectl rollout restart deployment/discovery-agent -n discovery-agent
```

### Rotate Secrets

```bash
# Docker
# 1. Update .env with new token
vim .env

# 2. Restart service
docker-compose -f docker-compose.production.yml restart discovery-agent

# Kubernetes
# 1. Update secret
kubectl create secret generic discovery-agent-secrets \
  --from-literal=GITLAB_TOKEN=new-token \
  --dry-run=client -o yaml | kubectl apply -f -

# 2. Restart pods
kubectl rollout restart deployment/discovery-agent -n discovery-agent
```

### Scale Service

```bash
# Kubernetes only (stateless operation)
kubectl scale deployment discovery-agent --replicas=3 -n discovery-agent
```

### View Logs

```bash
# Docker - Last 100 lines
docker-compose -f docker-compose.production.yml logs --tail=100 -f discovery-agent

# Docker - Search logs
docker-compose logs discovery-agent | grep "ERROR"

# Kubernetes - Follow logs
kubectl logs -f deployment/discovery-agent -n discovery-agent

# Kubernetes - Last hour
kubectl logs deployment/discovery-agent -n discovery-agent --since=1h

# Kubernetes - Search logs
kubectl logs deployment/discovery-agent -n discovery-agent | grep "ERROR"
```

## Monitoring and Alerting

### Key Metrics to Monitor

1. **API Request Rate**: Should be steady, not spiking
2. **API Latency**: p95 should be < 1s, p99 < 2s
3. **Error Rate**: Should be < 5%
4. **Rate Limit Remaining**: Should not approach 0
5. **Memory Usage**: Should be < 80% of limit
6. **CPU Usage**: Should be < 70% average

### Grafana Dashboards

Access Grafana at http://localhost:3000

**Discovery Agent - Overview**:
- API metrics
- Error rates
- Discovery progress
- Resource usage

### Alert Configuration

Alerts are defined in `monitoring/alerts.yml`:

- **ServiceDown**: Service unavailable for 2+ minutes
- **HighErrorRate**: Error rate > 10% for 5 minutes
- **CriticalErrorRate**: Error rate > 50% for 2 minutes
- **APIRateLimitApproaching**: < 100 calls remaining
- **APIRateLimitExhausted**: 0 calls remaining
- **HighAPILatency**: p95 > 2s for 5 minutes
- **HighMemoryUsage**: > 90% for 5 minutes
- **HighCPUUsage**: > 80% for 5 minutes

### Testing Alerts

```bash
# Trigger test alert
curl -X POST http://localhost:9093/api/v1/alerts -d '[
  {
    "labels": {
      "alertname": "TestAlert",
      "severity": "warning"
    },
    "annotations": {
      "summary": "Test alert"
    }
  }
]'
```

## Backup and Recovery

### Backup Data

```bash
# Docker volumes backup
docker-compose -f docker-compose.production.yml down
docker run --rm \
  -v gl2gh_discovery-data:/data \
  -v $(pwd)/backup:/backup \
  ubuntu tar czf /backup/discovery-data-$(date +%Y%m%d-%H%M%S).tar.gz /data

# Backup database (if using external DB)
# MongoDB example
mongodump --uri="mongodb://localhost:27017/discovery" --out=/backup/mongodb-$(date +%Y%m%d-%H%M%S)
```

### Restore Data

```bash
# Restore Docker volumes
docker run --rm \
  -v gl2gh_discovery-data:/data \
  -v $(pwd)/backup:/backup \
  ubuntu tar xzf /backup/discovery-data-YYYYMMDD-HHMMSS.tar.gz -C /

# Start services
docker-compose -f docker-compose.production.yml up -d

# Restore database
mongorestore --uri="mongodb://localhost:27017/discovery" /backup/mongodb-YYYYMMDD-HHMMSS
```

### Automated Backups

Add to crontab:

```bash
# Daily backup at 2 AM
0 2 * * * /path/to/backup-script.sh

# Weekly backup on Sunday at 3 AM
0 3 * * 0 /path/to/weekly-backup.sh
```

Backup script example:

```bash
#!/bin/bash
set -e

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d-%H%M%S)
RETENTION_DAYS=30

# Backup data
docker run --rm \
  -v gl2gh_discovery-data:/data \
  -v ${BACKUP_DIR}:/backup \
  ubuntu tar czf /backup/discovery-data-${DATE}.tar.gz /data

# Remove old backups
find ${BACKUP_DIR} -name "discovery-data-*.tar.gz" -mtime +${RETENTION_DAYS} -delete

# Upload to S3 (optional)
aws s3 cp ${BACKUP_DIR}/discovery-data-${DATE}.tar.gz s3://my-backup-bucket/
```

## Scaling

### Horizontal Scaling

```bash
# Kubernetes
kubectl scale deployment discovery-agent --replicas=3 -n discovery-agent

# Verify
kubectl get pods -n discovery-agent
```

### Vertical Scaling

```bash
# Kubernetes - Update resource requests/limits
kubectl edit deployment discovery-agent -n discovery-agent

# Update these values:
resources:
  requests:
    cpu: 1000m
    memory: 1Gi
  limits:
    cpu: 4000m
    memory: 4Gi
```

## Performance Tuning

### Optimize API Calls

1. **Reduce polling frequency**
2. **Implement caching**
3. **Use conditional requests** (If-Modified-Since)
4. **Batch operations**

### Memory Optimization

1. **Process in chunks**
2. **Stream large responses**
3. **Clear caches periodically**
4. **Use generators instead of lists**

### Network Optimization

1. **Use connection pooling**
2. **Enable HTTP/2**
3. **Compress responses**
4. **Use CDN for static assets**

### Configuration Tuning

```yaml
# Optimal settings for high-volume
MAX_API_CALLS: 10000
MAX_PER_PROJECT_CALLS: 500
CONCURRENT_REQUESTS: 10  # Add if implementing concurrency
CACHE_TTL: 3600  # Add caching
```

## Disaster Recovery

### Recovery Time Objective (RTO)

- **Target**: 4 hours
- **Maximum**: 24 hours

### Recovery Point Objective (RPO)

- **Target**: 24 hours
- **Maximum**: 7 days

### DR Plan

1. **Declare disaster** (notify team)
2. **Assess damage** (what's lost?)
3. **Restore from backup** (latest backup)
4. **Verify integrity** (check data)
5. **Resume operations** (start service)
6. **Monitor closely** (watch for issues)
7. **Document incident** (postmortem)

### DR Testing

Schedule quarterly DR drills:

```bash
# Quarterly DR drill
1. Simulate failure (stop all services)
2. Restore from backup
3. Verify functionality
4. Document results
5. Update runbook
```

## Contact and Escalation

### Support Channels

- **Slack**: #discovery-agent-support
- **Email**: team@example.com
- **PagerDuty**: https://company.pagerduty.com

### Escalation Path

1. **L1**: On-call engineer (PagerDuty)
2. **L2**: Team lead (after 30 min)
3. **L3**: Infrastructure team (after 1 hour)
4. **L4**: Management (P0 only)
