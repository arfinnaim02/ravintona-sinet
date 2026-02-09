#!/usr/bin/env python3
"""
Management utility for the Ravintola Sinet Django project.

This script is a thin wrapper around Django's command‑line
utilities and should be run for administrative tasks such as
migrations, running the development server and creating new
applications. It exists at the top level of the repository so
that it can be executed without having to modify the PYTHONPATH.
"""

import os
import sys


def main() -> None:
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ravintola_sinet.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and available on your PYTHONPATH?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()