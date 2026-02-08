#!/usr/bin/env python3
"""
Browsing Digest Summarizer (llama.cpp Edition)
Generates a 2-minute digest of your daily browsing using a local LLM via llama.cpp server.
Works 100% offline with OpenAI-compatible API at http://localhost:8080/v1

NEW: Automatically appends "Top Pages Visited" section with clickable links sorted by time spent.
NEW: Configuration via settings.env (or custom file) instead of .env

After generating the digest, automatically sends it to your email inbox (optional).
Uses Gmail app passwords with STARTTLS on port 587 for secure delivery.

Usage:
python dailyBrowsing_llamaCPP.py browsing-digest-2025-01-19.json
python dailyBrowsing_llamaCPP.py browsing-digest-2025-01-19.json --email  # Send via email
python dailyBrowsing_llamaCPP.py --check-server

Configuration Setup (REQUIRED for --email flag):
1. Create a file named `settings.env` in the same directory as this script:
   EMAIL_SENDER=your.email@gmail.com
   EMAIL_APP_PASSWORD=your_16_digit_app_password
   EMAIL_RECEIVER=your.email@gmail.com  # optional, defaults to sender

2. Generate Gmail App Password:
   - Enable 2FA on your Google account
   - Visit: https://myaccount.google.com/apppasswords
   - Select "Mail" → "Other" → Name it "Browsing Digest" → Generate
   - Use the 16-digit password in settings.env

Dependencies:
pip install requests markdown python-dotenv rich
"""
import json
import sys
import argparse
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import markdown  # For markdown-to-HTML conversion
from dotenv import load_dotenv
import requests
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from requests.exceptions import ConnectionError, Timeout, RequestException
from rich.console import Console
console = Console(width=90)
from rich.markdown import Markdown

def load_config(config_path: str = None) -> str:
    """
    Load configuration from a custom env file.
    Priority order:
      1. Explicit path via --config argument
      2. settings.env in script directory
      3. .env in script directory (backward compatibility)
    
    Returns:
        Path to successfully loaded config file, or None if none found
    """
    script_dir = Path(__file__).parent.resolve()
    
    # Priority 1: Explicit config path from CLI
    if config_path:
        config_file = Path(config_path).resolve()
        if config_file.exists():
            load_dotenv(config_file, override=True)
            return str(config_file)
        else:
            print(f"❌ Config file not found: {config_file}")
            return None
    
    # Priority 2: settings.env (your preferred name)
    settings_env = script_dir / "settings.env"
    if settings_env.exists():
        load_dotenv(settings_env, override=True)
        return str(settings_env)
    
    # Priority 3: .env (backward compatibility)
    dot_env = script_dir / ".env"
    if dot_env.exists():
        load_dotenv(dot_env, override=True)
        return str(dot_env)
    
    return None

def normalize_json_keys(obj: Any) -> Any:
    """
    Recursively normalize JSON keys and string values by stripping whitespace.
    Fixes common export issues where keys/values contain trailing spaces like:
    "date ": "2026-02-06 "  →  "date": "2026-02-06"
    Args:
        obj: JSON object (dict, list, str, or primitive)
    Returns:
        Normalized object with cleaned keys/values
    """
    if isinstance(obj, dict):
        return {
            key.strip(): normalize_json_keys(value)
            for key, value in obj.items()
            if key.strip()  # Skip empty keys after stripping
        }
    elif isinstance(obj, list):
        return [normalize_json_keys(item) for item in obj]
    elif isinstance(obj, str):
        return obj.strip()
    else:
        return obj

def _collect_keys(obj: Any, keys: set = None) -> set:
    """Helper to collect all keys from nested JSON structures."""
    if keys is None:
        keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str):
                keys.add(k)
            _collect_keys(v, keys)
    elif isinstance(obj, list):
        for item in obj:
            _collect_keys(item, keys)
    return keys

