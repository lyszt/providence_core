from django.apps import AppConfig
import os, shutil
from pathlib import Path
from django.conf import settings

class PlottingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plotting'

    def ready(self):
        print("[INFO] Removing previous graphs.")


        target: Path = Path(settings.BASE_DIR) / "speech" / "context_manager" / "graphs"
        try:
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"[ERROR] Error removing graphs: {e}")
        
