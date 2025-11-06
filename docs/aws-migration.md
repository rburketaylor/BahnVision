# AWS Migration Guide

This guide covers migrating BahnVision from the local demo environment to AWS production services, maintaining operational parity while leveraging cloud-native capabilities.

## Migration Overview

### Target AWS Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Route 53      │    │   AWS CloudMap    │    │   Amazon ECR     │
│   (DNS)         │    │   (Discovery)    │    │   (Images)      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CloudFront    │    │  Application LB  │    │   Amazon EKS     │
│   (CDN)         │◄──►│   (Load Balancer)│◄──►│   (Kubernetes)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
         ┌─────────────────┐    ┌──────────────────┐    │
         │   Amazon S3     │    │   AWS RDS Proxy  │    │
         │   (Static)      │    │   (DB Proxy)     │    │
         └─────────────────┘    └──────────────────┘    │
                 │                       │              │
         ┌─────────────────┐    ┌──────────────────┐    │
         │   AWS RDS       │    │ Amazon ElastiCache│    │
         │ (PostgreSQL)    │    │    (Redis)       │    │
         └─────────────────┘    └──────────────────┘    │
                                                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Amazon CloudWatch│◄──►│  AWS X-Ray/OTEL  │◄──►│   AWS Jaeger    │
│   (Metrics)     │    │   (Tracing)      │    │   (Tracing)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Service Mapping

| Local Component | AWS Service | Notes |
|-----------------|-------------|-------|
| Docker Compose | Amazon EKS | Container orchestration |
| kind cluster | Amazon EKS | Production Kubernetes |
| PostgreSQL | Amazon RDS for PostgreSQL | Managed database |
| Valkey/Redis | Amazon ElastiCache for Redis | Managed cache |
| Toxiproxy | AWS Fault Injection Simulator | Chaos and resilience testing |
| Prometheus | Amazon Managed Prometheus | Metrics collection |
| Grafana | Amazon Managed Grafana | Visualization |
| Jaeger | AWS X-Ray + Amazon OpenSearch | Distributed tracing |
| ingress-nginx | Application Load Balancer | L7 load balancing |
| ArgoCD | AWS CodePipeline + ArgoCD | GitOps deployment |

## Prerequisites

### AWS Account Setup
- AWS account with appropriate permissions
- AWS CLI configured (`aws configure`)
- eksctl installed
- kubectl installed
- Helm 3 installed

### Required IAM Permissions
- EKS cluster management
- RDS instance management
- ElastiCache management
- IAM role and policy creation
- VPC and security group management
- CloudWatch and X-Ray permissions

## Phase 1: Infrastructure Setup

### 1.1 VPC and Networking

Create a dedicated VPC for BahnVision:

```bash
# Create VPC with public and private subnets
aws cloudformation create-stack \
  --stack-name bahnvision-network \
  --template-body file://aws/network.yaml \
  --parameters \
    ParameterKey=VpcCidr,ParameterValue=10.0.0.0/16 \
    ParameterKey=PublicSubnetCidr1,ParameterValue=10.0.1.0/24 \
    ParameterKey=PublicSubnetCidr2,ParameterValue=10.0.2.0/24 \
    ParameterKey=PrivateSubnetCidr1,ParameterValue=10.0.3.0/24 \
    ParameterKey=PrivateSubnetCidr2,ParameterValue=10.0.4.0/24
```

### 1.2 EKS Cluster

Create the EKS cluster:

```bash
# Create EKS cluster
eksctl create cluster \
  --name bahnvision-prod \
  --version 1.28 \
  --region us-west-2 \
  --nodegroup-name bahnvision-nodes \
  --node-type t3.medium \
  --nodes 3 \
  --nodes-min 2 \
  --nodes-max 6 \
  --managed \
  --vpc-private-subnets subnet-xxx,subnet-yyy \
  --ssh-access \
  --ssh-public-key ~/.ssh/id_rsa.pub

# Update kubeconfig
aws eks update-kubeconfig --region us-west-2 --name bahnvision-prod
```

### 1.3 Addons Installation

Install required addons:

