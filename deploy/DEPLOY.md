# Deployment — datahive.uwyo.edu

How the OSDR ChatBot is served on the DataHive portal at
**https://datahive.uwyo.edu/osdr/**. It runs as a user systemd service on
localhost and is exposed through the site's Apache reverse proxy — it is **not**
an Open OnDemand app.

```
Browser ──HTTPS──► Apache (ood-portal.conf, :443)
                     │  ProxyPass /osdr/ ──► 127.0.0.1:8077 (uvicorn, user systemd)
                     └─ DocumentRoot /var/www/datahive  (portal landing page + cards)
```

## 1. Backend service

Run the FastAPI backend as a user systemd service (see
[`osdr-chatbot.service`](osdr-chatbot.service)), bound to `127.0.0.1:8077`:

```bash
cp deploy/osdr-chatbot.service ~/.config/systemd/user/
export XDG_RUNTIME_DIR=/run/user/$(id -u)
systemctl --user daemon-reload
systemctl --user enable --now osdr-chatbot
loginctl enable-linger "$USER"          # keep running across logout/reboot
```

Build the frontend first so FastAPI can serve it at `/`
(`cd frontend && npm run build`). The build is path-relocatable
(Vite `base: './'`, API paths relative to `document.baseURI`), so it works
under the `/osdr/` prefix without rebuilding.

## 2. Apache reverse proxy

Add to the active `:443` vhost (`/etc/apache2/sites-available/ood-portal.conf`),
alongside the other portal app proxies:

```apache
# OSDR ChatBot (RAG webapp)
ProxyPass        /osdr/ http://127.0.0.1:8077/ flushpackets=on
ProxyPassReverse /osdr/ http://127.0.0.1:8077/
```

`flushpackets=on` prevents Apache from buffering the `/api/chat` SSE token
stream. Apply with:

```bash
sudo apache2ctl configtest && sudo systemctl reload apache2
# local test (vhost binds the internal IP, not loopback):
curl -k --resolve datahive.uwyo.edu:443:172.26.7.78 https://datahive.uwyo.edu/osdr/
```

## 3. Portal card

The DataHive landing page is `/var/www/datahive/index.html` (a grid of `.card`
blocks). Add a card linking to the trailing-slash path:

```html
<a class="card" href="/osdr/">
  <div class="card-icon">🤖</div>
  <h2>OSDR ChatBot</h2>
  <p>RAG chatbot over NASA's Open Science Data Repository — ask across all 588
     OSD studies; answers cite the source study IDs.</p>
</a>
```

The link must keep the trailing slash (`/osdr/`) to match the `ProxyPass` rule.
