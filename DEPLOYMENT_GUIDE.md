"""
DEPLOYMENT_GUIDE.md - Production Deployment Guide

## Pre-Deployment Checklist

- [ ] All tests passing
- [ ] Code review completed
- [ ] Security scan completed
- [ ] Database backups configured
- [ ] SSL/TLS certificates ready
- [ ] Environment variables configured
- [ ] Load testing completed
- [ ] Monitoring set up
- [ ] Logging aggregation configured
- [ ] Disaster recovery plan documented

## Environment Configuration

### Production Environment Variables

Set these in your production environment:

```env
# Core
ENVIRONMENT=production
DEBUG=False
APP_NAME=AI SQL Backend
APP_VERSION=1.0.0

# Database
DATABASE_URL=postgresql://user:secure_password@db.example.com:5432/ai_sql_db
DATABASE_ECHO=False

# Security
SECRET_KEY=<generate-secure-random-key>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Logging
LOG_LEVEL=WARNING
LOG_FORMAT=json
```

### Generate Secure Secret Key

```python
import secrets
secret_key = secrets.token_urlsafe(32)
print(secret_key)
```

## Deployment Methods

### 1. Docker Deployment

#### Build Image
```bash
docker build -t ai-sql-backend:1.0.0 .
docker tag ai-sql-backend:1.0.0 ai-sql-backend:latest
docker push your-registry/ai-sql-backend:latest
```

#### Run with Docker Compose
```bash
docker-compose -f docker-compose.yml up -d
```

### 2. Kubernetes Deployment

Create a `deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-sql-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ai-sql-backend
  template:
    metadata:
      labels:
        app: ai-sql-backend
    spec:
      containers:
      - name: api
        image: your-registry/ai-sql-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: database-url
        - name: ENVIRONMENT
          value: "production"
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 512Mi
```

### 3. Traditional Server Deployment

#### System Service Setup

Create `/etc/systemd/system/ai-sql-backend.service`:

```ini
[Unit]
Description=AI SQL Backend API
After=network.target postgresql.service

[Service]
Type=notify
User=www-data
WorkingDirectory=/app
Environment="PATH=/app/venv/bin"
ExecStart=/app/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl start ai-sql-backend
sudo systemctl enable ai-sql-backend
```

## Database Setup

### Initial Migration

```bash
# Using Alembic
alembic upgrade head

# Or manually create tables
python -c "from app.database import init_db; init_db()"
```

### Backup Strategy

```bash
# PostgreSQL backup
pg_dump -h localhost -U user ai_sql_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore from backup
psql -h localhost -U user ai_sql_db < backup_20240515_100000.sql
```

### Performance Optimization

1. **Add indexes** for frequently queried columns
2. **Configure connection pooling** (PgBouncer)
3. **Set up read replicas** for read-heavy workloads
4. **Regular vacuum and analyze**

## SSL/TLS Configuration

### Using Nginx Reverse Proxy

```nginx
upstream ai_sql_backend {
    server 127.0.0.1:8000;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /etc/ssl/certs/api.crt;
    ssl_certificate_key /etc/ssl/private/api.key;

    location / {
        proxy_pass http://ai_sql_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Monitoring & Observability

### Application Metrics

```python
# Add Prometheus metrics
from prometheus_client import Counter, Histogram
import time

request_count = Counter('api_requests_total', 'Total API requests')
request_duration = Histogram('api_request_duration_seconds', 'API request duration')

@app.middleware("http")
async def add_metrics(request, call_next):
    request_count.inc()
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    request_duration.observe(duration)
    return response
```

### Log Aggregation

Configure ELK Stack or similar:

```json
{
  "logstash.conf": {
    "input": {
      "file": {
        "path": "/app/logs/app.log"
      }
    },
    "filter": {
      "json": {
        "source": "message"
      }
    },
    "output": {
      "elasticsearch": {
        "hosts": ["elasticsearch:9200"]
      }
    }
  }
}
```

### Health Checks

```bash
# Health endpoint
curl https://api.example.com/health

# Database connectivity
curl https://api.example.com/health/db

# Ready check
curl https://api.example.com/health/ready
```

## Scaling Strategies

### Horizontal Scaling

1. **Load Balancing**: Use Nginx, HAProxy, or cloud provider load balancer
2. **Multiple Instances**: Run multiple API instances
3. **Database Connection Pooling**: Use PgBouncer or SQLAlchemy connection pool
4. **Caching Layer**: Redis for session and data caching

### Vertical Scaling

1. Increase CPU allocation
2. Increase memory allocation
3. Optimize database queries

## Security Hardening

### API Security

1. **Rate Limiting**
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.get("/api/v1/users/")
@limiter.limit("100/minute")
async def list_users(request: Request):
    ...
```

2. **CORS Configuration**
```python
# Restrict to specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://frontend.example.com"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

3. **HTTPS Enforcement**
```python
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
app.add_middleware(HTTPSRedirectMiddleware)
```

### Database Security

1. Use strong passwords
2. Enable SSL for database connections
3. Restrict database access by IP
4. Regular security updates
5. Encrypted backups

### Application Security

1. Input validation and sanitization
2. SQL injection prevention (use ORM)
3. XSS protection
4. CSRF protection
5. Regular dependency updates

## Performance Tuning

### Application Level

1. Enable query result caching
2. Use pagination for large datasets
3. Optimize database queries
4. Use async operations
5. Connection pooling

### Database Level

1. Query optimization
2. Index strategy
3. Statistics updates
4. Partition large tables
5. Archive old data

### Infrastructure Level

1. CDN for static files
2. Caching headers
3. Compression (gzip)
4. Network optimization

## Disaster Recovery

### Backup Strategy

- Daily full backups
- Hourly incremental backups
- Store backups in multiple locations
- Test restore procedures monthly

### Business Continuity

- Geographic redundancy
- Multi-region deployment
- Failover procedures
- Communication plan

## Troubleshooting

### Common Issues

**High Memory Usage**
```bash
# Check process memory
ps aux | grep uvicorn

# Profile memory
python -m memory_profiler app/main.py
```

**Database Connection Errors**
```bash
# Check database connectivity
psql -h localhost -U user -d ai_sql_db -c "SELECT 1"

# Monitor connections
SELECT count(*) FROM pg_stat_activity;
```

**Slow Queries**
```bash
# Enable query logging
ALTER SYSTEM SET log_min_duration_statement = 1000;

# Analyze query performance
EXPLAIN ANALYZE SELECT * FROM users WHERE ...;
```

## Maintenance Tasks

### Regular Tasks

- [ ] Review logs daily
- [ ] Monitor resource usage
- [ ] Check backup success
- [ ] Update dependencies monthly
- [ ] Performance review
- [ ] Security audits
- [ ] Database maintenance

### Scheduled Maintenance

```bash
# Weekly: Vacuum and analyze
VACUUM ANALYZE;

# Monthly: Full backup
pg_dump ai_sql_db | gzip > backup_monthly.sql.gz

# Quarterly: Upgrade dependencies
pip list --outdated
pip install --upgrade -r requirements.txt

# Yearly: Security audit
# External security assessment
```

## Contact & Support

- Documentation: /docs
- Issues: GitHub Issues
- Support: support@example.com
"""
