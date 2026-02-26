#!/bin/sh
PATTERNS_FILE=/tmp/patterns.tmp
SITES_BASE=/ren-web/internet/active
RENESAS_BASE=/opt/bea/renesas

cat /dev/null > ${PATTERNS_FILE}

echo Finding missing...
for PATTERN in `awk '/(<Included resource or file \")*(\" not found from requested resource)/ {s=index($0,"<Included")+28; l=index($0,"\" not found from requested resource")-s; print substr($0, s, l)}' ${RENESAS_BASE}/*/act-server-*/weblogic.log*`; do
  if [ `grep -c ${PATTERN} ${PATTERNS_FILE}` -eq 0 ]; then
    echo ${PATTERN}>> ${PATTERNS_FILE}
  fi
done

echo Searching ${SITES_BASE}
cd ${SITES_BASE}
for SITE in `/bin/ls -l | awk '/^d/ {print $9}'`; do
  cd ${SITE}
  for FILE in `find . -name '*.jsp'`; do
    for PATTERN in `cat ${PATTERNS_FILE}`; do
      if [ ! -f .${PATTERN} -a ! -d .${PATTERN} ]; then
        if [ `grep -c ${PATTERN} ${FILE}` -ne 0 ]; then
          echo ${SITE}:${FILE}:${PATTERN}
        fi
      fi
    done
  done
  cd ..
done
echo Done.
rm ${PATTERNS_FILE}