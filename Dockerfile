FROM ubuntu:latest

LABEL vendor="AiLECS Lab"
LABEL status="Alpha"

MAINTAINER = Janis Dalins 'janis.dalins@afp.gov.au'

RUN mkdir /facebook
RUN apt-get update && apt-get -y install \
build-essential \
git \
imagemagick \
python3.7-dev \
python3-pip

# clone and build PDQ hashing cpp binaries
RUN git clone https://github.com/facebook/ThreatExchange.git /facebook
WORKDIR /facebook/hashing/pdq/cpp
RUN make

# install python requirements
COPY ./requirements.txt /app/requirements.txt
WORKDIR /app
#RUN pip3 install -r requirements.txt
RUN python3.7 /usr/bin/pip3 install -r requirements.txt

COPY python/ /app/

EXPOSE 8080

ENTRYPOINT [ "python3.7" ]

CMD [ "app.py" ]