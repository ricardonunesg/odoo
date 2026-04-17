FROM odoo:18.0

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        freetds-bin \
        tdsodbc \
        unixodbc \
        python3-pyodbc \
    && rm -rf /var/lib/apt/lists/*

USER odoo
