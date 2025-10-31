FROM denoland/deno:alpine-1.37.1
WORKDIR /app
COPY server.ts .
EXPOSE 3000
CMD ["run", "--allow-net", "--allow-env", "server.ts"]
