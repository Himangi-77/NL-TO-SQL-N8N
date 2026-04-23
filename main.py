import pyodbc
import os
from fastapi import FastAPI, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
import urllib.parse


load_dotenv()

app = FastAPI(title="SQL Schema API")

# ── Auth ──────────────────────────────────────────────────────────────────────
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def verify_key(key: str = Security(api_key_header)):
    if key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return key

# ── DB connection ─────────────────────────────────────────────────────────────
def get_connection():
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={os.getenv('SQL_SERVER')};"
        f"DATABASE={os.getenv('SQL_DATABASE')};"
        "Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/schema", dependencies=[Security(verify_key)])
def get_schema():
    """
    Returns all tables and columns from INFORMATION_SCHEMA.
    Called by n8n to build the Claude prompt.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                TABLE_NAME,
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
            ORDER BY TABLE_NAME, ORDINAL_POSITION
        """)
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Group columns under their table
    schema: dict = {}
    for table, column, dtype, nullable, max_len in rows:
        if table not in schema:
            schema[table] = []
        schema[table].append({
            "column": column,
            "type": dtype,
            "nullable": nullable == "YES",
            "max_length": max_len
        })

    return {"database": os.getenv("SQL_DATABASE"), "tables": schema}


@app.post("/execute", dependencies=[Security(verify_key)])
def execute_query(payload: dict):
    """
    Optional — runs a generated SQL query and returns results.
    Only enable this after you're satisfied with query quality.
    """
    sql = payload.get("query", "").strip()
    if not sql:
        raise HTTPException(status_code=400, detail="No query provided")

    # Basic safety guard — block anything that mutates data
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "EXEC"]
    if any(word in sql.upper() for word in forbidden):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed")

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"columns": columns, "rows": rows, "row_count": len(rows)}

