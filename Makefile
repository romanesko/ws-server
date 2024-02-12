IMAGE_NAME=ws-server

build:
	docker build -t $(IMAGE_NAME) .

run:
	docker run -it --rm --env-file .env $(IMAGE_NAME)

sh:
	docker run -it --rm --env-file .env $(IMAGE_NAME) --entrypoint /bin/sh