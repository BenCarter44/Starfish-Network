
``` sh
# To build image.
docker buildx build -t starfishnode .
```


``` sh
sudo docker run --network host -e ADDRESS="01:02:03:04:05:06:07:08" -e IOPORT=2321 -e TRANSPORT="tcp://127.0.0.1:9281" -d --name mynode -t starfishnode
```