"""
app.py — Flask web front-end for the PII Redaction Tool.

Fixes applied for Render deployment:
  - Correct imports from pii_redactor package (not the old broken `redact`)
  - spaCy model + Redactor loaded once at startup, not per request
  - Temp files written to /tmp/ (writable on all platforms)
  - Gunicorn-compatible (no debug mode in production)
"""

import os
import sys
import tempfile
import uuid
from pathlib import Path

import spacy
from flask import Flask, request, send_file, jsonify

from pii_redactor.redactor import Redactor
from pii_redactor.docx_io import redact_docx

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload limit

# Load spaCy model and Redactor once at startup
print("Loading spaCy model en_core_web_sm …", file=sys.stderr)
_nlp = spacy.load("en_core_web_sm")
_redactor = Redactor(nlp=_nlp, seed=42)
print("Model loaded. Ready.", file=sys.stderr)

# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>PII Redaction Tool — Shield Your Documents</title>
  <meta name="description" content="Upload a DOCX file and instantly redact all personally identifiable information (PII) including names, emails, phone numbers, addresses, and more." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet" />
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg-deep:    #080c14;
      --bg-card:    rgba(255,255,255,0.04);
      --border:     rgba(255,255,255,0.10);
      --accent:     #6366f1;
      --accent-2:   #8b5cf6;
      --success:    #10b981;
      --danger:     #ef4444;
      --text:       #f1f5f9;
      --muted:      #94a3b8;
      --radius:     20px;
    }

    html, body {
      min-height: 100vh;
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--bg-deep);
      color: var(--text);
      overflow-x: hidden;
    }

    /* Animated gradient background orbs */
    body::before, body::after {
      content: '';
      position: fixed;
      border-radius: 50%;
      filter: blur(120px);
      opacity: 0.18;
      pointer-events: none;
      animation: drift 14s ease-in-out infinite alternate;
    }
    body::before {
      width: 600px; height: 600px;
      background: radial-gradient(circle, #6366f1, #8b5cf6);
      top: -200px; left: -150px;
    }
    body::after {
      width: 500px; height: 500px;
      background: radial-gradient(circle, #06b6d4, #3b82f6);
      bottom: -150px; right: -100px;
      animation-delay: -7s;
    }
    @keyframes drift {
      from { transform: translate(0,0) scale(1); }
      to   { transform: translate(60px, 40px) scale(1.08); }
    }

    /* Layout */
    .page {
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 40px 20px;
      position: relative;
      z-index: 1;
    }

    /* Header */
    .header { text-align: center; margin-bottom: 48px; }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 16px;
      border-radius: 100px;
      background: rgba(99,102,241,0.15);
      border: 1px solid rgba(99,102,241,0.35);
      font-size: 12px;
      font-weight: 600;
      color: #a5b4fc;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 20px;
    }
    .badge::before { content: '🔒'; }
    h1 {
      font-size: clamp(2rem, 5vw, 3.5rem);
      font-weight: 800;
      line-height: 1.15;
      letter-spacing: -0.02em;
      background: linear-gradient(135deg, #e0e7ff 0%, #a5b4fc 50%, #c4b5fd 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      margin-bottom: 14px;
    }
    .subtitle {
      font-size: 1.05rem;
      color: var(--muted);
      max-width: 480px;
      line-height: 1.6;
    }

    /* Card */
    .card {
      width: 100%;
      max-width: 560px;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      backdrop-filter: blur(24px);
      -webkit-backdrop-filter: blur(24px);
      padding: 40px 36px;
      box-shadow: 0 25px 60px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.05);
    }

    /* Drop zone */
    .drop-zone {
      border: 2px dashed rgba(99,102,241,0.35);
      border-radius: 14px;
      padding: 48px 24px;
      text-align: center;
      cursor: pointer;
      transition: border-color 0.2s, background 0.2s, transform 0.15s;
      position: relative;
      overflow: hidden;
    }
    .drop-zone:hover, .drop-zone.dragover {
      border-color: var(--accent);
      background: rgba(99,102,241,0.08);
      transform: translateY(-2px);
    }
    .drop-zone input[type="file"] {
      position: absolute;
      inset: 0;
      opacity: 0;
      cursor: pointer;
      width: 100%;
      height: 100%;
    }
    .drop-icon {
      font-size: 3rem;
      margin-bottom: 16px;
      display: block;
      filter: drop-shadow(0 0 18px rgba(99,102,241,0.6));
      animation: float 3s ease-in-out infinite;
    }
    @keyframes float {
      0%, 100% { transform: translateY(0); }
      50%       { transform: translateY(-8px); }
    }
    .drop-label {
      font-size: 0.95rem;
      color: var(--text);
      font-weight: 500;
    }
    .drop-label span { color: #a5b4fc; text-decoration: underline; text-underline-offset: 3px; }
    .drop-hint {
      margin-top: 8px;
      font-size: 0.8rem;
      color: var(--muted);
    }

    /* Selected file chip */
    #file-chip {
      display: none;
      align-items: center;
      gap: 10px;
      margin-top: 16px;
      background: rgba(99,102,241,0.12);
      border: 1px solid rgba(99,102,241,0.3);
      border-radius: 10px;
      padding: 10px 14px;
      font-size: 0.88rem;
      color: #c7d2fe;
      word-break: break-all;
    }
    #file-chip.visible { display: flex; }
    .chip-icon { font-size: 1.1rem; flex-shrink: 0; }

    /* Submit button */
    .btn {
      margin-top: 24px;
      width: 100%;
      padding: 15px;
      border: none;
      border-radius: 12px;
      font-size: 1rem;
      font-weight: 700;
      font-family: inherit;
      cursor: pointer;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      color: #fff;
      letter-spacing: 0.02em;
      transition: transform 0.15s, box-shadow 0.15s, opacity 0.2s;
      box-shadow: 0 8px 24px rgba(99,102,241,0.35);
      position: relative;
      overflow: hidden;
    }
    .btn:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 12px 32px rgba(99,102,241,0.50);
    }
    .btn:active:not(:disabled) { transform: translateY(0); }
    .btn:disabled {
      opacity: 0.55;
      cursor: not-allowed;
      transform: none;
    }
    .btn .btn-text { display: flex; align-items: center; justify-content: center; gap: 8px; }

    /* Spinner */
    .spinner {
      display: none;
      width: 18px; height: 18px;
      border: 2.5px solid rgba(255,255,255,0.3);
      border-top-color: #fff;
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* Status / error */
    #status {
      margin-top: 18px;
      padding: 12px 16px;
      border-radius: 10px;
      font-size: 0.88rem;
      font-weight: 500;
      display: none;
      align-items: center;
      gap: 10px;
    }
    #status.success {
      background: rgba(16,185,129,0.12);
      border: 1px solid rgba(16,185,129,0.3);
      color: #6ee7b7;
      display: flex;
    }
    #status.error {
      background: rgba(239,68,68,0.12);
      border: 1px solid rgba(239,68,68,0.3);
      color: #fca5a5;
      display: flex;
    }

    /* PII tag list */
    .tags {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 28px;
      justify-content: center;
    }
    .tag {
      padding: 4px 12px;
      border-radius: 100px;
      font-size: 0.72rem;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.1);
      color: var(--muted);
    }

    /* Footer */
    footer {
      margin-top: 36px;
      font-size: 0.78rem;
      color: rgba(148,163,184,0.5);
      text-align: center;
    }
  </style>
