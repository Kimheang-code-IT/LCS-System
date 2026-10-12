# Static frontend: build the Nuxt SPA, then serve it with nginx.
# The nginx config is mounted from infrastructure/nginx/default.conf.

FROM node:22-alpine AS build

ENV NUXT_TELEMETRY_DISABLED=1 \
    PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH

RUN corepack enable && corepack prepare pnpm@10.30.3 --activate

WORKDIR /app

# Dependency layer (cached): only the manifests, so it survives source changes.
# --ignore-scripts skips the root "nuxt prepare" postinstall, which needs the
# application source that is copied afterwards.
# .pnpmfile.cjs, pnpm-workspace.yaml and patches/ must be present here: the
# lockfile pins their checksums, and the frozen install applies the pnpm hook
# (.pnpmfile.cjs strips Tiptap) and the @nuxt/devtools patch before resolving.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .pnpmfile.cjs ./
COPY patches ./patches
RUN pnpm install --frozen-lockfile --ignore-scripts

# Application source.
COPY . .

# Public runtime config is inlined at build time. Override per environment
# (e.g. NUXT_PUBLIC_SITE_URL=https://lcslog.minidev.in).
ARG NUXT_PUBLIC_SITE_URL=""
ARG NUXT_PUBLIC_AUTH_MODE="cookie"
ARG NUXT_PUBLIC_CSRF_COOKIE_NAME="XSRF-TOKEN"
ENV NUXT_PUBLIC_SITE_URL=$NUXT_PUBLIC_SITE_URL \
    NUXT_PUBLIC_AUTH_MODE=$NUXT_PUBLIC_AUTH_MODE \
    NUXT_PUBLIC_CSRF_COOKIE_NAME=$NUXT_PUBLIC_CSRF_COOKIE_NAME

RUN pnpm exec nuxt prepare
RUN pnpm generate

FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/.output/public /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
