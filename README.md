# Dynamic Island untuk Windows

Island hitam di tengah atas layar. Saat diam berbentuk garis dengan dua mata putih yang berkedip. Arahkan kursor (atau klik) untuk mengembang menjadi empat tampilan: **Musik**, **Sistem**, **Notif**, **Catatan**.

> Dibuat dan diuji tampilannya di Linux (render offscreen). Bagian yang bergantung pada Windows
> (Spotify, suhu, FPS) belum bisa saya jalankan langsung, jadi mohon laporkan jika ada yang tidak jalan.

## Menjalankan

1. Pasang **Python 3.10+** dari python.org (centang *Add python.exe to PATH*).
2. Ekstrak zip ke folder biasa (mis. Documents), lalu klik dua kali **`siapkan.pyw`**. Jendela kecil menampilkan kemajuan: ia membuat `.venv` dan memasang paket (beberapa menit, butuh internet), lalu island muncul. Aman dijalankan ulang.
3. Ikon di tray (dekat jam): *Tampilkan/sembunyikan*, *Mulai bersama Windows*, *Buat pintasan di Desktop*, *Keluar*.

Setelah pemasangan selesai, cukup pakai `mulai.pyw` atau pintasan Desktop. Pengaturan dan catatan lama tetap aman di `%APPDATA%\DynamicIsland`.

Manual: `pip install -r requirements.txt` lalu `python main.py`.

### Berjalan sendiri tanpa mengatur ulang

Setelah `siapkan.pyw` selesai, semuanya otomatis:

- **Pintasan berikon:** saat pertama dibuka, island membuat pintasan **Dynamic Island** di Desktop dan menu Start dengan ikon sendiri (dua mata putih). Bisa dibuat ulang kapan saja lewat tray → *Buat pintasan*.
- **Administrator otomatis:** karena alat pendamping sudah disertakan, island meminta izin Administrator satu kali (jendela izin Windows, jawab *Ya*), lalu berjalan dengan FPS aktif. Tidak perlu mengatur "Run as administrator" sendiri.
- **Alat pendamping:** LibreHardwareMonitor sudah disertakan dan dijalankan otomatis (diminimalkan), ditutup lagi saat island ditutup. PresentMon 2.6.0 (MIT) juga sudah disertakan di `tools\PresentMon`, jadi `presentmon_path` tidak perlu diisi. Versi lain di `C:\Tools`, Unduhan, atau Dokumen ikut dicari, dan yang terbaru dipakai.
- **Mulai bersama Windows:** tray → centang *Mulai bersama Windows*. Jika island sedang berjalan sebagai Administrator, dibuat tugas terjadwal sehingga island dan FPS menyala saat login **tanpa jendela izin**, juga saat laptop memakai baterai.
- Pengaturan dan catatan ada di `%APPDATA%\DynamicIsland`, jadi unduh ulang folder tidak menghapusnya.

Di perangkat baru hanya ada satu hal sekali saja: setujui pemasangan driver PawnIO saat jendelanya muncul (untuk suhu CPU).

Pengaturan di `config.json`: `run_as_admin` (`"auto"`, `true`, `false`), `lhm_autostart` (`false` untuk tidak menjalankan LibreHardwareMonitor), `lhm_path`, `presentmon_path` (isi manual bila alat disimpan di tempat lain).

Island hanya bisa berjalan satu salinan. Untuk menutupnya: klik kanan ikon tray → **Keluar**.

## Fitur dan syaratnya

| Fitur | Cara kerja | Syarat |
|---|---|---|
| Spotify | Kontrol media Windows (judul, artis, sampul, progres, putar/jeda/berikutnya/sebelumnya) | Spotify desktop berjalan. Tanpa login/API key |
| CPU, RAM | `psutil` | Tidak ada |
| GPU, VRAM, suhu GPU | NVML | Kartu grafis **NVIDIA** dengan driver terpasang |
| Suhu CPU | LibreHardwareMonitor bawaan (folder `tools`) | Administrator + driver PawnIO (sekali) |
| FPS | Membaca PresentMon | Lihat di bawah |
| Notifikasi | Server lokal `127.0.0.1:8765` | Kirim dengan `kirim_notif.py` |
| Catatan | Daftar centang tersimpan di `%APPDATA%\DynamicIsland\notes.json` | Tidak ada |

### Suhu CPU (sudah disertakan)
LibreHardwareMonitor sudah ada di folder `tools\LibreHardwareMonitor`, jadi tidak perlu mengunduh apa pun. Island menjalankannya sendiri (diminimalkan, Remote Web Server sudah diaktifkan otomatis) dan menutupnya saat island ditutup.

Di perangkat baru, pertama kali akan muncul jendela yang meminta izin memasang driver **PawnIO** (dibutuhkan untuk membaca sensor CPU). Setujui sekali; setelah itu tidak ditanya lagi. Jika ditolak, suhu CPU tampil "—" dan fitur lain tetap jalan. Island harus berjalan sebagai Administrator untuk ini (otomatis bila PresentMon ada, atau set `"run_as_admin": true`).

Ingin memakai LibreHardwareMonitor Anda sendiri? Isi `lhm_path` di `config.json`.

### FPS (sudah disertakan)
PresentMon sudah ada di `tools\PresentMon` dan dipakai otomatis. Langkah di bawah hanya bila ingin memakai PresentMon sendiri.

