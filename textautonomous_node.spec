# textautonomous_node.spec
block_cipher = None

a = Analysis(
    ['run_api.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('ui_dist', 'ui_dist'),
    ],
    hiddenimports=[
        'uvicorn',
        'uvicorn.workers',
        'fastapi',
        'pydantic',
        'jinja2',
        'starlette',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='textautonomous_node',
    debug=False,
    strip=False,
    upx=False,
    console=True,
)
