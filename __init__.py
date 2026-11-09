"""Hermes discovers this entry point when enabling the Hermie plugin."""

def register(ctx):
    from .hermie import register as register_hermie
    register_hermie(ctx)
