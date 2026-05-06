#!/bin/bash
# ============================================================
# ModelServe — complete VM bootstrap
# Usage: bash setup.sh  
# ============================================================
set -e

AWS_KEY="${1}"
AWS_SECRET="${2}"
REPO_URL="https://github.com/aunjum/MLOps-S2-Exam1-modelserve-capstone.git"
REPO_DIR="MLOps-S2-Exam1-modelserve-capstone"
VENV_DIR="mlops_venv"

echo "========================================"
echo "  ModelServe — VM Bootstrap"
echo "========================================"

# ── 1. System packages ────────────────────────────────────
echo ""
echo "[1/9] Installing system packages..."
sudo apt update -y -q
sudo apt install -y -q \
  python3.12-venv \
  python3-pip \
  unzip \
  curl \
  git-lfs

# ── 2. AWS CLI v2 ─────────────────────────────────────────
echo ""
echo "[2/9] Installing AWS CLI v2..."
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

# ── 3. Clone or pull repo ─────────────────────────────────
echo ""
echo "[3/9] Setting up repository..."
if [ ! -d "$REPO_DIR" ]; then
  git clone "$REPO_URL"
  echo "  Cloned fresh repo."
else
  echo "  Repo exists — pulling latest..."
  cd "$REPO_DIR"
  git pull
  cd ..
fi
cd "$REPO_DIR"

# ── 4. Git config + LFS ───────────────────────────────────
echo ""
echo "[4/9] Configuring git..."
git config --global user.email "tanviraunjum030@gmail.com"
git config --global user.name "aunjum"
# git config --global http.postBuffer 524288000
git lfs install --silent

# ── 5. AWS credentials ────────────────────────────────────
echo ""
echo "[5/9] Setting AWS credentials..."
if [ -z "$AWS_KEY" ] || [ -z "$AWS_SECRET" ]; then
  echo "  WARNING: No credentials passed — skipping."
  echo "  Run manually: aws configure set aws_access_key_id "
else
  aws configure set aws_access_key_id     "$AWS_KEY"
  aws configure set aws_secret_access_key "$AWS_SECRET"
  aws configure set default.region        ap-southeast-1
  aws configure set default.output        json
  echo "  Credentials set."
  aws sts get-caller-identity --query "Account" --output text 2>/dev/null \
    && echo "  AWS auth: OK" || echo "  AWS auth: FAILED — check credentials"
fi

# ── 6. Python venv ────────────────────────────────────────
echo ""
echo "[6/9] Creating Python venv..."
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

# force correct protobuf AFTER all installs (feast may downgrade it)
pip install "protobuf>=4.25.0,<6.0.0" --force-reinstall -q
# force mlflow version that supports protobuf 5.x
pip install "mlflow==2.15.1" -q

echo "  Python packages installed."

# ── 7. .env setup ─────────────────────────────────────────
echo ""
echo "[7/9] Setting up .env..."
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "  Copied .env.example → .env"
  else
    echo "  WARNING: .env.example not found. Creating minimal .env..."
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
S3_BUCKET_NAME=FraudDetector
DATA_PATH=training/fraudTrain.csv
ENVEOF
  fi
else
  echo "  .env already exists — keeping it."
fi

# inject AWS creds into .env if provided
if [ -n "$AWS_KEY" ] && [ -n "$AWS_SECRET" ]; then
  # remove old entries then append fresh ones
  grep -v "^AWS_ACCESS_KEY_ID\|^AWS_SECRET_ACCESS_KEY" .env > .env.tmp
  mv .env.tmp .env
  echo "AWS_ACCESS_KEY_ID=${AWS_KEY}"     >> .env
  echo "AWS_SECRET_ACCESS_KEY=${AWS_SECRET}" >> .env
  echo "  AWS credentials written to .env"
fi

# make sure .env is gitignored
grep -q "^\.env$" .gitignore 2>/dev/null || echo ".env" >> .gitignore

# ── 8. Feast repo files ───────────────────────────────────
echo ""
echo "[8/9] Checking feast_repo..."
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
else
  echo "  feature_store.yaml exists — skipping."
fi

if [ ! -f "feast_repo/feature_definitions.py" ]; then
  echo "  Creating feature_definitions.py..."
  cat > feast_repo/feature_definitions.py << 'EOF'
from datetime import timedelta
from feast import Entity, FeatureView, Field, FileSource
from feast.types import Float64, Int64

cc_num = Entity(
    name="cc_num",
    description="Credit card number — primary entity key",
)

fraud_source = FileSource(
    path="training/features.parquet",
    timestamp_field="event_timestamp",
)

fraud_features = FeatureView(
    name="fraud_features",
    entities=[cc_num],
    ttl=timedelta(days=365),
    schema=[
        Field(name="amt",          dtype=Float64),
        Field(name="category_enc", dtype=Int64),
        Field(name="trans_hour",   dtype=Int64),
        Field(name="trans_dow",    dtype=Int64),
        Field(name="city_pop",     dtype=Int64),
        Field(name="merch_lat",    dtype=Float64),
        Field(name="merch_long",   dtype=Float64),
    ],
    source=fraud_source,
)
EOF
else
  echo "  feature_definitions.py exists — skipping."
fi

# ── 9. Docker services ────────────────────────────────────
echo ""
echo "[9/9] Starting Docker services..."
docker compose up -d
echo "  Waiting 20s for services to become healthy..."
sleep 20
docker compose ps

# ── Done ──────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  Setup complete!"
echo "========================================"
echo ""
echo "  Tool versions:"
docker --version
docker compose version
python3 --version
git --version
aws --version 2>/dev/null || echo "aws: not found"
echo ""
echo "  Next steps:"
echo "  1. source $VENV_DIR/bin/activate"
echo "  2. export \$(grep -v '^#' .env | grep -v '^\$' | xargs)"
echo "  3. python3 training/train.py"
echo "  4. python3 training/generate_features.py"
echo "  5. cd feast_repo && feast apply"
echo "  6. feast materialize-incremental \$(date -u +'%Y-%m-%dT%H:%M:%S')"
echo "  7. cd .."
echo ""
echo "  MLflow UI : http://localhost:5000"
echo "  Grafana   : http://localhost:3000  (Session 4)"
echo "========================================"