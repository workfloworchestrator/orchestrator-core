import pathlib
import tempfile

from orchestrator.services.translations import generate_translations
from orchestrator.settings import app_settings


def test_generate_translations_empty():
    assert generate_translations("") == {}


def test_generate_translations():
    assert generate_translations("en-GB")


def test_generate_translations_custom_file():
    old_value = app_settings.TRANSLATIONS_DIR
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(f"{temp_dir}/nl-NL.json", "w") as temp_file:
                temp_file.write("[]")

            app_settings.TRANSLATIONS_DIR = pathlib.Path(temp_dir)

            assert generate_translations("nl-NL") == {}

            with open(f"{temp_dir}/nl-NL.json", "w") as temp_file:
                temp_file.write('{"foo": "bar"}')

            assert generate_translations("nl-NL") == {"foo": "bar"}

            app_settings.TRANSLATIONS_DIR = old_value

    finally:
        app_settings.TRANSLATIONS_DIR = old_value
