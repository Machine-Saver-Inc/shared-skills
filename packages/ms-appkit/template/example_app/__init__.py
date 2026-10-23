from example_app._version import __version__

APP_NAME = "Example Tool"
GITHUB_REPO = "Machine-Saver-Inc/example-tool"
SLUG = "example-tool"

# Public or private: decided before the first line of code (skill section 1a).
# A NEW PROGRAM IS PRIVATE unless it is meant for people outside Machine Saver;
# its releases then go to the Machine Saver release store. This template is
# public only because shared-skills is a public repository and must not carry
# the family's sign-in settings. For a private program write
#
#     VISIBILITY = "private"
#     from example_app._private import PRIVATE    # a PrivateConfig
#
# copy _private.py from an existing private program (airvibe-power-profiler),
# and use .github/workflows/release-private.yml as release.yml.
VISIBILITY = "public"
PRIVATE = None

__all__ = ["__version__", "APP_NAME", "GITHUB_REPO", "SLUG", "VISIBILITY", "PRIVATE"]
