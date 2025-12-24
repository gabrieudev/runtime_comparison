import { Hono } from "hono";

export const RUNTIME_NAME =
    globalThis?.process?.env?.RUNTIME_NAME ??
    (typeof Deno !== "undefined"
        ? Deno.env.get?.("RUNTIME_NAME") ?? "deno"
        : typeof Bun !== "undefined"
        ? "bun"
        : "node");

const DB_CONFIG = {
    host: process?.env?.DB_HOST ?? "postgres",
    port: Number(process?.env?.DB_PORT ?? 5432),
    database: process?.env?.DB_NAME ?? "perfdb",
    user: process?.env?.DB_USER ?? "postgres",
    password: process?.env?.DB_PASSWORD ?? "postgres",
    max: 1000,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 10000,
};

let pool = null;
let dbConnected = false;

async function initDB() {
    if (dbConnected && pool) return;

    try {
        const pgModule =
            typeof Deno !== "undefined"
                ? await import("npm:pg")
                : await import("pg");

        const { Pool } = pgModule;
        if (!Pool) throw new Error("Pool não encontrado no módulo pg");

        pool = new Pool(DB_CONFIG);

        const client = await pool.connect();
        try {
            await client.query("SELECT 1");
            dbConnected = true;
            console.log(`[${RUNTIME_NAME}] Conectado ao banco com sucesso`);
        } finally {
            client.release();
        }
    } catch (err) {
        console.error(`[${RUNTIME_NAME}] Falha ao conectar no banco:`, err);
        pool = null;
        dbConnected = false;
    }
}

async function getRandomProducts(limit = 100) {
    if (!pool) {
        throw new Error("Pool do banco não inicializado");
    }

    const start = Date.now();

    const result = await pool.query(
        `
      SELECT id, name, price, category, stock
      FROM products
      ORDER BY RANDOM()
      LIMIT $1
    `,
        [limit]
    );

    return {
        rowCount: result.rows.length,
        queryTime: Date.now() - start,
    };
}

export const app = new Hono();

app.get("/ping", (c) => {
    return c.text("pong", 200, {
        "X-Runtime": RUNTIME_NAME,
        "X-Framework": "Hono",
    });
});

app.get("/api/products", async (c) => {
    try {
        if (!dbConnected) await initDB();

        if (!dbConnected || !pool) {
            return c.json(
                {
                    success: false,
                    runtime: RUNTIME_NAME,
                    error: "Banco de dados indisponível",
                },
                503,
                {
                    "X-Runtime": RUNTIME_NAME,
                    "X-Framework": "Hono",
                }
            );
        }

        const limit = Number(c.req.query("limit") ?? 100);
        const result = await getRandomProducts(limit);

        return c.json(
            {
                success: true,
                runtime: RUNTIME_NAME,
                products_count: result.rowCount,
                query_time_ms: result.queryTime,
            },
            200,
            {
                "X-Runtime": RUNTIME_NAME,
                "X-Framework": "Hono",
                "x-processing-time": `${result.queryTime}ms`,
            }
        );
    } catch (err) {
        console.error(`[${RUNTIME_NAME}] Erro na rota /api/products:`, err);

        return c.json(
            {
                success: false,
                runtime: RUNTIME_NAME,
                error: String(err.message ?? err),
            },
            500,
            {
                "X-Runtime": RUNTIME_NAME,
                "X-Framework": "Hono",
            }
        );
    }
});
