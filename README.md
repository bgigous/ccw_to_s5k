# CCW To S5K

This is a tool used to convert components of a Connected Components Workbench project to Studio 5000 Logix Designer components. This is currently in *beta*.

**Note:** This project is in no way affiliated with Rockwell Automation.

## Getting Started

Clone the repository, then create a virtual environment and install packages:

```bash
$ python -m venv .venv
$ . .venv/bin/activate
# if on Windows
# > . .venv/Scripts/activate
$ pip install -r requirements.txt
```

See [README](CCW/README.md) in the `CCW` folder for exporting project tags.

Then, run the tool:

```bash
$ python convert.py
```

Or you can specify custom CCW and S5K paths:

```bash
$ python convert.py <CCW files path> <S5K converted files path>
```

## Current Functionality

This tool currently can only hand CCW variables with basic types: INT, REAL, etc. It can also handle TON and TOFF timer datatypes. Tag import will fail with other datatypes.

## TODO

- [ ] For S5K program output, also convert CCW structured text
  - Note: Can be found through `<PouBody>` tag in certain `*.isaxml` files

## Contributing

Please feel free to contribute with issues and pull requests.

## Supported Hardware

This tool has only been tested with the following PLCs:

- Micro870 (Micro800 series)
- 5069-L320ER (CompactLogix series)
