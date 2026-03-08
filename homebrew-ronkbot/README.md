# ronkbot Homebrew Tap

[![Homebrew](https://img.shields.io/badge/homebrew-tap-orange?logo=homebrew)](https://brew.sh)

Official Homebrew tap for [ronkbot](https://github.com/rohankag/ronkbot) — a personal AI assistant running on your Mac.

## Install

```bash
brew tap rohankag/ronkbot
brew install ronkbot
```

Then run the setup wizard:

```bash
ronkbot config
```

## What Gets Installed

- `ronkbot` CLI command — manage your bot from the terminal
- All required configuration files
- Docker Compose setup for n8n

## Requirements

- macOS (Intel or Apple Silicon)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- ~5 minutes for setup

## Upgrade

```bash
brew upgrade ronkbot
```

## Uninstall

```bash
brew uninstall ronkbot
brew untap rohankag/ronkbot
```

## Source

Formula: [Formula/ronkbot.rb](Formula/ronkbot.rb)  
Repository: [rohankag/ronkbot](https://github.com/rohankag/ronkbot)
