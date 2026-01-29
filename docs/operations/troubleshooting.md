# Troubleshooting Guide

## Table of Contents

1. [Diagnostic Commands](#diagnostic-commands)
2. [Common Issues](#common-issues)
3. [Error Messages](#error-messages)
4. [Performance Issues](#performance-issues)
5. [Network Issues](#network-issues)
6. [Configuration Issues](#configuration-issues)

## Diagnostic Commands

### Check Service Health

```bash
# Health check endpoint
curl -s http://localhost:8080/health | jq

# Liveness probe
curl -s http://localhost:8080/health/live | jq

# Readiness probe
curl -s http://localhost:8080/health/ready | jq
```

### Check Service Status

```bash
# Docker
docker-compose -f docker-compose.production.yml ps
docker-compose -f docker-compose.production.yml logs --tail=50 discovery-agent

# Kubernetes
kubectl get pods -n discovery-agent
kubectl describe pod <pod-name> -n discovery-agent
kubectl logs <pod-name> -n discovery-agent --tail=50
```

### Check Metrics

```bash
# View all metrics
curl -s http://localhost:9090/metrics

# Check API rate limit
curl -s http://localhost:9090/metrics | grep gitlab_api_rate_limit_remaining

# Check error count
curl -s http://localhost:9090/metrics | grep discovery_errors_total
```

### Check Resource Usage

```bash
# Docker
docker stats discovery-agent

# Kubernetes
kubectl top pod -n discovery-agent
kubectl describe node
```

## Common Issues

### Issue: Service Won't Start

**Symptoms**:
- Container exits immediately
- Pod in CrashLoopBackOff
- "Connection refused" errors

**Diagnosis**:
```bash
# Check logs
docker logs discovery-agent
# or
kubectl logs <pod-name> -n discovery-agent

# Check configuration
docker exec discovery-agent env | grep GITLAB
# or
kubectl exec <pod-name> -n discovery-agent -- env | grep GITLAB
```

**Common Causes**:

1. **Missing required environment variables**
   ```bash
   # Verify GITLAB_TOKEN and GITLAB_BASE_URL are set
   docker exec discovery-agent printenv | grep GITLAB
   ```
   **Fix**: Add missing variables to .env or secret

2. **Invalid GitLab token**
   ```bash
   # Test token
   curl -H "PRIVATE-TOKEN: your-token" https://gitlab.com/api/v4/user
   ```
   **Fix**: Generate new token with correct scopes

3. **Network connectivity issues**
   ```bash
   # Test connectivity
   docker exec discovery-agent ping -c 3 gitlab.com
   curl -I https://gitlab.com
   ```
   **Fix**: Check firewall rules, proxy settings

4. **Port already in use**
   ```bash
   # Check if ports are available
   netstat -tuln | grep -E ':(8080|9090)'
   ```
   **Fix**: Stop conflicting service or change ports

### Issue: High Memory Usage

**Symptoms**:
- OOMKilled pods
- Service becomes unresponsive
- Memory usage > 90%

**Diagnosis**:
```bash
# Check memory usage
docker stats discovery-agent
# or
kubectl top pod -n discovery-agent

# Check for memory leaks in logs
docker logs discovery-agent | grep -i "memory\|oom"
```

**Solutions**:

1. **Increase memory limits**
   ```yaml
   # k8s/deployment.yaml
   resources:
     limits:
       memory: 4Gi  # Increase from 2Gi
   ```

2. **Reduce concurrent operations**
   ```bash
   # Update configuration
   MAX_PER_PROJECT_CALLS=100  # Reduce from 200
   ```

3. **Enable memory profiling**
   ```python
   # Add to code for debugging
   import tracemalloc
   tracemalloc.start()
   ```

### Issue: API Rate Limit Errors

**Symptoms**:
- 429 HTTP status codes
- "Rate limit exceeded" messages
- APIRateLimitExhausted alert

**Diagnosis**:
```bash
# Check rate limit status
curl http://localhost:9090/metrics | grep gitlab_api_rate_limit_remaining

# Check error logs
docker logs discovery-agent | grep "429\|rate limit"
```

**Solutions**:

1. **Wait for rate limit reset**
   ```bash
   # Rate limits reset every minute for GitLab
   # Check headers for exact reset time
   curl -I -H "PRIVATE-TOKEN: token" https://gitlab.com/api/v4/user
   ```

2. **Reduce API call rate**
   ```bash
   # Update configuration
   MAX_API_CALLS=2000  # Reduce from 5000
   MAX_PER_PROJECT_CALLS=100  # Reduce from 200
   ```

3. **Implement exponential backoff** (already implemented)
   - Check logs for backoff messages
   - Verify backoff is working correctly

### Issue: Connection Timeouts

**Symptoms**:
- "Connection timeout" errors
- Requests taking too long
- HighAPILatency alert

**Diagnosis**:
```bash
# Test connectivity
curl -w "@curl-format.txt" -o /dev/null -s https://gitlab.com/api/v4/version

# curl-format.txt:
cat > curl-format.txt << 'EOF'
    time_namelookup:  %{time_namelookup}\n
       time_connect:  %{time_connect}\n
    time_appconnect:  %{time_appconnect}\n
   time_pretransfer:  %{time_pretransfer}\n
      time_redirect:  %{time_redirect}\n
 time_starttransfer:  %{time_starttransfer}\n
                    ----------\n
         time_total:  %{time_total}\n
EOF

# Check DNS resolution
nslookup gitlab.com
dig gitlab.com

# Trace route
traceroute gitlab.com
```

**Solutions**:

1. **Increase timeout values**
   ```python
   # gitlab_client.py
   DEFAULT_TIMEOUT = 60  # Increase from 30
   ```

2. **Check network configuration**
   ```bash
   # Verify proxy settings
   echo $HTTP_PROXY
   echo $HTTPS_PROXY
   
   # Test without proxy
   unset HTTP_PROXY HTTPS_PROXY
   curl https://gitlab.com/api/v4/version
   ```

3. **Use closer GitLab instance**
   - Consider geo-replication
   - Use regional GitLab instance

### Issue: Authentication Failures

**Symptoms**:
- 401 Unauthorized errors
- 403 Forbidden errors
- "Invalid token" messages

**Diagnosis**:
```bash
# Test token validity
curl -H "PRIVATE-TOKEN: your-token" https://gitlab.com/api/v4/user

# Check token scopes
curl -H "PRIVATE-TOKEN: your-token" https://gitlab.com/api/v4/personal_access_tokens/self
```

**Solutions**:

1. **Verify token has required scopes**
   - Required: `read_api`, `read_repository`
   - Generate new token: Settings > Access Tokens

2. **Check token expiration**
   ```bash
   # Tokens expire - check expiry date
   curl -H "PRIVATE-TOKEN: token" https://gitlab.com/api/v4/personal_access_tokens/self | jq '.expires_at'
   ```

3. **Verify token is for correct account**
   ```bash
   # Check token user
   curl -H "PRIVATE-TOKEN: token" https://gitlab.com/api/v4/user | jq '.username'
   ```

## Error Messages

### "Permission denied for step: detect_ci"

**Cause**: Token lacks `read_repository` scope

**Fix**:
1. Go to GitLab → Settings → Access Tokens
2. Generate new token with `read_repository` scope
3. Update GITLAB_TOKEN environment variable
4. Restart service

### "Resource not found" (404)

**Causes**:
- Project/group doesn't exist
- Token user doesn't have access
- Project is empty (no commits)

**Fix**:
```bash
# Verify project exists
curl -H "PRIVATE-TOKEN: token" "https://gitlab.com/api/v4/projects/PROJECT_ID"

# Check group access
curl -H "PRIVATE-TOKEN: token" "https://gitlab.com/api/v4/groups/GROUP_ID"
```

### "Connection reset by peer"

**Causes**:
- Network interruption
- GitLab server restart
- Firewall blocking connection

**Fix**:
1. Check GitLab status: https://status.gitlab.com
2. Verify network connectivity
3. Check firewall rules
4. Retry request (automatic retries enabled)

### "JSON decode error"

**Cause**: Invalid response from GitLab API

**Fix**:
```bash
# Check raw response
curl -H "PRIVATE-TOKEN: token" https://gitlab.com/api/v4/version

# Verify Content-Type header
curl -I -H "PRIVATE-TOKEN: token" https://gitlab.com/api/v4/version
```

## Performance Issues

### Slow Discovery

**Symptoms**:
- Discovery takes hours
- API requests are slow
- Timeout errors

**Diagnosis**:
```bash
# Check API latency
curl http://localhost:9090/metrics | grep gitlab_api_request_duration_seconds

# Monitor in Grafana
# Open "Discovery Agent - Overview" dashboard
```

**Solutions**:

1. **Optimize API usage**
   - Reduce `MAX_PER_PROJECT_CALLS`
   - Skip archived projects
   - Filter by project activity

2. **Increase concurrency** (if implemented)
   ```bash
   CONCURRENT_REQUESTS=5
   ```

3. **Use pagination efficiently**
   - Already implemented with `per_page=100`
   - Verify pagination is working

### High CPU Usage

**Symptoms**:
- CPU usage > 80%
- Service slow to respond
- Container throttling

**Diagnosis**:
```bash
# Check CPU usage
docker stats discovery-agent
# or
kubectl top pod -n discovery-agent

# Profile Python code
python -m cProfile -o profile.stats -m discovery_agent
```

**Solutions**:

1. **Increase CPU limits**
   ```yaml
   # k8s/deployment.yaml
   resources:
     limits:
       cpu: 4000m  # Increase from 2000m
   ```

2. **Optimize code**
   - Profile hot paths
   - Use generators instead of lists
   - Cache repeated calculations

## Network Issues

### Cannot Reach GitLab

**Diagnosis**:
```bash
# Test connectivity
ping gitlab.com
curl -I https://gitlab.com

# Check DNS
nslookup gitlab.com
dig gitlab.com

# Check routes
traceroute gitlab.com

# Check from container
docker exec discovery-agent curl -I https://gitlab.com
```

**Solutions**:

1. **Configure proxy**
   ```bash
   HTTP_PROXY=http://proxy.example.com:8080
   HTTPS_PROXY=http://proxy.example.com:8080
   NO_PROXY=localhost,127.0.0.1
   ```

2. **Update DNS settings**
   ```bash
   # /etc/resolv.conf
   nameserver 8.8.8.8
   nameserver 8.8.4.4
   ```

3. **Check firewall rules**
   ```bash
   # Allow outbound HTTPS
   iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT
   ```

### SSL Certificate Errors

**Symptoms**:
- "SSL certificate verify failed"
- "Certificate has expired"

**Diagnosis**:
```bash
# Check certificate
openssl s_client -connect gitlab.com:443 -showcerts

# Verify certificate chain
curl -v https://gitlab.com
```

**Solutions**:

1. **Update CA certificates**
   ```bash
   # Ubuntu/Debian
   apt-get update && apt-get install -y ca-certificates
   update-ca-certificates
   
   # Alpine
   apk add --no-cache ca-certificates
   ```

2. **Disable SSL verification** (not recommended for production)
   ```python
   # Only for testing
   requests.get(url, verify=False)
   ```

## Configuration Issues

### Environment Variables Not Loading

**Diagnosis**:
```bash
# Check if .env file exists
ls -la .env

# Check environment variables
docker exec discovery-agent env | grep GITLAB
# or
kubectl exec <pod-name> -n discovery-agent -- env | grep GITLAB
```

**Solutions**:

1. **Verify .env file format**
   ```bash
   # Should be KEY=VALUE format, no spaces
   GITLAB_TOKEN=glpat-xxx
   GITLAB_BASE_URL=https://gitlab.com
   ```

2. **Check file permissions**
   ```bash
   chmod 600 .env
   ```

3. **Restart service after changes**
   ```bash
   docker-compose restart discovery-agent
   ```

### Invalid Configuration Values

**Symptoms**:
- Service starts but doesn't work
- Unexpected behavior

**Diagnosis**:
```bash
# Validate configuration
python -m discovery_agent --help

# Check specific values
docker exec discovery-agent python -c "import os; print(os.getenv('MAX_API_CALLS'))"
```

**Solutions**:

1. **Use correct data types**
   ```bash
   MAX_API_CALLS=5000  # Number, not string
   JSON_LOGGING=true   # Boolean, not "yes"
   ```

2. **Validate URLs**
   ```bash
   # Should include https://
   GITLAB_BASE_URL=https://gitlab.com  # Correct
   GITLAB_BASE_URL=gitlab.com          # Incorrect
   ```

## Getting More Help

### Collect Diagnostic Information

```bash
# Generate diagnostic bundle
./scripts/collect-diagnostics.sh

# Includes:
# - Service logs
# - Configuration
# - Metrics snapshot
# - Resource usage
# - Network tests
```

### Enable Debug Logging

```bash
# Set log level to DEBUG
LOG_LEVEL=DEBUG

# Restart service
docker-compose restart discovery-agent
```

### Contact Support

Include the following information:

1. **Service version**: `docker exec discovery-agent python -m discovery_agent --version`
2. **Error message**: Full error from logs
3. **Steps to reproduce**: What were you doing when the error occurred?
4. **Configuration**: Sanitized configuration (remove secrets)
5. **Environment**: Docker/K8s, OS, network setup
6. **Diagnostic bundle**: Output from collect-diagnostics.sh

**Support Channels**:
- GitHub Issues: https://github.com/your-org/gl2gh/issues
- Slack: #discovery-agent-support
- Email: support@example.com
