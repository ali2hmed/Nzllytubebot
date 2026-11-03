FROM python:3.12-slim
WORKDIR /app
# ffmpeg merges YouTube's separate video and audio and makes MP3s; gcc only builds tgcrypto, then goes
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg gcc libc6-dev \
 && pip install --no-cache-dir tgcrypto tzdata \
 && apt-get purge -y gcc libc6-dev && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
# yt-dlp needs a JavaScript runtime to read YouTube's video links
COPY --from=denoland/deno:bin-2.1.4 /deno /usr/local/bin/deno
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py .
ENV DATA_DIR=/data PYTHONUNBUFFERED=1 DAILY_RESTART=1
# YouTube changes often, so get the newest yt-dlp on every start
CMD ["sh", "-c", "pip install -q --no-cache-dir --root-user-action=ignore --disable-pip-version-check -U 'yt-dlp[default]'; exec python bot.py"]
