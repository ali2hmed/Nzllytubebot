# YouTube Downloader Bot 🎬

A Telegram bot that downloads YouTube videos and Shorts in the quality you pick, from 144p up to 4K,
or as MP3. In English and Arabic.

Send it a link in private, or use `/dl <link>` in a group. People have to join
[@aliahmedbots](https://t.me/aliahmedbots) first (set `MUST_JOIN=` in `.env` to turn that off).

## Run it

1. Copy `.env.example` to `.env` and fill in your keys.
2. `docker compose up -d --build`

Messages are in `texts.py`. Videos over Telegram's 2 GB limit aren't offered.

Made by [@aliahmedbots](https://t.me/aliahmedbots)
