# ─── Build stage ───────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

# Enable pnpm via corepack (matches packageManager in package.json)
RUN corepack enable && corepack prepare pnpm@10.30.2 --activate

# Install deps first for layer caching
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy sources and build
COPY . .
RUN pnpm run build-only

# ─── Runtime stage (Nginx) ─────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# Remove default config and install ours
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built SPA
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
