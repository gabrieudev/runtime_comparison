const runtime = "bun";
const port = process.env.PORT || 3000;

const server = Bun.serve({
    port: +port,
    fetch(req) {
        const url = new URL(req.url);

        if (url.pathname === "/ping" && req.method === "GET") {
            // template string sem JSON.stringify
            return new Response(
                `{"ok":true,"runtime":"${runtime}","ts":${Date.now()}}`,
                { headers: { "Content-Type": "application/json" } }
            );
        }

        return new Response("not found", { status: 404 });
    },
});

console.log(`bun server listening on ${port}`);
