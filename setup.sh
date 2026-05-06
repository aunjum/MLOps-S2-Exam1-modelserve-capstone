#!/bin/bash
# ============================================================
# ModelServe — VM bootstrap (run from repo root)
# Usage: bash setup.sh <AWS_ACCESS_KEY> <AWS_SECRET_ACCESS_KEY>
# Prereq: Repo must already be cloned
# ============================================================
set -e

AWS_KEY="${1}"
AWS_SECRET="${2}"
VENV_DIR="mlops_venv"

# Check we're in the right place
if [ ! -f "docker-compose.yml" ]; then
  echo "ERROR: docker-compose.yml not found."
  echo "Run this script from the repo root directory."
  exit 1
fi

echo "========================================"
echo "  ModelServe — VM Bootstrap"
echo "========================================"

# ── 1. System packages ────────────────────────────────────
echo ""
echo "[1/11] Installing system packages..."
sudo apt update -y -q
sudo apt install -y -q \
  python3.12-venv \
  python3-pip \
  unzip \
  curl \
  git-lfs \
  redis-tools \
  postgresql-client

# ── 2. AWS CLI v2 ─────────────────────────────────────────
echo ""
echo "[2/11] Installing AWS CLI v2..."
if ! command -v aws &> /dev/null; then
  curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" \
    -o /tmp/awscliv2.zip
  unzip -q /tmp/awscliv2.zip -d /tmp/
  sudo /tmp/aws/install --update
  rm -rf /tmp/aws /tmp/awscliv2.zip
  echo "  AWS CLI installed."
else
  echo "  AWS CLI already installed — skipping."
fi

# ── 3. Pulumi ─────────────────────────────────────────────
echo ""
echo "[3/11] Installing Pulumi..."
if ! command -v pulumi &> /dev/null; then
  curl -fsSL https://get.pulumi.com | sh
  export PATH="$PATH:$HOME/.pulumi/bin"
  echo "export PATH=\$PATH:\$HOME/.pulumi/bin" >> ~/.bashrc
  echo "  Pulumi installed."
else
  echo "  Pulumi already installed — skipping."
  export PATH="$PATH:$HOME/.pulumi/bin"
fi
pulumi version

# ── 4. Git LFS ────────────────────────────────────────────
echo ""
echo "[4/11] Setting up git LFS..."
git lfs install
git lfs pull  # Fetch LFS data files (fraudTrain.csv, fraudTest.csv)

# ── 5. .env setup ─────────────────────────────────────────
echo ""
echo "[5/11] Setting up .env file..."
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "  Copied .env.example → .env"
  else
    echo "  Creating minimal .env..."
    cat > .env << 'ENVEOF'
POSTGRES_USER=mlflow
POSTGRES_PASSWORD=mlflow
POSTGRES_DB=mlflow
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
MLFLOW_TRACKING_URI=http://localhost:5000
MLFLOW_ARTIFACT_ROOT=/mlflow/artifacts
MODEL_NAME=FraudDetector
MODEL_STAGE=Production
APP_HOST=0.0.0.0
APP_PORT=8000
REDIS_HOST=redis
REDIS_PORT=6379
FEAST_REPO_PATH=./feast_repo
GF_SECURITY_ADMIN_PASSWORD=admin
GF_USERS_ALLOW_SIGN_UP=false
AWS_DEFAULT_REGION=ap-southeast-1
S3_BUCKET_NAME=
DATA_PATH=training/fraudTrain.csv
ENVEOF
  fi
else
  echo "  .env already exists — keeping it."
fi

# make sure .env is gitignored
grep -q "^\.env$" .gitignore 2>/dev/null || echo ".env" >> .gitignore

# ── 6. AWS credentials ─────────────────────────────────────
echo ""
echo "[6/11] Setting AWS credentials..."
if [ -z "$AWS_KEY" ] || [ -z "$AWS_SECRET" ]; then
  echo "  WARNING: No credentials passed — skipping AWS config."
