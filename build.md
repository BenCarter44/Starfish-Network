# Build Instructions


### Build image
``` sh
docker buildx build -t starfishnode .
```

### Run image 
``` sh
# Make sure that the port (-p) is the same as transport! Transport is what is broadcasted to others, so 
# it must be reachable by other nodes.
# It internally uses the -p flag from main.py to bind to all IPs (so it removes the need for --network host)
# IOPORT does not need to match. 2321 internal

sudo docker run -p 9280:9280 -p 2322:2321 -e ADDRESS="01:02:03:04:05:06:07:08" -e TRANSPORT="tcp://127.0.0.1:9280" \
    -d --name mynode -t starfishnode
```

### Run image without using docker (with uv)
``` sh
uv run --python 3.11 main.py -a 01:02:03:04:05:06:07:08 -i 2321 -t tcp://127.0.0.1:9281
```