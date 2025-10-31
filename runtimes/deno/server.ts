import { serve } from "https://deno.land/std@0.203.0/http/server.ts";

const runtime = "deno";
const port = Number(Deno.env.get("PORT") || 3000);

// força hostname 0.0.0.0 para expor a todos os interfaces
serve(
    async (req) => {
        const url = new URL(req.url);

        if (url.pathname === "/ping" && req.method === "GET") {
            const body = { ok: true, runtime, ts: Date.now() };
            return new Response(JSON.stringify(body), {
                status: 200,
                headers: { "content-type": "application/json" },
            });
        }

        if (url.pathname === "/data" && req.method === "POST") {
            try {
                const j = await req.json();
                const size = JSON.stringify(j).length;
                return new Response(
                    JSON.stringify({
                        receivedSize: size,
                        runtime,
                        ts: Date.now(),
                    }),
                    {
                        status: 200,
                        headers: { "content-type": "application/json" },
                    }
                );
            } catch (e) {
                return new Response("invalid json", { status: 400 });
            }
        }

        return new Response("not found", { status: 404 });
    },
    { port, hostname: "0.0.0.0" }
);