</head>
<body>
<div class="page">
  <div class="header">
    <div class="badge">AI-Powered PII Redaction</div>
    <h1>Shield Your Documents</h1>
    <p class="subtitle">Upload any DOCX file and get back a clean, redacted copy — names, emails, phones, addresses and more replaced instantly.</p>
  </div>

  <div class="card">
    <form id="redact-form" action="/redact" method="POST" enctype="multipart/form-data">
      <div class="drop-zone" id="drop-zone">
        <input type="file" name="file" id="file-input" accept=".docx" required />
        <span class="drop-icon">📄</span>
        <p class="drop-label">Drag &amp; drop your file here, or <span>browse</span></p>
        <p class="drop-hint">Supports .docx files up to 50 MB</p>
      </div>

      <div class="tags">
        <span class="tag">Names</span>
        <span class="tag">Emails</span>
        <span class="tag">Phones</span>
        <span class="tag">Addresses</span>
        <span class="tag">SSN</span>
        <span class="tag">Credit Cards</span>
        <span class="tag">IP Addresses</span>
        <span class="tag">Companies</span>
        <span class="tag">Dates of Birth</span>
      </div>

      <div id="file-chip">
        <span class="chip-icon">📎</span>
        <span id="chip-name">No file selected</span>
      </div>

      <div id="status"></div>

      <button class="btn" type="submit" id="submit-btn" disabled>
        <span class="btn-text">
          <span class="spinner" id="spinner"></span>
          <span id="btn-label">Select a file to begin</span>
        </span>
      </button>
    </form>
  </div>

  <footer>All processing happens server-side. Files are deleted immediately after download.</footer>
