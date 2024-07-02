# Build Stage
FROM python:3.11-alpine3.19 AS builder

ARG DEBIAN_FRONTEND=noninteractive

WORKDIR /build

# Copy only the necessary files for building

# Install build dependencies and compile
RUN apk --no-cache add git gcc musl-dev libffi-dev bash

COPY requirements.txt .
# COPY pyproject.toml .

RUN pip install -r requirements.txt

COPY . .

# Final Stage
FROM python:3.11-alpine3.19

WORKDIR /app

# Copy the installed code from the build stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY defi_repertoire ./defi_repertoire


ENV PYTHONPATH=.
ENV PORT=8000

CMD uvicorn defi_repertoire.main:app --workers=4 --host=0.0.0.0 --port=${PORT} --loop=asyncio --no-use-colors