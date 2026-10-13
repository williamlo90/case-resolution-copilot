# Checkpoint pembelajaran — Phase 1

Tanggal: 13 Oktober 2026. Gate: **PASS � lifecycle API dan kontrol terarah**. Branch: `codex/case-resolution-v2`.
Identitas SHA adalah commit tunggal yang memuat checkpoint ini.

## Perubahan utama

Receipt dari target hanya membuktikan permintaan diterima. Action sekarang tetap unknown sampai
read-back membuktikan operation ID, reference, target, semua parameter, nominal/mata uang, waktu
observasi dan jumlah efek cocok. Catatan manusia tidak dapat menggantikan read-back.

Lifecycle ledger menyimpan completion, reopen dan routing/acknowledgement sebagai event berbeda,
dengan actor, waktu, correlation ID dan hubungan ke event sebelumnya. Reopen menggunakan case
lama. Routing mengubah owner kasus dan membutuhkan acknowledgement penerima yang berwenang.
Status selesai tidak lagi bisa diatur melalui endpoint status generik.

Authority dicek sebelum side effect dan sebelum closure. Perubahan policy, evidence, proposal,
payload atau expired approval memblokir operasi. Unknown tidak boleh memicu blind retry. Lookup
yang pekerjanya terputus dapat dilanjutkan tanpa mengulangi write. Pergantian reference dari receipt
tersimpan dianggap mismatch meskipun response baru mengaku verified.

Telemetry membedakan API, DB, tool, provider, retrieval/decision, intake/worker, queue dan manual
wait. Laporan menggunakan event aktual untuk reopen dan acknowledgement serta operasi unik untuk
verified action. Denominator kosong ditampilkan N/A. Tidak ada autonomous grant; automation belum
menghasilkan success. Baca [kontrak dan runbook lifecycle](../../evidence/case-resolution-v2/LIFECYCLE.md)
untuk payload API, kondisi closure, migrasi, metrik dan batas cakupan.

## Bukti pengujian

| Pemeriksaan | Hasil |
| --- | --- |
| 11 modul unit terkait verifier, telemetry, gateway, recovery, service, migration, inbox, narrative dan materialization | 75 passed, 2.91 s |
| Guarded Neon: `test_resolution_lifecycle.py` + `test_case_action_api.py` | 8 passed, 148.56 s |
| Dua journey setelah tambahan recovery lease dan verified-action metric | 2 passed, 58.54 s |
| Pengujian perubahan reference receipt setelah closure | 1 passed, 36.77 s |
| Journey akhir dengan confirmed side-effect setelah read-back | 1 passed, 35.54 s |
| Ruff: aplikasi dan tes/migrasi baru | PASS |
| Mypy: 17 source files terkait | PASS |
| Frontend typecheck + ESLint pada empat file berubah | PASS |
| Dua komponen frontend (Quality dan Action Detail), satu worker | 3 passed |
| Whitespace, V1 unchanged, baseline pekerjaan lama | PASS; 11 baseline file tetap identik |

Runner database menggunakan konfigurasi Neon yang telah ditandai disposable dari checkout lama;
TLS/endpoint diverifikasi dan output dirahasiakan. Migrasi diujikan hanya pada database tersebut.
Python dan node_modules memakai environment existing melalui junction lokal yang di-ignore.
Tidak ada deployment, provider berbayar, browser E2E, load atau concurrency worker test.

## Latihan membaca kode

1. Ikuti execute → unknown → reconcile → verified. Mengapa HTTP 200 tidak cukup?
2. Ubah satu parameter atau reference di proof. Perhatikan mengapa keberadaan receipt tidak
   mengalahkan mismatch. Bandingkan timeout sebelum efek dan timeout setelah efek.
3. Telusuri foreign key previous_event_id ketika case ditutup lalu dibuka ulang. Mengapa riwayat
   completion awal tetap berguna meskipun hasil akhirnya invalidated?
4. Bandingkan escalation recommendation dengan perubahan owner dan acknowledgement penerima.
5. Pisahkan latency DB/tool dari elapsed sejak intake. Nested span tidak boleh dijumlahkan menjadi
   end-to-end latency; tiga puluh milidetik engine tidak berarti kasus selesai dalam waktu itu.
6. Baca test migrasi: completed legacy dipertahankan tanpa membuat proof palsu.

## Batas checkpoint dan handoff

Ini fondasi lifecycle dengan API-first commands. Closure explanation-only, dedicated lifecycle UI,
automation grants, polling provider dan durable external refund adapter belum diaktifkan. Operator
mengattestasi reference komunikasi; Gmail draft bukan pesan terkirim. Semua materialized actions
masih menjadi kewajiban closure; cancellation/supersession tidak diabaikan otomatis.

Gate menguji workflow kecil dan kontrolnya, bukan semantic oracle, production readiness, akurasi
holdout atau klaim speedup. Phase 2 berikutnya membangun evaluator, mutation suite dan golden oracle;
Phase 2 belum dimulai. Satu commit final Phase 1 menjadi checkpoint modul pembelajaran.
