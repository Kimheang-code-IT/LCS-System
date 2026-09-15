# Static frontend: build the Nuxt SPA, then serve it with nginx.
# The nginx config is mounted from infrastructure/nginx/default.conf.

FROM node:22-alpine AS build

ENV NUXT_TELEMETRY_DISABLED=1 \
    PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH

RUN corepack enable && corepack prepare pnpm@10.30.3 --activate

WORKDIR /app

# Install with full source so Nuxt's postinstall (nuxt prepare) can run.
COPY . .
RUN pnpm install --frozen-lockfile
RUN pnpm generate

FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/.output/public /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