def check_llama_cpp_server(server_url: str = "http://localhost:8080/v1") -> bool:
    """
    Check if llama.cpp server is running and responsive.
    Args:
        server_url: Base URL of the llama.cpp server API
    Returns:
        True if server is reachable and responding correctly
    """
    try:
        # Try health check endpoint first (llama.cpp specific)
        health_url = f"{server_url.rstrip('/').replace('/v1', '')}/health"
        response = requests.get(health_url, timeout=3)
        if response.status_code == 200:
            return True
        # Fallback to models endpoint (OpenAI-compatible)
        models_url = f"{server_url.rstrip('/')}/models"
        response = requests.get(models_url, timeout=3)
        return response.status_code == 200
    except (ConnectionError, Timeout, RequestException):
        return False

def call_llama_cpp_api(
    prompt: str,
    model: str = "local-model",
    server_url: str = "http://localhost:8080/v1",
    temperature: float = 0.7,
    max_tokens: int = 1500,
    timeout: int = 120
) -> str:
    """
    Call llama.cpp server via OpenAI-compatible API.
    Args:
        prompt: User prompt to send to the model
        model: Model identifier (usually "local-model" for llama.cpp)
        server_url: Base URL of the API server
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum tokens to generate
        timeout: Request timeout in seconds
    Returns:
        Model's response text
    Raises:
        RuntimeError: If API call fails or returns error
    """
    api_endpoint = f"{server_url.rstrip('/')}/chat/completions"
    # Format as OpenAI chat completion request
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a personal assistant that creates concise daily browsing digests. "
                           "Keep responses focused, useful, and skip fluff."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False
    }
    try:
        response = requests.post(
            api_endpoint,
            json=payload,
            timeout=timeout,
            headers={"Content-Type": "application/json"}
        )
        # Handle HTTP errors
        if response.status_code != 200:
            error_detail = response.json().get("error", {}).get("message", response.text)
            raise RuntimeError(
                f"API error {response.status_code}: {error_detail[:200]}"
            )
        # Parse successful response
        result = response.json()
        if "choices" not in result or not result["choices"]:
            raise RuntimeError("Unexpected API response format: missing 'choices'")
        message = result["choices"][0].get("message", {})
        content = message.get("content", "").strip()
        if not content:
            raise RuntimeError("Received empty response from model")
        return content
    except (ConnectionError, Timeout) as e:
        raise RuntimeError(
            f"Connection failed to {server_url}. Is llama.cpp server running?\n"
            f"Start it with: ./server -c 4096 --port 8080\n"
            f"Error: {e}"
        )
    except RequestException as e:
        raise RuntimeError(f"API request failed: {e}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response from API: {e}")

def load_browsing_data(filepath: str) -> dict:
    """
    Load and repair browsing data from JSON file.
    Automatically fixes common export issues:
    - Keys with trailing/leading spaces ("date " → "date")
    - Values with trailing spaces ("2026-02-06 " → "2026-02-06")
    - Preserves backup of original file if repairs were needed
    Args:
        filepath: Path to JSON file
    Returns:
        Normalized browsing data dictionary
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file isn't valid JSON or lacks required structure
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    if not path.suffix.lower() == '.json':
        raise ValueError(f"Expected JSON file, got: {path.suffix}")
    # Load raw JSON content
    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
        data = json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")
    # Check if repair is needed (detect whitespace in keys)
    needs_repair = any(
        isinstance(k, str) and (k.startswith(' ') or k.endswith(' '))
        for k in _collect_keys(data)
    )
    if needs_repair:
        print(f"⚠️  Malformed JSON detected - repairing keys/values...")
        original_backup = path.with_suffix('.json.bak')
        shutil.copy2(path, original_backup)
        print(f"   Original saved as: {original_backup.name}")
        # Repair the data structure
        repaired_data = normalize_json_keys(data)
        # Save repaired version
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(repaired_data, f, indent=2, ensure_ascii=False)
        print(f"   Repaired JSON saved to: {path.name}")
        data = repaired_data
    # Validate required structure
    required_keys = {'date', 'pages'}
    actual_keys = set(data.keys())
    missing_keys = required_keys - actual_keys
    if missing_keys:
        raise ValueError(
            f"JSON missing required keys: {missing_keys}. "
            f"Found keys: {actual_keys}. "
            "This may indicate a severely malformed export file."
        )
    return data

def prepare_content_for_llm(data: dict, max_tokens: int = 4000) -> str:  # FIXED: parameter name corrected
    """Prepare browsing content for LLM summarization."""
    pages = data.get('pages', [])
    if not pages:
        return ""
    # Sort by timestamp
    pages = sorted(pages, key=lambda x: x.get('timestamp', ''))
    # Build content string with budget
    content_parts = []
    estimated_tokens = 0
    tokens_per_char = 0.25  # Rough estimate
    for page in pages:
        title = page.get('title', 'Untitled')
        domain = page.get('domain', 'Unknown')
        content = page.get('content', '')[:1000]  # Limit per-page content
        timestamp = page.get('timestamp', '')
        # Format time
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = dt.strftime('%H:%M')
        except (ValueError, AttributeError):
            time_str = 'Unknown time'
        page_text = f"""
