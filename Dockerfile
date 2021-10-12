FROM ubuntu
RUN apt-get update
RUN apt-get git libxml2-dev libxslt-dev build-base -y
RUN git clone https://github.com/ustayready/fireprox /root/fireprox
RUN cd /root/fireprox && pip install -r requirements.txt
WORKDIR /root/fireprox
COPY entrypoint.sh /tmp/entrypoint.sh
RUN chmod +x /tmp/entrypoint.sh
ENTRYPOINT ["/tmp/entrypoint.sh"]
