FROM node:20-alpine
WORKDIR /app
COPY package.json .
COPY server.js .
RUN npm ci --production || true
EXPOSE 3000
CMD ["node", "server.js"]