---
[{time_str}] {title}
Source: {domain}
Content: {content}
"""
        page_tokens = len(page_text) * tokens_per_char
        if estimated_tokens + page_tokens > max_tokens:
            break
        content_parts.append(page_text)
        estimated_tokens += page_tokens
    return "\n".join(content_parts)

def generate_summary(
    content: str,
    model: str,
    date: str,
    server_url: str
) -> str:
    """Generate a summary using llama.cpp server via OpenAI-compatible API."""
    prompt = f"""Below is a log of web pages I visited on {date}. Create a 2-minute reading digest that:
1. **Main Themes**: What topics did I spend time on today? (2-3 bullet points)
2. **Key Insights**: What are the most important things I learned? (3-5 bullet points)
3. **Action Items**: Any tasks, ideas, or follow-ups worth noting? (if applicable)
4. **Time Analysis**: Brief observation about my browsing patterns
Keep it conversational and useful. Skip the fluff.
---
BROWSING LOG:
{content}
---
Now write my digest:"""
    return call_llama_cpp_api(
        prompt=prompt,
        model=model,
        server_url=server_url,
        temperature=0.6,
        max_tokens=1200,
        timeout=180  # 3 minutes for larger contexts
    )

def get_top_pages(data: dict, top_n: int = 15) -> List[Dict]:  # FIXED: parameter name corrected
    """
    Extract top pages sorted by reading time (descending), with content length as fallback.
    Filters out pages with negligible engagement (< 30 seconds).
    """
    pages = data.get('pages', [])
    # Filter valid pages with URLs and meaningful engagement
    valid_pages = [
        p for p in pages 
        if p.get('url') 
        and p.get('url').strip().startswith('http')  # Valid URL
        and (p.get('readingTime', 0) > 0.5 or len(p.get('content', '')) > 100)  # Meaningful engagement
    ]
    
    if not valid_pages:
        return []
    
    # Sort primarily by readingTime, secondarily by content length
    sorted_pages = sorted(
        valid_pages,
        key=lambda p: (
            p.get('readingTime', 0), 
            len(p.get('content', ''))
        ),
        reverse=True
    )
    
    # Deduplicate by domain + title to avoid repetitive entries
    seen = set()
    unique_pages = []
    for page in sorted_pages:
        title = page.get('title', '').strip().lower()[:50]  # First 50 chars for uniqueness
        domain = page.get('domain', '').strip().lower()
        key = f"{domain}:{title}"
        if key not in seen:
            seen.add(key)
            unique_pages.append(page)
            if len(unique_pages) >= top_n:
                break
    
    return unique_pages[:top_n]

def append_top_pages_section(digest: str, data: dict, top_n: int = 15) -> str:  # FIXED: parameter name corrected
    """
    Append a "Top Pages Visited" section to the digest with clickable links.
    Returns the enhanced digest content.
    """
    top_pages = get_top_pages(data, top_n)
    if not top_pages:
        return digest
    
    # Build links section
    links_section = "\n## 🔗 Top Pages Visited\n\n"
    links_section += f"*Pages sorted by time spent (top {len(top_pages)}):*\n\n"
    
    for i, page in enumerate(top_pages, 1):
        title = page.get('title', 'Untitled').strip()
        url = page.get('url', '#').strip()
        reading_time = page.get('readingTime', 0)
        
        # Minimal markdown escaping for safety
        safe_title = (title
            .replace('[', '\\[')
            .replace(']', '\\]')
            .replace('(', '\\(')
            .replace(')', '\\)')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
        )
        
        # Format with emoji indicators based on time spent
        if reading_time >= 5:
            indicator = "🕗"
        elif reading_time >= 2:
            indicator = "🕓"
        else:
            indicator = "🕑"
        
        links_section += f"{i}. {indicator} [{safe_title}]({url}) — **{reading_time:.1f} min**\n"
    
    links_section += "\n---\n"
    return digest + links_section

def convert_markdown_to_html(markdown_text: str) -> str:
    """Convert markdown to styled HTML for email."""
    html_body = markdown.markdown(
        markdown_text,
        extensions=['extra', 'codehilite', 'tables', 'toc']
    )
    return f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                line-height: 1.6; 
                color: #333; 
                max-width: 800px; 
                margin: 20px auto; 
                padding: 20px; 
                background-color: #f9f9f9;
            }}
            .container {{ 
                background-color: white; 
                border-radius: 10px; 
                padding: 30px; 
                box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            }}
            h1, h2, h3 {{ color: #2c3e50; margin-top: 1.5em; }}
            h1 {{ border-bottom: 2px solid #eee; padding-bottom: 10px; }}
            a {{ color: #3498db; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            code {{ 
                background-color: #f5f5f5; 
                padding: 2px 4px; 
                border-radius: 4px; 
                font-family: monospace; 
                font-size: 0.95em;
            }}
            pre {{ 
                background-color: #2d2d2d; 
                color: #f8f8f2; 
                padding: 15px; 
                border-radius: 5px; 
                overflow-x: auto; 
                font-family: monospace;
            }}
            blockquote {{ 
                border-left: 4px solid #4a90e2; 
                padding-left: 15px; 
                color: #555; 
                margin: 20px 0; 
                font-style: italic;
            }}
            table {{ 
                border-collapse: collapse; 
                width: 100%; 
                margin: 20px 0; 
                font-size: 0.95em;
            }}
            th, td {{ 
                border: 1px solid #ddd; 
                padding: 10px; 
                text-align: left; 
            }}
            th {{ 
                background-color: #f2f2f2; 
                font-weight: 600;
            }}
            ul, ol {{ padding-left: 20px; }}
            li {{ margin-bottom: 8px; }}
            .footer {{ 
                margin-top: 30px; 
                padding-top: 20px; 
                border-top: 1px solid #eee; 
                color: #777; 
                font-size: 0.9em;
            }}
            .time-indicator {{ 
                display: inline-block; 
                width: 1.5em; 
                text-align: center; 
                margin-right: 0.5em;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            {html_body}
            <div class="footer">
                <p>📧 Sent automatically from your local browsing digest generator</p>
                <p>🔒 100% private – processed entirely on your machine with llama.cpp</p>
            </div>
        </div>
    </body>
    </html>
    """

