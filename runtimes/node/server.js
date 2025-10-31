const http = require("http");

const port = process.env.PORT || 3000;
const runtime = "node";

const server = http.createServer(async (req, res) => {
    if (req.url === "/ping" && req.method === "GET") {
        const body = JSON.stringify({ ok: true, runtime, ts: Date.now() });
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(body);
        return;
    }

    if (req.url === "/data" && req.method === "POST") {
        let data = "";
        req.on("data", (chunk) => (data += chunk));
        req.on("end", () => {
            try {
                const body = JSON.stringify({
                    receivedSize: Buffer.byteLength(data || ""),
                    runtime,
                    ts: Date.now(),
                });
                res.writeHead(200, { "Content-Type": "application/json" });
                res.end(body);
            } catch (err) {
                res.writeHead(400);
                res.end("invalid json");
            }
        });
        return;
    }

    res.writeHead(404);
    res.end("not found");
});

server.listen(port, () => {
    console.log(`node server listening on ${port}`);
});
