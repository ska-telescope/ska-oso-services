# Based on https://developer.skatelescope.org/en/latest/tools/containers/base-images.html#example-dockerfile-uv
ARG BUILD_IMAGE="artefact.skao.int/ska-build-python:0.5.0"
ARG RUNTIME_BASE_IMAGE="artefact.skao.int/ska-python:0.2.5"

FROM $BUILD_IMAGE AS requirements

WORKDIR /src

COPY uv.lock pyproject.toml ./

RUN uv sync --frozen --no-dev --no-install-project

FROM $RUNTIME_BASE_IMAGE

ENV APP_USER="tango"

RUN adduser $APP_USER --disabled-password

WORKDIR /src

ENV VIRTUAL_ENV=/src/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY --from=requirements ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY ./src/ska_oso_services ./ska_oso_services

# Add source code to PYTHONPATH so Python can find the package
ENV PYTHONPATH=${PYTHONPATH}:/src/

USER ${APP_USER}

CMD ["uvicorn", \
    "ska_oso_services.app:main", \
    "--host", "0.0.0.0", \
    "--port", "5000", \
    "--proxy-headers" \
]
