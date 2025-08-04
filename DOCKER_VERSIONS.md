# 🐳 Docker Image Versions (2025 Latest)

This document tracks the latest Docker image versions used in the Prompt Injection Scanner stack.

## Current Docker Images

| Service | Image | Version | Release Date | Key Features |
|---------|-------|---------|--------------|--------------|
| **PostgreSQL** | `postgres:17-alpine` | 17.x | 2024 | Latest stable with improved performance |
| **Redis** | `redis:8.2-alpine` | 8.2 | 2025 | Major performance & memory improvements |
| **etcd** | `gcr.io/etcd-development/etcd:v3.6.4` | 3.6.4 | 2024 | Latest stable distributed key-value store |
| **MinIO** | `minio/minio:RELEASE.2025-07-23T15-54-02Z` | 2025-07-23 | Jul 2025 | Latest object storage with AI features |
| **Milvus** | `milvusdb/milvus:v2.6.0` | 2.6.0 | 2025 | Streaming Node GA, improved performance |
| **Adminer** | `adminer:latest` | Latest | 2025 | Database administration interface |
| **Redis Commander** | `rediscommander/redis-commander:latest` | Latest | 2025 | Redis management UI |
| **Nginx** | `nginx:1.27-alpine` | 1.27 | 2025 | Latest stable reverse proxy |

## Version Highlights

### 🔥 **Redis 8.2**
- **Major performance improvements**: 30+ optimizations
- **Memory footprint reduction**: Significant memory savings
- **New commands**: Enhanced functionality
- **Command extensions** for better compatibility

### 🐘 **PostgreSQL 17**
- **Performance improvements**: Better query execution
- **Enhanced security**: Improved authentication and authorization
- **JSON enhancements**: Better JSON/JSONB support
- **Parallel processing**: Improved parallel query execution

### 🚀 **Milvus 2.6**
- **Streaming Node GA**: New component for shard-level WAL operations
- **Query delegator**: Enhanced query routing and processing
- **Performance optimizations**: Better vector search performance
- **Improved stability**: Production-ready streaming capabilities

### 🗄️ **MinIO 2025**
- **AI/ML optimizations**: Better support for AI workloads
- **Performance improvements**: Enhanced object storage operations
- **Security enhancements**: Updated security features
- **Compatibility**: Better S3 API compatibility

### 🔗 **etcd 3.6.4**
- **Stability improvements**: Enhanced reliability
- **Performance optimizations**: Better key-value operations
- **Security updates**: Latest security patches
- **Compatibility**: Improved cluster management

## Update Strategy

### 🔄 **Automatic Updates**
- Services using `:latest` tag will auto-update
- Monitor logs for compatibility issues after updates

### 🎯 **Pinned Versions**
- Critical services use specific version tags
- Manual updates required for version bumps
- Test in development before production deployment

### 🧪 **Testing Matrix**
Before updating production:
1. **Development**: Test with latest versions
2. **Staging**: Validate full integration
3. **Production**: Rolling update with rollback plan

## Compatibility Notes

### ⚠️ **Breaking Changes**
- **Redis 8.2**: Some commands deprecated, check application compatibility
- **PostgreSQL 17**: Review extension compatibility
- **Milvus 2.6**: Streaming Node changes may affect existing configurations

### ✅ **Backward Compatibility**
- Database schemas remain compatible
- API endpoints maintain backward compatibility
- Configuration files work with new versions

## Monitoring

### 📊 **Health Checks**
All services include comprehensive health checks:
- **Database connectivity**: PostgreSQL, Redis connection tests
- **Service readiness**: Application startup validation
- **Resource monitoring**: Memory, CPU, disk usage tracking

### 🔍 **Version Verification**
```bash
# Check running versions
docker compose ps
docker exec scanner-postgres psql --version
docker exec scanner-redis redis-server --version
docker exec scanner-milvus milvus --version
```

## Rollback Plan

### 🔙 **Previous Stable Versions**
Keep these versions as rollback targets:
- PostgreSQL: `postgres:15-alpine`
- Redis: `redis:7-alpine`
- Milvus: `milvusdb/milvus:v2.3.0`
- MinIO: `minio/minio:RELEASE.2023-03-20T20-16-18Z`

### 🚨 **Emergency Rollback**
```bash
# Quick rollback to previous versions
git checkout HEAD~1 docker-compose.yml
docker compose down
docker compose up -d
```

---

**Last Updated**: January 2025  
**Next Review**: March 2025  

> 💡 **Tip**: Always test new versions in development before updating production deployments.