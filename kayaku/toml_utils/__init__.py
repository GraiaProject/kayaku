def validate_data(data: dict) -> None:
    for k, v in data.items():
        if not isinstance(k, str):
            raise ValueError(f"{data} contains TOML-incompliant key!")
        elif isinstance(v, dict):
            validate_data(v)
        elif isinstance(v, list):
            [validate_data(s) for s in v if isinstance(s, dict)]
        elif v is None:
            raise TypeError(f"{data} contains None!")
