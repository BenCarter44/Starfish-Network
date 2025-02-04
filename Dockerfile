
FROM ubuntu

ENV DEBIAN_FRONTEND=nointeractive

RUN apt update
RUN apt install wget g++ -y
RUN apt install python3 -y

WORKDIR "/home/ubuntu"

RUN apt install python3-pip -y
RUN pip install virtualenv --break-system-packages

COPY requirements.txt .
RUN pip install -r requirements.txt --break-system-packages

COPY . .


CMD python3 test.py 1
