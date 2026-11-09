"""Hermes discovers this entry point when enabling the Hermie plugin."""


def register(ctx):
    from .hermie_plugin import register as register_hermie
    register_hermie(ctx)
