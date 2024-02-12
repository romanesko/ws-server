FROM python:3.12.2-alpine3.19 as compile-image
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12.2-alpine3.19 as build-image
COPY --from=compile-image /root/.local /root/.local

COPY ./src /src
WORKDIR /src

ENV PATH=/root/.local/bin:$PATH
ENTRYPOINT ["python3", "app.py"]