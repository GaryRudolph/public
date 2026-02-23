#!/usr/bin/env bash

# Reset Docker to a clean vanilla state. Will destroy all containers, images, networks, volumes, and cache.

[ $(docker ps | wc -l) -ne 1 ] && echo "Stopping all containers..." && docker stop $(docker ps | sed -n '1d;p' | awk -F" " '{print $1}')
[ $(docker ps -a | wc -l) -ne 1 ] && echo "Deleting all containers..." && docker rm $(docker ps -a | sed -n '1d;p' | awk -F" " '{print $1}')
[ $(docker images | wc -l) -ne 1 ] && echo "Deleting all images..." && docker image rm $(docker images | sed -n '1d;p' | awk -F" " '{print $3}')
echo "Pruning networks, volumes, and cache..." && docker system prune -a -f --volumes

echo "Docker is back to Vanilla... COMPLETE!"
