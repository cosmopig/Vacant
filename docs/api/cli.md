# `vacant.cli`

Console-script entrypoint declared in `pyproject.toml` as
`vacant = "vacant.cli:main"`. Each subcommand maps to a function in
`vacant.cli.commands`; local key / logbook persistence lives in
`vacant.cli.local_store`.

::: vacant.cli.commands

::: vacant.cli.local_store
