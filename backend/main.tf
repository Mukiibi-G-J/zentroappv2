# provider "aws" {
#   region = "us-east-2"
# }

# # resource "aws_ecr_repository" "zentro_backend" {
# #   name = "zentro-backend"
# # }
# resource "aws_vpc" "default" {
#   cidr_block = "10.0.0.0/16"
#   enable_dns_hostnames = true
#   enable_dns_support = true
#   tags = {
#     Name = "zentro-vpc"
#   }
# }

# # internet gateway to allow internet access
# resource "aws_internet_gateway" "default" {
#   vpc_id = aws_vpc.default.id
#   tags = {
#     Name = "zentro-internet-gateway"
#   }
# }

# # route table to allow internet access allows traffic to the internet gateway
# resource "aws_route_table" "default" {
#   vpc_id = aws_vpc.default.id
#   route {
#     cidr_block = "0.0.0.0/0"
#     gateway_id = aws_internet_gateway.default.id
#   }
#   tags = {
#     Name = "zentro-route-table"
#   }
# }

# # subnet to allow internet access
# resource "aws_subnet" "subnet_1" {
#   vpc_id = aws_vpc.default.id
#   cidr_block = "10.0.1.0/24"
#   map_public_ip_on_launch = false
#   availability_zone = "us-east-2a"
#   tags = {
#     Name = "zentro-public-subnet-1"
#   }
# }


# resource "aws_subnet" "subnet_2" {
#   vpc_id = aws_vpc.default.id
#   cidr_block = "10.0.2.0/24"
#   map_public_ip_on_launch = false
#   availability_zone = "us-east-2b"
#   tags = {
#     Name = "zentro-public-subnet-2"
#   }
# }


# resource "aws_route_table_association" "a" {
#   subnet_id = aws_subnet.subnet_1.id
#   route_table_id = aws_route_table.default.id
# }

# resource "aws_route_table_association" "b" {
#   subnet_id = aws_subnet.subnet_2.id
#   route_table_id = aws_route_table.default.id
# }

# # security group to allow inbound and outbound traffic
# resource "aws_security_group" "ec2_security_group" {
#   name = "ec2-security-group"
#   vpc_id = aws_vpc.default.id
  
#   # Allow SSH access
#   ingress {
#     from_port = 22
#     to_port = 22
#     protocol = "tcp"
#     cidr_blocks = ["0.0.0.0/0"]
#   }
  
#   # Allow HTTP access
#   ingress {
#     from_port = 80
#     to_port = 80
#     protocol = "tcp"
#     cidr_blocks = ["0.0.0.0/0"]
#   }
  
#   # Allow port 8000 for Django
#   ingress {
#     from_port = 8000
#     to_port = 8000
#     protocol = "tcp"
#     cidr_blocks = ["0.0.0.0/0"]
#   }
  
#   egress {
#     from_port = 0
#     to_port = 0
#     protocol = "-1"
#     cidr_blocks = ["0.0.0.0/0"]
#   }
  
#   tags = {
#     Name = "ec2-security-group"
#   }
# }


# variable "secret_key" {
#   description = "The Secret key for Django"
#   type = string
#   sensitive = true
# }

# resource "aws_instance" "web" {
#   ami = "ami-0e0bf53f6def86294"
#   instance_type = "t2.micro"
#   # key_name = "zentro-key"
#   vpc_security_group_ids = [aws_security_group.ec2_security_group.id]
#   subnet_id = aws_subnet.subnet_1.id

#   associate_public_ip_address = true
#   user_data_replace_on_change = true

#   iam_instance_profile = aws_iam_instance_profile.ec2_profile.name

#   user_data = <<EOF
# #!/bin/bash
# set -ex
# yum update -y
# yum install -y yum-utils

# # Install docker
# sudo yum install -y docker
# sudo systemctl start docker
# sudo systemctl enable docker

# # install aws cli
# sudo yum install -y aws-cli

# # Authenticate to ECR
# aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 311377958566.dkr.ecr.us-east-2.amazonaws.com

# # Pull the Docker image from ECR
# docker pull 311377958566.dkr.ecr.us-east-2.amazonaws.com/zentro-backend:latest

# # Run the Docker image with proper port mapping
# docker run -d \
#   -p 80:8000 \
#   --env SECRET_KEY=${var.secret_key} \
#   311377958566.dkr.ecr.us-east-2.amazonaws.com/zentro-backend:latest
# EOF

#   tags = {
#     Name = "zentro-web-server"
#   }
# }

# resource "aws_iam_role" "ec2_role" {
#   assume_role_policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Action = "sts:AssumeRole"
#         Effect = "Allow"
#         Principal = {
#           Service = "ec2.amazonaws.com"
#         },
#         Effect = "Allow",
#       }
#     ]
#   })
# }


# resource "aws_iam_role_policy_attachment" "ecr_read" {
#   role = aws_iam_role.ec2_role.name
#   policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
# }


# resource "aws_iam_instance_profile" "ec2_profile" {
#   name = "zentro-ec2-profile"
#   role = aws_iam_role.ec2_role.name
# }