</div>

<script>
  const input    = document.getElementById('file-input');
  const dropZone = document.getElementById('drop-zone');
  const chip     = document.getElementById('file-chip');
  const chipName = document.getElementById('chip-name');
  const btn      = document.getElementById('submit-btn');
  const btnLabel = document.getElementById('btn-label');
  const spinner  = document.getElementById('spinner');
  const status   = document.getElementById('status');
  const form     = document.getElementById('redact-form');

  function setFile(file) {
    if (!file) return;
    if (!file.name.endsWith('.docx')) {
      showStatus('error', '⚠️ Only .docx files are supported.');
      return;
    }
    chipName.textContent = file.name;
    chip.classList.add('visible');
    btn.disabled = false;
    btnLabel.textContent = 'Redact PII';
    status.className = '';
    status.style.display = 'none';
  }

  input.addEventListener('change', () => setFile(input.files[0]));

  dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) {
      const dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      setFile(file);
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    btn.disabled = true;
    spinner.style.display = 'block';
    btnLabel.textContent = 'Redacting…';
    status.className = '';
    status.style.display = 'none';

    const data = new FormData(form);
    try {
      const res = await fetch('/redact', { method: 'POST', body: data });
      if (res.ok) {
        const blob = await res.blob();
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        a.href     = url;
        a.download = 'redacted_output.docx';
        a.click();
        URL.revokeObjectURL(url);
        showStatus('success', '✅ Done! Your redacted file has been downloaded.');
        btnLabel.textContent = 'Redact Another File';
      } else {
        const msg = await res.text();
        showStatus('error', '❌ ' + (msg || 'Something went wrong. Please try again.'));
        btnLabel.textContent = 'Redact PII';
      }
    } catch (err) {
      showStatus('error', '❌ Network error. Please check your connection and try again.');
      btnLabel.textContent = 'Redact PII';
    } finally {
      spinner.style.display = 'none';
      btn.disabled = false;
    }
  });

  function showStatus(type, msg) {
    status.className = type;
    status.textContent = msg;
  }
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return HTML


@app.route("/redact", methods=["POST"])
def redact():
    if "file" not in request.files:
        return "No file part in request.", 400

    uploaded = request.files["file"]

    if not uploaded.filename:
        return "No file selected.", 400

    if not uploaded.filename.lower().endswith(".docx"):
        return "Please upload a .docx file.", 400

    # Use /tmp so this works on Render (read-only CWD) and locally
    uid = uuid.uuid4().hex
    input_path  = f"/tmp/input_{uid}.docx"
    output_path = f"/tmp/output_{uid}.docx"

    try:
        uploaded.save(input_path)
        redact_docx(input_path, output_path, _redactor)

        return send_file(
            output_path,
            as_attachment=True,
            download_name="redacted_output.docx",
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as exc:
        app.logger.exception("Redaction failed: %s", exc)
        return f"Redaction error: {exc}", 500
    finally:
        # Clean up temp files immediately
        for path in (input_path, output_path):
            try:
                os.remove(path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Entry point (local dev only — Render uses gunicorn)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)