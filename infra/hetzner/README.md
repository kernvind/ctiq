# Hetzner VM Deployment (tier 0)

The simplest production deployment for ctiq: **one x86 Hetzner VM, Docker Compose, four
containers** (`api-core`, `inference-service`, `web-dashboard`, and `caddy` for TLS), all
talking to the existing external Supabase Postgres. No Kubernetes, no Terraform.

Deploy files live at the **repo root** (siblings to the per-service dev compose files, which stay
local-only):

| File | Purpose |
|---|---|
| `docker-compose.hetzner.yml` | The production stack. api-core/inference publish no host ports; only Caddy is public. |
| `Caddyfile` | Reverse proxy + automatic Let's Encrypt TLS. Set your real domain. |
| `.env.production.example` | Secrets template. Copy to `.env.production` on the VM (gitignored). |

## 1. Provision the VM

Create an **x86** server — `cpx21` (3 vCPU/4GB) minimum, `cpx31`/`cx32` (8GB) for comfortable
build headroom. **Not** an Arm `cax*` plan: all ctiq images are `linux/amd64` only (see the
`Makefile` `PLATFORM` pin), so Arm fails with `exec format error`. Verify after boot with
`uname -m` → must be `x86_64`.

### cloud-init (paste into Hetzner's "Cloud config" field)

Installs Docker + Compose plugin + BuildKit, creates a hardened non-root `deploy` user, and
disables root + password SSH. Replace the SSH key with your own public key.

```yaml
#cloud-config
package_update: true
package_upgrade: true
packages: [git, curl, ca-certificates]

users:
  - name: deploy
    groups: [sudo]
    shell: /bin/bash
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    ssh_authorized_keys:
      - ssh-ed25519 AAAA...REPLACE_WITH_YOUR_PUBLIC_KEY... you@host

disable_root: true
ssh_pwauth: false

write_files:
  - path: /etc/ssh/sshd_config.d/99-ctiq-hardening.conf
    permissions: "0644"
    content: |
      PermitRootLogin no
      PasswordAuthentication no
      KbdInteractiveAuthentication no
      PubkeyAuthentication yes

runcmd:
  - curl -fsSL https://get.docker.com | sh
  - systemctl enable --now docker
  - usermod -aG docker deploy   # in runcmd, not users: — the docker group doesn't exist until install
  - systemctl restart ssh
```

### Firewall (Hetzner Firewall resource, not ufw)

Open only 22 (scope to your admin IP), 80, and 443. api-core and inference-service publish no
host ports, so there's nothing else to expose.

## 2. Deploy

SSH in as **`deploy`** (never root):

```bash
ssh deploy@<vm-ip>
cloud-init status --wait        # confirm first-boot finished
uname -m                        # must be x86_64
docker compose version          # confirm the v2 plugin

# Clone via a read-only GitHub DEPLOY KEY (don't paste a personal token onto the box):
#   ssh-keygen -t ed25519     → add the .pub as a deploy key on the repo
git clone git@github.com:<org>/ctiq.git ctiq && cd ctiq

cp .env.production.example .env.production
nano .env.production           # real Supabase URLs, JWT_SECRET, SEARCH_API_TOKEN
chmod 600 .env.production
nano Caddyfile                 # set your real domain (or use the :80 block to test on the IP)

docker compose -f docker-compose.hetzner.yml --env-file .env.production up -d --build
docker compose -f docker-compose.hetzner.yml ps      # all 4 containers → (healthy)
docker compose -f docker-compose.hetzner.yml logs -f
```

**First build is slow** — inference-service bakes a ~274MB embedding model. Cached after that.

## 3. Update after a code change

```bash
ssh deploy@<vm-ip> && cd ctiq
git pull
docker compose -f docker-compose.hetzner.yml --env-file .env.production up -d --build
```

Compose recreates containers one at a time — a few seconds of downtime per service, not a true
rolling update. Acceptable for an MVP; move to k3s (`ctiq-hetzner-kubernetes`) when that matters.

## Notes / gotchas

- **`FAST_API_VERSION_V1` + `FAST_API_SEARCH_TRIAL_PATH` are required.** api-core's trial-search
  service `getOrThrow`s them; the compose file sets sensible defaults. Without them, trial search
  throws at runtime (the service still boots and passes healthchecks).
- **api-core `(unhealthy)` = a real failure.** Its `/` healthcheck runs `SELECT 1` (DB
  connectivity only). Unhealthy almost always means a bad/unreachable `DATABASE_URL` — use the
  Supabase **direct** connection (port 5432), not the 6543 transaction pooler.
- **Migrations:** run from anywhere with the 5432 direct URL —
  `make migrate-all DATABASE_URL="postgresql://...@db.<ref>.supabase.co:5432/postgres"`.
- **HF_TOKEN** is an optional build secret (the Dockerfile mount is `required=false`); only set
  it if anonymous Hugging Face downloads get rate-limited.
- **Lockout safety:** root/password SSH are disabled. Keep a second SSH session open when first
  connecting, and remember Hetzner's web Console (VNC) is the fallback if you lock yourself out.

## Observability (optional)

`inference-service` writes **one JSON object per line to stdout** (override with
`LOG_FORMAT=text` / `LOG_LEVEL=DEBUG` for local work) and exposes Prometheus metrics at
`/metrics` (internal network only - never route it through Caddy). Every request gets an
`X-Request-ID`, stamped on every log line it produces.

The collection stack is **opt-in** via a compose profile, so a normal deploy is unchanged:

```bash
# set GRAFANA_ADMIN_PASSWORD in .env.production first
docker compose -f docker-compose.hetzner.yml --env-file .env.production --profile monitoring up -d
ssh -L 3030:localhost:3030 deploy@<vm>      # then open http://localhost:3030 -> "ctiq - inference-service"
```

Prometheus (15-day metrics), Loki (14-day logs), Alloy (ships container logs) and Grafana add
roughly 0.7-1 GB RAM - use the 8 GB plan. Configs live in `infra/monitoring/`. Example log query:
`{service="inference-service"} | json | severity="ERROR"`.
Never log raw search text or patient profiles; log lengths, counts and ids.

