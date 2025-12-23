import { Hono } from "hono";

// CONFIGURAÇÃO

export const RUNTIME_NAME =
    globalThis?.process?.env?.RUNTIME_NAME ??
    (typeof Deno !== "undefined"
        ? Deno.env.get?.("RUNTIME_NAME") ?? "deno"
        : typeof Bun !== "undefined"
        ? "bun"
        : "node");

const DB_CONFIG = {
    host: process.env.DB_HOST || "postgres",
    port: Number(process.env.DB_PORT || 5432),
    database: process.env.DB_NAME || "perfdb",
    user: process.env.DB_USER || "postgres",
    password: process.env.DB_PASSWORD || "postgres",
    max: 1000,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 10000,
};

// BANCO

let pool;
let dbConnected = false;

async function initDB() {
    if (dbConnected) return;

    const { Pool } =
        typeof Deno !== "undefined"
            ? await import("npm:pg")
            : await import("pg");

    pool = new Pool(DB_CONFIG);

    const client = await pool.connect();
    client.release();
    dbConnected = true;
}

async function getRandomProducts(limit = 100) {
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

// CONTROLADOR DA API

export const app = new Hono();

app.get("/ping", async (c) => {
    return c.json({
        pong: true,
        runtime: RUNTIME_NAME,
        db_connected: dbConnected,
        timestamp: new Date().toISOString(),
    });
});

app.get("/api/products", async (c) => {
    try {
        if (!dbConnected) await initDB();

        const limit = Number(c.req.query("limit") || 100);
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
                "x-processing-time": `${result.queryTime}ms`,
            }
        );
    } catch (err) {
        return c.json(
            {
                success: false,
                error: err.message,
                runtime: RUNTIME_NAME,
            },
            500
        );
    }
});
