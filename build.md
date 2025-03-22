# Build Instructions


### Build image
``` sh
docker buildx build -t starfish .
```

### Run image 
``` sh
# Make sure that the port (-p) is the same as transport! Transport is what is broadcasted to others, so 
# it must be reachable by other nodes.
# It internally uses the -p flag from main.py to bind to all IPs (so it removes the need for --network host)
# IOPORT does not need to match. 2321 internal

sudo docker run -p 9280:9280 -p 2322:2321 \
    -e ADDRESS="01:02:03:04:05:06:07:08" \
    -e TRANSPORT="tcp://127.0.0.1:9280" \
    -v log:/home/ubuntu/log \
    -d --name mynode -t starfish
```

### Run image without using docker (with uv)
``` sh
mkdir -p filestorage
mkdir -p log
uv run main.py -a 01:02:03:04:05:06:07:08 -i 2321 -t tcp://127.0.0.1:9281
```

### Run Simulation
A simulation controller does not require the full package environment. It only needs
the packages in `sim-requirements.txt` 

So, do the usual. Don't forget the .env file with the following:
``` sh
MQTT_SERVER = ""
MQTT_PORT = 1883
MQTT_USER = ""
MQTT_PWD = ""
``` 

``` sh
virtualenv sim-env
source sim-env/bin/activate
pip install -r sim-requirements.txt

# To run worker host:
python3 simulation_client.py

# To run testing controller
python3 simulation_test.py

# To run simulation logger
python3 simulation_logger.py

# To run simulation viewer (web server)
cd sim
python3 server.py # opens a web server
```