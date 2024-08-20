# VideoUniqueizer

VideoUniqueizer is a Python-based tool designed to help you process and transform videos by adding unique watermarks, overlays, or other effects. It ensures that each video processed is distinct, making it ideal for situations where you need to produce multiple versions of a video for different purposes.

## Features

- **Watermarking**: Add custom watermarks to your videos to protect your content or brand them for different uses.
- **Batch Processing**: Handle multiple videos at once, with each video receiving a unique identifier.
- **Easy Configuration**: Customize the processing settings using a simple configuration file.
- **Logging**: Detailed logging for every step of the video processing, helping you keep track of what’s been processed and when.

## Prerequisites

Docker

## Installation

1. **Clone the repository:**

   ```
   git clone https://github.com/atljh/VideoUniqueizer.git
   cd VideoUniqueizer
    ```
##Usage
1. Configure your settings:

Edit the docker-compose.yaml file to adjust the processing settings.

2. Run bot:

    ```
    make build
    make run
    ```
