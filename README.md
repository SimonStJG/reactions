Requires ffmpeg and libasound2-dev on Ubuntu.

## Link-local

To connect direct to the machine without needing a router

On Ubuntu:

```
sudo apt-get install avahi-daemon avahi-discover avahi-utils libnss-mdns mdns-scan
```

Then plug in the ethernet cable and set to link-local in the network settings.  The raspberry pi will be at raspberrypi.local.

