FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY . .
# Las rewrites de Next se resuelven al compilar: el backend se llama "api" dentro de Docker
ARG BACKEND_URL=http://api:8000
ENV BACKEND_URL=$BACKEND_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Desarrollo (compose.dev.yml, `target: dev`): `next dev` con recarga y todas las devDependencies, así que sirve
# también para tsc, lint, vitest y build en contenedor. El build de producción no pasa por este stage.
FROM node:22-alpine AS dev
WORKDIR /app
RUN chown node:node /app
USER node
COPY --chown=node:node package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY --chown=node:node . .
# punto de montaje del volumen anónimo de .next (compose.dev.yml): así nace con dueño node
RUN mkdir -p .next
# en dev el rewrite /api se evalúa al arrancar `next dev`
ENV BACKEND_URL=http://api:8000 NEXT_TELEMETRY_DISABLED=1
EXPOSE 3000
CMD ["npx", "next", "dev", "--hostname", "0.0.0.0", "--port", "3000"]

# Producción (stage final: lo que construye `docker compose up --build` sin target)
FROM node:22-alpine
WORKDIR /app
# también en ejecución: los Server Components leen la sesión y los datos iniciales del api
ARG BACKEND_URL=http://api:8000
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0 BACKEND_URL=$BACKEND_URL
# sin root: el usuario node (uid 1000) que trae la imagen; Next escribe su caché en .next/cache
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
# /login no exige sesión: 200 si Next responde (wget viene en alpine)
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -qO /dev/null http://127.0.0.1:3000/login || exit 1
CMD ["node", "server.js"]
