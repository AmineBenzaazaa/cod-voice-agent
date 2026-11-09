"""Live view of orders and call events while the agent talks.

    uv run dashboard.py      # http://localhost:7870
"""

import html
import json
import os

import psycopg
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

load_dotenv()
DSN = os.environ["DATABASE_URL"]
app = FastAPI()


@app.get("/api/state")
def state():
    with psycopg.connect(DSN) as conn:
        orders = conn.execute(
            "SELECT id, customer_name, city, address, total_mad, status, delivery_date, attempts "
            "FROM orders ORDER BY id"
        ).fetchall()
        events = conn.execute(
            "SELECT to_char(created_at, 'HH24:MI:SS'), order_id, action, detail "
            "FROM call_events ORDER BY id DESC LIMIT 15"
        ).fetchall()
    return JSONResponse({
        "orders": [
            dict(zip(["id", "customer", "city", "address", "total", "status", "delivery", "attempts"],
                     [str(v) if v is not None else "" for v in o]))
            for o in orders
        ],
        "events": [{"time": t, "order": o, "action": a, "detail": json.dumps(d)} for t, o, a, d in events],
    })


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>COD confirmations</title>
<style>
 body{font-family:-apple-system,Segoe UI,sans-serif;margin:24px;background:#0f1115;color:#e8e8e8}
 h1{font-size:20px} h2{font-size:15px;color:#9aa0aa;margin-top:28px}
 table{border-collapse:collapse;width:100%;font-size:14px}
 td,th{padding:8px 10px;border-bottom:1px solid #262a33;text-align:left;vertical-align:top}
 th{color:#9aa0aa;font-weight:600}
 .s{padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600}
 .pending{background:#3a3320;color:#f5c451}.confirmed{background:#173a26;color:#5ad08a}
 .rescheduled{background:#1d2c45;color:#7fb0ff}.cancelled{background:#43201f;color:#ff7b72}
 .no_answer{background:#2b2b2b;color:#aaa} code{color:#9aa0aa;font-size:12px}
 tr.flash{animation:f 1.5s} @keyframes f{from{background:#2f3b55}to{background:transparent}}
</style></head><body>
<h1>COD order confirmations (live)</h1>
<table id="o"><thead><tr><th>Order</th><th>Customer</th><th>City</th><th>Address</th><th>Total</th>
<th>Status</th><th>Delivery</th><th>Calls</th></tr></thead><tbody></tbody></table>
<h2>Agent actions</h2>
<table id="e"><thead><tr><th>Time</th><th>Order</th><th>Action</th><th>Detail</th></tr></thead><tbody></tbody></table>
<script>
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let prev={};
async function tick(){
 const d=await (await fetch('/api/state')).json();
 document.querySelector('#o tbody').innerHTML=d.orders.map(o=>{
  const key=JSON.stringify(o), changed=prev[o.id]&&prev[o.id]!==key; prev[o.id]=key;
  return `<tr class="${changed?'flash':''}"><td>${esc(o.id)}</td><td>${esc(o.customer)}</td><td>${esc(o.city)}</td>
  <td>${esc(o.address)}</td><td>${esc(o.total)} MAD</td><td><span class="s ${esc(o.status)}">${esc(o.status)}</span></td>
  <td>${esc(o.delivery)}</td><td>${esc(o.attempts)}</td></tr>`}).join('');
 document.querySelector('#e tbody').innerHTML=d.events.map(e=>
  `<tr><td>${esc(e.time)}</td><td>${esc(e.order)}</td><td>${esc(e.action)}</td><td><code>${esc(e.detail)}</code></td></tr>`).join('');
}
tick(); setInterval(tick,1500);
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("DASHBOARD_PORT", "7870")))
