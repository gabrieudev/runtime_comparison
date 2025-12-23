import http from "k6/http";
import { sleep, check } from "k6";

export let options = {
    vus: __ENV.VUS ? parseInt(__ENV.VUS) : 50,
    duration: __ENV.DURATION ? __ENV.DURATION : "1800s",
    thresholds: {
        http_req_duration: ["p(95)<2000"],
        http_req_failed: ["rate<0.05"],
    },
    discardResponseBodies: false,
};

const BASE = __ENV.TARGET_URL || "http://localhost:3000";

export default function () {
    const response = http.get(`${BASE}/api/products`);

    check(response, {
        "status is 200": (r) => r.status === 200,
        "response time < 2s": (r) => r.timings.duration < 2000,
        "has products data": (r) => {
            try {
                const body = JSON.parse(r.body);
                return (
                    body.success === true &&
                    body.data &&
                    body.data.products_count === 100
                );
            } catch {
                return false;
            }
        },
        "has runtime header": (r) => r.headers["X-Runtime"] !== undefined,
        "has framework header": (r) => r.headers["X-Framework"] === "Hono",
    });

    sleep(0.1);
}
