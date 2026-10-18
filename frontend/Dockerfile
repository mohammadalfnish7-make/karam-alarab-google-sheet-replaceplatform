FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
ENV API_UPSTREAM=api:8000
# Only substitute API_UPSTREAM so nginx vars like $host / $uri stay intact.
ENV NGINX_ENVSUBST_FILTER=API_UPSTREAM
