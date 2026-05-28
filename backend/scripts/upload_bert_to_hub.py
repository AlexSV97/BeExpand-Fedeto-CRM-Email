"""
Sube el modelo BERT fine-tuneado a HuggingFace Hub.

Uso:
    # Primero crea el repo en https://huggingface.co/new
    #   Model name: beexpand-bert-crm
    #   Visibility: Private

    python scripts/upload_bert_to_hub.py

Requiere:
    pip install huggingface_hub
    HUGGINGFACE_TOKEN en .env o variable de entorno
"""

import os
import sys
from pathlib import Path

# Asegurar que podemos importar desde src/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings


def main():
    settings = get_settings()
    token = settings.huggingface_token or os.getenv("HUGGINGFACE_TOKEN")
    model_id = settings.bert_onnx_model_id or os.getenv("HUGGINGFACE_MODEL_ID", "AlexSV97/beexpand-bert-crm")

    if not token:
        print("ERROR: No hay HUGGINGFACE_TOKEN configurado.")
        print("  Añádelo a .env o exporta la variable de entorno.")
        sys.exit(1)

    from huggingface_hub import HfApi

    api = HfApi(token=token)

    # Verificar que el repo existe
    print(f"Verificando repo {model_id}...")
    try:
        info = api.model_info(model_id)
        print(f"  ✓ Repo encontrado: {model_id}")
        print(f"  ├ Privado: {info.private}")
        print(f"  └ Archivos: {[f.rfilename for f in info.siblings]}")
    except Exception:
        print(f"  ✗ El repo {model_id} no existe.")
        print()
        print("  Crea el repo manualmente en:")
        print("    https://huggingface.co/new")
        print("    Type: Model | Name: beexpand-bert-crm | Visibility: Private")
        sys.exit(1)

    # Subir archivos del modelo
    model_dir = Path(__file__).resolve().parent.parent / "src" / "classifier" / "model"
    files = ["config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json"]

    print(f"\nSubiendo modelo desde {model_dir}...")
    for fname in files:
        fpath = model_dir / fname
        if not fpath.exists():
            print(f"  ⚠ {fname} no encontrado, lo salto")
            continue

        size_mb = fpath.stat().st_size / (1024 * 1024)
        print(f"  Subiendo {fname} ({size_mb:.1f} MB)...", end=" ", flush=True)
        api.upload_file(
            path_or_fileobj=str(fpath),
            path_in_repo=fname,
            repo_id=model_id,
            repo_type="model",
        )
        print("✓")

    print(f"\n✅ Modelo subido a: https://huggingface.co/{model_id}")
    print(f"   Ahora en produccion (Render) BERT se descargara automaticamente.")


if __name__ == "__main__":
    main()
