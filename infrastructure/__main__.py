# ============================================================================
# ModelServe — Pulumi Infrastructure
# ============================================================================
# Provisions AWS resources: VPC, EC2, S3, ECR, IAM
# ============================================================================

import os
import base64
import pulumi
import pulumi_aws as aws


# Configuration
config = pulumi.Config()
aws_region = config.get("aws_region", "ap-southeast-1")
ssh_public_key = os.environ.get("SSH_PUBLIC_KEY", "").encode().decode("unicode_escape")

# Tags - all resources tagged with Project=modelserve
tags = {"Project": "modelserve"}


# ─────────────────────────────────────────────────────────────
#  VPC and Networking
# ─────────────────────────────────────────────────────────────

# Create VPC
vpc = aws.ec2.Vpc(
    "modelserve-vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_hostnames=True,
    enable_dns_support=True,
    tags={**tags, "Name": "modelserve-vpc"},
)

# Create public subnet
subnet = aws.ec2.Subnet(
    "modelserve-subnet",
    vpc_id=vpc.id,
    cidr_block="10.0.1.0/24",
    availability_zone=f"{aws_region}a",
    map_public_ip_on_launch=True,
    tags={**tags, "Name": "modelserve-subnet"},
)

# Create Internet Gateway
igw = aws.ec2.InternetGateway(
    "modelserve-igw",
    vpc_id=vpc.id,
    tags={**tags, "Name": "modelserve-igw"},
)

# Create route table
route_table = aws.ec2.RouteTable(
    "modelserve-rt",
    vpc_id=vpc.id,
    routes=[
        {
            "cidr_block": "0.0.0.0/0",
            "gateway_id": igw.id,
        }
    ],
    tags={**tags, "Name": "modelserve-rt"},
)

# Associate route table with subnet
route_table_association = aws.ec2.RouteTableAssociation(
    "modelserve-rta",
    subnet_id=subnet.id,
    route_table_id=route_table.id,
)


# ─────────────────────────────────────────────────────────────
#  Security Group
# ─────────────────────────────────────────────────────────────

# Security group with required ports
sg = aws.ec2.SecurityGroup(
    "modelserve-sg",
    description="Security group for ModelServe services",
    vpc_id=vpc.id,
    ingress=[
        # SSH from anywhere (restrict in production)
        {"protocol": "tcp", "from_port": 22, "to_port": 22, "cidr_blocks": ["0.0.0.0/0"]},
        # FastAPI
        {"protocol": "tcp", "from_port": 8000, "to_port": 8000, "cidr_blocks": ["0.0.0.0/0"]},
        # Grafana
        {"protocol": "tcp", "from_port": 3000, "to_port": 3000, "cidr_blocks": ["0.0.0.0/0"]},
        # MLflow
        {"protocol": "tcp", "from_port": 5000, "to_port": 5000, "cidr_blocks": ["0.0.0.0/0"]},
        # Prometheus
        {"protocol": "tcp", "from_port": 9090, "to_port": 9090, "cidr_blocks": ["0.0.0.0/0"]},
    ],
    egress=[
        {"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]},
    ],
    tags={**tags, "Name": "modelserve-sg"},
)


# ─────────────────────────────────────────────────────────────
#  IAM Role and Profile
# ─────────────────────────────────────────────────────────────

# IAM role for EC2
role = aws.iam.Role(
    "modelserve-role",
    assume_role_policy="""{
        "Version": "2012-10-17",
        "Statement": [{
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {"Service": "ec2.amazonaws.com"}
        }]
    }""",
    tags=tags,
)

# Attach S3 full access policy
s3_policy = aws.iam.RolePolicyAttachment(
    "modelserve-s3-attachment",
    role=role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonS3FullAccess",
)

# Attach ECR access policy
ecr_policy = aws.iam.RolePolicyAttachment(
    "modelserve-ecr-attachment",
    role=role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryFullAccess",
)

# Instance profile
instance_profile = aws.iam.InstanceProfile(
    "modelserve-profile",
    role=role.name,
    tags=tags,
)


# ─────────────────────────────────────────────────────────────
#  EC2 Instance
# ─────────────────────────────────────────────────────────────

# Get latest Ubuntu AMI
ami = aws.get_ami(
    most_recent=True,
    owners=["099720109477"],
    filters=[{"name": "name", "values": ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-*"]}],
)

# User data script to install Docker and Docker Compose
user_data = """#!/bin/bash
set -e

# Update and install dependencies
apt-get update
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    build-essential

# Install Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add ubuntu user to docker group
usermod -aG docker ubuntu

# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
./aws/install

# Install Docker Compose (standalone)
curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Create app directory
mkdir -p /app
"""

# EC2 instance
instance = aws.ec2.Instance(
    "modelserve-ec2",
    ami=ami.id,
    instance_type="t3.small",
    subnet_id=subnet.id,
    vpc_security_group_ids=[sg.id],
    iam_instance_profile=instance_profile.name,
    user_data_base64=base64.b64encode(user_data.encode()).decode(),
    tags={**tags, "Name": "modelserve-ec2"},
    root_block_device={
        "volume_size": 30,
        "volume_type": "gp3",
    },
)

# Elastic IP
eip = aws.ec2.Eip(
    "modelserve-eip",
    instance=instance.id,
    domain="vpc",
    tags={**tags, "Name": "modelserve-eip"},
)


# ─────────────────────────────────────────────────────────────
#  S3 Bucket for MLflow Artifacts
# ─────────────────────────────────────────────────────────────

s3_bucket = aws.s3.Bucket(
    "modelserve-mlflow",
    bucket="modelserve-mlflow-artifacts",
    acl="private",
    tags={**tags, "Name": "modelserve-mlflow"},
)

# Prevent accidental deletion
aws.s3.BucketV2(
    "modelserve-mlflow-protection",
    bucket=s3_bucket.bucket,
    lifecycle_rules=[
        {
            "enabled": True,
            "expiration": 30,  # Days
        }
    ],
)


# ─────────────────────────────────────────────────────────────
#  ECR Repository
# ─────────────────────────────────────────────────────────────

ecr_repo = aws.ecr.Repository(
    "modelserve-ecr",
    name="fastapi-app",
    force_delete=True,  # Important: allows pulumi destroy to work
    image_tag_mutability="MUTABLE",
    image_scanning_configuration={
        "scan_on_push": True,
    },
    tags={**tags, "Name": "modelserve-ecr"},
)


# ─────────────────────────────────────────────────────────────
#  Outputs
# ─────────────────────────────────────────────────────────────

pulumi.export("instance_ip", eip.public_ip)
pulumi.export("instance_id", instance.id)
pulumi.export("vpc_id", vpc.id)
pulumi.export("subnet_id", subnet.id)
pulumi.export("security_group_id", sg.id)
pulumi.export("s3_bucket_name", s3_bucket.bucket)
pulumi.export("ecr_repository_url", ecr_repo.repository_url)
pulumi.export("ecr_registry", ecr_repo.repository_url.split("/")[0])