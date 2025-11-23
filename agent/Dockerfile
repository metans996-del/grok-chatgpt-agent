FROM python:3.10-slim

RUN useradd -m sandbox
WORKDIR /home/sandbox/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /home/sandbox/app
RUN chown -R sandbox:sandbox /home/sandbox/app
USER sandbox

CMD ["pytest", "-q"]
