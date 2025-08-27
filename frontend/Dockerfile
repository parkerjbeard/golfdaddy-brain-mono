FROM node:20-slim AS builder

WORKDIR /app

# Copy package files and install dependencies
COPY package*.json ./
# Clean install with platform-specific dependencies
RUN npm ci --no-audit --no-fund || (rm -rf node_modules package-lock.json && npm install --legacy-peer-deps)

# Copy the rest of the application
COPY . .

# Build the application
RUN npm run build

# Production image
FROM nginx:alpine

# Copy built artifacts from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose the port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"] 