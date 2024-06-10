"""
Entry point for application
"""
import logging

import sentry_sdk
from gunicorn import glogging
from ska_ser_logging import configure_logging, get_default_formatter

from ska_oso_services import create_app

# Comes from https://skao-7j.sentry.io/settings/projects/oso-services/keys/
SENTRY_DSN = "https://b3fc20cf2b04b13efad0fec41a9682c6@o4507377535287296.ingest.de.sentry.io/4507405976797264"  # fmt: skip # pylint # noqa

# https://docs.sentry.io/platforms/python/integrations/flask/
sentry_sdk.init(
    dsn=SENTRY_DSN,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100%
    # of sampled transactions.
    # We recommend adjusting this value in production.
    profiles_sample_rate=1.0,
)

app = create_app()


class UniformLogger(glogging.Logger):
    def setup(self, cfg):
        # override the configuration but inherit gunicorn logging level
        super().setup(cfg)
        configure_logging(level=self.loglevel)

        # Override gunicorn format with SKA.
        self._set_handler(self.error_log, cfg.errorlog, get_default_formatter())


if __name__ == "__main__":
    app.run(host="0.0.0.0")
else:
    # presume being run from gunicorn
    # use gunicorn logging level for app and module loggers
    gunicorn_logger = logging.getLogger("gunicorn.error")
    app.app.logger.setLevel(gunicorn_logger.level)
    logger = logging.getLogger("ska_db_oda")
    logger.setLevel(gunicorn_logger.level)
