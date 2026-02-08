# Browsing Digest Summarizer (llama.cpp Edition) 📚🤖

![Local AI Digest Generator](https://img.shields.io/badge/Privacy-100%25_Local-008000) ![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue) ![llama.cpp](https://img.shields.io/badge/llama.cpp-Compatible-orange)

Generate beautiful, insightful daily browsing digests using **100% local AI** with llama.cpp. Automatically summarizes your browsing history, highlights top visited pages with clickable links, and optionally delivers to your inbox — all without sending your data to external servers.

[Example Digest Preview](#example)

## ✨ Key Features

- **100% Private Processing**: All analysis happens locally on your machine — your browsing history never leaves your computer
- **AI-Powered Summaries**: Uses llama.cpp to generate concise 2-minute reading digests with:
  - Main themes & topics explored
  - Key insights learned
  - Action items & follow-ups
  - Time pattern analysis
- **Top Pages Section**: Automatically appends clickable links to pages you spent the most time on (sorted by reading time)
- **Beautiful Email Delivery**: Sends professionally formatted HTML emails with responsive styling (optional)
- **Smart JSON Repair**: Automatically fixes malformed export files from Browsing Digest extension
- **Flexible Configuration**: Uses `settings.env` for secure credential management

## 📁 Project Structure

```
browsing-digest-summarizer/
├── dailyBrowsing_llamaCPP.py     # Main application script
├── settings.env.example          # Configuration template (rename to settings.env)
├── README.md                     # This documentation file
├── requirements.txt              # Python dependencies
└── examples/
    ├── digest-2025-01-19.md      # Sample output file
    └── browsing-digest-2025-01-19.json  # Sample input file
```

## ⚙️ Core Functions

### `load_browsing_data(filepath)`
- Loads and repairs malformed JSON exports from Browsing Digest extension
- Automatically strips whitespace from keys/values (fixes `"date "` → `"date"`)
- Creates backup (`*.json.bak`) before repairs
- Validates required structure (`date`, `pages` fields)

### `prepare_content_for_llm(data, max_tokens=4000)`
- Processes browsing history into LLM-friendly format
- Sorts pages chronologically
- Respects token budget with intelligent truncation
- Preserves timestamps, titles, domains, and content snippets

### `generate_summary(content, model, date, server_url)`
- Crafts prompt for llama.cpp server with clear instructions
- Requests structured digest with 4 key sections (themes, insights, actions, patterns)
- Handles API errors with descriptive messages

### `get_top_pages(data, top_n=15)`
- **Smart ranking**: Sorts pages by reading time (primary) + content length (fallback)
- **Deduplication**: Removes repetitive entries by domain + title fingerprinting
- **Engagement filtering**: Excludes pages with <30 seconds engagement
- Returns clean list of meaningful pages for link section

### `append_top_pages_section(digest, data, top_n=15)`
- Appends beautifully formatted "Top Pages Visited" section
- Uses time-based emoji indicators (🕗 = 5+ min, 🕓 = 2-5 min, 🕑 = <2 min)
- Creates safe markdown links with proper escaping
- Example output:
  ```markdown
  ## 🔗 Top Pages Visited
  
  *Pages sorted by time spent (top 10):*
  
  1. 🕗 [Understanding Transformers](https://example.com) — **8.3 min**
  2. 🕓 [Python Type Hints Guide](https://example.com) — **4.7 min**
  ```

### `send_markdown_email(...)`
- Converts markdown to responsive HTML email with professional styling
- Uses Gmail app passwords with STARTTLS (port 587)
- Includes plain-text fallback for email clients
- Handles authentication errors with helpful setup guidance

## 🚀 Quick Start

### Prerequisites
1. **llama.cpp server** running locally:
   ```bash
   # From llama.cpp directory
   ./server -c 4096 --port 8080
   ```
2. **Python 3.8+** installed
3. **Browsing Digest extension** export file (JSON format)

### Installation
```bash
# Clone repository
git https://github.com/fabiomatricardi/daily-Browsing-llamaCPP-with-Email-summary
cd daily-Browsing-llamaCPP-with-Email-summary

# Install dependencies
pip install -r requirements.txt
# Or manually:
pip install requests markdown python-dotenv rich
```

### Configuration (for email delivery)
1. Create `settings.env` from template:
   ```bash
   copy settings.env.example settings.env   # Windows
   cp settings.env.example settings.env     # macOS/Linux
   ```
2. Edit `settings.env` with your Gmail credentials:
   ```env
   EMAIL_SENDER=your.email@gmail.com
   EMAIL_APP_PASSWORD=abcd efgh ijkl mnop  # 16-digit app password
   # EMAIL_RECEIVER=optional@domain.com    # Defaults to sender if omitted
   ```
3. **Generate Gmail App Password**:
   - Enable 2-Factor Authentication on your Google account
   - Visit: https://myaccount.google.com/apppasswords
   - Select "Mail" → "Other" → Name it "Browsing Digest" → Generate
   - Use the **16-digit password** (not your regular password!)

> ⚠️ **Security Note**: Never commit `settings.env` to version control! Add to `.gitignore`.

## 💻 Usage

### Basic Usage (save to file only)
```bash
python dailyBrowsing_llamaCPP.py browsing-digest-2025-01-19.json
```

### With Email Delivery
```bash
python dailyBrowsing_llamaCPP.py browsing-digest-2025-01-19.json --email
```

### Custom Options
```bash
# Custom output filename
python dailyBrowsing_llamaCPP.py data.json --output today.md

# Include top 20 pages (instead of default 15)
python dailyBrowsing_llamaCPP.py data.json --top-pages 20 --email

# Use custom config file
python dailyBrowsing_llamaCPP.py data.json --config my-settings.env --email

# Check server status
python dailyBrowsing_llamaCPP.py --check-server
```

### Full Command Reference
```text
usage: dailyBrowsing_llamaCPP.py [-h] [--model MODEL] [--server SERVER]
                                 [--output OUTPUT] [--email] [--config CONFIG]
                                 [--check-server] [--top-pages TOP_PAGES]
                                 input_file

Generate a 2-minute digest of your daily browsing using local AI (llama.cpp)

positional arguments:
  input_file            JSON file exported from Browsing Digest extension

options:
  -h, --help            show this help message and exit
  -m MODEL, --model MODEL
                        Model identifier for API (default: local-model)
  -s SERVER, --server SERVER
                        llama.cpp server URL (default: http://localhost:8080/v1)
  -o OUTPUT, --output OUTPUT
                        Output markdown file (default: digest-YYYY-MM-DD.md)
  -e, --email           Send digest to email after generation (requires settings.env)
  --config CONFIG       Path to custom configuration file (default: settings.env)
  --check-server        Check server status and exit
  -t TOP_PAGES, --top-pages TOP_PAGES
                        Number of top pages to include in links section (default: 15)
```

## 🔒 Privacy & Security

- **Zero external data transmission**: All processing occurs locally via llama.cpp server
- **No cloud dependencies**: Unlike commercial summarization services, your browsing history stays on your machine
- **Secure credential handling**: 
  - Uses environment variables (never hardcodes passwords)
  - Requires Gmail App Passwords (not your main password)
  - Configuration file excluded from version control by default
- **Transparent operation**: Console output shows exactly what's being processed and when emails are sent

## 🛠 Troubleshooting

| Issue | Solution |
|-------|----------|
| `Connection failed to http://localhost:8080` | Start llama.cpp server: `./llama-server.exe -m yourmodel.gguf -c 4096 --port 8080` |
| `Authentication failed` | Verify 16-digit app password (not regular password) in `settings.env` |
| `Malformed JSON detected` | Script auto-repairs files; check `.json.bak` backup if issues persist |
| `Missing required dependencies` | Run: `pip install requests markdown python-dotenv rich` |
| Links not clickable in email | Most email clients support markdown links; view in Gmail/Outlook web for best experience |
| No top pages shown | Ensure pages have `readingTime > 0.5` or meaningful content (>100 chars) |

## 🌐 Requirements

### System Requirements
- Python 3.8 or higher
- llama.cpp server running locally (v3.0+ recommended)
- 4GB+ RAM (for 7B parameter models)

### Python Dependencies (`requirements.txt`)
```text
requests>=2.28.0
markdown>=3.4.0
python-dotenv>=1.0.0
rich>=13.0.0
```

### Supported Browsers
Works with JSON exports from:
- [My Browsing Digest from GitHub Repo](https://github.com/fabiomatricardi/your-daily-browsing-digest) Chrome/Edge extension
- Any tool exporting in compatible JSON format with `date` and `pages` fields

<a name="example"></a>
## 📜 Sample Output Structure

```markdown
# 📚 Browsing Digest - 2025-01-19
**Generated**: 2025-01-19 22:15
**Pages analyzed**: 42
**Estimated reading time**: 87 minutes

## Main Themes
- Deep dive into transformer architectures and attention mechanisms
- Research on Python type hinting best practices for large codebases
- Exploring new prompt engineering techniques for LLMs

## Key Insights
- Rotary Position Embedding (RoPE) significantly improves long-context performance
- Pydantic v2 offers 30% faster validation than v1 for complex schemas
- Chain-of-thought prompting works best when examples match target domain

## Action Items
- [ ] Implement type hints in project X using Pydantic models
- [ ] Test RoPE implementation on our custom transformer variant
- [ ] Create prompt template library for common tasks

## Time Analysis
Spent 68% of time on technical deep-dives (ML/AI topics), 22% on productivity tools, 10% on news. Most focused session: 23 minutes on transformer paper analysis at 14:30.

## 🔗 Top Pages Visited

*Pages sorted by time spent (top 15):*

1. 🕗 [Rotary Position Embedding Explained](https://example.com/rope) — **12.4 min**
2. 🕗 [Pydantic v2 Performance Deep Dive](https://example.com/pydantic) — **9.8 min**
3. 🕓 [Chain-of-Thought Prompting Guide](https://example.com/cot) — **6.2 min**
...

---
*Generated locally using llama.cpp server. No data left your machine.*
```

## 🤝 Contributing

Contributions welcome! Please open an issue or PR for:
- New output formats (PDF, Obsidian notes, etc.)
- Additional email providers (Outlook, Yahoo)
- Enhanced page ranking algorithms
- Browser extension integrations

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

> 💡 **Pro Tip**: Schedule daily runs with Task Scheduler (Windows) or cron (macOS/Linux) to get automatic morning digests of yesterday's browsing!

**Made with ❤️ for privacy-conscious knowledge workers**  
*Your data stays yours. Always.*

---

Fabio Matricardi - fabio.matricardi@gmail.com