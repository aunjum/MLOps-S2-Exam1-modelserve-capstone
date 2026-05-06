# ModelServe — Command Reference

This file contains all commands you need to test and run the project locally and on AWS.

---

## Part 1: Local Development Commands

### 1.1 Setup Environment

```bash
# Go to project root
cd /home/poridhian/code/MLOps-S2-Exam1-modelserve-capstone

# Create virtual environment (one time)
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file (one time)
cp .env.example .env
```

### 1.2 Run Local Stack with Docker

```bash
# Start all services (PostgreSQL, Redis, MLflow, FastAPI, Prometheus, Grafana)
docker compose up -d

# Check service status
docker compose ps

# View logs (all services)
docker compose logs -f

# View logs (specific service)
docker compose logs -f fastapi
docker compose logs -f mlflow
docker compose logs -f redis

# Stop all services
docker compose down

# Stop and remove volumes (clears all data)
docker compose down -v
```

### 1.3 Setup Feast Features

```bash
# Initialize Feast (register features)
cd /home/poridhian/code/MLOps-S2-Exam1-modelserve-capstone/feast_repo
feast apply

# Materialize features to Redis (load data for online serving)
feast materialize --start-date 2024-01-01 --end-date 2025-01-01
```

### 1.4 Train Model

```bash
# Train model and register to MLflow
cd /home/poridhian/code/MLOps-S2-Exam1-modelserve-capstone
python training/train.py
```

### 1.5 Test API Endpoints

```bash
# Check health
curl http://localhost:8000/health

# Root endpoint
curl http://localhost:8000/

# Predict (POST)
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"entity_id": 4613314721966}'

# Predict (GET with explain)
curl "http://localhost:8000/predict/4613314721966?explain=true"

# Get metrics
curl http://localhost:8000/metrics
```

### 1.6 Run Tests

```bash
# Run all tests
pytest app/tests/ -v

# Run specific test file
pytest app/tests/test_predict.py -v

# Run single test
pytest app/tests/test_predict.py::test_predict_returns_200 -v
```

### 1.7 Access Web UIs (Local)

| Service | URL | Default Login |
|---------|-----|---------------|
| FastAPI | http://localhost:8000 | - |
| MLflow | http://localhost:5000 | - |
| Grafana | http://localhost:3000 | admin/admin |
| Prometheus | http://localhost:9090 | - |

---

## Part 2: AWS Commands

### 2.1 Setup AWS Credentials

```bash
# Configure AWS CLI (use your credentials)
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_DEFAULT_REGION="ap-southeast-1"
```

### 2.2 Create AWS Infrastructure (Pulumi)

```bash
# Go to infrastructure folder
cd /home/poridhian/code/MLOps-S2-Exam1-modelserve-capstone/infrastructure

# Install Pulumi dependencies
pip install -r requirements.txt

# Preview what will be created
pulumi preview

# Create resources (answer "yes" when prompted)
pulumi up

# Note the outputs (instance IP, S3 bucket, ECR URL)
# You'll need: instance_ip, ecr_repository_url, s3_bucket_name
```

### 2.3 Connect to EC2

```bash
# SSH into EC2 (replace with your instance IP)
ssh -i /path/to/your-key.pem ubuntu@<INSTANCE_IP>

# Once logged in, check Docker is running
docker --version
docker-compose --version
```

### 2.4 Deploy to EC2 (Manual)

```bash
# On EC2 instance - create app directory
mkdir -p ~/app
cd ~/app

# Copy files from local to EC2 (run on LOCAL machine)
scp -i /path/to/key.pem -r docker-compose.yml ubuntu@<IP>:~/
scp -i /path/to/key.pem -r monitoring ubuntu@<IP>:~/
scp -i /path/to/key.pem -r feast_repo ubuntu@<IP>:~/
scp -i /path/to/key.pem -r app ubuntu@<IP>:~/
scp -i /path/to/key.pem -r Dockerfile ubuntu@<IP>:~/
scp -i /path/to/key.pem -r training ubuntu@<IP>:~/
scp -i /path/to/key.pem -r .env ubuntu@<IP>:~/

# On EC2 - Login to ECR
aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin <ECR_REGISTRY_URL>

# On EC2 - Start services
docker-compose up -d

# On EC2 - Check status
docker-compose ps
docker-compose logs -f
```

### 2.5 Test Production API

```bash
# Replace <INSTANCE_IP> with your EC2 IP
curl http://<INSTANCE_IP>:8000/health
curl -X POST http://<INSTANCE_IP>:8000/predict -H "Content-Type: application/json" -d '{"entity_id": 4613314721966}'
```

### 2.6 Access Production Web UIs

| Service | URL |
|---------|-----|
| FastAPI | http://<INSTANCE_IP>:8000 |
| MLflow | http://<INSTANCE_IP>:5000 |
| Grafana | http://<INSTANCE_IP>:3000 (admin/admin) |
| Prometheus | http://<INSTANCE_IP>:9090 |

### 2.7 AWS Cleanup (Destroy Infrastructure)

```bash
# WARNING: This deletes everything!
cd /home/poridhian/code/MLOps-S2-Exam1-modelserve-capstone/infrastructure
pulumi destroy
```

---

## Part 3: Troubleshooting Commands

### 3.1 Check Service Health

```bash
# All containers running?
docker compose ps

# Specific service healthy?
docker compose exec fastapi curl -f http://localhost:8000/health
docker compose exec redis redis-cli ping
docker compose exec postgres pg_isready -U mlflow
```

### 3.2 View Logs

```bash
# All services
docker compose logs

# Last 100 lines
docker compose logs --tail=100

# Follow specific service
docker compose logs -f fastapi
```

### 3.3 Common Fixes

```bash
# Restart a service
docker compose restart fastapi

# Rebuild after code changes
docker compose build fastapi
docker compose up -d

# Clear Feast registry and re-apply
rm feast_repo/registry.db
feast apply

# Clear MLflow data
docker compose down -v
docker compose up -d
```

---

## Part 4: GitHub Actions (CI/CD)

The pipeline runs automatically when you push to main branch:

1. **Test** - Runs pytest
2. **Build & Push** - Builds Docker image, pushes to ECR
3. **Deploy** - SSH to EC2, pulls image, restarts services

Required GitHub secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `ECR_REGISTRY`
- `EC2_HOST`
- `EC2_USER`
- `EC2_SSH_KEY`

---

## Quick Reference Card

```bash
# START EVERYTHING (local)
source .venv/bin/activate
docker compose up -d
feast apply
feast materialize --start-date 2024-01-01 --end-date 2025-01-01
python training/train.py

# TEST
curl http://localhost:8000/health
curl -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d '{"entity_id": 4613314721966}'
pytest app/tests/ -v

# STOP
docker compose down
```