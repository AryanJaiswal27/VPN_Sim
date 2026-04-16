"""
VPN Demo v2 — Server (PC2)
─────────────────────────
• TLS-encrypted tunnel between PC1 and PC2  (self-signed cert, auto-generated)
• Fetches full page: HTML + CSS + JS + images  for the Python client
• Still works as a plain HTTP/HTTPS CONNECT proxy for browsers
• Live dashboard at http://PC2_IP:9090
"""

import socket, threading, ssl, json, os, re, base64
import urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# ── Ports ──────────────────────────────────────────────────────────────────────
PROXY_PORT   = 8888   # TLS-wrapped proxy (Python client connects here)
MONITOR_PORT = 9090   # Dashboard

# ── Colours ───────────────────────────────────────────────────────────────────
C  = "\033[96m"; G = "\033[92m"; Y = "\033[93m"
R  = "\033[91m"; B = "\033[94m"; X = "\033[0m"; W = "\033[1m"

# ── Shared log ────────────────────────────────────────────────────────────────
logs, log_lock = [], threading.Lock()

def add_log(e):
    with log_lock:
        logs.append(e)
        if len(logs) > 200: logs.pop(0)

def ts(): return datetime.now().strftime("%H:%M:%S")

# ─────────────────────────────────────────────────────────────────────────────
#  TLS certificate  (auto-generated on first run, saved next to this script)
# ─────────────────────────────────────────────────────────────────────────────
CERT_FILE = os.path.join(os.path.dirname(__file__), "vpn_server.crt")
KEY_FILE  = os.path.join(os.path.dirname(__file__), "vpn_server.key")

