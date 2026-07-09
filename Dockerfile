ARG BUILD_IMAGE="artefact.skao.int/ska-build-python:0.5.0"
ARG RUNTIME_BASE_IMAGE="artefact.skao.int/ska-python:0.2.5"

FROM $BUILD_IMAGE AS requirements

WORKDIR /app

COPY uv.lock pyproject.toml ./

# Install dependencies only (no project code) so this layer is cached between
# source-only changes.
RUN uv sync --frozen --no-dev --no-install-project

FROM $RUNTIME_BASE_IMAGE AS runtime

ENV APP_USER="tango"
ENV APP_DIR="/app"

RUN adduser $APP_USER --disabled-password --home $APP_DIR

WORKDIR $APP_DIR

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY --chown=$APP_USER:$APP_USER --from=requirements ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# Copy and install the application source:
COPY --chown=$APP_USER:$APP_USER pyproject.toml README.md uv.lock ./
COPY --chown=$APP_USER:$APP_USER ./src ./src

# Install only the project itself (deps already in .venv from requirements stage)
RUN uv sync --frozen --no-dev --no-editable

# Add source to PYTHONPATH so Python can locate the package for imports
ENV PYTHONPATH="${PYTHONPATH}:/app/src"

USER ${APP_USER}

CMD ["uvicorn", \
    "ska_oso_services.app:main", \
    "--host", "0.0.0.0", \
    "--port", "5000", \
    "--proxy-headers" \
]