@app.get("/approve", response_class=HTMLResponse)
def approval_page(
    sql: str = "",
    question: str = "",
    resume_url: str = ""
):
    n8n_url = "https://leukos444.app.n8n.cloud/webhook-test/sql-approve"
    safe_sql      = sql.replace('"', '&quot;')
    safe_question = question.replace('"', '&quot;')

    return f"""
<!DOCTYPE html>
<html>
<head>
  <title>SQL Approval</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:Arial,sans-serif;background:#f5f5f5;
          min-height:100vh;display:flex;justify-content:center;
          align-items:flex-start;padding:40px 20px}}
    .card{{background:#fff;border-radius:10px;padding:32px;
           width:100%;max-width:680px;border:1px solid #ddd;
           box-shadow:0 2px 8px rgba(0,0,0,0.06)}}
    h2{{font-size:20px;color:#333;margin-bottom:20px}}
    .label{{font-size:11px;font-weight:bold;color:#888;
            text-transform:uppercase;margin-bottom:6px;display:block}}
    .question{{font-size:15px;color:#1a73e8;margin-bottom:20px;
               padding:10px;background:#f0f6ff;border-radius:6px}}
    textarea{{width:100%;height:200px;font-family:monospace;font-size:13px;
              padding:12px;border:1px solid #ccc;border-radius:6px;
              resize:vertical;line-height:1.5}}
    textarea:focus{{outline:none;border-color:#1a73e8}}
    .buttons{{display:flex;gap:12px;margin-top:20px;flex-wrap:wrap}}
    .btn{{padding:13px 28px;border:none;border-radius:6px;font-size:14px;
          font-weight:bold;cursor:pointer;text-decoration:none;
          display:inline-block;text-align:center}}
    .approve{{background:#34a853;color:#fff}}
    .reject{{background:#ea4335;color:#fff}}
    .approve:hover{{background:#2d9147}}
    .reject:hover{{background:#d33426}}
    .divider{{border:none;border-top:1px solid #eee;margin:28px 0}}
    .curl-section{{display:none;margin-top:20px}}
    .curl-section.visible{{display:block}}
    .curl-label{{font-size:12px;font-weight:bold;color:#555;margin-bottom:8px}}
    .curl-box{{background:#1e1e1e;color:#d4d4d4;font-family:monospace;
               font-size:12px;padding:14px;border-radius:6px;
               white-space:pre-wrap;word-break:break-all;line-height:1.6}}
    .copy-btn{{margin-top:10px;padding:8px 18px;background:#555;color:#fff;
               border:none;border-radius:4px;font-size:12px;cursor:pointer}}
    .copy-btn:hover{{background:#333}}
    .copy-btn.copied{{background:#34a853}}
    .status{{margin-top:16px;font-size:14px;padding:10px;border-radius:6px;
             display:none}}
    .status.success{{display:block;background:#e6f4ea;color:#2d7a3a}}
    .status.error{{display:block;background:#fce8e6;color:#c5221f}}
    .note{{font-size:12px;color:#999;line-height:1.8;margin-top:4px}}
  </style>
</head>
<body>
<div class="card">
  <h2>🔍 SQL Query Approval</h2>

  <span class="label">Question Asked</span>
  <div class="question">{safe_question}</div>

  <span class="label">Review and edit SQL if needed</span>
  <textarea id="sql-editor" spellcheck="false">{safe_sql}</textarea>

  <div class="buttons">
    <button class="btn approve" onclick="doAction('true')">
      ✅ Approve and Run
    </button>
    <button class="btn reject" onclick="doAction('false')">
      ❌ Reject
    </button>
    <button class="btn" style="background:#f0f0f0;color:#333"
            onclick="showCurl()">
      📋 Generate curl command
    </button>
  </div>

  <div class="status" id="status"></div>

  <div class="curl-section" id="curl-section">
    <hr class="divider"/>
    <div class="curl-label">Run this in your terminal:</div>
    <div class="curl-box" id="curl-box"></div>
    <button class="copy-btn" id="copy-btn" onclick="copyCurl()">
      Copy to clipboard
    </button>
    <p class="note" style="margin-top:12px">
      This curl command sends the query directly to n8n.
      Run it in any terminal to trigger execution.
    </p>
  </div>

</div>

<script>
  var N8N_URL  = "{n8n_url}";
  var question = "{safe_question}";

  function getSql() {{
    return document.getElementById('sql-editor').value.trim();
  }}

  function buildUrl(approved) {{
    return N8N_URL
      + "?approved=" + encodeURIComponent(approved)
      + "&sql="      + encodeURIComponent(getSql())
      + "&question=" + encodeURIComponent(question);
  }}

  function doAction(approved) {{
    var sql = getSql();
    if (approved === 'true' && !sql) {{
      showStatus('Please enter a SQL query before approving.', 'error');
      return;
    }}
    showStatus('Sending to n8n...', 'success');
    window.location.href = buildUrl(approved);
  }}

  function showCurl() {{
    var approved = 'true';
    var sql      = getSql();
    var cmd = 'curl -G "'  + N8N_URL + '" \\\\\\n'
      + '  --data-urlencode "approved=' + approved   + '" \\\\\\n'
      + '  --data-urlencode "sql='      + sql.replace(/"/g,'\\\\"') + '" \\\\\\n'
      + '  --data-urlencode "question=' + question.replace(/"/g,'\\\\"') + '"';

    document.getElementById('curl-box').textContent = cmd;
    var section = document.getElementById('curl-section');
    section.classList.add('visible');
    section.scrollIntoView({{behavior:'smooth'}});
  }}

  function copyCurl() {{
    var text = document.getElementById('curl-box').textContent;
    navigator.clipboard.writeText(text).then(function() {{
      var btn = document.getElementById('copy-btn');
      btn.textContent = 'Copied!';
      btn.classList.add('copied');
      setTimeout(function() {{
        btn.textContent = 'Copy to clipboard';
        btn.classList.remove('copied');
      }}, 2000);
    }});
  }}

  function showStatus(msg, type) {{
    var el = document.getElementById('status');
    el.textContent = msg;
    el.className = 'status ' + type;
  }}
</script>
</body>
</html>
"""

@app.get("/redirect")
def redirect_to_n8n(
    target: str,
    approved: str,
    sql: str = "",
    question: str = ""
):
    base = urllib.parse.unquote(target)
    params = urllib.parse.urlencode({
        "approved": approved,
        "sql": sql,
        "question": question
    })
    final_url = f"{base}?{params}"
    return RedirectResponse(url=final_url)