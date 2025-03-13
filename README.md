# Pramaana

The great thing about Zotero is its actively-maintained translation server (i.e. which parses a webpage and gets its metadata to generate a bib file). The thing I don't like is its client. Ideally you want references to be sorted into nested folders, along with corresponding pdfs etc. -- then you can just move them around or edit them however, in your terminal, file manager whatever without doing tons of point-and-click operations in Zotero client.

`pramaana` is a minimalist command-line reference manager that works with BibTeX files and the Zotero translation server. Basically works like Zotero with BetterBibTeX plus Zotmoov (or the earlier Zotfile).

In theory this is the perfect and optimal reference manager. Unfortunately it turns out [the published Zotero Translation Server module doesn't work as well as what Zotero actually uses](https://github.com/zotero/translation-server/issues/179). Hopefully that's one day fixed, and then this will really be great.

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
# 1) Omit `--from` to write in a bib file manually in vim, with a pre-
#    specified template given by --template=article, book, web etc.
#    (can be configured, see later)
# 2) Use `--attach` without any arguments (i.e. omit `paper.pdf`) to 
#    attach the latest item in `~/Downloads`
#    (can be configured, see later).
# 3) Use `--attach 3` (or any positive integer) to attach the latest 3
#    items in `~/Downloads`
pramaana new cs/ai_books/sutton_barto --from https://books.google.com/books?id=GDvW4MNMQ2wC --attach paper.pdf
pramaana new cs/ai_books/sutton_barto --template=book --attach paper.pdf
pramaana new cs/ai_books/sutton_barto --attach
pramaana new cs/ai_books/sutton_barto --attach 3

# Update a reference:
pramaana edit cs/ai_books/sutton_barto --from https://books.google.com/books?id=GDvW4MNMQ2wC --attach paper.pdf

# Run all configured exports (omit arguments to run all exports, see configuration below):
# pramana export is called automatically after any pramana new, edit, rm, trash, mv or cp operations
# but if you change anything outside the pramana command line, you'll want to run it afterward
pramaana export id1 id2

# Search for text
pramaana grep "sutton" cs/ # supports all grep options, but must be given at end
pramaana grep "sutton" cs/ --include="*.bib" # to only search .bib files (rather than e.g. pdf)

# Import from Zotero:
# NOTE: see below for how to export your Zotero library in a way that can be imported into Pramana
pramaana import /path/to/special_bbt_export.bib
```

Basic commands (all of these support the basic options supported by the commands they wrap, e.g. `rm -rf`, but the options need to be added at the *end*):

```bash
pramaana ls # or pramaana ls /path/to/subdir
pramaana rm path/to/subdir
pramaana trash path/to/subdir # if trash-cli is installed
pramaana mv path1 path2
pramaana cp path1 path2
pramaana ln path1 path2 -s
pramaana show cs/ai_books/sutton_barto/ # shows bibliographic content
pramaana open /path/to/file/or/subdir # opens file or directory in default application; omit arguments to just open the `pramaana_path` folder
```

## Configuration

Pramaana stores its configuration in `~/.pramaana/config.json`. The default configuration can be customized:

```python
{
    "storage_format": "bib",  # only bib is supported for now
    "attachment_mode": "cp",  # cp, mv, or ln
    "attachment_watch_dir": "~/Downloads",
    "pramaana_path": "~/.pramaana_data",  # default location for references
    "translation_server": "http://localhost:1969",  
    "exports": {
        "everything": { # give an ID for each export
            "source": ["/.exports/*"],
            "destination": "~/.pramaana_data/.exports/all_refs.bib",
        }
    },
}
```

`source` for exports takes gitignore style patterns to exclude and include folders.

In addition you can modify the default templates for the `pramaana new ... --template=` option by storing/editing them as `~/.pramaana/templates/article.bib` etc. (The default templates will be dumped in `~./pramaana/templates/` after the first run; you can inspect them beforehand in `src/pramaana/core.py::DEFAULT_TEMPLATES`.)

## Shell Completion

You can get:

- Command completion: `pramaana <tab>` shows all available commands
- Path completion: `pramaana show cs/<tab>` shows subdirectories
- Export completion: `pramaana export <tab>` shows configured export names
- Template completion: `pramaana new bla/foo/bar --template <tab>` shows all available templates

[NOTE: `--template=<tab>` and `--template<tab>` also work on zsh but not on bash. This is because Claude wrote them and it doesn't seem important enough to bother manually inspecting; just use `--template <tab>` i.e. with space, on bash.]

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

If you're using `oh-my-zsh`, **this will slow down your startup time**. You should instead just add

```zsh
fpath=(~/.zsh/completion $fpath)
```

*before* `source $ZSH/oh-my-zsh.sh`.

## Importing your references

To import from Zotero (or elsewhere), we will need a special kind of .bib export which, for each bib entry, contains the following fields:
- `file = {/path/to/attachment.pdf;/path/to/other_attachment.html}`
- `collection = {/collection/subcollection/subsubcollection}`

To get this with Zotero you can use the [BetterBibTeX](https://github.com/retorquere/zotero-better-bibtex) plugin with some special settings.

1) download [here](https://github.com/retorquere/zotero-better-bibtex/releases/latest) then in zotero "install plugin from file"

2) then in the plugin settings for BetterBibTeX, add this postscript:

```javascript
if (Translator.BetterTeX && zotero.collections) {
function path(key) {
    const coll = Translator.collections[key]
    if (!coll) return ''
    return `${path(coll.parent)}/${coll.name}`
}

zotero.collections.forEach((key, i) => {
    tex.add({ name: `collection${i > 0 ? i : ''}`, value: path(key) })
})
}
```

3. set this citation key formula in the BBT plugin settings: `(auth.lower + shorttitle(3,3) + year).replace("@", "")` (I think this is necessary, not sure what the default is)

4. Select `My Library` in Zotero, then `File -> Export Library...`, select `Format: BetterBibTeX`, leave everything unchecked except maybe `worker`, press `OK`.

5. Save the bib file, then import it as

```bash
pramaana import /path/to/special_bbt_import.bib [--via ln|cp|mv]
```

`--via` determines how the attachments are copied over -- they can be hardlinked, copied, or moved. Default is `ln`, which is instant like `mv` as it does not require data to be duplicated, but like `cp` retains the original files untouched (you can still delete the original files safely, as deletion just unlinks the pointers from the data.)

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
- [x] Make sure importing from Zotero works
- [ ] [Make sure translation server works for our needs](https://github.com/zotero/translation-server/issues/179)

WONTFIX:
- [x] ~~Make find command work within folders~~ changed to grep
- [ ] ~~Package it to automatically start the docker process~~
- [ ] ~~remove the `storage_format` option we don't want it~~