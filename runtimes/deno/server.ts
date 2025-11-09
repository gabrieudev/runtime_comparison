import { serve } from "https://deno.land/std@0.203.0/http/server.ts";

const runtime = "deno";
const port = Number(Deno.env.get("PORT") || 3000);

serve(
    async (req) => {
        const url = new URL(req.url);

        if (url.pathname === "/ping" && req.method === "GET") {
            // template string sem JSON.stringify
            return new Response(
                `{"ok":true,"runtime":"${runtime}","ts":${Date.now()}}`,
                {
                    status: 200,
                    headers: { "content-type": "application/json" },
                }
            );
        }

        return new Response("not found", { status: 404 });
    },
    { port, hostname: "0.0.0.0" }
);
