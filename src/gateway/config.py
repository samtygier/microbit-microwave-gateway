from os import PathLike
from pathlib import Path
import tomllib

def get_config(path: PathLike | None = None) -> dict[dict[str, str | int]]:
    if path is not None:
        path = Path(path)
    else:
        path = Path(__file__).parent.parent.parent / "config.toml"

    config = tomllib.load(path.open('rb'))

    return config
