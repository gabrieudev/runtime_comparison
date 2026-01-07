import http from "k6/http";
import { check } from "k6";

export let options = {
    vus: __ENV.VUS ? Number(__ENV.VUS) : 10,
    duration: __ENV.DURATION ? __ENV.DURATION : "15s",
};

export default function () {
    const BASE = __ENV.TARGET_URL || "http://localhost:3000";

    const r1 = http.get(`${BASE}/test/net`);
    check(r1, {
        "net: got 200": (r) => r.status === 200,
    });

    const r2 = http.get(`${BASE}/test/env`);
    check(r2, {
        "env: endpoint ok": (r) =>
            r.status === 200 && typeof r.json === "function",
    });

    const r3 = http.get(`${BASE}/test/fs`);
    check(r3, {
        "fs: responded": (r) =>
            r.status === 200 || r.status === 403 || r.status === 500,
    });
}
