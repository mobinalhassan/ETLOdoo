# syntax=docker/dockerfile:experimental
FROM python:3.7.6-slim
ENV DISPLAY=:99
WORKDIR /app

ADD ./scripts/setup.sh /app/scripts/setup.sh
ADD ./requirements.txt /app/requirements.txt

RUN bash scripts/setup.sh

RUN pip install -r requirements.txt
ADD ./ /app
CMD ["bash", "./scripts/run.sh"]
