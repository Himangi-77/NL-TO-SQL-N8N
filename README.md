# NL-TO-SQL-N8N
Ask a question in plain English. Get a SQL query written by AI, reviewed by a human, executed against your database, and the results delivered to your inbox — all automatically.
# 🧠 Natural Language to SQL — AI-Powered Query Generator

> Ask a question in plain English. Get a SQL query written by AI, reviewed by a human, executed against your database, and the results delivered to your inbox — all automatically.

---

## 📋 Table of Contents

- [What This Project Does](#what-this-project-does)
- [Architecture Overview](#architecture-overview)
- [Technologies Used](#technologies-used)
- [How Each Piece Fits Together](#how-each-piece-fits-together)
- [Workflow 1 — Generate SQL](#workflow-1--generate-sql)
- [Workflow 2 — Execute SQL](#workflow-2--execute-sql)
- [The Approval Page](#the-approval-page)
- [Step-by-Step Setup Guide](#step-by-step-setup-guide)
- [Security Model](#security-model)
- [Folder Structure](#folder-structure)

---

## What This Project Does

Most people who work with data are not SQL experts. They know what question they want answered — *"Show me the top 10 clients by revenue last quarter"* — but writing the SQL to answer it requires knowing the exact table names, column names, join conditions, and syntax.

This project solves that. You type a question in plain English. An AI reads your database schema, writes the correct SQL query, and emails it to you for review. You click **Approve** — and the results land in your inbox as a formatted table. No SQL knowledge required.

```
You type:     "Show me total payments by insurance plan this month"
                              │
                              ▼
AI writes:    SELECT p.PlanName, SUM(f.PaymentAmt) AS TotalPayments
              FROM FactAR f
              JOIN DimInsPlan p ON f.PriInsPlanSK = p.InsPlanSK
              JOIN DimDate d ON f.PostingDateSK = d.DateSK
              WHERE d.Mth = MONTH(GETDATE())
              AND d.Yr = YEAR(GETDATE())
              GROUP BY p.PlanName
              ORDER BY TotalPayments DESC
                              │
                              ▼
You review:   Email arrives → check SQL → click Approve
                              │
                              ▼
You receive:  HTML table of results in your inbox
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         YOUR PRIVATE NETWORK                        │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                    YOUR MACHINE                             │   │
│   │                                                             │   │
│   │   ┌──────────────┐        ┌──────────────────────────┐     │   │
│   │   │  SQL Server  │◄──────►│   FastAPI (Python)       │     │   │
│   │   │   (SSMS)     │        │   • /schema              │     │   │
│   │   │              │        │   • /execute             │     │   │
│   │   │  Port 1433   │        │   • /approve             │     │   │
│   │   │  Windows Auth│        │   • /redirect            │     │   │
│   │   └──────────────┘        └──────────┬───────────────┘     │   │
│   │                                      │ Port 8000           │   │
│   └──────────────────────────────────────┼─────────────────────┘   │
│                                          │                          │
│                               ┌──────────▼──────────┐              │
│                               │  Cloudflare Tunnel  │              │
│                               │  (cloudflared)      │              │
│                               └──────────┬──────────┘              │
└──────────────────────────────────────────┼─────────────────────────┘
                                           │ HTTPS
                          ┌────────────────▼────────────────┐
                          │         PUBLIC INTERNET         │
                          │                                 │
                          │   https://xyz.trycloudflare.com │
                          └────────────┬────────────────────┘
                                       │
              ┌────────────────────────┼──────────────────────────┐
              │                        │                          │
              ▼                        ▼                          ▼
   ┌──────────────────┐   ┌─────────────────────┐   ┌────────────────────┐
   │   n8n Cloud      │   │   OpenAI API        │   │   Gmail SMTP       │
   │                  │   │                     │   │                    │
   │  Workflow 1:     │   │  GPT-4o mini        │   │  Sends approval    │
   │  Generate SQL    │   │  Reads schema       │   │  email + results   │
   │                  │   │  Writes T-SQL       │   │  to Outlook inbox  │
   │  Workflow 2:     │   │                     │   │                    │
   │  Execute SQL     │   └─────────────────────┘   └────────────────────┘
   └──────────────────┘
```

---

## Technologies Used

### 🐍 FastAPI (Python)
**What it is:** A modern Python web framework for building APIs.

**What it does in this project:**
FastAPI is the brain of the private network side. It sits on your machine and acts as a secure middleman between the outside world (n8n Cloud) and your SQL Server. It exposes four endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/schema` | GET | Reads all table and column names from SQL Server and returns them as JSON |
| `/execute` | POST | Receives a SQL query, runs it against SQL Server, returns rows and columns |
| `/approve` | GET | Serves the HTML approval page where you can review, edit, approve or reject a query |
| `/redirect` | GET | Acts as a URL relay — reconstructs complex URLs that Outlook would otherwise mangle |

**Why FastAPI and not just direct database access from n8n?**
Your SQL Server is on a private network. n8n Cloud cannot reach it directly. FastAPI bridges that gap — it lives inside your network, talks to SQL Server natively using Windows Authentication, and exposes a clean HTTPS API that n8n can call.

```
n8n Cloud  ──HTTPS──►  FastAPI  ──Windows Auth──►  SQL Server
(public)               (private)                   (private)
```

---

### 🌐 Cloudflare Tunnel (cloudflared)
**What it is:** A free tool from Cloudflare that creates a secure outbound tunnel from your machine to the internet — without opening any firewall ports or configuring your router.

**What it does in this project:**
Your FastAPI server runs on `localhost:8000` — only accessible on your machine. Cloudflare Tunnel punches a secure hole through your firewall and gives it a public HTTPS URL like `https://xyz.trycloudflare.com`. n8n Cloud uses this URL to call your FastAPI endpoints.

**Why this is secure:**
- Traffic goes OUT from your machine — no inbound firewall ports opened
- All traffic is encrypted with HTTPS automatically
- The `X-API-Key` header on every request ensures only your n8n workflow can use it

```
Your Machine          Cloudflare Edge         n8n Cloud
localhost:8000  ◄────  Encrypted Tunnel  ◄────  API calls
                       (outbound only)
```

---

### 🔧 n8n (Workflow Automation)
**What it is:** A workflow automation platform similar to Zapier or Make, but with far more flexibility. Hosted at [cloud.n8n.io](https://cloud.n8n.io).

**What it does in this project:**
n8n is the orchestrator. It connects all the pieces together — receiving questions, fetching schema, calling OpenAI, sending emails, and executing queries. It has two separate workflows:

- **Workflow 1** — Takes a natural language question, fetches the schema, sends it to GPT-4o mini, and emails the generated SQL for approval
- **Workflow 2** — Triggered when you click Approve in the email, executes the SQL, formats the results as an HTML table, and emails them to you

---

### 🤖 OpenAI GPT-4o mini
**What it is:** A fast, cost-effective large language model from OpenAI.

**What it does in this project:**
GPT-4o mini receives a carefully constructed prompt containing your entire database schema and your natural language question. It responds with a T-SQL query that answers the question using the correct table and column names.

**Why GPT-4o mini and not GPT-4o?**
GPT-4o mini is significantly cheaper and faster, and SQL generation from schema is a well-defined task that does not require the full power of GPT-4o. For a schema with 50+ tables, GPT-4o mini produces accurate, well-structured T-SQL reliably.

---

### 📧 Gmail SMTP
**What it is:** Gmail's outbound mail server, accessed using an App Password.

**What it does in this project:**
Sends two types of emails:
1. **Approval email** — Contains the generated SQL and Approve/Reject buttons, sent to `himangi.shukla@ventrahealth.com`
2. **Results email** — Contains the query results formatted as an HTML table, sent after approval

**Why an App Password and not OAuth?**
App Passwords require no OAuth flow, no redirect URIs, no developer console setup. You generate a 16-character password once in your Google account and paste it into n8n. Done.

---

## How Each Piece Fits Together

```
QUESTION ENTERS                     AI GENERATES SQL
──────────────                      ────────────────
curl POST                           n8n sends schema
  │                                 + question to
  ▼                                 GPT-4o mini
n8n Webhook                              │
  │                                      ▼
  ▼                                 SQL query returned
n8n fetches                              │
schema from                              ▼
FastAPI /schema                     n8n extracts
  │                                 clean SQL
  ▼                                      │
SQL Server returns                       ▼
all table/column                    Gmail sends
names as JSON                       approval email
                                         │
HUMAN REVIEWS                            ▼
─────────────               himangi.shukla@ventrahealth.com
Email arrives                   receives email in Outlook
in Outlook
  │
  ├── Click Approve ──► n8n Workflow 2 triggered
  │                          │
  │                          ▼
  │                     FastAPI /execute
  │                     runs SQL on SQL Server
  │                          │
  │                          ▼
  │                     Results formatted
  │                     as HTML table
  │                          │
  │                          ▼
  │                     Gmail sends
  │                     results email
  │                          │
  │                          ▼
  └── Click Reject ──►  Rejection email sent
                        Workflow stops
```

---

## Workflow 1 — Generate SQL

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  WORKFLOW 1: Generate SQL                                                   │
└─────────────────────────────────────────────────────────────────────────────┘

 ┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
 │  1. Webhook  │────►│ 2. HTTP Request  │────►│  3. Code Node    │
 │              │     │                  │     │                  │
 │ POST trigger │     │ GET /schema from │     │ Builds prompt:   │
 │ Receives:    │     │ FastAPI          │     │ schema text +    │
 │ user_query   │     │                  │     │ user question    │
 │              │     │ Returns JSON of  │     │                  │
 │ Protected by │     │ all tables and   │     │ Formats for      │
 │ X-API-Key    │     │ columns          │     │ GPT-4o mini      │
 └──────────────┘     └──────────────────┘     └────────┬─────────┘
                                                         │
         ┌───────────────────────────────────────────────┘
         │
         ▼
 ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
 │  4. OpenAI Node  │────►│  5. Code Node    │────►│ 6. Code Node     │
 │                  │     │                  │     │                  │
 │ Model:           │     │ Extracts SQL     │     │ Prepares email   │
 │ gpt-4o-mini      │     │ from OpenAI      │     │ data:            │
 │                  │     │ response         │     │ • approve_link   │
 │ Receives prompt  │     │                  │     │ • reject_link    │
 │ Returns T-SQL    │     │ Handles both     │     │ • approve_page   │
 │ query            │     │ response formats │     │ • generated_sql  │
 └──────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                             │
         ┌───────────────────────────────────────────────────┘
         │
         ▼
 ┌──────────────────┐
 │  7. Send Email   │
 │                  │
 │ Via Gmail SMTP   │
 │                  │
 │ To: Outlook      │
 │ Contains:        │
 │ • Question asked │
 │ • Generated SQL  │
 │ • Approve button │
 │ • Reject button  │
 └──────────────────┘
```

### Node-by-Node Explanation

#### Node 1 — Webhook
The entry point of the entire system. Sits and waits for an HTTP POST request. When called, it wakes up the workflow.

- **Input:** HTTP POST with `{ "user_query": "your question here" }`
- **Protected by:** `X-API-Key` header — only requests with the correct secret key are accepted
- **Output:** The `user_query` string passed to the next node

```bash
# How to trigger it
curl -X POST https://leukos444.app.n8n.cloud/webhook/sql-query-generator \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-webhook-secret" \
  -d '{"user_query": "Show me top 10 clients by revenue"}'
```

---

#### Node 2 — HTTP Request (Fetch Schema)
Calls your FastAPI `/schema` endpoint over HTTPS through the Cloudflare Tunnel. FastAPI queries `INFORMATION_SCHEMA.COLUMNS` on your SQL Server and returns every table and column as JSON.

- **Input:** Nothing (just fires the GET request)
- **URL:** `https://xyz.trycloudflare.com/schema`
- **Protected by:** `X-API-Key` header matching your FastAPI secret
- **Output:** JSON object with all tables and their columns, data types, and nullable flags

```json
{
  "database": "YourDatabase",
  "tables": {
    "DimClient": [
      { "column": "ClientSK", "type": "int", "nullable": false },
      { "column": "ClientName", "type": "varchar", "nullable": true }
    ]
  }
}
```

---

#### Node 3 — Code Node (Build Prompt)
Takes the schema JSON and the user's question and combines them into a structured prompt for GPT-4o mini. This is where the magic instruction is written — telling the AI exactly what format to respond in.

- **Input:** Schema JSON from Node 2, `user_query` from Node 1
- **Process:** Loops through all tables and formats them as readable text
- **Output:** A single `prompt` string

```
You are a Microsoft SQL Server (T-SQL) expert.

Here is the database schema:

Table: DimClient
  - ClientSK (int)
  - ClientName (varchar, nullable)
  - ClientTier (nvarchar, nullable)
  ...

Write a T-SQL query that answers: "Show me top 10 clients by revenue"

Rules:
- Return ONLY the SQL query
- Use proper T-SQL syntax
- If unanswerable, say: CANNOT_ANSWER
```

---

#### Node 4 — OpenAI Node
Sends the prompt to GPT-4o mini and receives the SQL query back.

- **Model:** `gpt-4o-mini`
- **Max tokens:** 1000
- **Input:** The formatted prompt
- **Output:** Raw OpenAI API response containing the SQL query

---

#### Node 5 — Code Node (Extract SQL)
Parses the OpenAI response. The OpenAI node in n8n can return responses in two different formats depending on the API version — this node handles both.

- **Input:** OpenAI response (either `choices[0].message.content` or `output[0].content[0].text`)
- **Output:** Clean SQL string and the original `user_query`

---

#### Node 6 — Code Node (Prepare Email Data)
Pre-builds all the URLs needed for the approval email. This step exists because building complex URLs with encoded parameters directly inside HTML in the Send Email node is unreliable — n8n sometimes fails to evaluate nested expressions inside HTML blobs.

- **Builds:** `approve_link`, `reject_link`, `approve_page_link`
- **All links point to:** `https://leukos444.app.n8n.cloud/webhook-test/sql-approve`
- **Output:** All data needed by the Send Email node as plain pre-computed strings

---

#### Node 7 — Send Email (Approval)
Sends the approval email via Gmail SMTP. The email contains the generated SQL displayed in a monospace box, and two table-based buttons (Approve and Reject) that link directly to n8n Workflow 2.

- **From:** Your Gmail account
- **To:** `himangi.shukla@ventrahealth.com`
- **Contains:** Question, generated SQL, Approve button, Reject button, link to SQL editor page

---

## Workflow 2 — Execute SQL

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  WORKFLOW 2: Execute SQL (triggered by clicking Approve in email)           │
└─────────────────────────────────────────────────────────────────────────────┘

 ┌──────────────────┐     ┌──────────────────┐
 │  1. Webhook      │────►│  2. IF Node      │
 │                  │     │                  │
 │ GET trigger      │     │ Checks:          │
 │ Triggered by     │     │ approved == true │
 │ clicking Approve │     │                  │
 │ or Reject in     │     │ Routes to true   │
 │ email            │     │ or false branch  │
 │                  │     │                  │
 │ Receives:        │     └──────┬─────┬─────┘
 │ • approved       │            │     │
 │ • sql            │         TRUE│   FALSE│
 │ • question       │            │     │
 └──────────────────┘            │     │
                                 │     ▼
                                 │  ┌──────────────────┐
                                 │  │ 2b. Send Email   │
                                 │  │                  │
                                 │  │ Rejection notice │
                                 │  │ to Outlook       │
                                 │  └──────────────────┘
                                 │
                                 ▼
                      ┌──────────────────┐     ┌──────────────────┐
                      │ 3. HTTP Request  │────►│  4. Code Node    │
                      │                  │     │                  │
                      │ POST /execute    │     │ Formats rows +   │
                      │ to FastAPI       │     │ columns as       │
                      │                  │     │ HTML table       │
                      │ Runs SQL against │     │                  │
                      │ SQL Server       │     │ Styled with      │
                      │                  │     │ alternating rows │
                      │ Returns:         │     │ and headers      │
                      │ columns, rows,   │     │                  │
                      │ row_count        │     └────────┬─────────┘
                      └──────────────────┘              │
                                                        ▼
                                             ┌──────────────────┐
                                             │  5. Send Email   │
                                             │                  │
                                             │ Results email    │
                                             │ to Outlook       │
                                             │                  │
                                             │ Contains:        │
                                             │ • Question asked │
                                             │ • HTML table of  │
                                             │   query results  │
                                             │ • Row count      │
                                             └──────────────────┘
```

### Node-by-Node Explanation

#### Node 1 — Webhook (Approve/Reject trigger)
This is a separate webhook from Workflow 1. It is triggered by clicking the Approve or Reject link in the email — the link is a plain GET URL so clicking it in Outlook fires this webhook directly.

- **Method:** GET
- **Path:** `sql-approve`
- **Receives as query parameters:** `approved`, `sql`, `question`

---

#### Node 2 — IF Node
Routes the workflow based on whether the reviewer approved or rejected.

- **Condition:** `query.approved == true`
- **True branch:** Proceeds to execute the query
- **False branch:** Sends a rejection notification email and stops

---

#### Node 3 — HTTP Request (Execute Query)
Sends the SQL query to your FastAPI `/execute` endpoint. FastAPI runs it against SQL Server using Windows Authentication and returns the results.

- **Method:** POST
- **URL:** `https://xyz.trycloudflare.com/execute`
- **Body:** `{ "query": "SELECT ..." }`
- **Protected by:** `X-API-Key` header
- **Returns:** `{ "columns": [...], "rows": [...], "row_count": N }`

FastAPI has a safety guard that rejects any query containing `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, or `EXEC` — only `SELECT` queries can run.

---

#### Node 4 — Code Node (Format HTML Table)
Takes the raw rows and columns from FastAPI and builds a styled HTML table ready to be sent in an email.

- **Input:** `columns[]`, `rows[]`, `row_count`
- **Output:** A complete HTML document with a styled table, alternating row colors, and a row count footer

---

#### Node 5 — Send Email (Results)
Sends the formatted HTML table to your Outlook inbox.

- **Subject:** `Query Results: [your original question]`
- **Body:** The full styled HTML table from Node 4

---

## The Approval Page

The `/approve` page is served by FastAPI and accessible at:
```
https://xyz.trycloudflare.com/approve
```

It is a self-contained HTML page that gives reviewers three options:

```
┌─────────────────────────────────────────────────────┐
│  🔍 SQL Query Approval                              │
│                                                     │
│  QUESTION ASKED                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ Show me top 10 clients by revenue           │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  REVIEW AND EDIT SQL IF NEEDED                      │
│  ┌─────────────────────────────────────────────┐   │
│  │ SELECT TOP 10 c.ClientName,                 │   │
│  │   SUM(f.PaymentAmt) AS Revenue              │   │
│  │ FROM FactAR f                               │   │
│  │ JOIN DimClient c ON f.ClientSK = c.ClientSK │   │
│  │ GROUP BY c.ClientName                       │   │
│  │ ORDER BY Revenue DESC                       │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌─────────────┐ ┌──────────┐ ┌────────────────┐  │
│  │✅ Approve   │ │❌ Reject │ │📋 Generate curl│  │
│  │   and Run   │ │          │ │   command      │  │
│  └─────────────┘ └──────────┘ └────────────────┘  │
│                                                     │
│  ── Curl command (shown when button clicked) ─────  │
│  ┌─────────────────────────────────────────────┐   │
│  │ curl -G "https://leukos444..." \            │   │
│  │   --data-urlencode "approved=true" \        │   │
│  │   --data-urlencode "sql=SELECT..." \        │   │
│  │   --data-urlencode "question=..."           │   │
│  └─────────────────────────────────────────────┘   │
│  [ Copy to clipboard ]                             │
└─────────────────────────────────────────────────────┘
```

| Action | What Happens |
|--------|-------------|
| Edit SQL textarea | Changes the query before it runs — useful if AI made a mistake |
| Approve and Run | Redirects browser to n8n Workflow 2 webhook with `approved=true` |
| Reject | Redirects to n8n Workflow 2 with `approved=false` — sends rejection email |
| Generate curl command | Shows a ready-to-copy curl command to run from any terminal |

---

## Step-by-Step Setup Guide

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.8+ | Runs FastAPI |
| ODBC Driver 17 | Latest | Connects Python to SQL Server |
| Node.js | 18+ | Required by n8n (self-hosted only) |
| cloudflared | Latest | Cloudflare Tunnel client |

---

### Part 1 — FastAPI Setup

```bash
# 1. Create project folder
mkdir sql-schema-api && cd sql-schema-api

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# 3. Install dependencies
pip install fastapi uvicorn pyodbc python-dotenv
```

Create `.env`:
```env
SQL_SERVER=localhost
SQL_DATABASE=YourDatabaseName
API_SECRET_KEY=fastapi-secret-z9y8x7w6v5u4
```

Create `main.py` — see full source in [`main.py`](./main.py)

Start the server:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Test it:
```bash
curl -H "X-API-Key: fastapi-secret-z9y8x7w6v5u4" http://localhost:8000/schema
```

---

### Part 2 — Cloudflare Tunnel Setup

```bash
# Download cloudflared for Windows
# https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/

# Start the tunnel
cloudflared tunnel --url http://localhost:8000
```

You will see output like:
```
Your quick Tunnel has been created! Visit it at:
https://almost-issn-buried-delivering.trycloudflare.com
```

Copy this URL — you will use it everywhere FastAPI is referenced in n8n.

> ⚠️ The free Cloudflare Tunnel URL changes every time you restart `cloudflared`. For a permanent URL, create a free Cloudflare account and set up a named tunnel.

---

### Part 3 — Gmail App Password

1. Go to [myaccount.google.com](https://myaccount.google.com) → Security → 2-Step Verification → turn on
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. App name: `n8n SQL Approvals` → Create
4. Copy the 16-character password shown — it appears only once

---

### Part 4 — n8n Workflow 1 (Generate SQL)

1. Log in to [cloud.n8n.io](https://cloud.n8n.io) → New Workflow → name it `SQL Query Generator`

**Node 1 — Webhook**
- Method: `POST`
- Path: `sql-query-generator`
- Authentication: Header Auth → `X-API-Key`

**Node 2 — HTTP Request**
- Method: `GET`
- URL: `https://your-cloudflare-url/schema`
- Header: `X-API-Key: fastapi-secret-z9y8x7w6v5u4`

**Node 3 — Code (Build Prompt)**
```javascript
const webhookJson = $('Webhook').first().json;
const userQuery = webhookJson?.body?.user_query || webhookJson?.user_query;
const tables = $('HTTP Request').first().json.tables;

const schemaLines = Object.entries(tables).map(([tableName, columns]) => {
  const cols = columns
    .map(c => `  - ${c.column} (${c.type}${c.nullable ? ', nullable' : ''})`)
    .join('\n');
  return `Table: ${tableName}\n${cols}`;
});

const prompt = `You are a Microsoft SQL Server (T-SQL) expert.

Here is the database schema:

${schemaLines.join('\n\n')}

Write a T-SQL query that answers: "${userQuery}"

Rules:
- Return ONLY the SQL query, no explanation or markdown
- Use proper T-SQL syntax
- Use table aliases where appropriate
- If the question cannot be answered from the schema, say: CANNOT_ANSWER`;

return [{ json: { prompt, user_query: userQuery } }];
```

**Node 4 — OpenAI**
- Model: `gpt-4o-mini`
- Max tokens: `1000`
- Message: `{{ $json.prompt }}`

**Node 5 — Code (Extract SQL)**
```javascript
const responseData = $input.first().json;
const userQuery = $('Webhook').first().json.body.user_query;

let sql = '';
if (responseData.choices?.[0]?.message?.content) {
  sql = responseData.choices[0].message.content.trim();
} else if (responseData.output?.[0]?.content?.[0]?.text) {
  sql = responseData.output[0].content[0].text.trim();
}

const canAnswer = !sql.startsWith('CANNOT_ANSWER');
return [{ json: { generated_sql: canAnswer ? sql : null, can_answer: canAnswer, user_query: userQuery } }];
```

**Node 6 — Code (Prepare Email Data)**
```javascript
const generatedSql  = $input.first().json.generated_sql;
const userQuery     = $('Webhook').first().json.body.user_query;
const cloudflareUrl = 'https://your-cloudflare-url.trycloudflare.com';
const n8nWebhook    = 'https://leukos444.app.n8n.cloud/webhook/sql-approve';

const approveLink = cloudflareUrl
  + '/redirect?target=' + encodeURIComponent(n8nWebhook)
  + '&approved=true'
  + '&sql='      + encodeURIComponent(generatedSql)
  + '&question=' + encodeURIComponent(userQuery);

const rejectLink = cloudflareUrl
  + '/redirect?target=' + encodeURIComponent(n8nWebhook)
  + '&approved=false&sql=&question=' + encodeURIComponent(userQuery);

const approvePageLink = cloudflareUrl
  + '/approve?resume_url=' + encodeURIComponent(n8nWebhook)
  + '&sql='      + encodeURIComponent(generatedSql)
  + '&question=' + encodeURIComponent(userQuery);

return [{ json: { generated_sql: generatedSql, user_query: userQuery,
                  approve_link: approveLink, reject_link: rejectLink,
                  approve_page_link: approvePageLink } }];
```

**Node 7 — Send Email** — see full HTML template in [`email_approval.html`](./email_approval.html)

---

### Part 5 — n8n Workflow 2 (Execute SQL)

1. New Workflow → name it `SQL Execute and Email Results`

**Node 1 — Webhook**
- Method: `GET`
- Path: `sql-approve`

**Node 2 — IF**
- Value 1: `{{ $json.query.approved }}`
- Operation: Equal
- Value 2: `true`

**Node 3 — HTTP Request (Execute)**
- Method: `POST`
- URL: `https://your-cloudflare-url/execute`
- Header: `X-API-Key: fastapi-secret-z9y8x7w6v5u4`
- Body: `{ "query": "{{ $('Webhook').first().json.query.sql }}" }`

**Node 4 — Code (Format Table)**
```javascript
const { columns, rows, row_count } = $input.first().json;
const question = $('Webhook').first().json.query.question;

const headerCells = columns.map(c =>
  `<th style="background:#f0f0f0;padding:8px 12px;border:1px solid #ddd;font-size:13px">${c}</th>`
).join('');

const bodyRows = rows.map((row, i) =>
  `<tr style="background:${i % 2 === 0 ? '#fff' : '#fafafa'}">
    ${columns.map(col =>
      `<td style="padding:7px 12px;border:1px solid #eee;font-size:13px">${row[col] ?? ''}</td>`
    ).join('')}
  </tr>`
).join('');

const html = `<div style="font-family:Arial,sans-serif;max-width:800px;padding:20px">
  <h2 style="font-size:16px;color:#333">Query Results</h2>
  <p style="font-size:13px;color:#888">Question: ${question}</p>
  <table style="border-collapse:collapse;width:100%">
    <thead><tr>${headerCells}</tr></thead>
    <tbody>${bodyRows}</tbody>
  </table>
  <p style="font-size:12px;color:#999;margin-top:10px">${row_count} row${row_count !== 1 ? 's' : ''} returned</p>
</div>`;

return [{ json: { html, row_count, question } }];
```

**Node 5 — Send Email (Results)**
- To: `himangi.shukla@ventrahealth.com`
- Subject: `={{ 'Query Results: ' + $json.question }}`
- HTML: `={{ $json.html }}`

---

## Security Model

```
                    WHAT IS PROTECTED AND HOW
═══════════════════════════════════════════════════════════════════

  Threat                        Protection
  ──────────────────────────    ──────────────────────────────────
  Someone calls n8n webhook     X-API-Key header on Webhook node
  without permission            Unknown keys get 403 response

  Someone calls FastAPI         X-API-Key header checked on every
  /schema or /execute           protected route by FastAPI Security

  Malicious SQL injection       FastAPI blocks INSERT, UPDATE,
  via /execute endpoint         DELETE, DROP, ALTER, TRUNCATE, EXEC

  SQL Server exposed            Never — only FastAPI can reach it,
  to internet                   using Windows Auth on same machine

  Cloudflare URL discovered     Still protected by X-API-Key —
  by someone else               they cannot call any endpoint

  Man-in-the-middle attack      Cloudflare Tunnel is always HTTPS —
                                all traffic encrypted end to end
```

---

## Folder Structure

```
sql-schema-api/
│
├── main.py                 # FastAPI application
│   ├── GET  /health        # Health check
│   ├── GET  /schema        # Returns database schema as JSON
│   ├── POST /execute       # Runs a SELECT query, returns results
│   ├── GET  /approve       # Serves the HTML approval page
│   └── GET  /redirect      # URL relay for Outlook-safe links
│
├── .env                    # SQL Server config + API secret key
│                           # ⚠️ Never commit this to GitHub
│
├── requirements.txt        # Python dependencies
│   ├── fastapi
│   ├── uvicorn
│   ├── pyodbc
│   └── python-dotenv
│
└── README.md               # This file
```

> ⚠️ **Never commit `.env` to GitHub.** Add it to `.gitignore` immediately.
> Your `.gitignore` should include:
> ```
> .env
> venv/
> __pycache__/
> *.pyc
> ```

---

## Quick Reference — All URLs and Keys

| What | Value |
|------|-------|
| n8n Workflow 1 webhook | `https://leukos444.app.n8n.cloud/webhook/sql-query-generator` |
| n8n Workflow 2 webhook | `https://leukos444.app.n8n.cloud/webhook/sql-approve` |
| FastAPI schema endpoint | `https://your-cloudflare-url/schema` |
| FastAPI execute endpoint | `https://your-cloudflare-url/execute` |
| FastAPI approval page | `https://your-cloudflare-url/approve` |
| Approval email recipient | `himangi.shukla@ventrahealth.com` |

---

*Built with FastAPI · Cloudflare Tunnel · n8n · OpenAI GPT-4o mini · Gmail SMTP*
