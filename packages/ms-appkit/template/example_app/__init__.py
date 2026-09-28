from example_app._version import __version__

APP_NAME = "Example Tool"
GITHUB_REPO = "Machine-Saver-Inc/example-tool"
SLUG = "example-tool"

# Public or private: decided before the first line of code (skill section 1a).
# A private program also says how it signs in -- and because those values
# identify Machine Saver's infrastructure, it keeps them in a module of its own
# in its own private repository, never here:
#
#     VISIBILITY = "private"
#     from example_app._private import PRIVATE    # a PrivateConfig
VISIBILITY = "public"
PRIVATE = None

__all__ = ["__version__", "APP_NAME", "GITHUB_REPO", "SLUG", "VISIBILITY", "PRIVATE"]
