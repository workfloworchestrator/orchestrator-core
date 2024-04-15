from contextlib import contextmanager

from oauth2_lib.settings import oauth2lib_settings


@contextmanager
def mutation_authorization():
    old_oauth2_active = oauth2lib_settings.OAUTH2_ACTIVE
    old_mutations_enabled = oauth2lib_settings.MUTATIONS_ENABLED

    oauth2lib_settings.OAUTH2_ACTIVE = False
    oauth2lib_settings.MUTATIONS_ENABLED = True

    yield

    oauth2lib_settings.OAUTH2_ACTIVE = old_oauth2_active
    oauth2lib_settings.MUTATIONS_ENABLED = old_mutations_enabled
