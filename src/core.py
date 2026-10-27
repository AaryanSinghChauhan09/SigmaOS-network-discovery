"""LAN discovery engine for SigmaOS-network-discovery.

Principles: parse simulated scan output into a typed host/port model (pure),
plan scans before any packet hits the wire (plan-before-act), fail-fast on
malformed addresses, deterministic ordering everywhere, export is the only
side effect and only writes where the user points it.
"""
import argparse, csv, ipaddress, json, os, re, sys

ENGINE = {
    "name": "sigma-netdiscovery",
    "summary": "Discover hosts and services on a LAN from scan data",
    "language": "python",
    "verbs": ["scan-plan", "hosts", "services", "export"],
    "principles": ["Plan Before Act", "Separation of Concerns",
                   "Defensive Programming", "Fail-Fast", "Determinism", "KISS"],
}

cli_doc = """\
$ sigma-netdiscovery scan-plan 192.168.1.0/24 --ports top-100 --timing 4
network 192.168.1.0/24: 256 address(es)
  nmap -sn 192.168.1.0/24
$ sigma-netdiscovery hosts scan.txt --status up
192.168.1.1   router.lan   up   2 ports
$ sigma-netdiscovery services scan.txt
ssh  192.168.1.1:22/tcp  192.168.1.20:22/tcp
$ sigma-netdiscovery export scan.txt hosts.json --format json
"""

_PORT_RE = re.compile(r"^(\d{1,5})/(tcp|udp)\s+(open|closed|filtered)\s+(\S+)$")
_HOST_RE = re.compile(r"^(\S+)\s+(\S+)\s+(up|down)$")
_PORTSPEC_RE = re.compile(r"^[0-9,\-]+$")


class NetError(ValueError):
    pass


def _read(path):
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def parse_scan(text):
    """Parse simulated nmap-style output into ordered host records."""
    hosts, cur = [], None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        pm = _PORT_RE.match(line)
        if pm:
            if cur is None:
                raise NetError(f"line {lineno}: port line before any host")
            port = int(pm.group(1))
            if not 1 <= port <= 65535:
                raise NetError(f"line {lineno}: port out of range: {port}")
            cur["ports"].append({"port": port, "proto": pm.group(2),
                                 "state": pm.group(3), "service": pm.group(4)})
            continue
        hm = _HOST_RE.match(line)
        if not hm:
            raise NetError(f"line {lineno}: cannot parse line {line!r}")
        try:
            addr = str(ipaddress.ip_address(hm.group(1)))
        except ValueError as e:
            raise NetError(f"line {lineno}: bad address {hm.group(1)!r}") from e
        if any(h["addr"] == addr for h in hosts):
            raise NetError(f"line {lineno}: duplicate host {addr}")
        cur = {"addr": addr, "name": hm.group(2), "status": hm.group(3),
               "ports": []}
        hosts.append(cur)
    if not hosts:
        raise NetError("scan contained no hosts")
    return hosts


def _ipkey(addr):
    return ipaddress.ip_address(addr)


def hosts(scanned, status=None):
    """Filter parsed hosts by status; always sorted by numeric IP."""
    if status not in (None, "up", "down"):
        raise NetError(f"bad status filter: {status!r}")
    out = [h for h in scanned if status is None or h["status"] == status]
    return sorted(out, key=lambda h: _ipkey(h["addr"]))


def services(scanned):
    """Map open service names to sorted 'addr:port/proto' endpoints."""
    table = {}
    for h in scanned:
        for p in h["ports"]:
            if p["state"] != "open":
                continue
            table.setdefault(p["service"], []).append(
                f"{h['addr']}:{p['port']}/{p['proto']}")
    return {s: sorted(ep) for s, ep in sorted(table.items())}


def scan_plan(cidr, ports="top-1000", timing=4):
    """Pure scan plan -- refuses huge ranges, never runs a single packet."""
    try:
        net = ipaddress.ip_network(cidr, strict=False)
    except ValueError as e:
        raise NetError(f"bad CIDR {cidr!r}: {e}") from e
    if net.num_addresses > 4096:
        raise NetError(
            f"refusing to scan {net} ({net.num_addresses} addresses > 4096)")
    if not 1 <= timing <= 5:
        raise NetError(f"timing must be 1..5, got {timing}")
    if ports not in ("top-100", "top-1000", "all") and \
            not _PORTSPEC_RE.match(ports):
        raise NetError(f"bad port spec: {ports!r}")
    return {
        "cidr": str(net),
        "addresses": net.num_addresses,
        "steps": [f"nmap -sn {net}",
                  f"nmap -p {ports} -T{timing} --open <discovered hosts>",
                  "merge results into scan.txt"],
    }


