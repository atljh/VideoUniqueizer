# VideoUniqueizer

VideoUniqueizer is a Python-based tool designed to help you process and transform videos by adding unique watermarks, overlays, or other effects. It ensures that each video processed is distinct, making it ideal for situations where you need to produce multiple versions of a video for different purposes.

## Features

- **Watermarking**: Add custom watermarks to your videos to protect your content or brand them for different uses.
- **Batch Processing**: Handle multiple videos at once, with each video receiving a unique identifier.
- **Easy Configuration**: Customize the processing settings using a simple configuration file.
- **Logging**: Detailed logging for every step of the video processing, helping you keep track of what’s been processed and when.

## Prerequisites

- Docker

## Installation

1. **Clone the repository:**
   ```sh
   git clone https://github.com/atljh/VideoUniqueizer.git
   cd VideoUniqueizer
   ```

## Configuration

Edit the `.env` file to set up required environment variables:
```sh
BOT_TOKEN=your_bot_token
CHANNEL_URL=your_channel_url
CHANNEL_ID=your_channel_id
```

Modify the `docker-compose.yml` file if needed:
```yaml
version: '3'
services:
  telegram_bot:
    build: .
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - CHANNEL_URL=${CHANNEL_URL}
      - CHANNEL_ID=${CHANNEL_ID}
    restart: always
    volumes:
      - ./path/to/db.db:/app/db.db
      - ./logs:/app/logs
```

## Usage

1. **Build and run the container:**
   ```sh
   make build
   make run
   ```

2. **Check logs:**
   ```sh
   make logs
   ```
   or
   ```sh
   tail logs/bot.log
   ```

## Contributing

Feel free to contribute by submitting issues or pull requests. Any feedback is appreciated!

