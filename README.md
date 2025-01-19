# Pramaana

A minimalist command-line reference manager that works with BibTeX files and the Zotero translation server.

Basically works like Zotero with BetterBibTeX plus Zotmoov (or the earlier Zotfile).

(basically everything was written by Claude -- under construction, nothing to install yet)

## Installation

The recommended way to install Pramaana is using pipx:

```bash
pipx install pramaana
pramaana-install-completions # to install shell completions; see below though
```

This will install Pramaana in an isolated environment while making the `pramaana` command available globally.

## Prerequisites

Pramaana requires the Zotero translation server to be running for URL-based reference imports. You can start it using Docker:

```bash
docker pull zotero/translation-server
docker run -d -p 1969:1969 --rm --name translation-server zotero/translation-server
```

## Usage

Main commands:

```bash
# Create a new reference
# [Omit `--from` to write in a bib file manually in your default text editor. Use `--attach` without any arguments (i.e. omit `paper.pdf`) to attach the latest item in `~/Downloads` (can be configured, see later).]
pramaana new cs/ai_books/sutton_barto --from https://books.google.com/books?id=GDvW4MNMQ2wC --attach paper.pdf

# Update a reference:
pramaana edit cs/ai_books/sutton_barto --from https://books.google.com/books?id=GDvW4MNMQ2wC --attach paper.pdf

# Run all configured exports (omit arguments to run all exports, see configuration below):
pramaana export id1 id2

# Search for text
pramaana grep "sutton" cs/ # supports all grep options, but must be given at end
pramaana grep "sutton" cs/ --include="*.bib" # to only search .bib files (rather than e.g. pdf)

# Import from Zotero:
pramaana import /path/to/zotero_dir
```

Basic commands (all of these support the basic options supported by the commands they wrap, e.g. `rm -rf`):

```bash
pramaana ls # or pramaana ls /path/to/subdir
pramaana rm path/to/subdir
pramaana trash path/to/subdir # if trash-cli is installed
pramaana show cs/ai_books/sutton_barto/ # shows bibliographic content
pramaana open cs/ai_books/sutton_barto/paper.pdf # opens file or directory in default application
```

## Configuration

Pramaana stores its configuration in `~/.pramaana/config.json`. The default configuration can be customized:

```python
{
    "storage_format": "bib",  # or "csl"
    "attachment_mode": "cp",  # cp, mv, or ln
    "attachment_watch_dir": "~/Downloads",
    "pramaana_path": "~/.pramaana_data",  # default location for references
    "exports": {
        "everything": { # give an ID for each export
            "source": ["/.exports/*"],
            "destination": "~/.pramaana_data/.exports/all_refs.bib",
        }
    },
}
```

`source` for exports takes gitignore style patterns to exclude and include folders 

## Shell Completion

You can get:

- Command completion: `pramaana <tab>` shows all available commands
- Path completion: `pramaana show cs/<tab>` shows subdirectories
- Export completion: `pramaana export <tab>` shows configured export names

After installing, run

```bash
pramaana-install-completions
```
Then for bash, add to your `~/.bashrc`:

```bash
if [ -d ~/.local/share/bash-completion/completions ]; then
    for f in ~/.local/share/bash-completion/completions/*; do
        . "$f"
    done
fi
```

For zsh, add to your `~/.zshrc`:

```zsh
fpath=(~/.zsh/completion $fpath)
autoload -Uz compinit
compinit
```

This does add like half a second to zsh startup time though (bash seems fine).

## Development

To set up a development environment:

```bash
git clone https://github.com/abhimanyupallavisudhir/pramaana.git
cd pramaana
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e ".[dev]"
```

## TODO

- [x] make the `.pramaana` references folder configurable
- [x] make sure `pramaana edit` works as intended
- [x] `pramaana export id` to run only some exports
- [x] `pramaana ls`, `pramaana rm`, `pramaana trash`, `pramaana show`, `pramaana open`
- [x] make things work nicely with autocomplete, zsh etc.
- [ ] remove the csl option we don't want it
- [x] ~~Make find command work within folders~~ changed to grep
- [ ] Make sure importing from Zotero works
- [ ] Package it to automatically start the docker process