# Firewalls, and Doctor Raven's planned role with them

This doc explains what a firewall actually is, and what Doctor Raven will (and won't) do once
firewall management is added. **Status: design doc — not yet implemented.** See the `raven fw`
plan discussed in-repo before this lands as code.

## 1. What a firewall actually is

Every network connection to or from your PC is made of packets — small chunks of data tagged
with things like: source IP, destination IP, source port, destination port, and protocol
(TCP or UDP). A firewall is a rule engine sitting in front of your network stack that looks at
each packet and decides: **let it through, or drop it.**

That's it. It doesn't scan for viruses, it doesn't read file contents, it doesn't know anything
about "malware." It only ever answers one question, per packet: *does this connection match a
rule that allows it?*

### Inbound vs outbound

- **Inbound** — traffic trying to reach *your* machine from outside (someone connecting to a
  service you're running). This is the traffic a firewall protects you from most: an attacker
  scanning the internet for open ports, a compromised device on your LAN probing your machine,
  a service you forgot was running and exposed.
- **Outbound** — traffic *leaving* your machine. Less commonly restricted on a personal machine,
  but relevant if you ever want to notice/block something on your PC trying to phone home.

### Ports, in one sentence

A port is just a number (1–65535) that identifies *which service* on a machine a connection is
for — port 22 is SSH, port 443 is HTTPS, port 8080 is a common dev-server port, etc. "Opening a
port" means telling the firewall to let inbound connections to that number through.

### The Linux plumbing (what's actually running)

- **netfilter** — the actual packet-filtering engine, built into the Linux kernel. You never
  touch this directly.
- **iptables / nftables** — the traditional command-line tools for writing netfilter rules
  directly. Extremely powerful, also extremely easy to get wrong (one bad rule and you've
  locked yourself out of your own machine, or opened everything).
- **UFW (Uncomplicated Firewall)** — a friendly wrapper around iptables/nftables, standard on
  Debian-based systems including Parrot OS. Instead of raw iptables syntax, you write
  `ufw allow 22/tcp`. This is what Doctor Raven will build on — never raw iptables/nftables.

Doctor Raven already does one thing with UFW today, and it's read-only: `raven sec posture`
shells out to `ufw status` and reports back "active" or "inactive." It changes nothing.

## 2. What Doctor Raven will actually do (planned)

A new `raven fw` command group, built entirely on top of UFW:

| Command | What it does | Mutates anything? |
|---|---|---|
| `raven fw status` | Lists current rules, numbered, in plain English | No — read-only |
| `raven fw allow <port> [--from <ip>]` | Opens a port (optionally scoped to one source IP) | Yes — after confirmation |
| `raven fw deny <port> [--from <ip>]` | Blocks a port | Yes — after confirmation |
| `raven fw delete <rule-number>` | Removes a specific rule shown by `fw status` | Yes — after confirmation |
| `raven fw enable` / `disable` | Turns the whole firewall on/off | Yes — after extra confirmation |

Every mutating command follows the same two-step shape already used elsewhere in Doctor Raven
(`raven maintain --apply`, `raven doctor`):

1. **Preview** — print the exact command it's about to run and what it means in plain language.
   Example:
   ```
   This will run: sudo ufw allow 8080/tcp
   Effect: any device that can reach this machine will be able to connect to port 8080.
   Proceed? [y/N]
   ```
2. **Execute only on explicit yes.** Nothing runs on a default/empty answer.

Nothing here ever runs automatically. The background daemon (`raven daemon`) will keep doing
its existing read-only posture check on its normal schedule, but it will **never** call
`allow`/`deny`/`delete`/`enable`/`disable` on its own. Firewall rule changes are a human-only,
one-command-at-a-time action — same principle as the daemon's git auto-commit sweep, which
commits automatically but is hard-coded to never push.

### The one guardrail that matters most: SSH self-lockout

The realistic way this feature hurts someone: you run `raven fw enable`, UFW's default is to
deny inbound-by-default, SSH (port 22) was never explicitly allowed, and your remote session
drops — permanently, until someone has physical access to the machine.

So before `fw enable`, and before any `fw deny` targeting port 22/tcp, Doctor Raven checks
whether SSH is currently allowed. If it isn't, a plain `y` isn't enough — it shows a loud
warning and requires typing the port number back to proceed, so a half-asleep confirm can't
strand you.

## 3. How this actually protects your PC

Concretely, once in place:

- **Blocks unsolicited inbound connections by default.** If you spin up a dev server, a
  database, or any service that binds to a port, it's reachable from the network the moment it
  starts — unless a firewall says otherwise. `raven fw status` lets you see, in one glance,
  everything currently reachable from outside; `raven fw deny` closes anything you didn't mean
  to expose.
- **Shrinks the attack surface.** Every open port is one more thing an attacker (or automated
  internet-wide scanner) can find and try to exploit. Fewer open ports = fewer things that can
  go wrong.
- **Makes "what's exposed on this machine" a one-command answer** instead of something you have
  to remember `ufw status` (or worse, raw `iptables -L`) syntax to check under pressure.
- **Does not** protect against malware already running on your machine communicating out over
  an already-allowed port (e.g. HTTPS on 443), phishing, or anything that doesn't involve a
  network packet. A firewall is one layer, not the whole picture — it pairs with, not replaces,
  the existing `rkhunter`/`lynis`/`clamscan` scans in `raven maintain`.

## 4. What this deliberately does NOT do

- No raw iptables/nftables — UFW only, to keep the rule syntax simple and hard to misconfigure.
- No automatic rule changes by the daemon, ever.
- No silent `sudo` — every privileged call is a rule the user explicitly confirmed, matching
  how `raven maintain --apply` and `raven doctor` already handle `sudo apt-get`.
- No claim of virus/malware detection — a firewall filters connections, nothing more.
