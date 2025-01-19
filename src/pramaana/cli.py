import argparse
import os
import sys
import traceback
from .core import Pramaana, PramaanaError

def main():
    parser = argparse.ArgumentParser(description='Pramaana Reference Manager')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # new command
    new_parser = subparsers.add_parser('new', help='Create new reference')
    new_parser.add_argument('path', help='Reference path (e.g. cs/ai_books/sutton_barto)')
    new_parser.add_argument('--from', dest='source', help='Source URL or BibTeX file')
    new_parser.add_argument('--attach', nargs='?', const='', help='Attachment file path (uses latest file from watch dir if no path given)')
    
    # edit command
    edit_parser = subparsers.add_parser('edit', help='Edit existing reference')
    edit_parser.add_argument('path', help='Reference path')
    edit_parser.add_argument('--from', dest='source', help='Source URL or BibTeX file')
    edit_parser.add_argument('--attach', nargs='?', const='', help='Attachment file path (uses latest file from watch dir if no path given)')
    
    # find command
    find_parser = subparsers.add_parser('find', help='Search for references')
    find_parser.add_argument('query', help='Search query')

    grep_parser = subparsers.add_parser('grep', help='Search references using grep')
    grep_parser.add_argument('pattern', help='Search pattern')
    grep_parser.add_argument('path', nargs='?', help='Path to search in')
    grep_parser.add_argument('grep_args', nargs=argparse.REMAINDER, 
                           help='Additional arguments for grep (e.g. -i for case-insensitive)')
    
    # import command
    import_parser = subparsers.add_parser('import', help='Import from Zotero')
    import_parser.add_argument('zotero_dir', help='Path to Zotero data directory')

    # export command
    export_parser = subparsers.add_parser('export', help='Run configured exports')
    export_parser.add_argument('exports', nargs='*', help='Names of specific exports to run. If none provided, runs all exports.')


    # ls command
    ls_parser = subparsers.add_parser('ls', help='List references')
    ls_parser.add_argument('path', nargs='?', help='Subdirectory to list')
    ls_parser.add_argument('ls_args', nargs=argparse.REMAINDER, help='Additional arguments for ls')

    # rm command
    rm_parser = subparsers.add_parser('rm', help='Remove a file or directory')
    rm_parser.add_argument('path', help='Path to remove')
    rm_parser.add_argument('rm_args', nargs=argparse.REMAINDER, help='Additional arguments for rm')

    # trash command
    trash_parser = subparsers.add_parser('trash', help='Move a file or directory to trash')
    trash_parser.add_argument('path', help='Path to move to trash')
    trash_parser.add_argument('trash_args', nargs=argparse.REMAINDER, help='Additional arguments for trash-cli')

    # show command (similar to cat)
    show_parser = subparsers.add_parser('show', help='Show contents of a file or directory')
    show_parser.add_argument('path', help='Path to show')
    show_parser.add_argument('show_args', nargs=argparse.REMAINDER, help='Additional arguments for cat')

    # open command
    open_parser = subparsers.add_parser('open', help='Open a file or directory')
    open_parser.add_argument('path', help='Path to open')
    open_parser.add_argument('open_args', nargs=argparse.REMAINDER, help='Additional arguments for xdg-open')

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        pramaana = Pramaana()
        
        if args.command in ['new', 'edit']:
            source_is_file = args.source and os.path.exists(os.path.expanduser(args.source))
            bibtex = None
            if source_is_file:
                with open(os.path.expanduser(args.source)) as f:
                    bibtex = f.read()
            
            # Convert None attach to empty string if flag was used
            attachment = None
            if args.attach is not None:  # --attach was used
                attachment = args.attach or ''  # will be '' if no value provided
            
            if args.command == 'new':
                pramaana.new(
                    args.path,
                    source_url=None if source_is_file else args.source,
                    attachment=attachment,
                    bibtex=bibtex
                )
                print(f"Created reference: {args.path}")
            else:
                pramaana.edit(
                    args.path,
                    source_url=None if source_is_file else args.source,
                    attachment=attachment,
                    bibtex=bibtex
                )
                print(f"Updated reference: {args.path}")
                
        elif args.command == 'find':
            results = pramaana.find(args.query)
            if not results:
                print("No matches found")
            else:
                for result in results:
                    print(f"\nReference: {result['path']}")
                    print(f"File: {result['file']}")
                    print("-" * 40)
                    print(result['content'][:200] + "..." if len(result['content']) > 200 else result['content'])

        elif args.command == 'grep':
            pramaana.grep(args.pattern, args.path, args.grep_args)

        elif args.command == 'import':
            print(f"Importing from Zotero directory: {args.zotero_dir}")
            pramaana.import_zotero(args.zotero_dir)

        elif args.command == 'export':
            if args.exports:
                print(f"Running selected exports: {', '.join(args.exports)}")
                pramaana.export(args.exports)
            else:
                print("Running all exports...")
                pramaana.export()

        elif args.command == 'ls':
            try:
                if args.ls_args:  # If additional ls arguments provided, use native ls
                    pramaana.list_refs(args.path, args.ls_args)
                else:  # Otherwise use our nice tree view
                    tree = pramaana.list_refs(args.path)
                    if args.path:
                        print(f"{args.path}")
                    for line in tree:
                        print(line)
            except PramaanaError as e:
                print(f"Error: {str(e)}", file=sys.stderr)
                return 1

        elif args.command == 'rm':
            pramaana.remove(args.path, args.rm_args)

        elif args.command == 'trash':
            pramaana.trash(args.path, args.trash_args)

        elif args.command == 'show':
            if args.show_args:
                pramaana.show(args.path, args.show_args)
            else:
                content = pramaana.show(args.path)
                print(content)

        elif args.command == 'open':
            pramaana.open(args.path, args.open_args)

    except PramaanaError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        return 1
        
    return 0

if __name__ == '__main__':
    sys.exit(main())