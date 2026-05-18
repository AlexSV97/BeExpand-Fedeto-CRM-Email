"""
Router de historial de clasificación.

GET list con filtro email_id.
GET /{id} detail.
POST /retrain — re-entrena BERT con datos reales + revisiones manuales.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ClassificationHistory, User
from src.db.session import get_db

from src.api.deps import get_current_user
from src.api.schemas import ClassificationResponse

router = APIRouter(tags=["classification"])


class RetrainRequest(BaseModel):
    """Parámetros opcionales para re-entrenamiento."""
    epochs: int = 6
    augment_multiplier: int = 5
    synthetic_count: int = 200
    learning_rate: float = 5e-5
    real_only: bool = False


class RetrainResponse(BaseModel):
    """Resultado del re-entrenamiento."""
    status: str
    accuracy: float | None = None
    f1_macro: float | None = None
    train_samples: int | None = None
    test_samples: int | None = None
    real_samples: int | None = None
    training_time_seconds: float | None = None
    classification_report: dict | None = None  # noqa: UP006
    detail: str | None = None
    model_path: str | None = None


@router.get("")
async def list_classifications(
    email_id: str | None = Query(None, description="Filtrar por email"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista historial de clasificaciones con filtro opcional por email_id."""
    base = select(ClassificationHistory)
    count_base = select(func.count(ClassificationHistory.id))

    if email_id:
        base = base.where(ClassificationHistory.email_id == email_id)
        count_base = count_base.where(ClassificationHistory.email_id == email_id)

    total_result = await db.execute(count_base)
    total = total_result.scalar() or 0

    result = await db.execute(
        base.order_by(ClassificationHistory.created_at.desc())
    )
    items = result.scalars().all()

    return {
        "items": [ClassificationResponse.model_validate(c).model_dump() for c in items],
        "total": total,
    }


@router.get("/{classification_id}", response_model=ClassificationResponse)
async def get_classification(
    classification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtiene detalle de una clasificación por ID."""
    result = await db.execute(
        select(ClassificationHistory).where(
            ClassificationHistory.id == classification_id
        )
    )
    classification = result.scalar_one_or_none()
    if classification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classification not found",
        )
    return classification


@router.post("/retrain", response_model=RetrainResponse)
async def retrain_model(
    params: RetrainRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-entrena BERT con datos reales + revisiones manuales.

    Proceso:
    1. Extrae todos los emails clasificados de la BD
    2. Prioriza revisiones manuales (method='manual_review') como ground truth
    3. Aumenta datos reales con sinónimos/barajado/dropout
    4. Genera datos sintéticos balanceados
    5. Fine-tune DistilBERT multilingual
    6. Guarda el modelo en src/classifier/model/

    Parámetros opcionales:
    - epochs: número de épocas (defecto: 6)
    - augment_multiplier: multiplicador de aumento (defecto: 5)
    - synthetic_count: muestras sintéticas (defecto: 200)
    - learning_rate: tasa de aprendizaje (defecto: 5e-5)
    - real_only: solo datos reales (defecto: false)
    """
    try:
        from src.training.pipeline import retrain_from_db

        metrics = await retrain_from_db(
            db=db,
            epochs=params.epochs,
            augment_multiplier=params.augment_multiplier,
            synthetic_count=params.synthetic_count,
            learning_rate=params.learning_rate,
            real_only=params.real_only,
        )

        if metrics.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=metrics.get("detail", "Error en el entrenamiento"),
            )

        return RetrainResponse(**metrics)

    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cargando pipeline de entrenamiento: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante el re-entrenamiento: {e}",
        )
