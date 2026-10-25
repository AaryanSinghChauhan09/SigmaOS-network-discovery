    # SigmaOS-network-discovery

    Discover hosts & services on the LAN

    Part of the **SigmaOS** sovereign operating-system ecosystem — a multi-repository
    distribution modelled on Linux Mint and Omarchy Linux. See the parent
    [`SigmaOS`](https://github.com/AaryanSinghChauhan09/SigmaOS) repository for the
    full component index.

    ## Upstream inspirations
    - https://github.com/linuxmint/network-discovery

    ## Design principles applied
    - **Plan Before Act**
- **Separation of Concerns**
- **Defensive Programming**
- **Fail-Fast**
- **Determinism**
- **KISS**

    ## Usage
    Verbs: `scan-plan, hosts, services, export`

    ```
    $ sigma-netdiscovery scan-plan 192.168.1.0/24 --ports top-100 --timing 4
network 192.168.1.0/24: 256 address(es)
  nmap -sn 192.168.1.0/24
$ sigma-netdiscovery hosts scan.txt --status up
192.168.1.1   router.lan   up   2 ports
$ sigma-netdiscovery services scan.txt
ssh  192.168.1.1:22/tcp  192.168.1.20:22/tcp
$ sigma-netdiscovery export scan.txt hosts.json --format json

    ```

    ## Build & test
    ```
    make build
    make test
    ```

    ## Licence
    GNU General Public License v3.0 (FOSS).
