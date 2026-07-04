# firefox_antidetect

Antidetect browser **profile manager** (manual use) for the patched Firefox,
built on [`invisible_core`](https://github.com/feder-cr/invisible_core). Manage
many persistent browser identities — each with its own fixed fingerprint,
proxy, and persisted cookies/logins — and launch a real Firefox window per
profile. No Playwright.

## Install (dev)

```bash
pip install -e .            # pulls invisible-core (git) + platformdirs + PySide6
```

## Run

```bash
python -m firefox_antidetect
```

- The window lists your profiles. **New** creates one (name, seed, proxy,
  locale/timezone; *Preview fingerprint* shows the GPU/screen/fonts it will
  present). **Launch** opens a real Firefox window with that identity.
  **Edit** / **Delete** manage them.
- On the first launch of a given `firefox-N`, the patched binary is downloaded
  automatically (cached under your user data dir). It is not bundled.
- Each profile's fingerprint is stable across launches (fixed seed), and its
  cookies/storage/logins persist in its own profile directory.
- `locale`/`timezone` default to `auto` — resolved from the proxy's egress
  country so the browser's clock and language match the proxy.

## Where data lives

`platformdirs.user_data_dir("firefox-antidetect")`:
- `profiles.db` — profile metadata (SQLite)
- `profiles/<id>/` — the persistent Firefox profile (cookies, storage, `user.js`)

## Tests

```bash
pip install -e ".[dev]"
python -m pytest -q                 # unit + Qt smoke (offscreen)
python -m pytest -m integration -q  # launches a real firefox-14 (needs the binary)
```

## Packaging (standalone app)

```bash
pip install pyinstaller
pyinstaller packaging/firefox_antidetect.spec     # run once per OS
```

Produces an onedir bundle under `dist/firefox_antidetect/` (Windows `.exe`,
Linux dir/AppImage-ready, macOS `.app`). The Firefox binary is **not** bundled —
`ensure_binary()` downloads it on first launch. Code-signing and auto-update are
future work.

