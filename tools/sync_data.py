"""Bundle the canonical root resources in the wheel. Run before wheel creation."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
for name in ('configs','reference','docs','prompts'):
    shutil.copytree(root/name,root/'src/ecowalk_drive_aiplay/data'/name,dirs_exist_ok=True)
for name in ('LICENSE','NOTICE','THIRD_PARTY_NOTICES.md','README.md'):
    shutil.copyfile(root/name,root/'src/ecowalk_drive_aiplay/data'/name)