```bash
# Install AWS Load Balancer Controller
helm repo add eks https://aws.github.io/eks-charts
helm repo update

helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=bahnvision-prod \
  --set serviceAccount.create=true \
  --set serviceAccount.name=aws-load-balancer-controller

# Install Cluster Autoscaler
helm install cluster-autoscaler eks/cluster-autoscaler \
  -n kube-system \
  --set autoDiscovery.clusterName=bahnvision-prod \
  --set awsRegion=us-west-2
```

## Phase 2: Database Migration

### 2.1 Amazon RDS Setup

Create RDS PostgreSQL instance:

```bash
# Create security group for RDS
aws ec2 create-security-group \
  --group-name bahnvision-rds-sg \
  --description "Security group for BahnVision RDS" \
  --vpc-id vpc-xxx

# Allow EKS nodes to connect to RDS
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxx \
  --protocol tcp \
  --port 5432 \
  --source-group sg-yyy  # EKS node security group

# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier bahnvision-prod \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.4 \
  --master-username bahnvision \
  --master-user-password $(openssl rand -base64 32) \
  --allocated-storage 20 \
  --vpc-security-group-ids sg-xxx \
  --db-subnet-group-name default \
  --backup-retention-period 7 \
  --multi-az \
  --storage-type gp2 \
  --storage-encrypted
```

### 2.2 RDS Proxy Setup

Create RDS Proxy for connection pooling:

```bash
# Create IAM role for RDS Proxy
aws iam create-role \
  --role-name bahnvision-rds-proxy-role \
  --assume-role-policy-document file://aws/rds-proxy-trust-policy.json

aws iam attach-role-policy \
  --role-name bahnvision-rds-proxy-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonRDSDataAccessPolicy

# Create RDS Proxy
aws rds create-db-proxy \
  --db-proxy-name bahnvision-proxy \
  --engine-family POSTGRESQL \
  --auth auth-resource-arns=arn:aws:rds:us-west-2:account-id:db:bahnvision-prod \
    auth-secret-arn=arn:aws:secretsmanager:us-west-2:account-id:secret:bahnvision-db-credentials \
  --role-arn arn:aws:iam::account-id:role/bahnvision-rds-proxy-role \
  --vpc-subnet-ids subnet-xxx,subnet-yyy \
  --vpc-security-group-ids sg-xxx

# Create target group
aws rds register-db-proxy-targets \
  --db-proxy-name bahnvision-proxy \
  --db-instance-identifiers bahnvision-prod
```

### 2.3 Database Migration

Migrate data from local PostgreSQL:

```bash
# Export local data
pg_dump -h localhost -U bahnvision bahnvision > bahnvision-backup.sql

# Import to RDS (temporary EC2 instance)
psql -h bahnvision-prod.xxx.us-west-2.rds.amazonaws.com \
     -U bahnvision \
     -d bahnvision \
     < bahnvision-backup.sql
```

## Phase 3: Cache Migration

### 3.1 Amazon ElastiCache Setup

Create ElastiCache Redis cluster:

```bash
# Create subnet group
aws elasticache create-cache-subnet-group \
  --cache-subnet-group-name bahnvision-cache-subnet \
  --cache-subnet-group-description "Subnet group for BahnVision cache" \
  --subnet-ids subnet-xxx,subnet-yyy

# Create security group
aws ec2 create-security-group \
  --group-name bahnvision-cache-sg \
  --description "Security group for BahnVision ElastiCache" \
  --vpc-id vpc-xxx

# Create Redis cluster
aws elasticache create-replication-group \
  --replication-group-id bahnvision-prod \
  --replication-group-description "BahnVision Redis cluster" \
  --engine redis \
  --engine-version 7.0 \
  --cache-node-type cache.t3.micro \
  --num-cache-clusters 2 \
  --automatic-failover-enabled \
  --multi-az-enabled \
  --cache-subnet-group-name bahnvision-cache-subnet \
  --security-group-ids sg-xxx
```

### 3.2 Cache Configuration Update

Update application configuration for ElastiCache:

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: bahnvision-config
data:
  # Update Redis URL for ElastiCache
  VALKEY_URL: "redis://bahnvision-prod.xxx.clustercfg.usw2.cache.amazonaws.com:6379/0"
  # Add Redis cluster mode
  VALKEY_CLUSTER_MODE: "true"
