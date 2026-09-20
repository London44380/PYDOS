# PyDOS — Pentest DoS Testing Framework

Outil de test de charge/déni de service (UDP flood, SYN flood, HTTP flood, Slowloris, ICMP flood) pour évaluer la résistance d'une cible **que vous possédez ou pour laquelle vous avez une autorisation écrite explicite**.

> ⚠️ **Test de pénétration autorisé uniquement. Toute utilisation non autorisée est illégale.** Ne jamais viser une cible sans consentement écrit préalable ; utiliser exclusivement en environnement de lab/CTF ou sur son propre matériel.

## Usage
```
# UDP flood
python3 pydos.py -m udp -t 192.168.1.100 -p 53 -d 60 -T 200

# SYN flood (nécessite root)
sudo python3 pydos.py -m syn -t 192.168.1.100 -p 80 -d 30 -T 50

# HTTP flood
python3 pydos.py -m http -t 192.168.1.100 -p 8080 -d 60 -T 300 --path /api/search

# Slowloris
python3 pydos.py -m slowloris -t 192.168.1.100 -p 80 -d 120 --sockets 200

# ICMP flood (nécessite root)
sudo python3 pydos.py -m icmp -t 192.168.1.100 -d 30 -T 20
```

## Options
| Option | Rôle |
|---|---|
| `-m`, `--method` | `udp` \| `syn` \| `http` \| `slowloris` \| `icmp` |
| `-t`, `--target` | Adresse IP cible |
| `-p`, `--port` | Port cible (défaut 80) |
| `-d`, `--duration` | Durée en secondes (défaut 30) |
| `-T`, `--threads` | Nombre de threads (défaut 100) |
| `--path` | Chemin HTTP (méthode `http`) |
| `--sockets` | Sockets max (méthode `slowloris`) |

Les méthodes `syn` et `icmp` nécessitent des sockets raw (root/sudo).
