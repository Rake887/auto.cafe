# --- зависимости ---
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# --- сборка ---
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* попадает в браузерный бандл на этапе сборки, поэтому адрес
# API задаётся здесь, а не в рантайме контейнера.
ARG NEXT_PUBLIC_API_BASE
ARG NEXT_PUBLIC_DEMO_TOKEN
# кнопка входа демо-паролем — только для показа, на проде должна быть пустой
ARG NEXT_PUBLIC_DEMO_LOGIN
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_DEMO_TOKEN=$NEXT_PUBLIC_DEMO_TOKEN
ENV NEXT_PUBLIC_DEMO_LOGIN=$NEXT_PUBLIC_DEMO_LOGIN
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# --- рантайм ---
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0

CMD ["node", "server.js"]
