#!/bin/bash
# usage: fetch.sh id...   saves raw/<id>.html
for id in "$@"; do
  f="raw/${id//\//_}.html"
  [ -s "$f" ] && continue
  for t in 1 2 3; do
    code=$(curl -s -o "$f" -w "%{http_code}" "https://arxiv.org/abs/$id")
    [ "$code" = 200 ] && break
    sleep $((t*5))
  done
  echo "$code $id"
  sleep 3
done
