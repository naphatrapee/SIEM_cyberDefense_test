terraform {
  required_version = ">= 1.5"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.0" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
}

provider "aws" {
  region = var.region
}

# Latest Ubuntu 22.04 AMI via Canonical's public SSM parameter
data "aws_ssm_parameter" "ubuntu" {
  name = "/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id"
}

resource "random_password" "owner"  { 
  length  = 24
  special = false
}
resource "random_password" "app"    {
  length  = 24
  special = false
}
resource "random_password" "jwt"    {
  length  = 40
  special = false
}
resource "random_password" "admin"  {
  length  = 16
  special = false
}
resource "random_password" "viewer" {
  length  = 16
  special = false
}

resource "aws_security_group" "logdemo" {
  name_prefix = "logdemo-"
  description = "HTTPS/HTTP + syslog (+ optional SSH)"

  ingress {
    description = "HTTP (redirects to HTTPS, ACME challenge)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "Syslog UDP"
    from_port   = 514
    to_port     = 514
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "Syslog TCP"
    from_port   = 514
    to_port     = 514
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  dynamic "ingress" {
    for_each = var.ssh_cidr == "" ? [] : [var.ssh_cidr]
    content {
      description = "SSH"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "logdemo" {
  ami                    = data.aws_ssm_parameter.ubuntu.value
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.logdemo.id]

  root_block_device {
    volume_size = 40
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/user_data.sh.tpl", {
    repo_url      = var.repo_url
    domain        = var.domain
    duckdns_token = var.duckdns_token
    owner_pw      = random_password.owner.result
    app_pw        = random_password.app.result
    jwt           = random_password.jwt.result
    admin_pw      = random_password.admin.result
    viewer_pw     = random_password.viewer.result
  })

  tags = { Name = "logdemo" }
}

resource "aws_eip" "logdemo" {
  instance = aws_instance.logdemo.id
  domain   = "vpc"
}
