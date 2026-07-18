# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Aura Sidecar with complete FunASR support.

This spec ensures all FunASR modules are properly collected, including:
- Tokenizers (sentencepiece, char, word, etc.)
- Frontends (wav_frontend, whisper_frontend, etc.)
- Models (sense_voice, fsmn_vad, normalize, specaug, etc.)
- Data files from funasr and modelscope
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all FunASR submodules to ensure @tables.register decorators run
funasr_hidden_imports = collect_submodules('funasr')
modelscope_hidden_imports = collect_submodules('modelscope')
faster_whisper_hidden_imports = collect_submodules('faster_whisper')

# Collect data files
funasr_datas = collect_data_files('funasr')
modelscope_datas = collect_data_files('modelscope')
faster_whisper_datas = collect_data_files('faster_whisper')

# Critical FunASR modules that must be explicitly included
critical_imports = [
    # Tokenizers
    'funasr.tokenizer.sentencepiece_tokenizer',
    'funasr.tokenizer.char_tokenizer',
    'funasr.tokenizer.word_tokenizer',
    'funasr.tokenizer.phoneme_tokenizer',

    # Frontends
    'funasr.frontends.wav_frontend',
    'funasr.frontends.default',

    # Models
    'funasr.models.sense_voice.model',
    'funasr.models.fsmn_vad_streaming.model',
    'funasr.models.fsmn_vad_streaming.encoder',

    # Normalize
    'funasr.models.normalize.global_mvn',
    'funasr.models.normalize.utterance_mvn',

    # Specaug
    'funasr.models.specaug.specaug',
    'funasr.models.specaug.mask_along_axis',

    # Encoder components
    'funasr.models.transformer.encoder',
    'funasr.models.transformer.attention',

    # PyTorch and torchaudio
    'torch',
    'torchaudio',
    'torch.nn',
    'torch.nn.functional',
]

a = Analysis(
    ['aura/sidecar_entry.py'],
    pathex=[],
    binaries=[],
    datas=funasr_datas + modelscope_datas + faster_whisper_datas,
    hiddenimports=funasr_hidden_imports + modelscope_hidden_imports + faster_whisper_hidden_imports + critical_imports,
    hookspath=[],
    hooksconfig={},
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
    [],
    name='aura-sidecar-x86_64-pc-windows-msvc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
