# https://hub.docker.com/_/python
FROM python:3.8-slim-buster

ENV PYTHONUNBUFFERED True

RUN apt-get -y update && apt-get -y upgrade && apt-get install -y ffmpeg

WORKDIR /src
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /src/app

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
