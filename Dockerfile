FROM ubuntu
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update
RUN apt-get install git libxml2-dev libxslt-dev python3 python3-pip -y
RUN git clone https://github.com/ustayready/fireprox /root/fireprox
RUN cd /root/fireprox && pip3 install -r requirements.txt
WORKDIR /root/fireprox
COPY entrypoint.sh /tmp/entrypoint.sh
RUN chmod +x /tmp/entrypoint.sh
ENTRYPOINT ["/tmp/entrypoint.sh"]
