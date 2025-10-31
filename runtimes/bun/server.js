const runtime = "bun";
const port = process.env.PORT || 3000;

const server = Bun.serve({
    port: +port,
    fetch(req) {
        const url = new URL(req.url);
        if (url.pathname === "/ping" && req.method === "GET") {
            return new Response(
                JSON.stringify({ ok: true, runtime, ts: Date.now() }),
                { headers: { "Content-Type": "application/json" } }
            );
        }
        if (url.pathname === "/data" && req.method === "POST") {
            return req.text().then((text) => {
                try {
                    const obj = JSON.parse(text || "{}");
                    const size = Buffer.from(text || "").length;
                    return new Response(
                        JSON.stringify({
                            receivedSize: size,
                            runtime,
                            ts: Date.now(),
                        }),
                        { headers: { "Content-Type": "application/json" } }
                    );
                } catch (err) {
                    return new Response("invalid json", { status: 400 });
                }
            });
        }
        return new Response("not found", { status: 404 });
    },
});

console.log(`bun server listening on ${port}`);
