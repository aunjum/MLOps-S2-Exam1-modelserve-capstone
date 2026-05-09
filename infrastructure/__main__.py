# ============================================================================
# ModelServe — Pulumi Infrastructure
# ============================================================================
# AWS Infrastructure:
# - VPC
# - Public Subnet
# - Internet Gateway
# - Route Table
# - Security Group
# - IAM Role + Instance Profile
# - EC2 Instance
# - Elastic IP
# - Existing S3 Bucket Import
# - ECR Repository
# ============================================================================

import os
import base64
import pulumi
import pulumi_aws as aws


# ============================================================================
# Configuration
# ============================================================================

config = pulumi.Config()

aws_region = config.get("aws_region") or "ap-southeast-1"

tags = {
    "Project": "modelserve"
}


# ============================================================================
# Networking
# ============================================================================

vpc = aws.ec2.Vpc(
    "modelserve-vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_support=True,
    enable_dns_hostnames=True,
    tags={
        **tags,
        "Name": "modelserve-vpc",
    },
)

subnet = aws.ec2.Subnet(
    "modelserve-subnet",
    vpc_id=vpc.id,
    cidr_block="10.0.1.0/24",
    map_public_ip_on_launch=True,
    availability_zone=f"{aws_region}a",
    tags={
        **tags,
        "Name": "modelserve-subnet",
    },
)

igw = aws.ec2.InternetGateway(
    "modelserve-igw",
    vpc_id=vpc.id,
    tags={
        **tags,
        "Name": "modelserve-igw",
    },
)

route_table = aws.ec2.RouteTable(
    "modelserve-rt",
    vpc_id=vpc.id,
    routes=[
        aws.ec2.RouteTableRouteArgs(
            cidr_block="0.0.0.0/0",
            gateway_id=igw.id,
        )
    ],
    tags={
        **tags,
        "Name": "modelserve-rt",
    },
)

aws.ec2.RouteTableAssociation(
    "modelserve-rta",
    subnet_id=subnet.id,
    route_table_id=route_table.id,
)


# ============================================================================
# Security Group
# ============================================================================

security_group = aws.ec2.SecurityGroup(
    "modelserve-sg",
    description="Security group for ModelServe",
    vpc_id=vpc.id,

    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=22,
            to_port=22,
            cidr_blocks=["0.0.0.0/0"],
            description="SSH",
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=8000,
            to_port=8000,
            cidr_blocks=["0.0.0.0/0"],
            description="FastAPI",
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=3000,
            to_port=3000,
            cidr_blocks=["0.0.0.0/0"],
            description="Grafana",
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=5000,
            to_port=5000,
            cidr_blocks=["0.0.0.0/0"],
            description="MLflow",
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=9090,
            to_port=9090,
            cidr_blocks=["0.0.0.0/0"],
            description="Prometheus",
        ),
    ],

    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],
        )
    ],

    tags={
        **tags,
        "Name": "modelserve-sg",
    },
)


# ============================================================================
# IAM Role + Instance Profile
# ============================================================================

role = aws.iam.Role(
    "modelserve-role",
    assume_role_policy="""{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {
                "Service": "ec2.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }]
    }""",
    tags=tags,
)

aws.iam.RolePolicyAttachment(
    "modelserve-s3-policy",
    role=role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonS3FullAccess",
)

aws.iam.RolePolicyAttachment(
    "modelserve-ecr-policy",
    role=role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryFullAccess",
)

instance_profile = aws.iam.InstanceProfile(
    "modelserve-profile",
    role=role.name,
)


# ============================================================================
# Ubuntu AMI
# ============================================================================

ami = aws.ec2.get_ami(
    most_recent=True,
    owners=["099720109477"],
    filters=[
        {
            "name": "name",
            "values": [
                "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"
            ],
        }
    ],
)


# ============================================================================
# User Data
# ============================================================================

user_data = """#!/bin/bash
set -e

apt-get update

apt-get install -y \
    curl \
    unzip \
    docker.io \
    docker-compose-v2

systemctl enable docker
systemctl start docker

usermod -aG docker ubuntu

mkdir -p /app
"""


# ============================================================================
# EC2 Instance
# ============================================================================

instance = aws.ec2.Instance(
    "modelserve-ec2",
    ami=ami.id,
    instance_type="t3.small",

    subnet_id=subnet.id,

    vpc_security_group_ids=[
        security_group.id
    ],

    iam_instance_profile=instance_profile.name,

    user_data_base64=base64.b64encode(
        user_data.encode()
    ).decode(),

    root_block_device=aws.ec2.InstanceRootBlockDeviceArgs(
        volume_size=30,
        volume_type="gp3",
    ),

    tags={
        **tags,
        "Name": "modelserve-ec2",
    },
)


# ============================================================================
# Elastic IP
# ============================================================================

eip = aws.ec2.Eip(
    "modelserve-eip",
    instance=instance.id,
    domain="vpc",
    tags={
        **tags,
        "Name": "modelserve-eip",
    },
)


# ============================================================================
# Existing S3 Bucket Import
# ============================================================================

s3_bucket = aws.s3.Bucket(
    "modelserve-mlflow",
    bucket="modelserve-mlflow-artifacts",

    tags={
        **tags,
        "Name": "modelserve-mlflow",
    },

    # opts=pulumi.ResourceOptions(
    #     import_="modelserve-mlflow-artifacts"
    # ),
)

aws.s3.BucketAcl(
    "modelserve-mlflow-acl",
    bucket=s3_bucket.id,
    acl="private",
)

aws.s3.BucketLifecycleConfiguration(
    "modelserve-mlflow-lifecycle",
    bucket=s3_bucket.id,

    rules=[
        aws.s3.BucketLifecycleConfigurationV2RuleArgs(
            id="cleanup-old-artifacts",
            status="Enabled",

            expiration=aws.s3.BucketLifecycleConfigurationV2RuleExpirationArgs(
                days=30
            ),
        )
    ],
)


# ============================================================================
# ECR Repository
# ============================================================================

ecr_repo = aws.ecr.Repository(
    "modelserve-ecr",

    name="fastapi-app",

    force_delete=True,

    image_tag_mutability="MUTABLE",

    image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
        scan_on_push=True
    ),

    tags={
        **tags,
        "Name": "modelserve-ecr",
    },
)


# ============================================================================
# Outputs
# ============================================================================

pulumi.export("instance_ip", eip.public_ip)

pulumi.export("instance_id", instance.id)

pulumi.export("vpc_id", vpc.id)

pulumi.export("subnet_id", subnet.id)

pulumi.export("security_group_id", security_group.id)

pulumi.export("s3_bucket_name", s3_bucket.bucket)

pulumi.export(
    "ecr_repository_url",
    ecr_repo.repository_url
)

pulumi.export(
    "ecr_registry",
    ecr_repo.repository_url.apply(
        lambda url: url.split("/")[0]
    )
)