else
  # Inject into .env
  grep -v "^AWS_ACCESS_KEY_ID\|^AWS_SECRET_ACCESS_KEY" .env > .env.tmp 2>/dev/null || true
  mv .env.tmp .env 2>/dev/null || true
  echo "AWS_ACCESS_KEY_ID=${AWS_KEY}" >> .env
  echo "AWS_SECRET_ACCESS_KEY=${AWS_SECRET}" >> .env
  echo "  AWS credentials written to .env"

  # Configure AWS CLI
  aws configure set aws_access_key_id "$AWS_KEY"
  aws configure set aws_secret_access_key "$AWS_SECRET"
  aws configure set default.region ap-southeast-1
  aws configure set default.output json
  echo "  AWS CLI configured."

  aws sts get-caller-identity --query "Account" --output text 2>/dev/null \
    && echo "  AWS auth: OK" || echo "  AWS auth: FAILED"
fi

# ── 7. Python venv ────────────────────────────────────────
echo ""
echo "[7/11] Creating Python venv..."
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
  echo "  venv created."
else
  echo "  venv already exists — reusing."
fi
source "$VENV_DIR/bin/activate"

pip install --upgrade pip setuptools wheel "setuptools<81" -q
pip install "protobuf>=4.25.0,<6.0.0" -q
pip install -r requirements.txt -q

# Force correct protobuf after all installs
pip install "protobuf>=4.25.0,<6.0.0" --force-reinstall -q
pip install "mlflow==2.15.1" -q

echo "  Python packages installed."

# ── 8. Feast repo files ───────────────────────────────────
echo ""
echo "[8/11] Checking feast_repo..."
mkdir -p feast_repo/data

if [ ! -f "feast_repo/feature_store.yaml" ]; then
  echo "  Creating feature_store.yaml..."
  cat > feast_repo/feature_store.yaml << 'EOF'
project: modelserve
registry: feast_repo/data/registry.db
provider: local
online_store:
  type: redis
  connection_string: localhost:6379
offline_store:
  type: file
entity_key_serialization_version: 2
EOF
fi

if [ ! -f "feast_repo/feature_definitions.py" ]; then
  echo "  Creating feature_definitions.py..."
  cat > feast_repo/feature_definitions.py << 'EOF'
from datetime import timedelta
from feast import Entity, FeatureView, Field, FileSource
from feast.types import Float64, Int64

cc_num = Entity(name="cc_num", description="Credit card number")

fraud_source = FileSource(
    path="training/features.parquet",
    timestamp_field="event_timestamp",
)

fraud_features = FeatureView(
    name="fraud_features",
    entities=[cc_num],
    ttl=timedelta(days=365),
    schema=[
        Field(name="amt", dtype=Float64),
        Field(name="category_enc", dtype=Int64),
        Field(name="trans_hour", dtype=Int64),
        Field(name="trans_dow", dtype=Int64),
        Field(name="city_pop", dtype=Int64),
        Field(name="merch_lat", dtype=Float64),
        Field(name="merch_long", dtype=Float64),
    ],
    source=fraud_source,
)
EOF
fi

# ── 9. Docker services ───────────────────────────────────
echo ""
echo "[9/11] Starting Docker services..."
docker compose up -d
echo "  Waiting 30s for services to become healthy..."
sleep 30
docker compose ps

# Fix permissions for feast_repo (container needs write access)
chmod -R 777 feast_repo/

# ── 10. Train model + generate features ──────────────────
echo ""
echo "[10/11] Training model..."
source "$VENV_DIR/bin/activate"
export $(grep -v '^#' .env | grep -v '^\$' | xargs)

if [ ! -f "training/fraudTrain.csv" ]; then
  echo "  WARNING: training/fraudTrain.csv not found. Skipping training."
  echo "  Place your Kaggle fraud data in training/fraudTrain.csv"
else
  python3 training/train.py  # train.py also generates features.parquet
fi

# ── 11. Feast apply + materialize ─────────────────────────
echo ""
echo "[11/11] Setting up Feast..."
cd feast_repo
feast apply
TIMESTAMP=$(date -u +'%Y-%m-%dT%H:%M:%S')
feast materialize-incremental "$TIMESTAMP"
cd ..

# ── Done ──────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  Setup complete!"
echo "========================================"
echo ""
echo "  Services:"
echo "  - FastAPI:    http://localhost:8000"
echo "  - MLflow:     http://localhost:5000"
echo "  - Grafana:    http://localhost:3000 (admin/admin)"
echo "  - Prometheus: http://localhost:9090"
echo ""
echo "  Test:"
echo "  curl http://localhost:8000/health"
echo "========================================"