# FBA-Bench SaaS Infrastructure - Terraform Skeleton (AWS Example)
# This is a minimal, modular skeleton for Phase 0. Extend with variables.tf, outputs.tf, and modules in Phase 1.
# Assumes AWS provider; run 'terraform init' after creation. Cloud-agnostic by design – adapt for GCP.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.0"

  # Backend for state (S3 + DynamoDB for locking)
  backend "s3" {
    bucket         = "fba-bench-terraform-state"
    key            = "global/s3/terraform.tfstate"
    region         = "us-west-2"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}

# Variables (define in terraform.tfvars or via CLI)
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment (dev/stage/prod)"
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

# Core Networking: VPC, Subnets, Security Groups
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "fba-bench-${var.environment}"
  cidr = var.vpc_cidr

  azs             = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  enable_vpn_gateway = false

  tags = {
    Environment = var.environment
    Project     = "fba-bench-saas"
  }
}

# Security Groups
resource "aws_security_group" "api_sg" {
  name_prefix = "fba-api-${var.environment}-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [module.vpc.default_security_group_id]  # Internal only; use ALB for external
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Environment = var.environment
  }
}

resource "aws_security_group" "db_sg" {
  name_prefix = "fba-db-${var.environment}-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.api_sg.id]
  }

  tags = {
    Environment = var.environment
  }
}

resource "aws_security_group" "redis_sg" {
  name_prefix = "fba-redis-${var.environment}-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.api_sg.id]
  }

  tags = {
    Environment = var.environment
  }
}

# Database: RDS Postgres with RLS support
module "postgres" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier = "fba-bench-${var.environment}"

  engine               = "postgres"
  engine_version       = "15"
  family               = "postgres15"
  major_engine_version = "15"
  instance_class       = "db.t4g.micro"  # Scale up for prod

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "fba_bench"
  username = "fba_admin"
  password = var.db_password  # Use secrets manager in prod

  vpc_security_group_ids = [aws_security_group.db_sg.id]
  db_subnet_group_name   = module.vpc.database_subnet_group
  multi_az               = false  # Enable for prod HA

  backup_retention_period = 7
  skip_final_snapshot     = var.environment == "dev"
  deletion_protection     = var.environment != "dev"

  parameters = [
    { name = "rds.force_ssl", value = "0" },  # Disable for local-like dev
    { name = "log_statement", value = "all" }  # For audit
  ]

  tags = {
    Environment = var.environment
  }
}

# Object Storage: S3 for artifacts
resource "aws_s3_bucket" "artifacts" {
  bucket = "fba-bench-artifacts-${var.environment}-${random_id.bucket_suffix.hex}"
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket_versioning" "artifacts_versioning" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts_encryption" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts_block" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# IAM Roles for ECS Tasks (API, Runners)
resource "aws_iam_role" "ecs_task_role" {
  name = "fba-ecs-task-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "ecs_task_s3_policy" {
  name = "fba-ecs-s3-${var.environment}"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.artifacts.arn,
          "${aws_s3_bucket.artifacts.arn}/*"
        ]
      }
    ]
  })
}

# ECS Cluster for API and Runners
resource "aws_ecs_cluster" "fba_cluster" {
  name = "fba-bench-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Environment = var.environment
  }
}

# Application Load Balancer for API
resource "aws_lb" "api_alb" {
  name               = "fba-api-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.api_sg.id]
  subnets            = module.vpc.public_subnets

  tags = {
    Environment = var.environment
  }
}

resource "aws_lb_target_group" "api_tg" {
  name     = "fba-api-${var.environment}"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = module.vpc.vpc_id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/api/v1/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }

  tags = {
    Environment = var.environment
  }
}

resource "aws_lb_listener" "api_https" {
  load_balancer_arn = aws_lb.api_alb.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  certificate_arn   = var.acm_certificate_arn  # Request via ACM

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api_tg.arn
  }
}

# Outputs
output "vpc_id" {
  value = module.vpc.vpc_id
}

output "postgres_endpoint" {
  value = module.postgres.db_instance_endpoint
}

output "s3_bucket_name" {
  value = aws_s3_bucket.artifacts.id
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.fba_cluster.name
}

output "alb_dns_name" {
  value = aws_lb.api_alb.dns_name
}