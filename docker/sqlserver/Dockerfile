FROM mcr.microsoft.com/azure-sql-edge:latest

COPY docker/sqlserver/init-db.sh /usr/src/app/init-db.sh
COPY docker/sqlserver/init-db.sql /usr/src/app/init-db.sql

USER root

RUN chmod +x /usr/src/app/init-db.sh

CMD ["/bin/bash", "/usr/src/app/init-db.sh"]
