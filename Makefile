CONTAINER_RUNTIME ?= docker

holder:
	$(CONTAINER_RUNTIME) run --rm -it -p 3000:3000 -p 3001:3001 \
		-v $(abspath ./configs):/home/indy/configs:z \
		bcgovimages/aries-cloudagent:py36-1.16-0_0.6.0 \
		start --arg-file ./configs/holder.yml -e http://rocket:3000

issuer:
	$(CONTAINER_RUNTIME) run --rm -it -p 3002:3000 -p 3003:3001 \
		-v $(abspath ./configs):/home/indy/configs:z \
		bcgovimages/aries-cloudagent:py36-1.16-0_0.6.0 \
		start --arg-file ./configs/issuer.yml -e http://rocket:3002
