# 🐝 Buzzer Score — Deteksi Akun Buzzer Twitter Indonesia

**Analisis probabilitas akun buzzer Twitter/X Indonesia berdasarkan 9 sinyal perilaku.**

> 🇬🇧 *An open-source tool to detect coordinated inauthentic behavior (buzzer/bot accounts) on Indonesian Twitter, using 9 behavioral signals scored from 0-100%.*

## 🌐 Web Playground

**[▶️ Try it live](https://ainunnajib.github.io/buzzer-score/)** — No installation needed. Input account metrics manually and get instant scoring.

## ✨ Features

- **9 sinyal perilaku** — Analisis komprehensif dari umur akun, rasio follower, volume tweet, engagement, dan lainnya
- **CLI tool** — Python script untuk analisis via terminal (single, batch, JSON/CSV output)
- **Web playground** — Interactive browser tool, zero dependencies, fully offline
- **Batch mode** — Analisis puluhan akun sekaligus dari file
- **Adjustable weights** — Sesuaikan bobot setiap sinyal sesuai kebutuhan riset

## 📊 9 Sinyal Scoring

| # | Sinyal | Bobot | Deteksi |
|---|--------|-------|---------|
| 1 | 📅 **Account Age vs Activity** | 15 | Akun baru (<180 hari) tapi super aktif |
| 2 | 👥 **Follower/Following Ratio** | 15 | Following jauh lebih banyak dari followers |
| 3 | 📊 **Tweet Volume** | 10 | Frekuensi posting abnormal (>50/hari) |
| 4 | 💬 **Engagement Ratio** | 15 | Banyak tweet tapi engagement sangat rendah |
| 5 | 🔄 **Retweet Ratio** | 10 | Mayoritas konten cuma RT tanpa original |
| 6 | 🏷️ **Political Hashtag Density** | 10 | Spam hashtag politik Indonesia |
| 7 | 👤 **Profile Completeness** | 10 | Avatar default, bio kosong, nama generik |
| 8 | 📝 **Content Repetition** | 10 | Copy-paste tweet yang sama berulang |
| 9 | 📋 **Listed Count** | 5 | Banyak tweet tapi jarang dimasukkan ke list |

**Total bobot: 100 poin**

## 🏷️ Klasifikasi

| Skor | Label | Artinya |
|------|-------|---------|
| 0-14% | ✅ **CLEAN** | Kemungkinan besar akun organik |
| 15-29% | 🟡 **LOW RISK** | Ada beberapa tanda, tapi mungkin normal |
| 30-49% | 🔍 **SUSPICIOUS** | Perlu investigasi lebih lanjut |
| 50-74% | ⚠️ **PROBABLE BUZZER** | Kemungkinan besar buzzer |
| 75-100% | 🚨 **HIGHLY LIKELY BUZZER** | Hampir pasti buzzer |

## 🚀 Quick Start

### Web Playground (Tanpa Install)

Buka [`index.html`](index.html) di browser atau kunjungi **[live demo](https://ainunnajib.github.io/buzzer-score/)**.

### CLI Tool

```bash
# Clone repo
git clone https://github.com/ainunnajib/buzzer-score.git
cd buzzer-score

# Install dependency
pip install -r requirements.txt

# Set Twitter API Bearer Token
export TWITTER_BEARER_TOKEN="your-bearer-token-here"
```

## 💻 Usage (CLI)

### Analisis satu akun

```bash
python buzzer_score.py @username
```

### Analisis beberapa akun

```bash
python buzzer_score.py @user1 @user2 @user3
```

### Batch mode (dari file)

```bash
# accounts.txt — satu username per baris
python buzzer_score.py --batch accounts.txt
```

### Output JSON

```bash
python buzzer_score.py @username --json
```

### Output CSV

```bash
python buzzer_score.py @username --csv > results.csv
```

### Contoh output

```
═══════════════════════════════════════
  🐝 BUZZER PROBABILITY SCORE
═══════════════════════════════════════

  @patriot_nkri_2024 (Patriot NKRI 🇮🇩)
  NKRI Harga Mati | #2024GantiPresiden

  📅 Account age: 120 days
  👥 Followers: 45 | Following: 4,200
  📝 Tweets: 28,000 (233.3/day)
  📋 Listed in: 0 lists

  ─── Signal Breakdown ───

  📅 Account Age vs Activity:    15/15 ████████████████ 100%
  👥 Follower/Following Ratio:   15/15 ████████████████ 100%
  📊 Tweet Volume:               10/10 ████████████████ 100%
  💬 Engagement Ratio:           12/15 █████████████░░░  80%
  🔄 Retweet Ratio:              10/10 ████████████████ 100%
  🏷️ Political Hashtag Density:  10/10 ████████████████ 100%
  👤 Profile Completeness:        4/10 ██████░░░░░░░░░░  40%
  📝 Content Repetition:         10/10 ████████████████ 100%
  📋 Listed Count:                5/5  ████████████████ 100%

  ─── Result ───

  🚨 92% — HIGHLY LIKELY BUZZER

═══════════════════════════════════════
```

## 🔑 Twitter API Setup

1. Buat akun developer di [developer.twitter.com](https://developer.twitter.com)
2. Buat Project & App
3. Generate Bearer Token
4. Set environment variable:
   ```bash
   export TWITTER_BEARER_TOKEN="AAAAAAAAAAAAAAAAAAAAAxxxxxxxx"
   ```

> **Tanpa API key?** Gunakan web playground (`index.html`) untuk input manual — tidak butuh API key.

## 🎨 Web Playground

Web playground (`index.html`) bisa digunakan tanpa API key:

- **📝 Manual Mode** — Input metrik akun secara manual
- **📊 Batch Mode** — Import JSON hasil CLI untuk visualisasi
- **⚙️ Weights** — Atur bobot setiap sinyal

Fitur:
- Gauge visualization untuk skor
- Signal breakdown bars
- Classification badges
- Dark theme
- Fully responsive
- Zero external dependencies

## 🧠 Cara Kerja

Setiap sinyal diberi skor 0 sampai bobot maksimumnya. Skor final dihitung sebagai persentase dari total:

```
probability = (total_score / max_possible_score) × 100%
```

### Detail Sinyal

**1. Account Age vs Activity (15 poin)**
- Akun <180 hari + >20 tweets/hari = skor maksimum
- Buzzer sering menggunakan akun baru yang langsung aktif

**2. Follower/Following Ratio (15 poin)**
- Rasio following/followers > 10 = skor maksimum
- Buzzer follow banyak akun tapi jarang di-follow balik

**3. Tweet Volume (10 poin)**
- >50 tweets/hari = skor maksimum
- Manusia normal sulit memposting >50 tweet/hari

**4. Engagement Ratio (15 poin)**
- Engagement rate <0.01% dengan >1000 followers = skor maksimum
- Buzzer menghasilkan volume, bukan engagement

**5. Retweet Ratio (10 poin)**
- >90% tweets adalah RT = skor maksimum
- Buzzer bertugas meng-amplifikasi pesan, bukan membuat konten original

**6. Political Hashtag Density (10 poin)**
- >3 hashtag politik per 20 tweets = skor maksimum
- Mendeteksi: #pilpres, #capres, nama politisi, nama partai, dll.

**7. Profile Completeness (10 poin)**
- Avatar default (4), tanpa bio (3), username generik (3)
- Akun buzzer sering tidak diisi dengan lengkap

**8. Content Repetition (10 poin)**
- >50% tweets duplikat = skor maksimum
- Buzzer sering copy-paste tweet yang sama

**9. Listed Count (5 poin)**
- >1000 tweets tapi <5 lists = skor maksimum
- Akun asli biasanya ditambahkan ke Twitter Lists oleh pengguna lain

## ⚠️ Disclaimer

**Tool ini untuk edukasi dan riset.**

- Skor tinggi **tidak otomatis** berarti akun tersebut buzzer
- Beberapa akun asli (jurnalis, aktivis, fanbase) bisa memiliki skor tinggi
- Selalu lakukan verifikasi manual sebelum membuat kesimpulan
- Tool ini menganalisis **perilaku**, bukan **identitas**
- Jangan gunakan tool ini untuk harassment atau doxxing

## 🤝 Contributing

Contributions welcome! Beberapa ide:

- [ ] Tambah sinyal baru (network analysis, sentiment patterns)
- [ ] Improve political keyword list
- [ ] Support bahasa daerah dalam keyword detection
- [ ] Temporal analysis (posting time distribution)
- [ ] Export ke PDF report
- [ ] Browser extension

```bash
# Fork, clone, branch, code, PR
git checkout -b fitur-baru
# ... code ...
git commit -m "Tambah fitur X"
git push origin fitur-baru
```

## 📄 License

MIT License — lihat [LICENSE](LICENSE) untuk detail.

## 🙏 Credits

Built by [AI-Noon](https://x.com/ainunnajib) 🌞

Terinspirasi oleh kebutuhan literasi digital Indonesia dalam menghadapi buzzer politik di media sosial.

---

<div align="center">

**🐝 Buzzer Score** — Karena demokrasi butuh transparansi.

</div>
