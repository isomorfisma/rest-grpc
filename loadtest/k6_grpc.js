import grpc from 'k6/net/grpc';
import { check } from 'k6';
import { Counter, Rate } from 'k6/metrics';

// Padanan k6_rest.js untuk gRPC: alat, model beban, dan skema keluaran sama persis.
// open()/load() hanya tersedia pada tahap init; jalur relatif terhadap folder skrip ini.
const cfg = JSON.parse(open(__ENV.CFG_JSON || '../config/experiment.json'));
const svc = cfg.protocols.find((p) => p.name === (__ENV.PROTO || 'grpc'));

const TARGET = __ENV.TARGET || `${svc.ip}:${svc.port}`;
const SIZE   = __ENV.SIZE   || cfg.payload_classes[0].name;
const VUS    = Number(__ENV.VUS || cfg.concurrency_levels[0]);
const DUR    = __ENV.DUR    || cfg.experiment.duration;
const REP    = Number(__ENV.REP || 0);
const OUT    = __ENV.OUT    || '';

const client = new grpc.Client();
client.load(['..'], 'payload.proto');

// k6/net/grpc tidak punya padanan http_reqs dan http_req_failed, jadi dihitung sendiri
const grpcReqs   = new Counter('grpc_reqs');
const grpcFailed = new Rate('grpc_req_failed');

export const options = {
  vus: VUS,
  duration: DUR,
  insecureSkipTLSVerify: true,    // enkripsi tetap aktif; hanya verifikasi sertifikat dilewati
  summaryTrendStats: ['avg', 'med', 'p(95)', 'p(99)', 'max'],
};

let terhubung = false;               // status koneksi milik VU ini

export default function () {
  let ok = false;
  try {
    // Satu koneksi HTTP/2 per VU, dibuka sekali lalu dipakai ulang (setara keep-alive pada REST).
    // Pembentukan koneksi tidak masuk grpc_req_duration, sama seperti http_req_duration.
    if (!terhubung) {
      client.connect(TARGET, { timeout: cfg.experiment.timeout, maxReceiveSize: 64 * 1024 * 1024 });
      terhubung = true;
    }
    const res = client.invoke(svc.call, { size_class: SIZE }, {
      timeout: cfg.experiment.timeout,
      discardResponseMessage: true,   // respons diterima utuh tetapi tidak di-decode (setara discardResponseBodies)
    });
    ok = check(res, { 'gRPC OK': (r) => r && r.status === grpc.StatusOK });
  } catch (e) {
    ok = false;                       // gagal terhubung atau kesalahan transport: dihitung gagal,
  }                                   // seperti http_req_failed pada REST
  grpcReqs.add(1);
  grpcFailed.add(!ok);
}

export function handleSummary(data) {
  const m = data.metrics;
  const d = m.grpc_req_duration ? m.grpc_req_duration.values : {};   // kosong bila tak satu pun panggilan terkirim
  const row = {
    tool: 'k6', protocol: svc.name, payload_class: SIZE, concurrency: VUS, rep: REP,
    p50_ms: d.med ?? null, p95_ms: d['p(95)'] ?? null, p99_ms: d['p(99)'] ?? null,
    mean_ms: d.avg ?? null, max_ms: d.max ?? null,
    requests: m.grpc_reqs.values.count,
    rps: m.grpc_reqs.values.rate,
    error_rate: m.grpc_req_failed.values.rate,
    checks_ok: m.checks ? m.checks.values.rate : 0,
  };
  return OUT ? { [OUT]: JSON.stringify(row, null, 2) } : { stdout: JSON.stringify(row) + '\n' };
}
