# SigmaOS Network Discovery

Python tools for planning a bounded LAN scan and parsing nmap-style output into
host and service records. Parsed data can be filtered and exported to JSON or
CSV.

## Scan behavior and safety

`scan-plan` is a dry-run planner: it prints proposed `nmap` commands and sends
no packets. It refuses networks larger than 4,096 addresses, validates the
port specification, and bounds nmap timing. The `hosts`, `services`, and
`export` commands operate on a scan-results file supplied by the caller; no
scanner execution command is implemented here.

Network discovery can expose devices and services. Run any separately copied
scan command only on networks where you have authorization, and review its
target and port scope first.

## Development

`make test` exercises parsing, planning, and export behavior using local sample
data. This does not verify live network discovery.
