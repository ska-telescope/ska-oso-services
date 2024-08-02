# This Dockerfile taken heavily from FastAPI docs:
# https://fastapi.tiangolo.com/deployment/docker/#build-a-docker-image-for-fastapi
# and this blog post about Poetry in containers:
# https://medium.com/@albertazzir/blazing-fast-python-docker-builds-with-poetry-a78a66f5aed0


## The builder image, used to build the virtual environment
ARG BUILD_IMAGE="artefact.skao.int/ska-cicd-k8s-tools-build-deploy:0.13.1"
ARG RUNTIME_BASE_IMAGE="python:3.11-slim-bullseye"

FROM $BUILD_IMAGE AS buildenv


ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN touch README.md

RUN poetry install --without dev --no-root && rm -rf $POETRY_CACHE_DIR

# The runtime image, used to just run the code provided its virtual environment
FROM $RUNTIME_BASE_IMAGE AS runtime

# Used by the FilesystemRepository implementation of the ODA
RUN mkdir -p /var/lib/oda

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY --from=buildenv ${VIRTUAL_ENV} ${VIRTUAL_ENV}

COPY src/ska_oso_services ./src/ska_oso_services

CMD ["fastapi", "run", "src/ska_oso_services/app.py", "--port", "80"]