def generate_self_signed_cert():
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime as dt
    except ImportError:
        raise RuntimeError(
            "Run: pip install cryptography\n"
            "Then restart vpn_server.py"
        )

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "VPN-Demo-Server"),
    ])

    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + dt.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    with open(KEY_FILE, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    with open(CERT_FILE, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print(f"[{ts()}] Certificate generated: {CERT_FILE}")

def ensure_cert():
    if not (os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE)):
        print(f"{Y}[{ts()}] No certificate found — generating self-signed cert…{X}")
        generate_self_signed_cert()

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────
SKIP_HDR = {"proxy-connection","proxy-authorization","connection",
            "keep-alive","te","trailers","transfer-encoding","upgrade"}

CTX_CLIENT = ssl.create_default_context()
CTX_CLIENT.check_hostname = False
CTX_CLIENT.verify_mode    = ssl.CERT_NONE

def http_get(url, extra_headers=None):
    """Fetch url, return (status, headers_dict, bytes_body)."""
    headers = {"User-Agent": "Mozilla/5.0 (VPN-Demo/2.0)"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=CTX_CLIENT, timeout=15) as r:
        return r.status, dict(r.headers), r.read()

# ─────────────────────────────────────────────────────────────────────────────
#  Full-page bundler  (used by the Python client protocol)
# ─────────────────────────────────────────────────────────────────────────────
def _abs(base, href):
    """Resolve href relative to base URL."""
    return urllib.parse.urljoin(base, href)

def fetch_full_page(url):
    """
    Fetch HTML and inline every linked CSS / JS / image into a single
    self-contained HTML string (data-URIs for binary assets).
    Returns the bundled HTML string.
    """
    print(f"{Y}[{ts()}] Fetching HTML: {url}{X}")
    _, _, html_bytes = http_get(url)
    html = html_bytes.decode("utf-8", errors="replace")

    # ── Inline <link rel="stylesheet"> ───────────────────────────────────────
    def replace_css(m):
        href = m.group(1) or m.group(2)
        abs_url = _abs(url, href)
        try:
            _, _, body = http_get(abs_url)
            css = body.decode("utf-8", errors="replace")
            print(f"{G}  ✓ CSS  {abs_url[:60]}{X}")
            return f"<style>/* {abs_url} */\n{css}\n</style>"
        except Exception as e:
            print(f"{R}  ✗ CSS  {abs_url[:60]}  ({e}){X}")
            return m.group(0)

    html = re.sub(
        r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\'][^>]*>|'
        r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']stylesheet["\'][^>]*>',
        replace_css, html, flags=re.IGNORECASE)

    # ── Inline <script src="…"> ───────────────────────────────────────────────
    def replace_js(m):
        src = m.group(1)
        abs_url = _abs(url, src)
        try:
            _, _, body = http_get(abs_url)
            js = body.decode("utf-8", errors="replace")
            print(f"{G}  ✓ JS   {abs_url[:60]}{X}")
            return f"<script>/* {abs_url} */\n{js}\n</script>"
        except Exception as e:
            print(f"{R}  ✗ JS   {abs_url[:60]}  ({e}){X}")
            return m.group(0)

    html = re.sub(
        r'<script[^>]+src=["\']([^"\']+)["\'][^>]*></script>',
        replace_js, html, flags=re.IGNORECASE)

    # ── Inline <img src="…"> as data URI ─────────────────────────────────────
    def replace_img(m):
        src = m.group(1)
        if src.startswith("data:"): return m.group(0)
        abs_url = _abs(url, src)
        try:
            _, hdrs, body = http_get(abs_url)
            mime = hdrs.get("Content-Type", "image/png").split(";")[0]
            b64  = base64.b64encode(body).decode()
            print(f"{G}  ✓ IMG  {abs_url[:60]}  ({len(body):,}B){X}")
            return f'<img src="data:{mime};base64,{b64}"'
        except Exception as e:
            print(f"{R}  ✗ IMG  {abs_url[:60]}  ({e}){X}")
            return m.group(0)

    html = re.sub(r'<img[^>]+src=["\']([^"\']+)["\']', replace_img,
                  html, flags=re.IGNORECASE)

    return html

# ─────────────────────────────────────────────────────────────────────────────
#  Custom protocol handler  (PC1 ↔ PC2, over TLS)
# ─────────────────────────────────────────────────────────────────────────────
def recv_msg(sock):
    raw_len = b""
    while len(raw_len) < 4:
        chunk = sock.recv(4 - len(raw_len))
        if not chunk: raise ConnectionError("Connection closed")
        raw_len += chunk
    length = int.from_bytes(raw_len, "big")
    data = b""
    while len(data) < length:
        chunk = sock.recv(min(65536, length - len(data)))
        if not chunk: raise ConnectionError("Connection closed")
        data += chunk
    return json.loads(data.decode("utf-8"))

def send_msg(sock, obj):
    data = json.dumps(obj).encode("utf-8")
    sock.sendall(len(data).to_bytes(4, "big") + data)

def handle_client(raw_sock, addr):
    """Handle one Python-client connection (TLS + custom protocol)."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT_FILE, KEY_FILE)
    try:
        tls_sock = ctx.wrap_socket(raw_sock, server_side=True)
    except ssl.SSLError as e:
        print(f"{R}[{ts()}] TLS handshake failed from {addr}: {e}{X}")
        raw_sock.close()
        return

    print(f"{C}[{ts()}] 🔒 TLS connection from {addr[0]}{X}")

    try:
        while True:
            try:
                req = recv_msg(tls_sock)
            except (ConnectionError, json.JSONDecodeError):
                break

            url = req.get("url", "")
            log = {"time": ts(), "client": addr[0], "method": "GET",
                   "url": url, "status": None, "size": 0, "encrypted": True}

            print(f"{B}[{ts()}] {W}PC1→VPN{X}{B}  {url[:70]}{X}")
            print(f"{Y}[{ts()}] {W}VPN→Internet{X}{Y}  bundling full page…{X}")

            try:
                bundled = fetch_full_page(url)
                size    = len(bundled.encode("utf-8"))
                log.update(status="200", size=size)
                add_log(log)

                print(f"{G}[{ts()}] {W}VPN→PC1{X}{G}  sending {size:,} bytes (encrypted){X}\n")
                send_msg(tls_sock, {"ok": True, "html": bundled,
                                    "url": url, "size": size})
            
            # --- THE FIX IS APPLIED HERE ---
            except (ssl.SSLEOFError, ConnectionResetError, BrokenPipeError) as e:
                log.update(status="499") # 499: Client Closed Request
                add_log(log)
                print(f"{R}[{ts()}] Client disconnected before response was sent (Timeout?). ({e}){X}\n")
                break 

            except Exception as e:
                log.update(status="502")
                add_log(log)
                print(f"{R}[{ts()}] Error fetching {url}: {e}{X}\n")
                try:
                    send_msg(tls_sock, {"ok": False, "error": str(e)})
                except Exception:
                    pass

    finally:
        tls_sock.close()

# ─────────────────────────────────────────────────────────────────────────────
#  Plain HTTP/HTTPS CONNECT proxy  (for browsers)
# ─────────────────────────────────────────────────────────────────────────────
class BrowserProxyHandler(BaseHTTPRequestHandler):
    def do_CONNECT(self):
        log = {"time":ts(),"client":self.client_address[0],
               "method":"CONNECT","url":self.path,"status":None,"size":0,"encrypted":False}
        try:
            host, port = self.path.split(":", 1)
            remote = socket.create_connection((host, int(port)), timeout=10)
            self.send_response(200, "Connection Established")
            self.send_header("Proxy-Agent", "VPN-Demo-v2")
            self.end_headers()
            log["status"] = "200 TUNNEL"
            add_log(log)
            print(f"{G}[{ts()}] BROWSER TUNNEL  {self.client_address[0]} <-> {self.path}{X}")
            self._tunnel(self.connection, remote)
        except Exception as e:
            log["status"] = "502"; add_log(log)
            self.send_error(502, str(e))

    def _tunnel(self, a, b):
        def pipe(s, d):
            try:
                while True:
                    data = s.recv(8192)
                    if not data: break
                    d.sendall(data)
            except: pass
            finally:
                for x in (s,d):
                    try: x.close()
                    except: pass
        t1 = threading.Thread(target=pipe, args=(a,b), daemon=True)
        t2 = threading.Thread(target=pipe, args=(b,a), daemon=True)
        t1.start(); t2.start(); t1.join(); t2.join()

    def do_GET(self): self._fwd()
    def do_POST(self): self._fwd()
    def do_HEAD(self): self._fwd()

    def _fwd(self):
        url = self.path
        if not url.startswith("http"): url = "http://" + url
        log = {"time":ts(),"client":self.client_address[0],
               "method":self.command,"url":url,"status":None,"size":0,"encrypted":False}
        try:
            body_len = int(self.headers.get("Content-Length",0))
            body = self.rfile.read(body_len) if body_len else None
            hdrs = {k:v for k,v in self.headers.items() if k.lower() not in SKIP_HDR}
            hdrs["User-Agent"] = "Mozilla/5.0 (VPN-Demo-v2)"
            req = urllib.request.Request(url, data=body, headers=hdrs, method=self.command)
            with urllib.request.urlopen(req, context=CTX_CLIENT, timeout=15) as r:
                content = r.read()
                status  = r.status
                rhdrs   = r.headers
            log.update(status=str(status), size=len(content)); add_log(log)
            self.send_response(status)
            for k,v in rhdrs.items():
                if k.lower() not in {"transfer-encoding","connection","keep-alive"}:
                    self.send_header(k,v)
            self.send_header("X-VPN-Proxy","PC2-v2")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            log["status"]="502"; add_log(log)
            self.send_error(502, str(e))

    def log_message(self, *_): pass

class ThreadedBrowserProxy(ThreadingMixIn, HTTPServer):
    daemon_threads = True

# ─────────────────────────────────────────────────────────────────────────────
#  Dashboard
# ─────────────────────────────────────────────────────────────────────────────
DASH_HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VPN Demo v2 — Dashboard</title>
<style>
:root{--bg:#0d1117;--s:#161b22;--s2:#21262d;--b:#30363d;
  --t:#e6edf3;--m:#8b949e;--g:#3fb950;--bl:#58a6ff;
  --y:#d29922;--r:#f85149;--p:#a371f7;--font:'Segoe UI',system-ui,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--t);font-family:var(--font);min-height:100vh}
header{background:var(--s);border-bottom:1px solid var(--b);padding:14px 24px;
  display:flex;align-items:center;gap:12px}
h1{font-size:1rem;font-weight:600}
.sub{color:var(--m);font-size:.8rem}
.live{display:inline-flex;align-items:center;gap:6px;margin-left:auto;
  color:var(--m);font-size:.78rem}
.dot{width:7px;height:7px;border-radius:50%;background:var(--g);
  animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
main{max-width:1120px;margin:0 auto;padding:20px 16px}
.flow{display:flex;align-items:stretch;background:var(--s);
  border:1px solid var(--b);border-radius:10px;overflow:hidden;margin-bottom:20px}
.node{flex:1;text-align:center;padding:16px 8px}
.node.vpn{background:color-mix(in oklch,#58a6ff 8%,var(--s))}
.node-icon{font-size:1.8rem;margin-bottom:4px}
.node-lbl{font-size:.78rem;font-weight:600}
.node-sub{font-size:.68rem;color:var(--m);margin-top:2px}
.arr{display:flex;align-items:center;color:var(--bl);font-size:1.3rem;padding:0 2px;flex-shrink:0}
.lock{font-size:.65rem;color:var(--g);display:block;margin-top:2px}
.stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;margin-bottom:20px}
.stat{background:var(--s);border:1px solid var(--b);border-radius:8px;padding:14px 16px}
.sn{font-size:1.6rem;font-weight:700}.sl{font-size:.75rem;color:var(--m);margin-top:2px}
.g{color:var(--g)}.bl{color:var(--bl)}.r{color:var(--r)}.y{color:var(--y)}.p{color:var(--p)}
.sec{font-size:.78rem;font-weight:600;color:var(--m);margin-bottom:8px;
  text-transform:uppercase;letter-spacing:.07em}
table{width:100%;border-collapse:collapse;background:var(--s);
  border:1px solid var(--b);border-radius:8px;overflow:hidden;font-size:.8rem}
th{background:var(--s2);color:var(--m);padding:9px 12px;text-align:left;
  font-weight:600;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em}
td{padding:8px 12px;border-top:1px solid var(--b);max-width:300px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
tr:hover td{background:var(--s2)}
.badge{font-size:.68rem;font-weight:700;padding:1px 6px;border-radius:4px}
.GET{background:#1c3245;color:var(--bl)}.POST{background:#1c3020;color:var(--g)}
.CONNECT{background:#2d1f47;color:var(--p)}
.ok{color:var(--g)}.er{color:var(--r)}.tu{color:var(--p)}
.enc{font-size:.68rem;color:var(--g)}.plain{font-size:.68rem;color:var(--y)}
.empty{text-align:center;padding:36px;color:var(--m);font-size:.85rem}
</style></head><body>
<header>
  <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
    <rect width="32" height="32" rx="7" fill="#1c3245"/>
    <path d="M16 6L25 11V21L16 26L7 21V11Z" stroke="#58a6ff" stroke-width="1.4" fill="none"/>
    <circle cx="16" cy="16" r="3.5" fill="#58a6ff"/>
    <path d="M16 6v5M16 21v5M25 11l-4 2.5M7 11l4 2.5M25 21l-4-2.5M7 21l4-2.5"
      stroke="#58a6ff" stroke-width="1.3"/>
  </svg>
  <div><h1>VPN Demo v2 — PC2 Dashboard</h1>
    <div class="sub">TLS-encrypted proxy · full-page bundler</div></div>
  <div class="live"><span class="dot"></span> auto-refresh 2 s</div>
</header>
<main>
  <div class="flow">
    <div class="node"><div class="node-icon">💻</div>
      <div class="node-lbl">PC1</div><div class="node-sub">Client</div></div>
    <div class="arr">→<span class="lock">🔒 TLS</span></div>
    <div class="node vpn"><div class="node-icon">🛡️</div>
      <div class="node-lbl">VPN Server (PC2)</div><div class="node-sub">port 8888</div></div>
    <div class="arr">→</div>
    <div class="node"><div class="node-icon">🌐</div>
      <div class="node-lbl">Internet</div><div class="node-sub">real site</div></div>
    <div class="arr">←</div>
    <div class="node vpn"><div class="node-icon">📦</div>
      <div class="node-lbl">Bundle HTML+CSS+JS</div><div class="node-sub">inline assets</div></div>
    <div class="arr">←<span class="lock">🔒 TLS</span></div>
    <div class="node"><div class="node-icon">💻</div>
      <div class="node-lbl">PC1</div><div class="node-sub">full page saved</div></div>
  </div>
  <div class="stats">
    <div class="stat g"><div class="sn" id="st">0</div><div class="sl">Total</div></div>
    <div class="stat bl"><div class="sn" id="sk">0</div><div class="sl">Success</div></div>
    <div class="stat r"><div class="sn" id="se">0</div><div class="sl">Errors</div></div>
    <div class="stat p"><div class="sn" id="sc">0</div><div class="sl">Encrypted (TLS)</div></div>
    <div class="stat y"><div class="sn" id="sb">0</div><div class="sl">KB Transferred</div></div>
  </div>
  <div class="sec">Request Log (last 50)</div>
  <table><thead><tr>
    <th>Time</th><th>Client</th><th>Method</th><th>URL</th>
    <th>Status</th><th>Size</th><th>Channel</th>
  </tr></thead>
  <tbody id="tb"><tr><td colspan="7" class="empty">Waiting for traffic…</td></tr></tbody>
  </table>
</main>
<script>
function fmt(n){return n>=1024?(n/1024).toFixed(1)+' KB':n+' B'}
function sc(s){if(!s)return '';if(s.includes('TUNNEL'))return 'tu';
  const c=parseInt(s);return(c>=200&&c<300)?'ok':'er'}
function refresh(){
  fetch('/api/logs').then(r=>r.json()).then(logs=>{
    const tb=document.getElementById('tb');
    if(!logs.length){tb.innerHTML='<tr><td colspan="7" class="empty">Waiting…</td></tr>';return;}
    let t=0,k=0,e=0,enc=0,kb=0;
    tb.innerHTML=logs.map(l=>{
      t++;const s=l.status||'';const c=parseInt(s);
      if(s.includes('200')||s.includes('TUNNEL')||(c>=200&&c<300))k++;else e++;
      if(l.encrypted)enc++;
      kb+=l.size||0;
      return`<tr>
        <td style="color:var(--m)">${l.time}</td>
        <td>${l.client}</td>
        <td><span class="badge ${l.method}">${l.method}</span></td>
        <td title="${l.url}">${l.url.length>50?l.url.slice(0,50)+'…':l.url}</td>
        <td class="${sc(s)}">${s||'—'}</td>
        <td>${l.size?fmt(l.size):'—'}</td>
        <td>${l.encrypted?'<span class="enc">🔒 TLS</span>':'<span class="plain">⚠ plain</span>'}</td>
      </tr>`;
    }).join('');
    document.getElementById('st').textContent=t;
    document.getElementById('sk').textContent=k;
    document.getElementById('se').textContent=e;
    document.getElementById('sc').textContent=enc;
    document.getElementById('sb').textContent=(kb/1024).toFixed(1)+' KB';
  }).catch(()=>{});
}
refresh();setInterval(refresh,2000);
</script></body></html>"""

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/logs"):
            with log_lock:
                data = json.dumps(list(reversed(logs[-50:]))).encode()
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.send_header("Access-Control-Allow-Origin","*")
            self.end_headers(); self.wfile.write(data)
        else:
            body = DASH_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type","text/html")
            self.send_header("Content-Length",len(body))
            self.end_headers(); self.wfile.write(body)
    def log_message(self,*_): pass

class ThreadedDash(ThreadingMixIn, HTTPServer):
    daemon_threads = True

# ─────────────────────────────────────────────────────────────────────────────
#  Raw TCP listener for Python client (TLS upgrade inside handle_client)
# ─────────────────────────────────────────────────────────────────────────────
def run_tls_proxy(port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(50)
    print(f"{G}[{ts()}] TLS proxy listening on :{port}{X}")
    while True:
        try:
            conn, addr = srv.accept()
            threading.Thread(target=handle_client, args=(conn,addr), daemon=True).start()
        except Exception as e:
            print(f"{R}[{ts()}] Accept error: {e}{X}")

# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ensure_cert()

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); local_ip = s.getsockname()[0]; s.close()
    except: local_ip = "127.0.0.1"

    print(f"""
{C}{W}╔══════════════════════════════════════════════════╗
║      VPN Demo v2 — PC2 Server  (TLS + Bundle)    ║
╠══════════════════════════════════════════════════╣
║  TLS Proxy  :  {local_ip}:{PROXY_PORT}               
║  Dashboard  :  http://{local_ip}:{MONITOR_PORT}          
╠══════════════════════════════════════════════════╣
║  On PC1:                                         ║
║    python vpn_client.py --vpn {local_ip}         
║                                                  ║
║  Copy cert to PC1:                               ║
║    vpn_server.crt  →  same folder as client      ║
╚══════════════════════════════════════════════════╝{X}
""")

    # Start dashboard
    dash = ThreadedDash(("0.0.0.0", MONITOR_PORT), DashboardHandler)
    threading.Thread(target=dash.serve_forever, daemon=True).start()

    # Start TLS proxy  (blocks)
    try:
        run_tls_proxy(PROXY_PORT)
    except KeyboardInterrupt:
        print(f"\n{R}Shutting down.{X}")


