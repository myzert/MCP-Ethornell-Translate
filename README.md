# MCP-Ethornell-Translate

<div align="center">

[![License: GPL-3.0](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Model Context Protocol](https://img.shields.io/badge/MCP-Compatible-orange.svg)](https://modelcontextprotocol.io/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20Android%20(Termux)-lightgrey.svg)]()
[![Engine](https://img.shields.io/badge/VN%20Engine-BGI%20%2F%20Ethornell-purple.svg)]()

**High-Performance Model Context Protocol (MCP) Server & Visual Novel Translation Toolkit for BGI / Ethornell Engine.**

*Bongkar skenario, terjemah multi-bahasa paham konteks (ID/EN/dll), dan build/encode bytecode BGI tanpa pemotongan teks.*

[Fitur](#-fitur-utama) • [Instalasi MCP](#-integrasi-mcp) • [Panduan CLI](#-penggunaan-cli) • [Tools](#-daftar-mcp-tools) • [Lisensi](#-lisensi)

</div>

---

## 📖 Deskripsi

**MCP-Ethornell-Translate** adalah toolkit dan server [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) yang dirancang khusus untuk memodifikasi, mengekstrak, menerjemahkan, dan mengompilasi skrip visual novel yang berjalan di atas engine **BGI / Ethornell (Buriko General Interpreter)** (seperti karya SMEE, August, Whirlpool, dll., contohnya *Sugar Style*).

Toolkit ini memadukan **core native C** berkecepatan tinggi dari [BGIextractor](https://github.com/myzert/BGIextractor) untuk membongkar arsip dan mendekripsi kompresi DSC/CBG/BSE, dipadukan dengan **disassembler/compiler bytecode** modern dan **mesin translasi multi-bahasa berbasis konteks visual novel**.

---

## 🌟 Fitur Utama

- ⚡ **Native C Engine Integration:**
  - Unpack arsip `.arc` format `BURIKO ARC20` v2 dan `PackFile` v1.
  - Dekripsi & dekompresi native stream `DSC FORMAT 1.00`, format gambar `CompressedBG___` (CBG), dan kontainer enkripsi `BSE 1.0`.
  - Otomatis terkompilasi secara native di Linux, Android (Termux aarch64/arm), dan Windows.
- 🔄 **Full Script Decode & Encode (Tanpa Batasan Panjang):**
  - **Bongkar (Decode):** Membaca bytecode `BurikoCompiledScriptVer1.00` dan V0 ke dalam format JSON terstruktur lengkap dengan nama karakter pembicara (*speaker*), teks dialog, dan pilihan percabangan (*choices*).
  - **Build (Encode):** Membangun kembali skrip bytecode dengan menghitung ulang (*re-pointing*) alamat pointer string 32-bit. **Tidak ada pemotongan kalimat (*no truncation*)** dan tanpa spasi paksaan (*no padding*).
- 🧠 **Context-Aware Multi-Language Engine:**
  - Mendukung penerjemahan ke **Bahasa Indonesia (`id`)**, Inggris (`en`), Jepang (`ja`), Spanyol (`es`), Mandarin (`zh`), dll.
  - **Dialogue History Context:** Menyertakan konteks baris sebelumnya agar konsistensi pronomina (aku/kamu/dia) dan nada bicara karakter tetap terjaga.
  - **Honorifics Preservation:** Menjamin panggilan khas visual novel seperti `-san`, `-kun`, `-chan`, `Senpai`, dan `Sensei` tidak dihilangkan, terutama pada adegan penting & 18+ (*H-scenes*).
  - **Turbo Bulk Batching:** Mengirim batch baris dalam satu request (50x lebih cepat dibanding translasi 1 per 1).
- 🤖 **Model Context Protocol (MCP) Server Ready:**
  - Terintegrasi langsung dengan **Google Antigravity (`agy`)**, **Claude Desktop**, dan **Cursor** melalui standar JSON-RPC 2.0 stdio.

---

## 📁 Struktur Repositori

```
MCP-Ethornell-Translate/
├── native/                     # Core native C dari BGIextractor
│   ├── arc.c / arc.h          # Parser arsip ARC & kalkulasi offset BURIKO ARC20
│   ├── dsc.c / dsc.h          # Dekompresor stream DSC FORMAT 1.00
│   ├── cbg.c / cbg.h          # Dekoder CompressedBG graphics
│   ├── bse.c / bse.h          # Dekrip kontainer enkripsi BSE 1.0
│   ├── decrypt.c / decrypt.h  # Hash updates & bit helpers
│   ├── write.c / write.h      # Export gambar BMP / PNG
│   ├── main.c / Makefile      # Native CLI build
├── bgi_core/                   # Modul Python Engine
│   ├── native_bridge.py       # Wrapper native binary & auto-compile
│   ├── script_engine.py       # BGI bytecode disassembler & compiler
│   └── translator.py          # Mesin penerjemah multi-bahasa & bulk batching
├── server.py                  # MCP Server (JSON-RPC 2.0 stdio)
├── cli.py                     # Antarmuka CLI mandiri
├── full_translator.py         # Otomatisasi translasi massal & installer patch
├── batch_translator.py        # Batch translator & DLC patch generator
├── mcp_config.json            # Konfigurasi siap pakai MCP Client
├── LICENSE                    # GNU General Public License v3.0
└── README.md
```

---

## 🛠️ Daftar MCP Tools

| Tool Name | Parameter | Deskripsi |
| :--- | :--- | :--- |
| **`bgi_unpack_arc`** | `arc_path`, `output_dir`, `target_file` | Membongkar file `.arc` dan mendekripsi file skrip DSC, gambar CBG, dan BSE. |
| **`bgi_pack_arc`** | `input_dir`, `output_arc_path`, `reference_arc_path` | Mem-pack folder file kembali ke format `BURIKO ARC20` dengan urutan file asli. |
| **`bgi_decode_script`** | `script_path`, `output_json_path`, `include_context` | Disassemble skrip bytecode BGI menjadi JSON dialog yang bisa diedit. |
| **`bgi_encode_script`** | `original_script_path`, `translation_json_path`, `output_script_path` | Recompile JSON hasil terjemahan kembali ke bytecode skrip BGI. |
| **`bgi_translate`** | `input_json_path`, `output_json_path`, `target_lang`, `glossary` | Terjemahkan JSON dialog ke bahasa target dengan pemahaman konteks. |
| **`bgi_get_info`** | `file_path` | Inspeksi metadata file `.arc` atau skrip bytecode BGI. |
| **`bgi_generate_llm_prompt`** | `json_path`, `target_lang`, `count`, `start_id` | Buat prompt berkonteks VN untuk model LLM (Claude/Gemini/GPT). |

---

## 🚀 Integrasi MCP

### 1. Antigravity CLI (`agy`)
Daftarkan server secara global dengan satu perintah:
```bash
agy mcp add --env PYTHONIOENCODING=utf-8 --env PYTHONPATH=/path/to/MCP-Ethornell-Translate bgi-ethornell-translator python3 /path/to/MCP-Ethornell-Translate/server.py
```

### 2. Claude Desktop / Cursor (`mcp_config.json`)
Tambahkan ke konfigurasi MCP Anda:
```json
{
  "mcpServers": {
    "bgi-ethornell-translator": {
      "command": "python3",
      "args": [
        "/path/to/MCP-Ethornell-Translate/server.py"
      ],
      "env": {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": "/path/to/MCP-Ethornell-Translate"
      }
    }
  }
}
```

---

## 💻 Penggunaan CLI

Anda juga dapat menjalankan toolkit langsung dari terminal tanpa MCP client:

```bash
cd MCP-Ethornell-Translate

# 1. Unpack arsip scenario game
python cli.py unpack "/path/to/game/Archive/data01010.arc" ./extracted/

# 2. Decode skrip menjadi file JSON dialog
python cli.py decode ./extracted/01_prologue01 ./01_prologue01.json

# 3. Terjemahkan dialog ke Bahasa Indonesia
python cli.py translate ./01_prologue01.json ./01_prologue01_id.json --to id

# 4. Build/Encode kembali skrip bytecode
python cli.py encode ./extracted/01_prologue01 ./01_prologue01_id.json ./patched/01_prologue01

# 5. Pack kembali ke .arc siap main
python cli.py pack ./patched/ ./data01010.arc --ref "/path/to/game/Archive/data01010.arc"
```

---

## 📜 Lisensi

Proyek ini dilisensikan di bawah lisensi **GNU General Public License v3.0 (GPL-3.0)** — lihat file [LICENSE](LICENSE) untuk detail lengkap.
Kompatibel penuh dengan upstream [BGIextractor](https://github.com/myzert/BGIextractor).
