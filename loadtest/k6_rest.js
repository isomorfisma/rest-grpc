import http from 'k6/http';
import { check } from 'k6';

// open() hanya tersedia pada tahap init; konfigurasi dibaca sekali di sini.
const cfg = JSON.parse(open(__ENV.CFG_JSON || '../config/experiment.json'));
const svc = cfg.protocols.find((p) => p.name === (__ENV.PROTO || 'rest'));

const TARGET = __ENV.TARGET || `https://${svc.ip}:${svc.port}`;
const SIZE   = __ENV.SIZE   || cfg.payload_classes[0].name;
const VUS    = Number(__ENV.VUS || cfg.concurrency_levels[0]);
const DUR    = __ENV.DUR    || cfg.experiment.duration;
const REP    = Number(__ENV.REP || 0);
const OUT    = __ENV.OUT    || '';

export const options = {
  vus: VUS,
  duration: DUR,
  insecureSkipTLSVerify: true,    // enkripsi tetap aktif; hanya verifikasi sertifikat dilewati
  discardResponseBodies: true,    // body tetap diunduh penuh lalu dibuang: hemat RAM
  summaryTrendStats: ['avg', 'med', 'p(95)', 'p(99)', 'max'],
};

export default function () {
  const res = http.get(`${TARGET}${svc.path}?size=${SIZE}`, { timeout: cfg.experiment.timeout });
  check(res, { 'HTTP 200': (r) => r.status === 200, 'HTTP/1.1': (r) => r.proto === 'HTTP/1.1' });
}

export function handleSummary(data) {
  const m = data.metrics;
  const d = m.http_req_duration.values;
  const row = {
    tool: 'k6', protocol: svc.name, payload_class: SIZE, concurrency: VUS, rep: REP,
    p50_ms: d.med, p95_ms: d['p(95)'], p99_ms: d['p(99)'], mean_ms: d.avg, max_ms: d.max,
    requests: m.http_reqs.values.count,
    rps: m.http_reqs.values.rate,
    error_rate: m.http_req_failed.values.rate,
    checks_ok: m.checks.values.rate,
  };
  return OUT ? { [OUT]: JSON.stringify(row, null, 2) } : { stdout: JSON.stringify(row) + '\n' };
}