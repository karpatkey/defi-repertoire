FROM debian:12-slim

ARG DEBIAN_FRONTEND=noninteractive

COPY requirements.txt .

RUN apt-get update \
    && apt-get install -qq -y --no-install-recommends \
                        git \
                        python3 \
                        python3-dev \
                        python3-pip \
                        build-essential \
                        gcc \
    && pip install --break-system-packages -r requirements.txt \
    && apt-get autoremove -qq -y gcc build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

EXPOSE 8000

COPY rolesapi rolesapi

CMD ["uvicorn", "rolesapi.main:app", "--workers", "4"]