```

## Phase 4: Monitoring and Observability

### 4.1 Amazon Managed Prometheus

Set up AMP workspace:

```bash
# Create AMP workspace
aws amp create-workspace \
  --alias bahnvision-prod \
  --region us-west-2

# Get workspace endpoint
aws amp describe-workspace \
  --workspace-id ws-xxx \
  --query 'workspace.prometheusEndpoint' \
  --output text
```

Update Prometheus configuration:

```yaml
# prometheus-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s

    remote_write:
      - url: https://aps-workspaces.us-west-2.amazonaws.com/workspaces/ws-xxx/api/v1/remote_write
        sigv4:
          region: us-west-2
        queue_config:
          max_samples_per_send: 1000
          max_shards: 200
          capacity: 2500

    scrape_configs:
      - job_name: 'bahnvision-backend'
        kubernetes_sd_configs:
          - role: pod
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_label_app]
            action: keep
            regex: bahnvision-backend
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
            action: keep
            regex: true
```

### 4.2 Amazon Managed Grafana

Set up AMG workspace:

```bash
# Create AMG workspace
aws grafana create-workspace \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --workspace-name bahnvision-prod \
  --permission-type SERVICE_MANAGED \
  --workspace-role-arn arn:aws:iam::account-id:role/AmazonGrafanaAdminRole

# Configure data source
aws grafana create-workspace-data-source \
  --workspace-id ws-xxx \
  --data-source-name 'Amazon Prometheus' \
  --data-source-type 'PROMETHEUS' \
  --data-source-details '{"httpEndpointUri":"https://aps-workspaces.us-west-2.amazonaws.com/workspaces/ws-xxx/","defaultRegion":"us-west-2","authType":"SIGV4"}'
```

### 4.3 AWS X-Ray Integration

Update application for X-Ray tracing:

```yaml
# Deployment with X-Ray
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bahnvision-backend
spec:
  template:
    spec:
      containers:
      - name: backend
        env:
        - name: OTEL_ENABLED
          value: "true"
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: "http://aws-xray-daemon.service:2000"
        - name: AWS_XRAY_DAEMON_ADDRESS
          value: "xray-daemon.service:2000"
        - name: AWS_REGION
          value: "us-west-2"
```

## Phase 5: Application Deployment

### 5.1 Container Image Updates

Update image references for AWS:

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bahnvision-backend
spec:
  template:
    spec:
      containers:
      - name: backend
        image: account-id.dkr.ecr.us-west-2.amazonaws.com/bahnvision-backend:latest
        envFrom:
        - configMapRef:
            name: bahnvision-config
        - secretRef:
            name: bahnvision-secrets
```

### 5.2 IAM Roles for Service Accounts (IRSA)

Create IAM roles for pods:

```bash
# Create IAM role for backend
aws iam create-role \
  --role-name bahnvision-backend-role \
  --assume-role-policy-document file://aws/eks-trust-policy.json

# Attach required policies
aws iam attach-role-policy \
  --role-name bahnvision-backend-role \
  --policy-arn arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess

aws iam attach-role-policy \
  --role-name bahnvision-backend-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonPrometheusRemoteWriteAccess

# Create service account
kubectl create serviceaccount bahnvision-backend
kubectl annotate serviceaccount bahnvision-backend \
  eks.amazonaws.com/role-arn=arn:aws:iam::account-id:role/bahnvision-backend-role
```

### 5.3 Ingress Configuration

Update for AWS Load Balancer Controller:

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: bahnvision-ingress
  annotations:
    kubernetes.io/ingress.class: "alb"
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/ssl-policy: ELBSecurityPolicy-TLS-1-2-2017-01
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-west-2:account-id:certificate/xxx
spec:
  tls:
  - hosts:
    - api.bahnvision.com
    - www.bahnvision.com
  rules:
  - host: api.bahnvision.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: bahnvision-backend
            port:
              number: 8000
  - host: www.bahnvision.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: bahnvision-frontend
            port:
              number: 80
```

## Phase 6: DNS and CDN Setup

### 6.1 Route 53 Configuration

Create DNS records:

```bash
# Create hosted zone (if not exists)
aws route53 create-hosted-zone \
  --name bahnvision.com \
  --caller-reference $(date +%s)

