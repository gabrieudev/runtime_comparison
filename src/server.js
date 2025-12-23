import { app } from "./app.js";

const PORT = Number(
    process?.env?.PORT ??
        (typeof Deno !== "undefined" ? Deno.env.get?.("PORT") ?? 3000 : 3000)
);

console.log(
    `=== ${
        typeof Deno !== "undefined"
            ? "Deno"
            : typeof Bun !== "undefined"
            ? "Bun"
            : "Node"
    } ===`
);
console.log(`Servidor iniciando na porta ${PORT}`);

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
    const { serve } = await import("@hono/node-server");

    serve({
        fetch: app.fetch,
        port: PORT,
    });

    console.log(`Node -> http://localhost:${PORT}`);
}
