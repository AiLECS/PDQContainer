FROM ubuntu:latest
# JD 20200728: Below line added to avoid interaction required by tzdata updgrade.
ENV DEBIAN_FRONTEND=noninteractive

LABEL vendor="AiLECS Lab"
LABEL status="Beta"

MAINTAINER = Janis Dalins 'janis.dalins@afp.gov.au'

RUN mkdir /facebook
RUN apt-get update

RUN apt upgrade -y

RUN apt -y install \
build-essential \
git \
imagemagick \
python3-dev \
python3-pip

# clone and build PDQ hashing cpp binaries
RUN git clone https://github.com/facebook/ThreatExchange.git /facebook
WORKDIR /facebook/hashing/pdq/cpp
RUN make -Wall -Wno-error   R

# install python requirements
COPY ./requirements.txt /app/requirements.txt
WORKDIR /app

#RUN pip3 install -r requirements.txt
RUN python3 /usr/bin/pip3 install -r requirements.txt

COPY python/ /app/

EXPOSE 8080

ENTRYPOINT [ "python3" ]

CMD [ "app.py" ]