# Create records for ALB
aws route53 change-resource-record-sets \
  --hosted-zone-id Z2xxxxxx \
  --change-batch file://aws/dns-records.json
```

### 6.2 CloudFront Distribution

Create CloudFront for static assets:

```bash
aws cloudfront create-distribution \
  --distribution-config file://aws/cloudfront-config.json
```

## Phase 7: CI/CD Pipeline Updates

### 7.1 AWS CodePipeline

Update GitHub Actions for AWS deployment:

```yaml
# .github/workflows/deploy-aws.yml
name: Deploy to AWS

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v2
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: us-west-2

    - name: Login to Amazon ECR
      uses: aws-actions/amazon-ecr-login@v1

    - name: Build and push images
      run: |
        # Build backend
        docker build -t $ECR_REGISTRY/bahnvision-backend:$GITHUB_SHA -f backend/Dockerfile .
        docker push $ECR_REGISTRY/bahnvision-backend:$GITHUB_SHA

        # Build frontend
        docker build -t $ECR_REGISTRY/bahnvision-frontend:$GITHUB_SHA -f frontend/Dockerfile frontend/
        docker push $ECR_REGISTRY/bahnvision-frontend:$GITHUB_SHA

    - name: Update kubeconfig
      run: aws eks update-kubeconfig --region us-west-2 --name bahnvision-prod

    - name: Deploy to EKS
      run: |
        # Update image tags in deployments
        sed -i "s|bahnvision-backend:latest|$ECR_REGISTRY/bahnvision-backend:$GITHUB_SHA|g" k8s/backend-deployment.yaml
        sed -i "s|bahnvision-frontend:latest|$ECR_REGISTRY/bahnvision-frontend:$GITHUB_SHA|g" k8s/frontend-deployment.yaml

        # Apply manifests
        kubectl apply -f k8s/
```

## Configuration Updates

### Environment Variables for AWS

```bash
# .env.aws
# Database (RDS Proxy)
DATABASE_URL=postgresql+asyncpg://bahnvision:password@bahnvision-proxy.proxy-xxx.us-west-2.rds.amazonaws.com:5432/bahnvision

# Cache (ElastiCache)
VALKEY_URL=redis://bahnvision-prod.xxx.clustercfg.usw2.cache.amazonaws.com:6379/0

# OpenTelemetry (AWS X-Ray)
OTEL_ENABLED=true
OTEL_SERVICE_NAME=bahnvision-backend
OTEL_EXPORTER_OTLP_ENDPOINT=http://xray-daemon.service:2000
OTEL_PROPAGATORS=tracecontext,baggage,b3

# AWS Region
AWS_REGION=us-west-2

# Monitoring
PROMETHEUS_REMOTE_WRITE_URL=https://aps-workspaces.us-west-2.amazonaws.com/workspaces/ws-xxx/api/v1/remote_write
```

## Cost Optimization

### Right-sizing Resources

| Service | Recommendation |
|---------|----------------|
| RDS | Start with db.t3.micro, scale based on performance |
| ElastiCache | cache.t3.micro for development, t3.small for production |
| EKS Nodes | t3.medium with cluster autoscaler (2-6 nodes) |
| ALB | Application Load Balancer with appropriate pricing tier |

### Cost Monitoring

Set up CloudWatch cost alerts:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name BahnVisionMonthlyCost \
  --alarm-description "Alert when monthly costs exceed $200" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Sum \
  --period 86400 \
  --threshold 200 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1
```

## Security Considerations

### Network Security

- Use private subnets for RDS and ElastiCache
- Implement security groups with minimal required ports
- Use VPC endpoints for AWS services
- Enable encryption in transit and at rest

### Access Control

- Use IAM roles with least privilege principle
- Implement IRSA for pod-level permissions
- Rotate database credentials regularly
- Use AWS Secrets Manager for sensitive data

### Compliance

- Enable AWS CloudTrail for audit logging
- Use AWS Config for compliance monitoring
- Implement VPC Flow Logs for network monitoring
- Regular security assessments with AWS Inspector

