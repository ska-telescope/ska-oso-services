ARG BUILD_IMAGE="artefact.skao.int/ska-tango-images-pytango-builder:9.4.3"
ARG BASE_IMAGE="artefact.skao.int/ska-tango-images-pytango-runtime:9.4.3"

FROM $BUILD_IMAGE AS buildenv
FROM $BASE_IMAGE AS runtime

ARG CAR_PYPI_REPOSITORY_URL=https://artefact.skao.int/repository/pypi-internal
ENV PIP_INDEX_URL=${CAR_PYPI_REPOSITORY_URL}

USER root

WORKDIR /app

# Used by the FilesystemRepository implementation of the ODA
RUN mkdir -p /var/lib/oda && chown -R tango /var/lib/oda

# Copy poetry.lock* in case it doesn't exist in the repo
COPY pyproject.toml poetry.lock* ./

# Install runtime dependencies and the app
RUN poetry config virtualenvs.create false
# Developers may want to add --dev to the poetry export for testing inside a container
RUN poetry export --format requirements.txt --output poetry-requirements.txt --without-hashes && \
    pip install -r poetry-requirements.txt && \
    pip install . && \
    rm poetry-requirements.txt

USER tango

CMD ["python3", "-m", "ska_oso_services.wsgi"]
