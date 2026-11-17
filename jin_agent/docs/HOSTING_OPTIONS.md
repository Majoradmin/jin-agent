# HOSTING_OPTIONS — 24/7 Free Hosting for a Personal Telegram Bot

Checked: 16 November 2026, provider docs/pricing se verify (Sources dekhein).
Free tiers tez badalte hain — deploy se pehle aakhri check zaroor karein.

## 1. Context

Project: `jin_agent` — Python 3.14, stdlib-only Telegram bot (`python -m jin_agent bot`,
long polling `getUpdates`), chhota SQLite archive (`data/*.sqlite`, `data/config.json`),
loopback console (`127.0.0.1:8766`), Groq free-tier LLM, ~150 MB RAM, single user,
research jobs kabhi kabhi ~2 minute (LLM + HTTP fetches).

Deciding requirements: **24/7 always-on** (koi sleep/spin-down nahi),
**persistent local disk** (SQLite survive kare — ephemeral FS data uda deta hai),
**2-min jobs** (10 ms CPU / 60 s timeout wale serverless fail), **zero cost**
ideally bina card ke. Webhook optional — HTTPS endpoint chahiye, is liye polling.

## 2. Comparison

| Option | Always-on? | Free limits | Card? | Polling/Webhook | Verdict |
|---|---|---|---|---|---|
| **Oracle Cloud A1 (Arm)** | Haan, 24/7 VM | 2 OCPU + 12 GB RAM total, 200 GB block, 10 TB egress, no end date | Haan (verify only) | Dono (polling best) | **Top pick** |
| Oracle E2.1.Micro (AMD) | Haan | 2 × (1/8 OCPU, 1 GB RAM), same 200 GB pool | Haan | Dono | Backup plan, 1 GB RAM tight |
| Google Cloud e2-micro | Haan | 1 e2-micro/month, 30 GB pd-standard, 1 GB egress — **sirf** us-west1/us-central1/us-east1 | Haan | Dono | IPv4 ab paid (~$3.65/mo) → asal me free nahi |
| AWS Free Tier | 6 mahine | Ab 12-month tier nahi: $100 + $100 credits, Free plan 6 months, phir account band | Nahi (naye signup) | Dono | 2026 me long-term option nahi |
| Azure free account | 12 mahine | $200/30 days + 750 h B1s/B2pts/B2ats **12 months only** | Haan | Dono | Koi always-free VM nahi; month 13 pe bill |
| Render | Nahi | 750 instance-h/month, 512 MB, spin-down 15 min, no disk, free PG 30-day expiry | Nahi | Webhook (polling sleep ho jata) | SQLite ke liye unsuitable |
| Fly.io | Nahi (paid) | **Koi free tier nahi**; $1 trial 7 days, trial machine 5 min baad stop; <$5 invoice waived | Trial ke baad haan | Dono | Effective cost ~$2.19/mo = not free |
| Koyeb | Nahi | 1 free web service, 512 MB / 0.1 vCPU, 1 h idle → scale-to-zero, no volumes | Haan ($29 hold) | Webhook | Sleep + no disk + card = skip |
| Railway | Nahi | Trial $5/30 days, phir $1/month credit (0.5 GB cap) | Trial: nahi | Dono | $1 se 24/7 possible nahi |
| PythonAnywhere | Nahi | 1 web app (1-month expiry), 512 MB disk, 100 CPU-s/day, outbound whitelist | Nahi | Webhook-ish | 2026 ke naye accounts: no always-on task, no scheduled task → dead |
| Hugging Face Spaces | Nahi | Docker/Gradio Spaces ab **paid** (PRO $9); free = static + 2 ZeroGPU Gradio; 48 h sleep | PRO ke liye | Webhook | Docker free nahi raha |
| Cloudflare Workers | Nahi | 100k req/day, **10 ms CPU/request**, 128 MB, 50 subrequests | Nahi | Webhook only | 2-min research job possible nahi |
| Vercel Hobby | Nahi | 300 s max duration, 2 GB/1 vCPU, non-commercial only, no disk | Nahi | Webhook only | Bot loop + SQLite fit nahi |
| Heroku | Nahi (free nahi) | Free 28 Nov 2022 ko khatam; Eco $5/mo, 30 min idle sleep | Haan | Dono | Paid hai, free nahi |
| **fps.ms** | Haan | 128 MB RAM, 25% CPU, 250 MB SSD, **har 24 h renew**, no public URL on free | Nahi | Polling | 128 MB < 150 MB usage → OOM risk |
| **FadeHost** | Haan | 1 bot, 256 MB, 0.25 vCPU, 3 GB disk (`/data` persist), no renewal | Nahi | Polling (webhook paid) | **Runner-up** |
| SnapDeploy | Nahi | 4 containers, 100 container-hours/**month**, 512 MB, 15 min sleep | Nahi | Webhook | 100 h/month ≈ 4 din 24/7 |

## 3. Top recommendation: Oracle Cloud Always Free — A1 Flex VM

**Kyun:** yeh wahid option hai jo asli VM deta hai — apna filesystem, apna
systemd/Docker, apna SQLite, koi sleep nahi, koi monthly hour budget nahi.
2 OCPU / 12 GB humare 150 MB workload ke liye huge headroom hai, is liye 2-min
research jobs aur `batch` parallel runs aaram se chal jayenge. Long polling
default reh sakta hai, console loopback par band rehta hai.
**Numbers:** 2 OCPU + 12 GB (1,500 OCPU-h + 9,000 GB-h/month), 200 GB block
storage (boot + data), 5 volume backups, 10 TB/month egress, home region only.

**Risks aur unka jawab:**

- **Quota halved:** 4 OCPU/24 GB → **2 OCPU/12 GB** (docs 15 June 2026,
  enforcement ~18 Aug 2026); 4/24 wali purani guides galat hain.
- **Idle reclaim:** 7 din tak *teeno* true hon to reclaim ho sakta hai — CPU
  p95 < 20%, network < 20%, memory < 20% (A1 only). 150 MB / 12 GB ≈ 1.2%, is
  liye rule match kar sakta hai — mitigation Section 6 me.
- **Capacity:** "Out of host capacity" common hai — doosra AD ya scripted retry;
  home region signup ke baad change nahi hoti.
- **ARM (aarch64):** Python 3.14 uv/pyenv se; project stdlib-only hai, so issue nahi.
- **Account risk:** card verification ke liye (charge nahi jab tak upgrade na
  karein); 30 din idle account suspend ho sakta hai — backup off-box rakhein.

## 4. Runner-up: FadeHost free bot plan

Oracle signup/capacity se tang aa jayein to: FadeHost free = 256 MB RAM, 0.25
vCPU, 3 GB disk (`/data` deploys ke across rehta hai), **24/7 with no renewal
clicks**, no card, 1 bot, push-to-deploy + live console. Polling ke liye theek,
kyunki bot ko inbound traffic ki zaroorat nahi.

**Kyun top nahi:** free par region choice nahi, HTTPS webhook paid ($2/mo),
daily backups paid ($1/mo), aur yeh chhota commercial host hai — long-term
guarantee nahi. 256 MB me 150 MB bot + 2-min spike chal jayega magar headroom
kam hai; `data/` ko cron se off-box copy karein.

**fps.ms** budget floor (128 MB, 25% CPU, 250 MB SSD, Netherlands, no card) magar
**har 24 ghante manual renew**, 128 MB RAM humare ~150 MB se kam (OOM risk),
free par public URL nahi, renewal miss = offline. Sirf last resort.

## 5. What to avoid (aur kyun)

- **Render / SnapDeploy / Koyeb / Railway** — ephemeral FS ya no volume
  (SQLite har restart pe gayab) + sleep/scale-to-zero jo long polling ko maar
  deta hai; Render ka free Postgres 30 din me expire hota hai.
- **Cloudflare Workers / Vercel Hobby** — 10 ms CPU / 300 s cap + koi disk
  nahi. Yeh webhook receivers hain, bot runtime nahi.
- **AWS Free / Azure free** — trial hain, hosting nahi: AWS ka 6-month plan
  khatam par account close, Azure ka VM 12 months baad bill karta hai.
- **Fly.io** — free tier khatam (Oct 2024); $5 waiver ke liye bhi card lagta hai.
- **PythonAnywhere free** — naye accounts (2026-01-15 ke baad) me always-on
  task, scheduled task aur MySQL nahi; web app 1 month me expire.
- **HF Spaces** — Docker Spaces paid (PRO $9); **Heroku** — free 2022 me khatam,
  Eco $5 + 30 min sleep.
- **Webhook + polling ek saath** — Telegram 409 Conflict deta hai; ek hi mode.

## 6. Deployment checklist — Oracle A1 (Ubuntu 24.04)

1. **Account:** oracle.com/cloud/free se signup; home region wahi chunein jahan
   latency kam ho (Singapore/Mumbai/Frankfurt) — Always Free sirf home region
   me milta hai. Card sirf verification ke liye (upgrade na karein to charge nahi).
2. **Instance:** Compute → Create. Image **Ubuntu 24.04** (Minimal nahi), shape
   `VM.Standard.A1.Flex` **2 OCPU / 12 GB**, boot volume 50 GB (200 GB pool),
   "Assign a public IPv4" = Yes.
3. **SSH keys:** create ke waqt public key paste karein. `ssh -i ~/.ssh/oracle_bot
   ubuntu@<ip>`. Password auth band rakhein.
4. **Firewall (do jagah):** OCI → VCN → Security List → Ingress sirf `22/tcp`
   apne IP se (80/443 sirf tab jab Cloudflare Tunnel na ho); host par
   `sudo ufw allow from <your-ip> to any port 22 proto tcp && sudo ufw enable`.
   Console **8766 kabhi public na karein** — woh loopback-only designed hai.
5. **Python 3.14:** `curl -LsSf https://astral.sh/uv/install.sh | sh` phir
   `uv python install 3.14` (arm64 wheels). Ubuntu ka `python3` 3.12 hai, is liye
   uv/pyenv zaroori hai.
6. **Code + data:** repo `/opt/jin_agent` par (git/rsync), `data/` ko
   `/var/lib/jin_agent/data` par, ownership `jinbot:jinbot` (non-root).
7. **systemd unit** (`/etc/systemd/system/jin-bot.service`):

   ```ini
   [Unit]
   Description=JIN Agent bot (long polling)
   After=network-online.target

   [Service]
   Type=simple
   User=jinbot
   WorkingDirectory=/opt/jin_agent
   Environment=PYTHONUNBUFFERED=1
   ExecStart=/opt/jin_agent/.venv/bin/python -m jin_agent bot
   Restart=always
   RestartSec=10
   MemoryMax=700M

   [Install]
   WantedBy=multi-user.target
   ```

   `sudo systemctl daemon-reload && sudo systemctl enable --now jin-bot`;
   console ke liye alag unit `python -m jin_agent serve` (127.0.0.1:8766).
8. **Auto-restart + logs:** unit me `Restart=always`/`RestartSec=10` (upar);
   `systemctl status jin-bot`, `journalctl -u jin-bot -f`. Journald cap:
   `/etc/systemd/journald.conf` → `SystemMaxUse=200M`; file logs hon to
   `/etc/logrotate.d/jin-agent` (daily, rotate 7, compress).
9. **Backups (`data/*.sqlite`):** har 6 ghante
   `sqlite3 data/jin.sqlite ".backup '/var/backups/jin-$(date +%F-%H).sqlite'"`
   (plain `cp` na karein — WAL ke saath corrupt ho sakta hai), phir `rclone`/`scp`
   se off-box. `data/config.json` (tokens) bhi encrypted backup karein.
10. **Optional HTTPS webhook / remote console:** Cloudflare Tunnel free hai (no
    card): `cloudflared tunnel create jin` → `cloudflared tunnel route dns jin
    bot.example.com` → `cloudflared service install`. Webhook on karne se pehle
    polling band / `deleteWebhook`, warna Telegram 409 Conflict deta hai.
11. **Monitoring + idle-reclaim mitigation:** OCI → Observability → Metrics me
    CPU/memory/network 7-din rolling dekhein + UptimeRobot/Better Stack free
    heartbeat monitor lagayein. Reclaim rule *teeno* conditions par chalta hai,
    is liye memory 20% se upar rakhein — e.g. `stress-ng --vm 1 --vm-bytes 3G
    --vm-keep --timeout 0` ko systemd service banayein (12 GB me se 3 GB) ya
    2.5 GB tmpfs mount rakhein. (Honest note: workaround hai; sanctioned raasta
    Pay-As-You-Go upgrade hai, magar usme billing risk hai.) Mahine me ek baar
    Console me login karein (30-din idle suspension se bachne ke liye).

## 7. Sources

- Oracle Always Free resources (limits + idle reclamation): https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- Oracle A1 2 OCPU / 12 GB announcement: https://community.oracle.com/customerconnect/discussion/970310 (coverage: https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits)
- Oracle practical breakdown: https://rythium.com/oracle-cloud-free-tier/ · https://site2us.com/en/servers/oracle-cloud-free-tier
- Google Cloud free tier: https://docs.cloud.google.com/free/docs/free-cloud-features · IPv4 cost: https://agentdeals.dev/vendor/google-compute-engine
- AWS Free Tier plans/credits: https://aws.amazon.com/free/free-tier-faqs/ · https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html
- Azure free account: https://azure.microsoft.com/en-us/pricing/purchase-options/azure-account · https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/create-free-services
- Render: https://render.com/docs/free · Fly.io: https://fly.io/docs/about/pricing · https://docs.fly.io/about/free-trial
- Koyeb: https://www.koyeb.com/docs/reference/instances · https://www.koyeb.com/docs/run-and-scale/scale-to-zero · Railway: https://devshot.co/blog/is-railway-free
- PythonAnywhere: https://help.pythonanywhere.com/pages/FreeAccountsFeatures · https://blog.pythonanywhere.com/221
- Hugging Face Spaces: https://huggingface.co/docs/hub/spaces-overview · Cloudflare Workers: https://developers.cloudflare.com/workers/platform/limits/
- Vercel: https://vercel.com/docs/plans/hobby · https://vercel.com/docs/functions/limitations · Heroku: https://devcenter.heroku.com/articles/eco-dyno-hours
- fps.ms: https://fps.ms/free-telegram-bot-hosting · https://docs.fps.ms/getting-started/how-server-renewal-works
- FadeHost: https://fadehost.com/telegram-bot-hosting · SnapDeploy: https://snapdeploy.dev/docs/free-tier
