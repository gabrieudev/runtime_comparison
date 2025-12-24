import { app } from "./app.js";

const PORT = Number(
    process?.env?.PORT ??
        (typeof Deno !== "undefined" ? Deno.env.get?.("PORT") ?? 3000 : 3000)
);

const RUNTIME =
    typeof Deno !== "undefined"
        ? "Deno"
        : typeof Bun !== "undefined"
        ? "Bun"
        : "Node";

console.log(`=== ${RUNTIME} ===`);
console.log(`Servidor iniciando na porta ${PORT}`);

// Iniciar servidor

try {
    // Bun
    if (typeof Bun !== "undefined") {
        Bun.serve({
            port: PORT,
            fetch: app.fetch,
        });

        console.log(`Bun -> http://localhost:${PORT}`);
    }

    // Deno
    else if (typeof Deno !== "undefined") {
        Deno.serve({ port: PORT }, app.fetch);

        console.log(`Deno -> http://localhost:${PORT}`);
    }

    // Node
    else {
        (async () => {
            try {
                const { serve } = await import("@hono/node-server");

                serve({
                    fetch: app.fetch,
                    port: PORT,
                });

                console.log(`Node -> http://localhost:${PORT}`);
            } catch (err) {
                console.error("Erro ao iniciar servidor Node:", err);
                process.exit(1);
            }
        })();
    }
} catch (err) {
    console.error("Erro fatal ao iniciar servidor:", err);
}