def export(scanned, path, fmt="json"):
    """Write parsed scan data to path as json or csv. Returns the path."""
    if fmt not in ("json", "csv"):
        raise NetError(f"bad format: {fmt!r}")
    rows = hosts(scanned)
    if fmt == "json":
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2, sort_keys=True)
    else:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["addr", "name", "status", "port", "proto",
                        "state", "service"])
            for h in rows:
                if not h["ports"]:
                    w.writerow([h["addr"], h["name"], h["status"],
                                "", "", "", ""])
                for p in h["ports"]:
                    w.writerow([h["addr"], h["name"], h["status"], p["port"],
                                p["proto"], p["state"], p["service"]])
    return path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=ENGINE["name"],
                                description=ENGINE["summary"])
    sub = p.add_subparsers(dest="cmd", required=True)
    sc = sub.add_parser("scan-plan", help="plan a LAN scan (dry run)")
    sc.add_argument("cidr")
    sc.add_argument("--ports", default="top-1000")
    sc.add_argument("--timing", type=int, default=4)
    ho = sub.add_parser("hosts", help="list hosts from scan data")
    ho.add_argument("scan")
    ho.add_argument("--status", choices=["up", "down"], default=None)
    sv = sub.add_parser("services", help="aggregate open services")
    sv.add_argument("scan")
    ex = sub.add_parser("export", help="export parsed scan data")
    ex.add_argument("scan")
    ex.add_argument("out")
    ex.add_argument("--format", choices=["json", "csv"], default="json")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "scan-plan":
            plan = scan_plan(args.cidr, ports=args.ports, timing=args.timing)
            print(f"network {plan['cidr']}: {plan['addresses']} address(es)")
            for step in plan["steps"]:
                print(f"  {step}")
            return 0
        scanned = parse_scan(_read(args.scan))
        if args.cmd == "hosts":
            for h in hosts(scanned, status=args.status):
                print(f"{h['addr']:<15} {h['name']:<20} {h['status']:<5} "
                      f"{len(h['ports'])} port(s)")
        elif args.cmd == "services":
            for svc, eps in services(scanned).items():
                print(f"{svc:<16} {'  '.join(eps)}")
        elif args.cmd == "export":
            out = export(scanned, args.out, fmt=args.format)
            print(f"exported {len(scanned)} host(s) to {out}")
        return 0
    except NetError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def self_test() -> None:
    sample = """\
# simulated LAN scan
192.168.1.1 router.lan up
  22/tcp open ssh
  80/tcp open http
192.168.1.20 nas.lan up
  22/tcp open ssh
  445/tcp open smb
192.168.1.50 guest.lan down
  22/tcp closed ssh
"""
    scanned = parse_scan(sample)
    assert [h["addr"] for h in scanned] == \
        ["192.168.1.1", "192.168.1.20", "192.168.1.50"]
    assert scanned[0]["ports"][0] == {"port": 22, "proto": "tcp",
                                      "state": "open", "service": "ssh"}
    assert scanned[2]["status"] == "down"

    up = hosts(scanned, status="up")
    assert [h["addr"] for h in up] == ["192.168.1.1", "192.168.1.20"]
    # numeric (not lexicographic) ordering
    parsed = parse_scan("10.0.0.2 a up\n10.0.0.10 b up\n")
    assert [h["addr"] for h in hosts(parsed)] == ["10.0.0.2", "10.0.0.10"]

    svc = services(scanned)
    assert svc["ssh"] == ["192.168.1.1:22/tcp", "192.168.1.20:22/tcp"]
    assert svc["smb"] == ["192.168.1.20:445/tcp"]
    assert "ssh" not in services(parse_scan("192.168.1.50 g down\n"
                                            "  22/tcp closed ssh\n"))

    plan = scan_plan("192.168.1.0/24", ports="top-100", timing=3)
    assert plan["addresses"] == 256
    assert plan["steps"][1].startswith("nmap -p top-100 -T3")
    for bad in (lambda: scan_plan("10.0.0.0/8"),
                lambda: scan_plan("192.168.1.0/24", timing=9),
                lambda: scan_plan("192.168.1.0/24", ports="abc;rm -rf"),
                lambda: scan_plan("not-a-cidr"),
                lambda: parse_scan("999.1.1.1 host up"),
                lambda: parse_scan("  22/tcp open ssh\n192.168.1.1 a up"),
                lambda: parse_scan("no idea what this is"),
                lambda: parse_scan("# nothing\n"),
                lambda: hosts(scanned, status="maybe")):
        try:
            bad()
        except NetError:
            pass
        else:
            raise AssertionError("expected NetError")

    import tempfile
    with tempfile.TemporaryDirectory() as d:
        jp = export(scanned, os.path.join(d, "hosts.json"), fmt="json")
        data = json.load(open(jp, encoding="utf-8"))
        assert len(data) == 3 and data[0]["addr"] == "192.168.1.1"
        cp = export(scanned, os.path.join(d, "hosts.csv"), fmt="csv")
        rows = list(csv.reader(open(cp, encoding="utf-8")))
        assert rows[0][0] == "addr" and len(rows) == 1 + 5  # hdr + 5 ports
        try:
            export(scanned, os.path.join(d, "x"), fmt="xml")
        except NetError:
            pass
        else:
            raise AssertionError("bad export format accepted")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
