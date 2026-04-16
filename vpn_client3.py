import socket, ssl, json, argparse, os, sys

def send_msg(sock, obj):
    """Serialize and send length-prefixed JSON."""
    data = json.dumps(obj).encode("utf-8")
    sock.sendall(len(data).to_bytes(4, "big") + data)

def recv_msg(sock):
    """Receive length-prefixed JSON."""
    raw_len = b""
    while len(raw_len) < 4:
        chunk = sock.recv(4 - len(raw_len))
        if not chunk: raise ConnectionError("Connection closed by server")
        raw_len += chunk
    
    length = int.from_bytes(raw_len, "big")
    data = b""
    while len(data) < length:
        chunk = sock.recv(min(65536, length - len(data)))
        if not chunk: raise ConnectionError("Connection closed by server")
        data += chunk
        
    return json.loads(data.decode("utf-8"))

def main():
    parser = argparse.ArgumentParser(description="VPN Demo v2 - Client (PC1)")
    parser.add_argument("--vpn", required=True, help="IP address of the VPN Server (PC2)")
    parser.add_argument("--url", default="https://example.com", help="The URL you want to securely fetch")
    args = parser.parse_args()

    cert_path = "vpn_server.crt"
    if not os.path.exists(cert_path):
        print(f"\n[!] ERROR: '{cert_path}' is missing.")
        print(f"    You need to copy it from the server (PC2) into this directory.\n")
        sys.exit(1)

    # 1. Setup TLS Context (trust our self-signed cert)
    ctx = ssl.create_default_context()
    ctx.load_verify_locations(cert_path)
    ctx.check_hostname = False

    try:
        # 2. Connect to server
        # THE FIX: 150-second timeout ensures we don't drop the connection
        # while the server is downloading dozens of CSS/JS/IMG files.
        print(f"[*] Connecting to {args.vpn}:8888...")
        raw_sock = socket.create_connection((args.vpn, 8888), timeout=150.0)
        
        # 3. Upgrade to TLS
        print("[*] Securing tunnel with TLS...")
        tls_sock = ctx.wrap_socket(raw_sock, server_hostname="VPN-Demo-Server")
        
        # 4. Request the URL
        print(f"[*] Requesting bundled version of: {args.url}")
        print("[*] Waiting for server to fetch and bundle assets (this may take a minute)...")
        send_msg(tls_sock, {"url": args.url})
        
        # 5. Wait for the heavy payload
        resp = recv_msg(tls_sock)
        
        # 6. Process response
        if resp.get("ok"):
            html = resp.get("html", "")
            size_kb = resp.get("size", len(html.encode('utf-8'))) / 1024
            print(f"\n[+] SUCCESS! Received {size_kb:,.1f} KB of bundled data.")
            
            out_file = "bundled_page.html"
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"[+] Saved fully contained offline page to '{out_file}'")
        else:
            print(f"\n[-] SERVER ERROR: {resp.get('error')}")

    except TimeoutError:
        print("\n[-] ERROR: The request timed out (took longer than 150 seconds).")
    except Exception as e:
        print(f"\n[-] CONNECTION ERROR: {e}")
    finally:
        try: tls_sock.close() 
        except: pass

if __name__ == "__main__":
    main()

