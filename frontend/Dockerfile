# Multi-stage build for BahnVision frontend

# Build stage
FROM node:24-alpine AS builder

WORKDIR /app

# Skip downloading Playwright browsers during image builds; CI installs them when needed.
ARG PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=${PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD}

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build-time configuration for Vite (passed from docker-compose build args)
ARG VITE_API_BASE_URL
ARG VITE_ENABLE_DEBUG_LOGS=false
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_ENABLE_DEBUG_LOGS=${VITE_ENABLE_DEBUG_LOGS}

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine AS production

# Update packages to patch known vulnerabilities
RUN apk update && apk upgrade --no-cache

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

# Run as non-root user for security
USER nginx

CMD ["nginx", "-g", "daemon off;"]
