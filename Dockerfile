# This Dockerfile taken heavily from FastAPI docs:
# https://fastapi.tiangolo.com/deployment/docker/#build-a-docker-image-for-fastapi
# and this blog post about Poetry in containers:
# https://medium.com/@albertazzir/blazing-fast-python-docker-builds-with-poetry-a78a66f5aed0


## The builder image, used to build the virtual environment
ARG BUILD_IMAGE="artefact.skao.int/ska-build-python:0.3.1"
ARG RUNTIME_BASE_IMAGE="artefact.skao.int/ska-python:0.2.3"

FROM $BUILD_IMAGE AS buildenv

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

ENV APP_DIR="/app"

WORKDIR $APP_DIR

COPY pyproject.toml poetry.lock ./

# Install no-root here so we get a docker layer cached with dependencies
# but not app code, to rebuild quickly.
RUN poetry install --without dev --no-root && rm -rf $POETRY_CACHE_DIR

# The runtime image, used to just run the code provided its virtual environment
FROM $RUNTIME_BASE_IMAGE AS runtime

ENV APP_USER="tango"
ENV APP_DIR="/app"

RUN adduser $APP_USER --disabled-password --home $APP_DIR

WORKDIR $APP_DIR

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY --chown=$APP_USER:$APP_USER --from=buildenv ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# Now we copy and install the application code:
COPY pyproject.toml poetry.lock README.md ./
COPY --chown=$APP_USER:$APP_USER ./src ./src

RUN python -m pip --require-virtualenv install --no-deps -e .

USER ${APP_USER}

CMD ["uvicorn", \
    "ska_oso_services.app:main", \
    "--host", "0.0.0.0", \
    "--port", "5000", \
    # Trust TLS headers set by nginx ingress:
    "--proxy-headers" \
]
