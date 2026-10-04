FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY . .
EXPOSE 3000
ENV API_ORIGIN=http://api:8000
# Dev-mode runtime keeps the compose setup dependency-robust and rebuild-free
# (production path: deploy this directory to Vercel — see README).
CMD ["npm", "run", "dev"]
