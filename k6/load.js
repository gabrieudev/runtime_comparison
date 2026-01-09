import http from "k6/http";
import { sleep, check } from "k6";

const WARMUP_SECONDS = 30;

export let options = {
    vus: __ENV.VUS ? parseInt(__ENV.VUS) : 50,
    duration: __ENV.DURATION ? __ENV.DURATION : "40s",
    thresholds: {
        http_req_duration: ["p(95)<2000"],
    },
    discardResponseBodies: false,
};

const BASE = __ENV.TARGET_URL || "http://localhost:3000";
const startTime = Date.now();

export default function () {
    const elapsed = (Date.now() - startTime) / 1000;

    const response = http.get(`${BASE}/api/products`);

    if (elapsed >= WARMUP_SECONDS) {
        // após warm up
        check(response, {
            "status is 200": (r) => r.status === 200,
            "response time < 2s": (r) => r.timings.duration < 2000,
            "has products data": (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return (
                        body.success === true &&
                        body.products_count &&
                        body.products_count > 0
                    );
                } catch {
                    return false;
                }
            },
            "has runtime info": (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return body.runtime !== undefined;
                } catch {
                    return false;
                }
            },
        });
    }

    sleep(0.1);
}