1. Unduh **PresentMon** (konsol) dari repositori Intel GameTechDev.
2. Isi `presentmon_path` di `%APPDATA%\DynamicIsland\config.json`, misalnya `"C:\\Tools\\PresentMon.exe"`.
3. Jalankan island **sebagai Administrator** (atau tambahkan akun Anda ke grup *Performance Log Users*).
4. FPS tampil untuk game yang sedang berjalan. Untuk PresentMon versi 1.x, ganti `presentmon_args` menjadi `["-output_stdout", "-no_top", "-stop_existing_session"]`.

## Mengirim notifikasi

```
python kirim_notif.py "Judul" "Isi pesan" --app "Nama aplikasi" --url https://contoh.com
```
Island otomatis mengembang selama 6 detik. Tombol *Buka* aktif jika ada `--url`.
Dari bahasa lain: `POST http://127.0.0.1:8765/notify` dengan header `X-Island: 1` dan JSON `{"app","title","body","url"}`.

## Notifikasi WhatsApp

Island membaca notifikasi yang Windows tampilkan untuk aplikasi tertentu (bawaan: WhatsApp) dan menampilkannya di tab **Notif**. Semuanya dibaca lokal di komputer ini; tidak ada yang dikirim ke internet.

Syarat:
1. WhatsApp Desktop (atau WhatsApp Web di browser) terpasang dan terhubung.
2. *Pengaturan Windows → Sistem → Notifikasi*: notifikasi untuk WhatsApp **aktif**, dan mode *Fokus / Jangan ganggu* tidak menyembunyikannya. Notifikasi yang tidak dimunculkan Windows tidak tercatat, jadi tidak bisa dibaca island.
3. Pesan yang masuk saat island berjalan akan muncul. Pesan lama sebelum island dibuka tidak diputar ulang.

Jika tidak muncul, jalankan `.venv\Scripts\python.exe cek_notif.py`. Skrip ini mencetak 15 notifikasi terakhir beserta "ID aplikasi"-nya. Pastikan sebagian ID WhatsApp itu (huruf kecil) ada di `win_notif_apps` pada `config.json`. Untuk WhatsApp Web, tambahkan ID browser Anda, misalnya `"chrome"` atau `"msedge"`.

Pengaturan di `config.json`:
- `win_notif`: `false` untuk mematikan fitur ini.
- `win_notif_apps`: daftar potongan ID aplikasi. `[]` berarti semua aplikasi.
- `win_notif_show_body`: `false` untuk menampilkan nama pengirim saja tanpa isi pesan (berguna jika layar dilihat orang lain).

## Ekspresi mata

Mata tetap oval putih polos; ekspresinya muncul dari bentuk dan geraknya:

| Keadaan | Mata |
|---|---|
| Kursor bergerak di layar | Mata melirik mengikuti kursor |
| Musik diputar | Mata mengangguk pelan mengikuti irama, sesekali tersenyum (busur ^ ^) atau mengedip sebelah |
| Notifikasi masuk | Mata membulat kaget sekitar 1,4 detik |
| CPU/GPU ≥ 95% atau suhu ≥ 85°C | Mata menegang (kelopak miring); kembali normal setelah beban < 80% dan suhu < 78°C |
| Tidak ada gerakan kursor 3 menit | Mata mengantuk dan berkedip lambat; kaget sebentar saat kursor bergerak lagi |

Untuk mematikan semuanya (mata polos dan diam), set `"eye_expressions": false` di `config.json`.

## Tema

Bawaan: **air** (biru malam, aksen biru es, riak halus di sekeliling mata saat berkedip). Untuk tema hitam-amber lama, ubah di `config.json`:

```
"theme": "amber"
```

Warna bisa ditimpa satu per satu, misalnya:

```
"colors": { "accent": "#6EC1F5", "bg": "#060D17", "ripple": true }
```

Kunci yang tersedia: `bg`, `text`, `muted`, `accent`, `off`, `line`, `field`, `sep`, `body`, `art`, `eye`, `ripple`. Restart island setelah mengubahnya.

## Pengaturan

`%APPDATA%\DynamicIsland\config.json` (dibuat otomatis): jarak dari tepi atas, layar yang dipakai, hover on/off, lama notifikasi, port, alamat LibreHardwareMonitor, path PresentMon. Restart island setelah mengubah.

## Batasan yang perlu diketahui

- **Notifikasi WhatsApp** dibaca dari database notifikasi internal Windows, yang tidak didokumentasikan Microsoft. Sifatnya usaha terbaik dan bisa berhenti bekerja setelah pembaruan Windows (lihat bagian *Notifikasi WhatsApp*).
- Game dengan mode **fullscreen eksklusif** menutupi island. Pakai *borderless/windowed fullscreen*.
- GPU **AMD/Intel**: GPU, VRAM, dan suhu GPU tampil "—".
- Font: bila terpasang, **JetBrains Mono** dan **Schibsted Grotesk** dipakai; jika tidak, Cascadia Mono / Segoe UI sebagai pengganti.

## Berkas

`siapkan.pyw` (pemasangan pertama) · `mulai.pyw` · `main.py` (titik masuk, tray, pintasan, mulai bersama Windows) · `tools.py` (mencari/menjalankan alat pendamping) · `icon.ico` · `tools\LibreHardwareMonitor` (disertakan, lisensi MPL-2.0) · `island.py` (seluruh tampilan) · `sensors.py` · `media.py` · `server.py` · `store.py` · `config.py` · `kirim_notif.py`
