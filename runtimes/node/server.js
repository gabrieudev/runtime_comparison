const http = require("http");

const port = process.env.PORT || 3000;
const runtime = "node";

const server = http.createServer(async (req, res) => {
    if (req.url === "/ping" && req.method === "GET") {
        // template string sem JSON.stringify
        const body = `{"ok":true,"runtime":"${runtime}","ts":${Date.now()}}`;
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(body);
        return;
    }

    res.writeHead(404);
    res.end("not found");
});

server.listen(port, () => {
    console.log(`node server listening on ${port}`);
});
