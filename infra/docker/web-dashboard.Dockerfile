FROM node:20-alpine

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml turbo.json /app/
COPY apps/web-dashboard/package.json /app/apps/web-dashboard/package.json

RUN pnpm install --filter @itx/web-dashboard... --no-frozen-lockfile

COPY apps/web-dashboard /app/apps/web-dashboard

CMD ["pnpm", "--dir", "apps/web-dashboard", "dev", "--host", "0.0.0.0", "--port", "4173"]