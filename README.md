# MCP-Ethornell-Translate

Model Context Protocol (MCP) server & visual novel translation toolkit for the **BGI / Ethornell (Buriko General Interpreter)** visual novel engine.

Menggunakan core native C dari [BGIextractor](https://github.com/myzert/BGIextractor) untuk performa tinggi dan parsing binary yang bersih, dipadukan dengan script disassembler/compiler modern dan mesin penerjemah multi-bahasa yang memahami konteks visual novel.

---

## 🌟 Fitur Utama

1. **Native C Core Integration (BGIextractor):**
   - Unpack arsip `.arc` (format `BURIKO ARC20` v2 dan `PackFile` v1).
   - Dekripsi & dekompresi native stream `DSC FORMAT 1.00`, grafik `CompressedBG___` (CBG), dan kontainer `BSE 1.0`.
   - Otomatis terkompilasi secara native di Linux, Android (Termux aarch64/arm), dan Windows.

2. **Full Script Decode & Encode (Tanpa Batasan Panjang):**
   - **Bongkar (Decode):** Membaca bytecode `BurikoCompiledScriptVer1.00` dan V0 ke dalam format JSON/PO terstruktur lengkap dengan nama karakter (speaker), teks dialog, dan pilihan cabang (*choices*).
   - **Build (Encode):** Membangun kembali skrip bytecode dengan menghitung ulang (*re-pointing*) alamat string 32-bit di bytecode. **Tidak ada pemotongan teks (*truncation*)** dan tidak perlu spasi pengisi (*space padding*).

3. **Terjemah Multi-Bahasa & Paham Konteks (Context-Aware):**
   - Mendukung berbagai bahasa: **Indonesia (`id`)**, Inggris (`en`), Spanyol (`es`), Mandarin (`zh`), Jepang (`ja`), dll.
   - **Context-Aware Dialogue History:** Menyertakan konteks baris dialog sebelumnya dan identitas pembicara agar konsistensi pronomina (aku/kamu/gue/lu/dia) dan nada bicara karakter tetap terjaga.
   - **Glossary Support:** Penyesuaian nama karakter, istilah khas VN, dan honorifik Jepang (-san, -kun, -chan, Senpai, Sensei).
   - **LLM Prompt Generator:** Menyediakan prompt khusus bagi model AI (Claude, Gemini, GPT) untuk menerjemahkan bab skrip VN dengan cita rasa visual novel alami.

4. **Model Context Protocol (MCP) Server Ready:**
   - Menyediakan interface MCP standar (JSON-RPC 2.0 stdio) yang kompatibel langsung dengan **Antigravity**, **Claude Desktop**, dan **Cursor**.

---

## 📁 Struktur Proyek

```
MCP-Ethornell-Translate/
├── native/                     # Core native C dari BGIextractor
│   ├── arc.c / arc.h          # Parser & reader arsip ARC
│   ├── dsc.c / dsc.h          # Dekompresor DSC FORMAT 1.00
│   ├── cbg.c / cbg.h          # Dekoder CompressedBG graphics
│   ├── bse.c / bse.h          # Dekrip kontainer BSE
│   ├── decrypt.c / decrypt.h  # Hash updates & bit helpers
│   ├── write.c / write.h      # Export gambar
│   ├── main.c / Makefile      # Native CLI build
├── bgi_core/                   # Modul engine Python
│   ├── native_bridge.py       # Wrapper native executable & auto-compile
│   ├── script_engine.py       # BGI bytecode disassembler & compiler
│   └── translator.py          # Mesin penerjemah multi-bahasa & konteks
├── server.py                  # MCP Server (JSON-RPC 2.0 over stdio)
├── cli.py                     # Antarmuka baris perintah (CLI) mandiri
├── mcp_config.json            # Konfigurasi siap pakai untuk MCP client
└── README.md
```

---

## 🛠️ MCP Tools yang Tersedia

Ketika diintegrasikan ke AI Assistant melalui MCP:

| Tool Name | Deskripsi |
| :--- | :--- |
| `bgi_unpack_arc` | Membongkar file `.arc` dan mengekstrak semua file terdekripsi (DSC, CBG, BSE). |
| `bgi_pack_arc` | Mem-pack folder file kembali ke format `BURIKO ARC20` dengan urutan file asli. |
| `bgi_decode_script` | Mendisassembly file skrip bytecode BGI menjadi JSON dialog yang bisa diedit. |
| `bgi_encode_script` | Mengompilasi JSON dialog hasil terjemahan kembali ke bytecode skrip BGI. |
| `bgi_translate` | Menerjemahkan item dialog JSON ke bahasa target (misal Indonesia) dengan konteks. |
| `bgi_get_info` | Menampilkan informasi metadata file `.arc` atau skrip bytecode BGI. |
| `bgi_generate_llm_prompt` | Membuat prompt translasi berkonteks lengkap untuk AI model. |

---

## 🚀 Cara Menjalankan

### 1. Registrasi ke MCP Client (Antigravity / Claude Desktop)

Tambahkan ke file konfigurasi MCP Anda (misalnya `mcp_config.json`):

```json
{
  "mcpServers": {
    "bgi-ethornell-translator": {
      "command": "python3",
      "args": [
        "/path/to/MCP-Ethornell-Translate/server.py"
      ],
      "env": {
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

### 2. Menggunakan CLI Langsung

Toolkit ini juga bisa digunakan langsung via terminal:

```bash
# 1. Ekstrak arsip skrip game (misal data01010.arc)
python cli.py unpack "Sugar Style/Archive/data01010.arc" ./extracted_scripts/

# 2. Decode skrip scenario menjadi file JSON terjemahan
python cli.py decode ./extracted_scripts/01_chapter01a ./01_chapter01a.json

# 3. Terjemahkan dialog ke Bahasa Indonesia dengan konteks
python cli.py translate ./01_chapter01a.json ./01_chapter01a_id.json --to id

# 4. Build/Encode kembali skrip bytecode ber-bahasa Indonesia
python cli.py encode ./extracted_scripts/01_chapter01a ./01_chapter01a_id.json ./patched_scripts/01_chapter01a

# 5. Pack kembali folder ke file .arc siap main
python cli.py pack ./patched_scripts/ ./patched_data.arc --ref "Sugar Style/Archive/data01010.arc"
```

---

## 📄 Lisensi
GPL-3.0 / MIT (kompatibel dengan BGIextractor).
