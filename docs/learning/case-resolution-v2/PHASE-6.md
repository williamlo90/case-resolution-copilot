# Phase 6 — packaging dan release gate

Tanggal: 16 Oktober 2026. Status: **PASS untuk engineering package demo sintetis**.
Satu commit final pada branch `case-resolution-v2` menjadi checkpoint phase ini.

## Tujuan

Membuat frontend, API, migrasi, seed, dan database dapat dijalankan konsisten pada host
terisolasi. Docker menjadi paket reproduksi dan validasi; demo hosted tetap mengikuti
Vercel, Neon, dan Clerk. Phase 5 sudah selesai melalui benchmark lama dan tidak dibuka ulang.

## Implementasi utama

- `compose.demo.yaml` menjalankan database pgvector, job migrasi/seed, API, dan Next.js
  production build dengan batas resource dan port loopback.
- Container demo memakai runtime non-root untuk aplikasi, dependency terkunci, dan
  entrypoint yang memakai virtual environment terpasang tanpa instalasi saat startup.
- `scripts/demo-compose.ps1` menyediakan Config/Up/Smoke/Down; startup memerlukan
  penanda host terisolasi dan password lokal yang di-ignore.
- CI membangun image secara serial, memindai ketiga image, menguji startup/restart,
  restore logis, penggantian image/config, dan sepuluh journey PostgreSQL.
- Tes restart membuktikan unknown outcome tetap unknown tanpa mengarang bukti target.

## Bukti dan cara memverifikasi

[Evidence release](../../evidence/case-resolution-v2/PHASE6_RELEASE.md) mencatat kandidat yang
diuji, tautan CI, hasil, dan image ID. Container/source/script pada checkpoint ini dicocokkan
dengan kandidat tervalidasi; hasil CI tetap diatribusikan pada SHA kandidat tersebut.
Gate source kandidat mencatat 12 pemeriksaan lulus, 699 backend tests dan 186 frontend tests.
Gate terisolasi mencatat 10 integration tests lulus dan nol HIGH/CRITICAL pada tiga image.
Pemeriksaan source final setelah penyesuaian Phase 5 juga lulus 12/12: 699 backend tests,
186 frontend tests dan 525 file Python diperiksa tipe. Perbandingan kandidat cocok pada
1.123 file; validasi corpus statis menjalankan nol product run.

Pemeriksaan final menggunakan `scripts.run_release_verification`, validasi Compose Config,
parser PowerShell, tautan Markdown, `git diff --check`, dan perbandingan source kandidat.
Tidak ada Docker stack, browser automation, server aplikasi, atau benchmark yang dijalankan lokal.
Pemeriksaan HTTP ringan mengonfirmasi demo lama merespons dari revisi `dab033c` pada frontend
dan backend; itu bukan deployment V2 atau pengujian login baru.

## Batas hasil dan handoff

Restore membandingkan dua belas tabel pada seed tiga kasus; ledger aksi masih kosong.
Faulted-image drill kembali ke image kandidat yang sama, bukan binary versi produk sebelumnya.
Tidak ada klaim RTO/RPO cutover, payment sungguhan, cloud performance, atau production readiness.

[Runbook](../../runbooks/PHASE6_DEMO_RELEASE.md) memuat urutan pembaruan demo existing:
pastikan akses proyek Vercel, siapkan Neon preview/checkpoint, periksa migrasi, ikat Clerk,
deploy backend lalu frontend pada SHA yang sama, dan verifikasi sebelum promosi alias.
Konfigurasi proyek hosted tidak diubah saat menutup phase ini.

## Latihan

1. Bedakan HTTP readiness, startup smoke, dan keberhasilan resolusi bisnis.
2. Jelaskan mengapa ledger target yang hilang setelah restart tidak membuktikan efek belum terjadi.
3. Bedakan restore database, penggantian image, dan rollback binary lama yang kompatibel.
4. Ikuti pemisahan deterministic identity lokal dan autentikasi Clerk pada demo hosted.

Phase berikutnya adalah keputusan cakupan Phase 7: cloud validation hanya untuk klaim yang
memerlukannya. Hosting demo baru dan studi waktu operator bukan prasyaratnya.
