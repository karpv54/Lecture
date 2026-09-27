"""Create a source-only ZIP with README at its root, including safe dotfiles."""
import argparse
import hashlib
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES={'.editorconfig','.gitattributes','.gitignore','README.md','START_HERE.md','CONTRIBUTING.md',
            'START.cmd','SETUP.cmd','CHECK.cmd','launch.ps1'}
DIRECTORIES={'agents','apps','assets','docs','integrations','pipelex','reference','scripts','tests','.github'}
EXCLUDE={'.git','.venv','venv','__pycache__','node_modules','data','recordings','sessions','uploads','logs',
         '.pytest_cache','.mypy_cache','.ruff_cache','work','outputs','dist','build'}
EXTENSIONS={'.py','.md','.txt','.json','.html','.css','.js','.cjs','.mthds','.toml','.yml','.yaml','.svg','.ps1','.cmd'}

def include(path):
    relative=path.relative_to(ROOT)
    if path.is_symlink() or any(part in EXCLUDE for part in relative.parts):return False
    if relative.name.startswith('.env'):
        return relative.as_posix()=='apps/gradio/.env.example'
    if len(relative.parts)==1:return relative.name in ROOT_FILES
    return relative.parts[0] in DIRECTORIES and path.suffix in EXTENSIONS

def build(destination):
    destination=destination.resolve()
    destination.parent.mkdir(parents=True,exist_ok=True)
    files=sorted(p for p in ROOT.rglob('*') if p.is_file() and include(p))
    if not files:raise RuntimeError('No source files')
    with ZipFile(destination,'w',ZIP_DEFLATED) as archive:
        for file in files:archive.write(file,file.relative_to(ROOT).as_posix())
    with ZipFile(destination) as archive:
        names=archive.namelist()
        assert archive.testzip() is None
        assert 'README.md' in names and '.gitignore' in names and 'apps/gradio/.env.example' in names
        assert not any(part in EXCLUDE for name in names for part in Path(name).parts)
        assert not any(Path(name).name.startswith('.env') and name!='apps/gradio/.env.example' for name in names)
    print(f'{len(files)} source files; {destination.stat().st_size:,} bytes')
    print('SHA256 '+hashlib.sha256(destination.read_bytes()).hexdigest())
    return files

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    build(parser.parse_args().destination)
