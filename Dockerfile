
FROM ubuntu
LABEL maintainer="Benjamin Carter"

ENV DEBIAN_FRONTEND=nointeractive

RUN apt update
RUN apt install wget g++ -y
RUN apt install python3 -y
RUN apt install net-tools -y
RUN apt install iputils-ping -y
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"

WORKDIR "/home/ubuntu"

COPY .env .env
COPY pyproject.toml .
COPY .python-version .
COPY uv.lock .
# RUN uv init

# copy repository into /home/ubuntu
RUN mkdir filestorage
COPY examples examples
COPY src src

# Build all star files
WORKDIR "/home/ubuntu/examples"
RUN for file in *.stardef.py; do uv run "$file"; done
WORKDIR "/home/ubuntu"

COPY main.py main.py

ENV ADDRESS="01:02:03:04:05:06:07:08"
ENV TRANSPORT="tcp://127.0.0.1:9280"
ENV IOPORT=2321
ENV PYTHONUNBUFFERED=1
# CMD ["bash"]
CMD ["sh","-c","uv run main.py -a ${ADDRESS} -t ${TRANSPORT} -i ${IOPORT} -p -v 4"]
