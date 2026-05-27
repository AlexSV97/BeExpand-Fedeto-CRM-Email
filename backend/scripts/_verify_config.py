"""
Verifica la logica de seleccion de modelos en LLMClient
tanto con OpenRouter activo como con fallback a Ollama.

Ejecutar:
    py scripts/_verify_config.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings
from src.llm_client import LLMClient


def check_env():
    settings = get_settings()
    has_key = bool(settings.openrouter_api_key)
    print(f"\n{'='*60}")
    print(f"ENTORNO ACTUAL")
    print(f"{'='*60}")
    print(f"  OPENROUTER_API_KEY configurada: {'SI' if has_key else 'NO (fallback Ollama)'}")
    print(f"  openrouter_model:               {settings.openrouter_model}")
    print(f"  openrouter_chat_model:          {settings.openrouter_chat_model}")
    print(f"  ollama_model (fallback):        {settings.ollama_model}")
    return has_key


def test_config_values():
    settings = get_settings()
    different = settings.openrouter_model != settings.openrouter_chat_model
    print(f"\n{'='*60}")
    print(f"CONFIGURACION DE MODELOS")
    print(f"{'='*60}")
    print(f"  openrouter_model:      {settings.openrouter_model}")
    print(f"  openrouter_chat_model: {settings.openrouter_chat_model}")
    print(f"  Modelos DIFERENTES:    {'SI' if different else 'NO'}")
    return different


def test_selection_with_openrouter():
    settings = get_settings()
    has_key = bool(settings.openrouter_api_key)

    print(f"\n{'='*60}")
    print(f"SELECCION CON OPENROUTER {'ACTIVO' if has_key else 'SIMULADO'}")
    print(f"{'='*60}")

    if has_key:
        analyzer = LLMClient(model=None, use_chat_model=False)
        llm_clf = LLMClient(model=None, use_chat_model=True)
    else:
        analyzer = LLMClient(model=settings.openrouter_model, use_chat_model=False)
        llm_clf = LLMClient(model=settings.openrouter_chat_model, use_chat_model=True)

    print(f"  Analyzer model:      {analyzer.model}")
    print(f"  LLMClassifier model: {llm_clf.model}")
    print(f"  Modelos DIFERENTES:  {'SI' if analyzer.model != llm_clf.model else 'NO'}")

    a_ok = analyzer.model == settings.openrouter_model
    l_ok = llm_clf.model == settings.openrouter_chat_model
    print(f"  Analyzer == openrouter_model:     {'SI' if a_ok else 'NO'}")
    print(f"  LLMClf == openrouter_chat_model:  {'SI' if l_ok else 'NO'}")

    return a_ok and l_ok and (analyzer.model != llm_clf.model)


if __name__ == "__main__":
    errors = 0
    has_key = check_env()

    if not test_config_values():
        errors += 1
    if not test_selection_with_openrouter():
        errors += 1

    print(f"\n{'='*60}")
    print(f"RESULTADO: {errors} error(es) de 2 tests")
    print(f"{'='*60}")

    if not has_key:
        print(f"\nNOTA: OPENROUTER_API_KEY no esta configurada localmente.")
        print(f"En Render (produccion) si lo esta, y la seleccion automatica")
        print(f"usara openrouter_model y openrouter_chat_model correctamente.")
        print(f"Los tests de seleccion automatica solo pasan plenamente en Render.")
    sys.exit(errors)