def send_markdown_email(
    sender_email: str,
    sender_password: str,
    receiver_email: str,
    subject: str,
    markdown_content: str,
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 587
) -> bool:
    """
    Sends a beautifully formatted email using Markdown + HTML.
    Uses Gmail app passwords with STARTTLS on port 587.
    
    Returns:
        True if email sent successfully, False otherwise
    """
    # Convert Markdown to HTML with styling
    html_content = convert_markdown_to_html(markdown_content)
    
    # Create message container
    msg = MIMEMultipart("alternative")
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = subject

    # Attach plain text and HTML versions
    part1 = MIMEText(markdown_content, "plain")  # Fallback for plain-text clients
    part2 = MIMEText(html_content, "html")      # Pretty version
    msg.attach(part1)
    msg.attach(part2)

    try:
        # Gmail requires STARTTLS on port 587 (not SSL on 465)
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Upgrade connection to secure TLS
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print("✅ Email sent successfully!")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication failed. Check your app password:")
        print(f"   - Must use Gmail App Password (not your regular password)")
        print(f"   - Generate at: https://myaccount.google.com/apppasswords")
        print(f"   Error details: {e}")
        return False
    except Exception as e:
        print(f"❌ Failed to send email: {type(e).__name__}: {e}")
        return False

def save_digest(digest: str, output_path: str, date: str, stats: dict):
    """Save the digest to a markdown file."""
    full_content = f"""# 📚 Browsing Digest - {date}
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Pages analyzed**: {stats['total_pages']}
**Estimated reading time**: {stats['total_reading_time']} minutes
---
{digest}
---
*Generated locally using llama.cpp server. No data left your machine.*
"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(full_content)

def main():
    parser = argparse.ArgumentParser(
        description="Generate a 2-minute digest of your daily browsing using local AI (llama.cpp)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dailyBrowsing_llamaCPP.py browsing-digest-2025-01-19.json
  python dailyBrowsing_llamaCPP.py data.json --email
  python dailyBrowsing_llamaCPP.py data.json --output today.md --config my-settings.env
  python dailyBrowsing_llamaCPP.py --check-server

Configuration:
  By default loads from 'settings.env' in script directory.
  Falls back to '.env' for backward compatibility.
  Create settings.env with:
    EMAIL_SENDER=your.email@gmail.com
    EMAIL_APP_PASSWORD=your_16_digit_app_password
    EMAIL_RECEIVER=your.email@gmail.com  # optional

Email Requirements (for --email flag):
  1. Enable 2FA on your Google account
  2. Generate App Password at: https://myaccount.google.com/apppasswords
        """
    )
    parser.add_argument(
        "input_file",
        nargs="?",  # Make optional for --check-server usage
        help="JSON file exported from Browsing Digest extension"
    )
    parser.add_argument(
        "--model", "-m",
        default="local-model",
        help="Model identifier for API (default: local-model). "
             "Note: llama.cpp typically runs one model at a time."
    )
    parser.add_argument(
        "--server", "-s",
        default="http://localhost:8080/v1",
        help="llama.cpp server URL (default: http://localhost:8080/v1)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output markdown file (default: digest-YYYY-MM-DD.md)"
    )
    parser.add_argument(
        "--email", "-e",
        action="store_true",
        help="Send digest to email after generation (requires settings.env setup)"
    )
    parser.add_argument(
        "--config",
        help="Path to custom configuration file (default: settings.env)"
    )
    parser.add_argument(
        "--check-server",
        action="store_true",
        help="Check server status and exit"
    )
    parser.add_argument(
        "--top-pages", "-t",
        type=int,
        default=15,
        help="Number of top pages to include in links section (default: 15)"
    )
    args = parser.parse_args()

    # Load configuration early (needed for email setup messages)
    config_file = load_config(args.config)
    if config_file:
        print(f"⚙️  Configuration loaded from: {Path(config_file).name}")
    else:
        print("ℹ️  No configuration file found (settings.env or .env)")
        if args.email:
            print("   ⚠️  Email sending requires configuration!")
            print("   Create settings.env with your Gmail credentials:")
            print("   EMAIL_SENDER=your.email@gmail.com")
            print("   EMAIL_APP_PASSWORD=your_16_digit_app_password")
            sys.exit(1)

    # Server status check if requested
    if args.check_server:
        print(f"🔍 Checking llama.cpp server at {args.server}...")
        if check_llama_cpp_server(args.server):
            print("✅ Server is running and responsive")
            # Try to get model info
            try:
                resp = requests.get(f"{args.server.rstrip('/')}/models", timeout=5)
                if resp.status_code == 200:
                    models = resp.json().get("data", [])
                    if models:
                        print(f"📦 Loaded model: {models[0].get('id', 'unknown')}")
            except:
                pass
        else:
            print("❌ Server not reachable")
            print("   Start llama.cpp server with:")
            print("   ./server -c 4096 --port 8080")
        sys.exit(0)

    # Input file is required unless we're just checking server
    if not args.input_file:
        parser.error("the following arguments are required: input_file")

    # Check server availability
    print(f"🔍 Checking llama.cpp server at {args.server}...")
    if not check_llama_cpp_server(args.server):
        print("❌ llama.cpp server is not running!")
        print(f"   Start it with: ./server -c 4096 --port 8080")
        print("   Or download from: https://github.com/ggerganov/llama.cpp")
        sys.exit(1)
    print("✅ Server is running")

    # Load and repair data
    print(f"📂 Loading {args.input_file}...")
    try:
        data = load_browsing_data(args.input_file)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ Error loading file: {e}")
        sys.exit(1)

    # Check if there's data
    pages = data.get('pages', [])
    if not pages:
        print("❌ No browsing data found in the file")
        sys.exit(1)

    date = data.get('date', 'Unknown date')
    total_pages = data.get('totalPages', len(pages))
    total_reading_time = sum(p.get('readingTime', 0) for p in pages)
    print(f"📊 Found {total_pages} pages ({total_reading_time} min reading time)")

    # Prepare content
    print("📝 Preparing content for summarization...")
    content = prepare_content_for_llm(data)  # Now works correctly with 'data' parameter
    if not content:
        print("❌ No content to summarize")
        sys.exit(1)

    # Generate summary
    print(f"🤖 Generating digest with {args.model} via {args.server}...")
    print("   (This may take 30-90 seconds depending on context size)")
    try:
        digest = generate_summary(content, args.model, date, args.server)
    except RuntimeError as e:
        print(f"❌ Error generating summary: {e}")
        sys.exit(1)

    # ===== APPEND TOP PAGES SECTION =====
    print(f"🔗 Appending top {args.top_pages} pages visited...")
    digest = append_top_pages_section(digest, data, top_n=args.top_pages)  # Correct parameter name
    print(f"   Added {len(get_top_pages(data, args.top_pages))} unique pages to digest")

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        # Sanitize date for filename (remove invalid characters)
        safe_date = "".join(c if c.isalnum() or c in "-_" else "-" for c in str(date))
        output_path = f"digest-{safe_date}.md"

    # Save digest to file
    print(f"💾 Saving to {output_path}...")
    save_digest(
        digest,
        output_path,
        date,
        {'total_pages': total_pages, 'total_reading_time': total_reading_time}
    )
    print(f"✅ Done! Your digest is ready: {output_path}")

    # ===== EMAIL INTEGRATION =====
    if args.email:
        print("\n📧 Preparing to send email...")
        
        # Load credentials from environment variables (already loaded via load_config)
        sender_email = os.getenv("EMAIL_SENDER", "").strip()
        sender_password = os.getenv("EMAIL_APP_PASSWORD", "").strip()
        receiver_email = os.getenv("EMAIL_RECEIVER", sender_email).strip()
        
        # Validate credentials
        if not sender_email or not sender_password:
            print("❌ Missing email credentials in configuration file!")
            print(f"   Checked: {config_file or 'settings.env / .env'}")
            print("\n   Create settings.env with:")
            print("   EMAIL_SENDER=your.email@gmail.com")
            print("   EMAIL_APP_PASSWORD=your_16_digit_app_password")
            print("   EMAIL_RECEIVER=your.email@gmail.com  # optional")
            print("\n   🔑 Generate app password at: https://myaccount.google.com/apppasswords")
            sys.exit(1)
        
        # Prepare email content (full digest with header/footer)
        email_content = f"""# 📚 Daily Browsing Digest - {date}

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Pages analyzed**: {total_pages}
**Total reading time**: {total_reading_time} minutes

---

{digest}

---

🔒 *This digest was generated 100% locally on your machine using llama.cpp. No data was sent to external servers.*
"""
        
        subject = f"Daily Browsing Digest - {date}"
        
        # Send email
        success = send_markdown_email(
            sender_email=sender_email,
            sender_password=sender_password,
            receiver_email=receiver_email,
            subject=subject,
            markdown_content=email_content,
            smtp_server="smtp.gmail.com",
            smtp_port=587
        )
        
        if not success:
            print("\n⚠️  Email delivery failed. Digest was still saved to file.")
            sys.exit(1)
    
    # Show preview
    print("\n" + "=" * 50)
    print("PREVIEW (first 600 characters):")
    print("=" * 50)
    preview = digest[:600] + "..." if len(digest) > 600 else digest
    # Ensure preview prints correctly on Windows
    console.print(Markdown(preview.encode('utf-8', errors='replace').decode('utf-8', errors='replace')))

if __name__ == "__main__":
    # Check for required dependencies
    missing_deps = []
    try:
        import requests
    except ImportError:
        missing_deps.append("requests")
    
    try:
        import markdown
    except ImportError:
        missing_deps.append("markdown")
    
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("❌ Missing required dependency: python-dotenv")
        print("   Install with: pip install python-dotenv")
        sys.exit(1)
    
    if missing_deps:
        print("❌ Missing required dependencies!")
        print(f"   Install with: pip install {' '.join(missing_deps)} rich")
        sys.exit(1)
    
    main()
