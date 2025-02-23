import os
import shutil
from pathlib import Path

def main():
    """Install shell completions to user directory"""
    # Get package directory
    package_dir = Path(__file__).parent
    completion_dir = package_dir / 'data' / 'completions'
    
    if not completion_dir.exists():
        raise FileNotFoundError(
            f"Completion files not found in {completion_dir}. "
            "This might be a packaging issue."
        )
    
    # Install bash completion
    bash_dir = Path.home() / '.local/share/bash-completion/completions'
    bash_dir.mkdir(parents=True, exist_ok=True)
    
    bash_completion = completion_dir / 'pramaana-completion.bash'
    if not bash_completion.exists():
        raise FileNotFoundError(f"Bash completion file not found: {bash_completion}")
        
    shutil.copy2(
        bash_completion,
        bash_dir / 'pramaana'
    )
    print(f"Installed bash completion to {bash_dir / 'pramaana'}")
    
    # Install zsh completion
    zsh_dir = Path.home() / '.zsh/completion'
    zsh_dir.mkdir(parents=True, exist_ok=True)
    
    zsh_completion = completion_dir / '_pramaana'
    if not zsh_completion.exists():
        raise FileNotFoundError(f"Zsh completion file not found: {zsh_completion}")
        
    shutil.copy2(
        zsh_completion,
        zsh_dir / '_pramaana'
    )
    print(f"Installed zsh completion to {zsh_dir / '_pramaana'}")
    
    print("""
Completions installed!

For bash, add to your ~/.bashrc:
    if [ -d ~/.local/share/bash-completion/completions ]; then
        for f in ~/.local/share/bash-completion/completions/*; do
            . "$f"
        done
    fi

For zsh, add to your ~/.zshrc:
    fpath=(~/.zsh/completion $fpath)
    autoload -Uz compinit
    compinit

If you're using oh-my-zsh, that would slow down your startup time. You should instead just add
          
    fpath=(~/.zsh/completion $fpath)

Before the `source $ZSH/oh-my-zsh.sh` line in your ~/.zshrc.
    """)

if __name__ == '__main__':
    main()


