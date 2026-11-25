#!/bin/bash
S=$1; cd $S
for id in $(cat ids.txt); do
  f="raw/$id.html"; [ -s "$f" ] || { curl -s -m 60 -o "$f" "https://arxiv.org/abs/$id"; sleep 3; }
  if grep -q 'creativecommons.org/licenses/by\(-sa\)\?/4.0\|creativecommons.org/publicdomain' "$f"; then
    p="pdf/$id.pdf"; [ -s "$p" ] || { curl -s -m 120 -L -o "$p" "https://arxiv.org/pdf/$id"; sleep 3; }
  fi
done
echo done $(ls raw | wc -l) html $(ls pdf | wc -l) pdf
