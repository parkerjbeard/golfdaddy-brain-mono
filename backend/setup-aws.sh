#!/bin/bash
# AWS EC2 Setup Script for GolfDaddy Brain

set -e

echo "🚀 GolfDaddy Brain AWS Setup"
echo "============================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check if running on EC2
if [ -f /sys/hypervisor/uuid ] && [ `head -c 3 /sys/hypervisor/uuid` == ec2 ]; then
    print_status "Running on AWS EC2"
else
    print_warning "Not running on EC2, but continuing anyway..."
fi

# Get instance metadata (if on EC2)
if command -v ec2-metadata &> /dev/null; then
    INSTANCE_ID=$(ec2-metadata --instance-id | cut -d " " -f 2)
    PUBLIC_IP=$(ec2-metadata --public-ipv4 | cut -d " " -f 2)
    print_status "Instance ID: $INSTANCE_ID"
    print_status "Public IP: $PUBLIC_IP"
fi

# Create necessary directories
print_status "Creating directories..."
mkdir -p data backups logs ssl
chmod 755 data backups logs
chmod 700 ssl

# Check Docker installation
if ! command -v docker &> /dev/null; then
    print_error "Docker not installed. Please run:"
    echo "curl -fsSL https://get.docker.com -o get-docker.sh"
    echo "sudo sh get-docker.sh"
    echo "sudo usermod -aG docker ubuntu"
    exit 1
fi

# Check Docker Compose installation
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose not installed. Please run:"
    echo "sudo curl -L \"https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)\" -o /usr/local/bin/docker-compose"
    echo "sudo chmod +x /usr/local/bin/docker-compose"
    exit 1
fi

# Setup .env file
if [ ! -f .env ]; then
    print_warning "Creating .env file from example..."
    cp .env.example .env
    
    # Try to get region from instance metadata
    if command -v ec2-metadata &> /dev/null; then
        REGION=$(ec2-metadata --availability-zone | cut -d " " -f 2 | sed 's/[a-z]$//')
        sed -i "s/AWS_REGION=.*/AWS_REGION=$REGION/" .env
    fi
    
    echo ""
    print_warning "Please edit .env file with your API keys:"
    echo "  - OPENAI_API_KEY"
    echo "  - SLACK_BOT_TOKEN (if using Slack)"
    echo "  - SUPABASE_URL & SUPABASE_KEY (if using Supabase)"
    echo ""
    echo "Press Enter to edit .env file..."
    read
    nano .env
else
    print_status ".env file already exists"
fi

# Generate self-signed SSL certificate (for HTTPS)
if [ ! -f ssl/cert.pem ]; then
    print_status "Generating self-signed SSL certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout ssl/key.pem -out ssl/cert.pem \
        -subj "/C=US/ST=State/L=City/O=Company/CN=localhost"
    chmod 600 ssl/*
fi

# Create nginx configuration
print_status "Creating nginx configuration..."
cat > nginx-aws.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream app {
        server app:8000;
    }

    server {
        listen 80;
        server_name _;
        
        # Redirect HTTP to HTTPS
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl;
        server_name _;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        client_max_body_size 10M;

        location / {
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 300s;
            proxy_connect_timeout 75s;
        }

        location /health {
            access_log off;
            proxy_pass http://app/health;
        }
    }
}
EOF

# Create AWS-optimized docker-compose
print_status "Creating AWS-optimized docker-compose..."
cat > docker-compose.aws.yml << 'EOF'
version: '3.8'

services:
  app:
    build: .
    volumes:
      - ./data:/app/data
      - ./.env:/app/.env
    environment:
      - DATABASE_URL=sqlite:///app/data/golfdaddy.db
      - ENVIRONMENT=production
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx-aws.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - app
    restart: unless-stopped

volumes:
  app_data:
EOF

# Setup systemd service for auto-start
print_status "Setting up systemd service..."
sudo tee /etc/systemd/system/golfdaddy.service > /dev/null << EOF
[Unit]
Description=GolfDaddy Brain
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$(pwd)
ExecStart=/usr/local/bin/docker-compose -f docker-compose.aws.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.aws.yml down
StandardOutput=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable golfdaddy.service

# Setup daily backups
print_status "Setting up daily backups..."
(crontab -l 2>/dev/null || true; echo "0 2 * * * cd $(pwd) && ./scripts/backup.sh >> logs/backup.log 2>&1") | crontab -

# Setup log rotation
print_status "Setting up log rotation..."
sudo tee /etc/logrotate.d/golfdaddy > /dev/null << EOF
$(pwd)/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 ubuntu ubuntu
}
EOF

# Build and start application
print_status "Building and starting application..."
docker-compose -f docker-compose.aws.yml build
docker-compose -f docker-compose.aws.yml up -d

# Wait for services to start
echo ""
print_status "Waiting for services to start..."
sleep 10

# Check if services are running
if curl -k -f https://localhost/health > /dev/null 2>&1; then
    print_status "Application is running!"
else
    print_error "Application failed to start. Check logs:"
    echo "docker-compose -f docker-compose.aws.yml logs"
    exit 1
fi

# Setup AWS CLI (if available)
if command -v aws &> /dev/null; then
    print_status "AWS CLI detected. Setting up S3 backup..."
    
    # Create S3 bucket for backups (optional)
    read -p "Do you want to create an S3 bucket for backups? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter S3 bucket name: " BUCKET_NAME
        aws s3 mb s3://$BUCKET_NAME --region $REGION 2>/dev/null || print_warning "Bucket already exists or creation failed"
        echo "S3_BACKUP_BUCKET=$BUCKET_NAME" >> .env
    fi
fi

# Print summary
echo ""
echo "========================================"
print_status "Setup complete!"
echo "========================================"
echo ""
echo "🌐 Access your application:"
if [ ! -z "$PUBLIC_IP" ]; then
    echo "   https://$PUBLIC_IP"
    echo "   https://$PUBLIC_IP/docs (API documentation)"
else
    echo "   https://your-ec2-ip"
    echo "   https://your-ec2-ip/docs (API documentation)"
fi
echo ""
echo "⚠️  Note: You'll see a certificate warning because we're using a self-signed certificate."
echo "   This is normal for internal tools. Click 'Advanced' and 'Proceed' to continue."
echo ""
echo "📋 Useful commands:"
echo "   View logs:       docker-compose -f docker-compose.aws.yml logs -f"
echo "   Restart:         docker-compose -f docker-compose.aws.yml restart"
echo "   Stop:            docker-compose -f docker-compose.aws.yml down"
echo "   Backup:          ./scripts/backup.sh"
echo "   Update:          git pull && docker-compose -f docker-compose.aws.yml up -d --build"
echo ""
echo "🔒 Security reminder:"
echo "   - Update your EC2 Security Group to only allow your IP"
echo "   - Consider using AWS Systems Manager Session Manager instead of SSH"
echo "   - Enable automatic security updates: sudo dpkg-reconfigure unattended-upgrades"
echo ""
echo "💾 Backups are scheduled daily at 2 AM server time"
echo ""