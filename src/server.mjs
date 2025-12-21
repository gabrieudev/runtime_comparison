// Define a porta do servidor
const PORT = Number(
    process?.env?.PORT ??
        (typeof Deno !== "undefined" ? Deno.env.get?.("PORT") ?? 3000 : 3000)
);

// Identifica o runtime em execução
const RUNTIME_NAME =
    process?.env?.RUNTIME_NAME ??
    (typeof Deno !== "undefined"
        ? Deno.env.get?.("RUNTIME_NAME") ?? "deno?"
        : typeof Bun !== "undefined"
        ? "bun"
        : "node");

// Retorna timestamp atual no formato ISO
function nowIso() {
    return new Date().toISOString();
}

// Cria payload básico para resposta /ping
function makePayload() {
    return {
        pong: true,
        ts: nowIso(),
        runtime: RUNTIME_NAME,
    };
}

// Cria payload com informações do sistema para /info
function infoPayload() {
    let uptime = null;
    try {
        // Tenta obter uptime do processo (disponível no Node.js)
        if (typeof process !== "undefined" && process.uptime)
            uptime = Math.floor(process.uptime());
    } catch (e) {
        uptime = null; // Mantém null em caso de erro
    }
    return {
        ok: true,
        uptime,
        runtime: RUNTIME_NAME,
        ts: nowIso(),
    };
}

// Roteador principal - processa caminhos da URL
function handleUrl(pathname) {
    // Rota /ping - retorna heartbeat simples
    if (pathname === "/ping")
        return {
            status: 200,
            body: JSON.stringify(makePayload()),
            headers: { "content-type": "application/json" },
        };

    // Rota /info - retorna informações do sistema
    if (pathname === "/info")
        return {
            status: 200,
            body: JSON.stringify(infoPayload()),
            headers: { "content-type": "application/json" },
        };

    // Rota não encontrada - 404
    return {
        status: 404,
        body: JSON.stringify({ error: "not_found" }),
        headers: { "content-type": "application/json" },
    };
}

// Execução no Bun
if (typeof Bun !== "undefined") {
    console.log(`Starting server (bun) on port ${PORT}`);
    Bun.serve({
        port: PORT,
        fetch(req) {
            try {
                const url = new URL(req.url);
                const res = handleUrl(url.pathname);
                return new Response(res.body, {
                    status: res.status,
                    headers: res.headers,
                });
            } catch (err) {
                return new Response(JSON.stringify({ error: String(err) }), {
                    status: 500,
                    headers: { "content-type": "application/json" },
                });
            }
        },
    });
}
// Execução no Deno
else if (typeof Deno !== "undefined") {
    // Usa importação dinâmica do módulo HTTP do Deno
    (async () => {
        console.log(`Starting server (deno) on port ${PORT}`);
        const { serve } = await import(
            "https://deno.land/std@0.201.0/http/server.ts"
        );
        serve(
            (req) => {
                try {
                    const url = new URL(req.url);
                    const res = handleUrl(url.pathname);
                    return new Response(res.body, {
                        status: res.status,
                        headers: res.headers,
                    });
                } catch (err) {
                    return new Response(
                        JSON.stringify({ error: String(err) }),
                        {
                            status: 500,
                            headers: { "content-type": "application/json" },
                        }
                    );
                }
            },
            { port: PORT }
        );
    })();
}
// Execução no Node
else {
    // Usa importação dinâmica do módulo HTTP do Node
    (async () => {
        const http = await import("node:http");
        console.log(`Starting server (node) on port ${PORT}`);
        const server = http.createServer((req, res) => {
            try {
                const host = req.headers.host || `localhost:${PORT}`;
                const url = new URL(req.url || "/", `http://${host}`);
                const out = handleUrl(url.pathname);
                res.writeHead(out.status, out.headers);
                res.end(out.body);
            } catch (err) {
                res.writeHead(500, { "content-type": "application/json" });
                res.end(JSON.stringify({ error: String(err) }));
            }
        });
        server.listen(PORT);
    })();
}
