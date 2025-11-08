import http from "k6/http";
import { sleep } from "k6";

export let options = {
    vus: __ENV.VUS ? parseInt(__ENV.VUS) : 100,
    duration: __ENV.DURATION ? __ENV.DURATION : "30m",
    thresholds: {
        http_req_duration: ["p(95)<2000"],
    },
};

const BASE = __ENV.TARGET_URL || "http://host.docker.internal:3000";

export default function () {
    http.get(`${BASE}/ping`);

    sleep(0.05);
}
