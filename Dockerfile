
FROM ubuntu
LABEL maintainer="Benjamin Carter"

ENV DEBIAN_FRONTEND=nointeractive

RUN apt update
RUN apt install wget g++ -y
RUN apt install python3 -y

WORKDIR "/home/ubuntu"

RUN apt install python3-pip -y
RUN pip install virtualenv --break-system-packages

COPY requirements.txt .
RUN pip install -r requirements.txt --break-system-packages

# copy repository into /home/ubuntu
RUN mkdir filestorage
COPY examples examples
COPY src src
COPY main.py main.py



ENV ADDRESS="01:02:03:04:05:06:07:08"
# CMD ["bash"]
ENV TRANSPORT="tcp://0.0.0.0:9820"
ENV IOPORT=2321
# CMD ["python3","main.py","-a", "${address_var}","-t","${transport_var}","-i","${ioport_var}"]
CMD ["sh","-c","python3 main.py -a ${ADDRESS} -t ${TRANSPORT} -i ${IOPORT}"]