## Monitoring and Alerting

### CloudWatch Dashboards

Create custom dashboards:

```bash
aws cloudwatch put-dashboard \
  --dashboard-name BahnVision-Production \
  --dashboard-body file://aws/cloudwatch-dashboard.json
```

### Key Metrics to Monitor

- **Application**: Response time, error rate, throughput
- **Infrastructure**: CPU, memory, network, disk usage
- **Database**: Connection count, query performance, replication lag
- **Cache**: Hit ratio, memory usage, evictions
- **Load Balancer**: Request count, response codes, target health

### Alert Configuration

Set up SNS alerts:

```bash
aws sns create-topic --name bahnvision-alerts

aws cloudwatch put-metric-alarm \
  --alarm-name BahnVisionHighErrorRate \
  --alarm-description "High error rate detected" \
  --metric-name ErrorRate \
  --namespace BahnVision \
  --statistic Average \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-west-2:account-id:bahnvision-alerts
```

## Disaster Recovery

### Backup Strategy

- **RDS**: Automated daily snapshots with 30-day retention
- **ElastiCache**: Automatic backups with 15-day retention
- **EKS**: EBS volume snapshots and etcd backups
- **Application**: Periodic data exports to S3

### Multi-AZ Deployment

```bash
# Enable Multi-AZ for RDS
aws rds modify-db-instance \
  --db-instance-identifier bahnvision-prod \
  --multi-az \
  --apply-immediately

# Enable Multi-AZ for ElastiCache
aws elasticache modify-replication-group \
  --replication-group-id bahnvision-prod \
  --automatic-failover-enabled \
  --multi-az-enabled
```

### Failover Testing

Regular failover drills:

```bash
# Test RDS failover
aws rds reboot-db-instance \
  --db-instance-identifier bahnvision-prod \
  --force-failover

# Test ElastiCache failover
aws elasticache test-failover \
  --replication-group-id bahnvision-prod \
  --node-group-id 001
```

## Migration Timeline

### Week 1: Infrastructure Setup
- VPC and networking
- EKS cluster creation
- IAM roles and policies

### Week 2: Data Migration
- RDS setup and data migration
- ElastiCache cluster creation
- Application configuration updates

### Week 3: Monitoring Setup
- AMP and AMG workspaces
- X-Ray integration
- CloudWatch dashboards

### Week 4: Application Deployment
- Container image updates
- EKS deployment
- Load balancer and DNS configuration

### Week 5: Testing and Cut-over
- Integration testing
- Performance validation
- Traffic cut-over

### Week 6: Optimization
- Cost optimization
- Performance tuning
- Security hardening

## Post-Migration Checklist

- [ ] All services running in EKS
- [ ] Database connectivity verified
- [ ] Cache operations functional
- [ ] Monitoring data flowing
- [ ] Alerts configured and tested
- [ ] DNS resolution working
- [ ] SSL certificates valid
- [ ] Performance benchmarks met
- [ ] Security scan passed
- [ ] Backup procedures verified
- [ ] Documentation updated
- [ ] Team training completed

## Troubleshooting

### Common Issues

**Database connection failures**:
- Check security group rules
- Verify RDS proxy status
- Validate IAM permissions

**Cache connectivity issues**:
- Confirm subnet group configuration
- Check security group access
- Verify cluster endpoint

**Monitoring gaps**:
- Validate IAM roles for AMP
- Check remote write configuration
- Confirm Prometheus scraping

**Pod deployment failures**:
- Check IAM service account annotations
- Validate ECR image permissions
- Review resource limits

### Recovery Procedures

Database recovery:
```bash
# Restore from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier bahnvision-prod-restored \
  --db-snapshot-identifier bahnvision-prod-snapshot
```

Cache recovery:
```bash
# Create new cluster from backup
aws elasticache create-replication-group \
  --replication-group-id bahnvision-prod-new \
  --replication-group-description "Restored cluster" \
  --engine redis \
  --cache-node-type cache.t3.micro \
  --num-cache-clusters 2 \
  --snapshot-name bahnvision-prod-backup
```

This migration guide provides a comprehensive path from local development to production AWS deployment while maintaining the observability and resilience features demonstrated in the local environment.
